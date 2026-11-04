"""A direct reply to a quoted price condition may prepare, never apply, an amendment."""
import pytest
from app.conversation import recover_confirmed_price

PREV = {"id": "price-offer", "author": "b", "body": "Ok but the price will then be $700"}
LAST = {"id": "confirmation", "author": "a", "body": "I agree"}
TERMS = {"price": "$600", "deadline": "December 20, 2026", "scope": "A mobile responsive web app"}


def report(previous=PREV, latest=LAST, both_quotes=True):
    observations = [{"message_id": previous["id"], "kind": "condition",
                     "quote": previous["body"], "author": previous["author"],
                     "meaning": "The price would be $700"}]
    if both_quotes:
        observations.append({"message_id": latest["id"], "kind": "confirmation",
                             "quote": "I agree", "author": latest["author"],
                             "meaning": "Accepts the price condition in conversation"})
    return {"last_message_id": latest["id"], "last_author": latest["author"],
            "intent": "no_change", "changes": [], "observations": observations,
            "explanation": "An acceptance is not a new proposal"}


def test_saved_conversation_recovers_only_price_as_draft():
    original = report()
    recovered = recover_confirmed_price(original, PREV, LAST, TERMS)
    assert recovered["confirmed_prior_offer"] is True
    assert recovered["changes"] == [{"field": "price", "new_value": "$700",
                                      "evidence": PREV["body"], "source_message_id": PREV["id"]}]
    assert not original["changes"]


@pytest.mark.parametrize("prev,last,both", [
    (PREV, {**LAST, "body": "I agree but only after the job is done"}, True),
    (PREV, {**LAST, "body": "I agree?"}, True),
    (PREV, {**LAST, "author": "b"}, True),
    ({**PREV, "body": "Ok but the price will then be $700 or $900"}, LAST, True),
    ({**PREV, "body": "What if the price will then be $700?"}, LAST, True),
    (PREV, LAST, False),
    ({**PREV, "body": "Ok but the price will then be ₦700"}, LAST, True),
])
def test_recovery_refuses_ambiguous_or_unverified_dialogue(prev,last,both):
    assert not recover_confirmed_price(report(prev,last,both), prev, last, TERMS)["changes"]


def test_existing_saved_review_creates_pending_amendment_and_requires_second_approval(client, monkeypatch):
    created = client.post('/api/cases', json={
        'title': 'Mobile Website Delivery', 'party_a': 'Alex Morgan', 'party_b': 'Sam Lee',
        **TERMS,
    }).json()
    root = f'/api/cases/{created["case_id"]}'
    a, b = {'X-Party-Key': created['party_a_key']}, {'X-Party-Key': created['party_b_key']}
    assert client.post(root + '/confirm', headers=b).status_code == 200
    for auth, message in [(b,'I think we need to use python framework for this project'),
                          (a,'Nope, let us use Laravel framework'),
                          (b,PREV['body']), (a,LAST['body'])]:
        result = client.post(root + '/conversation/messages', headers=auth, json={'message':message})
        assert result.status_code == 201, result.text
    stored = result.json()['conversation']['messages']
    prior, latest = stored[-2:]
    saved = report({**PREV, 'id':prior['id']}, {**LAST, 'id':latest['id']})
    def fake_review(*_):
        return saved
    monkeypatch.setattr('app.main.analyze', fake_review)
    response = client.post(root + '/conversation/review', headers=a)
    assert response.status_code == 200, response.text
    view = client.get(root, headers=a).json()
    assert view['conversation']['review_current']
    assert view['conversation']['review']['changes'][0]['new_value'] == '$700'
    assert view['terms']['price'] == '$600'
    # The author of the quoted condition cannot prepare it from the confirmation.
    assert client.post(root + '/conversation/prepare-amendment', headers=b).status_code == 403
    # Preparing the change does not call Meta again or change approved terms.
    monkeypatch.setattr('app.main.analyze', lambda *_: (_ for _ in ()).throw(AssertionError('No extra model call')))
    prepared = client.post(root + '/conversation/prepare-amendment', headers=a)
    assert prepared.status_code == 200, prepared.text
    content = prepared.json()
    proposal = next(item for item in content['proposals'] if item['status'] == 'pending')
    assert content['terms'] == TERMS
    assert proposal['changes'][0]['new_value'] == '$700'
    assert proposal['changes'][0]['message_id'] == prior['id']
    assert client.post(root + '/conversation/prepare-amendment', headers=a).status_code == 409
    approved = client.post(root + f'/proposals/{proposal["id"]}/approve', headers=b)
    assert approved.status_code == 200, approved.text
    assert approved.json()['terms'] == {**TERMS,'price':'$700'}
    assert approved.json()['audit_valid']


