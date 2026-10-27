from app.engine import demo_detect
from app.storage import verify_chain


def make(client):
    r=client.post('/api/cases',json={"title":"Repair agreement","party_a":"Amina","party_b":"Bello","price":"₦120,000","deadline":"Friday","scope":"Repair vehicle engine"})
    assert r.status_code==201
    d=r.json(); id=d['case_id']
    def call(action,who='a',method='post',json=None):
        return client.request(method.upper(),f'/api/cases/{id}'+action,headers={'X-Party-Key':d[f'party_{who}_key']},json=json)
    return d,call


def test_drift_requires_two_confirmations(client):
    d,call=make(client)
    assert call('',method='get').json()['active'] is False
    assert call('/proposals',json={'message':'Finish on Monday'}).status_code==409
    call('/confirm')
    assert call('',method='get').json()['active'] is False
    call('/confirm','b')
    assert call('',method='get').json()['active'] is True
    resp=call('/proposals','b',json={'message':"I will finish on Monday. You'll need to add ₦40,000 for the extra work."})
    assert resp.status_code==200,resp.text
    obj=resp.json(); assert obj['proposal_created']
    case=obj['case'];p=case['proposals'][0]
    assert len(p['changes'])==2
    assert {x['field']:x['new_value'] for x in p['changes']}=={'price':'₦160,000','deadline':'Monday'}
    assert case['terms']['price']=='₦120,000'
    id=p['id']
    after_one=call(f'/proposals/{id}/approve','b').json()
    assert after_one['version']==1 and after_one['terms']['price']=='₦120,000'
    done=call(f'/proposals/{id}/approve','a').json()
    assert done['version']==2 and done['terms']['price']=='₦160,000' and done['terms']['deadline']=='Monday'
    assert done['audit_valid']
    assert done['proposals'][0]['status']=='applied'


def test_reject_preserves_terms(client):
    _,c=make(client);c('/confirm','a');c('/confirm','b')
    p=c('/proposals',json={'message':'Finish on Monday'}).json()['case']['proposals'][0]
    after=c(f"/proposals/{p['id']}/reject",'b').json()
    assert after['version']==1 and after['terms']['deadline']=='Friday'
    assert after['proposals'][0]['status']=='rejected'


def test_unauthorized_and_cross_case(client):
    d,c=make(client)
    assert client.get('/api/cases/'+d['case_id']).status_code==401
    assert client.get('/api/cases/'+d['case_id'],headers={'X-Party-Key':'fake'}).status_code==403


def test_questions_are_not_applied():
    f=demo_detect('Could we finish on Tuesday?', {'price':'₦120,000','deadline':'Friday','scope':'Repair engine'})
    assert f.intent=='ambiguous' and f.changes==[]


def test_no_confident_fabrication():
    f=demo_detect('Your price is interesting', {'price':'₦120,000','deadline':'Friday','scope':'Repair engine'})
    assert not f.changes and f.mode=='offline_demo'


def test_meta_failure_is_not_hidden(client,monkeypatch):
    _,c=make(client);c('/confirm','a');c('/confirm','b')
    monkeypatch.setenv('ANALYSIS_MODE','meta')
    monkeypatch.delenv('MODEL_API_KEY',raising=False)
    result=c('/proposals',json={'message':'Finish on Monday'})
    assert result.status_code==503
    assert not c('',method='get').json()['proposals']


def test_approved_document_and_revision_history(client):
    credentials, call = make(client)
    assert call('/documents', method='get').status_code == 409
    call('/confirm', 'a')
    assert call('/documents', method='get').status_code == 409
    call('/confirm', 'b')
    original = call('/documents/1', method='get').json()
    assert original['terms']['price'] == '₦120,000'
    assert original['current'] is True
    assert set(original['approvals']) == {'a', 'b'}
    assert call('/confirm', 'a').status_code == 200
    assert len(call('', method='get').json()['history']) == 3

    change = call('/proposals', 'b', json={'message': "I will finish on Monday. You'll need to add ₦40,000 for the extra work."}).json()
    proposal_id = change['case']['proposals'][0]['id']
    call(f'/proposals/{proposal_id}/approve', 'b')
    call(f'/proposals/{proposal_id}/approve', 'a')
    old = call('/documents/1', method='get').json()
    latest = call('/documents/2', method='get').json()
    assert old['terms']['price'] == '₦120,000'
    assert old['current'] is False
    assert latest['terms']['price'] == '₦160,000'
    assert latest['current'] is True
    assert latest['terms']['deadline'] == 'Monday'
    assert [r['version'] for r in call('/documents', method='get').json()] == [1, 2]
    assert call('/documents/3', method='get').status_code == 404
    assert client.get(f"/api/cases/{credentials['case_id']}/documents").status_code == 401
    assert client.get(f"/api/cases/{credentials['case_id']}/documents/1", headers={'X-Party-Key':'invalid'}).status_code == 403
