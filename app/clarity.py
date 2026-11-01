from __future__ import annotations

import json
import re
from datetime import datetime

from .engine import _money
from .storage import canon, utcnow


FIELDS = ("price", "deadline", "scope")


def normalize(field: str, value: str) -> str:
    value = value.strip()
    if field == "price":
        amount = _money(value)
        return f"{amount[0]}{amount[1]}" if amount else ""
    if field == "deadline":
        for pattern in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d %B %Y", "%d-%B-%Y", "%d %b %Y", "%d-%b-%Y"):
            try:
                return datetime.strptime(value, pattern).date().isoformat()
            except ValueError:
                pass
    return " ".join(re.sub(r"[^\w\s]", " ", value.casefold()).split())


def inspect(db, row, who: str) -> dict:
    revision = int(row["offer_revision"])
    check = db.execute("SELECT * FROM clarity_checks WHERE case_id=? AND revision=?", (row["id"], revision)).fetchone()
    if not check:
        return {"requested": False, "ready": True, "state": "not_requested", "submitted": {"a": False, "b": False}, "checks": [], "mine": None}
    responses = {r["party"]: json.loads(r["answers_json"]) for r in db.execute(
        "SELECT party, answers_json FROM clarity_answers WHERE case_id=? AND revision=?", (row["id"], revision))}
    submitted = {p: p in responses for p in ("a", "b")}
    result = {"requested": True, "ready": False, "revision": revision,
              "submitted": submitted, "checks": [], "mine": responses.get(who),
              "state": "awaiting_other" if submitted[who] else "awaiting_you"}
    if not all(submitted.values()):
        return result
    terms = json.loads(row["terms_json"])
    for field in FIELDS:
        a = responses["a"][field]
        b = responses["b"][field]
        reference = terms[field]
        a_matches_offer = normalize(field, a) == normalize(field, reference)
        b_matches_offer = normalize(field, b) == normalize(field, reference)
        result["checks"].append({"field": field, "matches": a_matches_offer and b_matches_offer,
                                 "a_matches_offer": a_matches_offer, "b_matches_offer": b_matches_offer,
                                 "a": a, "b": b, "agreed": reference})
    result["ready"] = all(check["matches"] for check in result["checks"])
    result["state"] = "aligned" if result["ready"] else "differences"
    return result


def request(db, row, who: str) -> None:
    db.execute("INSERT OR IGNORE INTO clarity_checks(case_id,revision,requested_by,created_at) VALUES(?,?,?,?)",
               (row["id"], row["offer_revision"], who, utcnow()))


def answer(db, row, who: str, answers: dict[str, str]) -> bool:
    if not db.execute("SELECT 1 FROM clarity_checks WHERE case_id=? AND revision=?", (row["id"], row["offer_revision"])).fetchone():
        raise ValueError("No understanding check has been requested")
    previous = db.execute("SELECT answers_json FROM clarity_answers WHERE case_id=? AND revision=? AND party=?",
                          (row["id"], row["offer_revision"], who)).fetchone()
    if previous and json.loads(previous["answers_json"]) == answers:
        return False
    db.execute("""INSERT INTO clarity_answers(case_id,revision,party,answers_json,created_at)
                  VALUES(?,?,?,?,?) ON CONFLICT(case_id,revision,party) DO UPDATE SET
                  answers_json=excluded.answers_json, created_at=excluded.created_at""",
               (row["id"], row["offer_revision"], who, canon(answers), utcnow()))
    return True
