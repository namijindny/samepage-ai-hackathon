"""Tiny transparent smoke benchmark; curated fixture ≠ field validation."""
import json
from pathlib import Path
from app.engine import demo_detect

CASES = Path(__file__).resolve().parents[1] / 'tests' / 'fixtures' / 'drift_cases.jsonl'
TERMS = {'price':'₦120,000','deadline':'Friday','scope':'Repair vehicle engine'}


def main():
    items=[json.loads(s) for s in CASES.read_text().splitlines() if s.strip()]
    passed=0
    for i,case in enumerate(items,1):
        result=demo_detect(case['text'], TERMS)
        ok=result.intent==case['intent'] and sorted(x['field'] for x in result.changes)==sorted(case['fields'])
        passed+=ok
        print(f'{"PASS" if ok else "FAIL"} {i:02d}: expected {case["intent"]}/{case["fields"]}; got {result.intent}/{[x["field"] for x in result.changes]}')
    print(f'\nCurated offline fixture agreement: {passed}/{len(items)}. NOT a measure of AI quality or field accuracy.')


if __name__=='__main__':main()
