import json
from app.conversation import validate_review
from app import storage

TERMS = {"price": "₦120,000", "deadline": "Friday", "scope": "Repair vehicle engine"}


def example_messages():
    return [
        {"id": "m1", "author": "a", "body": "The current price is ₦120,000.", "created_at": "2026-11-01T00:00:00Z"},
        {"id": "m2", "author": "b", "body": "Can you finish on Monday?", "created_at": "2026-11-01T00:01:00Z"},
        {"id": "m3", "author": "a", "body": "I will finish on Monday. Add ₦40,000 to the price.", "created_at": "2026-11-01T00:02:00Z"},
    ]


def review_data(observations=None, intent="change_proposal", changes=None):
    return {
        "summary": "Possible changes",
        "observations": observations or [],
        "latest": {
            "intent": intent,
            "explanation": "Changes need approval.",
            "changes": changes if changes is not None else [
                {"field": "deadline", "new_value": "Monday", "evidence": "finish on Monday", "operation": "replace", "certainty": "explicit"},
                {"field": "price", "new_value": "₦999,000", "evidence": "Add ₦40,000", "operation": "increase", "certainty": "explicit"},
            ],
        },
    }


def test_evidence_is_attributed_and_unverifiable_claims_are_dropped():
    result = validate_review(review_data([
        {"message_id": "m2", "kind": "question", "quote": "Can you finish on Monday?", "meaning": "A question"},
        {"message_id": "fake", "kind": "confirmation", "quote": "I accept", "meaning": "Not in conversation"},
        {"message_id": "m1", "kind": "proposal", "quote": "I accept", "meaning": "Invented quotation"},
    ]), example_messages(), TERMS)
    assert len(result["observations"]) == 1
    assert result["observations"][0]["author"] == "b"
    assert result["changes"] == [
        {"field": "deadline", "new_value": "Monday", "evidence": "finish on Monday"},
        {"field": "price", "new_value": "₦160,000", "evidence": "Add ₦40,000"},
    ]
    assert "summary" not in result


def test_old_messages_cannot_be_used_to_propose_new_terms():
    msgs = example_messages() + [{"id": "m4", "author": "b", "body": "What about Saturday?", "created_at": "now"}]
    result = validate_review(review_data(intent="question", changes=[
        {"field": "deadline", "new_value": "Monday", "evidence": "finish on Monday", "operation": "replace", "certainty": "explicit"}
    ]), msgs, TERMS)
    assert result["intent"] == "question" and not result["changes"]


def test_unknown_message_quotes_cannot_change_terms():
    wrong = review_data(changes=[
        {"field": "scope", "new_value": "New scope", "evidence": "New scope", "operation": "replace", "certainty": "explicit"}
    ])
    result = validate_review(wrong, example_messages(), TERMS)
    assert result["intent"] == "ambiguous" and not result["changes"]


def test_conversation_is_party_scoped_and_no_terms_are_changed(client, monkeypatch):
    response = client.post('/api/cases', json={
        'title': 'Engine work', 'party_a': 'Amina', 'party_b': 'Bello',
        'price': '₦120,000', 'deadline': 'Friday', 'scope': 'Repair vehicle engine'
    }).json()
    case_id = response['case_id']
    a = {'X-Party-Key': response['party_a_key']}
    b = {'X-Party-Key': response['party_b_key']}
    path = f'/api/cases/{case_id}'
    assert client.post(path+'/conversation/messages', json={'message':'hello'}).status_code == 401
    assert client.post(path+'/conversation/messages', headers={'X-Party-Key':'incorrect'}, json={'message':'hello'}).status_code == 403
    assert client.post(path+'/conversation/messages', headers=a, json={'message':'I can pay ₦120,000.'}).status_code == 201
    assert client.post(path+'/conversation/messages', headers=b, json={'message':'Can you finish on Monday?'}).status_code == 201
    assert client.post(path+'/conversation/messages', headers=a, json={'message':'I will finish on Monday. Add ₦40,000 to the price.'}).status_code == 201
    data = client.get(path, headers=a).json()
    assert [m['author'] for m in data['conversation']['messages']] == ['a','b','a']
    assert not data['conversation']['review_current']
    monkeypatch.setattr('app.main.analyze', lambda messages, current, participants: validate_review(review_data([
        {"message_id": messages[1]["id"], "kind": "question", "quote": "Can you finish on Monday?", "meaning": "Question about deadline"}
    ]), messages, current))
    review = client.post(path+'/conversation/review', headers=a)
    assert review.status_code == 200, review.text
    result = review.json()
    assert result['conversation']['review_current'] is True
    assert result['conversation']['review']['changes'][1]['new_value'] == '₦160,000'
    assert result['terms']['price'] == '₦120,000'
    assert result['version'] == 1
    assert result['audit_valid']
    assert client.post(path+'/conversation/messages', headers=b, json={'message':'I need to think.'}).status_code == 201
    assert client.get(path,headers=b).json()['conversation']['review_current'] is False
    assert client.get(path, headers=a).json()['terms'] == TERMS


