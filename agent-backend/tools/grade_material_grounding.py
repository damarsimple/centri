#!/usr/bin/env python3
"""Deterministic grounding / consistency verifier for generated learning material.

Unlike BERTScore (relevance to a reference text), this checks the material against the
measured GROUND TRUTH (the seed) and against itself — objectively, no model:

  1. ARITHMETIC CLOSURE — every explicit numeric claim in the prose must actually compute
     (catches "6.59 x 1.78 = 12.2", which is 11.7, not 12.2). Seed-independent.
  2. NUMBER GROUNDING — every physics-like number in the prose must trace to a seed value
     (direct, timeline, or a simple derived identity) within tolerance. Catches invented
     quantities. Needs the seed.
  3. TIER COMPLIANCE — basic: no equations/symbols; intermediate: the core relations;
     advanced: alpha + a timeline instant.
  4. MOTION-TYPE FAITHFULNESS — if the clip is accelerating/decelerating, the prose must not
     call it steady/constant/uniform.

Usage:
  python tools/grade_material_grounding.py \
      --seed material_work/<obj>/material_seed.json \
      --materials material.basic.json material.intermediate.json material.advanced.json \
      --out material_work/_eval/grounding_report.md
A single material may carry its own tier via the "tier" field; --seed is optional but
arithmetic/tier/motion checks run without it.
"""
import argparse, json, re, glob, pathlib

# ---- normalization -----------------------------------------------------------
_SYM = {"×": " * ", "·": " * ", "✕": " * ", "÷": " / ", "≈": " ~= ", "²": "^2 ",
        "³": "^3 ", "π": " pi ", "−": "-", "—": "-", "’": "'", "“": '"', "”": '"'}

def norm(s: str) -> str:
    for k, v in _SYM.items():
        s = s.replace(k, v)
    return s

NUM = r"[-+]?\d+(?:\.\d+)?"
SEP = r"[^0-9]{0,22}?"           # units / words allowed between tokens (bounded, lazy)
EQ  = r"(?:=|~=|yields?|gives?|equals?|matches|to(?: roughly| about| approximately)?|" \
      r"is(?: roughly| about| approximately)?|resulting in|producing)"
APPROX = r"(?:roughly|about|approximately|~|nearly)?"

def _f(x): return float(x)

# ---- (1) arithmetic closure --------------------------------------------------
def _neutralize_units(t: str) -> str:
    """Stop unit slashes (rad/s, m/s, m/s^2) from looking like numeric division."""
    t = re.sub(r"(rad|km|cm|mm|deg|m)\s*/\s*s(\s*\^?\s*2)?", r"\1_s", t)
    t = re.sub(r"(?<=[a-zA-Z])\s*/\s*s\b", "_s", t)
    return t

