"""SamePage Hackathon prototype — do not expose publicly without production auth."""
from __future__ import annotations
import base64
import binascii
import hmac
import json
import logging
import os
from pathlib import Path
import sqlite3
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .engine import detect, MetaResponseError
from .conversation import analyze, recover_explicit_deadline, recover_confirmed_price
from .documents import approved_documents
from . import storage as s
from . import workflow as w
from . import clarity as c
from . import fulfilment
from . import evidence

s.initialize()
logger = logging.getLogger(__name__)
app = FastAPI(title="SamePage AI", version="1.1.1")
ROOT = Path(__file__).resolve().parents[1]
app.mount("/static", StaticFiles(directory=ROOT / "web"), name="static")


def public_demo_enabled() -> bool:
    return os.environ.get("PUBLIC_DEMO", "").strip().lower() in ("1", "true", "yes")


def validate_demo_settings() -> None:
    if not public_demo_enabled():
        return
    password = os.environ.get("DEMO_PASSWORD", "")
    if len(password) < 16:
        raise RuntimeError("PUBLIC_DEMO requires DEMO_PASSWORD with at least 16 characters")
    if not os.environ.get("SAMEPAGE_DB", ""):
        raise RuntimeError("PUBLIC_DEMO requires SAMEPAGE_DB on persistent storage")
    if os.environ.get("ANALYSIS_MODE", "offline_demo").strip().lower() == "meta":
        if not os.environ.get("MODEL_API_KEY", "").strip():
            raise RuntimeError("Meta analysis requires MODEL_API_KEY")


validate_demo_settings()


def valid_demo_login(header: str) -> bool:
    if not header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(header[6:], validate=True).decode("utf-8")
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return False
    user, sep, password = decoded.partition(":")
    if not sep:
        return False
    expected_user = os.environ.get("DEMO_USERNAME", "judge")
    expected_password = os.environ.get("DEMO_PASSWORD", "")
    return hmac.compare_digest(user.encode("utf-8"), expected_user.encode("utf-8")) and hmac.compare_digest(password.encode("utf-8"), expected_password.encode("utf-8"))


@app.middleware("http")
async def demo_access(request: Request, call_next):
    if public_demo_enabled():
        validate_demo_settings()
        if request.url.path != "/healthz" and not valid_demo_login(request.headers.get("authorization", "")):
            return PlainTextResponse(
                "SamePage competition demo — login required",
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="SamePage demo", charset="UTF-8"', "Cache-Control": "no-store"},
            )
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    if request.url.path.startswith("/api/") or request.url.path == "/":
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"ok": True}


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


class Understanding(BaseModel):
    price: str = Field(min_length=1, max_length=140)
    deadline: str = Field(min_length=1, max_length=140)
    scope: str = Field(min_length=2, max_length=400)


class ConversationMessage(BaseModel):
    message: str = Field(min_length=2, max_length=1200)


class Completion(BaseModel):
    statement: str = Field(min_length=6, max_length=1500)
    reference: str = Field(default='', max_length=300)


class CompletionDecision(BaseModel):
    accepted: bool
    note: str = Field(default='', max_length=1000)


class DeliveryItemSpec(BaseModel):
    description: str = Field(min_length=5, max_length=250)
    acceptance_criteria: str = Field(min_length=5, max_length=350)


class DeliveryPlanRequest(BaseModel):
    items: list[DeliveryItemSpec] = Field(min_length=1, max_length=10)


class DeliveryPlanResponse(BaseModel):
    accepted: bool
    note: str = Field(default='', max_length=700)


class ScreenshotPayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    data: str = Field(min_length=20, max_length=2_700_000)


class EvidenceSubmission(BaseModel):
    statement: str = Field(min_length=8, max_length=1500)
    reference: str = Field(default='', max_length=500)
    screenshots: list[ScreenshotPayload] = Field(default_factory=list, max_length=2)


class DeliveryItemDecision(BaseModel):
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


