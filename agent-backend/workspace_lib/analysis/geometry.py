"""Calibration & trajectory cleaning (old steps 5-6), made deterministic.

Lifted verbatim from a known-good run (job 1fc6311f) except:
  * RANSAC samples from the seeded `common.RNG` instead of np.random  → identical
    circle fit every run (the old code's center_drift swung 8.9->1013 px).
  * `physical_size_source` is carried through as the provenance STRING, never the
    numeric value (the old agent code wrote 0.3 into that field by mistake).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import common
from .contract import Inputs
from .rectify import rectify


@dataclass
class Calibration:
    cx_px: float            # rotation center used downstream (cropped space)
    cy_px: float
    center_source: str
    center_drift_px: float  # distance between RANSAC fit center and the mark
    px_per_m: float
    physical_size_m: float
    physical_size_source: str
    diameter_px: float
    r_fit_px: float         # orbit radius of the tracked object
    r_fit_m: float
    n_inliers: int
    n_valid_frames: int
    n_outliers_rejected: int
    tracking_coverage_pct: float
    # How (and whether) the orbit was un-projected before any angle was measured.
    # Always present so stats.json can state the reason it was NOT done. See rectify.py.
    rectification: dict = field(default_factory=dict)


def _radius_cv(x, y, cx, cy) -> float:
    """Coefficient of variation of the per-point radius about (cx, cy). Low for a
    true center, high when the center is off the orbit axis."""
    r = np.sqrt((x - cx)**2 + (y - cy)**2)
    return float(r.std() / max(r.mean(), 1e-9))


def _ransac_circle_fit(x, y, n_iters=1000, threshold=8.0, min_inliers=20):
    """Circumcircle RANSAC. Deterministic: draws from common.RNG."""
    n = len(x)
    if n < 3:
        return None, None, None, np.zeros(n, dtype=bool)

    best_inliers = np.zeros(n, dtype=bool)
    best_params = None
    for _ in range(n_iters):
        idx = common.RNG.choice(n, 3, replace=False)
        xp, yp = x[idx], y[idx]
        D = 2 * (xp[0] * (yp[1] - yp[2]) + xp[1] * (yp[2] - yp[0]) + xp[2] * (yp[0] - yp[1]))
        if abs(D) < 1e-10:
            continue
        ux = ((xp[0]**2 + yp[0]**2) * (yp[1] - yp[2]) +
              (xp[1]**2 + yp[1]**2) * (yp[2] - yp[0]) +
              (xp[2]**2 + yp[2]**2) * (yp[0] - yp[1])) / D
        uy = ((xp[0]**2 + yp[0]**2) * (xp[2] - xp[1]) +
              (xp[1]**2 + yp[1]**2) * (xp[0] - xp[2]) +
              (xp[2]**2 + yp[2]**2) * (xp[1] - xp[0])) / D
        r = np.sqrt((xp[0] - ux)**2 + (yp[0] - uy)**2)
        dists = np.sqrt((x - ux)**2 + (y - uy)**2)
        inliers = np.abs(dists - r) < threshold
        if int(inliers.sum()) > best_inliers.sum():
            best_inliers = inliers
            best_params = (ux, uy, r)
            if int(inliers.sum()) >= min_inliers * 5:
                break
    if best_params is None:
        return None, None, None, np.zeros(n, dtype=bool)
    return best_params[0], best_params[1], best_params[2], best_inliers


def calibrate(inp: Inputs) -> tuple[Calibration, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Returns (Calibration, x_kin, y_kin, x_img, y_img).

    `x_kin`/`y_kin` are the coordinates every ANGLE is measured from — rectified onto
    the orbit's own plane when the clip has real perspective. `x_img`/`y_img` are the
    same frames in IMAGE space, and are what the renderers must draw: a rectified point
    plotted on unrectified footage lands off the object, which is the whole reason the
    marker used to float. Cleaning (outlier rejection) is applied to both together so a
    frame is either present in both or absent from both.
    """
    common.step_start("step5")
    x_img = inp.x_px.copy()
    y_img = inp.y_px.copy()
    n_raw_frames = inp.n_raw_frames

    # Un-project BEFORE anything geometric is measured. A circle filmed with real
    # perspective images as an ellipse whose centre is not the imaged axle, and both
    # effects distort ANGLE once per revolution — so a radius or a theta taken from the
    # raw image is already wrong. Needs `hub_px` (the imaged axle) from the agent; with
    # no hub, or on a near-affine clip, this returns the input untouched and records why.
    x_full, y_full, rect_centre, rect = rectify(x_img, y_img, inp.hub_px)
    if rect.applied:
        common.set_validation_flag("orbit_rectified")
        common.log(f"[calibrate] rectified: hub offset {rect.hub_offset_px:.1f}px, "
                   f"tilt {rect.tilt_deg:.1f}deg, radial residual "
                   f"{rect.radial_residual_before_pct:.2f}% -> "
                   f"{rect.radial_residual_after_pct:.2f}%")
    elif inp.hub_px is not None:
        common.log(f"[calibrate] rectification skipped: {rect.reason}")

    valid_mask = ~np.isnan(x_full) & ~np.isnan(y_full)
    n_valid_frames = int(valid_mask.sum())
    tracking_coverage_pct = 100.0 * n_valid_frames / max(n_raw_frames, 1)
    x_valid = x_full[valid_mask]
    y_valid = y_full[valid_mask]

    cx_cal, cy_cal = inp.cx_px, inp.cy_px

    # RANSAC can return a *degenerate* giant circle (a huge radius is locally almost
    # straight, so it captures arc points as "inliers"). Guard against it: a fit is
    # only usable if its radius is plausible relative to how far the points actually
    # sit from the marked center. Without this, a 8000 px bogus fit poisons both
    # r_fit and the outlier step (observed on IMG_3071).
    max_dist_from_mark = float(np.nanmax(np.sqrt((x_valid - cx_cal)**2 + (y_valid - cy_cal)**2)))
    cx_fit, cy_fit, r_fit_ransac, inlier_mask_raw = _ransac_circle_fit(x_valid, y_valid)
    n_inliers = int(inlier_mask_raw.sum())
    MIN_INLIERS = max(20, int(0.15 * n_valid_frames))
    ransac_ok = (
        cx_fit is not None
        and n_inliers >= MIN_INLIERS
        and r_fit_ransac <= 2.0 * max(max_dist_from_mark, 1.0)
        and abs(cx_fit - cx_cal) <= 2.0 * max_dist_from_mark
        and abs(cy_fit - cy_cal) <= 2.0 * max_dist_from_mark
    )
    if not ransac_ok:
        common.set_validation_flag("ransac_fit_rejected")

    # Center selection: trust the user/bootstrap mark by default, but a human can
    # place the mark off the true *projected* rotation axis (observed on the fan:
    # mark 158 px from the real orbit center -> spurious radius_unstable / period
    # _mismatch). Adopt the RANSAC fit over the mark only when it is unambiguously
    # better: a tight inlier residual AND a materially lower radius coefficient of
    # variation. A degenerate giant-circle fit fails both, so this is self-guarding.
    if rect.applied:
        # The rectified orbit is a circle about the imaged axle BY CONSTRUCTION — that
        # is what the vanishing line was built from — so there is nothing left for the
        # centre heuristics to choose, and letting RANSAC "improve" it here would only
        # re-introduce the error the rectification just removed.
        cx_active, cy_active = rect_centre
        center_source = "rectified_hub"
        center_drift_px = 0.0
    elif inp.center_source in ("user_mark", "bootstrap"):
        cx_active, cy_active = cx_cal, cy_cal
        center_source = inp.center_source
        if ransac_ok:
            center_drift_px = float(np.sqrt((cx_fit - cx_cal)**2 + (cy_fit - cy_cal)**2))
            if center_drift_px > 25:
                r_in = np.sqrt((x_valid[inlier_mask_raw] - cx_fit)**2
                               + (y_valid[inlier_mask_raw] - cy_fit)**2)
                fit_resid_ratio = float(r_in.std() / max(r_in.mean(), 1e-9))
                cv_mark = _radius_cv(x_valid, y_valid, cx_cal, cy_cal)
                cv_fit = _radius_cv(x_valid, y_valid, cx_fit, cy_fit)
                if fit_resid_ratio < 0.10 and cv_fit < 0.6 * cv_mark:
                    cx_active, cy_active = cx_fit, cy_fit
                    center_source = "ransac_override"
                    center_drift_px = 0.0  # drift is now measured vs the adopted center
                    common.set_validation_flag("center_overridden_from_mark")
                    common.log(f"[calibrate] mark off-axis; adopted RANSAC center "
                               f"(resid={fit_resid_ratio:.3f} cv {cv_mark:.3f}->{cv_fit:.3f})")
                else:
                    common.set_validation_flag("center_mismatch")
        else:
            center_drift_px = 0.0  # no trustworthy fit to compare against
    elif ransac_ok:
        center_drift_px = float(np.sqrt((cx_fit - cx_cal)**2 + (cy_fit - cy_cal)**2))
        cx_active, cy_active = (cx_fit, cy_fit) if center_drift_px > 10 else (cx_cal, cy_cal)
        center_source = "ransac_fit" if center_drift_px > 10 else inp.center_source
    else:
        cx_active, cy_active = cx_cal, cy_cal
        center_source = inp.center_source
        center_drift_px = 0.0

    # Orbit radius and outlier rejection are computed from the ACTIVE (trusted)
    # center via the robust median distance — never from the RANSAC radius, which
    # may be degenerate. This is scale-correct for a circular orbit by definition.
    r_per_frame = np.sqrt((x_full - cx_active)**2 + (y_full - cy_active)**2)
    r_valid = r_per_frame[valid_mask]
    r_fit_px = float(np.nanmedian(r_valid))
    sigma_r = float(np.nanstd(r_valid))
    outlier_full = np.abs(r_per_frame - r_fit_px) > np.maximum(2.5 * sigma_r, 15.0)
    x_full[outlier_full] = np.nan
    y_full[outlier_full] = np.nan
    # Drop the same frames from the image-space copy, so the drawn marker and the
    # measured angle can never disagree about which frames exist.
    x_img[outlier_full] = np.nan
    y_img[outlier_full] = np.nan
    n_outliers_rejected = int(outlier_full.sum())

    common.step_end("step5")

    # ── Calibration (old step 6): px_per_m from the reference diameter ───────
    common.step_start("step6")
    px_per_m = inp.diameter_px / inp.physical_size_m
    r_fit_m = r_fit_px / px_per_m
    common.step_end("step6")

    cal = Calibration(
        cx_px=float(cx_active), cy_px=float(cy_active),
        center_source=center_source, center_drift_px=center_drift_px,
        px_per_m=float(px_per_m),
        physical_size_m=inp.physical_size_m,
        physical_size_source=inp.physical_size_source,   # STRING, never the value
        diameter_px=inp.diameter_px,
        r_fit_px=float(r_fit_px), r_fit_m=float(r_fit_m),
        n_inliers=n_inliers, n_valid_frames=n_valid_frames,
        n_outliers_rejected=n_outliers_rejected,
        tracking_coverage_pct=float(tracking_coverage_pct),
        rectification=rect.as_dict(),
    )
    common.log(f"[calibrate] px_per_m={px_per_m:.2f} center_source={center_source} "
               f"drift={center_drift_px:.1f}px r_fit_m={r_fit_m:.4f}")
    return cal, x_full, y_full, x_img, y_img
