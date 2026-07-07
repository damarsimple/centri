#!/usr/bin/env python3
"""Module D (live, difficulty-tiered): turn this job's material_seed.json into THREE
grounded learning passages — basic | intermediate | advanced — one Qwen call per tier
(an A3B model bleeds vocabulary between tiers if asked for all three at once).

Seeded pipeline step, run in the worker (cwd = workspace, 192.168.1.205:8083 reachable):

    python -m analysis.material_tiers

Reads  analysis_output/data/material_seed.json
Writes analysis_output/data/material.{basic,intermediate,advanced}.json
       analysis_output/data/material_tiers_gate.json   (the grounding-gate verdict)

Each tier is told exactly which seed fields it may use (the depth ladder) and which
figures it sits beside — the `figures` text MUST mirror TIER_ARTIFACTS in
render/report.py so "Reading the figures" only narrates plots that tier's PDF embeds.

GROUNDING GATE: every generated tier is run through deterministic checks (arithmetic
closure, tier compliance, motion-type faithfulness). A failing tier is regenerated once;
if it still fails the file is kept but flagged in material_tiers_gate.json (proceed-but-
flag, like the figure-verify phase — the pipeline never silently ships a bad number).
Implements docs/difficulty-tiered-material-spec.md.
"""
import json, os, re, sys, pathlib, urllib.request

from . import material_gate as G
from .common import dedup_display_name

DATA = pathlib.Path("analysis_output/data")
BASE = os.environ.get("PI_INFERENCE_URL", "http://192.168.1.205:8083") + "/v1/chat/completions"
KEY = os.environ.get("PI_INFERENCE_API_KEY", "hwanglabyoungdumbandbreak")
MODEL = os.environ.get("PI_MATERIAL_MODEL", "Qwen3.6-35B")


def _load_hints():
    """Subtle wording nuances distilled from real gate rejections, kept in an editable
    sidecar (`material_hints.md`) so they can be tuned without touching this template. The
    local 35B model self-corrects poorly on regen, so we steer the FIRST pass with these."""
    p = pathlib.Path(__file__).with_name("material_hints.md")
    try:
        txt = p.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    return ("NUANCES & HINTS (subtle wording guidance learned from prior runs — follow these; "
            "they prevent the most common automatic-gate rejections):\n" + txt + "\n") if txt else ""


HINTS = _load_hints()

SECTIONS = ["Scenario", "The variables we measured", "How the variables are related",
            "What the video shows over time", "Reading the figures"]

# Per-tier worked instants: indices into the seed's 4-point timeline. Distinct instants
# per tier stop advanced ≈ intermediate (both verifying at the same moment). Basic gets
# none (no numeric verification at all). Skipped entirely when the measurement is
# unreliable (oblique capture) or the timeline is empty. Consumed by the prompt AND by
# material_gate.cross_tier_issues (kept in sync with grade_material_grounding.TIER_ANCHORS).
TIER_ANCHORS = {"intermediate": [1], "advanced": [2, 0, 3]}

