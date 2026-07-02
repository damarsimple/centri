#!/usr/bin/env python3
"""Module D, difficulty-tiered path: turn one material_seed.json into THREE grounded
learning passages (basic | intermediate | advanced) via the lab Qwen, one call per
tier (an A3B model bleeds vocabulary between tiers if asked for all three at once).

Implements docs/difficulty-tiered-material-spec.md. Each tier is told exactly which
seed fields it may use (the depth ladder) AND which figures it will be shown beside
its prose — so "Reading the figures" narrates only the plots that tier's PDF actually
embeds (see TIER_ARTIFACTS in analysis/render/report.py; the two must agree).

Output schema is the same `sections` dict the renderer + run_material_eval.py already
consume, plus tier metadata. Numbers come ONLY from the seed.

Usage:  python tools/generate_tier_material.py <seed.json | dir-with-material_seed.json> \
            [--tiers basic intermediate advanced] [--outdir DIR]
        # writes material.<tier>.json (next to the seed, or in --outdir)

Run it where 192.168.1.205:8083 is reachable (e.g. inside the worker container, or set
PI_INFERENCE_URL). Needs no GPU locally — it only calls the inference server.
"""
import argparse, json, os, re, sys, pathlib, urllib.request

BASE = os.environ.get("PI_INFERENCE_URL", "http://192.168.1.205:8083") + "/v1/chat/completions"
KEY = os.environ.get("PI_INFERENCE_API_KEY", "hwanglabyoungdumbandbreak")
MODEL = "Qwen3.6-35B"

SECTIONS = ["Scenario", "The variables we measured", "How the variables are related",
            "What the video shows over time", "Reading the figures"]

# Per-tier policy. `figures` MUST mirror TIER_ARTIFACTS in render/report.py so the prose
# only describes plots the tier's PDF shows. `seed_fields`/`forbidden` are the depth ladder.
TIERS = {
    "basic": {
        "bloom": "Remember / Understand",
        "interactivity": "low",
        "seed_fields": "object name, rotation direction, clip duration, and the radius "
                       "(as 'how far out it sits') plus the IDEA of an inward pull. "
                       "You may name 'centripetal acceleration' once, in words.",
        "forbidden": "NO symbols (omega/alpha/v/a_c), NO equations or formula derivations, "
                     "NO numeric substitution beyond the radius and the duration, NO "
                     "time-evolution analysis with numbers.",
        "figures": "Only two pictures: (1) a frame from the video showing the object on its "
                   "circular path with the radius marked from the centre, and (2) a plot of "
                   "the traced path showing every point falls on one circle. There is NO "
                   "data table and NO graph of speed or acceleration over time for this "
                   "reader — do not mention any table or any 'graph/plot of ... over time'.",
        "test": "Could a learner who has never seen the equations follow every sentence, "
                "holding one idea at a time?",
    },
    "intermediate": {
        "bloom": "Apply / Analyze",
        "interactivity": "moderate",
        "seed_fields": "the radius, angular velocity (omega), tangential speed (v), "
                       "centripetal acceleration (a_c), period (T), frequency (f) WITH their "
                       "measured values and units, and the relations v=omega*r, "
                       "a_c=v^2/r=omega^2*r, T=2*pi/omega=1/f shown to hold for THIS object.",
        "forbidden": "Do NOT make the motion's change over time the main point (one sentence "
                     "of context is fine), NO angular-acceleration value or timeline, NO "
                     "scale/calibration-caveat discussion.",
        "figures": "An annotated frame with the radius, a short data table of the core "
                   "measurements (radius, omega, v, a_c, period, frequency), one graph of "
                   "tangential speed over time, and the traced circular path. Do not mention "
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
                     "higher-order integration over time and at limits.",
        "figures": "An annotated frame, the full measurements table (including angular "
                   "acceleration and the calibration), graphs of angular velocity and "
                   "centripetal acceleration over time, and a summary panel that combines the "
                   "views, plus the traced path.",
        "test": "Does the passage integrate several quantities AND their change over time, and "
                "reason about proportionality, limits, or what the measurement does/doesn't pin down?",
    },
}


