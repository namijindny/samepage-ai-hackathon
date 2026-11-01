from app.storage import verify_chain


def case(client, responsible='b'):
    response = client.post('/api/cases', json={
        'title':'Kitchen renovation', 'party_a':'Amina', 'party_b':'Bello',
        'price':'₦120,000','deadline':'12 November 2026',
        'scope':'Install kitchen cabinets','responsible_party':responsible,
    })
    assert response.status_code == 201, response.text
    data=response.json()
    cid=data['case_id']
    def call(path='', method='GET', who='a', body=None):
        return client.request(method, f'/api/cases/{cid}{path}', headers={'X-Party-Key':data[f'party_{who}_key']}, json=body)
    return call


def test_initiator_and_recipient_roles(client):
    c=case(client)
    initial=c().json()
    assert initial['initiator']=='a' and initial['recipient']=='b'
    assert initial['status']=='awaiting_recipient'
    assert initial['a_confirmed'] and not initial['b_confirmed']
    assert c('/documents').status_code==409
    final=c('/confirm','POST','b').json()
    assert final['status']=='in_progress'
    assert c('/documents/1').status_code==200
    assert c('/documents/1').json()['initiator']=='Amina'


def test_recipient_counteroffer_and_document(client):
    c=case(client)
    assert c('/counter','POST','a',{'price':'₦130,000','deadline':'13 November 2026','scope':'Install kitchen cabinets'}).status_code == 409
    result=c('/counter','POST','b',{
        'price':'₦140,000','deadline':'13 November 2026','scope':'Install kitchen cabinets','note':'Materials more expensive'
    })
    assert result.status_code==200, result.text
    pending=result.json()
    assert pending['status']=='awaiting_initiator'
    assert not pending['a_confirmed'] and pending['b_confirmed']
    assert c('/documents').status_code==409
    accepted=c('/confirm','POST','a')
    assert accepted.status_code==200
    assert accepted.json()['status']=='in_progress'
    doc=c('/documents/1').json()
    assert doc['terms']['price']=='₦140,000'
    assert doc['approvals']['a'] and doc['approvals']['b']
    assert c().json()['audit_valid']


def test_decline_offer(client):
    c=case(client)
    assert c('/decline','POST','a',{'message':'Not interested'}).status_code==409
    declined=c('/decline','POST','b',{'message':'I cannot do this'}).json()
    assert declined['status']=='declined' and not declined['active']
    assert c('/confirm','POST','b').status_code==409


def test_manual_changes_and_delivery(client):
    c=case(client)
    c('/confirm','POST','b')
    result=c('/manual-proposals','POST','a',{
        'price':'₦140,000','deadline':'15 November 2026','scope':'Install kitchen cabinets',
        'reason':'Extra materials'
    })
    assert result.status_code==200, result.text
    pending=result.json()['proposals'][0]
    assert pending['a_approved'] and not pending['b_approved']
    assert c().json()['terms']['price']=='₦120,000'
    assert c('/completion','POST','b',{'statement':'Delivered kitchen cabinets'}).status_code==409
    done=c(f'/proposals/{pending["id"]}/approve','POST','b').json()
    assert done['version']==2 and done['terms']['price']=='₦140,000'
    assert c('/completion','POST','a',{'statement':'Cabinets installed'}).status_code==403
    submitted=c('/completion','POST','b',{
        'statement':'Installed kitchen cabinets and cleaned the workspace',
        'reference':'Photo 001'
    }).json()
    assert submitted['status']=='awaiting_completion_review'
    assert c('/completion/review','POST','b',{'accepted':True}).status_code==403
    completed=c('/completion/review','POST','a',{'accepted':True,'note':'Inspected'}).json()
    assert completed['status']=='completed' and completed['audit_valid']
    assert c('/manual-proposals','POST','b',{
        'price':'₦150,000','deadline':'16 November 2026','scope':'Install kitchen cabinets'
    }).status_code==409


