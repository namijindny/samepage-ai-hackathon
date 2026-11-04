"""Judge-demo evidence: uploads, access control, previous versions and optional AI."""
import base64
from io import BytesIO
from PIL import Image
from test_lifecycle import case
from app import evidence


def image_payload(text='demo.png'):
    output=BytesIO()
    Image.new('RGB',(160,90),'white').save(output,format='PNG')
    return {'name':text,'data':base64.b64encode(output.getvalue()).decode()}


def plan(client):
    c=case(client)
    c('/confirm','POST','b')
    proposal=c('/delivery-plan','POST','a',{'items':[{'description':'Build home page','acceptance_criteria':'Works on mobile and desktop'}]}).json()['delivery_plan']
    c(f'/delivery-plan/{proposal["id"]}/respond','POST','b',{'accepted':True})
    return c,proposal['items'][0]['id']


def test_two_images_private_download_and_audit(client):
    c,item=plan(client)
    result=c(f'/delivery-items/{item}/submit','POST','b',{'statement':'Here is the completed homepage','reference':'https://example.com/home',
        'screenshots':[image_payload(),image_payload('desktop.png')]})
    assert result.status_code==200, result.text
    data=result.json()
    images=data['delivery_plan']['items'][0]['screenshots']
    assert len(images)==2 and data['audit_valid']
    first=images[0]
    assert len(first['sha256'])==64
    # Authorized parties only; HTTP Basic for public mode is a further outer gate.
    assert client.get(f'/api/cases/{data["id"]}/evidence/{first["id"]}').status_code==401
    assert c(f'/evidence/{first["id"]}', 'GET','b').status_code==200
    assert c(f'/evidence/{first["id"]}', 'GET','a').headers['content-type']=='image/jpeg'
    # Re-fetch must preserve same metadata/digest.
    assert c().json()['delivery_plan']['items'][0]['screenshots']==images


def test_rejects_invalid_and_excess_uploads(client):
    c,item=plan(client)
    endpoint=f'/delivery-items/{item}/submit'
    common={'statement':'Completed and ready for review'}
    assert c(endpoint,'POST','b',common|{'screenshots':[image_payload()]*3}).status_code==422
    assert c(endpoint,'POST','b',common|{'screenshots':[{'name':'evil.png','data':base64.b64encode(b'hello world'*5).decode()}]}).status_code==422
    assert c(endpoint,'POST','a',common|{'screenshots':[image_payload()]}).status_code==403
    assert c().json()['delivery_plan']['items'][0]['status']=='pending'


def test_disputed_submission_keeps_previous_images(client):
    c,item=plan(client)
    first=c(f'/delivery-items/{item}/submit','POST','b',{'statement':'First attempt submitted','screenshots':[image_payload('first.png')]}).json()
    before=first['delivery_plan']['items'][0]['screenshots'][0]['id']
    c(f'/delivery-items/{item}/review','POST','a',{'accepted':False,'note':'Mobile menu is broken'})
    newer=c(f'/delivery-items/{item}/submit','POST','b',{'statement':'Fixed the mobile navigation','screenshots':[image_payload('fixed.png')]}).json()
    listed=newer['delivery_plan']['items'][0]
    assert listed['screenshots'][0]['name']=='fixed.png'
    assert listed['earlier_screenshots'][0]['id']==before
    assert c(f'/evidence/{before}', 'GET','a').status_code==200
    assert newer['audit_valid']


def test_ai_requires_review_role_and_reuses_saved_insight(client,monkeypatch):
    c,item=plan(client)
    c(f'/delivery-items/{item}/submit','POST','b',{'statement':'I have finished the mobile page','screenshots':[image_payload()]})
    assert c(f'/delivery-items/{item}/check-evidence','POST','b',{}).status_code==403
    calls=[]
    def fake(images,statement,criteria,url):
        calls.append((statement,criteria))
        return {'visible':'A homepage is visible','uncertain':'Menu behavior cannot be verified',
                'next_check':'Try the navigation on a phone','page_note':'Page not checked','mode':'meta_muse_spark_1_3'}
    monkeypatch.setattr(evidence,'review_with_meta',fake)
    checked=c(f'/delivery-items/{item}/check-evidence','POST','a',{})
    assert checked.status_code==200,checked.text
    insight=checked.json()['delivery_plan']['items'][0]['evidence_insight']
    assert 'homepage' in insight['visible'] and len(calls)==1
    assert c(f'/delivery-items/{item}/check-evidence','POST','a',{}).status_code==200
    assert len(calls)==1
    result=c(f'/delivery-items/{item}/review','POST','a',{'accepted':True}).json()
    assert result['status']=='completed' and result['audit_valid']


def test_public_url_blocks_private_and_http(monkeypatch):
    assert 'Only publicly' in evidence.public_page_text('http://example.com')[1]
    assert 'Only publicly' in evidence.public_page_text('https://localhost')[1]
    assert 'Only publicly' in evidence.public_page_text('https://127.0.0.1/admin')[1]
    assert 'Only publicly' in evidence.public_page_text('https://example.com:8443/')[1]
    import socket
    monkeypatch.setattr(socket,'getaddrinfo',lambda *args,**kwargs:[(socket.AF_INET,socket.SOCK_STREAM,6,'',('10.1.2.3',443))])
    assert 'Only publicly' in evidence.public_page_text('https://example.com')[1]
