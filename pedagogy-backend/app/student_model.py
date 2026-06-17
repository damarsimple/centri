"""Student model: profile (ability band) + misconception history.

Ported from fastapi-gpt's inquiry_db.py; on sqlite via app.db. Modality-independent —
works the same whether physics came from sensor or video.
"""
from . import db

_SCHEMA = """
CREATE TABLE IF NOT EXISTS student_profile (
    user_id TEXT PRIMARY KEY,
    grade_level TEXT,
    iq_rank_order TEXT,
    ability_band TEXT DEFAULT 'neutral',
    questions_answered INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS misconception_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    misconception_id TEXT NOT NULL,
    response_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_miscon_user ON misconception_history(user_id);
"""
db.register_schema(_SCHEMA)


def compute_ability_band(iq_rank_order):
    """Map 'A/Total' rank to high/medium/low (smaller rank = better). r=A/Total:
    r<=0.33 high, <=0.67 medium, else low. 'neutral' if missing/invalid."""
    if not iq_rank_order or "/" not in str(iq_rank_order):
        return "neutral"
    try:
        a_str, total_str = str(iq_rank_order).split("/")
        a, total = int(a_str.strip()), int(total_str.strip())
    except (ValueError, AttributeError):
        return "neutral"
    if total <= 0 or a < 1 or a > total:
        return "neutral"
    r = a / total
    if r <= 0.33:
        return "high"
    if r <= 0.67:
        return "medium"
    return "low"


def get_profile(user_id):
    with db.session() as conn:
        row = conn.execute(
            "SELECT * FROM student_profile WHERE user_id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else None


def ability_band(user_id):
    return (get_profile(user_id) or {}).get("ability_band", "neutral")


def upsert_profile(user_id, grade_level=None, iq_rank_order=None, ability_band=None):
    band = ability_band or (compute_ability_band(iq_rank_order) if iq_rank_order else None)
    with db.lock, db.session() as conn:
        exists = conn.execute(
            "SELECT 1 FROM student_profile WHERE user_id = ?", (user_id,)
        ).fetchone()
        if exists is None:
            conn.execute(
                "INSERT INTO student_profile (user_id, grade_level, iq_rank_order, ability_band) "
                "VALUES (?, ?, ?, ?)",
                (user_id, grade_level, iq_rank_order, band or "neutral"),
            )
        else:
            sets, params = [], []
            for col, val in (("grade_level", grade_level),
                             ("iq_rank_order", iq_rank_order),
                             ("ability_band", band)):
                if val is not None:
                    sets.append(f"{col} = ?")
                    params.append(val)
            if sets:
                params.append(user_id)
                conn.execute(
                    f"UPDATE student_profile SET {', '.join(sets)}, "
                    "updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                    params,
                )


def increment_questions_answered(user_id):
    with db.lock, db.session() as conn:
        conn.execute(
            "INSERT INTO student_profile (user_id, questions_answered) VALUES (?, 1) "
            "ON CONFLICT(user_id) DO UPDATE SET questions_answered = questions_answered + 1, "
            "updated_at = CURRENT_TIMESTAMP",
            (user_id,),
        )


def add_misconception(user_id, misconception_id, response_id=None):
    with db.lock, db.session() as conn:
        conn.execute(
            "INSERT INTO misconception_history (user_id, misconception_id, response_id) "
            "VALUES (?, ?, ?)",
            (user_id, misconception_id, response_id),
        )


def get_misconceptions(user_id):
    with db.session() as conn:
        rows = conn.execute(
            "SELECT misconception_id FROM misconception_history WHERE user_id = ? "
            "ORDER BY created_at ASC",
            (user_id,),
        ).fetchall()
        return [r["misconception_id"] for r in rows]