def conversation_view(db, case_id: str, version: int, revision: int, terms: dict | None = None):
    messages = [dict(r) for r in db.execute(
        "SELECT id, author, body, created_at FROM conversation_messages WHERE case_id=? ORDER BY rowid",
        (case_id,),
    )]
    saved = db.execute(
        "SELECT * FROM conversation_reviews WHERE case_id=? ORDER BY rowid DESC LIMIT 1", (case_id,)
    ).fetchone()
    review = json.loads(saved["result_json"]) if saved else None
    if (review and terms and messages and saved["base_version"] == version
            and saved["base_revision"] == revision):
        review = recover_explicit_deadline(review, messages[-1], terms)
        if len(messages) >= 2:
            review = recover_confirmed_price(review, messages[-2], messages[-1], terms)
    return {
        "messages": messages,
        "review": review,
        "review_id": saved["id"] if saved else None,
        "review_created_at": saved["created_at"] if saved else None,
        "review_current": bool(
            review and messages and review["last_message_id"] == messages[-1]["id"]
            and saved["base_version"] == version and saved["base_revision"] == revision
        ),
    }


def view(db, row, who: str):
    pending = [dict(p) for p in db.execute("SELECT * FROM proposals WHERE case_id=? ORDER BY created_at DESC,id DESC", (row["id"],))]
    for p in pending:
        p["changes"] = json.loads(p.pop("changes_json"))
    audits = db.execute("SELECT * FROM audit WHERE case_id=? ORDER BY id", (row["id"],)).fetchall()
    completion_row = db.execute("SELECT * FROM completion WHERE case_id=?", (row["id"],)).fetchone()
    delivery = dict(completion_row) if completion_row else None
    last_counter = next((event for event in reversed(audits) if event["event"] == "counteroffer_sent"), None)
    counter_changes = json.loads(last_counter["payload_json"]).get("changes", []) if last_counter else []
    plan = fulfilment.get_plan(db,row['id'])
    state = fulfilment.plan_status(plan) or w.status(row, delivery)
    understanding = c.inspect(db, row, who) if state in ("awaiting_recipient", "awaiting_initiator") else {
        "requested": False, "ready": True, "state": "not_applicable",
        "submitted": {"a": False, "b": False}, "checks": [], "mine": None,
    }
    return {
        "id": row["id"], "title": row["title"],
        "party_a": row["party_a"], "party_b": row["party_b"], "viewer": who,
        "initiator": "a", "recipient": "b", "responsible_party": row["responsible_party"],
        "offer_by": row["offer_by"], "offer_revision": row["offer_revision"],
        "offer_note": row["offer_note"], "offer_changes": counter_changes,
        "status": state, "completion": delivery, "delivery_plan": plan,
        "terms": json.loads(row["terms_json"]), "version": row["version"],
        "a_confirmed": bool(row["a_confirmed"]), "b_confirmed": bool(row["b_confirmed"]),
        "active": bool(row["a_confirmed"] and row["b_confirmed"] and not row["declined_at"]),
        "proposals": pending,
        "history": [{"event": a["event"], "created_at": a["created_at"], "payload": json.loads(a["payload_json"])} for a in audits],
        "audit_valid": s.verify_chain(audits),
        "understanding": understanding,
        "conversation": conversation_view(db, row["id"], row["version"], row["offer_revision"], json.loads(row["terms_json"])),
    }


@app.get("/")
def index():
    return FileResponse(ROOT / "web" / "index.html")


@app.get("/api/health")
def health():
    return {"ok": True, "mode": "meta_muse_spark_1_3" if os.environ.get("ANALYSIS_MODE", "offline_demo").lower() == "meta" else "offline_demo", "restricted_demo": public_demo_enabled(), "public_deployment_ready": False}


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
    return {"case_id":case_id,"party_a_key":a,"party_b_key":b,"warning": ("Restricted sample-only demo. The initiator receives an invitation key to share; participant identity is not verified." if public_demo_enabled() else "Local testing only. Both keys are returned to this browser; not safe for public deployment.")}



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
        if w.status(row) not in ("awaiting_recipient", "awaiting_initiator"):
            raise HTTPException(409, "No offer is awaiting confirmation")
        if not c.inspect(db, row, who)["ready"]:
            raise HTTPException(409, "Resolve the understanding differences before accepting the offer")
        db.execute(f"UPDATE cases SET {who}_confirmed=1 WHERE id=?",(case_id,))
        s.record(db,case_id,"initial_confirmed",{"party":who,"version":row["version"]})
        return view(db,fetch(db,case_id),who)