# Per-tier policy. `figures` MUST mirror TIER_ARTIFACTS in render/report.py.
TIERS = {
    "basic": {
        "bloom": "Remember / Understand",
        "interactivity": "low",
        "seed_fields": "object name, rotation direction, clip duration, the radius "
                       "(as 'how far out it sits'), the PERIOD as a plain number of seconds "
                       "('one full turn takes about T seconds'), the turn rate as a plain "
                       "TURNS-PER-SECOND count derived from the frequency ('it makes about "
                       "F full turns each second') — NEVER a bare 'per second' number with no "
                       "unit, and NEVER radians or rad/s, and angular velocity taught "
                       "as a LIVED IDEA (NOT a symbol): the object sweeps around by a growing "
                       "angle as time passes. Use ONLY the ANGLE-AT-TIME MILESTONES actually "
                       "supplied in the data to make this concrete and time-anchored (narrate "
                       "the exact milestone times you are given — do not invent your own '1 s "
                       "= a quarter turn' example, which may be wrong for a fast spin). In "
                       "'What the video shows over time', narrate those milestones as the "
                       "growing angle (this is what the coloured-dot picture shows). Plus the "
                       "IDEA of an inward pull; you may name 'centripetal acceleration' once, "
                       "in words.",
        "forbidden": "NO symbols (omega/alpha/v/a_c) and NO rad/s, NO equations or formula "
                     "derivations, NO numeric substitution beyond the radius, the duration, "
                     "the period in seconds, the turns-per-second count, and the qualitative "
                     "degrees-per-second sweep, and "
                     "NO rate-of-change VALUE for the turn rate (speeding up / slowing down is "
                     "described in plain words only, never as alpha or a computed rate). The "
                     "'How the variables are related' section MUST stay QUALITATIVE — explain "
                     "in words that a bigger circle or a faster sweep needs a stronger inward "
                     "pull; do NOT state a centripetal-acceleration or speed NUMBER there.",
        "figures": "Three pictures: (1) a frame from the video showing the object on its "
                   "circular path with the radius marked from the centre; (2) a picture of the "
                   "same path with COLOURED DOTS marking where the object is after 1, 2, 3... "
                   "seconds, each labelled with how far round it has swept (e.g. '1 s · 90° · a "
                   "quarter turn') — narrate this as the angle growing steadily with time; and "
                   "(3) a plot of the traced path showing every point falls on one circle. "
                   "There is NO data table and NO graph of speed or acceleration over time for "
                   "this reader — do not mention any table or any 'graph/plot of speed/"
                   "acceleration over time'.",
        "test": "Could a learner who has never seen the equations follow every sentence, "
                "holding one idea at a time?",
    },
    "intermediate": {
        "bloom": "Apply / Analyze",
        "interactivity": "moderate",
        "seed_fields": "the radius, angular velocity (omega), centripetal acceleration (a_c), "
                       "period (T), frequency (f) WITH their measured values and units, and the "
                       "relations a_c=omega^2*r and T=2*pi/omega=1/f. Present the relations in "
                       "an EXPLICIT, STRUCTURED way — name each quantity, state the relation, "
                       "then substitute this object's number (e.g. 'omega --(x r, then "
                       "squared)--> a_c') — so the reader sees HOW the variables are wired "
                       "together, shown to hold for THIS object. Tangential speed (v) is NOT a "
                       "headline variable at this tier: do NOT build on v=omega*r or a_c=v^2/r, "
                       "and do NOT list v as a measured variable; v may appear at most as a "
                       "one-clause aside if it truly aids intuition.",
        "forbidden": "Do NOT make the motion's change over time the main point (one sentence "
                     "of context is fine), NO angular-acceleration value or timeline, NO "
                     "scale/calibration-caveat discussion, NO tangential-speed derivation as a "
                     "core relation.",
        "figures": "An annotated frame with the radius, a short data table of the core "
                   "measurements (radius, angular velocity, centripetal acceleration, period, "
                   "frequency), one graph of the turn-rate (angular velocity) over time, and "
                   "the traced circular path. Do not mention tangential-speed graphs, "
                   "angular-acceleration graphs or a summary panel.",
        "test": "Does the passage coordinate a handful of interacting quantities through the "
                "standard relations, applied to this object's numbers?",
    },
    "advanced": {
        "bloom": "Analyze / Evaluate",
        "interactivity": "high",
        "seed_fields": "everything intermediate uses PLUS angular acceleration (alpha, "
                       "a_t=alpha*r), the spin-up/coast-down timeline (time evolution), the "
                       "squared sensitivity a_c proportional to omega^2, and the calibration "
                       "caveat (relative kinematics are scale-free; absolute a_c depends on "
                       "the reference size).",
        "forbidden": "Do not merely restate the intermediate content — the job here is the "
                     "higher-order integration over time and at limits. ELEMENT-INTERACTIVITY "
                     "FLOOR: you MUST wire together, each with this object's numbers at its "
                     "assigned instant, ALL of: a_c = ω²·r; T = 2π/ω = 1/f; α = dω/dt; "
                     "a_t = α·r; AND the squared sensitivity (a_c scales with ω², so a small "
                     "change in ω moves a_c much more). Restating the intermediate relation set "
                     "alone, without α, the time evolution, and the ω² sensitivity, is a "
                     "FAILURE at this tier.",
        "figures": "An annotated frame, the full measurements table (including angular "
                   "acceleration and the calibration), graphs of angular velocity and "
                   "centripetal acceleration over time, and the traced circular path. (There "
                   "is no combined summary panel — do not mention one.)",
        "test": "Does the passage integrate several quantities AND their change over time, and "
                "reason about proportionality, limits, or what the measurement does/doesn't pin down?",
    },
}


