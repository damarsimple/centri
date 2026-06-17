"""Shared helpers: deterministic RNG, logging, validation flags, step markers.

The progress feed (`app/progress_feed.py`, parsed by `worker/tasks.py`) keys off
the `[STEP START] stepN` / `[STEP END] stepN` log lines and the
`.centri_progress.json` heartbeat, so this module reproduces those exactly. Do
not change the marker format without updating the feed parser.
"""
import json
import time
from pathlib import Path

import numpy as np

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
