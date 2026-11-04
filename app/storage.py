"""SQLite prototype persistence and audit hashes (not a legal or tamper-proof ledger)."""
from __future__ import annotations
import hashlib
import json
import os
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

BASE = Path(__file__).resolve().parents[1]
DB = Path(os.environ.get("SAMEPAGE_DB", str(BASE / "data" / "samepage.sqlite3")))


def canon(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB, timeout=10)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        with conn:
            yield conn
    finally:
        conn.close()


def initialize():
    with connection() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS cases (
            id TEXT PRIMARY KEY, title TEXT NOT NULL,
            party_a TEXT NOT NULL, party_b TEXT NOT NULL,
            hash_a TEXT NOT NULL, hash_b TEXT NOT NULL,
            terms_json TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1,
            a_confirmed INTEGER NOT NULL DEFAULT 0,
            b_confirmed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS proposals (
            id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id),
            base_version INTEGER NOT NULL, author TEXT NOT NULL,
            source_text TEXT NOT NULL, changes_json TEXT NOT NULL,
            mode TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
            a_approved INTEGER NOT NULL DEFAULT 0,
            b_approved INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id TEXT NOT NULL REFERENCES cases(id),
            event TEXT NOT NULL, payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL, prev_hash TEXT NOT NULL, hash TEXT NOT NULL
        );
        """)
        columns = {row['name'] for row in db.execute('PRAGMA table_info(cases)')}
        if 'responsible_party' not in columns:
            db.execute("ALTER TABLE cases ADD COLUMN responsible_party TEXT NOT NULL DEFAULT 'b'")
        if 'declined_at' not in columns:
            db.execute('ALTER TABLE cases ADD COLUMN declined_at TEXT')
        if 'offer_by' not in columns:
            db.execute("ALTER TABLE cases ADD COLUMN offer_by TEXT NOT NULL DEFAULT 'a'")
            db.execute("UPDATE cases SET offer_by='b' WHERE a_confirmed=0 AND b_confirmed=1")
        if 'offer_revision' not in columns:
            db.execute('ALTER TABLE cases ADD COLUMN offer_revision INTEGER NOT NULL DEFAULT 0')
            db.execute('''UPDATE cases SET offer_revision=(
                SELECT COUNT(*) FROM audit WHERE case_id=cases.id AND event='counteroffer_sent'
            )''')
        if 'offer_note' not in columns:
            db.execute("ALTER TABLE cases ADD COLUMN offer_note TEXT NOT NULL DEFAULT ''")
        db.execute("""
            CREATE TABLE IF NOT EXISTS clarity_checks (
                case_id TEXT NOT NULL REFERENCES cases(id),
                revision INTEGER NOT NULL,
                requested_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (case_id, revision)
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS clarity_answers (
                case_id TEXT NOT NULL REFERENCES cases(id),
                revision INTEGER NOT NULL,
                party TEXT NOT NULL CHECK(party IN ('a','b')),
                answers_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (case_id,revision,party)
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS conversation_messages (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL REFERENCES cases(id),
                author TEXT NOT NULL CHECK(author IN ('a','b')),
                body TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS conversation_reviews (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL REFERENCES cases(id),
                last_message_id TEXT NOT NULL REFERENCES conversation_messages(id),
                base_version INTEGER NOT NULL,
                base_revision INTEGER NOT NULL DEFAULT 0,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS completion (
                case_id TEXT PRIMARY KEY REFERENCES cases(id),
                version INTEGER NOT NULL,
                submitted_by TEXT NOT NULL,
                submitted_at TEXT NOT NULL,
                statement TEXT NOT NULL,
                reference TEXT,
                status TEXT NOT NULL DEFAULT 'submitted',
                reviewed_by TEXT,
                reviewed_at TEXT,
                review_note TEXT
            )
        """)
        from . import fulfilment
        fulfilment.initialize(db)
        from . import evidence
        evidence.initialize(db)


def new_id() -> str:
    return uuid.uuid4().hex[:16]


def new_token() -> str:
    return secrets.token_urlsafe(32)


def digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf8")).hexdigest()


def record(db, case_id: str, event: str, data: dict):
    last = db.execute("SELECT hash FROM audit WHERE case_id=? ORDER BY id DESC LIMIT 1", (case_id,)).fetchone()
    prev = last["hash"] if last else "GENESIS"
    now = utcnow()
    payload = canon(data)
    value = hashlib.sha256((prev + "|" + event + "|" + payload + "|" + now).encode()).hexdigest()
    db.execute("INSERT INTO audit(case_id,event,payload_json,created_at,prev_hash,hash) VALUES(?,?,?,?,?,?)",
               (case_id,event,payload,now,prev,value))


def verify_chain(rows: list[sqlite3.Row]) -> bool:
    prev = "GENESIS"
    for r in rows:
        content = (prev + "|" + r["event"] + "|" + r["payload_json"] + "|" + r["created_at"]).encode()
        if r["prev_hash"] != prev or hashlib.sha256(content).hexdigest() != r["hash"]:
            return False
        prev = r["hash"]
    return True