@app.post("/api/cases/{case_id}/understanding/request")
def request_understanding(case_id: str, x_party_key: str | None = Header(default=None)):
    with s.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = fetch(db, case_id)
        who = authorize(row, x_party_key)
        if w.status(row) not in ("awaiting_recipient", "awaiting_initiator"):
            raise HTTPException(409, "Understanding can only be checked before the offer is accepted")
        existing = c.inspect(db, row, who)
        if not existing["requested"]:
            c.request(db, row, who)
            s.record(db, case_id, "understanding_requested", {"party": who, "offer_revision": row["offer_revision"]})
        return view(db, fetch(db, case_id), who)


@app.post("/api/cases/{case_id}/understanding")
def submit_understanding(case_id: str, payload: Understanding, x_party_key: str | None = Header(default=None)):
    with s.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = fetch(db, case_id)
        who = authorize(row, x_party_key)
        if w.status(row) not in ("awaiting_recipient", "awaiting_initiator"):
            raise HTTPException(409, "Understanding cannot be changed after acceptance")
        if not c.inspect(db, row, who)["requested"]:
            raise HTTPException(409, "Request a shared understanding check first")
        answers = {field: getattr(payload, field).strip() for field in c.FIELDS}
        previous = c.inspect(db, row, who)["ready"]
        changed = c.answer(db, row, who, answers)
        if changed:
            s.record(db, case_id, "understanding_submitted", {"party": who, "offer_revision": row["offer_revision"]})
        result = view(db, fetch(db, case_id), who)
        if result["understanding"]["ready"] and not previous:
            s.record(db, case_id, "understanding_aligned", {"offer_revision": row["offer_revision"]})
            result = view(db, fetch(db, case_id), who)
        return result


@app.post("/api/cases/{case_id}/decline")
def decline_case(case_id: str, payload: Message, x_party_key: str | None = Header(default=None)):
    with s.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row=fetch(db,case_id); who=authorize(row,x_party_key)
        if row["declined_at"] or w.status(row) not in ("awaiting_recipient", "awaiting_initiator") or who == row["offer_by"]:
            raise HTTPException(409,"Only the person reviewing the latest offer can decline it")
        db.execute("UPDATE cases SET declined_at=? WHERE id=?",(s.utcnow(),case_id))
        s.record(db,case_id,"offer_declined",{"party":who,"reason":payload.message})
        return view(db,fetch(db,case_id),who)


@app.post("/api/cases/{case_id}/counter")
def counter_case(case_id: str, payload: Counteroffer, x_party_key: str | None = Header(default=None)):
    with s.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row=fetch(db,case_id); who=authorize(row,x_party_key)
        if row["declined_at"] or w.status(row) not in ("awaiting_recipient", "awaiting_initiator") or who == row["offer_by"]:
            raise HTTPException(409,"Only the person reviewing the latest offer can suggest different terms")
        revised = w.clean_terms({"price": payload.price, "deadline": payload.deadline, "scope": payload.scope})
        changes = w.changes_between(json.loads(row["terms_json"]),revised)
        offerer_confirmed = "a_confirmed" if who == "a" else "b_confirmed"
        reviewer_confirmed = "b_confirmed" if who == "a" else "a_confirmed"
        db.execute(f"UPDATE cases SET terms_json=?, {offerer_confirmed}=1, {reviewer_confirmed}=0, offer_by=?, offer_revision=offer_revision+1, offer_note=? WHERE id=?",
                   (s.canon(revised), who, payload.note.strip(), case_id))
        s.record(db,case_id,"counteroffer_sent",{"party":who,"version":1,"changes":changes,"note":payload.note.strip(),"terms":revised})
        s.record(db,case_id,"initial_confirmed",{"party":who,"version":1})
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
        if fulfilment.has_live_plan(db,case_id):
            raise HTTPException(409, "Resolve the delivery checklist before changing terms")
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
        if fulfilment.has_live_plan(db,case_id):
            raise HTTPException(409, "Resolve the delivery checklist before changing terms")
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
        if fulfilment.has_live_plan(db,case_id):
            raise HTTPException(409, "An active delivery checklist cannot be bypassed")
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


