"""Shared helpers: deterministic RNG, logging, validation flags, step markers.

The progress feed (`app/progress_feed.py`, parsed by `worker/tasks.py`) keys off
the `[STEP START] stepN` / `[STEP END] stepN` log lines and the
`.centri_progress.json` heartbeat, so this module reproduces those exactly. Do
not change the marker format without updating the feed parser.
"""
import json
import math
import re
import time
from pathlib import Path

import numpy as np


# ── Display-name hygiene ─────────────────────────────────────────────────────
_DUP_ON = re.compile(r"^(.+?)\s+on\s+\1$", re.I)


def dedup_display_name(name: str | None) -> str:
    """Collapse the degenerate ``"<X> on <X>"`` composite (which arises when the
    tracked label equals the reference label, e.g. "fan blade on fan blade") down to
    ``"<X>"``, and normalise whitespace. Idempotent; ``None`` → "".

    The ``"<tracked> on <ref>"`` scene title is built in prompts/orchestrator.txt; when
    the two halves coincide it read as "fan blade on fan blade" in every figure/report
    title. Deduping was inlined only in render/report.py — this is the shared helper so
    figures.py, the seed, and the report all collapse it identically.
    """
    if not name:
        return ""
    s = re.sub(r"\s+", " ", str(name)).strip()
    m = _DUP_ON.fullmatch(s)
    return m.group(1).strip() if m else s


# ── Canonical angular velocity ───────────────────────────────────────────────
def canonical_omega(stats: dict) -> tuple[float | None, bool]:
    """The ONE angular velocity every material surface (seed prose, report table,
    figures) must quote, plus whether it is a clip-average.

    Returns ``(value, is_clip_average)``.

    For a (de)accelerating clip there is no genuine stable phase, so
    ``stable_phase.stable_mean_omega`` is a fluke of the per-frame phase labeller — on
    the red-phone flick it read 2.89 rad/s for a spin that time-averaged 5.79, and it
    does NOT close with the period / mean speed / mean a_c (all built from the true
    time-average). So for non-uniform motion we report ``summary.mean_omega`` (the honest
    time-average, magnitude): that makes v = omega*r close exactly
    (``mean_v == mean|omega| * r_fit``) and the label reads "clip average". Only a
    genuinely uniform spin quotes ``stable_mean_omega`` as "the" angular velocity.
    """
    summ = stats.get("summary") or {}
    sp = stats.get("stable_phase") or {}
    mt = ((stats.get("angular_acceleration") or {}).get("motion_type")) or "uniform"
    if mt in ("accelerating", "decelerating"):
        v = summ.get("mean_omega")
        is_clip_average = True
    else:
        v = sp.get("stable_mean_omega")
        if v is None:
            v = summ.get("mean_omega")
        is_clip_average = False
    return (abs(v) if isinstance(v, (int, float)) else None), is_clip_average


# ── The (de)acceleration block, resolved along the direction of travel ───────
def motion_along_travel(stats: dict) -> dict:
    """The angular-acceleration block as a READER must see it, or ``{}`` for a steady spin.

    The tracker's sign for omega is an image-coordinate accident: film the same spin from
    the other side and it is recorded negative. Two of the seven clips (both ceiling fans)
    are on that side, so their omega runs -9.51 -> -0.03 rad/s — a coast-down — while the
    constant-alpha fit returns alpha = +0.17. Reading "speeding up" off sign(alpha) taught
    one fan's BASIC worksheet "speeding up motion" beside its own graph reading "slowing
    down". So every reader-facing surface takes its motion trend from here.

    Returns ``{"motion_type", "alpha", "a_t", "omega_initial", "omega_final"}`` where

    * ``alpha`` is d|omega|/dt — negative means losing speed, whichever way round it turns;
    * ``a_t = alpha * r`` carries that same sign, so negative always reads "points against
      the direction of travel";
    * the two omegas are SPEEDS (magnitudes), matching the unsigned :func:`canonical_omega`
      the rest of the document quotes — a signed -9.51 -> -0.03 range printed next to a
      "clip-average omega = 5.7 rad/s" is a contradiction, not a sign convention.

    Works on a stats.json written before ``alpha_along_rad_s2`` existed by recovering the
    direction of travel from the omega endpoints, so an archived run renders correctly too.
    """
    aa = (stats or {}).get("angular_acceleration") or {}
    alpha = aa.get("alpha_rad_s2")
    # A clip the pipeline called uniform stays uniform: this only REORIENTS a trend already
    # found significant, it never promotes noise into an acceleration.
    if (aa.get("motion_type") not in ("accelerating", "decelerating")
            or not isinstance(alpha, (int, float))):
        return {}
    oi, of_ = aa.get("omega_initial"), aa.get("omega_final")
    along = aa.get("alpha_along_rad_s2")
    if not isinstance(along, (int, float)):
        if isinstance(oi, (int, float)) and isinstance(of_, (int, float)):
            along = alpha * (1.0 if (oi + of_) >= 0 else -1.0)
        else:                       # nothing to orient against — trust the stored label
            along = abs(alpha) if aa["motion_type"] == "accelerating" else -abs(alpha)
    out = {
        "motion_type": "accelerating" if along > 0 else "decelerating",
        "alpha": along,
        "omega_initial": abs(oi) if isinstance(oi, (int, float)) else None,
        "omega_final": abs(of_) if isinstance(of_, (int, float)) else None,
    }
    a_t = aa.get("a_t_mean_m_s2")
    if isinstance(a_t, (int, float)):
        out["a_t"] = math.copysign(abs(a_t), along)
    return out


