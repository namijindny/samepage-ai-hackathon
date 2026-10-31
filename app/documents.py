import json
from fastapi import HTTPException
from .storage import verify_chain


def approved_documents(db, case):
    if not (case["a_confirmed"] and case["b_confirmed"]):
        raise HTTPException(409, "Both people must approve the agreement first")

    events = db.execute(
        "SELECT * FROM audit WHERE case_id=? ORDER BY id", (case["id"],)
    ).fetchall()
    if not verify_chain(events):
        raise HTTPException(409, "Agreement history could not be verified")

    initial = next((e for e in events if e["event"] == "case_created"), None)
    if initial is None:
        raise HTTPException(409, "Original terms are unavailable")

    created = json.loads(initial["payload_json"])
    original_approvals = {}
    original_terms = created["terms"]
    revisions = []
    for event in events:
        details = json.loads(event["payload_json"])
        if event["event"] == "counteroffer_sent":
            original_terms = details["terms"]
            original_approvals = {}
        elif event["event"] == "initial_confirmed" and details["version"] == 1:
            original_approvals[details["party"]] = event["created_at"]
        elif event["event"] == "new_version_applied":
            proposal_id = details["proposal"]
            approvals = {}
            for approval in events:
                if approval["event"] != "proposal_approved_by_party":
                    continue
                accepted = json.loads(approval["payload_json"])
                if accepted["proposal"] == proposal_id:
                    approvals[accepted["party"]] = approval["created_at"]
            if set(approvals) != {"a", "b"}:
                raise HTTPException(409, "Agreement approval record is incomplete")
            revisions.append({
                "version": details["version"],
                "terms": details["terms"],
                "approved_at": event["created_at"],
                "approvals": approvals,
            })

    if set(original_approvals) != {"a", "b"}:
        raise HTTPException(409, "Original confirmation record is incomplete")

    documents = [{
        "version": 1,
        "terms": original_terms,
        "approved_at": max(original_approvals.values()),
        "approvals": original_approvals,
    }, *revisions]

    if documents[-1]["version"] != case["version"]:
        raise HTTPException(409, "Agreement version history is incomplete")

    for item in documents:
        item.update({
            "case_id": case["id"],
            "title": case["title"],
            "party_a": case["party_a"],
            "party_b": case["party_b"],
            "initiator": case["party_a"],
            "recipient": case["party_b"],
            "current": item["version"] == case["version"],
        })
    return documents
