"""Projective rectification of a circular orbit filmed off-axis.

A circle photographed at a slant images as an ellipse, and — when there is real
perspective rather than mere tilt — the image of the circle's CENTRE is not the
centre of that ellipse. Both effects distort ANGLE: a uniformly turning object
appears to sweep unequal angles per frame, once per revolution. That ripple is
deterministic (it repeats identically every revolution), so no filter can remove
it without also destroying the real deceleration underneath.

The geometry that fixes it needs no camera calibration. For a circle, the polar
line of its centre with respect to the circle is that plane's line at infinity.
Both the conic and the polar survive projection, so the imaged hub `h` plus the
fitted orbit conic `C` give the vanishing line directly:

    l = C h                                   vanishing line of the orbit's plane
    H = [[1,0,0], [0,1,0], l]                 maps l to infinity  -> AFFINE image
    then ellipse -> circle by the axis stretch -> METRIC, so atan2 is the true angle

THE ONE WAY TO GET THIS WRONG: `h` must be the imaged AXLE, not the centre of the
ellipse you see. Those coincide only under affine viewing, and their offset IS the
perspective — it is the entire input to the method. Pass the ellipse centre and the
polar comes back as the line at infinity, the homography is the identity, and you
have silently done nothing.

SCALE. Rectification redistributes angle WITHIN a revolution; it cannot change how
many revolutions happened, and it must not quietly restate the scale. The rectified
plane is recovered only up to a similarity, so we pin it: the output is scaled so
its orbit radius equals the MAJOR semi-axis of the imaged ellipse — the direction
that was never foreshortened — leaving `px_per_m` from Step 6 meaningful. `r_fit_m`
therefore moves by the foreshortening the old circle fit was averaging over, which
is the correction, not a side effect.

VALIDATION IS NOT "IT LOOKS SMOOTHER" — smoothing does that. `rectify` reports the
two checks that matter and the caller records both:
  * mean |omega| must be PRESERVED (it is a revolution count, immune to this map);
  * the orbit's radial residual must FALL, having never been optimized — `l` comes
    from the hub, never from the motion.
Prototype this is lifted from: `docs/figures/rectify_prototype.py`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict

import numpy as np

# Below this the clip is affine for our purposes: the corpus's near-face-on clips sit
# at 0.7-8.8 px of hub offset, roundabout-4046 at 85.6. Rectifying a near-affine clip
# is not merely pointless, it injects error, because `l` is then fitted to noise.
MIN_HUB_OFFSET_PX = 20.0

# Guard rails. A rectification that moves the revolution count is not a rectification.
MAX_MEAN_OMEGA_DRIFT = 0.02      # 2%


@dataclass
class Rectification:
    applied: bool
    reason: str
    hub_px: tuple[float, float] | None = None
    ellipse_centre_px: tuple[float, float] | None = None
    hub_offset_px: float = float("nan")
    axis_ratio: float = float("nan")
    tilt_deg: float = float("nan")
    vanishing_line: tuple[float, float, float] | None = None
    radial_residual_before_pct: float = float("nan")
    radial_residual_after_pct: float = float("nan")
    scale_applied: float = float("nan")

    def as_dict(self) -> dict:
        """JSON-safe: the writer dumps with `allow_nan=False`, and every diagnostic here
        is NaN whenever rectification was skipped — which is the common case."""
        def clean(v):
            if isinstance(v, float) and not math.isfinite(v):
                return None
            if isinstance(v, (tuple, list)):
                return [clean(i) for i in v]
            return v
        return {k: clean(v) for k, v in asdict(self).items()}


def fit_conic(x, y):
    """Least-squares conic through the points, as a symmetric 3x3 matrix.

    Normalised before the SVD: raw pixel coordinates square to ~1e6 and the solve is
    badly conditioned without it.
    """
    xm, ym = x.mean(), y.mean()
    s = max(x.std(), y.std(), 1e-9)
    X, Y = (x - xm) / s, (y - ym) / s
    D = np.c_[X * X, X * Y, Y * Y, X, Y, np.ones_like(X)]
    _, _, V = np.linalg.svd(D)
    a, b, c, d, e, g = V[-1]
    Cn = np.array([[a, b / 2, d / 2], [b / 2, c, e / 2], [d / 2, e / 2, g]])
    S = np.array([[1 / s, 0, -xm / s], [0, 1 / s, -ym / s], [0, 0, 1]])
    return S.T @ Cn @ S


def conic_params(C):
    """Centre, semi-axes (major first) and axis frame of an ellipse conic, or None."""
    A = C[:2, :2]
    if np.linalg.det(A) <= 0:
        return None
    try:
        cen = np.linalg.solve(2 * A, [-2 * C[0, 2], -2 * C[1, 2]])
    except np.linalg.LinAlgError:
        return None
    fp = cen @ A @ cen + 2 * C[:2, 2] @ cen + C[2, 2]
    ev, evec = np.linalg.eigh(A)
    rad = -fp / ev
    if np.any(rad <= 0) or not np.all(np.isfinite(rad)):
        return None
    ax = np.sqrt(rad)
    o = np.argsort(-ax)
    return dict(c=cen, A=float(ax[o][0]), B=float(ax[o][1]), R=evec[:, o])


def _metric_from_ellipse(x, y):
    """Affine image of a circle -> circle. Handedness is preserved (det = +1) so the
    SIGN of omega, and therefore the reported rotation direction, cannot flip."""
    p = conic_params(fit_conic(x, y))
    if p is None:
        return None
    R = p["R"]
    if np.linalg.det(R) < 0:
        R = np.c_[R[:, 0], -R[:, 1]]
    q = np.c_[x - p["c"][0], y - p["c"][1]] @ R
    return q[:, 0], q[:, 1] * (p["A"] / p["B"]), p


def _radial_residual_pct(x, y, cx, cy) -> float:
    r = np.hypot(x - cx, y - cy)
    return float(100.0 * r.std() / max(r.mean(), 1e-9))


def rectify(x_full, y_full, hub_px):
    """Map a trajectory to the metric plane of its own orbit.

    `x_full`/`y_full` may contain NaN (dropped frames); they are preserved as NaN.
    `hub_px` is the imaged axle in the SAME space as the trajectory.

    Returns `(x_rect, y_rect, centre_xy, Rectification)`. When rectification does not
    apply, the inputs come back untouched with `applied=False` and a reason — callers
    do not need a separate code path.
    """
    meta = Rectification(applied=False, reason="not_attempted")
    if hub_px is None:
        meta.reason = "no_hub_px"
        return x_full, y_full, None, meta

    m = np.isfinite(x_full) & np.isfinite(y_full)
    if int(m.sum()) < 50:
        meta.reason = "too_few_points"
        return x_full, y_full, None, meta

    x, y = x_full[m], y_full[m]
    hx, hy = float(hub_px[0]), float(hub_px[1])
    meta.hub_px = (hx, hy)

    C = fit_conic(x, y)
    p = conic_params(C)
    if p is None:
        meta.reason = "orbit_is_not_an_ellipse"
        return x_full, y_full, None, meta

    meta.ellipse_centre_px = (float(p["c"][0]), float(p["c"][1]))
    meta.hub_offset_px = float(np.hypot(hx - p["c"][0], hy - p["c"][1]))
    meta.axis_ratio = float(p["B"] / p["A"])
    meta.tilt_deg = float(np.degrees(np.arccos(min(1.0, p["B"] / p["A"]))))

    if meta.hub_offset_px < MIN_HUB_OFFSET_PX:
        # Affine to within our ability to measure it. Say so and leave the data alone;
        # fitting `l` here would be fitting noise.
        meta.reason = f"hub_offset_below_{MIN_HUB_OFFSET_PX:g}px"
        return x_full, y_full, None, meta

    l = C @ np.array([hx, hy, 1.0])
    n = np.linalg.norm(l[:2])
    if not np.isfinite(n) or n < 1e-12:
        meta.reason = "degenerate_vanishing_line"
        return x_full, y_full, None, meta
    l = l / n
    meta.vanishing_line = (float(l[0]), float(l[1]), float(l[2]))

    H = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [l[0], l[1], l[2]]])
    P = np.c_[x, y, np.ones_like(x)] @ H.T
    w = P[:, 2]
    if np.any(np.abs(w) < 1e-9):
        meta.reason = "point_on_vanishing_line"
        return x_full, y_full, None, meta
    xa, ya = P[:, 0] / w, P[:, 1] / w

    got = _metric_from_ellipse(xa, ya)
    if got is None:
        meta.reason = "affine_stage_failed"
        return x_full, y_full, None, meta
    xm_, ym_, _pa = got

    # Pin the similarity: the rectified orbit takes the radius of the imaged ellipse's
    # MAJOR semi-axis — the direction perspective never shortened — so px_per_m from
    # Step 6 keeps meaning what it meant.
    r_rect = np.hypot(xm_, ym_)
    scale = float(p["A"] / max(np.median(r_rect), 1e-9))
    xm_, ym_ = xm_ * scale, ym_ * scale
    meta.scale_applied = scale

    meta.radial_residual_before_pct = _radial_residual_pct(x, y, p["c"][0], p["c"][1])
    meta.radial_residual_after_pct = _radial_residual_pct(xm_, ym_, 0.0, 0.0)

    # Put the rectified orbit back where the clip is, so overlays and the ROI crop still
    # line up with the footage: centre it on the imaged hub.
    x_out = np.full_like(x_full, np.nan)
    y_out = np.full_like(y_full, np.nan)
    x_out[m] = xm_ + hx
    y_out[m] = ym_ + hy

    meta.applied = True
    meta.reason = "vanishing_line"
    return x_out, y_out, (hx, hy), meta
