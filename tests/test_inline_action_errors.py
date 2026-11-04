"""Browser failures should be shown at the action that triggered them."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_localized_error_helper_is_accessible_and_safe():
    source = (ROOT / 'web' / 'app.js').read_text(encoding='utf-8')
    style = (ROOT / 'web' / 'styles.css').read_text(encoding='utf-8')
    assert 'function showActionError(message, anchor)' in source
    assert "error.setAttribute('role', 'alert')" in source
    assert 'error.textContent = message' in source
    assert 'region.insertAdjacentElement(\'afterend\', error)' in source
    assert '.inline-action-error' in style


def test_delivery_and_agreement_errors_go_next_to_their_action():
    source = (ROOT / 'web' / 'app.js').read_text(encoding='utf-8')
    for snippet in (
        'showActionError(error.message, elements.createForm)',
        'showActionError(error.message, elements.messageForm)',
        'showActionError(error.message, elements.conversationForm)',
        'showActionError(error.message, elements.understandingForm)',
        'showActionError(error.message, elements.manualForm)',
        'showActionError(unchanged ? ',
        'showActionError(error.message, itemForm)',
        'showActionError(error.message, disputeForm)',
        'showActionError(error.message, elements.confirmButton)',
        'showActionError(error.message, button)',
    ):
        assert snippet in source


def test_evidence_review_has_own_nearby_error_and_no_duplicate_global_alert():
    source = (ROOT / 'web' / 'app.js').read_text(encoding='utf-8')
    assert 'evidenceReviewError = { itemId, message };' in source
    section = source.split("const evidenceCheck = event.target.closest('button[data-evidence-check]')", 1)[1].split("const planAction", 1)[0]
    assert 'notify(message, true)' not in section
    assert 'evidence-review-error' in source
