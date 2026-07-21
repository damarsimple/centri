"""Shared helpers: deterministic RNG, logging, validation flags, step markers.

The progress feed (`app/progress_feed.py`, parsed by `worker/tasks.py`) keys off
the `[STEP START] stepN` / `[STEP END] stepN` log lines and the
`.centri_progress.json` heartbeat, so this module reproduces those exactly. Do
not change the marker format without updating the feed parser.
"""
import json
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
