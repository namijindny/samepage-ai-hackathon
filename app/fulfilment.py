"""Mutually approved delivery checklist with participant-controlled evidence decisions."""
from __future__ import annotations

import json
from . import storage as store


def initialize(db):
    db.execute('''CREATE TABLE IF NOT EXISTS delivery_plans (
        id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id),
        version INTEGER NOT NULL, author TEXT NOT NULL CHECK(author IN ('a','b')),
        status TEXT NOT NULL CHECK(status IN ('pending','active','rejected')),
        created_at TEXT NOT NULL, reviewed_at TEXT, reviewer TEXT, review_note TEXT
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS delivery_items (
        id TEXT PRIMARY KEY, plan_id TEXT NOT NULL REFERENCES delivery_plans(id),
        position INTEGER NOT NULL, description TEXT NOT NULL,
        acceptance_criteria TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending'
            CHECK(status IN ('pending','submitted','disputed','accepted')),
        statement TEXT, reference TEXT, submitted_at TEXT,
        reviewed_at TEXT, reviewer TEXT, review_note TEXT,
        UNIQUE(plan_id,position)
    )''')


def get_plan(db, case_id):
    plan = db.execute(
        'SELECT * FROM delivery_plans WHERE case_id=? ORDER BY rowid DESC LIMIT 1',
        (case_id,)
    ).fetchone()
    if not plan:
        return None
    result = dict(plan)
    result['items'] = [dict(row) for row in db.execute(
        'SELECT * FROM delivery_items WHERE plan_id=? ORDER BY position', (plan['id'],)
    )]
    from . import evidence
    for item in result['items']:
        item['screenshots'] = evidence.images_for(db,item['id'],item.get('submission_id'))
        item['earlier_screenshots'] = evidence.past_images(db,item['id'],item.get('submission_id'))
        latest = db.execute('SELECT result_json FROM evidence_reviews WHERE item_id=? AND submission_id=? ORDER BY rowid DESC LIMIT 1',
                            (item['id'],item.get('submission_id'))).fetchone() if item.get('submission_id') else None
        item['evidence_insight'] = json.loads(latest['result_json']) if latest else None
    if plan['status'] == 'active':
        result['accepted_count'] = sum(item['status']=='accepted' for item in result['items'])
        result['total_count'] = len(result['items'])
    return result


def plan_status(plan):
    if not plan or plan['status'] != 'active':
        return None
    states = [item['status'] for item in plan['items']]
    if states and all(state == 'accepted' for state in states):
        return 'completed'
    if any(state == 'submitted' for state in states):
        return 'awaiting_completion_review'
    if any(state == 'disputed' for state in states):
        return 'disputed'
    return 'in_progress'


def has_live_plan(db, case_id):
    return db.execute(
        "SELECT 1 FROM delivery_plans WHERE case_id=? AND status IN ('pending','active') LIMIT 1",
        (case_id,)
    ).fetchone() is not None


def all_deliveries(db, case_id):
    return [dict(r) for r in db.execute(
        "SELECT id,status,version,author,created_at,reviewed_at FROM delivery_plans WHERE case_id=? ORDER BY rowid",
        (case_id,)
    )]
