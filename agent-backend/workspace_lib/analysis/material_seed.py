"""Deterministic seed for Module D (learning material).

This is the DETERMINISTIC half of material generation: it reads the frozen
`stats.json` + `kinematics.csv` and emits `material_seed.json` — the ground-truth
facts (variables, formula relations, the angular-acceleration block, and a
time-anchored omega(t) timeline) that Subagent D turns into authentic prose
WITHOUT inventing numbers. Same-inputs -> identical seed, like the rest of
`analysis/`. The LLM step lives in Subagent D, not here.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

from . import quality_signals
from .common import dedup_display_name

DATA = Path("analysis_output/data")
N_TIMELINE = 4  # time-anchored samples across the active window

# Canonical figure names Subagent B produces (referenced in the prose).
FIGURES = {
    "image": "plots/annotated_image.png",
    "graph": "plots/annotated_graph.png",
    "table": "plots/annotated_table.png",
    "summary": "plots/summary_panel.png",
}


def _timeline_from_csv(csv_path: Path, n: int = N_TIMELINE):
    """Sample the pipeline's own per-frame kinematics over the ACTIVE window.

    Uses kinematics.csv's omega/v/a_c directly so the time-anchored narration
    matches every other number in the material.
    """
    rows = []
    with open(csv_path, newline="") as fh:
        for r in csv.DictReader(fh):
            if r.get("active") not in ("1", "1.0", "True", "true"):
                continue
            try:
                rows.append({
                    "t_s": float(r["time_s"]),
                    "omega_rad_s": abs(float(r["omega_rad_s"])),
                    "v_m_s": abs(float(r["v_m_s"])),
                    "a_c_m_s2": float(r["ac_m_s2"]),
                })
            except (ValueError, KeyError):
                continue
    if len(rows) < 5:
        return []
    t0, t1 = rows[0]["t_s"], rows[-1]["t_s"]
    out = []
    for k in range(n):
        ts = t0 + (t1 - t0) * (k / (n - 1)) if n > 1 else t0
        r = min(rows, key=lambda x: abs(x["t_s"] - ts))
        out.append({
            "t_s": round(r["t_s"], 2),
            "omega_rad_s": round(r["omega_rad_s"], 3),
            "v_m_s": round(r["v_m_s"], 2),
            "a_c_m_s2": round(r["a_c_m_s2"], 2),
        })
    return out


def _absval(x):
    """abs() of a real number, else the value unchanged (None/str pass through)."""
    return abs(x) if isinstance(x, (int, float)) else x


_TURN_LABEL = {90: "a quarter turn", 180: "half a turn",
               270: "three-quarters of a turn", 360: "a full turn"}


def angle_milestones(csv_path: Path, unreliable: bool = False):
    """Time of the first crossing of 90/180/270/360 degrees of swept angle — the
    ground truth behind the basic tier's "one second in ≈ a quarter turn, ~90°" figure.

    theta_rad in kinematics.csv is already unwrapped/cumulative; we rebase it (and time)
    to the first ACTIVE sample and report the magnitude of the swept angle so the sign of
    the rotation direction doesn't matter. ``unreliable`` (oblique capture): the
    quarter-turn positions are projection-distorted, so only the 180°/360° milestones —
    where the object is diametrically opposite / back at start, robust to viewing angle —
    are kept. ≤5 entries. Empty if the clip never completes a quarter turn or the CSV is
    too short.
    """
    rows = []
    try:
        with open(csv_path, newline="") as fh:
            for r in csv.DictReader(fh):
                if r.get("active") not in ("1", "1.0", "True", "true"):
                    continue
                try:
                    rows.append((float(r["time_s"]), float(r["theta_rad"])))
                except (ValueError, KeyError):
                    continue
    except OSError:
        return []
    if len(rows) < 5:
        return []
    t0, th0 = rows[0]
    targets = [180, 360] if unreliable else [90, 180, 270, 360]
    out = []
    for deg in targets:
        for t, th in rows:
            if abs(math.degrees(th - th0)) >= deg:
                out.append({"t_s": round(t - t0, 2), "angle_deg": deg,
                            "turn": _TURN_LABEL[deg]})
                break
    return out[:5]


def _narrative_context() -> dict:
    """Read the optional user-typed scene context from the workspace sidecar (cwd =
    workspace). ``scene_context`` (app free-text) is authoritative; a VLM ``notes`` hint
    is advisory. Absent/unreadable → an empty 'none' block so the tiers fall back to a
    generic second-person framing with no invented proper nouns. Never raises."""
    user_text = vlm_hint = None
    try:
        sc = json.loads(Path("sidecar.json").read_text())
        if isinstance(sc, dict):
            ut = sc.get("scene_context")
            user_text = ut.strip() if isinstance(ut, str) and ut.strip() else None
            sug = sc.get("scene_suggestion")
            note = sc.get("scene_notes")
            if not note and isinstance(sug, dict):
                note = sug.get("notes")
            vlm_hint = note.strip() if isinstance(note, str) and note.strip() else None
    except (OSError, ValueError):
        pass
    source = "user" if user_text else ("vlm" if vlm_hint else "none")
    return {"user_text": user_text, "vlm_hint": vlm_hint, "source": source}


def build_seed(stats: dict, csv_path: Path | None = None) -> dict:
    calib = stats.get("calibration", {})
    summ = stats.get("summary", {})
    pf = stats.get("period_and_frequency", {})
    aa = stats.get("angular_acceleration", {})

    # The radius v and a_c are BUILT from is the fitted orbit radius (r_fit_m), not the
    # mean of per-frame point distances (mean_r_m) — they differ a few % on a noisy orbit.
    # Report r_fit_m so v = omega*r and a_c = omega^2*r close exactly at every instant.
    r_fit = calib.get("r_fit_m")
    r_report = r_fit if r_fit is not None else summ.get("mean_r_m")

    variables = [
        {"symbol": "r", "name": "radius", "value": r_report, "unit": "m",
         "definition": "fitted radius of the orbit (the radius used to compute v and a_c)"},
        # Store the UNSIGNED magnitude — direction lives in rotation_direction. The signed
        # mean (e.g. -2.12) otherwise contradicted the table's magnitude (2.08) in the prose.
        {"symbol": "omega", "name": "angular velocity", "value": _absval(summ.get("mean_omega")),
         "unit": "rad/s",
         "definition": "how fast the angle is swept per second (rate of change of angle)"},
        {"symbol": "v", "name": "tangential speed", "value": _absval(summ.get("mean_v")), "unit": "m/s",
         "definition": "linear speed along the circular path"},
        {"symbol": "a_c", "name": "centripetal acceleration", "value": summ.get("mean_ac"),
         "unit": "m/s^2",
         "definition": "inward acceleration that keeps the object on its circle"},
        {"symbol": "T", "name": "period", "value": pf.get("period_s"), "unit": "s",
         "definition": "time for one full revolution"},
        {"symbol": "f", "name": "frequency", "value": pf.get("frequency_hz"), "unit": "Hz",
         "definition": "revolutions per second"},
    ]

    relations = [
        {"name": "angular velocity", "formula": "omega = d(theta)/dt",
         "plain": "angular velocity is how quickly the swept angle changes with time"},
        {"name": "tangential speed", "formula": "v = omega * r",
         "plain": "the farther out (larger r) or faster the spin (larger omega), the faster it moves"},
        {"name": "centripetal acceleration", "formula": "a_c = v^2 / r = omega^2 * r",
         "plain": "the inward acceleration grows with the square of the speed (or angular velocity)"},
        {"name": "period", "formula": "T = 2*pi / omega = 1 / f",
         "plain": "one full turn takes 2*pi radians divided by the angular velocity"},
    ]

    aa_out = None
    if aa and aa.get("motion_type"):
        mt = aa["motion_type"]
        aa_out = {
            "motion_type": mt,
            "alpha_rad_s2": aa.get("alpha_rad_s2"),
            "alpha_r2": aa.get("alpha_r2"),
            "omega_initial": aa.get("omega_initial"),
            "omega_final": aa.get("omega_final"),
            "a_t_mean_m_s2": aa.get("a_t_mean_m_s2"),
            "relation": "alpha = d(omega)/dt ; a_t = alpha * r",
            "plain": {
                "accelerating": "the object is speeding up at a steady angular acceleration alpha",
                "decelerating": "the object is slowing down (coasting) at a steady angular deceleration",
                "uniform": "the object turns at a constant rate (no angular acceleration)",
            }.get(mt, ""),
        }

    timeline = []
    measurement_quality = None
    milestones = []
    if csv_path and Path(csv_path).exists():
        timeline = _timeline_from_csv(Path(csv_path))
        # Trust channel for the LLM: is per-instant omega reliable, or is the omega(t)
        # ripple a viewing-angle (oblique-capture) projection artifact? Drives the
        # hedging policy in material_tiers.py so the prose can't launder an artifact.
        try:
            sig = quality_signals.compute(Path(csv_path), stats)
            measurement_quality = quality_signals.build_quality_block(sig, stats)
        except Exception:
            measurement_quality = None
        unreliable = bool(measurement_quality) and not measurement_quality.get("reliable", True)
        milestones = angle_milestones(Path(csv_path), unreliable=unreliable)

    # Clean display names once, here, so every downstream consumer (tiers, figures,
    # report) sees the same deduped strings. When the scene title collapses to nothing
    # (it was the degenerate "<X> on <X>"), fall back to the plain object name.
    object_name = dedup_display_name(stats.get("object_name"))
    scene_title = dedup_display_name(stats.get("scene_title")) or object_name

    return {
        "object_name": object_name,
        "scene_title": scene_title,
        "tracked_label": stats.get("tracked_label"),
        "rotation_direction": summ.get("rotation_direction"),
        "active_duration_s": (stats.get("video_info", {}) or {}).get("duration_s"),
        "variables": variables,
        "relations": relations,
        "angular_acceleration": aa_out,
        "timeline": timeline,
        "angle_milestones": milestones,
        "narrative_context": _narrative_context(),
        "figures": FIGURES,
        "calibration_note": {
            "px_per_m": calib.get("px_per_m"),
            "reference_physical_size_m": calib.get("physical_size_m"),
            "reference_source": calib.get("physical_size_source"),
            "caveat": "absolute SI scale depends on the reference size; relative kinematics "
                      "(omega, alpha, period, ratios) are scale-free and robust",
        },
        "measured_radius_m": summ.get("mean_r_m"),
        "consistency_note": {
            "radius_used": "r is the fitted orbit radius r_fit_m; v and a_c are computed "
                           "from it, so v = omega*r and a_c = omega^2*r close exactly at any "
                           "single instant (see timeline).",
            "means_are_time_averages": (
                "the summary r, omega, v, a_c are time-AVERAGES over the clip. For "
                "non-uniform motion DO NOT verify a_c = omega^2*r by plugging the mean "
                "omega: mean(a_c) = mean(omega^2)*r is strictly greater than "
                "(mean omega)^2*r (Jensen). To show a relation numerically, use a single "
                "timeline instant, where every identity closes exactly."),
        },
        "validation_flags": stats.get("validation_flags", []),
        "measurement_quality": measurement_quality,
    }


def write_material_seed(stats: dict | None = None) -> dict:
    if stats is None:
        stats = json.loads((DATA / "stats.json").read_text())
    seed = build_seed(stats, DATA / "kinematics.csv")
    (DATA / "material_seed.json").write_text(json.dumps(seed, indent=2))
    return seed


def main() -> int:
    seed = write_material_seed()
    n = len(seed["timeline"])
    mt = (seed["angular_acceleration"] or {}).get("motion_type", "uniform")
    nm = len(seed.get("angle_milestones", []))
    src = (seed.get("narrative_context") or {}).get("source", "none")
    print(f"OK material_seed.json ({len(seed['variables'])} vars, {n} timeline pts, "
          f"{nm} angle milestones, motion={mt}, context={src})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
