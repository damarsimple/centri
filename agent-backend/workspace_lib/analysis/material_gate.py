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

    def check(expr, lhs, rhs, kind="generic"):
        if rhs == 0:
            ok = abs(lhs) < 1e-9
        else:
            ok = abs(lhs - rhs) / max(abs(rhs), 1e-9) <= rel_tol
        # `kind` lets the gate keep only SCALE-FREE claims (the period identity 2pi/omega)
        # on an oblique clip, where per-instant v=omega*r / a_c=omega^2*r cannot be verified
        # but T = 2pi/omega still must hold.
        claims.append({"claim": expr.strip(), "computed": round(lhs, 4),
                       "stated": rhs, "ok": ok, "kind": kind})

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
        if a != 0: check("2pi / "+m.group(1)+" = "+m.group(2), 6.283185307/a, c, kind="period")
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


# ---- (1b) seed self-consistency (the deterministic blocks, verified) ---------
def _eval_arith(expr):
    """Best-effort numeric value of a substitution expression — the RHS of any '=',
    reduced to digits, + - * / ( ) and ^2/^3/pi. None when it will not parse. This is what
    verifies the 'correct-by-construction' worked examples actually compute (arithmetic_claims
    only matches simple binary A op B = C forms, so it misses '(A - B) / C', which is exactly
    how the red-phone alpha example shipped -4.07 from an expression equal to -1.34)."""
    e = norm(expr or "")
    e = e.split("=")[-1]                                  # RHS of "v = 2.7 * 0.15"
    e = e.replace("^3", "**3").replace("^2", "**2")
    e = re.sub(r"\bpi\b", "3.141592653589793", e)
    e = re.sub(r"[^0-9.+\-*/() ]", " ", e).strip().rstrip("*/+-. ")
    if not e:
        return None
    try:
        return eval(e, {"__builtins__": {}})             # noqa: S307 — sanitized to digits/ops
    except (SyntaxError, ValueError, ZeroDivisionError, TypeError):
        return None


def _first_num(s):
    m = re.search(NUM, s or "")
    return float(m.group(0)) if m else None


def _byk(seed):
    return {v["symbol"]: v.get("value") for v in seed.get("variables", [])
            if isinstance(v.get("value"), (int, float))}


def seed_consistency_issues(seed):
    """Verify the SEED's own numbers before render — the deterministic 'correct-by-
    construction' blocks and the summary table, independent of any LLM prose.

    Catches the red-phone/wheel classes: (a) a worked example whose printed arithmetic does
    not evaluate to its printed result; (b) a summary that mixes ω statistics so v ≠ ω·r or
    T ≠ 2π/ω̄ (unless the honesty box flags the period as an average); (c) a Jensen violation
    ⟨ω²⟩ < ⟨ω⟩². Returns a list of issue strings (empty = consistent)."""
    issues = []

    # (a) every deterministic worked example must compute to its stated result.
    for tier, exs in (seed.get("worked_examples") or {}).items():
        for e in exs:
            sub = e.get("substitute") or ""
            if "vs" in sub:                              # Jensen two-expression form
                continue
            got, want = _eval_arith(sub), _first_num(e.get("result", ""))
            if got is None or want is None:
                continue
            if abs(got - want) > max(0.5, 0.03 * abs(want)):
                issues.append(f"worked example [{tier}] '{e.get('title')}': "
                              f"{sub} computes {round(got, 3)}, stated {want}")

    # (a') the CYU answers embed prose-style A op B = C claims — the robust parser handles those.
    for tier, qs in (seed.get("check_understanding") or {}).items():
        for q in qs:
            for c in arithmetic_claims(q.get("answer", "")):
                if not c["ok"]:
                    issues.append(f"check-understanding [{tier}]: {c['claim']} computes "
                                  f"{c['computed']}, stated {c['stated']}")

    # (b/c) summary closure: v = ω·r, T ≈ 2π/ω̄, Jensen ⟨ω²⟩ ≥ ⟨ω⟩².
    b = _byk(seed)
    r, om, v, ac, T = (b.get("r"), b.get("omega"), b.get("v"), b.get("a_c"), b.get("T"))
    if all(isinstance(x, (int, float)) for x in (om, r, v)):
        if abs(v - abs(om) * r) > max(0.02, 0.03 * abs(v)):
            issues.append(f"summary: v={v} but omega*r={round(abs(om) * r, 3)} "
                          f"(v = omega*r broken — mixed omega statistics?)")
    if isinstance(om, (int, float)) and isinstance(T, (int, float)) and abs(om) > 1e-6:
        import math as _m
        pred = 2 * _m.pi / abs(om)
        note = (seed.get("measurement_honesty") or {}).get("intermediate", "") or ""
        if abs(T - pred) > max(0.03, 0.05 * abs(T)) and "average period is not" not in note:
            issues.append(f"summary: T={T} but 2pi/omega={round(pred, 3)} and the honesty "
                          f"box does not flag the period as an average (Jensen)")
    if all(isinstance(x, (int, float)) for x in (om, r, ac)) and r:
        w2_measured = ac / r                             # ⟨ω²⟩ implied by mean a_c
        if w2_measured + max(0.05, 0.02 * om * om) < om * om:
            issues.append(f"summary: mean a_c/r={round(w2_measured, 3)} < omega^2="
                          f"{round(om * om, 3)} (Jensen ⟨ω²⟩ ≥ ⟨ω⟩² violated)")

    # (d) A1: no deterministic block may multiply a rate by the clip length on a rest-then-turn
    # clip (laps/arc must use the turning window). Guards against a seed-construction regression.
    seed_text = " ".join(f"{e.get('substitute', '')} {e.get('result', '')}"
                         for exs in (seed.get("worked_examples") or {}).values() for e in exs)
    seed_text += " " + " ".join(q.get("answer", "")
                                for qs in (seed.get("check_understanding") or {}).values() for q in qs)
    issues += [f"seed wrong-duration: {w}" for w in wrong_duration_products(seed_text, seed)]
    return issues


