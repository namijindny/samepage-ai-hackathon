from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from . import storage


def reserve_request() -> None:
    limit = int(os.environ.get("MAX_META_CALLS_PER_DAY", "20"))
    if limit < 1 or limit > 200:
        raise RuntimeError("MAX_META_CALLS_PER_DAY must be between 1 and 200")
    day = datetime.now(timezone.utc).date().isoformat()
    with storage.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("CREATE TABLE IF NOT EXISTS model_usage (day TEXT PRIMARY KEY, attempts INTEGER NOT NULL)")
        count = db.execute("SELECT attempts FROM model_usage WHERE day=?", (day,)).fetchone()
        if count and count["attempts"] >= limit:
            raise RuntimeError("Daily Meta request allowance reached. No API call was made.")
        db.execute("INSERT INTO model_usage(day, attempts) VALUES(?,1) ON CONFLICT(day) DO UPDATE SET attempts=attempts+1", (day,))
