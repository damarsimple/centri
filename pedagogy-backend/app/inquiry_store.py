"""Persistence for generated inquiries and student responses — the tutor's session log.

Makes the tutor stateful: submit-response can look up the inquiry by id, and every
turn is recorded for history/analytics.
"""
import json

from . import db

_SCHEMA = """
CREATE TABLE IF NOT EXISTS inquiry (
    inquiry_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    stage TEXT,
    inquiry TEXT,
    difficulty TEXT,
    object_label TEXT,
    measurement_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_inquiry_user ON inquiry(user_id);
CREATE TABLE IF NOT EXISTS response (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inquiry_id TEXT,
    user_id TEXT NOT NULL,
    user_answer TEXT,
    is_correct INTEGER,
    feedback TEXT,
    next_step TEXT,
    misconception_id TEXT,
    concept_coverage TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_response_user ON response(user_id);
"""
db.register_schema(_SCHEMA)


def _ser_measurement(m):
    if m is None:
        return None
    if hasattr(m, "model_dump"):       # pydantic v2
        return json.dumps(m.model_dump())
    if hasattr(m, "dict"):             # pydantic v1
        return json.dumps(m.dict())
    return json.dumps(m)


def save_inquiry(inquiry_id, user_id, stage, inquiry, difficulty,
                 object_label=None, measurement=None):
    with db.lock, db.session() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO inquiry "
            "(inquiry_id, user_id, stage, inquiry, difficulty, object_label, measurement_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (inquiry_id, user_id, stage, inquiry, difficulty, object_label,
             _ser_measurement(measurement)),
        )


def get_inquiry(inquiry_id):
    with db.session() as conn:
        row = conn.execute(
            "SELECT * FROM inquiry WHERE inquiry_id = ?", (inquiry_id,)
        ).fetchone()
        return dict(row) if row else None


def save_response(inquiry_id, user_id, user_answer, is_correct, feedback, next_step,
                  misconception_id=None, concept_coverage=None):
    cov = json.dumps(concept_coverage) if concept_coverage else None
    with db.lock, db.session() as conn:
        conn.execute(
            "INSERT INTO response "
            "(inquiry_id, user_id, user_answer, is_correct, feedback, next_step, "
            " misconception_id, concept_coverage) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (inquiry_id, user_id, user_answer, int(bool(is_correct)), feedback, next_step,
             misconception_id, cov),
        )


def session_history(user_id, limit=50):
    with db.session() as conn:
        inq = conn.execute(
            "SELECT inquiry_id, stage, inquiry, difficulty, created_at FROM inquiry "
            "WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        resp = conn.execute(
            "SELECT inquiry_id, user_answer, is_correct, feedback, misconception_id, created_at "
            "FROM response WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return {"inquiries": [dict(r) for r in inq], "responses": [dict(r) for r in resp]}
