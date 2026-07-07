#!/usr/bin/env python3
"""Single source of truth for the material grounding gate — deterministic, no model.

This module is the ONE place the material checks live. It ships into every workspace
(``app/workspace.py seed_pipeline()`` copies the whole ``analysis/`` dir), so the LIVE
gate in ``material_tiers.py`` and the repo verifier ``tools/grade_material_grounding.py``
run the *same* code — the two used to drift (e.g. the intermediate ``v=omega*r``
requirement lived in one and not the other). Repo tools bootstrap onto it with::

    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / "workspace_lib"))
    from analysis import material_gate

What it checks, objectively, against the measured ground truth (the seed) and the prose
itself:

  1. ARITHMETIC CLOSURE   — every explicit numeric claim must actually compute.
  2. NUMBER GROUNDING     — every physics-like number must trace to a seed value.
  3. TIER COMPLIANCE      — basic: no equations/symbols; intermediate: the structured
                            a_c = omega^2 * r relation; advanced: alpha + a timeline instant.
  4. MOTION FAITHFULNESS  — an accelerating/decelerating clip is never called steady.
  5. VOCABULARY           — no tracking/pipeline words (rule 8) and no dynamics words
                            (rule 8b: this is a KINEMATICS lesson — no force/energy/mass...).
  6. STORY FENCE          — the shared frame's who/where may appear ONLY in Scenario.
  7. CROSS-TIER           — titles equal; per-tier worked instants distinct; element
                            interactivity rises basic < intermediate < advanced.

Rules 5/6/7 are new (the tracking-vocab, kinematics-only, and cross-tier checks). The
TRACKING_VOCAB / DYNAMICS_VOCAB constants are also consumed by ``material_tiers.py`` to
render HARD RULE 8 / 8b, so the prompt and the check cannot drift.
"""
import re

# ---- normalization -----------------------------------------------------------
_SYM = {"×": " * ", "·": " * ", "✕": " * ", "÷": " / ", "≈": " ~= ", "²": "^2 ",
        "³": "^3 ", "π": " pi ", "−": "-", "—": "-", "’": "'", "“": '"', "”": '"'}


def norm(s: str) -> str:
    for k, v in _SYM.items():
        s = s.replace(k, v)
    return s


NUM = r"[-+]?\d+(?:\.\d+)?"
SEP = r"[^0-9]{0,22}?"           # units / words allowed between tokens (bounded, lazy)
EQ = (r"(?:=|~=|yields?|gives?|equals?|matches|to(?: roughly| about| approximately)?|"
      r"is(?: roughly| about| approximately)?|resulting in|producing)")
APPROX = r"(?:roughly|about|approximately|~|nearly)?"


def _f(x):
    return float(x)


# ---- (1) arithmetic closure --------------------------------------------------
def _neutralize_units(t: str) -> str:
    """Stop unit slashes (rad/s, m/s, m/s^2) from looking like numeric division."""
    t = re.sub(r"(rad|km|cm|mm|deg|m)\s*/\s*s(\s*\^?\s*2)?", r"\1_s", t)
    t = re.sub(r"(?<=[a-zA-Z])\s*/\s*s\b", "_s", t)
    return t