@app.post("/api/cases/{case_id}/conversation/messages", status_code=201)
def add_conversation_message(case_id: str, payload: ConversationMessage,
                             x_party_key: str | None = Header(default=None)):
    with s.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = fetch(db, case_id)
        who = authorize(row, x_party_key)
        if row["declined_at"]:
            raise HTTPException(409, "This agreement has been declined")
        if db.execute("SELECT COUNT(*) FROM conversation_messages WHERE case_id=?", (case_id,)).fetchone()[0] >= 100:
            raise HTTPException(409, "Conversation history is full")
        text = payload.message.strip()
        if len(text) < 2:
            raise HTTPException(422, "Enter a message")
        db.execute(
            "INSERT INTO conversation_messages(id,case_id,author,body,created_at) VALUES(?,?,?,?,?)",
            (s.new_id(), case_id, who, text, s.utcnow()),
        )
        return view(db, fetch(db, case_id), who)


def conversation_error_message(error: Exception) -> str:
    status = getattr(error, "status_code", None)
    reason = getattr(error, "reason", None)
    name = type(error).__name__
    if isinstance(error, MetaResponseError):
        if reason == "output_limit":
            return "Meta could not finish this review. Try reviewing fewer messages."
        return "Meta returned an answer that could not be verified. Please try again later."
    if status in (401, 403):
        return "Meta could not authorize the review. Check the API key and billing status."
    if status == 429:
        return "Meta's request limit has been reached. Try again later."
    if name in ("APITimeoutError", "TimeoutError", "ConnectTimeout", "ReadTimeout"):
        return "Meta took too long to respond. Please try again later."
    if name in ("APIConnectionError", "ConnectError"):
        return "Unable to connect to Meta. Check your connection and try again."
    message = str(error)
    if "Daily Meta request allowance reached" in message:
        return "The daily AI review allowance has been reached. Try again tomorrow."
    if "requires Meta mode" in message or "not configured" in message:
        return "AI review is not ready. Check the Meta connection in your server."
    return "The AI review could not finish. Please try again later."


@app.post("/api/cases/{case_id}/conversation/review")
def review_conversation(case_id: str, x_party_key: str | None = Header(default=None)):
    with s.connection() as db:
        row = fetch(db, case_id)
        authorize(row, x_party_key)
        messages = conversation_view(db, case_id, row["version"], row["offer_revision"])["messages"]
        if not messages:
            raise HTTPException(409, "Add a conversation message first")
        last_id, base_version, base_revision = messages[-1]["id"], row["version"], row["offer_revision"]
        current = json.loads(row["terms_json"])
        participants = {"a": row["party_a"], "b": row["party_b"]}
    try:
        result = analyze(messages, current, participants)
    except Exception as error:
        logger.warning("Conversation analysis unavailable: %s (status %s)",
                       type(error).__name__, getattr(error, "status_code", "unknown"))
        raise HTTPException(503, conversation_error_message(error)) from error
    with s.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = fetch(db, case_id)
        who = authorize(row, x_party_key)
        current_last = db.execute(
            "SELECT id FROM conversation_messages WHERE case_id=? ORDER BY rowid DESC LIMIT 1", (case_id,)
        ).fetchone()
        if not current_last or current_last["id"] != last_id or row["version"] != base_version or row["offer_revision"] != base_revision:
            raise HTTPException(409, "Conversation or agreement changed during review. Review again.")
        db.execute(
            "INSERT INTO conversation_reviews(id,case_id,last_message_id,base_version,base_revision,result_json,created_at) VALUES(?,?,?,?,?,?,?)",
            (s.new_id(), case_id, last_id, base_version, base_revision, s.canon(result), s.utcnow()),
        )
        return view(db, fetch(db, case_id), who)


