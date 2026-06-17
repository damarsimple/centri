"""Deterministic figure QA (part 'c' of the figure-verification flow).

The figure subagent is an LLM; it has twice plotted trajectory geometry from the
raw full-frame `api_cache.json` instead of the cropped `kinematics.csv` columns,
leaving the fitted circle floating `roi_crop.y_off` px off the points. A prompt
HARD RULE did not hold. This check makes that class of error **impossible to ship**:

The subagent must write `plots/figure_qa.json` reporting the min/max of the exact
x/y arrays it passed to the trajectory scatter. We recompute the truth from
`kinematics.csv` (`x_px,y_px`, the cropped series the kinematics used) and fail if
the plotted bounds don't match — a full-frame plot is off by the crop offset and is
caught immediately. Run as `python -m analysis.verify_figures`; exit 0 pass, 1 fail.
On fail it writes `plots/figure_verify.json` with a feedback message the orchestrator
injects into the retry.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

PLOTS = Path("analysis_output/plots")
DATA = Path("analysis_output/data")
QA_IN = PLOTS / "figure_qa.json"
REPORT = PLOTS / "figure_verify.json"


def _kinematics_bounds() -> dict | None:
    """True cropped trajectory extent from kinematics.csv (x_px,y_px)."""
    path = DATA / "kinematics.csv"
    if not path.exists():
        return None
    xs, ys = [], []
    with path.open() as f:
        for row in csv.DictReader(f):
            x, y = row.get("x_px", ""), row.get("y_px", "")
            if x and y:
                xs.append(float(x))
                ys.append(float(y))
    if not xs:
        return None
    return {"x_min": min(xs), "x_max": max(xs), "y_min": min(ys), "y_max": max(ys)}


def verify() -> tuple[bool, list[str]]:
    fails: list[str] = []

    truth = _kinematics_bounds()
    if truth is None:
        return False, ["kinematics.csv missing or has no x_px,y_px — cannot verify figures."]

    if not QA_IN.exists():
        return False, [
            "plots/figure_qa.json not found. The figure subagent MUST write it, "
            "reporting the min/max of the exact x/y arrays it passed to the "
            "trajectory scatter, e.g. "
            '{"trajectory": {"x_min":..,"x_max":..,"y_min":..,"y_max":..,'
            '"source":"kinematics.csv:x_px,y_px"}}.'
        ]

    try:
        qa = json.loads(QA_IN.read_text())
        traj = qa["trajectory"]
        px = {k: float(traj[k]) for k in ("x_min", "x_max", "y_min", "y_max")}
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        return False, [f"plots/figure_qa.json malformed ({e}); need trajectory x/y min/max."]

    # Tolerance scaled to the orbit: 8% of the larger plotted span. A full-frame
    # plot is offset by the crop, far exceeding this; honest jitter is well within.
    span = max(truth["x_max"] - truth["x_min"], truth["y_max"] - truth["y_min"], 1.0)
    tol = 0.08 * span
    for k in ("x_min", "x_max", "y_min", "y_max"):
        d = abs(px[k] - truth[k])
        if d > tol:
            fails.append(
                f"trajectory {k}={px[k]:.1f} differs from kinematics.csv {truth[k]:.1f} "
                f"by {d:.1f}px (> {tol:.1f} tol). You plotted the WRONG coordinate space — "
                f"plot x_px,y_px from kinematics.csv (cropped), NOT api_cache.json "
                f"(full-frame). The offset ≈ roi_crop.y_off is the tell."
            )
    return (not fails), fails


def main() -> int:
    ok, fails = verify()
    PLOTS.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({"passed": ok, "failures": fails}, indent=2))
    if ok:
        print("FIGURE_VERIFY OK")
        return 0
    print("FIGURE_VERIFY FAIL")
    for f in fails:
        print(f"  - {f}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