# ----------------------------------------------------------------------------- prompt
def _facts(seed, tier=None):
    # Use the plain object name (never the "<X> on <X>" composite scene title) for the
    # object fact — the authoritative title comes from the shared frame, not here.
    lines = [f"object: {seed.get('object_name') or seed.get('scene_title')}",
             f"rotation_direction: {seed.get('rotation_direction')}",
             f"clip_duration_s: {seed.get('active_duration_s')}", "measured variables:"]
    for v in seed.get("variables", []):
        val = v["value"]
        val = round(val, 3) if isinstance(val, (int, float)) else val
        lines.append(f"  - {v['name']} ({v['symbol']}) = {val} {v['unit']}  [{v['definition']}]")
    if seed.get("relations"):
        lines.append("formula relations (ground truth):")
        for r in seed["relations"]:
            lines.append(f"  - {r['formula']}   ({r['plain']})")
    aa = seed.get("angular_acceleration")
    if aa:
        lines.append(f"motion type: {aa['motion_type']} — {aa.get('plain','')}")
        lines.append(f"  alpha = {round(aa['alpha_rad_s2'],3)} rad/s^2 "
                     f"(fit R^2={round(aa['alpha_r2'],5)}), omega "
                     f"{round(aa['omega_initial'],2)} -> {round(aa['omega_final'],2)} rad/s, "
                     f"mean tangential accel a_t = {round(aa['a_t_mean_m_s2'],2)} m/s^2")
    else:
        lines.append("motion type: approximately uniform (no angular-acceleration block)")
    if seed.get("timeline"):
        lines.append("time-anchored samples (pipeline's own per-frame values):")
        for s in seed["timeline"]:
            lines.append(f"  - t={s['t_s']} s: omega={s['omega_rad_s']} rad/s, "
                         f"v={s['v_m_s']} m/s, a_c={s['a_c_m_s2']} m/s^2")
    cn = seed.get("consistency_note") or {}
    if cn:
        lines.append("consistency note: report radius as the fitted orbit radius r; verify "
                     "v=omega*r and a_c=omega^2*r at a SINGLE timeline instant, never with the "
                     "summary means (Jensen).")
    cal = seed.get("calibration_note", {})
    if cal:
        lines.append(f"calibration note: scale from a reference of "
                     f"{cal.get('reference_physical_size_m')} m; {cal.get('caveat')}")
    # Angle-at-time milestones are the BASIC tier's ground truth ("after 1.0 s it has
    # swept about 90°, a quarter turn"). Only the basic passage narrates them (and the
    # WS-3 angle figure sits beside it); higher tiers work from the timeline instead.
    if tier == "basic" and seed.get("angle_milestones"):
        lines.append("angle-at-time milestones (for the basic 'angle grows with time' story):")
        for ms in seed["angle_milestones"]:
            lines.append(f"  - after {ms['t_s']} s the object has swept about "
                         f"{ms['angle_deg']} degrees ({ms['turn']})")
    return "\n".join(lines)


SYSTEM_TMPL = (
    "You are a physics teacher writing a SHORT expository learning passage about circular "
    "motion, grounded strictly on ground-truth measurements from a real video. You write at "
    "ONE difficulty tier: {tier_upper}.\n\n"
    "Tier target — Bloom objective the passage equips: {bloom}; cognitive-load element "
    "interactivity: {interactivity}.\n"
    "Seed fields you MAY use at this tier: {seed_fields}\n"
    "Forbidden at this tier: {forbidden}\n"
    "Figures shown beside this passage: {figures}\n\n"
    "HARD RULES:\n"
    "1. Numbers come ONLY from the data below — never invent, extrapolate, or add a quantity "
    "not given; quote values with units; round prose to ~3 significant figures. Any quantity "
    "already measured and listed below (period T, frequency f, radius r, angular velocity ω, "
    "a_c) MUST be quoted EXACTLY as given — do NOT recompute or re-derive it from the others "
    "(e.g. never recompute T from 2π/ω or f from 1/T and state your own answer); if you show "
    "such a relation to explain it, the number you write MUST equal the given value to 3 "
    "significant figures. The SHARED "
    "LESSON FRAME story in the user message is provided ground truth for the Scenario section "
    "ONLY: retell that situation faithfully, never extend it, and never attach a number to it "
    "that is not in the data.\n"
    "2. This is exposition ONLY — no questions, quizzes, 'try this', or exercises.\n"
    "3. {motion_policy}\n"
    "4. If you show a relation numerically, verify it at a SINGLE timeline instant (where "
    "v=omega*r and a_c=omega^2*r close exactly), never with the summary means.\n"
    "5. 'Reading the figures' must describe ONLY the figures listed above for this tier — do "
    "not mention any plot or table that is not in that list.\n"
    "6. The element interactivity AND the Bloom objective must both point to {tier} — if they "
    "disagree, rewrite.\n"
    "7. WRITER'S TEST for this tier: {test}\n"
    "8. Teach the PHYSICS, not the measurement pipeline. This is a physics lesson about the "
    "object's motion, never a tracking/analysis report. Do NOT use any of these words: "
    + G.TRACKING_VOCAB_HUMAN + ". Never write a figure filename (e.g. omega_t.png). Refer to "
    "figures by what they SHOW: a plot is 'the graph of how the angle grows'; the still picture "
    "of the object is 'the labelled photo' or 'the picture of the object on its base' — NEVER "
    "'the annotated frame', 'the recorded frame', or 'the captured image' (those words are "
    "banned above). Speak about the object's motion, not how it was measured or filmed.\n"
    "8b. This is a KINEMATICS lesson — describe HOW the object moves (its angle, turn rate, "
    "inward acceleration), never WHY. Do NOT invoke any of these dynamics words: "
    + G.DYNAMICS_VOCAB_HUMAN + ". The inward effect is named ONLY as the 'centripetal "
    "acceleration' (you may call it an 'inward pull'); the speeding-up or slowing-down has NO "
    "named cause — never a motor, brake, friction, or force.\n"
    "9. Plain Unicode ONLY — never LaTeX or backslashes. PREFER the actual Unicode characters "
    "ω, α, π, ², · (not the spelled-out words 'omega'/'alpha'); write subscripts as plain "
    "ASCII a_c, a_t. NEVER emit $...$, \\omega, \\times, or any backslash: a stray backslash "
    "makes the JSON invalid and unparseable.\n"
    "{quality_policy}\n"
    "{anchor_policy}\n"
    "{hints}"
    "Return ONLY a JSON object (no markdown fences, no prose outside JSON) with keys: "
    "object_name, scene_title, tier, bloom_objective, element_interactivity, "
    "concepts_introduced (list of the seed symbols/relations this tier actually used), "
    "sections (an object with EXACTLY these five string keys, in order: "
    + ", ".join(f'\"{h}\"' for h in SECTIONS) + "), and tier_conflict (boolean). "
    "If the tier cannot be honestly reached for this seed, set tier_conflict true, explain in "
    "Scenario, and write the nearest honest tier."
)


