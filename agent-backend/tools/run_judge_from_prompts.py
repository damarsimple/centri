#!/usr/bin/env python3
"""Score the frozen judge prompts (tools/export_judge_prompts.py) and emit judge_<clip>.md.

Two sources, one output format, so build_pmagic_tables.py can read either rater's directory
without knowing which model produced it:

  --model NAME    POST each frozen prompt to the lab inference endpoint (the local Qwen path).
  --from-json DIR read scores that were produced elsewhere — e.g. by agents given the identical
                  prompt files — as <clip>.json holding a list of per-tier score objects.

Comparing two raters is only meaningful if they answered the same question, which is why nothing
here rebuilds a prompt: the frozen file is sent verbatim.

Usage:
  python tools/run_judge_from_prompts.py --prompts /tmp/judge_prompts \
      --out material_work/_eval/judge_qwen_2026-07-31 --model Qwen3.6-35B
  python tools/run_judge_from_prompts.py --prompts /tmp/judge_prompts \
      --out material_work/_eval/judge_claude_2026-07-31 --from-json /tmp/judge_claude \
      --label 'Claude Opus 5 (subagent per clip)'
"""
import argparse
import collections
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run_llm_judge import CRITERIA, _call, _parse  # noqa: E402 — same rubric, same transport

TIERS = ["basic", "intermediate", "advanced"]


def load_prompts(prompt_dir):
    """{clip: {tier: prompt_dict}} from the frozen prompt files."""
    out = collections.defaultdict(dict)
    for p in sorted(pathlib.Path(prompt_dir).glob("*.json")):
        d = json.loads(p.read_text())
        out[d["clip"]][d["tier"]] = d
    return out


def score_via_api(prompt, model):
    import run_llm_judge
    run_llm_judge.MODEL = model
    return _parse(_call(prompt["system"], prompt["user"]))


def load_external(from_json, clip):
    """{tier: scores} from a pre-scored <clip>.json (a list of per-tier objects)."""
    p = pathlib.Path(from_json) / f"{clip}.json"
    if not p.exists():
        return {}
    rows = json.loads(p.read_text())
    if isinstance(rows, dict):
        rows = rows.get("rows", [])
    return {r.get("tier"): r for r in rows}


def report(clip, rows, label):
    """One judge_<clip>.md in the exact shape read by build_pmagic_tables.read_judge."""
    L = ["# LLM-as-judge — Centri learning material (text axes 1–3, 1–5; reconciled Utami+P-MAGIC)\n",
         f"Model: `{label}`. Rubric: docs/eval-framework.md + docs/eval-rubric-ika.md.",
         "Scored from the frozen prompts (tools/export_judge_prompts.py) — byte-identical to "
         "every other rater's.\n",
         "| Material | Level | " + " | ".join(CRITERIA) + " | Bloom | Rationale |",
         "|---|---|" + "|".join(["---"] * len(CRITERIA)) + "|---|---|"]
    for tier in TIERS:
        r = rows.get(tier)
        if not r:
            continue
        L.append(f"| material.{tier} | {tier} | "
                 + " | ".join(str(r.get(c, "—")) for c in CRITERIA)
                 + f" | {r.get('achieved_bloom', '—')} | {r.get('rationale', '')} |")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompts", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default=None, help="score by calling the inference endpoint")
    ap.add_argument("--from-json", default=None, help="score from pre-scored <clip>.json files")
    ap.add_argument("--label", default=None, help="model name written into the report header")
    args = ap.parse_args()
    if bool(args.model) == bool(args.from_json):
        ap.error("give exactly one of --model / --from-json")

    prompts = load_prompts(args.prompts)
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    label = args.label or args.model or "external"

    all_rows, missing = [], []
    for clip, by_tier in sorted(prompts.items()):
        external = load_external(args.from_json, clip) if args.from_json else None
        rows = {}
        for tier in TIERS:
            if tier not in by_tier:
                continue
            if external is not None:
                r = external.get(tier)
                if r is None:
                    missing.append(f"{clip}.{tier}")
                    continue
            else:
                try:
                    r = score_via_api(by_tier[tier], args.model)
                except Exception as e:  # noqa: BLE001 — report and keep going
                    print(f"!! {clip}.{tier}: {e}")
                    missing.append(f"{clip}.{tier}")
                    continue
            bad = [c for c in CRITERIA if not isinstance(r.get(c), int) or not 1 <= r[c] <= 5]
            if bad:
                print(f"!! {clip}.{tier}: not an integer 1–5: {bad}")
            rows[tier] = r
            all_rows.append({"clip": clip, "tier": tier, **{c: r.get(c) for c in CRITERIA},
                             "achieved_bloom": r.get("achieved_bloom"),
                             "rationale": r.get("rationale", "")})
        (out / f"judge_{clip}.md").write_text(report(clip, rows, label))
        print(f"{clip:20s} {len(rows)}/3")

    (out / "rows.json").write_text(json.dumps({"label": label, "criteria": CRITERIA,
                                               "rows": all_rows}, indent=2))
    print(f"\n{len(all_rows)} scored -> {out}")
    if missing:
        print(f"MISSING ({len(missing)}): {', '.join(missing)}")


if __name__ == "__main__":
    main()
