"""Entry point: `python -m analysis.run` (run from the job workspace root).

Reads analysis_output/data/pipeline_inputs.json (written by the agent's
perception steps), then deterministically produces kinematics.csv and stats.json.
The agent must NOT reimplement any of this — it only calls it.
"""
from __future__ import annotations

import sys
from pathlib import Path

from . import common, writer
from .contract import ContractError, load_inputs
from .geometry import calibrate
from .kinematics import compute


def main() -> int:
    common.reset_rng()
    Path("analysis_output/data").mkdir(parents=True, exist_ok=True)
    common.progress("kinematics", "Measuring speed and acceleration", 68)
    try:
        inp = load_inputs()
    except ContractError as e:
        common.log(f"[run] CONTRACT ERROR: {e}")
        print(f"CONTRACT ERROR: {e}", file=sys.stderr)
        return 2

    cal, x_full, y_full = calibrate(inp)
    k = compute(inp, cal, x_full, y_full)
    stats = writer.write_stats(inp, cal, k)
    writer.write_csv(inp, cal, k)

    common.progress("kinematics", "Kinematics complete", 72)
    common.log("[run] pipeline complete")
    # Echo a compact summary for the orchestrator's log.
    print(f"OK period_s={stats['period_and_frequency']['period_s']} "
          f"mean_omega={stats['summary']['mean_omega']} "
          f"flags={stats['validation_flags']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
