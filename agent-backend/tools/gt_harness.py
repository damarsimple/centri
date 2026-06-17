#!/usr/bin/env python3
"""Ground-truth + determinism harness for the frozen analysis pipeline.

Two things it proves, the two failures we set out to fix:

  1. DETERMINISM — run `analysis.run` twice on the same reconstructed inputs and
     assert byte-identical stats.json. (The old agent-authored code produced 28
     distinct schemas across 30 jobs.)

  2. ACCURACY — compare the pipeline's period / mean omega against the phone-gyro
     ground truth in /home/damar/new-case/<video>.csv (gyro_gamma = the
     screen-perpendicular spin axis, deg/s).

Because running the full pi agent is expensive, the harness reconstructs the
perception->math handoff (pipeline_inputs.json) from an existing job's saved
state files via `build_inputs_from_job`. That exercises the exact code path the
seeded pipeline runs in production.

Usage:
    python tools/gt_harness.py                      # all jobs it can map
    python tools/gt_harness.py <job_dir> [<job_dir> ...]
"""
from __future__ import annotations

import csv
import glob
import json
import math
import os
import shutil
import statistics as st
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
NEW_CASE = Path("/home/damar/new-case")

# Map a source video stem to its gyro CSV.
GT_CSV = {p.stem: p for p in NEW_CASE.glob("IMG_*.csv")} if NEW_CASE.exists() else {}


def gyro_truth(video_stem: str) -> dict | None:
    """Ground-truth mean/peak omega (rad/s) and period (s) from gyro_gamma."""
    csv_path = GT_CSV.get(video_stem)
    if not csv_path:
        return None
    g = []
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            g.append(float(row["gyro_gamma"]))
    peak = max(abs(v) for v in g)
    active = [abs(v) for v in g if abs(v) > 0.2 * peak]
    mean_degs = st.mean(active) if active else 0.0
    mean_omega = math.radians(mean_degs)
    return {
        "mean_omega": mean_omega,
        "peak_omega": math.radians(peak),
        "period_s": (2 * math.pi / mean_omega) if mean_omega else None,
    }


class SkipJob(Exception):
    """Job lacks the state files needed to reconstruct the input contract."""


def build_inputs_from_job(job_dir: Path) -> dict:
    """Reconstruct pipeline_inputs.json from a job's saved perception state."""
    d = job_dir / "analysis_output" / "data"
    need = ("step1_meta.json", "step2_state.json", "step4_state.json", "step6_state.json")
    missing = [f for f in need if not (d / f).exists()]
    if missing:
        raise SkipJob(f"missing {missing}")
    s1 = json.load(open(d / "step1_meta.json"))
    s2 = json.load(open(d / "step2_state.json"))
    s4 = json.load(open(d / "step4_state.json"))
    s6 = json.load(open(d / "step6_state.json"))

    n = int(s2["NB_FRAMES"])
    tracked = s2["tracked_label"]
    # Raw per-frame centroid of the tracked object, cropped-video space.
    by_frame = {pt["frame"]: pt for pt in s2["trajectories"][tracked]}
    xs = [by_frame[i]["cx"] if i in by_frame else None for i in range(n)]
    ys = [by_frame[i]["cy"] if i in by_frame else None for i in range(n)]

    return {
        "fps": float(s2["FPS"]),
        "duration_s": float(s1["duration_s"]),
        "n_raw_frames": n,
        "object_name": s2.get("object_name", s1.get("object_name", tracked)),
        "tracked_label": tracked,
        "ref_label": s2.get("ref_label", s1.get("ref_label", "")),
        "trajectory_x_px": xs,
        "trajectory_y_px": ys,
        "center": {
            "cx_px": float(s4["cx_calibration"]),
            "cy_px": float(s4["cy_calibration"]),
            "source": "user_mark" if s4.get("user_center_used") else "bootstrap",
        },
        "reference": {
            "diameter_px": float(s6["diameter_px"]),
            "physical_size_m": float(s6["physical_size_m"]),
            "physical_size_source": str(s6["physical_size_source"]),
        },
        "roi_crop": {
            "x_off": int(s2["x_off"]), "y_off": int(s2["y_off"]),
            "crop_w": int(s2["crop_w"]), "crop_h": int(s2["crop_h"]),
            "fallback": bool(s2["use_full_frame"]),
        },
    }


