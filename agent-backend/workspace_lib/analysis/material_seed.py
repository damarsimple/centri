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
from .common import SIGN_NOTE, canonical_omega, dedup_display_name, motion_along_travel

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

# WS-4: each level is a STAIRCASE of three graded steps, not one jump. The steps are named
# here (deterministically — never by the writer) and printed as a strip at the top of the
# level, so a reader can see which rung they are on and what the next one asks. Three
# documents, three graded steps inside each; the machine keys and filenames are unchanged.
# `after` names the section this step actually ENDS at, so report.py can print the step's
# checkpoint there. A staircase printed only as a map at the top tells the reader where the
# rungs are without ever making them stand on one; the checkpoint is what turns the map into
# something you have to climb. `check` is the question that has to be answerable to go on —
# its answer prints in the teacher copy only, like every other answer.
TIER_STEPS = {
    "basic": [
        {"title": "What the words mean",
         "goal": "Say what the radius, the period and the turn rate each measure.",
         "after": "What these words mean",
         "check": "Without looking back: which of the three tells you how long one lap takes, "
                  "and which tells you how far out the object sits?",
         "answer": "The period is the time for one lap. The radius is how far out it sits."},
        {"title": "What this clip's numbers are",
         "goal": "Read this object's own radius, period and turns-per-second off the table "
                 "and the picture.",
         "after": "The variables we measured",
         "check": "Point to where each of those three numbers appears in the picture or the "
                  "text above. Which one is NOT marked on the picture?",
         "answer": "The radius is marked on the picture; the period and the turns-per-second "
                   "come from the text. (The picture marks the turn rate as turns per second.)"},
        {"title": "Which idea joins them",
         "goal": "Explain why a wider circle, or a faster sweep, needs a stronger inward pull.",
         "after": "How the variables are related",
         "check": "Two objects sweep round at the same rate, one on a small circle and one on "
                  "a big one. Which needs the stronger inward pull?",
         "answer": "The one on the bigger circle."},
    ],
    "intermediate": [
        {"title": "Read the graph in words",
         "goal": "Describe what the turn-rate graph does, with no formula at all.",
         "after": "What the video shows over time",
         "check": "In one sentence, and without using a symbol: what does the turn-rate graph "
                  "do from the start of the clip to the end?",
         "answer": "It falls — the object sweeps round more slowly as the clip goes on "
                   "(or rises, on a clip that speeds up)."},
        {"title": "Meet the equation, and put this clip's numbers in",
         "goal": "Recognise a_c = ω²·r as the compact way to say what you just described, and "
                 "evaluate it at one instant.",
         "after": "How the variables are related",
         "check": "If the turn rate at some instant were half what you used, what would the "
                  "inward acceleration be?",
         "answer": "A quarter of it — a_c follows the SQUARE of the turn rate."},
        {"title": "How long to slow from this rate to that one",
         "goal": "Read two turn rates off the graph and say how long the object took to fall "
                 "between them.",
         "after": "Reading the figures",
         "check": "You read that time off the graph rather than calculating it. What would you "
                  "need to know to calculate it instead?",
         "answer": "How fast the turn rate itself is changing — the angular acceleration, "
                   "which is what the advanced edition measures."},
    ],
    "advanced": [
        {"title": "Compare two moments",
         "goal": "Take two instants and account for the difference in ω, v and a_c between them.",
         "after": "How the variables are related",
         "check": "Between your two instants the turn rate fell by some factor. By what factor "
                  "did the inward acceleration fall, and why is it not the same factor?",
         "answer": "By the SQUARE of that factor, because a_c = ω²·r and only ω changed."},
        {"title": "Compare the phases of the motion",
         "goal": "Say how the parts of the clip differ from one another, and by how much.",
         "after": "What the video shows over time",
         "check": "Which part of the clip would give the most misleading answer if you "
                  "described the whole clip by its average alone?",
         "answer": "The part furthest from the average — on a clip that slows, the fast opening "
                   "stretch; the average understates it and overstates the end."},
        {"title": "Which claims does this video actually support?",
         "goal": "Separate what the measurement pins down from what it only suggests, and "
                 "say why.",
         "after": "__CLAIMS__",
         "check": "Of the claims you just judged, which one would a longer clip settle, and "
                  "which would still be unsettled however long the clip ran?",
         "answer": "A longer clip settles what happens after the last frame (the stopping "
                   "time). It never settles the real-world scale — that rests on the measured "
                   "size in the scene, not on the length of the recording."},
    ],
}

