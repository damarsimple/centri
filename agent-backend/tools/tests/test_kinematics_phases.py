#!/usr/bin/env python3
"""Offline unit tests for the per-frame phase labeller (analysis/kinematics._phases).

No video / perception — synthetic omega(t) profiles drive the labeller directly. Pins the
phase-labeller fix: the threshold is taken off the 90th percentile of |dω/dt| (not its max, which
an impulsive flick's rise spike dominates), and the clean-up closes short STABLE gaps then
despeckles short direction runs (replacing the old transition-commit loop that clobbered the last
active phase to STABLE when the clip came to rest). A rest→flick→coast-down→rest clip must now show
a DECREASE phase; clean spin-up/decel show INCREASE/DECREASE; a uniform spin stays all-STABLE."""
import pathlib
import sys
import types

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "workspace_lib"))
from analysis.kinematics import Kinematics, _phases  # noqa: E402

FPS = 60.0


def _phase_seq(omega, motion_type="uniform"):
    """Run _phases on a synthetic omega(t) and return (deduped active phase sequence, label list)."""
    omega = np.asarray(omega, float)
    n = len(omega)
    t = np.arange(n) / FPS
    theta = np.cumsum(omega) / FPS
    active = np.abs(omega) > 0.1 * float(np.max(np.abs(omega)))
    k = Kinematics(
        t_s=t, r_px=np.zeros(n), r_m=np.zeros(n), theta_unwrapped=theta,
        omega=omega, v_m_s=np.zeros(n), ac_m_s2=np.zeros(n),
        active_mask=active, rotation_direction="CCW",
        active_duration_s=float(active.sum()) / FPS)
    k.motion_type = motion_type
    inp = types.SimpleNamespace(n_raw_frames=n)
    _phases(k, inp, FPS, theta_smooth=None)
    labels = k.phase_labels
    seq = []
    for lab in labels:
        if lab == "INACTIVE":
            continue
        if not seq or seq[-1] != lab:
            seq.append(lab)
    return seq, labels


def test_flick_shows_decrease():
    # rest → fast flick to 10 over 0.4 s → 1.6 s coast-down → rest.
    rest = np.zeros(int(2.0 * FPS))
    up = np.linspace(0.0, 10.0, int(0.4 * FPS))
    down = np.linspace(10.0, 0.2, int(1.6 * FPS))
    tail = np.zeros(int(1.0 * FPS))
    seq, labels = _phase_seq(np.concatenate([rest, up, down, tail]), "decelerating")
    assert "DECREASE" in labels, seq            # the coast-down is no longer mislabelled steady
    assert labels.count("DECREASE") > int(0.5 * FPS), seq  # a real, sustained phase
    assert seq and seq[-1] == "DECREASE", seq   # ends slowing down (rise absorbed as <0.5 s)


def test_uniform_all_stable():
    rng = np.random.default_rng(0)
    seq, labels = _phase_seq(5.0 + rng.normal(0, 0.05, int(6.0 * FPS)), "uniform")
    assert set(labels) <= {"STABLE", "INACTIVE"}, seq
    assert "INCREASE" not in labels and "DECREASE" not in labels


def test_clean_spin_up_shows_increase():
    rng = np.random.default_rng(1)
    seq, labels = _phase_seq(np.linspace(0.5, 12.0, int(6.0 * FPS)) + rng.normal(0, 0.1, int(6.0 * FPS)),
                             "accelerating")
    assert "INCREASE" in labels, seq
    assert labels.count("INCREASE") > 4 * int(0.5 * FPS), seq  # dominant, not a blip
    assert "DECREASE" not in labels, seq


def test_clean_decel_shows_decrease():
    rng = np.random.default_rng(2)
    seq, labels = _phase_seq(np.linspace(12.0, 1.0, int(6.0 * FPS)) + rng.normal(0, 0.1, int(6.0 * FPS)),
                             "decelerating")
    assert "DECREASE" in labels, seq
    assert labels.count("DECREASE") > 4 * int(0.5 * FPS), seq
    assert "INCREASE" not in labels, seq


def test_spin_up_then_steady():
    rng = np.random.default_rng(3)
    up = np.linspace(0.5, 10.0, int(2.5 * FPS))
    hold = 10.0 + rng.normal(0, 0.08, int(3.5 * FPS))
    seq, labels = _phase_seq(np.concatenate([up, hold]), "accelerating")
    assert seq[0] == "INCREASE" and "STABLE" in seq, seq   # speeds up, then holds
    assert "DECREASE" not in labels, seq


def run():
    fns = [v for kk, v in sorted(globals().items()) if kk.startswith("test_")]
    for fn in fns:
        fn()
        print(f"[PASS] {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} kinematics phase tests passed")


if __name__ == "__main__":
    run()
