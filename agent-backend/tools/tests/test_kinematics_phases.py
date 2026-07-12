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


def test_staircase_not_oversegmented():
    # Frequency-synth omega is a quantised staircase: spin up 1→4 in 0.5-step treads, then coast
    # 4→1. The step-edges must NOT chop this into dozens of alternating bands — the directional
    # merge collapses each side into ONE coarse phase: a single INCREASE then a single DECREASE.
    up = np.concatenate([np.full(int(1.5 * FPS), v) for v in (1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0)])
    down = np.concatenate([np.full(int(1.5 * FPS), v) for v in (4.0, 3.5, 3.0, 2.5, 2.0, 1.5, 1.0)])
    seq, labels = _phase_seq(np.concatenate([up, down]), "accelerating")
    dir_runs = [x for x in seq if x in ("INCREASE", "DECREASE")]
    assert dir_runs == ["INCREASE", "DECREASE"], seq   # exactly one of each, in order
    assert len(seq) <= 5, seq                          # not 20+ speckled bands


def test_ripple_decel_no_spurious_increase():
    # Decelerating spin with a strong 1/rev projection ripple (±25 %). The ripple crests must not
    # be read as INCREASE phases on a clip that is overall slowing down.
    t = np.arange(int(12.0 * FPS)) / FPS
    base = np.linspace(11.0, 5.5, t.size)              # slow decline
    ripple = 1.0 * np.sin(2 * np.pi * 1.0 * t)         # ~1 Hz orbital ripple, ~12 %
    seq, labels = _phase_seq(base + ripple, "decelerating")
    assert "INCREASE" not in labels, seq               # no ripple-crest INCREASE
    assert "DECREASE" in labels, seq                   # the real slowdown still shows


def test_clockwise_spin_up_is_increase():
    # Clockwise rotation → negative omega. As it spins UP the magnitude grows (0.5→12) even though
    # signed omega decreases. Labelling SPEED means this reads INCREASE ("speeding up"), not the
    # inverted DECREASE that signed-omega labelling produced.
    rng = np.random.default_rng(4)
    om = -(np.linspace(0.5, 12.0, int(6.0 * FPS)) + rng.normal(0, 0.1, int(6.0 * FPS)))
    seq, labels = _phase_seq(om, "accelerating")
    assert "INCREASE" in labels and "DECREASE" not in labels, seq


def run():
    fns = [v for kk, v in sorted(globals().items()) if kk.startswith("test_")]
    for fn in fns:
        fn()
        print(f"[PASS] {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} kinematics phase tests passed")


if __name__ == "__main__":
    run()
