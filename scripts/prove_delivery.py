"""Run a synthetic, two-participant delivery proof without Meta API calls."""
from __future__ import annotations

import tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from app import storage
from app.main import app


def run():
    original = storage.DB
    with tempfile.TemporaryDirectory(prefix='samepage-proof-') as folder:
        storage.DB = Path(folder) / 'proof.sqlite3'
        try:
            storage.initialize()
            with TestClient(app) as client:
                response = client.post('/api/cases', json={
                    'title':'Small business website', 'party_a':'Alex', 'party_b':'Sam',
                    'price':'$1,000', 'deadline':'10 November 2026',
                    'scope':'Responsive website with an invoice download', 'responsible_party':'b',
                })
                assert response.status_code == 201, response.text
                result = response.json()
                case_id = result['case_id']
                def call(who, endpoint, body=None):
                    res=client.post(f'/api/cases/{case_id}{endpoint}',json=body,
                        headers={'X-Party-Key':result[f'party_{who}_key']})
                    assert res.status_code in (200,201),f'{endpoint}: {res.status_code} {res.text}'
                    return res.json()
                call('b','/confirm')
                planned=call('a','/delivery-plan',{'items':[
                    {'description':'Responsive homepage', 'acceptance_criteria':'Works on mobile and desktop'},
                    {'description':'Invoice download', 'acceptance_criteria':'PDF downloads with the correct amount'},
                ]})
                plan=planned['delivery_plan'];first,second=[item['id'] for item in plan['items']]
                call('b',f'/delivery-plan/{plan["id"]}/respond',{'accepted':True})
                call('b',f'/delivery-items/{first}/submit',{
                    'statement':'Homepage is ready on desktop', 'reference':'Screenshot A'
                })
                disputed=call('a',f'/delivery-items/{first}/review',{
                    'accepted':False, 'note':'Mobile navigation does not work'
                })
                assert disputed['status']=='disputed'
                call('b',f'/delivery-items/{first}/submit',{
                    'statement':'Mobile navigation fixed and tested', 'reference':'Screenshot B'
                })
                partial=call('a',f'/delivery-items/{first}/review',{'accepted':True})
                assert partial['status']=='in_progress'
                call('b',f'/delivery-items/{second}/submit',{
                    'statement':'PDF invoice generated with correct amount', 'reference':'Invoice sample 003'
                })
                final=call('a',f'/delivery-items/{second}/review',{'accepted':True})
                assert final['status']=='completed'
                assert final['delivery_plan']['accepted_count']==2
                assert final['audit_valid']
                events=[e['event'] for e in final['history']]
                assert events.count('deliverable_disputed')==1
                assert events.count('deliverable_resubmitted')==1
                print('SAMEPAGE DELIVERY PROOF — PASS')
                print('1. Initiator and recipient accepted the same agreement')
                print('2. Recipient independently approved the delivery checklist')
                print('3. Responsible participant submitted evidence for item 1')
                print('4. Reviewer disputed item 1 and specified the problem')
                print('5. Corrected evidence was resubmitted and item 1 accepted')
                print('6. Item 2 was submitted and accepted')
                print('7. Completion required both items; evidence history validated')
                print(f'Final status: {final["status"]} | {final["delivery_plan"]["accepted_count"]} of 2 items accepted | Audit chain valid')
        finally:
            storage.DB = original


if __name__ == '__main__':
    run()