def _call_qwen(system, user, temperature=0.4, max_tokens=24000):
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": temperature, "max_tokens": max_tokens,
        "chat_template_kwargs": {"enable_thinking": True},
    }).encode()
    req = urllib.request.Request(BASE, data=body, headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {KEY}"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        out = json.loads(resp.read())
    ch = out["choices"][0]
    content = ch["message"].get("content") or ""
    if ch.get("finish_reason") == "length":
        raise RuntimeError(f"truncated: raise max_tokens (got {len(content)} content chars)")
    return content


# A backslash that does NOT begin a valid JSON escape (" \ / b f n r t u...). RULE 9/12
# forbids LaTeX, but the 35B still occasionally slips one (\omega, \alpha, \cdot, \sqrt,
# \Delta, \le), and a single lone backslash makes json.loads raise and forces a full regen.
# Doubling those stray backslashes turns the escape into a literal backslash+char (which
# tex_escape then renders harmlessly), so a LaTeX slip degrades to a cosmetic blemish
# instead of losing the whole draft. Valid escapes (\n newlines, \" quotes, \uXXXX) are
# left untouched. First line of defence stays the prompt prohibition.
_BAD_JSON_ESCAPE = re.compile(r'\\(?![\"\\/bfnrtu])')


def _sanitize_json_escapes(s: str) -> str:
    return _BAD_JSON_ESCAPE.sub(r'\\\\', s)


def _parse_json(text):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.S)
    a, b = text.find("{"), text.rfind("}")
    if a == -1 or b == -1:
        raise ValueError(f"no JSON object in reply: {text[:200]!r}")
    blob = text[a:b + 1]
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        # A stray LaTeX backslash slipped through — repair the invalid escapes and retry once
        # rather than discarding an otherwise-good draft.
        return json.loads(_sanitize_json_escapes(blob))


# -------------------------------------------------------------- shared lesson frame
FRAME_SYSTEM = (
    "You are a physics teacher composing the SHARED opening story for a circular-motion "
    "lesson. This short story is the authentic, everyday CONTEXT that all three difficulty "
    "levels will open with: a real object moving in a circle, tied to a person and place, in "
    "plain human terms — the who, what, where, when, why and how.\n\n"
    "HARD RULES:\n"
    "1. Ground the scene in the REAL object named below, and when a setting is given (what "
    "the object is part of or mounted on), set the story THERE. Do NOT rename the object to a "
    "generic 'turntable' or 'rotating system', and do NOT invent a surface — a table, a wooden "
    "board, a desk — that the given setting does not mention: if it sits on a bicycle tire it "
    "sits on a bicycle tire, and if it is a fan blade it is a fan blade.\n"
    "2. If a learner's note is given, it is AUTHORITATIVE: build the story around it and never "
    "contradict it (the who/where/why come from the note). If NO note is given, write in the "
    "SECOND PERSON and invent NO proper names, NO places, NO people — a wrong invented name "
    "('Irfan at the night market') is worse than none. To START the motion, say you give it "
    "'a spin' / 'a twist' / 'a flick' / 'a nudge' — NEVER 'a push', 'a shove', or any word "
    "naming a force (this is a kinematics story, so the cause is never named).\n"
    "3. Tell a SHORT, warm, concrete story of 3–5 sentences: who is doing what with this "
    "object, where, and why it ends up going round in a circle. Not a lab report.\n"
    "3b. If a 'how the motion changes' fact is given (slowing down / speeding up), let the "
    "story gently show it — a wheel that is coasting and winding down, a fan spinning up. Do "
    "NOT call such a motion 'steady', 'smooth and uninterrupted', 'unchanging', or say it "
    "'holds that pace/path' — that contradicts the data. Only a genuinely constant-rate clip "
    "may be described as steady.\n"
    "4. The ONLY numbers you may mention are: the clip length in seconds, how far out the "
    "object sits (radius, in plain words), and how long one full turn takes. Mention no other "
    "quantity, symbol, equation, or measurement.\n"
    "5. NEVER mention filming, video, tracking, cameras, measurement, analysis, or a pipeline "
    "— write the scene ITSELF, as if you stood there watching it.\n"
    "6. Plain Unicode only — no LaTeX, no backslashes.\n"
    "Return ONLY a JSON object: {\"scene_title\": \"...\", \"scenario_story\": \"...\", "
    "\"who\": \"...\", \"where\": \"...\"}. scene_title is a short human title naming the real "
    "object in Title Case (never '<X> on <X>'). who/where name the person and place ONLY if "
    "the note supplies them, else the empty string \"\"."
)