def test_no_saved_confirmation_quote_stays_non_actionable(client, monkeypatch):
    created = client.post('/api/cases', json={
        'title':'Website Development','party_a':'Alex Morgan','party_b':'Sam Lee',**TERMS,
    }).json()
    root=f'/api/cases/{created["case_id"]}'
    a,b={'X-Party-Key':created['party_a_key']},{'X-Party-Key':created['party_b_key']}
    client.post(root+'/confirm',headers=b)
    client.post(root+'/conversation/messages',headers=b,json={'message':PREV['body']})
    client.post(root+'/conversation/messages',headers=a,json={'message':LAST['body']})
    last=client.get(root,headers=a).json()['conversation']['messages'][-1]
    previous=client.get(root,headers=a).json()['conversation']['messages'][-2]
    monkeypatch.setattr('app.main.analyze',lambda *_:report({**PREV,'id':previous['id']},{**LAST,'id':last['id']},False))
    client.post(root+'/conversation/review',headers=a)
    assert not client.get(root,headers=a).json()['conversation']['review']['changes']
    assert client.post(root+'/conversation/prepare-amendment',headers=a).status_code == 409


def test_amount_should_be_price_confirmation_saved_review(client, monkeypatch):
    """Reported live wording can produce a DRAFT, never an automatic change."""
    created = client.post('/api/cases', json={
        'title': 'Website project', 'party_a': 'Alex Morgan', 'party_b': 'Sam Lee', **TERMS,
    }).json()
    root = f'/api/cases/{created["case_id"]}'
    a, b = {'X-Party-Key': created['party_a_key']}, {'X-Party-Key': created['party_b_key']}
    assert client.post(root + '/confirm', headers=b).status_code == 200
    transcript = [
        (b, 'I will use python to develop the website'),
        (a, 'No, please use PHP Laravel framework for my project.'),
        (b, 'In this case the amount should be $700'),
        (a, 'I agree.'),
    ]
    for auth, message in transcript:
        res = client.post(root + '/conversation/messages', headers=auth, json={'message': message})
        assert res.status_code == 201, res.text
    prior, last = res.json()['conversation']['messages'][-2:]
    prior_body = prior['body']
    def stored_meta_review(*_):
        return {
            'last_message_id': last['id'], 'last_author': last['author'],
            'intent': 'no_change', 'changes': [],
            'explanation': 'Confirmation is not a new proposal',
            'observations': [
                {'message_id': prior['id'], 'author': 'b', 'kind': 'condition',
                 'quote': prior_body, 'meaning': 'Conditions Laravel work on $700'},
                {'message_id': last['id'], 'author': 'a', 'kind': 'confirmation',
                 'quote': 'I agree.', 'meaning': 'Accepts the price condition in chat'},
            ], 'mode': 'meta_muse_spark_1_3'
        }
    monkeypatch.setattr('app.main.analyze', stored_meta_review)
    assert client.post(root + '/conversation/review', headers=a).status_code == 200
    current = client.get(root, headers=a).json()
    assert current['terms']['price'] == '$600'
    assert current['conversation']['review']['changes'][0]['new_value'] == '$700'
    monkeypatch.setattr('app.main.analyze', lambda *_: (_ for _ in ()).throw(AssertionError('Should not call Meta again')))
    draft = client.post(root + '/conversation/prepare-amendment', headers=a)
    assert draft.status_code == 200, draft.text
    assert draft.json()['terms']['price'] == '$600'
    proposal = next(x for x in draft.json()['proposals'] if x['status']=='pending')
    assert proposal['changes'][0]['new_value'] == '$700'
    accepted = client.post(root + f'/proposals/{proposal["id"]}/approve', headers=b)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()['terms']['price'] == '$700'


def test_amount_should_be_requires_proper_quote():
    previous = {**PREV, 'body': 'In this case the amount should be $700'}
    observed = report(previous=previous)
    assert recover_confirmed_price(observed, previous, LAST, TERMS)['changes'][0]['new_value'] == '$700'
    observed['observations'][0]['quote'] = 'fabricated quote'
    assert not recover_confirmed_price(observed, previous, LAST, TERMS)['changes']
