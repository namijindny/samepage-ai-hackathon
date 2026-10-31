from __future__ import annotations

import json
import sys
from types import SimpleNamespace
import pytest

from app.engine import validate_response, detect

CURRENT = {"price": "₦120,000", "deadline": "Friday", "scope": "Repair vehicle engine"}


def output(intent, changes=None, explanation="Review the message"):
    return {"intent": intent, "changes": changes or [], "explanation": explanation}


def change(field, value, evidence, operation="replace", certainty="explicit"):
    return {"field": field, "new_value": value, "evidence": evidence, "operation": operation, "certainty": certainty}


@pytest.mark.parametrize("intent", ["question", "conditional", "rejection", "withdrawal", "no_change", "ambiguous"])
def test_non_proposals_cannot_generate_changes(intent):
    text = "Maybe finish on Monday?"
    result = validate_response(output(intent, [change("deadline", "Monday", "Monday")]), text, CURRENT)
    assert result.intent == intent and not result.changes


def test_correct_arithmetic_is_computed_in_python():
    text = "Please add ₦40,000 to the price."
    result = validate_response(output("change_proposal", [change("price", "₦900,000", "add ₦40,000", "increase")]), text, CURRENT)
    assert result.changes == [{"field": "price", "new_value": "₦160,000", "evidence": "add ₦40,000"}]


def test_claimed_evidence_must_be_substring():
    result = validate_response(output("change_proposal", [change("deadline", "Monday", "finish on Monday")]), "Finish by Saturday", CURRENT)
    assert result.intent == "ambiguous" and result.changes == []


def test_wrong_total_rejected():
    text = "New total is ₦160,000."
    result = validate_response(output("change_proposal", [change("price", "₦999,000", "₦160,000")]), text, CURRENT)
    assert result.intent == "ambiguous" and not result.changes


def test_nonexplicit_changes_rejected():
    result = validate_response(output("change_proposal", [change("deadline", "Monday", "Monday", certainty="uncertain")]), "Maybe Monday", CURRENT)
    assert not result.changes


def test_deadline_quote_supports_value():
    result = validate_response(output("change_proposal", [change("deadline", "Monday", "finish on Monday")]), "I will finish on Monday", CURRENT)
    assert result.changes[0]["new_value"] == "Monday"


def test_changed_scope_not_in_message_is_rejected():
    result = validate_response(output("change_proposal", [change("scope", "Build two houses", "Add paint")]), "Add paint", CURRENT)
    assert not result.changes


def test_actual_meta_path_with_mock_sdk(monkeypatch, tmp_path):
    from app import storage
    from app import usage
    monkeypatch.setattr(storage, "DB", tmp_path / "usage.sqlite3")
    monkeypatch.setenv("MODEL_API_KEY", "mock-test-key")
    monkeypatch.setenv("ANALYSIS_MODE", "meta")
    monkeypatch.setenv("MAX_META_CALLS_PER_DAY", "1")
    calls = []

    class Client:
        def __init__(self, **kwargs):
            assert kwargs["base_url"] == "https://api.meta.ai/v1"
            assert kwargs["max_retries"] == 0
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.complete))

        def complete(self, **kwargs):
            calls.append(kwargs)
            assert kwargs["model"] == "muse-spark-1.3"
            assert kwargs["response_format"]["type"] == "json_schema"
            answer = output("change_proposal", [change("deadline", "Monday", "finish on Monday")])
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(answer)))])

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=Client))
    result = detect("I'll finish on Monday", CURRENT)
    assert result.mode == "meta_muse_spark_1_3"
    assert result.changes[0]["new_value"] == "Monday"
    with pytest.raises(RuntimeError, match="Daily Meta request allowance"):
        detect("I'll finish on Monday", CURRENT)
    assert len(calls) == 1


def test_no_api_key_means_no_model_call(monkeypatch):
    monkeypatch.setenv("ANALYSIS_MODE", "meta")
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="MODEL_API_KEY"):
        detect("Finish on Monday", CURRENT)
