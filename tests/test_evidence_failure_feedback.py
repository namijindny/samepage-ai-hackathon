"""A failed paid review must leave a clear, local error and not imply acceptance."""
from pathlib import Path
from types import SimpleNamespace, ModuleType
import sys
import pytest
from app import evidence
from app.engine import MetaResponseError

ROOT=Path(__file__).resolve().parents[1]


def test_evidence_failure_is_shown_next_to_action():
    js=(ROOT/'web'/'app.js').read_text(encoding='utf8')
    css=(ROOT/'web'/'styles.css').read_text(encoding='utf8')
    assert 'let evidenceReviewError = null' in js
    assert 'role="alert"' in js
    assert 'No decision was made.' in js
    assert 'evidenceReviewError = { itemId, message }' in js
    assert 'reviewed?.evidence_insight' in js
    assert '.evidence-review-error' in css


def test_meta_evidence_output_limit_gets_explicit_error(monkeypatch):
    monkeypatch.setenv('ANALYSIS_MODE','meta')
    monkeypatch.setenv('MODEL_API_KEY','example-private-key')
    monkeypatch.setattr(evidence,'reserve_request',lambda:None)
    seen={}
    class MockChat:
        def create(self,**kwargs):
            seen['tokens']=kwargs['max_completion_tokens']
            return SimpleNamespace(choices=[SimpleNamespace(finish_reason='length',message=SimpleNamespace(content=''))])
    class FakeClient:
        def __init__(self,**kwargs):
            self.chat=SimpleNamespace(completions=MockChat())
    monkeypatch.setitem(sys.modules,'openai',ModuleType('openai'))
    sys.modules['openai'].OpenAI=FakeClient
    with pytest.raises(MetaResponseError, match='output_limit'):
        evidence.review_with_meta([('image',b'image')],'Finished','Check page','')
    assert seen['tokens']==3500


def test_normal_meta_evidence_result_still_works(monkeypatch):
    monkeypatch.setenv('ANALYSIS_MODE','meta')
    monkeypatch.setenv('MODEL_API_KEY','example-private-key')
    monkeypatch.setattr(evidence,'reserve_request',lambda:None)
    class MockChat:
        def create(self,**kwargs):
            return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop',message=SimpleNamespace(content='{"visible":"Shows a page","uncertain":"Backend not tested","next_check":"Try the form"}'))])
    class FakeClient:
        def __init__(self,**kwargs):self.chat=SimpleNamespace(completions=MockChat())
    monkeypatch.setitem(sys.modules,'openai',ModuleType('openai'))
    sys.modules['openai'].OpenAI=FakeClient
    result=evidence.review_with_meta([('image',b'image')],'Finished','Check page','')
    assert result['next_check']=='Try the form'