def arithmetic_claims(text: str, rel_tol=0.02):
    """Find explicit `A op B (op ...) eq C` numeric claims and check they compute."""
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
    # squared forms FIRST (unit/paren may sit between the number and ^2):
    #   A^2 * B eq C   and   A^2 / B eq C   (e.g. "(4.861 rad/s)^2 times 0.148", "0.385^2 / 0.075")
    for m in re.finditer(rf"{NOPRE}({NUM}){SEP}\^2{SEP}{MUL}{SEP}({NUM}){SEP}{EQ}\s*{APPROX}\s*({NUM})", t):
        a, b, c = map(_f, m.groups()); check(m.group(0), a*a*b, c)
    for m in re.finditer(rf"{NOPRE}({NUM}){SEP}\^2{SEP}{DIV}{SEP}({NUM}){SEP}{EQ}\s*{APPROX}\s*({NUM})", t):
        a, b, c = map(_f, m.groups())
        if b != 0: check(m.group(0), a*a/b, c)
    # 2*pi / B eq C  (period; BEFORE generic division so pi isn't dropped). op may be / , "divided by", or "by"
    for m in re.finditer(rf"2\s*\*?\s*pi\s*(?:/|divided by|by)\s*({NUM}){SEP}{EQ}\s*{APPROX}\s*({NUM})", t):
        a, c = map(_f, m.groups())
        if a != 0: check("2pi / "+m.group(1)+" = "+m.group(2), 6.283185307/a, c)
    # plain product:  A * B eq C   (skip squared/pi spans)
    for m in re.finditer(rf"{NOPRE}({NUM}){SEP}{MUL}{SEP}({NUM}){SEP}{EQ}\s*{APPROX}\s*({NUM})", t):
        if "^2" in m.group(0) or "pi" in m.group(0):
            continue
        a, b, c = map(_f, m.groups()); check(m.group(0), a*b, c)
    # division / reciprocal:  A / B eq C   (skip squared/pi spans)
    for m in re.finditer(rf"{NOPRE}({NUM}){SEP}{DIV}{SEP}({NUM}){SEP}{EQ}\s*{APPROX}\s*({NUM})", t):
        if "^2" in m.group(0) or "pi" in m.group(0):
            continue   # handled by squared / 2pi rules above
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
    aa = seed.get("angular_acceleration") or {}
    for k in ("alpha_rad_s2", "omega_initial", "omega_final", "a_t_mean_m_s2"):
        add(aa.get(k))
    add(seed.get("active_duration_s")); add(seed.get("measured_radius_m"))
    cn = seed.get("calibration_note") or {}
    add(cn.get("px_per_m")); add(cn.get("reference_physical_size_m"))
    # simple derived: 2pi/omega, 1/f, alpha*r, omega^2*r, omega*r per variable pairs
    byk = {v["symbol"]: v.get("value") for v in seed.get("variables", []) if v.get("value") is not None}
    if "omega" in byk and byk["omega"]:
        add(6.283185307 / byk["omega"])
    if "f" in byk and byk["f"]:
        add(1 / byk["f"])
    if "r" in byk and "omega" in byk:
        add(byk["omega"] * byk["r"]); add(byk["omega"]**2 * byk["r"])
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
EQ_SIGNS = re.compile(r"[=/^]|×|·|÷|²|√|\bomega\b|\bω\b|\balpha\b|\bα\b|\bv\s*=\s*|a_c|rad/s")
def tier_compliance(tier, text):
    issues = []
    t = text
    if tier == "basic":
        hits = [s for s in [r"=", r"\^2", r"²", r"ω", r"\bomega\b", r"α", r"\balpha\b",
                            r"v\s*=", r"a_c", r"rad/s"] if re.search(s, t)]
        if hits:
            issues.append(f"basic tier contains equation/symbol markers: {hits}")
    if tier == "intermediate":
        if not re.search(r"v\s*=\s*(?:omega|ω)\s*\*?\s*r|tangential.*angular|angular.*radius", norm(t), re.I):
            issues.append("intermediate tier: no v=ωr relation found")
    if tier == "advanced":
        if not re.search(r"alpha|α", t):
            issues.append("advanced tier: no angular acceleration (alpha) mentioned")
        if not re.search(rf"t\s*[=≈~]\s*{NUM}\s*s", norm(t)):
            issues.append("advanced tier: no explicit timeline instant (t = … s) used")
    return issues

# ---- (4) motion-type faithfulness -------------------------------------------
# NB: "constant angular ACCELERATION" (constant alpha) is CORRECT for accelerating motion —
# only flag constant speed/rate/velocity/spin, not constant acceleration.
_STEADY = re.compile(r"\b(steady (?:pace|speed|spin)|constant (?:speed|rate|velocity|spin)|"
                     r"uniform (?:motion|rate|speed)|does not (?:speed up|change)|"
                     r"no (?:speeding up|change in speed)|unchanging speed)\b", re.I)