# The bridge BETWEEN levels, appended to the last section. It names the step it hands over
# to (A3 -> B1, B3 -> C1) rather than advertising the next document in general, so the three
# editions read as one staircase instead of three separate documents.
TIER_BRIDGE = {
    "basic": "Ready for more? Step 1 of the intermediate edition picks up exactly where "
             "step 3 leaves off: it reads the turn-rate graph in words, and then meets "
             "a_c = ω²·r as the compact way to write down what you have just explained.",
    "intermediate": "Ready for more? Step 1 of the advanced edition picks up exactly where "
                    "step 3 leaves off: instead of reading the fall off the graph, it "
                    "compares two moments directly, turns the difference into a single "
                    "rate — the angular acceleration — and then asks how far that rate can "
                    "be trusted.",
    "advanced": "",
}


def _g(x, sig=3):
    """Display string for a number at ~`sig` significant figures ('1.55', '18.6', '0.0505')."""
    if not isinstance(x, (int, float)) or x != x:
        return str(x)
    return f"{x:.{sig}g}"


def _shown(x, sig=3):
    """The value a reader actually SEES, as a number.

    A worked example has to close on the figures it prints: a student multiplying
    "1.2 × 15 s" must get the number on the result line. Computing from the full-precision
    value instead lets the two disagree whenever the rounding falls the other way — on
    roundabout-4046, f = 1.2479 and t = 14.998 give 18.7 → "≈ 19 laps" under a substitution
    line that reads 1.2 × 15 = 18. It fires only near a .5 boundary, which is how it
    survived a whole sweep. Round-tripping through `_g` makes display and arithmetic the
    same number by construction.
    """
    return float(_g(x, sig))


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
    # Written at high-school reading level (WS-2.1): the ideas are unchanged, but the terms a
    # physics teacher flagged — "calibration", "scale-free", the ⟨·⟩ average notation and the
    # name of the inequality — are said in plain words here and stated formally only in the
    # teacher copy (`_teacher_notes`).
    adv = [
        "Fit and interpret the angular acceleration α = Δω/Δt and the tangential "
        "acceleration a_t = α·r, and say what a negative value of each one means.",
        "Track how ω, v and a_c evolve across the clip using ω(t) = ω₀ + αt.",
        "Explain why a_c follows the SQUARE of the turn rate, and why putting the clip's "
        "average turn rate into a_c = ω²·r does not give back the average a_c.",
        "Say which of the reported quantities would be wrong if the scene had been sized "
        "wrongly, and which would be unaffected.",
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
        # 3.14 and the rounded radius, because that is what the substitution line shows the
        # student to multiply. Using math.pi and full-precision r here would be more accurate
        # and less honest — the printed arithmetic has to be the arithmetic we did.
        circ = 2 * 3.14 * _shown(r)
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
        laps = _shown(f, 2) * _shown(turn)
        out["basic"].append({
            "title": "Roughly how many laps while it is turning?",
            "given": f"It actually turns for about {_g(turn)} s and makes about {_g(f, 2)} turns "
                     f"each second.",
            "formula": "laps = turns each second × seconds spent turning",
            "substitute": f"{_g(f, 2)} × {_g(turn)} s",
            "result": f"≈ {round(laps)} laps",
            "interpret": f"So the {obj} goes all the way round about {round(laps)} times"
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
    # ---- intermediate, step 3 (WS-4 B3): squeeze the graph harder ----
    # "How long to slow from this speed to that one", answered by READING the measurement, not
    # by computing it from a fitted rate: the angular acceleration and everything built on it
    # stay at the advanced level, which is where the step-3 -> step-1 bridge hands over. Two
    # timeline instants far enough apart that the fall is real, never a rounding artifact.
    if not ctx["unreliable"] and len(tl) >= 2 and ctx["motion"] in ("decelerating", "accelerating"):
        # A sub-interval, not the whole clip: "how long did the WHOLE thing take" is the clip
        # length the reader already has, which would make step 3 easier than step 2 rather
        # than harder. Two named instants inside the record is the real step up from B2's
        # single instant, and it sets up C1's compare-two-moments directly.
        a, b = tl[0], (tl[-2] if len(tl) >= 3 else tl[-1])
        w_a, w_b = abs(a["omega_rad_s"]), abs(b["omega_rad_s"])
        dt = _shown(b["t_s"]) - _shown(a["t_s"])
        faster, slower = (a, b) if w_a >= w_b else (b, a)
        drop = abs(_shown(w_a) - _shown(w_b))
        if dt > 0 and drop > 0.05 * max(w_a, w_b):
            verb = "slow" if ctx["motion"] == "decelerating" else "speed up"
            out["intermediate"].append({
                "title": f"How long did it take to {verb} from one turn rate to the other?",
                "given": f"The turn-rate graph reads ω = {_g(abs(faster['omega_rad_s']))} rad/s "
                         f"at t = {_g(faster['t_s'])} s and ω = "
                         f"{_g(abs(slower['omega_rad_s']))} rad/s at t = {_g(slower['t_s'])} s.",
                "formula": "time taken = later time − earlier time",
                "formula_tex": r"\Delta t = t_{2} - t_{1}",
                "substitute": f"{_g(_shown(b['t_s']))} − {_g(_shown(a['t_s']))}",
                "substitute_tex": rf"\Delta t = {_g(_shown(b['t_s']))} - "
                                  rf"{_g(_shown(a['t_s']))} = {_g(dt)}",
                "result": f"≈ {_g(dt)} s",
                "interpret": f"So the {obj} took about {_g(dt)} s to change its turn rate by "
                             f"{_g(drop)} rad/s. You read that straight off the measurement. The "
                             f"advanced edition turns the same fall into a single rate and then "
                             f"asks how far that rate can be trusted.",
            })

    # ---- advanced ----
    aa_ok = all(isinstance(ctx[k], (int, float)) for k in ("alpha", "omega_i", "omega_f", "a_t"))
    if aa_ok:
        al, oi, of_, at = ctx["alpha"], ctx["omega_i"], ctx["omega_f"], ctx["a_t"]
        out["advanced"].append({
            "title": "Fit the angular acceleration",
            # oi/of_ are SPEEDS (see the aa_out block): quoting a signed range here next to
            # the unsigned clip-average ω elsewhere is what made "ω runs from −9.51 to −0.03"
            # sit beside "clip-average ω = 5.7" in the same edition.
            "given": f"The turn rate goes from {_g(oi)} rad/s to {_g(of_)} rad/s over "
                     f"{_g(fit_dt)} s of turning.",
            "formula": "α = Δω/Δt", "formula_tex": FORMULA_TEX["alpha"],
            "substitute": f"({_g(of_)} − {_g(oi)}) / {_g(fit_dt)}",
            "substitute_tex": rf"\alpha = \dfrac{{{_g(of_)} - {_g(oi)}}}{{{_g(fit_dt)}}} = {_g(al)}",
            "result": f"α ≈ {_g(al)} rad/s²",
            "interpret": ("The minus sign says the turn rate is falling — it is not a value "
                          f"below nothing: the {obj} loses about {_g(abs(al), 2)} rad/s of "
                          f"spin every second."
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
            "interpret": ("The minus sign is a direction: it points against the way the "
                          f"{obj} is travelling, which is what coasting down means in vector "
                          "language." if at < 0 else
                          "It points along the direction of travel, speeding the object up."),
        })
        # "Why the averages don't close" — the honest-data example. It compares exactly two
        # numbers the reader can already see: the shortcut (average ω)²·r, and the MEASURED
        # average a_c. The old version compared the shortcut against a third value modelled
        # from the fit endpoints — a different averaging window from the one the mean ω comes
        # from, so on both fan clips it printed the inequality backwards (19.2 "greater than"
        # 20.6) and then called the further number "closer to the measured".
        # Averages are written in WORDS, never as ⟨ω⟩ (WS-2.1): the angle-bracket notation and
        # the name of the inequality are teacher-copy material, the idea is not.
        om_c, a_c_mean = ctx["omega"], ctx["a_c"]
        naive = om_c * om_c * r if all(isinstance(x, (int, float))
                                       for x in (om_c, a_c_mean, r)) else None
        # Only claim the shortcut undershoots when it demonstrably does on THIS clip: mean a_c
        # averages per-frame radii, so a wandering orbit could in principle close the gap.
        if naive is not None and naive < a_c_mean:
            out["advanced"].append({
                "title": "Why the average turn rate doesn't reproduce the average inward pull",
                "given": f"Average turn rate ω = {_g(om_c)} rad/s and r = {_g(r)} m; the "
                         f"measured average inward acceleration is {_g(a_c_mean)} m/s².",
                "formula": "(average ω)²·r, compared with the measured average a_c",
                "formula_tex": r"(\text{average }\omega)^{2} r \;<\; "
                               r"\text{average } a_{\mathrm{c}}",
                "substitute": f"(average ω)²·r = {_g(om_c)}² × {_g(r)} = {_g(naive)}",
                "substitute_tex": rf"({_g(om_c)})^{{2}} \times {_g(r)} = {_g(naive)}",
                "result": f"{_g(naive)} m/s² — short of the measured {_g(a_c_mean)} m/s²",
                "interpret": "Squaring the average is not the same as averaging the squares. "
                             "Whenever the turn rate changes, the average of ω² is larger than "
                             "the square of the average ω, so this shortcut always undershoots "
                             "the real average inward pull. Each identity is still exact at a "
                             "single instant.",
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

    # ---- fade the advanced examples (expertise reversal) ---------------------
    # A fully worked example is what a NOVICE needs; for a reader who already has the schema it
    # stops helping and starts replacing the practice that would build it. The standard remedy
    # is fading: keep the first one worked in full as the model, then hand the reader the last
    # step of each one that follows. `fade` tells report.py to withhold the result from the
    # student edition — the teacher copy still prints it, like every other answer.
    for e in out["advanced"][1:]:
        e["fade"] = True
    return out


def _check_understanding(ctx):
    """Per-tier check-your-understanding items {question, answer}, computed from the seed."""
    obj, r, v, f, T, dur = ctx["obj"], ctx["r"], ctx["v"], ctx["f"], ctx["T"], ctx["dur"]
    mt = ctx["motion"]
    out = {"basic": [], "intermediate": [], "advanced": []}

    out["basic"].append({
        # Keep the answer QUALITATIVE: the basic relations section teaches "bigger circle -> stronger
        # inward pull" in words only, so answering "it doubles" would test a proportionality the tier
        # never taught (Part B #3 — assessment/instruction alignment).
        "question": f"If the {obj} sat twice as far from the centre but swept round at the same "
                    f"rate, would the inward pull be stronger, weaker, or the same?",
        "answer": "Stronger — a wider circle needs a stronger inward pull to hold the same turn rate.",
    })
    # These reference the "turns completed vs time" graph (fig_angle_points_basic), whose SHAPE
    # shows the speed change — matching what the figure actually draws (C5/A4). The old wording
    # cited per-second dots on the circle that the figure no longer contains.
    if mt == "decelerating":
        out["basic"].append({
            "question": "On the 'turns completed' graph, the line climbs steeply at first and then "
                        "bends flatter toward the end. What does that tell you about the motion?",
            "answer": f"The {obj} completes fewer turns each second — it is slowing down.",
        })
    elif mt == "accelerating":
        out["basic"].append({
            "question": "On the 'turns completed' graph, the line climbs ever more steeply toward "
                        "the end. What does that tell you about the motion?",
            "answer": f"The {obj} completes more turns each second — it is speeding up.",
        })
    if isinstance(T, (int, float)):
        out["basic"].append({
            "question": f"One full turn takes about {_g(T)} s. In your own words, what does that "
                        f"number mean?",
            "answer": f"One complete lap takes about {_g(T)} s.",
        })
    # The tangential-release item used to live here; it now sits in `_misconceptions` with the
    # rest of the documented circular-motion misconceptions, printed under its own heading so a
    # teacher can see at a glance which ones the material confronts.

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
            # Plain words, no "calibration" and no pixel count: same idea, a reading level a
            # high-school student actually has (WS-2.1).
            "question": "Every length here is worked out from one measured size in the scene — "
                        "a real object of known width, used to turn on-screen size into metres. "
                        "If that size were 10% too big, which of the reported quantities would "
                        "be wrong, and which would be unaffected?",
            "answer": "The turn rate ω, the angular acceleration α, the period T and the "
                      "frequency f would be unaffected — they are angles and times, and an "
                      "angle does not depend on how big we think the scene is. The radius r, "
                      "the speed v and both accelerations a_c and a_t would each be 10% out, "
                      "because every one of them is built from that size.",
        })
    return out


def _honesty(ctx):
    """Per-tier measurement-honesty box text (oblique projection, averages-vs-instant,
    calibration), deepening with tier per Part B.2."""
    obj, mt, unreliable = ctx["obj"], ctx["motion"], ctx["unreliable"]
    trend = {"decelerating": "slowing down", "accelerating": "speeding up"}.get(mt)
    # Plain-language, not capture jargon: "filmed" is on the student-facing vocabulary
    # blocklist (material_gate.TRACKING_VOCAB), so wording the caveat that way asks the
    # writer for a sentence its own gate then rejects.
    oblique = (" The circle is seen at a slight slant rather than face-on, so the exact turn "
               "rate at any single instant is hard to pin down; only the whole-clip trend is "
               "reliable." if unreliable else "")
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
    # One plain sentence for what used to be two named ideas ("calibration-independent" and
    # "scale-free" say the same thing twice), and the formal inequality is gone from the
    # student edition entirely — it is stated in the teacher copy instead (WS-2.1).
    cal_line = (" One more thing worth knowing: every length here — the radius, the speed and "
                "both accelerations — is worked out from a single measured size in the scene, "
                "so all of them would be out by the same proportion if that size were wrong. "
                "The turn rate, the angular acceleration, the period and the frequency are "
                "angles and times, so they do not depend on it at all."
                if isinstance(px, (int, float)) else "")
    adv = inter + cal_line
    return {"basic": basic, "intermediate": inter, "advanced": adv}


def _predict_first(ctx):
    """Predict-Observe-Explain: one prediction per tier, printed BEFORE the measurement it is
    about, with the answer in the teacher copy only.

    This is the affordance the medium actually gives us. A textbook cannot stop before the
    reveal; a video can, and a worksheet built from a video should. Every prediction below is
    about something the reader is about to see in THIS clip's own data, so it is checkable
    against the page rather than against an opinion — and each targets the specific intuition
    that the measurement is about to correct.
    """
    obj, mt, tl = ctx["obj"], ctx["motion"], ctx["tl"]
    out = {"basic": [], "intermediate": [], "advanced": []}
    trend = {"decelerating": ("fewer", "more"), "accelerating": ("more", "fewer")}.get(mt)
    if trend:
        got, _other = trend
        out["basic"].append({
            "prompt": f"Before you read on. In a moment you will see a graph of how many turns "
                      f"the {obj} has completed as time passes. As the clip goes on, do you "
                      f"think it completes MORE turns each second, FEWER, or the same number? "
                      f"Write down your guess, then check it against the graph.",
            "answer": f"{got.capitalize()} — the {obj} is "
                      + ("slowing down" if mt == "decelerating" else "speeding up") +
                      ", so the line "
                      + ("bends flatter" if mt == "decelerating" else "steepens") + ".",
        })
    else:
        out["basic"].append({
            "prompt": f"Before you read on. In a moment you will see a graph of how many turns "
                      f"the {obj} has completed as time passes. Do you expect that line to be "
                      f"straight, or to bend? Write down your guess, then check it.",
            "answer": "Straight — this clip turns at a steady rate, so the same number of "
                      "turns accumulates in every second.",
        })
    # Intermediate predicts the SQUARE law before meeting a_c = ω²·r — the single most
    # commonly mis-predicted relation in circular motion.
    out["intermediate"].append({
        "prompt": f"Before you read on. You are about to meet the rule linking the turn rate "
                  f"to the inward acceleration. Suppose the {obj} swept round at HALF the turn "
                  f"rate, on the same circle. Would the inward acceleration be half as big, a "
                  f"quarter as big, or unchanged? Commit to an answer before you read the next section.",
        "answer": "A quarter as big. The inward acceleration follows the SQUARE of the turn "
                  "rate, so halving ω divides a_c by four — most readers predict 'half'.",
    })
    if len(tl) > 1 and not ctx["unreliable"]:
        a, b = tl[0], tl[-1]
        wa, wb = abs(a["omega_rad_s"]), abs(b["omega_rad_s"])
        if wa and wb and abs(wa - wb) > 0.05 * max(wa, wb):
            hi, lo = (a, b) if wa >= wb else (b, a)
            out["advanced"].append({
                "prompt": f"Before you read on. At t = {_g(hi['t_s'])} s the turn rate is "
                          f"{_g(abs(hi['omega_rad_s']))} rad/s; at t = {_g(lo['t_s'])} s it is "
                          f"{_g(abs(lo['omega_rad_s']))} rad/s. Without computing anything: is "
                          f"the inward acceleration at the second instant more or less than "
                          f"half the first? Predict, then verify from the data below.",
                "answer": f"Less than half. The turn rate falls by a factor of "
                          f"{_g(abs(hi['omega_rad_s']) / abs(lo['omega_rad_s']), 2)}, so a_c "
                          f"falls by the SQUARE of that — "
                          f"{_g((abs(hi['omega_rad_s']) / abs(lo['omega_rad_s'])) ** 2, 2)}.",
            })
    return out


def _misconceptions(ctx):
    """The documented circular-motion misconceptions this material can confront.

    NOTE THE FENCE. This is a kinematics lesson — it describes HOW the object moves and never
    names a cause (material_gate.DYNAMICS_VOCAB). That rules out the misconception cluster
    that lives in the dynamics: centrifugal force as a real outward push, centripetal force as
    an extra force rather than a net one, "what keeps it moving". The three below are the ones
    that can be posed honestly WITHOUT naming a force, and they are the ones a kinematics
    treatment is actually equipped to correct. The rest need the fence moved, which is a
    teaching decision, not a code change.
    """
    obj, r = ctx["obj"], ctx["r"]
    tangent = {
        "misconception": "a released object flies radially outward",
        "question": f"Suppose the {obj} suddenly came loose while spinning. Which way would it "
                    f"head off — straight outward from the centre, or straight ahead in the "
                    f"direction it was already moving?",
        "answer": "Straight ahead, along the direction it was already moving (the tangent). "
                  "Nothing flings it outward — the inward pull simply stops, so it carries on "
                  "in a straight line.",
    }
    steady_but_accelerating = {
        "misconception": "constant speed means no acceleration",
        "question": f"Imagine the {obj} went round at a perfectly steady rate, never speeding "
                    f"up or slowing down. Would its inward (centripetal) acceleration be zero?",
        "answer": "No. Going round a circle means the direction of travel is changing every "
                  "instant, and that change IS an acceleration. Something can have an "
                  "acceleration while its speed never changes.",
    }
    omega_is_not_v = {
        "misconception": "same turn rate means same speed",
        "question": f"Two markers sit on the same turning object, one near the centre and one "
                    f"out at {_g(r)} m. They complete a lap in the same time. Do they travel "
                    f"at the same speed along their circles?",
        "answer": "No. Same turn rate, different circles: the outer one covers a much longer "
                  "path in the same time, so it travels faster. Turn rate and speed are "
                  "different things.",
    }
    two_accelerations = {
        "misconception": "the inward acceleration is what speeds the object up or slows it down",
        "question": "This clip has an inward acceleration and, because the spin is changing, "
                    "an acceleration along the direction of travel. Which of the two changes "
                    "the object's SPEED, and which changes only its direction?",
        "answer": "The one along the direction of travel (a_t) changes the speed. The inward "
                  "one (a_c) changes only the direction — it is at right angles to the motion, "
                  "so it turns the object without making it faster or slower.",
    }
    out = {"basic": [tangent, steady_but_accelerating],
           "intermediate": [omega_is_not_v, steady_but_accelerating],
           "advanced": [two_accelerations]}
    if ctx["motion"] == "uniform":
        # a_t is zero here, so the two-accelerations item has nothing to point at.
        out["advanced"] = [steady_but_accelerating]
    return out


def _transfer(ctx):
    """One prompt that moves the same physics to a DIFFERENT setting.

    A single clip binds the concept to a single object: a learner who only ever meets circular
    motion on a turntable tends to file it under "turntables". Transfer needs a second context,
    and we have one video — so the second context is posed qualitatively, with no invented
    numbers, which is also what keeps it honest.
    """
    obj = ctx["obj"]
    return {
        "basic": [{
            "question": f"Everything you have just read about the {obj} is also true of a "
                        f"child sitting on a playground roundabout. Which part of the "
                        f"roundabout would give the child the fastest ride — near the middle, "
                        f"or out at the edge? Say why, in the words you have just learned.",
            "answer": "Out at the edge. Every part of the roundabout sweeps round at the same "
                      "rate, but the edge is on a bigger circle, so it covers more distance in "
                      "the same time.",
        }],
        "intermediate": [{
            "question": "A bicycle wheel turns at the same rate as this object, but its rim is "
                        "three times further from the centre. Compare the speed along the path "
                        "and the inward acceleration at the rim with the values you worked out "
                        "here.",
            "answer": "The speed is three times larger (v = ω·r, and only r changed). The "
                      "inward acceleration is also three times larger (a_c = ω²·r) — note it "
                      "is NOT nine times, because it is the turn rate that is squared, not the "
                      "radius.",
        }],
        "advanced": [{
            "question": "A satellite in a circular orbit sweeps round at the same rate for "
                        "years. Which of the methods you used here would still apply to it, "
                        "and which would fail — and what does that tell you about what this "
                        "measurement really rests on?",
            "answer": "The relations (a_c = ω²·r, T = 2π/ω) transfer unchanged: they are "
                      "geometry, and hold for any circular motion. What fails is the technique. "
                      "There is no object of known size beside it to set the real-world scale, "
                      "and no slowing-down stretch to fit a rate of change to. The physics is "
                      "general; the method depends on the scene.",
        }],
    }


def _placement(ctx):
    """A short self-check so the reader CHOOSES a level instead of being handed one.

    Three fixed reading levels with nobody deciding which one a given student gets is
    differentiated materials, not differentiated instruction. This does not diagnose anyone —
    it states what this level assumes and names the neighbouring level in both directions, so
    a reader who is in the wrong place can move.
    """
    assumes = {
        "basic": ["you have met the idea of a circle's radius",
                  "you can read a simple graph of one thing against time"],
        "intermediate": ["you can substitute numbers into a formula and keep the units straight",
                         "you can read a value off a graph at a given time",
                         "you know that squaring a number is not the same as doubling it"],
        "advanced": ["you can work with a rate of change (something per second, per second)",
                     "you can compare two moments of a motion and account for the difference",
                     "you are willing to argue about what a measurement does and does not show"],
    }
    neighbours = {
        "basic": (None, "intermediate"),
        "intermediate": ("basic", "advanced"),
        "advanced": ("intermediate", None),
    }
    out = {}
    for tier, items in assumes.items():
        down, up = neighbours[tier]
        note = []
        if down:
            note.append(f"If more than one of those is new to you, start with the {down} "
                        f"edition — it covers the same clip.")
        if up:
            note.append(f"If all of them are already easy, go straight to the {up} edition; "
                        f"this one will not stretch you.")
        out[tier] = {"assumes": items, "note": " ".join(note)}
    return out


def _claims_review(ctx):
    """WS-4 step C3 — "which claims does this video actually support?", as a TASK.

    The advanced level's distinguishing job is comparison and judgement, not intermediate with
    more numbers. So the honesty argument stops being a paragraph of vocabulary the reader is
    asked to absorb and becomes something to DO: each claim is graded well-supported / supported
    only under a stated assumption / not supported, and the verdicts print in the teacher copy
    only, exactly like the answer key. Every item is built from what this clip actually
    measured, so the list is never generic.
    """
    obj, r, T = ctx["obj"], ctx["r"], ctx["T"]
    items = []
    turn = ctx.get("turning_dur") or ctx.get("dur")
    if isinstance(ctx["f"], (int, float)) and isinstance(turn, (int, float)):
        items.append({
            "claim": f"“The {obj} went round about {round(_shown(ctx['f'], 2) * _shown(turn))} "
                     f"times while it was turning.”",
            "verdict": "Well supported",
            "why": "Counting laps is what the measurement does most directly: the swept angle "
                   "is accumulated frame by frame, and a miscount would have to lose a whole "
                   "revolution to matter.",
        })
    if isinstance(T, (int, float)):
        items.append({
            "claim": f"“Every lap took {_g(T)} s.”",
            "verdict": "Not supported as stated",
            "why": f"{_g(T)} s is the average lap over the whole clip. The turn rate is "
                   f"changing, so early laps and late laps take visibly different times; the "
                   f"average describes the spin as a whole, not any one lap.",
        })
    if ctx["unreliable"]:
        # Name a real instant from this clip's own timeline — "at t = 2 s" is nonsense on a
        # clip shorter than that, and the whole point of the task is that it is not generic.
        tl = ctx.get("tl") or []
        at = f"At t = {_g(tl[1]['t_s'])} s" if len(tl) > 1 else "At any single instant"
        items.append({
            "claim": f"“{at} the turn rate was exactly the value on the graph.”",
            "verdict": "Not supported",
            "why": "The circle is seen at a slant rather than face-on, so the value at any "
                   "single instant carries a once-per-turn wobble that is the viewing angle, "
                   "not the object. Only the trend across the clip is reliable.",
        })
    else:
        items.append({
            "claim": "“The turn rate fell at a perfectly steady rate.”",
            "verdict": "Supported only as a model",
            "why": "A steady rate of change is the simplest curve that fits the measured "
                   "angles well, and it is what every prediction here assumes. It is a good "
                   "description, not a fact the video establishes on its own.",
        })
    if ctx["motion"] == "decelerating" and not ctx.get("comes_to_rest"):
        items.append({
            "claim": f"“The {obj} came to a stop shortly after the clip ended.”",
            "verdict": "Supported only under a stated assumption",
            "why": "It rests entirely on the slow-down staying steady after the last frame we "
                   "have. Nothing in the video shows what happened next.",
        })
    if isinstance(r, (int, float)) and isinstance(ctx["px_per_m"], (int, float)):
        items.append({
            "claim": f"“The inward acceleration was {_g(ctx['a_c'])} m/s².”",
            "verdict": "Supported, but only as well as the scene was sized",
            "why": "Every value in metres rests on one measured real-world size in the scene. "
                   "The turn rate, the period and the frequency would survive an error there; "
                   "this number would not.",
        })
    return {"basic": [], "intermediate": [], "advanced": items}


def _teacher_notes(ctx):
    """Per-tier notes that print ONLY in the teacher copy (report.py renders these when
    ``with_answers``).

    Where an idea has a formal name or notation above the reading level of the worksheet, the
    student meets the idea in plain words and the exact statement lives here — so lowering the
    reading level does not cost the teacher the precision they need to field a question about
    it. This is re-routing, not deletion: nothing that was said before has been dropped.
    """
    out = {"basic": [], "intermediate": [], "advanced": []}
    om_c, a_c_mean, r = ctx["omega"], ctx["a_c"], ctx["r"]
    averaging = {
        "title": "The averaging caveat, formally",
        "tex": FORMULA_TEX["omega2_avg"],
        "body": ("The student edition says only that squaring an average is not the same as "
                 "averaging the squares. Formally this is Jensen's inequality applied to the "
                 "squaring function, which is convex: for any turn rate that varies, "
                 "⟨ω²⟩ ≥ ⟨ω⟩², with "
                 "equality only when ω is constant. That is why a_c built from the average of "
                 "ω² exceeds the a_c built from the square of the average ω, and why every "
                 "identity in the material is verified at a single instant instead."),
    }
    if all(isinstance(x, (int, float)) for x in (om_c, a_c_mean, r)):
        averaging["body"] += (f" Here: ⟨ω⟩²r = {_g(om_c*om_c*r)} m/s², against a measured "
                              f"⟨a_c⟩ = ⟨ω²⟩r of {_g(a_c_mean)} m/s².")
    out["intermediate"].append(averaging)
    out["advanced"].append(dict(averaging))
    px = ctx["px_per_m"]
    if isinstance(px, (int, float)):
        out["advanced"].append({
            "title": "Which quantities depend on the calibration",
            "body": (f"The scene is calibrated at {_g(px, 5)} pixels per metre, from a "
                     f"reference object of known size. ω, α, T and f are calibration-"
                     f"independent (scale-free): they are angles and times, so a wrong "
                     f"reference size leaves them untouched. r, v, a_c and a_t are all built "
                     f"through that scale, so a k% error in the reference length moves each of "
                     f"them by k%. The student edition states this in plain words and does not "
                     f"use the word 'calibration'."),
        })
    return out


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
        # Everything the reader sees is resolved ALONG THE DIRECTION OF TRAVEL: alpha is
        # d|omega|/dt (negative = slowing, whichever way round it turns), a_t carries that
        # same sign, and the endpoint omegas are speeds — so they agree with the unsigned
        # canonical omega the rest of the document quotes instead of contradicting it with
        # a stray "-9.51 -> -0.03 rad/s" beside a "clip average 5.7 rad/s".
        along = motion_along_travel(stats)
        mt = along.get("motion_type") or aa["motion_type"]
        aa_out = {
            "motion_type": mt,
            "alpha_rad_s2": along.get("alpha", aa.get("alpha_rad_s2")),
            "alpha_r2": aa.get("alpha_r2"),
            "omega_initial": along.get("omega_initial", aa.get("omega_initial")),
            "omega_final": along.get("omega_final", aa.get("omega_final")),
            "a_t_mean_m_s2": along.get("a_t", aa.get("a_t_mean_m_s2")),
            "impulsive_start": bool(aa.get("impulsive_start")),
            "relation": "alpha = d(omega)/dt ; a_t = alpha * r",
            "sign_note": SIGN_NOTE if mt in ("accelerating", "decelerating") else "",
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
            # Plain wording: this string is quoted straight into the writer's fact sheet, and a
            # fact sheet that says "scale-free" is how "scale-free" reached the student (8c).
            "caveat": "every value in metres (radius, speed, both accelerations) is only as "
                      "right as that reference size, and all of them are out by the same "
                      "proportion if it is wrong; the turn rate, angular acceleration, period "
                      "and frequency are angles and times, so they do not depend on it",
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
                "(mean omega)^2*r, because squaring an average is not the same as averaging "
                "the squares. To show a relation numerically, use a single timeline instant, "
                "where every identity closes exactly."),
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
        # Teacher-copy only (report.py renders these when with_answers): the formal statement
        # of anything the student edition now says in plain words.
        "teacher_notes": _teacher_notes(ctx),
        # WS-4: the three graded steps inside this level, the advanced step-3 judgement task,
        # and the bridge onto the first step of the next level.
        "tier_steps": TIER_STEPS,
        "claims_review": _claims_review(ctx),
        "tier_bridge": TIER_BRIDGE,
        # ── the reader DOES something, rather than only reads ──
        # A worksheet built from a video should stop before the reveal, confront what the
        # reader probably believes, and move the idea to a second setting — none of which a
        # passage of expository prose does on its own.
        "predict_first": _predict_first(ctx),
        "misconceptions": _misconceptions(ctx),
        "transfer": _transfer(ctx),
        "placement": _placement(ctx),
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