def arithmetic_claims(text: str, rel_tol=0.02):
    """Find explicit ``A op B (op ...) eq C`` numeric claims and check they compute."""
    t = _neutralize_units(norm(text))
    claims = []

    def check(expr, lhs, rhs):
        if rhs == 0:
            ok = abs(lhs) < 1e-9
        else:
            ok = abs(lhs - rhs) / max(abs(rhs), 1e-9) <= rel_tol
        claims.append({"claim": expr.strip(), "computed": round(lhs, 4),
                       "stated": rhs, "ok": ok})

    MUL = r"(?:\*|times|multiplied by)"
    DIV = r"(?:/|divided by)"
    NOPRE = r"(?<![\^\d.])"          # don't start an operand on the '2' of '^2' or mid-number
    # the result must TERMINATE the equation, not be a restated intermediate that a fuller
    # worked solution continues with another operator, e.g. "A^2 * B = <A^2> * B = C": the
    # first "<A^2>" is an intermediate, not the product of A^2*B. Reject a result that is
    # immediately followed by another arithmetic operator (chained-equation guard). The
    # (?![.\d]) also blocks the engine from backtracking the result NUM to a partial number
    # (e.g. shrinking 57.9 -> 57) just to dodge the operator lookahead.
    NOCONT = r"(?![.\d])(?!\s*(?:\*|/|times|multiplied by|divided by))"
    # squared forms FIRST (unit/paren may sit between the number and ^2):
    for m in re.finditer(rf"{NOPRE}({NUM}){SEP}\^2{SEP}{MUL}{SEP}({NUM}){SEP}{EQ}\s*{APPROX}\s*({NUM}){NOCONT}", t):
        a, b, c = map(_f, m.groups()); check(m.group(0), a*a*b, c)
    for m in re.finditer(rf"{NOPRE}({NUM}){SEP}\^2{SEP}{DIV}{SEP}({NUM}){SEP}{EQ}\s*{APPROX}\s*({NUM}){NOCONT}", t):
        a, b, c = map(_f, m.groups())
        if b != 0: check(m.group(0), a*a/b, c)
    # 2*pi / B eq C  (period; BEFORE generic division so pi isn't dropped)
    for m in re.finditer(rf"2\s*\*?\s*pi\s*(?:/|divided by|by)\s*({NUM}){SEP}{EQ}\s*{APPROX}\s*({NUM}){NOCONT}", t):
        a, c = map(_f, m.groups())
        if a != 0: check("2pi / "+m.group(1)+" = "+m.group(2), 6.283185307/a, c)
    # plain product:  A * B eq C   (skip squared/pi spans)
    for m in re.finditer(rf"{NOPRE}({NUM}){SEP}{MUL}{SEP}({NUM}){SEP}{EQ}\s*{APPROX}\s*({NUM}){NOCONT}", t):
        if "^2" in m.group(0) or "pi" in m.group(0):
            continue
        a, b, c = map(_f, m.groups()); check(m.group(0), a*b, c)
    # division / reciprocal:  A / B eq C   (skip squared/pi spans)
    for m in re.finditer(rf"{NOPRE}({NUM}){SEP}{DIV}{SEP}({NUM}){SEP}{EQ}\s*{APPROX}\s*({NUM}){NOCONT}", t):
        if "^2" in m.group(0) or "pi" in m.group(0):
            continue
        a, b, c = map(_f, m.groups())
        if b != 0: check(m.group(0), a/b, c)
    # dedupe by claim text
    seen, out = set(), []
    for c in claims:
        if c["claim"] not in seen:
            seen.add(c["claim"]); out.append(c)
    return out


