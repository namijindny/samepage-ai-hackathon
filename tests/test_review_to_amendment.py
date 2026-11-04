from app.conversation import validate_review


def case_and_keys(client):
    response = client.post('/api/cases', json={
        'title': 'Website delivery', 'party_a': 'Ada', 'party_b': 'Bayo',
        'price': '₦150,000', 'deadline': '31-December-2026',
        'scope': 'Build a responsive website'
    })
    assert response.status_code == 201
    data = response.json()
    path = f"/api/cases/{data['case_id']}"
    a = {'X-Party-Key': data['party_a_key']}
    b = {'X-Party-Key': data['party_b_key']}
    assert client.post(path + '/confirm', headers=b).status_code == 200
    return path, a, b


def review_proposal(client, monkeypatch, path, headers):
    message = 'I propose January 15, 2027, and the price stays the same.'
    saved = client.post(path + '/conversation/messages', headers=headers, json={'message': message})
    assert saved.status_code == 201
    def fake(messages, current, participants):
        return validate_review({
            'observations': [{
                'message_id': messages[-1]['id'], 'quote': 'I propose January 15, 2027,',
                'kind': 'proposal', 'meaning': 'A new deadline proposed',
            }],
            'latest': {'intent': 'change_proposal', 'changes': [{
                'field': 'deadline', 'new_value': 'January 15, 2027',
                'operation': 'replace', 'evidence': 'January 15, 2027', 'certainty': 'explicit',
            }], 'explanation': 'Explicit deadline proposal'},
        }, messages, current)
    monkeypatch.setattr('app.main.analyze', fake)
    response = client.post(path + '/conversation/review', headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_reviewed_proposal_requires_other_party_approval(client, monkeypatch):
    path, a, b = case_and_keys(client)
    reviewed = review_proposal(client, monkeypatch, path, a)
    assert reviewed['conversation']['review_current'] is True
    assert reviewed['conversation']['review_id']
    before = client.get(path, headers=b).json()['terms']
    assert before['deadline'] == '31-December-2026'
    prepared = client.post(path + '/conversation/prepare-amendment', headers=a)
    assert prepared.status_code == 200, prepared.text
    data = prepared.json()
    proposal = next(p for p in data['proposals'] if p['status'] == 'pending')
    assert proposal['mode'] == 'meta_conversation'
    assert proposal['a_approved'] == 1 and proposal['b_approved'] == 0
    assert proposal['changes'] == [{
        'field': 'deadline', 'old_value': '31-December-2026',
        'new_value': 'January 15, 2027', 'evidence': 'January 15, 2027',
        'message_id': reviewed['conversation']['review']['last_message_id'],
    }]
    assert data['terms'] == before
    assert client.post(path + '/conversation/prepare-amendment', headers=a).status_code == 409
    accepted = client.post(path + '/proposals/' + proposal['id'] + '/approve', headers=b)
    assert accepted.status_code == 200
    assert accepted.json()['terms']['deadline'] == 'January 15, 2027'
    assert accepted.json()['terms']['price'] == '₦150,000'
    assert accepted.json()['version'] == 2
    assert accepted.json()['audit_valid'] is True
    documents = client.get(path + '/documents', headers=a).json()
    assert {d['version'] for d in documents} == {1, 2}


def test_proposer_only_and_review_expiry(client, monkeypatch):
    path, a, b = case_and_keys(client)
    review_proposal(client, monkeypatch, path, a)
    assert client.post(path + '/conversation/prepare-amendment', headers=b).status_code == 403
    assert client.post(path + '/conversation/prepare-amendment').status_code == 401
    assert client.post(path + '/conversation/messages', headers=b, json={
        'message': 'Please explain the change first.'
    }).status_code == 201
    assert client.post(path + '/conversation/prepare-amendment', headers=a).status_code == 409
    assert not client.get(path, headers=a).json()['proposals']


def test_no_verified_change_cannot_be_submitted(client, monkeypatch):
    path, a, b = case_and_keys(client)
    assert client.post(path + '/conversation/messages', headers=a, json={
        'message': 'Can we agree on January 15, 2027?'
    }).status_code == 201
    monkeypatch.setattr('app.main.analyze', lambda messages, current, participants: {
        'intent': 'question', 'changes': [], 'observations': [],
        'explanation': 'This is only a question', 'last_author': 'a',
        'last_message_id': messages[-1]['id'], 'mode': 'meta_muse_spark_1_3',
    })
    assert client.post(path + '/conversation/review', headers=a).status_code == 200
    blocked = client.post(path + '/conversation/prepare-amendment', headers=a)
    assert blocked.status_code == 409
    assert client.get(path, headers=b).json()['terms']['deadline'] == '31-December-2026'


def test_declined_reviewed_change_does_not_change_original(client, monkeypatch):
    path, a, b = case_and_keys(client)
    review_proposal(client, monkeypatch, path, a)
    prepared = client.post(path + '/conversation/prepare-amendment', headers=a).json()
    proposal_id = next(p['id'] for p in prepared['proposals'] if p['status'] == 'pending')
    declined = client.post(path + f'/proposals/{proposal_id}/reject', headers=b)
    assert declined.status_code == 200
    assert declined.json()['terms']['deadline'] == '31-December-2026'
    assert declined.json()['version'] == 1