def test_disputed_delivery_and_currency_rules(client):
    c=case(client)
    c('/confirm','POST','b')
    assert c('/manual-proposals','POST','b',{
        'price':'$150','deadline':'12 November 2026','scope':'Install kitchen cabinets'
    }).status_code==422
    c('/completion','POST','b',{'statement':'Cabinets installed','reference':''})
    result=c('/completion/review','POST','a',{'accepted':False,'note':'Upper cabinet is missing'})
    assert result.status_code==200 and result.json()['status']=='disputed'
    assert c('/completion/review','POST','a',{'accepted':True}).status_code==409


def test_disputed_delivery_can_be_corrected(client):
    c=case(client)
    c('/confirm','POST','b')
    c('/completion','POST','b',{'statement':'Initial installation reported'})
    c('/completion/review','POST','a',{'accepted':False,'note':'Some cabinets missing'})
    updated=c('/completion/resubmit','POST','b',{'statement':'Added missing cabinets and fixed doors','reference':'Photo 002'})
    assert updated.status_code == 200
    assert updated.json()['status'] == 'awaiting_completion_review'
    final=c('/completion/review','POST','a',{'accepted':True,'note':'Everything delivered now'})
    assert final.json()['status'] == 'completed'
    assert any(item['event']=='delivery_resubmitted' for item in final.json()['history'])
    assert final.json()['audit_valid']


def test_manual_approval_is_idempotent(client):
    c=case(client)
    c('/confirm','POST','b')
    result=c('/manual-proposals','POST','a',{'price':'₦125,000','deadline':'12 November 2026','scope':'Install kitchen cabinets'}).json()
    pid=result['proposals'][0]['id']
    before=len(result['history'])
    already=c(f'/proposals/{pid}/approve','POST','a').json()
    assert len(already['history'])==before
    assert already['terms']['price']=='₦120,000'
    accepted=c(f'/proposals/{pid}/approve','POST','b').json()
    assert accepted['terms']['price']=='₦125,000'


def test_counteroffers_can_move_back_and_forth_until_accepted(client):
    c = case(client)
    first = c('/counter', 'POST', 'b', {
        'price': '₦140,000', 'deadline': '15 November 2026',
        'scope': 'Install kitchen cabinets', 'note': 'More materials required'
    })
    assert first.status_code == 200
    assert first.json()['offer_by'] == 'b'
    assert first.json()['offer_revision'] == 1
    assert first.json()['status'] == 'awaiting_initiator'
    assert first.json()['offer_changes'][0]['field'] == 'price'
    assert c('/counter', 'POST', 'b', {
        'price': '₦125,000', 'deadline': '15 November 2026',
        'scope': 'Install kitchen cabinets'
    }).status_code == 409
    second = c('/counter', 'POST', 'a', {
        'price': '₦130,000', 'deadline': '15 November 2026',
        'scope': 'Install kitchen cabinets', 'note': 'Can we meet halfway?'
    })
    assert second.status_code == 200
    assert second.json()['offer_by'] == 'a'
    assert second.json()['offer_revision'] == 2
    assert second.json()['status'] == 'awaiting_recipient'
    assert second.json()['terms']['price'] == '₦130,000'
    assert c('/documents').status_code == 409
    final = c('/confirm', 'POST', 'b')
    assert final.status_code == 200
    assert final.json()['status'] == 'in_progress'
    assert final.json()['a_confirmed'] and final.json()['b_confirmed']
    assert c('/documents/1').json()['terms']['price'] == '₦130,000'
    assert c().json()['audit_valid']
    assert c('/completion', 'POST', 'b', {
        'statement': 'Installed the agreed cabinets.'
    }).json()['status'] == 'awaiting_completion_review'


def test_only_pending_reviewer_can_decline_latest_counter(client):
    c = case(client)
    c('/counter', 'POST', 'b', {
        'price': '₦140,000', 'deadline': '15 November 2026',
        'scope': 'Install kitchen cabinets'
    })
    assert c('/decline', 'POST', 'b', {'message': 'Cancel this'}).status_code == 409
    result = c('/decline', 'POST', 'a', {'message': 'Cannot meet this budget'})
    assert result.status_code == 200
    assert result.json()['status'] == 'declined'
    assert c('/confirm', 'POST', 'a').status_code == 409
    assert c('/documents').status_code == 409
