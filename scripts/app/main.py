"""SamePage Hackathon prototype — do not expose publicly without production auth."""
from __future__ import annotations
import json
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

s.initialize()
app = FastAPI(title="SamePage AI — Agreement Drift Guardian", version="0.4.0")
ROOT = Path(__file__).resolve().parents[1]
app.mount("/static", StaticFiles(directory=ROOT / "web"), name="static")


class CreateCase(BaseModel):
    title: str = Field(min_length=3, max_length=100)
    party_a: str = Field(min_length=2, max_length=70)
    party_b: str = Field(min_length=2, max_length=70)
    price: str = Field(min_length=1, max_length=140)
    deadline: str = Field(min_length=1, max_length=140)
    scope: str = Field(min_length=2, max_length=400)


class Message(BaseModel):
    message: str = Field(min_length=3, max_length=2500)


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
        p.pop("changes_json", None)
    audits = db.execute("SELECT * FROM audit WHERE case_id=? ORDER BY id", (row["id"],)).fetchall()
    return {
        "id": row["id"], "title": row["title"],
        "party_a": row["party_a"], "party_b": row["party_b"], "viewer": who,
        "terms": json.loads(row["terms_json"]), "version": row["version"],
        "a_confirmed": bool(row["a_confirmed"]), "b_confirmed": bool(row["b_confirmed"]),
        "active": bool(row["a_confirmed"] and row["b_confirmed"]),
        "proposals": pending,
        "history": [{"event":a["event"],"created_at":a["created_at"],"payload":json.loads(a["payload_json"]),"hash":a["hash"][:14]} for a in audits],
        "audit_valid": s.verify_chain(audits),
        "privacy_note": "Local prototype only. Audit hashes are not independent signatures or legal proof."
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
    terms = {"price": payload.price.strip(), "deadline":payload.deadline.strip(), "scope":payload.scope.strip()}
    with s.connection() as db:
        db.execute("INSERT INTO cases(id,title,party_a,party_b,hash_a,hash_b,terms_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
                   (case_id,payload.title.strip(),payload.party_a.strip(),payload.party_b.strip(),s.digest(a),s.digest(b),s.canon(terms),s.utcnow()))
        s.record(db,case_id,"case_created",{"terms":terms,"version":1})
    return {"case_id":case_id,"party_a_key":a,"party_b_key":b, "warning":"Keys shown once for LOCAL testing. Share securely and separately for real use."}


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
        if row[f"{who}_confirmed"]:
            return view(db,row,who)
        db.execute(f"UPDATE cases SET {who}_confirmed=1 WHERE id=?",(case_id,))
        s.record(db,case_id,"initial_confirmed",{"party":who,"version":row["version"]})
        return view(db,fetch(db,case_id),who)


@app.post("/api/cases/{case_id}/proposals")
def propose(case_id: str, payload: Message, x_party_key: str | None = Header(default=None)):
    with s.connection() as db:
        row=fetch(db,case_id)
        who=authorize(row,x_party_key)
        if not (row["a_confirmed"] and row["b_confirmed"]):
            raise HTTPException(409,"Both parties must confirm the original agreement first")
        if db.execute("SELECT 1 FROM proposals WHERE case_id=? AND status='pending'",(case_id,)).fetchone():
            raise HTTPException(409,"Resolve the pending proposal before creating another")
        current=json.loads(row["terms_json"])
        base_version = row["version"]
        try: finding=detect(payload.message,current)
        except Exception as exc:
            raise HTTPException(503,"Analysis is unavailable or the daily request limit has been reached. No agreement changes were made.") from exc
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


@app.post("/api/cases/{case_id}/proposals/{proposal_id}/approve")
def approve(case_id: str,proposal_id: str,x_party_key: str | None=Header(default=None)):
    with s.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row=fetch(db,case_id);who=authorize(row,x_party_key)
        prop=db.execute("SELECT * FROM proposals WHERE id=? AND case_id=?",(proposal_id,case_id)).fetchone()
        if not prop:raise HTTPException(404,"Proposal not found")
        if prop["status"]!="pending":raise HTTPException(409,"Proposal already resolved")
        if prop["base_version"]!=row["version"]:raise HTTPException(409,"Stale proposal: base version changed")
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
