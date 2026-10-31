from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from app.engine import detect

CURRENT = {"price": "₦120,000", "deadline": "Friday", "scope": "Repair vehicle engine"}
FILE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "semantic_cases.jsonl"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a controlled Meta agreement-analysis evaluation")
    parser.add_argument("--live", action="store_true", help="Explicitly authorize paid Meta API calls")
    parser.add_argument("--limit", type=int, default=3, help="Number of cases to test, 1–10")
    args = parser.parse_args()
    cases = [json.loads(line) for line in FILE.read_text(encoding="utf8").splitlines()]
    if not args.live:
        print(f"Prepared {len(cases)} labeled development cases. No API requests made.")
        print("Pass --live to test a limited sample with your Meta credits.")
        return
    if not 1 <= args.limit <= 10:
        parser.error("--limit must be between 1 and 10")
    if not os.environ.get("MODEL_API_KEY"):
        parser.error("Set MODEL_API_KEY in the environment before using --live")
    os.environ["ANALYSIS_MODE"] = "meta"
    matched_intent = matched_fields = 0
    for index, case in enumerate(cases[:args.limit], 1):
        try:
            finding = detect(case["message"], CURRENT)
        except Exception as error:
            print(f"Case {index}: API error: {type(error).__name__}: {error}")
            break
        fields = [change["field"] for change in finding.changes]
        correct_intent = finding.intent == case["expected_intent"]
        correct_fields = set(fields) == set(case["expected_fields"])
        matched_intent += correct_intent
        matched_fields += correct_fields
        print(f"Case {index}: intent={finding.intent} fields={fields}; expected={case['expected_intent']} {case['expected_fields']}")
    print(f"Matched intent on {matched_intent} of {min(index, args.limit)} attempted cases; matched fields on {matched_fields}.")
    print("This is a small labeled development set, not a generalization or competitor benchmark.")


if __name__ == "__main__":
    main()
