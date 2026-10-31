"""SamePage Hackathon prototype — do not expose publicly without production auth."""
from __future__ import annotations
import json
import logging
import os
from pathlib import Path
import sqlite3
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .engine import detect
from .documents import approved_documents
from . import storage as s
from . import workflow as w

s.initialize()
logger = logging.getLogger(__name__)
app = FastAPI(title="SamePage AI — Agreement Drift Guardian", version="0.5.0")
ROOT = Path(__file__).resolve().parents[1]
app.mount("/static", StaticFiles(directory=ROOT / "web"), name="static")


class CreateCase(BaseModel):
    title: str = Field(min_length=3, max_length=100)
    party_a: str = Field(min_length=2, max_length=70)
    party_b: str = Field(min_length=2, max_length=70)
    price: str = Field(min_length=1, max_length=140)
    deadline: str = Field(min_length=1, max_length=140)
    scope: str = Field(min_length=2, max_length=400)
    responsible_party: str = Field(default="b", pattern="^[ab]$")


class Message(BaseModel):
    message: str = Field(min_length=3, max_length=2500)


class Counteroffer(BaseModel):
    price: str = Field(min_length=1, max_length=140)
    deadline: str = Field(min_length=1, max_length=140)
    scope: str = Field(min_length=2, max_length=400)
    note: str = Field(default='', max_length=500)


class ManualChange(BaseModel):
    price: str = Field(min_length=1, max_length=140)
    deadline: str = Field(min_length=1, max_length=140)
    scope: str = Field(min_length=2, max_length=400)
    reason: str = Field(default='', max_length=500)


class Completion(BaseModel):
    statement: str = Field(min_length=6, max_length=1500)
    reference: str = Field(default='', max_length=300)


class CompletionDecision(BaseModel):
    accepted: bool
    note: str = Field(default='', max_length=1000)


def fetch(db, case_id: str):
    row = db.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Case not found")
    return row


def authorize(row, token: str | None) -> str:
    if not token or len(token) > 256:
        raise HTTPException(401, "Party access key required")
    hashed = s.digest(token)
    from hmac import compare_digest
    if compare_digest(hashed, row["hash_a"]): return "a"
    if compare_digest(hashed, row["hash_b"]): return "b"
    raise HTTPException(403, "Invalid party access key")


def view(db, row, who: str):
    pending = [dict(p) for p in db.execute("SELECT * FROM proposals WHERE case_id=? ORDER BY created_at DESC,id DESC", (row["id"],))]
    for p in pending:
        p["changes"] = json.loads(p.pop("changes_json"))
    audits = db.execute("SELECT * FROM audit WHERE case_id=? ORDER BY id", (row["id"],)).fetchall()
    completion_row = db.execute("SELECT * FROM completion WHERE case_id=?", (row["id"],)).fetchone()
    delivery = dict(completion_row) if completion_row else None
    return {
        "id": row["id"], "title": row["title"],
        "party_a": row["party_a"], "party_b": row["party_b"], "viewer": who,
        "initiator": "a", "recipient": "b", "responsible_party": row["responsible_party"],
        "status": w.status(row, delivery), "completion": delivery,
        "terms": json.loads(row["terms_json"]), "version": row["version"],
        "a_confirmed": bool(row["a_confirmed"]), "b_confirmed": bool(row["b_confirmed"]),
        "active": bool(row["a_confirmed"] and row["b_confirmed"] and not row["declined_at"]),
        "proposals": pending,
        "history": [{"event": a["event"], "created_at": a["created_at"], "payload": json.loads(a["payload_json"])} for a in audits],
        "audit_valid": s.verify_chain(audits),
    }


@app.get("/")
def index():
    return FileResponse(ROOT / "web" / "index.html")


@app.get("/api/health")
def health():
    return {"ok": True, "mode": "meta_muse_spark_1_3" if os.environ.get("ANALYSIS_MODE", "offline_demo").lower() == "meta" else "offline_demo", "public_deployment_ready": False}


