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

# Per-tier policy. AUTHORITATIVE SOURCE: analysis/material_tiers.py — this standalone tool
# imports its TIERS so the two can never drift (the old local copy still had v=omega*r as an
# intermediate core relation after the live pipeline dropped it). `figures` mirrors
# TIER_ARTIFACTS in render/report.py so the prose only describes plots the tier's PDF shows.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "workspace_lib"))
from analysis.material_tiers import TIERS  # noqa: E402
from analysis.material_gate import tier_gate  # noqa: E402 — deterministic per-tier verdict


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


def _generate_tier(tier, system, user):
    """One draft for a tier: call Qwen, parse, stamp the requested tier."""
    obj = _parse_json(_call_qwen(system, user))
    obj["tier"] = tier  # trust our request over the model's self-label
    return obj


def _select_candidate(tier, system, user, seed, k):
    """Generate-K-gate-select (Utami SocioMathLLM pattern): draft K, run each through the
    deterministic tier_gate, keep the cleanest. Plays to the 35B's strength (drafting) and
    around its weakness (self-correction) — see IKA_DISSERTATION_TAKEAWAYS.md §2.

    Returns (best_obj, candidate_log). Tie-break is deterministic: fewest gate issues, then
    earliest draft index — so the choice is reproducible given the same K drafts.
    """
    cands = []
    for i in range(k):
        try:
            obj = _generate_tier(tier, system, user)
        except Exception as e:  # noqa: BLE001 — a bad draft shouldn't sink the whole tier
            print(f"   draft {i + 1}/{k}: FAILED ({e})", flush=True)
            continue
        issues = tier_gate(obj, seed)
        cands.append((len(issues), i, obj, issues))
        print(f"   draft {i + 1}/{k}: {len(issues)} gate issue(s)"
              + (f" -> {issues[0]}" if issues else " -> clean"), flush=True)
    if not cands:
        raise RuntimeError(f"all {k} drafts failed for tier {tier}")
    cands.sort(key=lambda c: (c[0], c[1]))  # fewest issues, then earliest draft
    best_n, best_i, best_obj, best_issues = cands[0]
    log = [{"draft": i, "n_issues": n, "issues": iss} for n, i, _, iss in sorted(cands, key=lambda c: c[1])]
    print(f"   selected draft {best_i + 1} ({best_n} issue(s))", flush=True)
    return best_obj, log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("seed")
    ap.add_argument("--tiers", nargs="+", default=list(TIERS), choices=list(TIERS))
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--candidates", type=int, default=1, metavar="K",
                    help="generate K drafts per tier and gate-select the cleanest (K=1 = "
                         "current single-draft behaviour, unchanged).")
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
        if args.candidates > 1:
            print(f".. generating {tier} — {args.candidates} candidates (Qwen) ...", flush=True)
            obj, cand_log = _select_candidate(tier, system, user, seed, args.candidates)
        else:
            print(f".. generating {tier} (Qwen) ...", flush=True)
            obj, cand_log = _parse_json(_call_qwen(system, user)), None
            obj["tier"] = tier  # trust our request over the model's self-label
        obj.setdefault("object_name", seed.get("object_name"))
        obj.setdefault("scene_title", seed.get("scene_title"))
        out_p = outdir / f"material.{tier}.json"
        out_p.write_text(json.dumps(obj, indent=2, ensure_ascii=False))
        if cand_log is not None:
            (outdir / f"material.{tier}.candidates.json").write_text(
                json.dumps(cand_log, indent=2, ensure_ascii=False))
        secs = obj.get("sections", {})
        miss = [h for h in SECTIONS if h not in secs]
        print(f"OK {out_p.name}: {len(secs)} sections, bloom={obj.get('bloom_objective')}, "
              f"ei={obj.get('element_interactivity')}, conflict={obj.get('tier_conflict')}"
              + (f", MISSING {miss}" if miss else ""))


if __name__ == "__main__":
    main()