@app.post("/api/cases/{case_id}/conversation/prepare-amendment")
def prepare_conversation_amendment(case_id: str, x_party_key: str | None = Header(default=None)):

    with s.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = fetch(db, case_id)
        who = authorize(row, x_party_key)
        if w.status(row) != "in_progress":
            raise HTTPException(409, "Only active agreements can be amended")
        if db.execute("SELECT 1 FROM completion WHERE case_id=?", (case_id,)).fetchone():
            raise HTTPException(409, "Resolve the delivery review before changing terms")
        if fulfilment.has_live_plan(db,case_id):
            raise HTTPException(409, "Resolve the delivery checklist before changing terms")
        if db.execute("SELECT 1 FROM proposals WHERE case_id=? AND status='pending'", (case_id,)).fetchone():
            raise HTTPException(409, "There is already a change waiting for approval")
        saved = db.execute(
            "SELECT * FROM conversation_reviews WHERE case_id=? ORDER BY rowid DESC LIMIT 1", (case_id,)
        ).fetchone()
        latest = db.execute(
            "SELECT id, author, body FROM conversation_messages WHERE case_id=? ORDER BY rowid DESC LIMIT 1",
            (case_id,),
        ).fetchone()
        if not saved or not latest:
            raise HTTPException(409, "Review the conversation before preparing an amendment")
        review = json.loads(saved["result_json"])
        if (saved["last_message_id"] != latest["id"]
                or saved["base_version"] != row["version"]
                or saved["base_revision"] != row["offer_revision"]):
            raise HTTPException(409, "This review is outdated. Review the current conversation again")
        if review.get("last_author") != who or latest["author"] != who:
            raise HTTPException(403, "Only the person who proposed these terms can send them for approval")
        original = json.loads(row["terms_json"])
        review = recover_explicit_deadline(review, dict(latest), original)
        previous_row = db.execute(
            "SELECT id, author, body FROM conversation_messages WHERE case_id=? "
            "ORDER BY rowid DESC LIMIT 2", (case_id,)
        ).fetchall()
        previous = dict(previous_row[1]) if len(previous_row) > 1 else None
        review = recover_confirmed_price(review, previous, dict(latest), original)
        if review.get("intent") != "change_proposal" or not review.get("changes"):
            raise HTTPException(409, "The review contains no verified proposal")
        suggested = original.copy()
        seen = set()
        source_ids = {}
        for item in review["changes"]:
            field = item.get("field")
            quote = item.get("evidence", "")
            source_id = item.get("source_message_id", latest["id"])
            # Prior-message evidence is permitted only after the strict,
            # revalidated two-turn confirmation recovery above.
            from_prior = (review.get("confirmed_prior_offer") is True
                          and field == "price" and previous and source_id == previous["id"])
            source_body = previous["body"] if from_prior else latest["body"] if source_id == latest["id"] else None
            if field not in w.FIELDS or field in seen or not quote or not source_body or quote not in source_body:
                raise HTTPException(409, "The proposal evidence could not be verified")
            seen.add(field)
            source_ids[field] = source_id
            suggested[field] = item["new_value"]
        suggested = w.clean_terms(suggested)
        changes = w.changes_between(original, suggested)
        if not changes:
            raise HTTPException(409, "There are no new terms to propose")
        for change in changes:
            change["evidence"] = next(
                item["evidence"] for item in review["changes"] if item["field"] == change["field"]
            )
            change["message_id"] = source_ids[change["field"]]
        proposal_id = s.new_id()
        db.execute(
            "INSERT INTO proposals(id,case_id,base_version,author,source_text,changes_json,mode,a_approved,b_approved,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (proposal_id, case_id, row["version"], who,
             (previous["body"] + "\n" + latest["body"]) if review.get("confirmed_prior_offer") else latest["body"],
             s.canon(changes),
             "meta_conversation", int(who == "a"), int(who == "b"), s.utcnow()),
        )
        s.record(db, case_id, "change_proposed", {
            "party": who, "proposal": proposal_id, "changes": changes,
            "analysis_mode": "meta_conversation", "source_message_id": latest["id"],
            "review_id": saved["id"],
        })
        s.record(db, case_id, "proposal_approved_by_party", {"party": who, "proposal": proposal_id})
        return view(db, fetch(db, case_id), who)