@app.post("/api/cases", status_code=201)
def create_case(payload: CreateCase):
    a, b = s.new_token(), s.new_token()
    case_id = s.new_id()
    terms = w.clean_terms({"price": payload.price, "deadline": payload.deadline, "scope": payload.scope})
    with s.connection() as db:
        db.execute("INSERT INTO cases(id,title,party_a,party_b,hash_a,hash_b,terms_json,a_confirmed,responsible_party,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                   (case_id,payload.title.strip(),payload.party_a.strip(),payload.party_b.strip(),s.digest(a),s.digest(b),s.canon(terms),1,payload.responsible_party,s.utcnow()))
        s.record(db,case_id,"case_created",{"terms":terms,"version":1,"initiator":"a","responsible_party":payload.responsible_party})
        s.record(db,case_id,"initial_confirmed",{"party":"a","version":1})
    return {"case_id":case_id,"party_a_key":a,"party_b_key":b,"warning":"Local testing only. Both keys are returned to this browser; not safe for public deployment."}



@app.get("/api/cases/{case_id}")
def get_case(case_id: str, x_party_key: str | None = Header(default=None)):
    with s.connection() as db:
        row=fetch(db,case_id)
        return view(db,row,authorize(row,x_party_key))


@app.get("/api/cases/{case_id}/documents")
def list_documents(case_id: str, x_party_key: str | None = Header(default=None)):
    with s.connection() as db:
        row = fetch(db, case_id)
        authorize(row, x_party_key)
        docs = approved_documents(db, row)
        return [{"version": d["version"], "approved_at": d["approved_at"], "current": d["current"]} for d in docs]


@app.get("/api/cases/{case_id}/documents/{version}")
def get_document(case_id: str, version: int, x_party_key: str | None = Header(default=None)):
    with s.connection() as db:
        row = fetch(db, case_id)
        authorize(row, x_party_key)
        for document in approved_documents(db, row):
            if document["version"] == version:
                return document
        raise HTTPException(404, "Agreement version not found")


@app.post("/api/cases/{case_id}/confirm")
def confirm_case(case_id: str, x_party_key: str | None = Header(default=None)):
    with s.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row=fetch(db,case_id); who=authorize(row,x_party_key)
        if row["declined_at"]:
            raise HTTPException(409,"This offer has been declined")
        if row[f"{who}_confirmed"]:
            return view(db,row,who)
        db.execute(f"UPDATE cases SET {who}_confirmed=1 WHERE id=?",(case_id,))
        s.record(db,case_id,"initial_confirmed",{"party":who,"version":row["version"]})
        return view(db,fetch(db,case_id),who)


@app.post("/api/cases/{case_id}/decline")
def decline_case(case_id: str, payload: Message, x_party_key: str | None = Header(default=None)):
    with s.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row=fetch(db,case_id); who=authorize(row,x_party_key)
        if who != "b" or row["declined_at"] or row["b_confirmed"]:
            raise HTTPException(409,"Only the recipient can decline a pending offer")
        db.execute("UPDATE cases SET declined_at=? WHERE id=?",(s.utcnow(),case_id))
        s.record(db,case_id,"offer_declined",{"party":who,"reason":payload.message})
        return view(db,fetch(db,case_id),who)


@app.post("/api/cases/{case_id}/counter")
def counter_case(case_id: str, payload: Counteroffer, x_party_key: str | None = Header(default=None)):
    with s.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row=fetch(db,case_id); who=authorize(row,x_party_key)
        if who != "b" or row["declined_at"] or row["b_confirmed"]:
            raise HTTPException(409,"Counteroffers are available only to a recipient reviewing an initial offer")
        revised = w.clean_terms({"price": payload.price, "deadline": payload.deadline, "scope": payload.scope})
        changes = w.changes_between(json.loads(row["terms_json"]),revised)
        db.execute("UPDATE cases SET terms_json=?, a_confirmed=0, b_confirmed=1 WHERE id=?",(s.canon(revised),case_id))
        s.record(db,case_id,"counteroffer_sent",{"party":"b","version":1,"changes":changes,"note":payload.note,"terms":revised})
        s.record(db,case_id,"initial_confirmed",{"party":"b","version":1})
        return view(db,fetch(db,case_id),who)


@app.post("/api/cases/{case_id}/proposals")
def propose(case_id: str, payload: Message, x_party_key: str | None = Header(default=None)):
    with s.connection() as db:
        row=fetch(db,case_id)
        who=authorize(row,x_party_key)
        if row["declined_at"] or not (row["a_confirmed"] and row["b_confirmed"]):
            raise HTTPException(409,"Both parties must confirm the original agreement first")
        if db.execute("SELECT 1 FROM proposals WHERE case_id=? AND status='pending'",(case_id,)).fetchone():
            raise HTTPException(409,"Resolve the pending proposal before creating another")
        if db.execute("SELECT 1 FROM completion WHERE case_id=?", (case_id,)).fetchone():
            raise HTTPException(409,"Resolve the delivery review before changing the terms")
        current=json.loads(row["terms_json"])
        base_version = row["version"]
        try: finding=detect(payload.message,current)
        except Exception as exc:
            logger.warning("Agreement analysis failed: %s (status %s)", type(exc).__name__, getattr(exc, "status_code", "unknown"))
            name = type(exc).__name__.lower()
            message = str(exc).lower()
            if 'ratelimit' in name or 'limit' in message:
                detail = 'The analysis allowance is unavailable. No changes were saved.'
            elif 'authentication' in name or '401' in message or 'key is missing' in message:
                detail = 'Meta authentication failed. Check the API key and account access. No changes were saved.'
            elif 'permission' in name or 'billing' in message or '403' in message:
                detail = 'Meta access or billing is restricted. Check your account. No changes were saved.'
            elif 'timeout' in name:
                detail = 'Meta did not respond in time. No changes were saved.'
            else:
                detail = 'Analysis could not be completed. Check the server log and model settings; no changes were saved.'
            raise HTTPException(503,detail) from exc
        if not finding.changes:
            return {"proposal_created": False, "finding":finding.__dict__}
        proposal_id=s.new_id()
        changes_with_before = [{**c, "old_value": current.get(c["field"], "")} for c in finding.changes]
        # Recheck state transactionally before saving as AI calls can take time.
        db.execute("BEGIN IMMEDIATE")
        row=fetch(db,case_id)
        if row["version"]!=base_version or db.execute("SELECT 1 FROM proposals WHERE case_id=? AND status='pending'",(case_id,)).fetchone():
            raise HTTPException(409,"Agreement changed or another proposal was created; retry")
        db.execute("INSERT INTO proposals(id,case_id,base_version,author,source_text,changes_json,mode,created_at) VALUES(?,?,?,?,?,?,?,?)",
                   (proposal_id,case_id,row["version"],who,payload.message,s.canon(changes_with_before),finding.mode,s.utcnow()))
        s.record(db,case_id,"change_proposed",{"proposal":proposal_id,"party":who,"changes":changes_with_before,"analysis_mode":finding.mode,"source":payload.message})
        return {"proposal_created":True,"finding":finding.__dict__,"case":view(db,fetch(db,case_id),who)}


@app.post("/api/cases/{case_id}/manual-proposals")
def manual_proposal(case_id: str, payload: ManualChange, x_party_key: str | None = Header(default=None)):
    with s.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row=fetch(db,case_id); who=authorize(row,x_party_key)
        if w.status(row) != "in_progress":
            raise HTTPException(409,"This agreement is not accepting changes")
        if db.execute("SELECT 1 FROM completion WHERE case_id=?",(case_id,)).fetchone():
            raise HTTPException(409,"A delivery review must be resolved first")
        if db.execute("SELECT 1 FROM proposals WHERE case_id=? AND status='pending'",(case_id,)).fetchone():
            raise HTTPException(409,"Resolve the pending proposal first")
        values=w.clean_terms({"price":payload.price,"deadline":payload.deadline,"scope":payload.scope})
        changes=w.changes_between(json.loads(row["terms_json"]),values)
        proposal_id=s.new_id()
        db.execute("INSERT INTO proposals(id,case_id,base_version,author,source_text,changes_json,mode,a_approved,b_approved,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                   (proposal_id,case_id,row["version"],who,payload.reason.strip() or 'Updated terms proposed directly',s.canon(changes),"manual",int(who=='a'),int(who=='b'),s.utcnow()))
        s.record(db,case_id,"change_proposed",{"party":who,"proposal":proposal_id,"changes":changes,"analysis_mode":"manual","source":payload.reason.strip()})
        s.record(db,case_id,"proposal_approved_by_party",{"party":who,"proposal":proposal_id})
        return view(db,fetch(db,case_id),who)


@app.post("/api/cases/{case_id}/proposals/{proposal_id}/approve")
def approve(case_id: str,proposal_id: str,x_party_key: str | None=Header(default=None)):
    with s.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row=fetch(db,case_id);who=authorize(row,x_party_key)
        prop=db.execute("SELECT * FROM proposals WHERE id=? AND case_id=?",(proposal_id,case_id)).fetchone()
        if not prop:raise HTTPException(404,"Proposal not found")
        if prop["status"]!="pending":raise HTTPException(409,"Proposal already resolved")
        if w.status(row) != "in_progress":raise HTTPException(409,"Agreement is not accepting amendments")
        if prop["base_version"]!=row["version"]:raise HTTPException(409,"Stale proposal: base version changed")
        if prop[f"{who}_approved"]:
            return view(db,row,who)
        db.execute(f"UPDATE proposals SET {who}_approved=1 WHERE id=?",(proposal_id,))
        s.record(db,case_id,"proposal_approved_by_party",{"proposal":proposal_id,"party":who})
        p=db.execute("SELECT * FROM proposals WHERE id=?",(proposal_id,)).fetchone()
        if p["a_approved"] and p["b_approved"]:
            updated=json.loads(row["terms_json"])
            for c in json.loads(prop["changes_json"]):updated[c["field"]]=c["new_value"]
            db.execute("UPDATE cases SET terms_json=?,version=version+1 WHERE id=?",(s.canon(updated),case_id))
            db.execute("UPDATE proposals SET status='applied' WHERE id=?",(proposal_id,))
            s.record(db,case_id,"new_version_applied",{"proposal":proposal_id,"version":row["version"]+1,"terms":updated})
        return view(db,fetch(db,case_id),who)


@app.post("/api/cases/{case_id}/proposals/{proposal_id}/reject")
def reject(case_id: str,proposal_id: str,x_party_key: str | None=Header(default=None)):
    with s.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row=fetch(db,case_id);who=authorize(row,x_party_key)
        prop=db.execute("SELECT * FROM proposals WHERE id=? AND case_id=?",(proposal_id,case_id)).fetchone()
        if not prop:raise HTTPException(404,"Proposal not found")
        if prop["status"]!="pending":raise HTTPException(409,"Proposal already resolved")
        db.execute("UPDATE proposals SET status='rejected' WHERE id=?",(proposal_id,))
        s.record(db,case_id,"proposal_rejected",{"proposal":proposal_id,"party":who})
        return view(db,fetch(db,case_id),who)


@app.post("/api/cases/{case_id}/completion")
def submit_completion(case_id: str, payload: Completion, x_party_key: str | None = Header(default=None)):
    with s.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = fetch(db,case_id); who=authorize(row,x_party_key)
        if who != row["responsible_party"]:
            raise HTTPException(403,"Only the person responsible for delivery may submit completion")
        if w.status(row) not in ("in_progress",):
            raise HTTPException(409,"The agreement is not active")
        if db.execute("SELECT 1 FROM proposals WHERE case_id=? AND status='pending'",(case_id,)).fetchone():
            raise HTTPException(409,"Resolve proposed changes before submitting delivery")
        if db.execute("SELECT 1 FROM completion WHERE case_id=?",(case_id,)).fetchone():
            raise HTTPException(409,"Delivery already submitted; await review")
        now=s.utcnow()
        db.execute("INSERT INTO completion(case_id,version,submitted_by,submitted_at,statement,reference) VALUES(?,?,?,?,?,?)",
                   (case_id,row["version"],who,now,payload.statement.strip(),payload.reference.strip() or None))
        s.record(db,case_id,"delivery_submitted",{"party":who,"version":row["version"],"statement":payload.statement.strip(),"reference":payload.reference.strip()})
        return view(db,fetch(db,case_id),who)


@app.post("/api/cases/{case_id}/completion/review")
def review_completion(case_id: str, payload: CompletionDecision, x_party_key: str | None = Header(default=None)):
    with s.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row=fetch(db,case_id); who=authorize(row,x_party_key)
        if who == row["responsible_party"]:
            raise HTTPException(403,"Only the other participant may review delivery")
        delivery=db.execute("SELECT * FROM completion WHERE case_id=?",(case_id,)).fetchone()
        if not delivery or delivery["status"]!="submitted" or delivery["version"]!=row["version"]:
            raise HTTPException(409,"No delivery is awaiting review")
        if not payload.accepted and not payload.note.strip():
            raise HTTPException(422,"Provide a reason for disputing delivery")
        status = "accepted" if payload.accepted else "disputed"
        db.execute("UPDATE completion SET status=?,reviewed_by=?,reviewed_at=?,review_note=? WHERE case_id=?",
                   (status,who,s.utcnow(),payload.note.strip(),case_id))
        s.record(db,case_id,"delivery_accepted" if payload.accepted else "delivery_disputed",
                 {"party":who,"note":payload.note.strip(),"version":row["version"]})
        return view(db,fetch(db,case_id),who)


@app.post("/api/cases/{case_id}/completion/resubmit")
def resubmit_completion(case_id: str, payload: Completion, x_party_key: str | None = Header(default=None)):
    with s.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row=fetch(db,case_id); who=authorize(row,x_party_key)
        delivery=db.execute("SELECT * FROM completion WHERE case_id=?",(case_id,)).fetchone()
        if who != row["responsible_party"]:
            raise HTTPException(403,"Only the person responsible for delivery can resubmit")
        if not delivery or delivery["status"]!="disputed" or delivery["version"]!=row["version"]:
            raise HTTPException(409,"There is no disputed delivery to resubmit")
        db.execute("UPDATE completion SET statement=?,reference=?,submitted_at=?,status='submitted',reviewed_by=NULL,reviewed_at=NULL,review_note=NULL WHERE case_id=?",
                   (payload.statement.strip(),payload.reference.strip() or None,s.utcnow(),case_id))
        s.record(db,case_id,"delivery_resubmitted",{"party":who,"version":row["version"],"statement":payload.statement.strip(),"reference":payload.reference.strip(),"previous_review":delivery["review_note"]})
        return view(db,fetch(db,case_id),who)