def _frame_user(seed) -> str:
    nc = seed.get("narrative_context") or {}
    radius = next((v.get("value") for v in seed.get("variables", [])
                   if v.get("symbol") == "r"), None)
    period = next((v.get("value") for v in seed.get("variables", [])
                   if v.get("symbol") == "T"), None)
    obj = (seed.get("object_name") or "").strip()
    # The tracked object's setting (what it is mounted on / part of) lives in scene_title,
    # formatted "<tracked> on <reference>". object_name alone drops it, which lets the model
    # invent a generic surface (e.g. a "wooden board" for a marker on a bicycle tire). Surface
    # the reference explicitly, unless it just repeats the object ("fan blade on fan blade").
    scene = (seed.get("scene_title") or "").strip()
    mounted_on = None
    if " on " in scene:
        ref = scene.split(" on ", 1)[1].strip()
        if ref and ref.lower() not in (obj.lower(), (seed.get("tracked_label") or "").strip().lower()):
            mounted_on = ref
    bits = [f"object: {obj}"]
    if mounted_on:
        bits.append(f"what it is part of / mounted on (the REAL setting — build the scene on "
                    f"this; never swap it for a generic table, board, or turntable): {mounted_on}")
    bits += [f"rotation direction: {seed.get('rotation_direction')}",
             f"clip length: {seed.get('active_duration_s')} s"]
    # The frame must know if the spin is winding down / up, so the opening story doesn't
    # call a decelerating motion "steady" or "smooth and uninterrupted" (A1).
    aa = seed.get("angular_acceleration") or {}
    mt = aa.get("motion_type", "uniform")
    if mt == "decelerating":
        if aa.get("impulsive_start"):
            bits.append("how the motion goes: the object sits STILL, then a single flick sends "
                        "it spinning; it reaches its fastest right after the flick and then "
                        "coasts down"
                        + (", winding to a stop before the clip ends"
                           if seed.get("comes_to_rest") else ", still turning when the clip ends"))
        else:
            bits.append("how the motion changes: it is gradually SLOWING DOWN over the clip"
                        + ("" if seed.get("comes_to_rest") else
                           " (and is still turning, just slower, when the clip ends — it does "
                           "not fully stop)"))
    elif mt == "accelerating":
        bits.append("how the motion changes: it is gradually SPEEDING UP over the clip")
    if isinstance(radius, (int, float)):
        # Round to match the value the tier bodies quote from the seed's `r` variable
        # (3 decimals), so the story and the physics never disagree (0.08 vs 0.075).
        bits.append(f"how far out it sits (radius): about {round(radius, 3)} m")
    if isinstance(period, (int, float)):
        bits.append(f"one full turn takes: about {round(period, 2)} s")
    if nc.get("user_text"):
        bits.append("LEARNER'S NOTE (authoritative — build the story around this):\n  "
                    + nc["user_text"])
    elif nc.get("vlm_hint"):
        bits.append("advisory scene hint (use loosely, invent no proper nouns):\n  "
                    + nc["vlm_hint"])
    return ("Facts for the shared story:\n" + "\n".join(bits) +
            "\n\nWrite the shared opening story now as JSON.")


def _frame_fallback(seed) -> dict:
    """Deterministic frame when the LLM call fails or won't parse — second person, no
    invented proper nouns, no numbers beyond the ones already in the seed's prose fields."""
    obj = seed.get("object_name") or "the object"
    title = (seed.get("scene_title") or obj or "Circular Motion").strip()
    mt = (seed.get("angular_acceleration") or {}).get("motion_type", "uniform")
    # Motion-aware so the fallback never calls a slowing/speeding clip "steady" (A1).
    if mt == "decelerating":
        change = ("Little by little it loses speed, coasting slower and slower but still going "
                  "round" + (" until it winds to a stop." if seed.get("comes_to_rest")
                             else ", and it is still turning when the clip ends."))
    elif mt == "accelerating":
        change = "Turn by turn it picks up speed, sweeping round faster and faster."
    else:
        change = "It settles into a steady loop, coming back around to the same spot again and again."
    story = (f"You set {obj} spinning and watch it trace the same circle over and over. "
             f"{change} Each point it passes marks out one smooth circle — a clear, everyday "
             f"example of something moving in a circle.")
    return {"scene_title": title, "scenario_story": story, "who": "", "where": ""}


