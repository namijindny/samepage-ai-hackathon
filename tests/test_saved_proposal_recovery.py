"""Source-linked saved review can be used without another paid Meta request."""
import pytest
from app.conversation import recover_explicit_deadline

TERMS = {"price": "$500", "deadline": "December 10, 2026", "scope": "Build a responsive homepage"}
MESSAGE = {"id": "last-msg", "author": "a", "body": "I propose December 20, 2026, but the price must remain $500"}


def saved_review(message=MESSAGE, *, intent="conditional", observation=True):
    return {
        "last_message_id": message["id"], "last_author": message["author"],
        "intent": intent, "changes": [], "explanation": "The proposal is conditional",
        "observations": [{"message_id": message["id"], "author": message["author"],
                          "kind": "proposal", "quote": "I propose December 20, 2026",
                          "meaning": "Alex proposes the date"}] if observation else [],
        "mode": "meta_muse_spark_1_3",
    }


def test_saved_review_of_explicit_date_with_unchanged_price_is_recovered_without_meta():
    before = saved_review()
    recovered = recover_explicit_deadline(before, MESSAGE, TERMS)
    assert recovered["intent"] == "change_proposal"
    assert recovered["changes"] == [{"field": "deadline", "new_value": "December 20, 2026",
                                     "evidence": "I propose December 20, 2026"}]
    assert recovered["verified_from_saved_evidence"] is True
    assert not before["changes"]  # Saved model report is not changed.


@pytest.mark.parametrize("message,observed", [
    ("I propose December 20, 2026, but the price must remain $600", True),
    ("I propose December 20, 2026, if the client pays me today", True),
    ("I propose December 20, 2026, but I also need $200 more", True),
    ("I propose February 31, 2027, but the price must remain $500", True),
    ("Could we change to December 20, 2026?", True),
    ("I propose December 20, 2026, but the price must remain $500", False),
])
def test_recovery_refuses_unsafe_or_unsupported_cases(message, observed):
    last = {**MESSAGE, "body": message}
    assert recover_explicit_deadline(saved_review(last, observation=observed), last, TERMS)["changes"] == []


def test_recovery_does_not_revise_question_with_proposal_quote():
    assert not recover_explicit_deadline(saved_review(intent="question"), MESSAGE, TERMS)["changes"]


def test_saved_review_can_be_prepared_and_approved_without_second_meta_call(client, monkeypatch):
    result = client.post('/api/cases', json={
        'title': 'Website Development', 'party_a': 'Alex Morgan', 'party_b': 'Sam Lee',
        'price': '$500', 'deadline': 'December 10, 2026', 'scope': 'Build a responsive homepage',
    }).json()
    path = f'/api/cases/{result["case_id"]}'
    a, b = {'X-Party-Key': result['party_a_key']}, {'X-Party-Key': result['party_b_key']}
    assert client.post(path + '/confirm', headers=b).status_code == 200
    msg = client.post(path + '/conversation/messages', headers=a, json={
        'message': MESSAGE['body']
    })
    assert msg.status_code == 201
    stored = msg.json()['conversation']['messages'][-1]

    def fake_analysis(*_):
        return saved_review({**MESSAGE, 'id': stored['id']})
    monkeypatch.setattr('app.main.analyze', fake_analysis)
    assert client.post(path + '/conversation/review', headers=a).status_code == 200

    def do_not_call_meta(*_):
        raise AssertionError('Must not call Meta a second time')
    monkeypatch.setattr('app.main.analyze', do_not_call_meta)
    viewed = client.get(path, headers=a).json()
    assert viewed['conversation']['review_current'] is True
    assert viewed['conversation']['review']['changes'][0]['new_value'] == 'December 20, 2026'
    assert viewed['terms']['deadline'] == 'December 10, 2026'
    assert client.post(path + '/conversation/prepare-amendment', headers=b).status_code == 403
    prepared = client.post(path + '/conversation/prepare-amendment', headers=a)
    assert prepared.status_code == 200, prepared.text
    pending = next(p for p in prepared.json()['proposals'] if p['status'] == 'pending')
    assert pending['changes'][0]['evidence'] == 'I propose December 20, 2026'
    assert prepared.json()['terms']['price'] == '$500'
    assert prepared.json()['terms']['deadline'] == 'December 10, 2026'
    accepted = client.post(path + '/proposals/' + pending['id'] + '/approve', headers=b)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()['terms']['deadline'] == 'December 20, 2026'
    assert accepted.json()['terms']['price'] == '$500'
    assert accepted.json()['audit_valid']