# ---- (2) number grounding ----------------------------------------------------
def allowed_values(seed: dict):
    vals = set()

    def add(x):
        try:
            x = float(x)
        except (TypeError, ValueError):
            return
        vals.add(abs(x))
    for v in seed.get("variables", []):
        add(v.get("value"))
    for tl in seed.get("timeline", []):
        for k in ("t_s", "omega_rad_s", "v_m_s", "a_c_m_s2"):
            add(tl.get(k))
        om = tl.get("omega_rad_s")
        if isinstance(om, (int, float)):
            add(om * om)   # ω² — the sanctioned intermediate step of a_c = ω²·r at that instant
    aa = seed.get("angular_acceleration") or {}
    for k in ("alpha_rad_s2", "omega_initial", "omega_final", "a_t_mean_m_s2"):
        add(aa.get(k))
    # WS-3: the basic-tier angle milestones the prose is allowed to narrate
    # ("about a quarter turn, ~90 degrees, after 1.0 s").
    for ms in seed.get("angle_milestones", []):
        add(ms.get("t_s"))
        add(ms.get("angle_deg"))
    add(seed.get("active_duration_s")); add(seed.get("measured_radius_m"))
    cn = seed.get("calibration_note") or {}
    add(cn.get("px_per_m")); add(cn.get("reference_physical_size_m"))
    # simple derived: 2pi/omega, 1/f, alpha*r, omega^2*r, omega*r per variable pairs
    byk = {v["symbol"]: v.get("value") for v in seed.get("variables", []) if v.get("value") is not None}
    if "omega" in byk and byk["omega"]:
        add(6.283185307 / byk["omega"])
    if "f" in byk and byk["f"]:
        add(1 / byk["f"])
    if "omega" in byk and byk["omega"]:
        add(byk["omega"]**2)        # mean ω² (same sanctioned intermediate, mean instant)
    if "r" in byk and "omega" in byk:
        add(byk["omega"] * byk["r"]); add(byk["omega"]**2 * byk["r"])
    # Sanction the richer advanced derivations a strong model produces from GROUNDED omegas,
    # so they read as derived (not fabricated): T=2pi/omega and f=omega/2pi at ANY grounded
    # instant (not just the mean), and the a_c ~ omega^2 SCALING between two instants
    # ("omega drops by k -> a_c drops by k^2"): the omega-ratio k and its square k^2.
    omegas = [tl.get("omega_rad_s") for tl in seed.get("timeline", [])]
    omegas += [byk.get("omega")] + [aa.get("omega_initial"), aa.get("omega_final")]
    omegas = [abs(float(o)) for o in omegas if isinstance(o, (int, float)) and o]
    for om in omegas:
        add(6.283185307 / om)      # T = 2pi/omega at that instant
        add(om / 6.283185307)      # f = omega/2pi at that instant
    for oi in omegas:
        for oj in omegas:
            if oj:
                ratio = oi / oj
                # only sanction a MEANINGFUL scaling (a real drop/rise between two
                # instants). Ratios of near-equal omegas cluster around 1.0 and would
                # otherwise ground any ~1.0 statistic (e.g. a fabricated R^2 = 0.99976).
                if abs(ratio - 1.0) > 0.05:
                    add(ratio); add(ratio * ratio)   # omega-ratio k and a_c-ratio k^2
    return vals


def grounded(x, allowed, rel_tol=0.02, abs_tol=0.01):
    ax = abs(x)
    return any(abs(ax - a) <= max(abs_tol, rel_tol * max(a, 1e-9)) for a in allowed)


# small structural integers that are never "data" (counts, 2 in 2pi, 360 deg, percentages)
_WHITELIST = set(range(0, 13)) | {360, 180, 90, 100}


def ungrounded_numbers(text: str, allowed):
    t = norm(text)
    bad = []
    for m in re.finditer(rf"(?<![\w.]){NUM}(?![\w])", t):
        x = float(m.group(0))
        if x == int(x) and int(abs(x)) in _WHITELIST:
            continue
        if "." not in m.group(0) and abs(x) < 1000:   # bare small ints: likely counts/ratios
            continue
        if not grounded(x, allowed):
            ctx = t[max(0, m.start()-25):m.end()+15].replace("\n", " ")
            bad.append({"value": x, "context": "…"+ctx.strip()+"…"})
    return bad