# ---- (1c) wrong-duration products (A1) ---------------------------------------
def wrong_duration_products(text: str, seed: dict, rel_tol=0.03):
    """A1: on a clip where the object is at rest for much of the run (turning window <<
    clip length), any rate*time product — laps = f*t, arc = v*t, angle = omega*t — must use
    the TURNING time, not the clip length. arithmetic_claims can't catch this (0.907*5.87
    computes fine); the error is a modelling one (wrong duration), so flag the product where a
    rate is multiplied by a number ~= the clip length. Returns a list of issue strings."""
    clip, turn = seed.get("active_duration_s"), seed.get("turning_duration_s")
    if not (isinstance(clip, (int, float)) and isinstance(turn, (int, float))):
        return []
    if clip <= 0 or turn >= 0.9 * clip:          # spins throughout → clip length IS the turning time
        return []
    b = _byk(seed)
    rates = [abs(b[k]) for k in ("f", "v", "omega") if isinstance(b.get(k), (int, float))]
    rates += [abs(tl["omega_rad_s"]) for tl in seed.get("timeline", [])
              if isinstance(tl.get("omega_rad_s"), (int, float))]
    if not rates:
        return []
    t = _neutralize_units(norm(text))
    MUL = r"(?:\*|times|multiplied by)"
    issues = []
    for m in re.finditer(rf"({NUM}){SEP}{MUL}{SEP}({NUM})", t):
        a, c = float(m.group(1)), float(m.group(2))
        for x, y in ((a, c), (c, a)):            # x = the rate, y = the (wrong) clip-length time
            if (any(abs(x - r) <= max(0.02, rel_tol * r) for r in rates)
                    and abs(y - clip) <= max(0.05, rel_tol * clip)):
                issues.append(f"'{m.group(0).strip()}' multiplies a rate by the {round(clip, 2)} s "
                              f"clip length, but the object turns for only {round(turn, 2)} s "
                              f"(use the turning time)")
    return list(dict.fromkeys(issues))


def average_period_as_peak(text: str, seed: dict, window=70):
    """A2: the clip-average period T = 2*pi/<omega> is the pace of the WHOLE spin, not of any
    single moment. On a non-uniform clip the fastest instant turns much quicker
    (2*pi/omega_peak — e.g. the red-phone flick peaks at ~0.67 s while T = 1.1 s). Flag prose
    that pins the average period onto a peak/fastest moment: the average value appearing close
    to fastest-moment wording, with no averaging qualifier nearby to disambiguate. Returns a
    list of issue strings (empty when the peak lap barely differs from the average)."""
    aa = seed.get("angular_acceleration") or {}
    if aa.get("motion_type") not in ("decelerating", "accelerating"):
        return []
    T = next((v.get("value") for v in seed.get("variables", [])
              if v.get("symbol") == "T"), None)
    cands = [abs(x) for x in (aa.get("omega_initial"), aa.get("omega_final"))
             if isinstance(x, (int, float)) and abs(x) > 1e-6]
    if not (isinstance(T, (int, float)) and T > 0 and cands):
        return []
    peak_period = 6.283185307 / max(cands)
    if peak_period >= 0.85 * T:                  # peak lap barely differs from the average
        return []
    t = norm(text)
    PEAK = (r"fastest|quickest|peak|top speed|its (?:quickest|fastest)|"
            r"right after (?:the|that) (?:flick|nudge|spin|twist|push)")
    AVG = r"average|averaged|on average|over the whole|over the entire|\bmean\b|typical"
    issues = []
    for m in re.finditer(rf"({NUM})\s*(?:s\b|sec)", t):
        val = float(m.group(1))
        if abs(val - T) > max(0.05, 0.05 * T):   # not the average-period value
            continue
        ctx = t[max(0, m.start() - window):min(len(t), m.end() + window)]
        if re.search(PEAK, ctx) and not re.search(AVG, ctx):
            snippet = t[max(0, m.start() - 32):m.end() + 12].strip()
            issues.append(f"the clip-average period {round(T, 2)} s is stated as a peak/fastest "
                          f"pace ('...{snippet}...'); at its fastest a lap is ~"
                          f"{round(peak_period, 2)} s (the average describes the whole spin)")
    return list(dict.fromkeys(issues))


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
    add(seed.get("turning_duration_s"))          # the active turning window (A1)
    # sanction the CORRECT rate*turning products (laps, arc length) so they read as grounded
    turn = seed.get("turning_duration_s")
    if isinstance(turn, (int, float)):
        b0 = _byk(seed)
        for k in ("f", "v", "omega"):
            if isinstance(b0.get(k), (int, float)):
                add(abs(b0[k]) * turn)
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
_STEADY = re.compile(r"\b(steady (?:pace|speed|spin|rhythm)|constant (?:speed|rate|velocity|spin)|"
                     r"uniform (?:motion|rate|speed)|does not (?:speed up or slow down|change)|"
                     r"no (?:speeding up|change in speed)|unchanging (?:speed|pace|rate|spin)|"
                     r"smooth[, ]+(?:and )?(?:uninterrupted|unchanging|predictable)|"
                     r"uninterrupted (?:spin|rotation|motion|pace)|"
                     r"holds (?:that|its) (?:pace|speed))\b", re.I)
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