# One plain sentence explaining the only minus signs a reader still meets. Quoted by the
# seed (student prose + the LLM's fact sheet) and by the report's full measurements table,
# so the explanation always travels with the number.
SIGN_NOTE = ("A minus sign on the angular acceleration or on the tangential acceleration "
             "means \"against the motion\" — the object is losing speed. It never means "
             "less than nothing, and it does not say which way round the object turns; "
             "the turning direction is stated separately, in words.")

# ── Determinism ─────────────────────────────────────────────────────────────
# RANSAC and any other sampling MUST draw from this generator. An unseeded
# np.random.choice in the old agent code was the root cause of center_drift_px
# varying 8.9->1013 px on identical input. Fixed seed => identical fit every run.
RANDOM_SEED = 20240517
RNG = np.random.default_rng(RANDOM_SEED)


def reset_rng() -> None:
    """Re-seed the module RNG. Call once at the start of a run for repeatability."""
    global RNG
    RNG = np.random.default_rng(RANDOM_SEED)


# ── Logging / flags / step markers ──────────────────────────────────────────
_LOG_PATH = Path("analysis_output/debug/pipeline.log")
_validation_flags: list[str] = []
_step_times: dict[str, float] = {}


def log(msg: str) -> None:
    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(_LOG_PATH, "a") as lf:
        lf.write(line + "\n")


def set_validation_flag(flag: str) -> None:
    if flag not in _validation_flags:
        _validation_flags.append(flag)
        log(f"[FLAG] {flag}")


def validation_flags() -> list[str]:
    return list(_validation_flags)


def step_start(name: str) -> float:
    t = time.time()
    _step_times[name] = t
    log(f"[STEP START] {name}")
    return t


def step_end(name: str) -> float:
    elapsed = time.time() - _step_times.get(name, time.time())
    log(f"[STEP END] {name} — {elapsed:.1f}s")
    return elapsed


def progress(stage: str, note: str, pct: int) -> None:
    """Heartbeat the live UI reads between step markers."""
    with open(".centri_progress.json", "w") as f:
        json.dump({"stage": stage, "note": note, "pct": pct}, f)


def fit_orbit_ellipse(x, y, min_points: int = 20):
    """Least-squares conic through the tracked points, returned as an ellipse:
    `(cx, cy, semi_major, semi_minor, angle_deg)`, or None if it will not fit.

    FOR DRAWING ONLY. A circular orbit filmed off-axis images as an ellipse, so a
    drawn circle can only hug the path on a face-on clip; every physical quantity
    still comes from the circle fit in `geometry.py`. On a face-on clip the two
    semi-axes come out equal to within a few pixels, so this degrades to the circle
    it replaces instead of inventing eccentricity.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    m = np.isfinite(x) & np.isfinite(y)
    x, y = x[m], y[m]
    if x.size < min_points:
        return None

    # Normalise before the SVD: raw pixel coordinates square to ~1e6 and the conic
    # solve is badly conditioned without it.
    xm, ym = x.mean(), y.mean()
    s = max(x.std(), y.std(), 1e-9)
    X, Y = (x - xm) / s, (y - ym) / s
    D = np.c_[X * X, X * Y, Y * Y, X, Y, np.ones_like(X)]
    try:
        _, _, V = np.linalg.svd(D)
    except np.linalg.LinAlgError:
        return None
    a, b, c, d, e, g = V[-1]
    A = np.array([[a, b / 2], [b / 2, c]])
    if np.linalg.det(A) <= 0:          # hyperbola/parabola — not an orbit
        return None
    try:
        cen = np.linalg.solve(2 * A, [-d, -e])
    except np.linalg.LinAlgError:
        return None
    scale = cen @ A @ cen + np.array([d, e]) @ cen + g
    ev, evec = np.linalg.eigh(A)
    rad = -scale / ev
    if np.any(rad <= 0) or not np.all(np.isfinite(rad)):
        return None
    axes = np.sqrt(rad)
    order = np.argsort(-axes)          # major first
    axes = axes[order] * s
    major_vec = evec[:, order[0]]
    return (float(cen[0] * s + xm), float(cen[1] * s + ym),
            float(axes[0]), float(axes[1]),
            float(np.degrees(np.arctan2(major_vec[1], major_vec[0]))))