# ---- (3) tier compliance -----------------------------------------------------
def tier_compliance(tier, text, unreliable=False):
    """basic: no equations/symbols. intermediate: the STRUCTURED a_c = omega^2 * r
    relation (v=omega*r is intentionally NOT required — v is de-emphasised at this
    tier per the spec). advanced: alpha + an explicit timeline instant.

    ``unreliable`` (oblique-capture clip): the advanced tier cannot cite alpha or a
    per-instant timeline value, so those two requirements are dropped — enforcing them
    would penalise the correct hedging the quality policy demands."""
    issues = []
    t = text
    if tier == "basic":
        hits = [s for s in [r"=", r"\^2", r"²", r"ω", r"\bomega\b", r"α", r"\balpha\b",
                            r"v\s*=", r"a_c", r"rad/s"] if re.search(s, t)]
        if hits:
            issues.append(f"basic tier contains equation/symbol markers: {hits}")
    if tier == "intermediate":
        nt = norm(t)
        has_ac_relation = (
            (bool(re.search(r"a_?c\s*=", nt)) and bool(re.search(r"(?:omega|ω)\s*\^2", nt)))
            or bool(re.search(r"(?:omega|ω)\s*\^2\s*\*?\s*r\b", nt))
            or bool(re.search(r"centripetal accel\w*[^.]{0,140}?(?:omega|ω|angular)"
                              r"[^.]{0,40}?(?:\^2|squar)", nt, re.I))
        )
        if not has_ac_relation:
            issues.append("intermediate tier: no structured a_c = omega^2 * r relation found")
    if tier == "advanced" and not unreliable:
        if not re.search(r"alpha|α", t):
            issues.append("advanced tier: no angular acceleration (alpha) mentioned")
        if not re.search(rf"t\s*[=≈~]\s*{NUM}\s*s", norm(t)):
            issues.append("advanced tier: no explicit timeline instant (t = … s) used")
    return issues


# ---- (4) motion-type faithfulness -------------------------------------------
# NB: "constant angular ACCELERATION" (constant alpha) is CORRECT for accelerating motion —
# only flag constant speed/rate/velocity/spin, not constant acceleration.
_STEADY = re.compile(r"\b(steady (?:pace|speed|spin)|constant (?:speed|rate|velocity|spin)|"
                     r"uniform (?:motion|rate|speed)|does not (?:speed up or slow down|change)|"
                     r"no (?:speeding up|change in speed)|unchanging speed)\b", re.I)
# Union of both historical negation look-back lists (grounding tool + live gate).
_NEG = ("rather than", "instead of", "not ", "isn't", "is not", "no longer",
        "maintaining", "never")


def motion_faithfulness(seed, text):
    mt = ((seed or {}).get("angular_acceleration") or {}).get("motion_type")
    if mt not in ("accelerating", "decelerating"):
        return []
    out = []
    for m in _STEADY.finditer(text):
        pre = text[max(0, m.start()-40):m.start()].lower()
        if any(neg in pre for neg in _NEG):
            continue
        out.append(f'says "{m.group(0)}" but motion_type={mt}')
    return out


# ---- (5) vocabulary ----------------------------------------------------------
# Rule 8 (tracking / pipeline): this is a physics lesson, not a tracking report.
TRACKING_VOCAB = [
    r"\btrack(?:ed|ing)\b", r"pipeline", r"detect(?:ed|ion|or)?", r"coverage",
    r"fps", r"frame rate", r"frames? per second", r"validation flags?", r"\bROI\b",
    r"pixels?", r"bounding box", r"the (?:tool|model|algorithm)", r"\bfilm(?:ed|ing)?\b",
    r"\brecord(?:ed|ing)?\b", r"(?:video|screen|image|frame)[ -]?captur\w*", r"annotat(?:e|ed|ion)",
    r"data ?set", r"\bframe\b",
]
# Rule 8b (dynamics — this tier is KINEMATICS only): describe HOW it moves, never WHY.
# "inward pull" / "centripetal acceleration" are the sanctioned phrasings for the a_c;
# slowing/speeding has no named cause at any tier.
DYNAMICS_VOCAB = [
    r"forces?", r"torque", r"friction", r"\benergy\b", r"momentum", r"\bmass(?:es)?\b",
    r"dissipat(?:e|es|ed|ion)", r"\bbrak(?:e|es|ed|ing)\b", r"\bmotor\b", r"newtons?",
    r"\bwork\b(?! out\b| together\b)", r"inertia", r"\bdrag\b", r"gravit(?:y|ational)",
    r"\bpush(?:es|ed)?\b",
]
_TRACKING_RE = re.compile("|".join(f"(?:{p})" for p in TRACKING_VOCAB), re.I)
_DYNAMICS_RE = re.compile("|".join(f"(?:{p})" for p in DYNAMICS_VOCAB), re.I)