_NUMWORD = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
_PHASE_WORDS = ("speeding up", "slowing down", "steady")


def annotation_issues(text: str, phases):
    """Axis-4 render-aware annotation correctness: the prose must not claim more motion phases —
    or a phase word — than the tier's rendered graphs actually show. ``phases`` is the ordered
    list of phase meanings those graphs carry (render.figures._phase_sequence, significance-
    filtered so it matches the drawn bands). This closes the C2 gap: on the flick the ω(t) figure
    renders two bands (speeding up -> slowing down) but the prose used to assert "three distinct
    phases: speeding up, steady, and slowing down" — a phantom "steady" the figure never draws.
    Empty ``phases`` (uniform / oblique clip) => no check (nothing to contradict). Returns issue
    strings."""
    if not phases:
        return []
    present = {p.lower() for p in phases}
    n = len(phases)
    t = norm(text)
    issues = []
    # (a) a numeric phase-count claim that disagrees with what renders
    for m in re.finditer(r"\b(one|two|three|four|five|six|\d+)\s+"
                         r"(?:distinct\s+|different\s+|separate\s+)?phases?\b", t):
        w = m.group(1)
        claimed = _NUMWORD.get(w) or (int(w) if w.isdigit() else None)
        if claimed is not None and claimed != n:
            issues.append(f"prose claims {claimed} phase(s) ('{m.group(0).strip()}') but the "
                          f"figure shows {n} ({', '.join(phases)})")
    # (b) a phase WORD enumerated right after a "phases" mention that no rendered band carries.
    # Only fire inside an actual enumeration — the window must also name a REAL rendered phase —
    # so "the phases are not steady" (no listed phase) never trips it.
    for pm in re.finditer(r"phases?\b", t):
        window = t[pm.end(): pm.end() + 80]
        if not any(p in window for p in present):
            continue
        for word in _PHASE_WORDS:
            if word in window and word not in present:
                issues.append(f"prose names a '{word}' phase but the figure's phases are "
                              f"{', '.join(phases)}")
    return list(dict.fromkeys(issues))


# ---- live per-tier gate (used by material_tiers.py) --------------------------
def tier_gate(obj, seed, frame=None, manifest_phases=None):
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
    # Arithmetic closure. On an oblique clip we cannot verify per-instant v=omega*r /
    # a_c=omega^2*r (per-instant omega is unreliable), but the SCALE-FREE period identity
    # T = 2pi/omega still must hold — checking only that catches the wheel's false
    # "2pi/7.813 = 0.837" while sparing the correctly-hedged per-instant relations.
    claims = arithmetic_claims(text)
    if unreliable:
        claims = [c for c in claims if c.get("kind") == "period"]
    issues += [f"arithmetic: {c['claim']} -> computes {c['computed']}, stated {c['stated']}"
               for c in claims if not c["ok"]]
    issues += [f"ungrounded number {u['value']} in {u['context']}"
               for u in ungrounded_numbers(text, allowed_values(seed))]
    issues += [f"wrong-duration: {w}" for w in wrong_duration_products(text, seed)]
    issues += [f"avg-period-as-peak: {w}" for w in average_period_as_peak(text, seed)]
    issues += [f"annotation: {a}" for a in annotation_issues(text, manifest_phases or [])]
    issues += tier_compliance(tier, text, unreliable=unreliable)
    issues += motion_faithfulness(seed, text)
    issues += [f"vocab[{v['kind']}]: '{v['word']}' in {v['context']}" for v in vocab_issues(text)]
    issues += story_fence_issues(obj, frame)
    return issues