def run_pipeline(inputs: dict) -> str:
    """Run analysis.run in a throwaway workspace; return raw stats.json text."""
    work = Path(tempfile.mkdtemp(prefix="gt_"))
    try:
        shutil.copytree(REPO / "workspace_lib" / "analysis", work / "analysis")
        data = work / "analysis_output" / "data"
        data.mkdir(parents=True)
        (data / "pipeline_inputs.json").write_text(json.dumps(inputs))
        proc = subprocess.run(
            [sys.executable, "-m", "analysis.run"],
            cwd=work, capture_output=True, text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"pipeline exited {proc.returncode}\n{proc.stderr}")
        return (data / "stats.json").read_text()
    finally:
        shutil.rmtree(work, ignore_errors=True)


def video_stem_for(job_dir: Path) -> str | None:
    for mp4 in job_dir.glob("IMG_*.mp4"):
        return mp4.stem
    return None


def check_job(job_dir: Path) -> tuple[bool, str | None, float | None, float | None]:
    inputs = build_inputs_from_job(job_dir)
    a = run_pipeline(inputs)
    b = run_pipeline(inputs)
    deterministic = (a == b)

    s = json.loads(a)
    period = s["period_and_frequency"]["period_s"]
    mean_omega = s["summary"]["mean_omega"]
    stem = video_stem_for(job_dir)
    gt = gyro_truth(stem) if stem else None

    print(f"\n=== {job_dir.name[:18]}  video={stem} ===")
    print(f"  determinism : {'PASS (byte-identical x2)' if deterministic else 'FAIL'}")
    print(f"  period_s    : {period:.3f}" + (f"   gyro≈{gt['period_s']:.3f}" if gt and gt['period_s'] else ""))
    print(f"  mean_omega  : {mean_omega:.3f}" + (f"   gyro≈{gt['mean_omega']:.3f}" if gt else ""))
    if gt and gt["mean_omega"]:
        err = abs(mean_omega - gt["mean_omega"]) / gt["mean_omega"] * 100
        print(f"  omega error : {err:.1f}% vs gyro (note: video clip & sensor windows differ)")
    print(f"  flags       : {s['validation_flags']}")
    return deterministic, stem, period, mean_omega


def main(argv: list[str]) -> int:
    if argv:
        jobs = [Path(a) for a in argv]
    else:
        ws = REPO / "workspaces"
        jobs = sorted({Path(p).parent.parent.parent for p in
                       glob.glob(str(ws / "job_*/analysis_output/data/step2_state.json"))})
    runnable = [j for j in jobs if (j / "analysis_output/data/step2_state.json").exists()]
    skipped = [j for j in jobs if j not in runnable]
    for j in skipped:
        print(f"SKIP {j.name[:18]} — no step2_state.json (legacy ad-hoc handoff; "
              f"the pipeline_inputs.json contract removes this variance going forward)")
    if not runnable:
        print("No jobs with reconstructable inputs found.")
        return 1

    ok, by_video = True, {}
    for j in runnable:
        try:
            det, stem, period, _ = check_job(j)
        except SkipJob as e:
            print(f"SKIP {j.name[:18]} — {e} (legacy ad-hoc handoff)")
            continue
        ok = ok and det
        if stem and period:
            by_video.setdefault(stem, []).append(period)

    # Same video -> same data: report cross-job period spread per video.
    print("\n--- cross-run period spread per video (same video should agree) ---")
    for stem, ps in sorted(by_video.items()):
        if len(ps) > 1:
            spread = (max(ps) - min(ps)) / min(ps) * 100
            print(f"  {stem}: {len(ps)} runs  {min(ps):.3f}-{max(ps):.3f}s  ({spread:.1f}% spread)")
        else:
            print(f"  {stem}: 1 run  {ps[0]:.3f}s")

    print(f"\n{'ALL DETERMINISTIC' if ok else 'DETERMINISM FAILURES PRESENT'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main([a for a in sys.argv[1:]]))