@app.post("/api/cases/{case_id}/completion")
def submit_completion(case_id: str, payload: Completion, x_party_key: str | None = Header(default=None)):
    with s.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = fetch(db,case_id); who=authorize(row,x_party_key)
        if fulfilment.has_live_plan(db,case_id):
            raise HTTPException(409, "Use the itemized delivery checklist")
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
        if fulfilment.has_live_plan(db,case_id):
            raise HTTPException(409, "Use the itemized delivery checklist")
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
        if fulfilment.has_live_plan(db,case_id):
            raise HTTPException(409, "Use the itemized delivery checklist")
        delivery=db.execute("SELECT * FROM completion WHERE case_id=?",(case_id,)).fetchone()
        if who != row["responsible_party"]:
            raise HTTPException(403,"Only the person responsible for delivery can resubmit")
        if not delivery or delivery["status"]!="disputed" or delivery["version"]!=row["version"]:
            raise HTTPException(409,"There is no disputed delivery to resubmit")
        db.execute("UPDATE completion SET statement=?,reference=?,submitted_at=?,status='submitted',reviewed_by=NULL,reviewed_at=NULL,review_note=NULL WHERE case_id=?",
                   (payload.statement.strip(),payload.reference.strip() or None,s.utcnow(),case_id))
        s.record(db,case_id,"delivery_resubmitted",{"party":who,"version":row["version"],"statement":payload.statement.strip(),"reference":payload.reference.strip(),"previous_review":delivery["review_note"]})
        return view(db,fetch(db,case_id),who)


@app.post("/api/cases/{case_id}/delivery-plan", status_code=201)
def create_delivery_plan(case_id: str, payload: DeliveryPlanRequest,
                         x_party_key: str | None = Header(default=None)):
    with s.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row = fetch(db,case_id); who = authorize(row,x_party_key)
        if w.status(row) != 'in_progress':
            raise HTTPException(409, 'The agreement must be active before planning delivery')
        if db.execute('SELECT 1 FROM completion WHERE case_id=?', (case_id,)).fetchone():
            raise HTTPException(409, 'A delivery has already been reported')
        if db.execute("SELECT 1 FROM proposals WHERE case_id=? AND status='pending'", (case_id,)).fetchone():
            raise HTTPException(409, 'Resolve the proposed amendment before planning delivery')
        if fulfilment.has_live_plan(db,case_id):
            raise HTTPException(409, 'There is already a delivery checklist awaiting or holding approval')
        items = [(item.description.strip(),item.acceptance_criteria.strip()) for item in payload.items]
        if any(len(description)<5 or len(criteria)<5 for description,criteria in items):
            raise HTTPException(422, 'Describe each deliverable and how it will be accepted')
        if len({(d.casefold(), c.casefold()) for d,c in items}) != len(items):
            raise HTTPException(422, 'Remove duplicate checklist items')
        plan_id=s.new_id()
        db.execute('INSERT INTO delivery_plans(id,case_id,version,author,status,created_at) VALUES(?,?,?,?,?,?)',
                   (plan_id,case_id,row['version'],who,'pending',s.utcnow()))
        for position,(description,criteria) in enumerate(items,1):
            db.execute('INSERT INTO delivery_items(id,plan_id,position,description,acceptance_criteria) VALUES(?,?,?,?,?)',
                       (s.new_id(),plan_id,position,description,criteria))
        s.record(db,case_id,'delivery_plan_proposed',{'party':who,'plan':plan_id,'version':row['version'],
                 'items':[{'description':d,'acceptance_criteria':c} for d,c in items]})
        return view(db,fetch(db,case_id),who)


