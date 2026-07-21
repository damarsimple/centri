#!/usr/bin/env python3
"""Offline unit tests for analysis.quality_signals — the trust channel that decides whether
per-instant angular velocity may be narrated.

Pins two holes found on turntable-3, whose v(t) shows a visible speed-up midway through a
coast-down that no turntable can physically perform:

  1. The old rule required an ELLIPTICAL image orbit before it would distrust a phase-locked
     ripple, because oblique capture was the cause it had been derived from. A phase-locked
     ripple on a ROUND orbit was therefore cleared however large it was. turntable-3 is round
     to an axis ratio of 1.002 and was declared "reliable; narrate the timeline normally".
  2. Nothing checked how many revolutions the phase-lock statistic had to work with. Below
     ~2 it fits four harmonics to about 1.5 cycles and can neither convict nor clear.
"""
import csv
import math
import os
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workspace_lib"))
from analysis import quality_signals as Q

FPS = 60.0
R_PX = 400.0


def _write(t, th, x, y, om):
    d = tempfile.mkdtemp()
    p = os.path.join(d, "kinematics.csv")
    with open(p, "w") as f:
        f.write("time_s,r_px,r_m,theta_rad,omega_rad_s,v_m_s,ac_m_s2,active,x_px,y_px\n")
        for i in range(len(t)):
            r = math.hypot(x[i] - 500.0, y[i] - 500.0)
            f.write(f"{t[i]},{r},0.4,{th[i]},{om[i]},1,1,1,{x[i]},{y[i]}\n")
    return p


def _clip(revs, ripple_amp=0.0, ellipse=1.0, dur=6.0, ripple_harmonic=1):
    """A clip of `revs` revolutions with an optional ripple locked to ORBITAL PHASE."""
    n = int(dur * FPS)
    t = np.arange(n) / FPS
    base = revs * 2 * np.pi * t / dur
    th = base + ripple_amp * np.sin(ripple_harmonic * base)
    om = np.gradient(th, t)
    x = 500.0 + R_PX * np.cos(th)
    y = 500.0 + R_PX / ellipse * np.sin(th)
    return _write(t, th, x, y, om)


def _sig(path):
    s = Q.compute(path, {})
    return s, Q.build_quality_block(s, {})


def test_phase_locked_ripple_on_a_ROUND_orbit_is_not_cleared():
    """The hole that let turntable-3 through: cause unknown is not the same as no problem."""
    s, b = _sig(_clip(revs=9, ripple_amp=0.12, ellipse=1.0))
    assert s["orbit_axis_ratio"] < Q.AXIS_UNRELIABLE, s["orbit_axis_ratio"]
    assert s["omega_phaselocked_fraction"] >= Q.PHASELOCK_UNRELIABLE
    assert "per_instant_omega_unreliable" in s["flags"], s["flags"]
    assert b["reliable"] is False
    assert b["do_not_claim"], "a distrusted clip must forbid per-instant claims"


def test_round_orbit_guidance_does_not_invent_a_cause():
    """It must not tell the writer the orbit is slanted when the orbit is round."""
    _s, b = _sig(_clip(revs=9, ripple_amp=0.12, ellipse=1.0))
    g = b["guidance"].lower()
    assert "slant" not in g and "ellipse" not in g, g
    assert "not identified" in g or "cannot" in g, g


def test_oblique_orbit_still_names_the_cause():
    _s, b = _sig(_clip(revs=9, ripple_amp=0.12, ellipse=1.30))
    assert b["reliable"] is False
    assert "slant" in b["guidance"].lower(), b["guidance"]


def test_too_few_revolutions_is_reported_as_unverified_not_reliable():
    """turntable-2/-3 sit at 1.4-1.8 revolutions with a material ripple that is only
    MODERATELY phase-locked (0.26-0.52) — below the conviction threshold, and on too short a
    record to clear. The trust channel must not claim it has cleared them."""
    rng = np.random.default_rng(3)
    n = int(6.0 * FPS)
    t = np.arange(n) / FPS
    base = 1.5 * 2 * np.pi * t / 6.0
    th = base + 0.05 * np.sin(base)
    om = np.gradient(th, t) * (1.0 + 0.30 * rng.standard_normal(n))
    x = 500.0 + R_PX * np.cos(th)
    y = 500.0 + R_PX * np.sin(th)
    s, b = _sig(_write(t, th, x, y, om))
    assert s["omega_ripple_cv"] >= Q.RIPPLE_CV_UNRELIABLE, s["omega_ripple_cv"]
    assert s["omega_phaselocked_fraction"] < Q.PHASELOCK_UNRELIABLE, s
    assert s["n_revolutions"] < Q.MIN_REVS_FOR_PHASELOCK
    assert "per_instant_omega_unverified" in s["flags"], s["flags"]
    assert b["reliable"] is False
    assert b["do_not_claim"]
    assert "revolution" in b["guidance"].lower()


def test_short_clip_with_a_SMALL_ripple_is_still_fine():
    """Not every short clip is suspect — only one whose ripple is material."""
    s, b = _sig(_clip(revs=1.5, ripple_amp=0.0))
    assert s["omega_ripple_cv"] < Q.RIPPLE_CV_UNRELIABLE
    assert "per_instant_omega_unverified" not in s["flags"], s["flags"]
    assert b["reliable"] is True


def test_a_clean_long_clip_is_untouched():
    s, b = _sig(_clip(revs=12, ripple_amp=0.0))
    assert b["reliable"] is True
    assert not [f for f in s["flags"] if f.startswith("per_instant")]
    assert b["guidance"].startswith("Per-instant angular velocity is reliable")


def test_a_big_ripple_that_is_NOT_phase_locked_survives():
    """The fans carry a 30-42% ripple that tracks TIME (real spin-up), not orbital phase.
    Distrusting those would suppress the very thing they are there to teach."""
    rng = np.random.default_rng(7)
    n = int(8.0 * FPS)
    t = np.arange(n) / FPS
    th = np.cumsum(np.linspace(0.05, 0.30, n))          # steadily speeding up
    # a large but UNSTRUCTURED wobble: big residual, no orbital-phase signature
    om = np.gradient(th, t) * (1.0 + 0.35 * rng.standard_normal(n))
    x = 500.0 + R_PX * np.cos(th)
    y = 500.0 + R_PX * np.sin(th)
    s, b = _sig(_write(t, th, x, y, om))
    assert s["omega_ripple_cv"] >= Q.RIPPLE_CV_UNRELIABLE, s["omega_ripple_cv"]
    assert s["omega_phaselocked_fraction"] < Q.PHASELOCK_UNRELIABLE, s
    assert b["reliable"] is True, b


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"{len(fns)}/{len(fns)} passed")
