from test_lifecycle import case


def understanding(price="₦120,000", deadline="12 November 2026", scope="Install kitchen cabinets"):
    return {"price": price, "deadline": deadline, "scope": scope}


def test_understanding_is_opt_in(client):
    c = case(client)
    assert c('/confirm', 'POST', 'b').status_code == 200


def test_approval_is_blocked_until_both_understand(client):
    c = case(client)
    request = c('/understanding/request', 'POST', 'b')
    assert request.status_code == 200
    assert c('/confirm', 'POST', 'b').status_code == 409
    assert c('/understanding', 'POST', 'b', understanding()).status_code == 200
    assert c('/confirm', 'POST', 'b').status_code == 409
    a = c('/understanding', 'POST', 'a', understanding()).json()
    assert a['understanding']['ready']
    assert all(check['matches'] for check in a['understanding']['checks'])
    assert c('/confirm', 'POST', 'b').json()['status'] == 'in_progress'
    assert c().json()['audit_valid']


def test_conflict_and_repair(client):
    c = case(client)
    c('/understanding/request', 'POST', 'a')
    c('/understanding', 'POST', 'a', understanding())
    response = c('/understanding', 'POST', 'b', understanding(price='₦150,000'))
    result = response.json()['understanding']
    assert not result['ready']
    assert [x['field'] for x in result['checks'] if not x['matches']] == ['price']
    assert result['checks'][0]['a'] == '₦120,000'
    assert result['checks'][0]['b'] == '₦150,000'
    assert c('/confirm', 'POST', 'b').status_code == 409
    assert c('/understanding', 'POST', 'b', understanding()).json()['understanding']['ready']
    assert c('/confirm', 'POST', 'b').status_code == 200


def test_answers_not_exposed_before_both_reply(client):
    c = case(client)
    c('/understanding/request', 'POST', 'b')
    c('/understanding', 'POST', 'a', understanding(scope='Private description'))
    recipient = c('', 'GET', 'b').json()['understanding']
    assert recipient['mine'] is None
    assert recipient['checks'] == []
    assert recipient['submitted']['a'] is True
    assert 'Private description' not in str(recipient)


def test_counteroffer_resets_check_and_retains_original_records(client):
    c = case(client)
    c('/understanding/request', 'POST', 'a')
    c('/understanding', 'POST', 'a', understanding())
    counter = c('/counter', 'POST', 'b', understanding(price='₦140,000'))
    assert counter.status_code == 200
    assert not counter.json()['understanding']['requested']
    assert c('/confirm', 'POST', 'a').status_code == 200
    assert c().json()['terms']['price'] == '₦140,000'
    assert c().json()['audit_valid']


def test_cannot_start_after_approval_or_submit_without_request(client):
    c = case(client)
    assert c('/understanding', 'POST', 'b', understanding()).status_code == 409
    c('/confirm', 'POST', 'b')
    assert c('/understanding/request', 'POST', 'a').status_code == 409
    assert c('/understanding', 'POST', 'a', understanding()).status_code == 409


def test_deadline_format_equivalence(client):
    c = case(client)
    c('/understanding/request', 'POST', 'a')
    c('/understanding', 'POST', 'a', understanding(deadline='2026-11-12'))
    result = c('/understanding', 'POST', 'b', understanding(deadline='12-November-2026')).json()
    assert result['understanding']['ready']


def test_understanding_state_tracks_missing_recipient_and_prevents_duplicate_activity(client):
    c = case(client)
    c('/understanding/request', 'POST', 'a')
    first = c('/understanding', 'POST', 'a', understanding()).json()
    assert first['understanding']['state'] == 'awaiting_other'
    recipient = c('', 'GET', 'b').json()
    assert recipient['understanding']['state'] == 'awaiting_you'
    before = len(first['history'])
    repeat = c('/understanding', 'POST', 'a', understanding()).json()
    assert len(repeat['history']) == before
    assert c('/confirm', 'POST', 'b').status_code == 409


def test_scope_paraphrase_is_visible_mismatch_and_cannot_be_silent_approval(client):
    c = case(client)
    c('/understanding/request', 'POST', 'a')
    c('/understanding', 'POST', 'a', understanding())
    resp = c('/understanding', 'POST', 'b', understanding(scope='Put cabinets in the kitchen'))
    check = resp.json()['understanding']
    assert check['state'] == 'differences'
    assert not check['ready']
    scope = next(item for item in check['checks'] if item['field'] == 'scope')
    assert scope['a_matches_offer']
    assert not scope['b_matches_offer']
    assert c('/confirm', 'POST', 'b').status_code == 409
    assert c('/understanding', 'POST', 'b', understanding()).json()['understanding']['state'] == 'aligned'