@app.post('/api/cases/{case_id}/delivery-plan/{plan_id}/respond')
def respond_delivery_plan(case_id: str, plan_id: str, payload: DeliveryPlanResponse,
                          x_party_key: str | None = Header(default=None)):
    with s.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row=fetch(db,case_id); who=authorize(row,x_party_key)
        plan=db.execute('SELECT * FROM delivery_plans WHERE case_id=? AND id=?',(case_id,plan_id)).fetchone()
        if not plan:raise HTTPException(404,'Delivery checklist not found')
        if plan['status']!='pending':raise HTTPException(409,'This checklist has already been reviewed')
        if plan['author']==who:raise HTTPException(403,'Only the other participant can approve the checklist')
        if plan['version']!=row['version'] or w.status(row)!='in_progress':
            raise HTTPException(409,'The agreement changed; a new checklist is needed')
        if not payload.accepted and len(payload.note.strip())<5:
            raise HTTPException(422,'Explain what should change in the checklist')
        decision='active' if payload.accepted else 'rejected'
        db.execute('UPDATE delivery_plans SET status=?, reviewer=?, reviewed_at=?,review_note=? WHERE id=?',
                   (decision,who,s.utcnow(),payload.note.strip(),plan_id))
        s.record(db,case_id,'delivery_plan_approved' if payload.accepted else 'delivery_plan_rejected',
                 {'party':who,'plan':plan_id,'note':payload.note.strip(),'version':row['version']})
        return view(db,fetch(db,case_id),who)


@app.post('/api/cases/{case_id}/delivery-items/{item_id}/submit')
def submit_delivery_item(case_id: str, item_id: str, payload: EvidenceSubmission,
                         x_party_key: str | None = Header(default=None)):
    try:
        prepared = evidence.prepare_images([image.model_dump() for image in payload.screenshots])
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    with s.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row=fetch(db,case_id); who=authorize(row,x_party_key)
        if who!=row['responsible_party']:
            raise HTTPException(403,'Only the responsible participant may submit work')
        plan=fulfilment.get_plan(db,case_id)
        if not plan or plan['status']!='active' or plan['version']!=row['version']:
            raise HTTPException(409,'An approved, current delivery checklist is required')
        item=next((item for item in plan['items'] if item['id']==item_id),None)
        if not item:raise HTTPException(404,'Deliverable not found')
        if item['status'] not in ('pending','disputed'):
            raise HTTPException(409,'This deliverable is not open for submission')
        statement=payload.statement.strip()
        if len(statement)<8:
            raise HTTPException(422,'Describe the completed work')
        reference=payload.reference.strip()
        submission_id=s.new_id()
        saved=evidence.save_images(db,case_id,item_id,submission_id,prepared)
        db.execute('UPDATE delivery_items SET status=?,statement=?,reference=?,submission_id=?,submitted_at=?,reviewed_at=NULL,reviewer=NULL,review_note=NULL WHERE id=?',
                   ('submitted',statement,reference or None,submission_id,s.utcnow(),item_id))
        s.record(db,case_id,'deliverable_resubmitted' if item['status']=='disputed' else 'deliverable_submitted',
                 {'party':who,'item':item_id,'description':item['description'],'statement':statement,
                  'reference':reference,'screenshot_evidence':saved,'previous_review':item['review_note']})
        return view(db,fetch(db,case_id),who)


@app.get('/api/cases/{case_id}/evidence/{evidence_id}')
def download_evidence(case_id: str, evidence_id: str, x_party_key: str | None = Header(default=None)):
    with s.connection() as db:
        row=fetch(db,case_id); authorize(row,x_party_key)
        record=db.execute('SELECT filename FROM evidence_files WHERE case_id=? AND id=?',
                          (case_id,evidence_id)).fetchone()
        if not record: raise HTTPException(404,'Evidence not found')
        image_path=evidence.private_dir()/record['filename']
        if not image_path.is_file(): raise HTTPException(404,'Evidence file missing')
    return FileResponse(image_path,media_type='image/jpeg',headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})


