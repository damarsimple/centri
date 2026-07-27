"""Locked output contract: kinematics.csv + stats.json + a sanity gate.

This is the single place stats.json is written. The key order and nesting here
ARE the contract — downstream consumers (LaTeX report, the three subagents,
app/result_data.py) may rely on it. Two hard guarantees:

  * `json.dump(..., allow_nan=False)` — a stray NaN raises instead of emitting
    invalid JSON (17 of 30 old jobs shipped bare `NaN`). `_num()` converts any
    NaN/inf to null up front so legitimately-missing values serialize cleanly.
  * Fixed schema every run — no agent improvisation, so "same inputs ->
    byte-identical stats.json".
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from . import common
from .contract import Inputs
from .geometry import Calibration
from .kinematics import Kinematics

DATA = Path("analysis_output/data")


def _num(x):
    """JSON-safe scalar: NaN/inf/None -> None, else float."""
    if x is None:
        return None
    try:
        xf = float(x)
    except (TypeError, ValueError):
        return None
    return None if (math.isnan(xf) or math.isinf(xf)) else xf


class GateError(RuntimeError):
    """Raised when the finished stats.json fails a sanity gate."""


def _gate(stats: dict, cal: Calibration) -> None:
    """Cheap post-hoc sanity checks. These flag; only schema/NaN issues abort."""
    if cal.tracking_coverage_pct < 50:
        common.set_validation_flag("low_tracking_coverage")
    if cal.center_drift_px > 100 and cal.center_source in ("user_mark", "bootstrap"):
        common.set_validation_flag("high_center_drift")
    p = stats["period_and_frequency"]["period_s"]
    if p is None or p <= 0:
        common.set_validation_flag("invalid_period")


def write_csv(inp: Inputs, cal: Calibration, k: Kinematics) -> None:
    # x_px,y_px are the tracked centroid in CROPPED-video space (same space as the
    # center cx_px/cy_px and everything else in stats.json) — appended last so
    # existing column order is unchanged. Figures must plot geometry from THESE,
    # not from api_cache.json (which is raw full-frame space and will be offset by
    # the crop by exactly roi_crop.y_off — the cause of the "circle off the points"
    # figure bug). null where the detector missed the frame.
    # omega/ac_uncorrected are the same measurement BEFORE the camera-angle correction, and
    # exist only on a rectified clip. Appended last, and the columns are only emitted when
    # there is something to put in them, so every existing reader of this file is unaffected.
    pre = k.omega_uncorrected.size == inp.n_raw_frames and k.ac_uncorrected.size == inp.n_raw_frames
    header = "time_s,r_px,r_m,theta_rad,omega_rad_s,v_m_s,ac_m_s2,active,x_px,y_px"
    lines = [header + (",omega_rad_s_uncorrected,ac_m_s2_uncorrected" if pre else "")]
    for i in range(inp.n_raw_frames):
        def f(v):
            return "" if (v is None or (isinstance(v, float) and math.isnan(v))) else f"{v:.6f}"
        row = [
            f"{k.t_s[i]:.6f}",
            f(k.r_px[i]), f(k.r_m[i]),              # real radius, not dx (old bug)
            f(k.theta_unwrapped[i]), f(k.omega[i]),
            f(k.v_m_s[i]), f(k.ac_m_s2[i]),
            "1" if k.active_mask[i] else "0",
            f(k.x_px[i]), f(k.y_px[i]),             # cropped centroid (cleaned + gap-filled)
        ]
        if pre:
            row += [f(k.omega_uncorrected[i]), f(k.ac_uncorrected[i])]
        lines.append(",".join(row))
    (DATA / "kinematics.csv").write_text("\n".join(lines) + "\n")
    common.log(f"[writer] kinematics.csv written ({inp.n_raw_frames} rows)")


def build_stats(inp: Inputs, cal: Calibration, k: Kinematics) -> dict:
    """The locked schema. Edit deliberately — this is the public contract."""
    return {
        "schema_version": 1,
        "object_name": inp.object_name,
        "scene_title": inp.scene_title,
        "tracked_label": inp.tracked_label,
        "ref_label": inp.ref_label,
        "coordinate_space": "cropped-video",
        "video_info": {
            "fps": _num(inp.fps),
            "duration_s": _num(inp.duration_s),
            "n_raw_frames": int(inp.n_raw_frames),
        },
        "tracking": {
            "coverage_pct": _num(cal.tracking_coverage_pct),
            "n_valid_frames": int(cal.n_valid_frames),
            "n_inliers": int(cal.n_inliers),
            "n_outliers_rejected": int(cal.n_outliers_rejected),
            "active_duration_s": _num(k.active_duration_s),
            "active_start_s": _num(k.active_start_s),
            "active_end_s": _num(k.active_end_s),
            "n_interpolated_frames": int(k.n_interpolated),
        },
        "calibration": {
            "cx_px": _num(cal.cx_px),
            "cy_px": _num(cal.cy_px),
            "center_source": cal.center_source,
            "center_drift_px": _num(cal.center_drift_px),
            "px_per_m": _num(cal.px_per_m),
            "diameter_px": _num(cal.diameter_px),
            "physical_size_m": _num(cal.physical_size_m),
            "physical_size_source": cal.physical_size_source,
            "r_fit_px": _num(cal.r_fit_px),
            "r_fit_m": _num(cal.r_fit_m),
            # Whether the orbit was un-projected before any angle was measured, and if
            # not, why not. Always present so a reader never has to guess (rectify.py).
            "rectification": cal.rectification,
        },
        "summary": {
            "mean_r_m": _num(k.mean_r_m),
            "std_r_m": _num(k.std_r_m),
            "mean_omega": _num(k.mean_omega),
            "std_omega": _num(k.std_omega),
            "mean_v": _num(k.mean_v),
            "mean_ac": _num(k.mean_ac),
            "max_ac": _num(k.max_ac),
            "rotation_direction": k.rotation_direction,
        },
        "period_and_frequency": {
            "period_s": _num(k.period_s),
            "frequency_hz": _num(k.frequency_hz),
            "T_primary": _num(k.T_primary),
            "T_fft": _num(k.T_fft),
            "period_discrepancy": _num(k.period_discrepancy),
        },
        "stable_phase": {
            "stable_mean_omega": _num(k.stable_mean_omega),
            "stable_mean_ac": _num(k.stable_mean_ac),
            "stable_omega_r2": _num(k.stable_omega_r2),
            "stable_omega_std_err": _num(k.stable_omega_std_err),
            "n_stable_segments": int(k.n_stable_segments),
        },
        "phase_boundaries": {
            "increase_start_omega": _num(k.increase_start_omega),
            "increase_end_omega": _num(k.increase_end_omega),
            "decrease_end_omega": _num(k.decrease_end_omega),
        },
        "angular_acceleration": {
            "motion_type": k.motion_type,
            "alpha_rad_s2": _num(k.alpha_rad_s2),
            # d|omega|/dt — alpha along the direction of travel. This is what decides
            # speeding-up vs slowing-down and what a_t is built from (kinematics.py).
            "alpha_along_rad_s2": _num(k.alpha_along_rad_s2),
            "alpha_r2": _num(k.alpha_r2),
            "omega_initial": _num(k.omega_initial),
            "omega_final": _num(k.omega_final),
            "a_t_mean_m_s2": _num(k.a_t_mean_m_s2),
            "fit_window_s": _num(k.fit_window_s),
            "impulsive_start": bool(k.impulsive_start),
        },
        "roi_crop": inp.roi_crop,
        "validation_flags": common.validation_flags(),
        "phases": {
            "phase_labels": k.phase_labels,
            "stable_segments": k.stable_segments,
        },
    }


def write_stats(inp: Inputs, cal: Calibration, k: Kinematics) -> dict:
    stats = build_stats(inp, cal, k)
    _gate(stats, cal)
    stats["validation_flags"] = common.validation_flags()  # refresh after gate
    with open(DATA / "stats.json", "w") as f:
        json.dump(stats, f, indent=2, allow_nan=False)      # invalid JSON -> raise
    common.log(f"[writer] stats.json written (flags={stats['validation_flags']})")
    return stats
