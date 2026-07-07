#!/usr/bin/env python3
"""LLM-as-judge for Centri learning material — the qualitative complement to BERTScore.

BERTScore measures surface relevance to a reference; the grounding gate measures arithmetic/
tier/vocab correctness. Neither rates whether the passage is a GOOD lesson. This tool asks the
lab Qwen to score each generated material on the rubric adapted verbatim from Utami (2025)
Tables 8–9 (see docs/eval-rubric-ika.md), plus a Centri physics/tier extension block, so our
numbers sit directly beside the parent line's published ones.

Rubric (per material, 1–5). Grouped into three axes:
  Axis 1 — Authenticity & linguistic (Utami Table 8, verbatim):
    motivating_context           — a meaningful, compelling purpose.
    language_clarity             — language/terminology accessible to the target reading level.
    solution_steps               — requires more than one step to reach a solution.
    solution_strategy_variety    — supports multiple strategies to reach a solution.
    cognitive_demand             — an appropriate level of cognitive challenge.
  Axis 2 — Mathematical (Utami Table 9, verbatim):
    answerability                — at least one valid solution; necessary info, no ambiguity.
    structure_clarity            — logical flow linking given info to the required solution.
    multiple_strategies          — allows multiple solving methods (creativity / math thinking).
  Axis 3 — Centri physics/tier extension (ours, on top of hers):
    difficulty_fit               — depth matches the asserted tier (basic/intermediate/advanced).
    concept_accuracy             — physics correct, no misconceptions, relations right.
    grounding_accuracy           — numbers/figures consistent with the measured seed values.
plus achieved_bloom              — the Bloom level the passage actually reaches (Remember…Create).

Utami's Table 10 (socialization) is intentionally NOT adopted — it is her Study-4 contribution,
outside Centri's lane (see docs/eval-rubric-ika.md, decision #5).

Usage (run where PI_INFERENCE_URL is reachable, e.g. the worker or the lab machine):
  python tools/run_llm_judge.py \
      --materials material_work/<obj>/material.*.json \
      [--seed material_work/<obj>/material_seed.json] \
      [--difficulty-report material_work/_eval/tier_difficulty_report.json] \
      --out material_work/_eval/llm_judge_report.md
"""
import argparse, json, glob, os, pathlib, re, statistics, urllib.request

BASE = os.environ.get("PI_INFERENCE_URL", "http://192.168.1.205:8083") + "/v1/chat/completions"
KEY = os.environ.get("PI_INFERENCE_API_KEY", "hwanglabyoungdumbandbreak")
MODEL = os.environ.get("PI_JUDGE_MODEL", os.environ.get("PI_MATERIAL_MODEL", "Qwen3.6-35B"))

# Axes and their criteria, adapted from Utami (2025) Tables 8–9 + our physics/tier extension.
# docs/eval-rubric-ika.md is the shared source of truth (also drives build_rater_sheet.py).
AXES = {
    "authenticity_linguistic": [
        "motivating_context", "language_clarity", "solution_steps",
        "solution_strategy_variety", "cognitive_demand"],
    "mathematical": [
        "answerability", "structure_clarity", "multiple_strategies"],
    "physics_tier": [
        "difficulty_fit", "concept_accuracy", "grounding_accuracy"],
}
CRITERIA = [c for axis in AXES.values() for c in axis]
BLOOM = ["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"]

_RUBRIC_LINES = (
    "Axis 1 — Authenticity & linguistic (Utami 2025, Table 8):\n"
    "- motivating_context: presents a meaningful and compelling purpose.\n"
    "- language_clarity: language/terminology accessible to the target reading level.\n"
    "- solution_steps: requires more than one step to arrive at a solution.\n"
    "- solution_strategy_variety: supports multiple strategies to arrive at a solution.\n"
    "- cognitive_demand: an appropriate level of cognitive challenge.\n"
    "Axis 2 — Mathematical (Utami 2025, Table 9):\n"
    "- answerability: has at least one valid solution; necessary information provided without "
    "ambiguity; no redundant/misleading data unless intentional.\n"
    "- structure_clarity: logical flow lets the learner see the relationship between the given "
    "information and the required solution.\n"
    "- multiple_strategies: allows multiple solving methods, encouraging creativity.\n"
    "Axis 3 — Centri physics/tier extension:\n"
    "- difficulty_fit: the depth matches the asserted tier ({level}). basic = no equations, one "
    "idea at a time; intermediate = coordinates a few relations with numbers; advanced = "
    "integrates change-over-time, limits, proportionality.\n"
    "- concept_accuracy: the physics is correct — no misconceptions, relations right.\n"
    "- grounding_accuracy: numbers and described figures are internally consistent and match the "
    "measured values.\n"
)

SYSTEM = (
    "You are an expert physics-education assessor grading a SHORT learning passage about "
    "circular motion generated from a real video's measurements. Grade ONLY what is written. "
    "Be strict and consistent.\n\n"
    "Score each criterion 1–5 (5 = excellent):\n"
    + _RUBRIC_LINES +
    "Also state achieved_bloom: the single Bloom level the passage actually reaches, one of "
    + ", ".join(BLOOM) + ".\n"
    "Return ONLY JSON with exactly these keys: "
    + "{" + ",".join(f'"{c}":n' for c in CRITERIA)
    + ',"achieved_bloom":"...","rationale":"one sentence"}.'
)