@app.post('/api/cases/{case_id}/delivery-items/{item_id}/check-evidence')
def check_visual_evidence(case_id: str, item_id: str, x_party_key: str | None = Header(default=None)):
    with s.connection() as db:
        row=fetch(db,case_id); who=authorize(row,x_party_key)
        if who==row['responsible_party']:
            raise HTTPException(403,'Only the reviewing participant may check evidence')
        plan=fulfilment.get_plan(db,case_id)
        if not plan or plan['status']!='active' or plan['version']!=row['version']:
            raise HTTPException(409,'A current delivery checklist is required')
        item=next((item for item in plan['items'] if item['id']==item_id),None)
        if not item or item['status']!='submitted':
            raise HTTPException(409,'No submitted evidence awaiting review')
        submission_id=item.get('submission_id')
        files=evidence.images_for(db,item_id,submission_id)
        if not files: raise HTTPException(409,'No screenshot attached to this submission')
        cached=db.execute('SELECT result_json FROM evidence_reviews WHERE item_id=? AND submission_id=? ORDER BY rowid DESC LIMIT 1',
                          (item_id,submission_id)).fetchone()
        if cached: return view(db,row,who)
        payload=(item['statement'],item['acceptance_criteria'],item['reference'] or '',files)
    images=[]
    try:
        for record in payload[3]:
            stored=evidence.private_dir()/(record['id']+'.jpg')
            images.append((record['name'],stored.read_bytes()))
        report=evidence.review_with_meta(images,*payload[:3])
    except Exception as exc:
        logger.warning('Visual evidence review unavailable: %s',type(exc).__name__)
        raise HTTPException(503,conversation_error_message(exc)) from exc
    with s.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row=fetch(db,case_id); who=authorize(row,x_party_key)
        item=db.execute('SELECT * FROM delivery_items WHERE id=?',(item_id,)).fetchone()
        if not item or item['submission_id']!=submission_id or item['status']!='submitted':
            raise HTTPException(409,'Evidence changed during review')
        cached=db.execute('SELECT 1 FROM evidence_reviews WHERE item_id=? AND submission_id=?',(item_id,submission_id)).fetchone()
        if not cached:
            db.execute('INSERT INTO evidence_reviews(id,case_id,item_id,submission_id,result_json,created_at) VALUES(?,?,?,?,?,?)',
                       (s.new_id(),case_id,item_id,submission_id,s.canon(report),s.utcnow()))
            s.record(db,case_id,'evidence_ai_reviewed',{'item':item_id,'submission':submission_id,'mode':report['mode']})
        return view(db,row,who)


@app.post('/api/cases/{case_id}/delivery-items/{item_id}/review')
def review_delivery_item(case_id: str, item_id: str, payload: DeliveryItemDecision,
                         x_party_key: str | None = Header(default=None)):
    with s.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row=fetch(db,case_id); who=authorize(row,x_party_key)
        if who==row['responsible_party']:
            raise HTTPException(403,'Only the other participant can review the work')
        plan=fulfilment.get_plan(db,case_id)
        if not plan or plan['status']!='active' or plan['version']!=row['version']:
            raise HTTPException(409,'No active delivery checklist can be reviewed')
        item=next((item for item in plan['items'] if item['id']==item_id),None)
        if not item:raise HTTPException(404,'Deliverable not found')
        if item['status']!='submitted':
            raise HTTPException(409,'This deliverable is not awaiting review')
        if not payload.accepted and len(payload.note.strip())<5:
            raise HTTPException(422,'Explain what is missing or incorrect')
        outcome='accepted' if payload.accepted else 'disputed'
        db.execute('UPDATE delivery_items SET status=?, reviewer=?,reviewed_at=?,review_note=? WHERE id=?',
                   (outcome,who,s.utcnow(),payload.note.strip(),item_id))
        s.record(db,case_id,'deliverable_accepted' if payload.accepted else 'deliverable_disputed',
                 {'party':who,'item':item_id,'description':item['description'],'note':payload.note.strip(),
                  'statement':item['statement'],'reference':item['reference']})
        plan=fulfilment.get_plan(db,case_id)
        if fulfilment.plan_status(plan)=='completed':
            s.record(db,case_id,'delivery_completed',{'version':row['version'],'plan':plan['id'],
                         'items':[item['id'] for item in plan['items']]})
        return view(db,fetch(db,case_id),who)