# Prompt-facing plain-English views of the two banned lists. material_tiers.py renders
# HARD RULE 8 / 8b from THESE, co-located with the regexes above so the prompt the model
# sees and the check it is graded against are maintained together (cannot drift).
TRACKING_VOCAB_HUMAN = (
    "tracking or tracked (the object), pipeline, detect / detection, coverage, fps or frame rate, "
    "validation flag, ROI, pixel, bounding box, 'the tool / the model / the algorithm', "
    "film / filmed, record / recording, video capture, annotate, dataset, frame")
DYNAMICS_VOCAB_HUMAN = (
    "force, torque, friction, energy, momentum, mass, dissipate, brake / braking, motor, "
    "newton, work, inertia, drag, gravity, push")


def _vocab_scan(regex, text, kind):
    out = []
    for m in regex.finditer(text):
        a, b = max(0, m.start()-15), min(len(text), m.end()+15)
        ctx = text[a:b].replace("\n", " ")
        out.append({"kind": kind, "word": m.group(0), "context": "…"+ctx.strip()+"…"})
    return out


def vocab_issues(text):
    """Tracking/pipeline words (rule 8) + dynamics words (rule 8b), with context."""
    return _vocab_scan(_TRACKING_RE, text, "tracking") + \
        _vocab_scan(_DYNAMICS_RE, text, "dynamics")


# ---- (6) story fence ---------------------------------------------------------
def story_fence_issues(obj, frame):
    """The frame's fictional who/where may colour the Scenario ONLY. If a proper name
    or place leaks into the physics sections (2–5), the fiction is contaminating the
    grounded content — flag it."""
    if not frame:
        return []
    secs = obj.get("sections", {}) if isinstance(obj, dict) else {}
    if not isinstance(secs, dict):
        return []
    strings = []
    for tok in (frame.get("who"), frame.get("where")):
        if isinstance(tok, str):
            strings += [w for w in re.split(r"[\s,./]+", tok) if len(w) >= 3]
    if not strings:
        return []
    out = []
    for h, body in secs.items():
        if h == "Scenario" or not isinstance(body, str):
            continue
        low = body.lower()
        for w in strings:
            if re.search(rf"\b{re.escape(w.lower())}\b", low):
                out.append(f"frame token '{w}' leaked into '{h}' (fiction outside Scenario)")
    return out


# ---- (7) cross-tier ----------------------------------------------------------
# Ported from tools/grade_material_difficulty.py — the element-interactivity counters.
QUANTITIES = {
    "radius (r)":                 [r"\bradius\b", r"distance from (?:the )?cent(?:er|re)", r"\br\b"],
    "angular velocity (omega)":   [r"angular (?:velocity|speed)", r"spin rate", r"\bomega\b", "ω", r"rad/?s"],
    "linear speed (v)":           [r"linear speed", r"tangential", r"\bspeed\b", r"\bvelocity\b", r"m/?s\b"],
    "centripetal accel. (a_c)":   [r"centripetal accel", r"inward pull", r"a_?c\b", r"m/?s.?2", "m/s²"],
    "period (T)":                 [r"\bperiod\b", r"one full (?:turn|revolution|cycle)", r"time (?:for|of) one"],
    "frequency (f)":              [r"\bfrequency\b", r"\bhz\b", r"turns per second", r"revolutions per second"],
    "angular accel. (alpha)":     [r"angular accel", r"\balpha\b", "α", r"rad/?s.?2"],
}
RELATION_CUES = [
    r"=", r"∝", r"proportional to", r"varies (?:as|with)", r"divided by",
    r"product of", r"squared", r"square of", r"the ratio of", r"times the",
    r"multiplied by", r"\bv\s*=\s*", r"a_?c\s*=", r"2\s*π", r"2pi",
]


def quantities_in(text):
    t = text.lower()
    return [name for name, cues in QUANTITIES.items() if any(re.search(c, t) for c in cues)]


def relations_in(text):
    t = text.lower()
    return sum(len(re.findall(c, t)) for c in RELATION_CUES)


def ei_score(text):
    """Element-interactivity proxy (CLT): distinct quantities + explicit relations."""
    return len(quantities_in(text)) + relations_in(text)


