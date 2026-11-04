from __future__ import annotations

import getpass
import os
from app.conversation import analyze

TERMS = {"price": "₦120,000", "deadline": "Friday", "scope": "Repair vehicle engine"}
PARTIES = {"a": "Amara", "b": "Bola"}

SCENARIOS = [
    (
        "Firm change after negotiation",
        [
            ("a", "The repair costs ₦120,000 and will finish on Friday."),
            ("b", "Can you finish on Monday instead?"),
            ("a", "I propose finishing on Monday and adding ₦40,000 to the price."),
        ],
        "change_proposal", {"deadline", "price"},
    ),
    (
        "Unanswered question",
        [
            ("a", "The repair will finish Friday."),
            ("b", "Could we finish on Monday?"),
        ],
        "question", set(),
    ),
    (
        "Conditional promise",
        [
            ("a", "Friday is the agreed date."),
            ("b", "If the parts arrive, I can finish on Monday."),
        ],
        "conditional", set(),
    ),
    (
        "Withdrawal of a previous offer",
        [
            ("b", "I propose finishing on Monday."),
            ("b", "I withdraw my Monday proposal."),
        ],
        "withdrawal", set(),
    ),
    (
        "Acceptance is not app approval",
        [
            ("b", "I propose finishing on Monday."),
            ("a", "Agreed, finish on Monday."),
        ],
        "no_change", set(),
    ),
]


def main():
    key = os.environ.get("MODEL_API_KEY") or getpass.getpass("Meta Model API key (hidden): ").strip()
    if not key:
        raise SystemExit("No API key was supplied. No requests were made.")
    os.environ["MODEL_API_KEY"] = key
    os.environ["ANALYSIS_MODE"] = "meta"
    os.environ.setdefault("MAX_META_CALLS_PER_DAY", "10")
    passed = 0
    completed = 0
    for label, turns, expected_intent, expected_fields in SCENARIOS:
        msgs = [
            {"id": f"m{index+1}", "author": party, "body": message,
             "created_at": f"2026-11-01T12:{index:02d}:00Z"}
            for index, (party, message) in enumerate(turns)
        ]
        try:
            result = analyze(msgs, TERMS, PARTIES)
        except Exception as error:
            print(f"{label}: unavailable ({type(error).__name__})")
            break
        completed += 1
        actual_fields = {change["field"] for change in result["changes"]}
        success = result["intent"] == expected_intent and actual_fields == expected_fields
        passed += success
        print(f"{label}: {'PASS' if success else 'FAIL'} — {result['intent']}, {sorted(actual_fields)}")
    print(f"Completed: {completed}/{len(SCENARIOS)}. Matched expectations: {passed}/{completed or 1}.")
    print("These are synthetic evaluation cases, not proof of real-world accuracy or competitor superiority.")


if __name__ == "__main__":
    main()