def _generate_frame(seed) -> dict:
    """One shared narrative frame per job (5W+1H story + authoritative scene title). Built
    from the authentic object name and any learner/VLM context, so the three tiers can no
    longer each invent a generic 'Decelerating Circular Motion on a Turntable' title. Any
    failure (network, parse) falls back to a deterministic second-person template."""
    try:
        frame = _parse_json(_call_qwen(FRAME_SYSTEM, _frame_user(seed), temperature=0.7))
        title = dedup_display_name(frame.get("scene_title")) or (seed.get("scene_title") or "")
        story = (frame.get("scenario_story") or "").strip()
        if not story:
            raise ValueError("empty scenario_story")
        return {"scene_title": title, "scenario_story": story,
                "who": (frame.get("who") or "").strip(),
                "where": (frame.get("where") or "").strip()}
    except Exception as e:  # noqa: BLE001 — proceed-but-flag; never block the pipeline
        print(f"   frame generation failed ({e}); using deterministic fallback", flush=True)
        return _frame_fallback(seed)


def _anchor_policy(tier, seed) -> str:
    """Per-tier worked-instant instruction from TIER_ANCHORS. Empty for basic, when the
    timeline is missing, or when the measurement is unreliable (no per-instant claims)."""
    mq = seed.get("measurement_quality") or {}
    if mq and not mq.get("reliable", True):
        return ""
    tl = seed.get("timeline") or []
    idxs = TIER_ANCHORS.get(tier, [])
    if not tl or not idxs:
        return ""
    ts = [tl[i]["t_s"] for i in idxs if 0 <= i < len(tl)]
    if not ts:
        return ""
    if tier == "intermediate":
        return (f"11. WORKED INSTANT: verify your numeric relation ONLY at t = {ts[0]} s "
                "(use that timeline row's values); do not work any other instant.")
    if tier == "advanced":
        others = ", ".join(f"t = {t} s" for t in ts[1:])
        forbid = tl[TIER_ANCHORS["intermediate"][0]]["t_s"] if TIER_ANCHORS.get("intermediate") else None
        clause = (f"11. WORKED INSTANTS: anchor your main calculation at t = {ts[0]} s, and "
                  f"contrast the earlier vs later moments {others} to show the time evolution")
        if forbid is not None:
            clause += f"; do NOT reuse the intermediate tier's instant (t = {forbid} s)"
        return clause + "."
    return ""


# ----------------------------------------------------------------------------- main
def _quality_policy(seed) -> str:
    """Hedging clause when per-instant omega is unreliable (oblique-capture artifact).
    Empty string when the measurement is reliable — normal narration."""
    mq = seed.get("measurement_quality") or {}
    if not mq or mq.get("reliable", True):
        return ""
    return (
        "10. MEASUREMENT-QUALITY OVERRIDE (this clip, overrides any 'narrate the timeline / "
        "turn-rate over time' instruction above): " + (mq.get("guidance") or "") +
        " You MUST NOT narrate the timeline, quote any per-instant angular-velocity value, "
        "describe the detailed shape of the omega(t) curve, or claim the object speeds up/slows "
        "down WITHIN a revolution. You MAY still state the OVERALL qualitative trend across the "
        "WHOLE clip — if the motion type is accelerating/decelerating, say plainly that it "
        "gradually speeds up / slows down over the clip (that whole-clip trend is robust; only "
        "the per-instant and per-revolution detail is unreliable). Any numbers you cite (ONLY "
        "quantities your tier already permits — introduce no new ones) must be time-AVERAGE "
        "values; do NOT numerically verify a_c = omega^2*r or v = omega*r for this clip (that "
        "needs a reliable per-instant value) — present those relations structurally and label "
        "the values as clip averages, without asserting the identity closes to an exact number. "
        "In 'What the video shows over time' and 'Reading the figures', include ONE plain "
        "sentence that the "
        "per-instant angular velocity is not reliably recoverable because the orbit was filmed "
        "at an oblique angle, and describe any time graph only at that level — never reading its "
        "wiggles as real physics."
    )