def _passage(obj):
    secs = obj.get("sections", {}) if isinstance(obj, dict) else {}
    return " ".join(v for v in secs.values() if isinstance(v, str))


def _instants_cited(text):
    """Every t = X s the prose asserts, as floats (for the worked-instant check)."""
    return [float(m.group(1)) for m in re.finditer(rf"t\s*[=≈~]\s*({NUM})\s*s", norm(text))]


def cross_tier_issues(materials, seed, anchors, unreliable=False):
    """Belt-and-braces checks ACROSS the three tiers, once all are generated.

    - title equality: every tier's scene_title identical (WS-1b overwrites them, so this
      is a guard against a future regression).
    - worked-instant compliance/uniqueness: each tier cites the timeline instants it was
      assigned (``anchors[tier]`` are timeline indices) and does NOT reuse another tier's.
      Skipped when ``unreliable`` (no per-instant claims are allowed on an oblique clip).
    - EI monotonicity: ei(basic) < ei(intermediate) < ei(advanced).
    """
    issues = []
    tiers = [t for t in ("basic", "intermediate", "advanced") if t in materials]

    titles = {t: (materials[t].get("scene_title") or "").strip() for t in tiers}
    uniq = set(v for v in titles.values() if v)
    if len(uniq) > 1:
        issues.append(f"scene_title differs across tiers: {titles}")

    timeline = seed.get("timeline") or []
    if not unreliable and timeline and anchors:
        assigned = {}  # tier -> set of expected t-values
        for t in tiers:
            idxs = anchors.get(t, [])
            assigned[t] = {round(timeline[i]["t_s"], 2) for i in idxs
                           if 0 <= i < len(timeline)}
        for t in tiers:
            want = assigned[t]
            if not want:
                continue
            cited = _instants_cited(_passage(materials[t]))
            for w in want:
                if not any(abs(w - c) <= 0.05 for c in cited):
                    issues.append(f"{t} tier: missing assigned worked instant t={w} s")
            # uniqueness: this tier must not reuse another tier's assigned instant
            others = set().union(*[assigned[o] for o in tiers if o != t]) if len(tiers) > 1 else set()
            others -= want
            for c in cited:
                if any(abs(o - c) <= 0.05 for o in others):
                    issues.append(f"{t} tier: reuses another tier's instant t={c} s")

    eis = {t: ei_score(_passage(materials[t])) for t in tiers}
    order = [t for t in ("basic", "intermediate", "advanced") if t in eis]
    for a, b in zip(order, order[1:]):
        if not eis[a] < eis[b]:
            issues.append(f"element interactivity not rising: {a}={eis[a]} !< {b}={eis[b]}")
    return issues


# ---- live per-tier gate (used by material_tiers.py) --------------------------
def tier_gate(obj, seed, frame=None):
    """Return a list of issue strings for ONE generated tier (empty = passes).

    Mirrors the historical ``material_tiers._gate`` but sourced here so prompt and check
    share constants. When per-instant omega is unreliable (oblique capture) the
    arithmetic and advanced-timeline checks are skipped — the material is REQUIRED to
    avoid per-instant claims, so enforcing them would penalise correct hedging.
    """
    text = _passage(obj)
    tier = obj.get("tier")
    unreliable = not (seed.get("measurement_quality") or {}).get("reliable", True)
    issues = []
    if not unreliable:
        issues += [f"arithmetic: {c['claim']} -> computes {c['computed']}, stated {c['stated']}"
                   for c in arithmetic_claims(text) if not c["ok"]]
    issues += [f"ungrounded number {u['value']} in {u['context']}"
               for u in ungrounded_numbers(text, allowed_values(seed))]
    issues += tier_compliance(tier, text, unreliable=unreliable)
    issues += motion_faithfulness(seed, text)
    issues += [f"vocab[{v['kind']}]: '{v['word']}' in {v['context']}" for v in vocab_issues(text)]
    issues += story_fence_issues(obj, frame)
    return issues
