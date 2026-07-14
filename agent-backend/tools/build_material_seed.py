#!/usr/bin/env python3
"""Deterministic seed builder for Module D (grounded learning material).

Reads a finished job workspace and emits ``material_seed.json`` — the ground-truth
facts a generator (Qwen) turns into authentic explanatory prose WITHOUT inventing
numbers. The seed carries:

  * the measured variables (r, omega, v, a_c, T, f) with values + units + plain
    definitions,
  * the formula relations linking them (ground truth, so the model never guesses),
  * the angular-acceleration block (spin-up / coast-down) when present,
  * a TIME-ANCHORED timeline omega(t) reconstructed from the per-frame trajectory,
    so the material can say "at t=3 s it turns at ... by t=7 s it has sped up to ..."
    grounded on the real phenomenon,
  * paths to the annotated figures to reference in the prose.

Usage:  python tools/build_material_seed.py <job_id> [<job_id> ...]
        (writes material_seed.json into each job's analysis_output/data/)
"""
import json, sys, re, csv, pathlib

WS = pathlib.Path("workspaces")
OUT = pathlib.Path("material_work")  # host-writable staging (workspaces are root-owned)
FIG_NAMES = {
    "image": "annotated_image.png",
    "graph": "annotated_graph.png",
    "table": "annotated_table.png",
    "summary": "summary_panel.png",
}
N_TIMELINE = 4  # number of time-anchored samples


def find_ws(job_id: str):
    hits = sorted(WS.glob(f"job_{job_id}*"))
    return hits[0] if hits else None


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "scene").lower()).strip("-")[:40]


def _timeline_from_csv(csv_path, n=N_TIMELINE):
    """Sample the pipeline's own per-frame kinematics.csv over the ACTIVE window.

    Uses the pipeline's omega/v/a_c directly (consistent with the report), so the
    time-anchored narration matches every other number in the material.
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


def build(stats, kinematics_csv=None):
    calib = stats.get("calibration", {})
    summ = stats.get("summary", {})
    pf = stats.get("period_and_frequency", {})
    aa = stats.get("angular_acceleration", {})
    label = stats.get("tracked_label") or stats.get("object_name") or ""

    # v and a_c are BUILT from the fitted orbit radius (r_fit_m), not the mean of
    # per-frame point distances (mean_r_m) — they differ a few % on a noisy orbit.
    # Report r_fit_m so v = omega*r and a_c = omega^2*r close exactly at any instant.
    r_fit = calib.get("r_fit_m")
    r = r_fit if r_fit is not None else summ.get("mean_r_m")
    omega = summ.get("mean_omega")
    v = summ.get("mean_v")
    ac = summ.get("mean_ac")
    T = pf.get("period_s")
    f = pf.get("frequency_hz")

    variables = [
        {"symbol": "r", "name": "radius", "value": r, "unit": "m",
         "definition": "fitted radius of the orbit (the radius used to compute v and a_c)"},
        {"symbol": "omega", "name": "angular velocity", "value": omega, "unit": "rad/s",
         "definition": "how fast the angle swept per second (rate of change of angle)"},
        {"symbol": "v", "name": "tangential speed", "value": v, "unit": "m/s",
         "definition": "linear speed along the circular path"},
        {"symbol": "a_c", "name": "centripetal acceleration", "value": ac, "unit": "m/s^2",
         "definition": "acceleration pointing to the centre that keeps the object on its circle"},
        {"symbol": "T", "name": "period", "value": T, "unit": "s",
         "definition": "time for one full revolution"},
        {"symbol": "f", "name": "frequency", "value": f, "unit": "Hz",
         "definition": "revolutions per second"},
    ]

    relations = [
        {"name": "angular velocity", "formula": "omega = d(theta)/dt",
         "plain": "angular velocity is how quickly the swept angle changes with time"},
        {"name": "tangential speed", "formula": "v = omega * r",
         "plain": "the farther out (larger r) or the faster the spin (larger omega), the faster it moves"},
        {"name": "centripetal acceleration", "formula": "a_c = v^2 / r = omega^2 * r",
         "plain": "the inward acceleration grows with the square of the speed (or angular velocity)"},
        {"name": "period", "formula": "T = 2*pi / omega = 1 / f",
         "plain": "one full turn takes 2*pi radians divided by the angular velocity"},
    ]

    # angular-acceleration prose hook
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

    # time-anchored timeline (from the pipeline's own per-frame kinematics)
    timeline = []
    if kinematics_csv and pathlib.Path(kinematics_csv).exists():
        timeline = _timeline_from_csv(kinematics_csv)

    figs = stats.get("_figure_paths", {})  # filled by caller if available

    return {
        "object_name": stats.get("object_name"),
        "scene_title": stats.get("scene_title"),
        "tracked_label": label,
        "rotation_direction": summ.get("rotation_direction"),
        # active_duration_s = CLIP length; turning_duration_s = the active turning window (A1).
        "active_duration_s": (stats.get("video_info", {}) or {}).get("duration_s"),
        "turning_duration_s": (stats.get("tracking", {}) or {}).get("active_duration_s"),
        "variables": variables,
        "relations": relations,
        "angular_acceleration": aa_out,
        "timeline": timeline,
        "figures": figs,
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
    }


def main(job_ids):
    for jid in job_ids:
        ws = find_ws(jid)
        if not ws:
            print(f"!! no workspace for {jid}")
            continue
        data = ws / "analysis_output" / "data"
        sp = data / "stats.json"
        if not sp.exists():
            print(f"!! {ws.name}: no stats.json (not finished?)")
            continue
        stats = json.loads(sp.read_text())
        kin_csv = data / "kinematics.csv"

        # attach available figure paths
        plots = ws / "analysis_output" / "plots"
        figs = {}
        for key, name in FIG_NAMES.items():
            for cand in (plots / name, data.parent / name):
                if cand.exists():
                    figs[key] = str(cand.relative_to(ws))
                    break
        stats["_figure_paths"] = figs

        seed = build(stats, kin_csv if kin_csv.exists() else None)
        short = ws.name.replace("job_", "")[:8]
        dest = OUT / f"{slug(seed.get('scene_title') or seed.get('object_name'))}__{short}"
        dest.mkdir(parents=True, exist_ok=True)
        out = dest / "material_seed.json"
        out.write_text(json.dumps(seed, indent=2))
        tl = seed["timeline"]
        print(f"OK {ws.name}: material_seed.json  "
              f"({len(seed['variables'])} vars, {len(tl)} timeline pts"
              + (f", motion={seed['angular_acceleration']['motion_type']}"
                 if seed['angular_acceleration'] else "") + ")")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1:])
