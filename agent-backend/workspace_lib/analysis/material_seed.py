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
from .common import canonical_omega, dedup_display_name

DATA = Path("analysis_output/data")
N_TIMELINE = 4  # time-anchored samples across the active window

# Canonical figure names Subagent B produces (referenced in the prose).
FIGURES = {
    "image": "plots/annotated_image.png",
    "graph": "plots/annotated_graph.png",
    "table": "plots/annotated_table.png",
    "summary": "plots/summary_panel.png",
}


def _timeline_from_csv(csv_path: Path, n: int = N_TIMELINE, coast_from_peak: bool = False):
    """Sample the pipeline's own per-frame kinematics over the ACTIVE window.

    Uses kinematics.csv's omega/v/a_c directly so the time-anchored narration
    matches every other number in the material.

    A3: on an impulsive (flick) clip the active window straddles the peak, so evenly-spaced
    samples run pre-peak -> post-peak and a decay-framed narration reads two coast-down points
    as "climbed" (2.687 -> 4.802 skipping the 9.4 peak between them). With coast_from_peak the
    timeline starts at the peak, so every narrated instant sits on the coast-down (one phase)
    and the (t, omega) sequence is monotone non-increasing.
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
    if coast_from_peak:
        pk = max(range(len(rows)), key=lambda i: rows[i]["omega_rad_s"])
        if pk <= len(rows) - 5:          # keep >=5 coast-down rows; else leave the window as-is
            rows = rows[pk:]
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


# ── worked-example / check-your-understanding / honesty ingredients ────────────
# Everything below is computed here so the numbers are correct BY CONSTRUCTION — the
# LLM never authors them. report.py renders these blocks deterministically. This is the
# whole point of the material critique (numbers that check out), so the 35B is kept out
# of the arithmetic entirely (see docs/difficulty-tiered-material-spec.md).

# Canonical, verified LaTeX for each relation (math mode). Shared by "How the variables
# are related" and the worked examples so every occurrence typesets identically. Kept
# aligned with the seed's `relations` list; report.py renders these WITHOUT tex_escape.
FORMULA_TEX = {
    "circumference": r"C = 2\pi r",
    "v":             r"v = \omega\,r",
    "a_c":           r"a_{\mathrm{c}} = \omega^{2} r",
    "T":             r"T = \dfrac{2\pi}{\omega} = \dfrac{1}{f}",
    "alpha":         r"\alpha = \dfrac{\Delta\omega}{\Delta t}",
    "a_t":           r"a_{\mathrm{t}} = \alpha\,r",
    "omega2_avg":    r"\langle\omega^{2}\rangle \ge \langle\omega\rangle^{2}",
    "stop":          r"0 = \omega_{1} + \alpha\,t",
}

# Tier bridge appended to the last section — deterministic, no LLM.
TIER_BRIDGE = {
    "basic": "Ready for more? The intermediate edition puts numbers to these ideas: it "
             "measures the turn rate and the inward pull and shows exactly how they are linked.",
    "intermediate": "Ready for more? The advanced edition adds how the spin changes over "
                    "time — the angular acceleration — and reasons about what the measurement "
                    "can and cannot pin down.",
    "advanced": "",
}


def _g(x, sig=3):
    """Display string for a number at ~`sig` significant figures ('1.55', '18.6', '0.0505')."""
    if not isinstance(x, (int, float)) or x != x:
        return str(x)
    return f"{x:.{sig}g}"


def _objectives(ctx):
    """Per-tier 'After this material you can…' objectives (CLT depth ladder, Part B.2)."""
    obj = ctx["obj"]
    mt = ctx["motion"]
    trend = {"decelerating": "gradually slowing down",
             "accelerating": "gradually speeding up"}.get(mt)
    basic = [
        "Name what the radius, the period and the frequency of a circular motion are.",
        f"Describe, in plain words, how far and how fast the {obj} travels as it goes round.",
        "Explain why something moving in a circle needs an inward pull (a centripetal acceleration).",
    ]
    if trend:
        basic.append(f"See from the picture that the {obj} is {trend} as the clip goes on.")
    inter = [
        "Use v = ω·r to get the speed along the path from the turn rate and radius.",
        "Use a_c = ω²·r to find the inward (centripetal) acceleration.",
        "Move between period and frequency with T = 1/f = 2π/ω.",
        "Read the turn-rate graph and tie its value back to the tabulated numbers.",
    ]
    adv = [
        "Fit and interpret the angular acceleration α = Δω/Δt and the signed "
        "tangential acceleration a_t = α·r.",
        "Track how ω, v and a_c evolve across the clip using ω(t) = ω₀ + αt.",
        "Explain the ω² sensitivity of a_c and why plugging the clip-average ω does "
        "not reproduce the average a_c (⟨ω²⟩ > ⟨ω⟩²).",
        "State which measured quantities are independent of the calibration.",
    ]
    return {"basic": basic, "intermediate": inter, "advanced": adv}


def _relations_display(ctx):
    """Per-tier numbered relation list — each formula on its OWN display-math line with a
    one-line meaning, so "How the variables are related" reads as a scannable list instead of
    a wall of inline formulas. Basic stays words-only (empty). Uses the verified FORMULA_TEX
    bank so every formula typesets identically to the worked examples."""
    inter = [
        {"tex": r"T = \dfrac{1}{f} = \dfrac{2\pi}{\omega}",
         "plain": "Period and frequency are two views of one turn rate."},
        {"tex": FORMULA_TEX["a_c"],
         "plain": "The inward (centripetal) acceleration grows with the SQUARE of the turn rate."},
    ]
    adv = [
        {"tex": FORMULA_TEX["v"],
         "plain": "Linear speed along the path, from the turn rate and the radius."},
        {"tex": FORMULA_TEX["a_c"],
         "plain": "Centripetal acceleration — grows with the square of the turn rate."},
        {"tex": r"T = \dfrac{2\pi}{\omega} = \dfrac{1}{f}",
         "plain": "Period from the turn rate; frequency is its reciprocal."},
        {"tex": FORMULA_TEX["alpha"],
         "plain": "Angular acceleration — how fast the turn rate itself changes."},
        {"tex": FORMULA_TEX["a_t"],
         "plain": ("Tangential acceleration; negative here — it opposes the motion as the "
                   "spin winds down." if ctx["motion"] == "decelerating" else
                   "Tangential acceleration along the direction of travel.")},
        {"tex": r"a_{\mathrm{c}} \propto \omega^{2}",
         "plain": "Squared sensitivity: a small change in the turn rate moves a_c much more."},
    ]
    return {"basic": [], "intermediate": inter, "advanced": adv}


def _worked_examples(ctx):
    """Per-tier worked examples in house format (Given/Formula/Substitute/Result/Interpret),
    every number pre-evaluated. `formula_tex`/`substitute_tex` carry proper LaTeX for the
    intermediate/advanced math; basic stays symbol-free (words + one arithmetic line)."""
    obj, r, f, dur = ctx["obj"], ctx["r"], ctx["f"], ctx["dur"]
    # alpha is fit over the active window, NOT the whole clip — divide Delta-omega by this.
    fit_dt = ctx.get("fit_dt") or dur
    tl = ctx["tl"]
    out = {"basic": [], "intermediate": [], "advanced": []}

    # ---- basic (symbol-free) ----
    if isinstance(r, (int, float)):
        circ = 2 * math.pi * r
        out["basic"].append({
            "title": "How far does it travel in one lap?",
            "given": f"It sits about {_g(r)} m out from the centre.",
            "formula": "distance once around = 2 × π × radius",
            "substitute": f"2 × 3.14 × {_g(r)} m",
            "result": f"≈ {_g(circ)} m",
            "interpret": f"Every lap the {obj} travels about {_g(circ)} m along its circle, even "
                         f"though it never gets more than {_g(r)} m from the centre.",
        })
    # laps = turns/second × the time it is ACTUALLY TURNING (not the clip length — the object
    # is at rest for part of an impulsive/decaying clip, so f×clip_len over-counts ~3× (A1)).
    turn = ctx.get("turning_dur") or dur
    if isinstance(f, (int, float)) and isinstance(turn, (int, float)):
        laps = f * turn
        out["basic"].append({
            "title": "Roughly how many laps while it is turning?",
            "given": f"It actually turns for about {_g(turn)} s and makes about {_g(f, 2)} turns "
                     f"each second.",
            "formula": "laps = turns each second × seconds spent turning",
            "substitute": f"{_g(f, 2)} × {_g(turn)} s",
            "result": f"≈ {round(laps)} laps",
            "interpret": f"The dots pile up on the circle because the {obj} goes round about "
                         f"{round(laps)} times"
                         + (" before it stops." if ctx.get("comes_to_rest") else " as it spins."),
        })

    # ---- intermediate (one timeline instant, so v=ωr and a_c=ω²r close exactly) ----
    # Index 1 mirrors material_tiers.TIER_ANCHORS['intermediate']=[1] (kept in sync).
    if not ctx["unreliable"] and len(tl) > 1:
        s = tl[1]
        om, vv, ac = s["omega_rad_s"], s["v_m_s"], s["a_c_m_s2"]
        out["intermediate"].append({
            "title": "Speed along the path",
            "given": f"At t = {s['t_s']} s the turn rate is ω = {_g(om)} rad/s and r = {_g(r)} m.",
            "formula": "v = ω·r", "formula_tex": FORMULA_TEX["v"],
            "substitute": f"v = {_g(om)} × {_g(r)}",
            "substitute_tex": rf"v = {_g(om)} \times {_g(r)} = {_g(vv)}",
            "result": f"v ≈ {_g(vv)} m/s",
            "interpret": f"About the pace of a brisk walk — you could keep up with the {obj} on foot.",
        })
        out["intermediate"].append({
            "title": "Check the inward pull",
            "given": f"Same instant: ω = {_g(om)} rad/s, r = {_g(r)} m.",
            "formula": "a_c = ω²·r", "formula_tex": FORMULA_TEX["a_c"],
            "substitute": f"a_c = {_g(om)}² × {_g(r)}",
            "substitute_tex": rf"a_{{\mathrm{{c}}}} = {_g(om)}^{{2}} \times {_g(r)} = {_g(ac)}",
            "result": f"a_c ≈ {_g(ac)} m/s²",
            "interpret": "The inward (centripetal) acceleration that keeps it on its circle at "
                         "this moment.",
        })
    if isinstance(ctx["f"], (int, float)) and isinstance(ctx["T"], (int, float)):
        out["intermediate"].append({
            "title": "Period and frequency are one number, two ways",
            "given": f"The frequency is f = {_g(ctx['f'], 3)} Hz.",
            "formula": "T = 1/f", "formula_tex": r"T = \dfrac{1}{f}",
            "substitute": f"T = 1 / {_g(ctx['f'], 3)}",
            "substitute_tex": rf"T = \dfrac{{1}}{{{_g(ctx['f'], 3)}}} = {_g(ctx['T'])}",
            "result": f"T ≈ {_g(ctx['T'])} s",
            "interpret": "Frequency counts laps per second; the period times one lap. Either one "
                         "gives the other.",
        })

    # ---- advanced ----
    aa_ok = all(isinstance(ctx[k], (int, float)) for k in ("alpha", "omega_i", "omega_f", "a_t"))
    if aa_ok:
        al, oi, of_, at = ctx["alpha"], ctx["omega_i"], ctx["omega_f"], ctx["a_t"]
        out["advanced"].append({
            "title": "Fit the angular acceleration",
            "given": f"ω runs from {_g(oi)} rad/s to {_g(of_)} rad/s over {_g(fit_dt)} s "
                     f"of turning.",
            "formula": "α = Δω/Δt", "formula_tex": FORMULA_TEX["alpha"],
            "substitute": f"({_g(of_)} − {_g(oi)}) / {_g(fit_dt)}",
            "substitute_tex": rf"\alpha = \dfrac{{{_g(of_)} - {_g(oi)}}}{{{_g(fit_dt)}}} = {_g(al)}",
            "result": f"α ≈ {_g(al)} rad/s²",
            "interpret": ("The negative sign encodes the slow-down: it loses about "
                          f"{_g(abs(al), 2)} rad/s of spin every second."
                          if al < 0 else
                          f"It gains about {_g(abs(al), 2)} rad/s of spin every second."),
        })
        out["advanced"].append({
            "title": "Signed tangential acceleration",
            "given": f"α = {_g(al)} rad/s², r = {_g(r)} m.",
            "formula": "a_t = α·r", "formula_tex": FORMULA_TEX["a_t"],
            "substitute": f"a_t = {_g(al)} × {_g(r)}",
            "substitute_tex": rf"a_{{\mathrm{{t}}}} = {_g(al)} \times {_g(r)} = {_g(at)}",
            "result": f"a_t ≈ {_g(at)} m/s²",
            "interpret": ("It points against the direction of travel — that is what coasting "
                          "down means in vector language." if at < 0 else
                          "It points along the direction of travel, speeding the object up."),
        })
        # "Why the averages don't close" — the honest-data example (Jensen), only when we have
        # an omega range to build ⟨ω²⟩ from and the mean a_c to compare against.
        om_c, a_c_mean = ctx["omega"], ctx["a_c"]
        if all(isinstance(x, (int, float)) for x in (om_c, a_c_mean, oi, of_, r)):
            om2_avg = (oi * oi + oi * of_ + of_ * of_) / 3.0   # time-avg of ω² for linear ω(t)
            out["advanced"].append({
                "title": "Why the clip-average ω doesn't reproduce the average a_c",
                "given": f"Clip-average ω = {_g(om_c)} rad/s; measured average a_c = "
                         f"{_g(a_c_mean)} m/s².",
                "formula": "⟨ω²⟩ ≥ ⟨ω⟩²",
                "formula_tex": FORMULA_TEX["omega2_avg"],
                "substitute": f"{_g(om_c)}² × {_g(r)} = {_g(om_c*om_c*r)}  vs  "
                              f"⟨ω²⟩·r = {_g(om2_avg*r)}",
                "substitute_tex": rf"\langle\omega\rangle^{{2}} r = {_g(om_c*om_c*r)}"
                                  rf"\quad\text{{vs}}\quad \langle\omega^{{2}}\rangle r = {_g(om2_avg*r)}",
                "result": f"⟨ω²⟩·r ≈ {_g(om2_avg*r)} m/s², closer to the "
                          f"measured {_g(a_c_mean)}",
                "interpret": "Squaring the average is not the same as averaging the squares "
                             "whenever the speed changes, so plugging the mean ω falls short. "
                             "Each identity is still exact at a single instant.",
            })
        # Extrapolated stopping time — only for a decelerating clip that has NOT yet stopped.
        if ctx["motion"] == "decelerating" and not ctx["comes_to_rest"] and al and of_ > 0:
            t_stop = of_ / abs(al)
            out["advanced"].append({
                "title": "When would it stop?",
                "given": f"At the clip end ω = {_g(of_)} rad/s and α = {_g(al)} rad/s².",
                "formula": "0 = ω_final + α·t", "formula_tex": FORMULA_TEX["stop"],
                "substitute": f"t = {_g(of_)} / {_g(abs(al), 3)}",
                "substitute_tex": rf"t = \dfrac{{{_g(of_)}}}{{{_g(abs(al), 3)}}} = {_g(t_stop)}",
                "result": f"≈ {_g(t_stop)} s after the clip ends",
                "interpret": "This assumes the slow-down stays steady — a stated assumption, and "
                             "a good check on how far the model can be trusted.",
            })
    return out


def _check_understanding(ctx):
    """Per-tier check-your-understanding items {question, answer}, computed from the seed."""
    obj, r, v, f, T, dur = ctx["obj"], ctx["r"], ctx["v"], ctx["f"], ctx["T"], ctx["dur"]
    mt = ctx["motion"]
    out = {"basic": [], "intermediate": [], "advanced": []}

    out["basic"].append({
        "question": f"If the {obj} sat twice as far from the centre but swept round at the same "
                    f"rate, would the inward pull be stronger, weaker, or the same?",
        "answer": "Stronger — it doubles when the radius doubles.",
    })
    if mt == "decelerating":
        out["basic"].append({
            "question": "The dots marking each second sit a little closer together near the end "
                        "of the clip than at the start. What does that tell you?",
            "answer": f"The {obj} covers less angle each second — it is slowing down.",
        })
    elif mt == "accelerating":
        out["basic"].append({
            "question": "The dots marking each second spread a little farther apart near the end "
                        "of the clip. What does that tell you?",
            "answer": f"The {obj} covers more angle each second — it is speeding up.",
        })
    if isinstance(T, (int, float)):
        out["basic"].append({
            "question": f"One full turn takes about {_g(T)} s. In your own words, what does that "
                        f"number mean?",
            "answer": f"One complete lap takes about {_g(T)} s.",
        })

    if isinstance(f, (int, float)) and isinstance(T, (int, float)):
        out["intermediate"].append({
            "question": f"Using T = 1/f with f = {_g(f, 3)} Hz, work out T and compare with the table.",
            "answer": f"T = 1/{_g(f, 3)} ≈ {_g(T)} s — it matches the measured period.",
        })
    out["intermediate"].append({
        "question": "If ω doubled while r stayed the same, what would happen to a_c?",
        "answer": "It quadruples — a_c grows with the square of ω.",
    })
    # Arc length uses the TURNING time, not the clip length: v̄ is the mean speed WHILE turning,
    # so s = v̄·t_turning; multiplying by the whole clip (rest included) over-counts ~3× (A1).
    turn = ctx.get("turning_dur") or dur
    if isinstance(v, (int, float)) and isinstance(turn, (int, float)):
        out["intermediate"].append({
            "question": f"How far does the {obj} travel along its arc while it is turning "
                        f"(about {_g(turn)} s)?",
            "answer": f"s = v·t ≈ {_g(v)} × {_g(turn)} ≈ {_g(v*turn)} m.",
        })

    # These use the robust quadratic-fit endpoints (omega_initial/final, alpha) and r —
    # all reliable even on an oblique clip — so they are NOT gated on `unreliable`.
    aa_ok = all(isinstance(ctx[k], (int, float)) for k in ("alpha", "omega_i", "omega_f", "a_t"))
    if aa_ok:
        al, oi, of_, at = ctx["alpha"], ctx["omega_i"], ctx["omega_f"], ctx["a_t"]
        v0, v1 = oi * r, of_ * r
        ac0, ac1 = oi * oi * r, of_ * of_ * r
        out["advanced"].append({
            "question": "Work out the tangential speed at the start and end of the spin, and the "
                        "centripetal acceleration at each.",
            "answer": f"v ≈ {_g(v0)} → {_g(v1)} m/s; a_c ≈ {_g(ac0)} → {_g(ac1)} m/s².",
        })
        out["advanced"].append({
            "question": "The tangential acceleration is a_t = α·r. Compute it and state its "
                        "direction.",
            "answer": f"a_t = {_g(al)} × {_g(r)} ≈ {_g(at)} m/s²; "
                      + ("it points against the motion (slowing down)." if at < 0
                         else "it points along the motion (speeding up)."),
        })
        if mt == "decelerating" and not ctx["comes_to_rest"] and al and of_ > 0:
            out["advanced"].append({
                "question": "If it kept slowing at the same rate, how long after the clip until it stops?",
                "answer": f"t = ω_final/|α| ≈ {_g(of_)}/{_g(abs(al), 3)} "
                          f"≈ {_g(of_/abs(al))} s.",
            })
    if isinstance(ctx["px_per_m"], (int, float)):
        out["advanced"].append({
            "question": f"The absolute a_c depends on the calibration ({_g(ctx['px_per_m'], 5)} px/m). "
                        f"Which reported quantities are calibration-independent?",
            "answer": "ω, α, T and f — all the angular ones; r, v, a_c and a_t scale with "
                      "the calibration.",
        })
    return out


def _honesty(ctx):
    """Per-tier measurement-honesty box text (oblique projection, averages-vs-instant,
    calibration), deepening with tier per Part B.2."""
    obj, mt, unreliable = ctx["obj"], ctx["motion"], ctx["unreliable"]
    trend = {"decelerating": "slowing down", "accelerating": "speeding up"}.get(mt)
    oblique = (" The clip was filmed at a slight angle, so the exact turn rate at any single "
               "instant is hard to pin down; only the whole-clip trend is reliable."
               if unreliable else "")
    basic = ("A note on honesty: the numbers here are summaries over the whole clip." +
             (f" Because the {obj} is {trend}, its speed at any one instant differs from the "
              f"average, but the average is still a faithful picture of the motion." if trend else "")
             + oblique)
    # When the speed is changing, the SAME averaging subtlety hits the period: the average
    # period is not 2π over the average turn rate. Say so, so the material never quietly
    # implies 2π/ω̄ = T (the closure the intermediate edition wrongly asserted for the wheel).
    period_note = (" The same caution applies to the period: because the turn rate is "
                   "changing, the average period is not simply 2π divided by the average "
                   "turn rate." if trend else "")
    inter = (basic + " This is also why putting the average turn rate into a_c = ω²·r "
             "does not exactly reproduce the average inward acceleration: squaring an average is "
             "not the same as averaging the squares, so the two differ slightly whenever the "
             "speed changes. Each identity is exact at a single instant." + period_note)
    px = ctx["px_per_m"]
    cal_line = (f" Absolute values of r, v, a_c and a_t all scale with the calibration "
                f"({_g(px, 5)} px per metre); the angular quantities ω, α, T and f are "
                f"scale-free and independent of it." if isinstance(px, (int, float)) else "")
    adv = (inter + " Formally ⟨ω²⟩ ≥ ⟨ω⟩² for any varying "
           "ω (a Jensen inequality), so the inward acceleration built from ⟨ω²⟩ "
           "exceeds the one from the mean ω squared." + cal_line)
    return {"basic": basic, "intermediate": inter, "advanced": adv}


def build_seed(stats: dict, csv_path: Path | None = None) -> dict:
    calib = stats.get("calibration", {})
    summ = stats.get("summary", {})
    pf = stats.get("period_and_frequency", {})
    aa = stats.get("angular_acceleration", {})
    sp = stats.get("stable_phase", {})

    # The radius v and a_c are BUILT from is the fitted orbit radius (r_fit_m), not the
    # mean of per-frame point distances (mean_r_m) — they differ a few % on a noisy orbit.
    # Report r_fit_m so v = omega*r and a_c = omega^2*r close exactly at every instant.
    r_fit = calib.get("r_fit_m")
    r_report = r_fit if r_fit is not None else summ.get("mean_r_m")

    # ONE canonical angular velocity the whole document quotes (A2/A4), shared with the
    # report table + figures via common.canonical_omega so prose and table never diverge.
    # For a (de)accelerating clip this is the true time-AVERAGE (mean_omega), NOT
    # stable_mean_omega: on the red-phone flick stable_mean_omega was a fluke 2.89 rad/s
    # that broke v=omega*r and T=2pi/omega by ~2x, while mean_omega (5.79) closes exactly.
    # Magnitude only (direction lives in rotation_direction, so the prose ω never
    # contradicts the table with a stray sign).
    omega_canonical, _omega_is_clip_avg = canonical_omega(stats)

    variables = [
        {"symbol": "r", "name": "radius", "value": r_report, "unit": "m",
         "definition": "fitted radius of the orbit (the radius used to compute v and a_c)"},
        {"symbol": "omega", "name": "angular velocity", "value": omega_canonical,
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
        # SIGNED tangential acceleration a_t = alpha*r (A3). New pipeline runs store this
        # signed already; older stats.json still hold the magnitude, so re-sign from alpha
        # here to be robust to either — a_t must carry alpha's sign (negative decelerating).
        alpha_v = aa.get("alpha_rad_s2")
        a_t_v = aa.get("a_t_mean_m_s2")
        if isinstance(a_t_v, (int, float)) and isinstance(alpha_v, (int, float)):
            a_t_v = math.copysign(abs(a_t_v), alpha_v)
        aa_out = {
            "motion_type": mt,
            "alpha_rad_s2": alpha_v,
            "alpha_r2": aa.get("alpha_r2"),
            "omega_initial": aa.get("omega_initial"),
            "omega_final": aa.get("omega_final"),
            "a_t_mean_m_s2": a_t_v,
            "impulsive_start": bool(aa.get("impulsive_start")),
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
        # Impulsive clips sample the coast-down only, so the advanced over-time narration is
        # monotone and never reads a pre-peak vs post-peak pair as "climbing" (A3).
        timeline = _timeline_from_csv(Path(csv_path),
                                      coast_from_peak=bool(aa_out and aa_out.get("impulsive_start")))
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

    unreliable = bool(measurement_quality) and not measurement_quality.get("reliable", True)
    duration_s = (stats.get("video_info", {}) or {}).get("duration_s")
    tracking = stats.get("tracking", {}) or {}
    active_end_s = tracking.get("active_end_s")
    # The span alpha is fit over (Delta-omega / fit_window, NOT / whole-clip duration). Older
    # stats.json predate the field — fall back to the active duration, then the clip length.
    fit_dt = aa.get("fit_window_s")
    if not isinstance(fit_dt, (int, float)) or fit_dt <= 0:
        fit_dt = tracking.get("active_duration_s") or duration_s

    # comes_to_rest: a decelerating clip that actually reaches (near) zero spin WITHIN the
    # clip — gates the "slows to rest" narrative and the stopping-time example (A7). Two ways
    # to qualify: (a) the fit's final omega is already ~0, or (b) the object STOPPED ON CAMERA
    # — its active window ends well before the clip does (it spun down and then sat still).
    # The red-phone flick stops at ~4.4 s of a 5.84 s clip, so (b) catches it even though the
    # fit's omega_final (2.13, extrapolated to the active-window end) is not near zero. At
    # 6.25 rad/s the black-handle clip does NOT stop, so this stays False and the prose says
    # "still turning, more slowly, when the clip ends".
    omega_final = (aa_out or {}).get("omega_final")
    is_decel = bool(aa_out and aa_out["motion_type"] == "decelerating")
    stops_by_omega = is_decel and isinstance(omega_final, (int, float)) and abs(omega_final) < 0.5
    stops_on_camera = (is_decel and isinstance(active_end_s, (int, float))
                       and isinstance(duration_s, (int, float))
                       and active_end_s < duration_s - 0.5)
    comes_to_rest = bool(stops_by_omega or stops_on_camera)

    ctx = {
        "obj": object_name or "object",
        "r": r_report, "omega": omega_canonical,
        "v": _absval(summ.get("mean_v")), "a_c": summ.get("mean_ac"),
        "T": pf.get("period_s"), "f": pf.get("frequency_hz"),
        "dur": duration_s, "fit_dt": fit_dt,
        # The TURNING window (how long the object actually spun), not the clip length. On the
        # impulsive flick it turns for ~1.9 s of a ~5.9 s clip; any rate*time product (laps,
        # arc distance, angle swept) must use THIS, never the clip duration (A1). Falls back to
        # the clip length for a clip that spins throughout (active window ~= duration).
        "turning_dur": tracking.get("active_duration_s"),
        "alpha": (aa_out or {}).get("alpha_rad_s2"),
        "omega_i": (aa_out or {}).get("omega_initial"),
        "omega_f": omega_final,
        "a_t": (aa_out or {}).get("a_t_mean_m_s2"),
        "motion": (aa_out or {}).get("motion_type", "uniform"),
        "impulsive": bool((aa_out or {}).get("impulsive_start")),
        "comes_to_rest": comes_to_rest,
        "px_per_m": calib.get("px_per_m"),
        "tl": timeline,
        "unreliable": unreliable,
        "direction": summ.get("rotation_direction"),
    }

    return {
        "object_name": object_name,
        "scene_title": scene_title,
        "tracked_label": stats.get("tracked_label"),
        "rotation_direction": summ.get("rotation_direction"),
        # NOTE: `active_duration_s` here holds the CLIP length (whole clip); the ACTIVE turning
        # window lives in `turning_duration_s`. The name is kept for back-compat with consumers
        # that quote it as the clip length; new callers should prefer the two explicit fields.
        "active_duration_s": (stats.get("video_info", {}) or {}).get("duration_s"),
        "turning_duration_s": tracking.get("active_duration_s"),
        "active_start_s": tracking.get("active_start_s"),
        "active_end_s": tracking.get("active_end_s"),
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
        # ── deterministic learning-material blocks (correct by construction) ──
        "comes_to_rest": comes_to_rest,
        "objectives": _objectives(ctx),
        "relations_display": _relations_display(ctx),
        "worked_examples": _worked_examples(ctx),
        "check_understanding": _check_understanding(ctx),
        "measurement_honesty": _honesty(ctx),
        "tier_bridge": TIER_BRIDGE,
        "formula_tex": FORMULA_TEX,
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
    we = seed.get("worked_examples") or {}
    cyu = seed.get("check_understanding") or {}
    nwe = sum(len(v) for v in we.values())
    ncy = sum(len(v) for v in cyu.values())
    print(f"OK material_seed.json ({len(seed['variables'])} vars, {n} timeline pts, "
          f"{nm} angle milestones, motion={mt}, context={src}, "
          f"{nwe} worked examples, {ncy} CYU, comes_to_rest={seed.get('comes_to_rest')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