def test_review_fails_without_ai_but_keeps_the_chat(client):
    result = client.post('/api/cases', json={
        'title':'Paint the walls','party_a':'Amina','party_b':'Bello',
        'price':'₦100,000','deadline':'Friday','scope':'Paint walls'
    }).json()
    path = f'/api/cases/{result["case_id"]}'
    headers = {'X-Party-Key': result['party_a_key']}
    assert client.post(path+'/conversation/messages',headers=headers,json={'message':'I can begin Saturday.'}).status_code==201
    response = client.post(path+'/conversation/review',headers=headers)
    assert response.status_code == 503
    data = client.get(path, headers=headers).json()
    assert data['conversation']['review'] is None
    assert data['conversation']['messages'][0]['body'] == 'I can begin Saturday.'
    assert data['terms']['deadline'] == 'Friday'


def test_conditional_and_acceptance_words_cannot_create_changes():
    candidate = review_data()
    conditional = [{"id": "c1", "author":"b", "body":"If the parts arrive I will finish on Monday. Add ₦40,000 to the price.", "created_at":"today"}]
    result = validate_review(candidate, conditional, TERMS)
    assert result["intent"] == "conditional" and not result["changes"]
    accepted = [{"id":"a1", "author":"a", "body":"Agreed, finish on Monday.", "created_at":"today"}]
    result = validate_review(candidate, accepted, TERMS)
    assert result["intent"] == "no_change" and not result["changes"]



def test_review_returns_actionable_failure_without_changing_agreement(client, monkeypatch):
    from app.main import conversation_error_message
    from app.engine import MetaResponseError
    from types import SimpleNamespace
    assert "verified" in conversation_error_message(MetaResponseError("invalid_content"))
    assert "authorize" in conversation_error_message(SimpleNamespace(status_code=401))
    assert "request limit" in conversation_error_message(SimpleNamespace(status_code=429))
    assert "daily" in conversation_error_message(RuntimeError("Daily Meta request allowance reached. No API call was made."))

    result = client.post('/api/cases', json={
        'title': 'Repair agreement', 'party_a': 'Amina', 'party_b': 'Bello',
        'price': '₦100,000', 'deadline': 'Monday', 'scope': 'Repair the vehicle'
    }).json()
    case_id = result['case_id']
    headers = {'X-Party-Key': result['party_a_key']}
    client.post(f'/api/cases/{case_id}/conversation/messages', headers=headers, json={'message': 'I propose a new deadline.'})
    def reject(*args):
        raise MetaResponseError('invalid_json')
    monkeypatch.setattr('app.main.analyze', reject)
    response = client.post(f'/api/cases/{case_id}/conversation/review', headers=headers)
    assert response.status_code == 503
    assert 'verified' in response.json()['detail']
    state = client.get(f'/api/cases/{case_id}', headers=headers).json()
    assert state['terms']['deadline'] == 'Monday'
    assert state['conversation']['review'] is None
