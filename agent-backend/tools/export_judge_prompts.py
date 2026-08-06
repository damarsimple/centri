#!/usr/bin/env python3
"""Freeze the LLM-judge question for every worksheet, so a second judge answers the SAME one.

The rubric lives in run_llm_judge.py and is imported, never restated here. Each worksheet becomes
one file holding the exact `system` and `user` strings that run_llm_judge would send to the lab
Qwen. A different model — an agent, a hosted API, a human — can then be scored on the identical
question, and any difference in the numbers is a difference between RATERS rather than between two
hand-assembled prompts.

Usage:
  python tools/export_judge_prompts.py \
      --workspaces 'workspaces/job_*' --out /tmp/judge_prompts
"""
import argparse
import glob
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run_llm_judge import CRITERIA, build_prompt  # noqa: E402 — same rubric, one source

TIERS = ["basic", "intermediate", "advanced"]


def export(workspace, out_dir):
    """Write one prompt file per tier for a single workspace; returns the paths written."""
    data = pathlib.Path(workspace) / "analysis_output" / "data"
    clip = pathlib.Path(workspace).name.replace("job_", "")
    seed_path = data / "material_seed.json"
    seed = json.loads(seed_path.read_text()) if seed_path.exists() else None
    written = []
    for tier in TIERS:
        mat_path = data / f"material.{tier}.json"
        if not mat_path.exists():
            continue
        system, user, level = build_prompt(json.loads(mat_path.read_text()), seed)
        p = pathlib.Path(out_dir) / f"{clip}.{tier}.json"
        p.write_text(json.dumps({
            "clip": clip, "tier": tier, "level": level, "criteria": CRITERIA,
            "source": str(mat_path), "system": system, "user": user}, indent=2))
        written.append(p)
    return written


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspaces", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    paths = []
    for w in args.workspaces:
        paths += sorted(glob.glob(w)) if any(c in w for c in "*?[") else [w]
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    total = 0
    for w in paths:
        written = export(w, out)
        total += len(written)
        print(f"{pathlib.Path(w).name:28s} {len(written)} prompts")
    print(f"\n{total} prompts -> {out}")


if __name__ == "__main__":
    main()
