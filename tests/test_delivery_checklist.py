from test_lifecycle import case


def plan_items():
    return {'items': [
        {'description': 'Deliver a responsive homepage', 'acceptance_criteria': 'Homepage works at 375px and 1280px widths'},
        {'description': 'Provide an invoice download', 'acceptance_criteria': 'An invoice downloads as a PDF'},
    ]}


def new_plan(client):
    c = case(client)
    c('/confirm','POST','b')
    created = c('/delivery-plan','POST','a',plan_items())
    assert created.status_code == 201, created.text
    return c, created.json()['delivery_plan']


def test_plan_requires_two_person_approval(client):
    c=case(client)
    assert c('/delivery-plan','POST','a',plan_items()).status_code == 409
    c('/confirm','POST','b')
    planned=c('/delivery-plan','POST','a',plan_items()).json()
    plan=planned['delivery_plan']
    assert plan['status']=='pending' and len(plan['items'])==2
    assert c(f'/delivery-plan/{plan["id"]}/respond','POST','a',{'accepted':True}).status_code==403
    assert c(f'/delivery-items/{plan["items"][0]["id"]}/submit','POST','b',{'statement':'Finished all pages'}).status_code==409
    active=c(f'/delivery-plan/{plan["id"]}/respond','POST','b',{'accepted':True}).json()
    assert active['delivery_plan']['status']=='active'
    assert active['status']=='in_progress'
    assert active['audit_valid']


def test_plan_rejection_can_be_reproposed(client):
    c, plan = new_plan(client)
    assert c(f'/delivery-plan/{plan["id"]}/respond','POST','b',{'accepted':False,'note':''}).status_code==422
    rejected=c(f'/delivery-plan/{plan["id"]}/respond','POST','b',{'accepted':False,'note':'Need a more precise scope'})
    assert rejected.status_code==200
    assert rejected.json()['delivery_plan']['status']=='rejected'
    updated=c('/delivery-plan','POST','b',plan_items())
    assert updated.status_code==201
    assert updated.json()['delivery_plan']['author']=='b'


def test_each_item_must_be_reviewed(client):
    c, plan = new_plan(client)
    c(f'/delivery-plan/{plan["id"]}/respond','POST','b',{'accepted':True})
    first,second=[row['id'] for row in plan['items']]
    assert c(f'/delivery-items/{first}/submit','POST','a',{'statement':'Homepage done'}).status_code==403
    submitted=c(f'/delivery-items/{first}/submit','POST','b',{
        'statement':'Homepage finished and tested','reference':'Demo recording 1'
    }).json()
    assert submitted['status']=='awaiting_completion_review'
    assert c(f'/delivery-items/{first}/review','POST','b',{'accepted':True}).status_code==403
    partial=c(f'/delivery-items/{first}/review','POST','a',{'accepted':True}).json()
    assert partial['status']=='in_progress'
    assert partial['delivery_plan']['accepted_count']==1
    assert c(f'/delivery-items/{second}/submit','POST','b',{'statement':'Invoice download works'}).status_code==200
    complete=c(f'/delivery-items/{second}/review','POST','a',{'accepted':True}).json()
    assert complete['status']=='completed'
    assert complete['delivery_plan']['accepted_count']==2
    assert any(row['event']=='delivery_completed' for row in complete['history'])
    assert complete['audit_valid']
    assert c(f'/delivery-items/{second}/review','POST','a',{'accepted':True}).status_code==409


def test_dispute_resubmission_keeps_previous_evidence(client):
    c, plan=new_plan(client)
    c(f'/delivery-plan/{plan["id"]}/respond','POST','b',{'accepted':True})
    first=plan['items'][0]['id']
    c(f'/delivery-items/{first}/submit','POST','b',{'statement':'Initial homepage is done','reference':'First screenshot'})
    assert c(f'/delivery-items/{first}/review','POST','a',{'accepted':False,'note':''}).status_code==422
    disputed=c(f'/delivery-items/{first}/review','POST','a',{'accepted':False,'note':'Mobile menu is broken'}).json()
    assert disputed['status']=='disputed'
    assert c(f'/delivery-items/{first}/review','POST','a',{'accepted':True}).status_code==409
    resubmitted=c(f'/delivery-items/{first}/submit','POST','b',{'statement':'Fixed mobile navigation menu','reference':'New screenshot'})
    assert resubmitted.status_code==200
    assert resubmitted.json()['status']=='awaiting_completion_review'
    accepted=c(f'/delivery-items/{first}/review','POST','a',{'accepted':True}).json()
    events=[e for e in accepted['history'] if e['event'] in ('deliverable_submitted','deliverable_disputed','deliverable_resubmitted')]
    assert [e['event'] for e in events]==['deliverable_submitted','deliverable_disputed','deliverable_resubmitted']
    assert events[0]['payload']['reference']=='First screenshot'
    assert events[2]['payload']['reference']=='New screenshot'
    assert accepted['audit_valid']


def test_plan_blocks_legacy_delivery_and_amendment_bypass(client):
    c, plan = new_plan(client)
    assert c('/manual-proposals','POST','a',{'price':'₦130,000','deadline':'12 November 2026','scope':'Install kitchen cabinets'}).status_code==409
    assert c('/completion','POST','b',{'statement':'Everything done'}).status_code==409
    c(f'/delivery-plan/{plan["id"]}/respond','POST','b',{'accepted':True})
    assert c('/manual-proposals','POST','a',{'price':'₦130,000','deadline':'12 November 2026','scope':'Install kitchen cabinets'}).status_code==409
    assert c('/completion','POST','b',{'statement':'Everything done'}).status_code==409
    assert c('/delivery-plan','POST','a',plan_items()).status_code==409


def test_invalid_delivery_items_and_permissions(client):
    c,plan=new_plan(client)
    assert c('/delivery-plan','POST','a',{'items':[plan_items()['items'][0]]}).status_code==409
    c(f'/delivery-plan/{plan["id"]}/respond','POST','b',{'accepted':True})
    assert c('/delivery-items/notfound/submit','POST','b',{'statement':'Work finished'}).status_code==404
    first=plan['items'][0]['id']
    assert c(f'/delivery-items/{first}/submit','POST','b',{'statement':'done'}).status_code==422
    assert c(f'/delivery-items/{first}/submit','POST','b',{'statement':'Work completed properly'}).status_code==200
    assert c(f'/delivery-items/{first}/submit','POST','b',{'statement':'More completed work'}).status_code==409


def test_checklist_works_when_responsibility_is_initiator(client):
    c=case(client,responsible='a')
    c('/confirm','POST','b')
    plan=c('/delivery-plan','POST','b',plan_items()).json()['delivery_plan']
    c(f'/delivery-plan/{plan["id"]}/respond','POST','a',{'accepted':True})
    first=plan['items'][0]['id']
    assert c(f'/delivery-items/{first}/submit','POST','b',{'statement':'Work completed properly'}).status_code==403
    assert c(f'/delivery-items/{first}/submit','POST','a',{'statement':'Work completed properly'}).status_code==200
    assert c(f'/delivery-items/{first}/review','POST','b',{'accepted':True}).status_code==200
