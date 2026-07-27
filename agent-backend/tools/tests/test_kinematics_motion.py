#!/usr/bin/env python3
"""Offline unit tests for the motion-segmentation model (analysis/kinematics._motion_model).

No video / perception — synthetic omega(t) profiles drive the classifier directly. Pins the
flick fix: a rest -> flick -> coast-down -> rest clip must be read as an IMPULSIVE start whose
alpha is fit over the coast-down only (omega_initial = the real peak), while clean monotonic
spin-up / spin-down clips keep the whole-run fit unchanged (no regression)."""
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "workspace_lib"))
from analysis.kinematics import Kinematics, _motion_model

FPS = 60.0


class _Cal:
    r_fit_m = 0.2


def _kin(omega):
    """A Kinematics carrying a synthetic omega(t); theta is its integral, active where the
    spin is meaningfully non-zero (mirrors the real active-detection outcome)."""
    t = np.arange(len(omega)) / FPS
    theta = np.cumsum(omega) / FPS
    active = np.abs(omega) > 0.1 * float(np.max(np.abs(omega)))
    return Kinematics(
        t_s=t, r_px=np.zeros_like(t), r_m=np.zeros_like(t), theta_unwrapped=theta,
        omega=np.asarray(omega, float), v_m_s=np.zeros_like(t), ac_m_s2=np.zeros_like(t),
        active_mask=active, rotation_direction="CCW",
        active_duration_s=float(active.sum()) / FPS)


def test_flick_is_impulsive_and_fits_the_coastdown():
    # 2 s at rest, a fast flick up to 10 rad/s over 0.4 s, then a 1.6 s linear coast-down to 0.
    rest = np.zeros(int(2.0 * FPS))
    up = np.linspace(0.0, 10.0, int(0.4 * FPS))
    down = np.linspace(10.0, 0.2, int(1.6 * FPS))
    tail = np.zeros(int(1.0 * FPS))
    k = _kin(np.concatenate([rest, up, down, tail]))
    _motion_model(k, _Cal(), FPS)
    assert k.motion_type == "decelerating"
    assert k.impulsive_start is True
    # omega_initial is the real peak (~10), NOT a parabola intercept over rise+fall.
    assert 8.0 < k.omega_initial < 11.0, k.omega_initial
    # fit window is the ~1.6 s coast-down, well short of the ~2 s active run (rise+fall).
    assert k.fit_window_s < 1.9, k.fit_window_s


def test_clean_decel_not_impulsive():
    # Monotonic spin-down from the first active frame — the whole run is coherent.
    k = _kin(np.linspace(9.0, 6.0, int(6.0 * FPS)))
    _motion_model(k, _Cal(), FPS)
    assert k.motion_type == "decelerating"
    assert k.impulsive_start is False
    assert k.fit_window_s > 5.5           # whole run, not split


def test_clean_accel_not_impulsive():
    # Monotonic spin-up (fan) — peak sits at the END, so no interior split.
    k = _kin(2.0 + 1.6 * (np.arange(int(6.0 * FPS)) / FPS))
    _motion_model(k, _Cal(), FPS)
    assert k.motion_type == "accelerating"
    assert k.impulsive_start is False
    assert abs(k.alpha_rad_s2 - 1.6) < 0.2


def test_negative_omega_coastdown_is_decelerating():
    """The ceiling-fan defect: a clip filmed from the side the tracker records as NEGATIVE.

    |omega| falls 9.5 -> 0.03 (a coast-down), so the quadratic fits alpha = +0.17 and
    sign(alpha) reads "accelerating" — which is how a fan's basic worksheet came to teach
    "speeding up motion" beside a graph reading "slowing down". The trend must come from
    the speed, and a_t must oppose the motion."""
    k = _kin(-np.linspace(9.5, 0.03, int(6.0 * FPS)))
    _motion_model(k, _Cal(), FPS)
    assert k.alpha_rad_s2 > 0, k.alpha_rad_s2          # the raw fit really is positive
    assert k.motion_type == "decelerating", k.motion_type
    assert k.alpha_along_rad_s2 < 0, k.alpha_along_rad_s2
    assert k.a_t_mean_m_s2 < 0, k.a_t_mean_m_s2        # points against the direction of travel


def test_negative_omega_spinup_is_accelerating():
    """Mirror image: turning the negative way and picking up speed is still speeding up."""
    k = _kin(-(2.0 + 1.6 * (np.arange(int(6.0 * FPS)) / FPS)))
    _motion_model(k, _Cal(), FPS)
    assert k.alpha_rad_s2 < 0, k.alpha_rad_s2
    assert k.motion_type == "accelerating", k.motion_type
    assert abs(k.alpha_along_rad_s2 - 1.6) < 0.2, k.alpha_along_rad_s2
    assert k.a_t_mean_m_s2 > 0, k.a_t_mean_m_s2


def test_positive_omega_unchanged():
    """No regression on the clips that already read correctly: turning the positive way,
    alpha and alpha-along-travel agree."""
    k = _kin(np.linspace(9.0, 6.0, int(6.0 * FPS)))
    _motion_model(k, _Cal(), FPS)
    assert k.motion_type == "decelerating"
    assert k.alpha_along_rad_s2 == k.alpha_rad_s2
    assert k.a_t_mean_m_s2 < 0


def test_uniform_not_impulsive():
    rng = np.random.default_rng(0)
    k = _kin(5.0 + rng.normal(0, 0.02, int(6.0 * FPS)))
    _motion_model(k, _Cal(), FPS)
    assert k.motion_type == "uniform"
    assert k.impulsive_start is False


def run():
    fns = [v for kk, v in sorted(globals().items()) if kk.startswith("test_")]
    for fn in fns:
        fn()
        print(f"[PASS] {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} kinematics motion tests passed")


if __name__ == "__main__":
    run()
