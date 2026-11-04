"""Regressions for private screenshot previews and transparent AI review UI."""
from pathlib import Path
from types import SimpleNamespace
import sys
from types import ModuleType

from app import evidence

ROOT = Path(__file__).resolve().parents[1]


def test_private_image_previews_allowed_by_browser_policy(client):
    page = client.get('/')
    assert page.status_code == 200
    csp = page.headers['content-security-policy']
    assert "img-src 'self' data: blob:" in csp
    assert "script-src 'self'" in csp


def test_review_prompt_does_not_conflate_phone_frame_with_mockup(monkeypatch):
    monkeypatch.setenv('ANALYSIS_MODE', 'meta')
    monkeypatch.setenv('MODEL_API_KEY', 'test-key-only')
    monkeypatch.setattr(evidence, 'reserve_request', lambda: None)
    monkeypatch.setattr(evidence, 'public_page_text', lambda url: ('Homepage and contact link', 'Public HTML only'))
    seen = {}

    class MockChat:
        def create(self, **kwargs):
            seen['prompt'] = kwargs['messages'][0]['content'][0]['text']
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"visible":"A website screenshot is shown","uncertain":"Live interaction was not tested","next_check":"Open the page"}'))])

    class FakeClient:
        def __init__(self, **kwargs):
            seen['model_url'] = kwargs['base_url']
            self.chat = SimpleNamespace(completions=MockChat())

    fake_module = ModuleType('openai')
    fake_module.OpenAI = FakeClient
    monkeypatch.setitem(sys.modules, 'openai', fake_module)
    result = evidence.review_with_meta([('image.jpg', b'test bytes')], 'Homepage finished', 'Mobile menu works', 'https://example.com')
    assert result['mode'] == 'meta_muse_spark_1_3'
    assert 'Do not speculate' in seen['prompt']
    assert 'phone-framed' in seen['prompt']
    assert 'explicit visible evidence' in seen['prompt']
    assert 'cannot verify live behavior' in seen['prompt']
    assert seen['model_url'] == 'https://api.meta.ai/v1'


def test_delivery_ui_has_clear_submission_and_progress_feedback():
    js = (ROOT / 'web' / 'app.js').read_text(encoding='utf8')
    styles = (ROOT / 'web' / 'styles.css').read_text(encoding='utf8')
    assert 'Submit work for review' in js
    assert 'nothing further to submit' in js
    assert 'AI review in progress' in js
    assert 'evidenceReviewPendingId = null' in js
    assert 'role="status"' in js
    assert 'evidence-spinner' in styles
    assert 'prefers-reduced-motion' in styles