def _call(system, user, temperature=0.0, max_tokens=2000):
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": temperature, "max_tokens": max_tokens,
        "chat_template_kwargs": {"enable_thinking": False},
    }).encode()
    req = urllib.request.Request(BASE, data=body, headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {KEY}"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        out = json.loads(resp.read())
    return out["choices"][0]["message"].get("content") or ""


def _parse(text):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    a, b = text.find("{"), text.rfind("}")
    if a == -1 or b == -1:
        raise ValueError(f"no JSON in judge reply: {text[:160]!r}")
    return json.loads(text[a:b + 1])


def judge_one(mat, seed=None, measured_ei=None):
    secs = mat.get("sections", mat)
    passage = "\n\n".join(f"## {k}\n{v}" for k, v in secs.items() if isinstance(v, str))
    level = mat.get("difficulty_level") or mat.get("tier") or "unspecified"
    ctx = ""
    if seed:
        vs = "; ".join(f"{v['symbol']}={v.get('value')}" for v in seed.get("variables", []))
        ctx += f"\n\nMeasured ground truth (for grounding_accuracy checks): {vs}"
    if measured_ei is not None:
        ctx += (f"\n\nDeterministic gate measured element-interactivity for this tier = "
                f"{measured_ei} (distinct quantities + relations). Use it to sanity-check "
                f"difficulty_fit: higher EI should accompany a higher tier.")
    user = f"Asserted difficulty level: {level}\n\nPassage:\n{passage}{ctx}"
    res = _parse(_call(SYSTEM.format(level=level), user))
    res["_level"] = level
    return res


def _load_measured_ei(path):
    """Map tier -> measured EI score from a grade_material_difficulty JSON report."""
    if not path:
        return {}
    data = json.loads(pathlib.Path(path).read_text())
    return {r.get("tier"): r.get("ei_score") for r in data.get("rows", [])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--materials", nargs="+", required=True)
    ap.add_argument("--seed", default=None)
    ap.add_argument("--difficulty-report", default=None,
                    help="grade_material_difficulty JSON; feeds measured EI per tier to the judge")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    paths = []
    for m in args.materials:
        paths += sorted(glob.glob(m)) if any(c in m for c in "*?[") else [m]
    paths = [p for p in paths if "report" not in pathlib.Path(p).stem]
    seed = json.loads(pathlib.Path(args.seed).read_text()) if args.seed else None
    ei_by_tier = _load_measured_ei(args.difficulty_report)

    rows = []
    for p in paths:
        mat = json.loads(pathlib.Path(p).read_text())
        tier = mat.get("tier") or mat.get("difficulty_level")
        try:
            r = judge_one(mat, seed, measured_ei=ei_by_tier.get(tier))
        except Exception as e:  # noqa: BLE001 — report the failure, keep going
            print(f"!! {pathlib.Path(p).name}: {e}")
            continue
        r["_file"] = pathlib.Path(p).stem
        rows.append(r)
        print(f"{r['_file']:28s} " + " ".join(f"{c[:4]}={r.get(c)}" for c in CRITERIA)
              + f"  bloom={r.get('achieved_bloom')}")

    L = ["# LLM-as-judge — Centri learning material (rubric 1–5, Utami 2025 Tables 8–9 + tiers)\n",
         f"Model: `{MODEL}`. Rubric: docs/eval-rubric-ika.md.",
         "Axes: authenticity/linguistic (Table 8), mathematical (Table 9), Centri physics/tier.\n",
         "| Material | Level | " + " | ".join(CRITERIA) + " | Bloom | Rationale |",
         "|---|---|" + "|".join(["---"] * len(CRITERIA)) + "|---|---|"]
    for r in rows:
        L.append(f"| {r['_file']} | {r['_level']} | "
                 + " | ".join(str(r.get(c, "—")) for c in CRITERIA)
                 + f" | {r.get('achieved_bloom', '—')} | {r.get('rationale', '')} |")

    def _mean(keys):
        vals = [r[c] for r in rows for c in keys if isinstance(r.get(c), (int, float))]
        return statistics.mean(vals) if vals else None

    L.append("\n## Means per axis\n| Axis | mean |\n|---|---|")
    for axis, keys in AXES.items():
        m = _mean(keys)
        if m is not None:
            L.append(f"| {axis} | {m:.2f} |")
    L.append("\n## Means per criterion\n| Criterion | mean |\n|---|---|")
    for c in CRITERIA:
        m = _mean([c])
        if m is not None:
            L.append(f"| {c} | {m:.2f} |")

    out = pathlib.Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L) + "\n")
    json.dump({"model": MODEL, "criteria": CRITERIA, "axes": AXES, "rows": rows},
              open(out.with_suffix(".json"), "w"), indent=2)
    print(f"\nreport -> {out}  ({len(rows)} materials judged)")


if __name__ == "__main__":
    main()