def _facts(seed):
    """Compact, model-friendly rendering of the seed (numbers are ground truth)."""
    lines = [f"object: {seed.get('scene_title') or seed.get('object_name')}",
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
        lines.append(f"consistency note: report radius as r={cn.get('radius_used')} "
                     f"(the fitted orbit radius); verify v=omega*r and a_c=omega^2*r at a "
                     f"SINGLE timeline instant, never with the summary means (Jensen).")
    cal = seed.get("calibration_note", {})
    if cal:
        lines.append(f"calibration note: scale from a reference of "
                     f"{cal.get('reference_physical_size_m')} m; {cal.get('caveat')}")
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
    "not given; quote values with units; round prose to ~3 significant figures.\n"
    "2. This is exposition ONLY — no questions, quizzes, 'try this', or exercises.\n"
    "3. Motion-type faithfulness: if motion type is accelerating/decelerating you MUST convey "
    "the speed change qualitatively at THIS tier (e.g. 'whirls faster and faster'); never call "
    "a speeding-up motion steady. The alpha value + timeline are reserved for the advanced tier.\n"
    "4. If you show a relation numerically, verify it at a SINGLE timeline instant (where "
    "v=omega*r and a_c=omega^2*r close exactly), never with the summary means.\n"
    "5. 'Reading the figures' must describe ONLY the figures listed above for this tier — do "
    "not mention any plot or table that is not in that list.\n"
    "6. The element interactivity AND the Bloom objective must both point to {tier} — if they "
    "disagree, rewrite.\n"
    "7. WRITER'S TEST for this tier: {test}\n\n"
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


def _parse_json(text):
    """Pull the JSON object out of the model reply (tolerate ```json fences / <think>)."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.S)
    a, b = text.find("{"), text.rfind("}")
    if a == -1 or b == -1:
        raise ValueError(f"no JSON object in reply: {text[:200]!r}")
    return json.loads(text[a:b + 1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("seed")
    ap.add_argument("--tiers", nargs="+", default=list(TIERS), choices=list(TIERS))
    ap.add_argument("--outdir", default=None)
    args = ap.parse_args()

    sp = pathlib.Path(args.seed)
    seed_p = sp / "material_seed.json" if sp.is_dir() else sp
    if not seed_p.exists():
        sys.exit(f"!! no seed at {seed_p}")
    seed = json.loads(seed_p.read_text())
    outdir = pathlib.Path(args.outdir) if args.outdir else seed_p.parent
    outdir.mkdir(parents=True, exist_ok=True)
    facts = _facts(seed)

    for tier in args.tiers:
        spec = TIERS[tier]
        system = SYSTEM_TMPL.format(tier=tier, tier_upper=tier.upper(), **spec)
        user = ("Ground-truth measurements for this clip:\n\n" + facts +
                f"\n\nWrite the {tier.upper()} passage now, following every rule and using "
                "the exact five section headers as JSON keys.")
        print(f".. generating {tier} (Qwen) ...", flush=True)
        obj = _parse_json(_call_qwen(system, user))
        obj.setdefault("object_name", seed.get("object_name"))
        obj.setdefault("scene_title", seed.get("scene_title"))
        obj["tier"] = tier  # trust our request over the model's self-label
        out_p = outdir / f"material.{tier}.json"
        out_p.write_text(json.dumps(obj, indent=2, ensure_ascii=False))
        secs = obj.get("sections", {})
        miss = [h for h in SECTIONS if h not in secs]
        print(f"OK {out_p.name}: {len(secs)} sections, bloom={obj.get('bloom_objective')}, "
              f"ei={obj.get('element_interactivity')}, conflict={obj.get('tier_conflict')}"
              + (f", MISSING {miss}" if miss else ""))


if __name__ == "__main__":
    main()
