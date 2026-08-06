#!/usr/bin/env python3
"""Freeze the Axis-4 (multimodal) judge question — the figures, not the prose.

Axis 1-3 are text and are handled by export_judge_prompts.py. Axis 4 asks whether the FIGURES
beside a passage are correct, labelled and relevant, so the rater has to see the images. Each
worksheet becomes one file naming the exact image paths for that tier, together with the render
manifest's claim about what each image shows.

**Modalities are per TIER, not per clip.** `report.TIER_ARTIFACTS` decides what is printed beside
each tier, and the basic tier ships **no table**. Its four table criteria are therefore NOT
APPLICABLE rather than bad — scoring an absent modality would penalise a tier for a figure it
deliberately never showed. That distinction is the reason this exporter exists instead of a flag
on the text one.

Usage:
  python tools/export_multimodal_prompts.py --workspaces 'workspaces/job_*' --out /tmp/mm_prompts
"""
import argparse
import glob
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "workspace_lib"))
from run_llm_judge import build_multimodal_prompt  # noqa: E402 — one rubric

TIERS = ["basic", "intermediate", "advanced"]

# Which concrete figures each tier prints, and which rubric modality each one belongs to. Mirrors
# analysis/render/report.py TIER_ARTIFACTS; kept here as data so this tool does not import the
# renderer (which pulls in matplotlib and the whole analysis stack).
TIER_FIGURES = {
    "basic": {
        "image": ["annotated_image_basic.png"],
        "graph": ["angle_points_basic.png", "trajectory_basic.png"],
    },
    "intermediate": {
        "image": ["annotated_image.png"],
        "graph": ["omega_t.png", "trajectory.png"],
        "table": ["annotated_table.png"],
    },
    "advanced": {
        "image": ["annotated_image.png"],
        "graph": ["omega_t.png", "ac_t.png", "trajectory.png"],
        "table": ["annotated_table.png"],
    },
}
# The annotated frame carries the overlays, so any tier showing an image can be asked about them.
VIDEO_MODALITY_NEEDS = "image"


def export(workspace, out_dir):
    data = pathlib.Path(workspace) / "analysis_output" / "data"
    plots = pathlib.Path(workspace) / "analysis_output" / "plots"
    clip = pathlib.Path(workspace).name.replace("job_", "")

    seed_path = data / "material_seed.json"
    seed = json.loads(seed_path.read_text()) if seed_path.exists() else None
    qa_path = plots / "figure_qa.json"
    qa = json.loads(qa_path.read_text()) if qa_path.exists() else {}
    claims_all = qa.get("annotations", {})

    written = []
    for tier in TIERS:
        mat_path = data / f"material.{tier}.json"
        if not mat_path.exists():
            continue
        wanted = TIER_FIGURES[tier]
        images, present, missing = [], set(), []
        for modality, names in wanted.items():
            found = [str(plots / n) for n in names if (plots / n).exists()]
            missing += [n for n in names if not (plots / n).exists()]
            if found:
                present.add(modality)
                images += found
        if VIDEO_MODALITY_NEEDS in present:
            present.add("video")

        claims = {k: v for k, v in claims_all.items()
                  if any(pathlib.Path(i).name == k for i in images)}
        system, user, crits = build_multimodal_prompt(
            json.loads(mat_path.read_text()), present, figure_claims=claims, seed=seed)

        p = pathlib.Path(out_dir) / f"{clip}.{tier}.json"
        p.write_text(json.dumps({
            "clip": clip, "tier": tier, "criteria": crits,
            "modalities_present": sorted(present),
            "modalities_absent": sorted(set(TIER_FIGURES["advanced"]) - present),
            "images": images, "missing_figures": missing,
            "system": system, "user": user}, indent=2))
        written.append((p, len(crits), len(images), missing))
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
        for p, ncrit, nimg, missing in export(w, out):
            total += 1
            warn = f"  MISSING {missing}" if missing else ""
            print(f"{p.stem:34s} {ncrit:2d} criteria, {nimg} images{warn}")
    print(f"\n{total} prompts -> {out}")


if __name__ == "__main__":
    main()