def motion_faithfulness(seed, text):
    mt = ((seed or {}).get("angular_acceleration") or {}).get("motion_type")
    if mt not in ("accelerating", "decelerating"):
        return []
    out = []
    for m in _STEADY.finditer(text):
        # allow "rather than maintaining a constant spin" (negated) — look back far enough
        pre = text[max(0, m.start()-40):m.start()].lower()
        if any(neg in pre for neg in ("rather than", "instead of", "not ", "isn't", "is not",
                                      "no longer", "maintaining", "never")):
            continue
        out.append(f'says "{m.group(0)}" but motion_type={mt}')
    return out

# ---- driver ------------------------------------------------------------------
def grade_one(mat, seed):
    secs = mat.get("sections", mat)
    text = "\n".join(v for v in secs.values() if isinstance(v, str))
    tier = mat.get("tier", "?")
    ar = arithmetic_claims(text)
    ar_fail = [c for c in ar if not c["ok"]]
    ung = ungrounded_numbers(text, allowed_values(seed)) if seed else []
    tc = tier_compliance(tier, text) if tier in ("basic", "intermediate", "advanced") else []
    mf = motion_faithfulness(seed, text) if seed else []
    n_checks = len(ar) + (1 if seed else 0) + 1 + (1 if seed else 0)
    passed = (len(ar) - len(ar_fail)) + (0 if ung else (1 if seed else 0)) \
             + (0 if tc else 1) + (0 if mf else (1 if seed else 0))
    return {"tier": tier, "arith": ar, "arith_fail": ar_fail, "ungrounded": ung,
            "tier_issues": tc, "motion_issues": mf,
            "ok": not (ar_fail or ung or tc or mf)}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", default=None)
    ap.add_argument("--materials", nargs="+", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    paths = []
    for m in args.materials:
        paths += sorted(glob.glob(m)) if any(c in m for c in "*?[") else [m]
    seed = json.loads(pathlib.Path(args.seed).read_text()) if args.seed else None

    L = ["# Material grounding & consistency report",
         "Deterministic checks against the measured seed (no model). "
         "PASS = every numeric claim computes, every number traces to the seed, tier rules "
         "hold, motion described faithfully.\n"]
    n_ok = 0
    for p in paths:
        mat = json.loads(pathlib.Path(p).read_text())
        r = grade_one(mat, seed)
        n_ok += r["ok"]
        name = pathlib.Path(p).stem
        L.append(f"## {name}  —  tier={r['tier']}  —  {'✅ PASS' if r['ok'] else '❌ FAIL'}")
        L.append(f"- arithmetic claims: {len(r['arith'])} found, "
                 f"**{len(r['arith_fail'])} fail**")
        for c in r["arith_fail"]:
            L.append(f"    - ❌ `{c['claim']}` → computes to **{c['computed']}**, stated **{c['stated']}**")
        if r["arith"] and not r["arith_fail"]:
            L.append(f"    - ✅ all {len(r['arith'])} compute "
                     + ", ".join(f"`{c['claim']}`={c['computed']}" for c in r["arith"][:3])
                     + (" …" if len(r["arith"]) > 3 else ""))
        if seed:
            L.append(f"- ungrounded numbers: **{len(r['ungrounded'])}**")
            for u in r["ungrounded"]:
                L.append(f"    - ❌ {u['value']}  in  {u['context']}")
        L.append(f"- tier compliance: {'✅ ok' if not r['tier_issues'] else '❌ ' + '; '.join(r['tier_issues'])}")
        if seed:
            L.append(f"- motion faithfulness: {'✅ ok' if not r['motion_issues'] else '❌ ' + '; '.join(r['motion_issues'])}")
        L.append("")
    L.insert(2, f"**{n_ok}/{len(paths)} materials fully grounded.**\n")
    report = "\n".join(L)
    print(report)
    if args.out:
        out = pathlib.Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report + "\n")
        print(f"\nreport -> {out}")

if __name__ == "__main__":
    main()
