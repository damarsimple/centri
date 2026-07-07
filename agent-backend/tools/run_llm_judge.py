#!/usr/bin/env python3
"""LLM-as-judge for Centri learning material — the qualitative complement to BERTScore.

BERTScore measures surface relevance to a reference; the grounding gate measures arithmetic/
tier/vocab correctness. Neither rates whether the passage is a GOOD lesson. This tool asks the
lab Qwen to score each generated material on a fixed rubric (1–5) and to rate the Bloom level
the passage actually ACHIEVES (the deck's "Bloom-level column" commitment), so the asserted
difficulty ladder gets an independent, model-based signal to sit beside the model-free one from
grade_material_difficulty.py.

Rubric (per material, 1–5):
  relevance            — is it about THIS scene's circular motion, on-topic and useful?
  answerability        — could a learner act on it (understand / apply) after reading?
  difficulty_fit       — does the depth match its asserted level (basic/intermediate/advanced)?
  concept_accuracy     — is the physics correct (no misconceptions, right relations)?
  annotation_accuracy  — do the described figures/numbers match what the data supports?
plus achieved_bloom    — the Bloom level the passage reaches (Remember…Create).

TODO(IKA): fold in the IKA mathematics-paper judging criteria once Vinsa shares the paper.

Usage (run where PI_INFERENCE_URL is reachable, e.g. the worker or the lab machine):
  python tools/run_llm_judge.py \
      --materials material_work/<obj>/material.*.json \
      [--seed material_work/<obj>/material_seed.json] \
      --out material_work/_eval/llm_judge_report.md
"""
import argparse, json, glob, os, pathlib, re, statistics, urllib.request

BASE = os.environ.get("PI_INFERENCE_URL", "http://192.168.1.205:8083") + "/v1/chat/completions"
KEY = os.environ.get("PI_INFERENCE_API_KEY", "hwanglabyoungdumbandbreak")
MODEL = os.environ.get("PI_JUDGE_MODEL", os.environ.get("PI_MATERIAL_MODEL", "Qwen3.6-35B"))

CRITERIA = ["relevance", "answerability", "difficulty_fit",
            "concept_accuracy", "annotation_accuracy"]
BLOOM = ["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"]

SYSTEM = (
    "You are an expert physics-education assessor grading a SHORT learning passage about "
    "circular motion generated from a real video's measurements. Grade ONLY what is written. "
    "Be strict and consistent.\n\n"
    "Score each criterion 1–5 (5 = excellent):\n"
    "- relevance: on-topic for this scene's circular motion, and useful.\n"
    "- answerability: a learner could understand/apply the idea after reading.\n"
    "- difficulty_fit: the depth matches the asserted level ({level}). Basic = no equations, "
    "one idea at a time; intermediate = coordinates a few relations with numbers; advanced = "
    "integrates change-over-time, limits, proportionality.\n"
    "- concept_accuracy: the physics is correct — no misconceptions, relations right.\n"
    "- annotation_accuracy: the numbers and described figures are internally consistent and "
    "match what the measurements support.\n"
    "Also state achieved_bloom: the single Bloom level the passage actually reaches, one of "
    + ", ".join(BLOOM) + ".\n"
    "Return ONLY JSON: {\"relevance\":n,\"answerability\":n,\"difficulty_fit\":n,"
    "\"concept_accuracy\":n,\"annotation_accuracy\":n,\"achieved_bloom\":\"...\","
    "\"rationale\":\"one sentence\"}."
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


def judge_one(mat, seed=None):
    secs = mat.get("sections", mat)
    passage = "\n\n".join(f"## {k}\n{v}" for k, v in secs.items() if isinstance(v, str))
    level = mat.get("difficulty_level") or mat.get("tier") or "unspecified"
    ctx = ""
    if seed:
        vs = "; ".join(f"{v['symbol']}={v.get('value')}" for v in seed.get("variables", []))
        ctx = f"\n\nMeasured ground truth (for accuracy checks): {vs}"
    user = f"Asserted difficulty level: {level}\n\nPassage:\n{passage}{ctx}"
    res = _parse(_call(SYSTEM.format(level=level), user))
    res["_level"] = level
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--materials", nargs="+", required=True)
    ap.add_argument("--seed", default=None)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    paths = []
    for m in args.materials:
        paths += sorted(glob.glob(m)) if any(c in m for c in "*?[") else [m]
    paths = [p for p in paths if "report" not in pathlib.Path(p).stem]
    seed = json.loads(pathlib.Path(args.seed).read_text()) if args.seed else None

    rows = []
    for p in paths:
        mat = json.loads(pathlib.Path(p).read_text())
        try:
            r = judge_one(mat, seed)
        except Exception as e:  # noqa: BLE001 — report the failure, keep going
            print(f"!! {pathlib.Path(p).name}: {e}")
            continue
        r["_file"] = pathlib.Path(p).stem
        rows.append(r)
        print(f"{r['_file']:28s} " + " ".join(f"{c[:4]}={r.get(c)}" for c in CRITERIA)
              + f"  bloom={r.get('achieved_bloom')}")

    L = ["# LLM-as-judge — Centri learning material (rubric, 1–5)\n",
         f"Model: `{MODEL}`. Criteria: {', '.join(CRITERIA)} + achieved Bloom level.",
         "> TODO(IKA): add the IKA-paper judging criteria once available.\n",
         "| Material | Level | " + " | ".join(CRITERIA) + " | Bloom | Rationale |",
         "|---|---|" + "|".join(["---"] * len(CRITERIA)) + "|---|---|"]
    for r in rows:
        L.append(f"| {r['_file']} | {r['_level']} | "
                 + " | ".join(str(r.get(c, "—")) for c in CRITERIA)
                 + f" | {r.get('achieved_bloom', '—')} | {r.get('rationale', '')} |")
    L.append("\n## Means per criterion\n| Criterion | mean |\n|---|---|")
    for c in CRITERIA:
        vals = [r[c] for r in rows if isinstance(r.get(c), (int, float))]
        if vals:
            L.append(f"| {c} | {statistics.mean(vals):.2f} |")
    out = pathlib.Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L) + "\n")
    print(f"\nreport -> {out}  ({len(rows)} materials judged)")


if __name__ == "__main__":
    main()
