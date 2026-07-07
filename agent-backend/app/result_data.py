"""Load structured result data from a job workspace so /result can hand the app
native-renderable series + worksheet (instead of the baked summary_panel.png / PDFs).

Pure stdlib parsing — cheap, no pandas dependency at request time.
"""
import csv
import json
import os
from pathlib import Path

# Cap the series we ship so the /result payload stays reasonable on long clips.
MAX_POINTS = 2000


def _ws(job_id: str) -> Path:
    base = Path(os.environ.get("WORKSPACE_DIR", "./workspaces"))
    return base / f"job_{job_id}" / "analysis_output" / "data"


def _f(v):
    try:
        x = float(v)
        return x if x == x else 0.0  # NaN → 0.0 for JSON safety
    except (TypeError, ValueError):
        return 0.0


def load_series(job_id: str) -> dict | None:
    path = _ws(job_id) / "kinematics.csv"
    if not path.exists():
        return None
    cols = {k: [] for k in
            ("t_s", "omega_rad_s", "ac_m_s2", "v_m_s", "r_m", "theta_rad", "active")}
    try:
        with open(path, newline="") as fh:
            rows = list(csv.DictReader(fh))
    except Exception:
        return None
    if not rows:
        return None

    step = max(1, len(rows) // MAX_POINTS)
    for row in rows[::step]:
        cols["t_s"].append(_f(row.get("time_s")))
        cols["omega_rad_s"].append(_f(row.get("omega_rad_s")))
        cols["ac_m_s2"].append(_f(row.get("ac_m_s2")))
        cols["v_m_s"].append(_f(row.get("v_m_s")))
        cols["r_m"].append(_f(row.get("r_m")))
        cols["theta_rad"].append(_f(row.get("theta_rad")))
        cols["active"].append(int(_f(row.get("active"))))
    return cols


_TIERS = ("basic", "intermediate", "advanced")


def load_materials(job_id: str) -> dict | None:
    """The difficulty-tiered learning material as native JSON (mirrors load_worksheet), so
    the app can render it in-place instead of only offering the PDF. Returns
    {tier: {object_name, scene_title, difficulty_level, bloom_objective, sections, ...}} for
    every material.<tier>.json present, or None for legacy/untiered jobs."""
    data = _ws(job_id)
    out = {}
    for t in _TIERS:
        p = data / f"material.{t}.json"
        if not p.exists():
            continue
        try:
            m = json.loads(p.read_text(errors="replace"))
        except Exception:
            continue
        if not isinstance(m, dict):
            continue
        secs = m.get("sections")
        out[t] = {
            "object_name": m.get("object_name"),
            "scene_title": m.get("scene_title"),
            "difficulty_level": m.get("difficulty_level") or m.get("tier") or t,
            "bloom_objective": m.get("bloom_objective"),
            "element_interactivity": m.get("element_interactivity"),
            "concepts_introduced": m.get("concepts_introduced") or [],
            "sections": secs if isinstance(secs, dict) else {},
        }
    return out or None


def load_material_gate(job_id: str) -> dict | None:
    """The grounding-gate verdict (material_tiers_gate.json), if present."""
    p = _ws(job_id) / "material_tiers_gate.json"
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text(errors="replace"))
        return d if isinstance(d, dict) else None
    except Exception:
        return None


def load_worksheet(job_id: str) -> dict | None:
    path = _ws(job_id) / "questions.json"
    if not path.exists():
        return None
    try:
        d = json.loads(path.read_text(errors="replace"))
    except Exception:
        return None
    if not isinstance(d, dict):
        return None
    qs = d.get("questions")
    return {
        "object_name": d.get("object_name"),
        "scenario": d.get("scenario"),
        "questions": qs if isinstance(qs, list) else [],
    }