def _motion_policy(seed) -> str:
    """RULE 3 body, tuned to the real motion type AND whether the object actually comes to
    rest within the clip (seed.comes_to_rest). Fixes A1 ('steady' on a slowing clip) and A7
    ('slows to rest' when it never stops in the clip)."""
    aa = seed.get("angular_acceleration") or {}
    mt = aa.get("motion_type", "uniform")
    impulsive = aa.get("impulsive_start")
    if mt == "accelerating":
        return ("Motion-type faithfulness: this motion is SPEEDING UP — convey it "
                "qualitatively at THIS tier ('whirls faster and faster', 'gains speed as it "
                "goes'). NEVER call the motion steady, uniform, smooth-and-unchanging, or "
                "constant-speed. The alpha value + timeline are reserved for the advanced tier.")
    if mt == "decelerating":
        # A flick: object starts at rest, is nudged up to its fastest, then coasts down. The
        # generator must NOT narrate it as already spinning fast from the first frame.
        lead = ("The object begins AT REST; it is given a single flick, briefly reaches its "
                "fastest spin, and then coasts down — do NOT describe it as already spinning "
                "quickly from the first moment, and note it is motionless before the flick. "
                if impulsive else "")
        end = ("it loses spin and gradually slows to a stop within the clip"
               if seed.get("comes_to_rest") else
               "it loses spin and keeps slowing — still turning, only more slowly, when the "
               "clip ends. Do NOT say it stops, halts, or comes to rest: it has not stopped "
               "by the end of the clip")
        return ("Motion-type faithfulness: " + lead + "this motion is SLOWING DOWN — say so "
                f"plainly at THIS tier: {end}. NEVER call the motion steady, uniform, smooth-"
                "and-unchanging, or constant-speed, and do NOT hedge it as 'does not speed up "
                "or slow down'. The alpha value + timeline are reserved for the advanced tier.")
    return ("Motion-type faithfulness: this clip turns at an approximately CONSTANT rate — it "
            "is fine to describe the motion as steady/uniform. Do not invent a speed-up or "
            "slow-down that the data does not show.")


def _frame_block(frame) -> str:
    """The SHARED LESSON FRAME appended to every tier's user message."""
    return (
        "\n\nSHARED LESSON FRAME (authoritative — the Scenario section MUST open by retelling "
        "this story, adapted to this reading level. Any people or places in the story may "
        "appear ONLY in Scenario, NEVER in any other section. Retell it, do not extend it, and "
        "attach no number to it that is not in the data above):\n"
        f"  Scene title: {frame.get('scene_title')}\n"
        f"  Story: {frame.get('scenario_story')}")


def _generate(tier, facts, seed, frame, prior_issues=None):
    spec = TIERS[tier]
    quality_policy = _quality_policy(seed)
    anchor_policy = _anchor_policy(tier, seed)
    if quality_policy:
        # Don't hand the model a per-instant timeline it must not use — remove the
        # temptation entirely when the measurement is flagged unreliable.
        facts = re.sub(r"time-anchored samples.*", "", facts, flags=re.S)
    system = SYSTEM_TMPL.format(tier=tier, tier_upper=tier.upper(),
                                quality_policy=quality_policy,
                                anchor_policy=anchor_policy, hints=HINTS,
                                motion_policy=_motion_policy(seed), **spec)
    # Failure-informed regeneration: a blind re-roll at temperature 0.4 rarely clears the
    # same fault, so on a retry we hand the model the EXACT gate failures to fix. Each issue
    # already names the offending phrase/number, which is enough for a targeted rewrite.
    revision = ""
    if prior_issues:
        revision = ("\n\nYour PREVIOUS draft was rejected by the automatic checker for these "
                    "specific problems — rewrite the passage so EVERY one is fixed, and change "
                    "nothing else that was already correct:\n"
                    + "\n".join(f"  - {i}" for i in prior_issues))
    user = ("Ground-truth measurements for this clip:\n\n" + facts + _frame_block(frame) +
            revision +
            f"\n\nWrite the {tier.upper()} passage now, following every rule and using "
            "the exact five section headers as JSON keys.")
    obj = _parse_json(_call_qwen(system, user))
    # Hard-overwrite the identity fields (same pattern as the tier label below): the frame
    # holds the ONE authoritative title, so a tier can never invent its own generic one.
    obj["scene_title"] = frame.get("scene_title") or seed.get("scene_title")
    obj["object_name"] = seed.get("object_name")
    obj["tier"] = tier              # trust our request over the model's self-label
    obj["difficulty_level"] = tier  # user-facing name (WS-4); machine key stays `tier`
    return obj


def _implicated_tiers(cross_issues):
    """Which tier(s) a cross-tier issue points at (for the one targeted cross-tier regen)."""
    out = []
    for s in cross_issues:
        names = re.findall(r"\b(basic|intermediate|advanced)\b", s)
        if "!<" in s and len(names) >= 2:
            names = [names[1]]        # EI monotonicity: fix the tier that's too low
        for n in names:
            if n not in out:
                out.append(n)
    return out


