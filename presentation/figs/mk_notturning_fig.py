#!/usr/bin/env python3
"""Provenance for figs/notturning_before.png — the "not turning" caption over a moving curve.

**This image CANNOT be regenerated from current code, and that is deliberate.** It is the shipped
`omega_t.png` for `computerfan-4029` as it stood on 2026-07-31 before
`figures._rest_label_is_contradicted` landed. Re-rendering that clip today produces the corrected
figure: the three false "not turning" captions are gone and the grey shading remains. The file is
therefore a **snapshot kept under version control**, copied from the workspace before the fix:

    cp workspaces/job_computerfan-4029/analysis_output/plots/omega_t.png \
       presentation/figs/notturning_before.png

That workspace was archived on 2026-08-06 (superseded by `job_computerfan-4029-2`, which has the
sticky-lock fix) and now lives at
`agent-backend/workspaces-archive/superseded-4029-pretrackerfix-20260806/job_computerfan-4029/`.

A "before" figure must never point at a live workspace path — the workspace is regenerated and the
slide would silently start showing the "after". This script exists to record where the bytes came
from and how to prove the defect is real, not to rebuild them.

To re-confirm the defect from the data alone (works at any commit, needs no old code):
    python3 presentation/figs/mk_notturning_fig.py
It prints, for every rest-labelled band in the corpus, the largest |omega| inside it — the numbers
quoted on the slide and in docs/axis4-multimodal-2026-07-31.md.
"""
import csv
import json
import pathlib

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2] / "agent-backend"
REST = {"INACTIVE", "IDLE"}


def spans(labels):
    """[(start, end, label)] — contiguous runs, same segmentation the renderer shades."""
    out, s = [], 0
    for i in range(1, len(labels) + 1):
        if i == len(labels) or labels[i] != labels[s]:
            out.append((s, i, labels[s]))
            s = i
    return out


def main():
    print(f"{'clip':20s} {'band':>16s} {'max |omega|':>12s}  verdict")
    for ws in sorted((ROOT / "workspaces").glob("job_*")):
        data = ws / "analysis_output" / "data"
        if not (data / "stats.json").exists():
            continue
        stats = json.loads((data / "stats.json").read_text())
        labels = (stats.get("phases") or {}).get("phase_labels") or []
        rows = list(csv.DictReader(open(data / "kinematics.csv")))
        om = np.abs(np.array([
            float(r["omega_rad_s"]) if r.get("omega_rad_s") not in (None, "", "nan") else np.nan
            for r in rows]))
        n = min(len(labels), len(om))
        if not n:
            continue
        ymax = np.nanmax(om[:n])
        for s, e, lab in spans(labels[:n]):
            if str(lab).upper() not in REST:
                continue
            seg = om[s:e][np.isfinite(om[s:e])]
            if seg.size == 0:
                continue
            peak = float(seg.max())
            bad = peak > max(0.05 * float(ymax), 1e-9)
            print(f"{ws.name.replace('job_',''):20s} {f'[{s}:{e}]':>16s} {peak:12.2f}  "
                  + ("CONTRADICTED — caption suppressed" if bad else "genuinely at rest"))


if __name__ == "__main__":
    main()
