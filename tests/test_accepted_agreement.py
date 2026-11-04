
def test_understanding_check_applies_to_pending_offer_not_later_amendments(client):
    created = client.post('/api/cases', json={
        'title': 'Building work', 'party_a': 'Ada', 'party_b': 'Bayo',
        'price': '$150,000', 'deadline': '31-December-2026',
        'scope': 'Build the agreed property',
    })
    assert created.status_code == 201
    case = created.json()
    url = f"/api/cases/{case['case_id']}"
    a = {'X-Party-Key': case['party_a_key']}
    b = {'X-Party-Key': case['party_b_key']}
    answers = {'price': '$150,000', 'deadline': '31-December-2026', 'scope': 'Build the agreed property'}
    assert client.post(url + '/understanding/request', headers=a).status_code == 200
    assert client.post(url + '/understanding', headers=a, json=answers).status_code == 200
    clarity = client.post(url + '/understanding', headers=b, json=answers).json()
    assert clarity['understanding']['state'] == 'aligned'
    accepted = client.post(url + '/confirm', headers=b)
    assert accepted.status_code == 200
    assert accepted.json()['status'] == 'in_progress'
    assert accepted.json()['understanding']['state'] == 'not_applicable'
    amended = client.post(url + '/manual-proposals', headers=a, json={
        'price': '$150,000', 'deadline': 'January 15, 2027', 'scope': 'Build the agreed property',
        'reason': 'Deadline extension while keeping the price',
    })
    assert amended.status_code == 200, amended.text
    proposal = next(x for x in amended.json()['proposals'] if x['status']=='pending')
    updated = client.post(url + f"/proposals/{proposal['id']}/approve", headers=b)
    assert updated.status_code == 200, updated.text
    result = updated.json()
    assert result['terms']['deadline'] == 'January 15, 2027'
    assert result['understanding']['state'] == 'not_applicable'
    assert result['understanding']['ready'] is True
    assert any(x['event'] == 'understanding_aligned' for x in result['history'])
    assert result['audit_valid'] is True
