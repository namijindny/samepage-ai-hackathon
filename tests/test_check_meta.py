from __future__ import annotations

from types import SimpleNamespace

from scripts import check_meta


def test_failure_mapping():
    for status, marker in ((400, "format"), (401, "key"), (402, "billing"), (403, "access"), (404, "endpoint"), (429, "rate limit")):
        error = type("HTTPFailure", (Exception,), {"status_code": status})()
        assert marker in check_meta.explain_failure(error).lower()


def test_diagnostic_calls_model_without_changing_agreement(monkeypatch, capsys):
    monkeypatch.setenv("MODEL_API_KEY", "test-only-key")
    requests = []

    def stub(message, current):
        requests.append((message, current))
        return SimpleNamespace(mode="meta_muse_spark_1_3", intent="change_proposal", changes=[{"field": "deadline", "new_value": "Monday"}])

    monkeypatch.setattr(check_meta, "detect", stub)
    assert check_meta.main() == 0
    output = capsys.readouterr().out
    assert "CONNECTED" in output
    assert "test-only-key" not in output
    assert len(requests) == 1


def test_failure_message_does_not_leak_secrets(monkeypatch, capsys):
    monkeypatch.setenv("MODEL_API_KEY", "very-sensitive-test-key")

    def stub(_message, _current):
        error = type("ModelError", (Exception,), {"status_code": 401})("very-sensitive-test-key")
        raise error

    monkeypatch.setattr(check_meta, "detect", stub)
    assert check_meta.main() == 1
    output = capsys.readouterr().out
    assert "very-sensitive-test-key" not in output
    assert "HTTP 401" in output


def test_distinct_model_response_reasons():
    from app.engine import MetaResponseError
    assert "token limit" in check_meta.explain_failure(MetaResponseError("output_limit"))
    assert "JSON" in check_meta.explain_failure(MetaResponseError("invalid_json"))