def main():
    seed_p = DATA / "material_seed.json"
    if not seed_p.exists():
        sys.exit(f"!! no seed at {seed_p} (run analysis.run first)")
    seed = json.loads(seed_p.read_text())
    unreliable = not (seed.get("measurement_quality") or {}).get("reliable", True)

    print(".. generating shared lesson frame (Qwen) ...", flush=True)
    frame = _generate_frame(seed)
    print(f"   frame: scene_title={frame['scene_title']!r} "
          f"(who={frame['who']!r}, where={frame['where']!r})", flush=True)

    materials, gate_report, cross_regen_used = {}, {}, {}
    for tier in TIERS:
        facts = _facts(seed, tier)  # basic gets the angle milestones; others don't
        print(f".. generating {tier} (Qwen) ...", flush=True)
        obj = _generate(tier, facts, seed, frame)
        issues = G.tier_gate(obj, seed, frame)
        # Failure-informed best-of-N: re-roll up to twice feeding the EXACT current faults,
        # and keep a re-roll only when it has STRICTLY fewer issues. A single regen at temp
        # 0.4 often trades one violation for another ('recorded' -> 'pushes'); rejecting the
        # lateral trade and re-rolling against the same fault converges far more reliably.
        attempt = 0
        while issues and attempt < 2:
            attempt += 1
            print(f"   gate FAILED ({len(issues)}): {issues}; regen {attempt}/2 ...", flush=True)
            cand = _generate(tier, facts, seed, frame, prior_issues=issues)
            cand_issues = G.tier_gate(cand, seed, frame)
            if len(cand_issues) < len(issues):
                obj, issues = cand, cand_issues
        materials[tier] = obj
        gate_report[tier] = {"passed": not issues, "issues": issues}
        cross_regen_used[tier] = False

    # Cross-tier pass: titles equal, distinct worked instants, element interactivity rising.
    # This has its OWN regen budget (separate from the per-tier best-of-N above) so a tier
    # can still be fixed for a missing worked instant after spending its per-tier retries.
    cross = G.cross_tier_issues(materials, seed, TIER_ANCHORS, unreliable=unreliable)
    if cross:
        print(f"   cross-tier issues: {cross}", flush=True)
        for tier in _implicated_tiers(cross):
            if tier in TIERS and not cross_regen_used.get(tier):
                print(f"   regenerating {tier} once for cross-tier fit ...", flush=True)
                # Feed BOTH the cross-tier fault AND any residual per-tier issue, so the
                # re-roll fixes the instant without reintroducing a vocab/grounding leak.
                prior = [c for c in cross if tier in c] + gate_report[tier]["issues"]
                cand = _generate(tier, _facts(seed, tier), seed, frame, prior_issues=prior)
                cand_issues = G.tier_gate(cand, seed, frame)
                cross_regen_used[tier] = True
                if len(cand_issues) <= len(gate_report[tier]["issues"]):
                    materials[tier] = cand
                    gate_report[tier] = {"passed": not cand_issues, "issues": cand_issues}
        cross = G.cross_tier_issues(materials, seed, TIER_ANCHORS, unreliable=unreliable)

    for tier, obj in materials.items():
        out_p = DATA / f"material.{tier}.json"
        out_p.write_text(json.dumps(obj, indent=2, ensure_ascii=False))
        passed = gate_report[tier]["passed"]
        secs = obj.get("sections", {})
        miss = [h for h in SECTIONS if h not in secs]
        flag = "OK" if passed else "FLAGGED"
        print(f"{flag} {out_p.name}: {len(secs)} sections, "
              f"bloom={obj.get('bloom_objective')}, ei={obj.get('element_interactivity')}"
              + (f", MISSING {miss}" if miss else "")
              + ("" if passed else f"  << gate: {gate_report[tier]['issues']}"))

    # Seed self-consistency: the DETERMINISTIC blocks (worked examples/CYU) and the summary
    # table, verified independently of the LLM prose. This is the check that would have caught
    # the red-phone alpha example (-4.07 from an expression equal to -1.34) and the mixed-omega
    # table (v != omega*r, T != 2pi/omega). Proceed-but-flag like the per-tier gate.
    seed_consistency = G.seed_consistency_issues(seed)
    if seed_consistency:
        print(f"   seed consistency issues: {seed_consistency}", flush=True)

    all_ok = (all(g["passed"] for g in gate_report.values())
              and not cross and not seed_consistency)
    (DATA / "material_tiers_gate.json").write_text(json.dumps({
        "all_passed": all_ok,
        "frame": frame,
        "tiers": gate_report,
        "cross_tier": {"passed": not cross, "issues": cross},
        "seed_consistency": {"passed": not seed_consistency, "issues": seed_consistency},
    }, indent=2, ensure_ascii=False))
    print(f"\nMATERIAL TIERS {'OK' if all_ok else 'COMPLETED WITH FLAGS'} — "
          f"3 tiers written; gate -> material_tiers_gate.json"
          + ("" if not cross else f"  << cross-tier: {cross}")
          + ("" if not seed_consistency else f"  << seed-consistency: {seed_consistency}"))
    return 0  # proceed-but-flag: never hard-block the pipeline on prose


if __name__ == "__main__":
    raise SystemExit(main())
