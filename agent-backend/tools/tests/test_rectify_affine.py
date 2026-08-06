"""A centred but tilted orbit must be de-foreshortened.

`rectify()` gated only on hub offset (decentering). It measured `axis_ratio` two lines
above and then ignored it, so a perfectly centred but heavily TILTED orbit was returned
untouched — an ellipse.

That left "the orbit radius" with no single value. On fan-4656 (axis ratio 0.823, hub
offset 0.05 px) two runs from a BYTE-IDENTICAL sidecar chose differently — semi-major
260 px vs circle-fit 245 px — giving px_per_m 591 vs 558 and a 6% swing in the taught
a_c. The ambiguity was the defect; the uncorrected ellipse was its cause.
"""
import math

import numpy as np
import pytest

from workspace_lib.analysis.rectify import (AFFINE_MIN_AXIS_RATIO, MIN_HUB_OFFSET_PX,
                                            rectify)


def tilted_orbit(n=600, r=260.0, ratio=0.823, ang_deg=90.8, cx=902.0, cy=502.0,
                 turns=6.0, noise=0.0, seed=0):
    """A circle of radius r seen at a tilt: an ellipse, centred exactly on the hub."""
    rng = np.random.default_rng(seed)
    th = np.linspace(0, 2 * math.pi * turns, n)
    x, y = r * np.cos(th), r * ratio * np.sin(th)
    a = math.radians(ang_deg)
    xr = x * math.cos(a) - y * math.sin(a)
    yr = x * math.sin(a) + y * math.cos(a)
    if noise:
        xr = xr + rng.normal(0, noise, n)
        yr = yr + rng.normal(0, noise, n)
    return xr + cx, yr + cy, (cx, cy), th


def _axis_ratio(x, y, cx, cy):
    q = np.c_[x - cx, y - cy]
    ev = np.linalg.eigvalsh(np.cov(q.T))
    return float(math.sqrt(min(ev) / max(ev)))


def test_centred_but_tilted_orbit_is_now_rectified():
    x, y, hub, _ = tilted_orbit()
    xr, yr, centre, meta = rectify(x, y, hub)
    assert meta.applied, f"still skipped: {meta.reason}"
    assert meta.reason == "affine_foreshortening"
    assert meta.hub_offset_px < MIN_HUB_OFFSET_PX      # the old gate would have bailed here
    assert _axis_ratio(xr, yr, *centre) > 0.99, "orbit is still an ellipse after rectifying"


def test_rectified_radius_is_the_major_semi_axis():
    """px_per_m must keep meaning: the pinned radius is the unforeshortened one."""
    R = 260.0
    x, y, hub, _ = tilted_orbit(r=R, ratio=0.823)
    xr, yr, centre, meta = rectify(x, y, hub)
    rr = np.hypot(xr - centre[0], yr - centre[1])
    assert abs(np.median(rr) - R) / R < 0.02, (np.median(rr), R)


def test_a_round_orbit_is_left_alone():
    """Above the ratio threshold, correcting would be stretching noise."""
    x, y, hub, _ = tilted_orbit(ratio=0.99)
    _, _, _, meta = rectify(x, y, hub)
    assert not meta.applied
    assert "axis_ratio_above" in meta.reason


@pytest.mark.parametrize("ratio", [0.60, 0.75, 0.823, 0.90])
def test_revolution_count_is_preserved(ratio):
    """Guard rail: a rectification that moves the revolution count is not a rectification."""
    x, y, hub, _ = tilted_orbit(ratio=ratio, turns=6.0)
    xr, yr, centre, meta = rectify(x, y, hub)
    assert meta.applied
    before = np.unwrap(np.arctan2(y - hub[1], x - hub[0]))
    after = np.unwrap(np.arctan2(yr - centre[1], xr - centre[0]))
    rev_b = abs(before[-1] - before[0]) / (2 * math.pi)
    rev_a = abs(after[-1] - after[0]) / (2 * math.pi)
    assert abs(rev_a - rev_b) / rev_b < 0.02, (rev_b, rev_a)


@pytest.mark.parametrize("ratio", [0.60, 0.823, 0.94])
def test_rotation_direction_cannot_flip(ratio):
    """Handedness is preserved, so the sign of omega survives — the 07-31 lesson."""
    for sign in (+1, -1):
        x, y, hub, th = tilted_orbit(ratio=ratio)
        if sign < 0:
            x, y = x[::-1], y[::-1]
        xr, yr, centre, meta = rectify(x, y, hub)
        assert meta.applied
        d_before = np.diff(np.unwrap(np.arctan2(y - hub[1], x - hub[0])))
        d_after = np.diff(np.unwrap(np.arctan2(yr - centre[1], xr - centre[0])))
        assert np.sign(np.median(d_before)) == np.sign(np.median(d_after))


def test_uniform_speed_stays_uniform():
    """The whole point: the 2/rev ripple foreshortening puts on omega must come out."""
    x, y, hub, _ = tilted_orbit(ratio=0.823, n=2000, turns=20.0)
    xr, yr, centre, meta = rectify(x, y, hub)
    w_before = np.diff(np.unwrap(np.arctan2(y - hub[1], x - hub[0])))
    w_after = np.diff(np.unwrap(np.arctan2(yr - centre[1], xr - centre[0])))
    sd_b = w_before.std() / abs(w_before.mean())
    sd_a = w_after.std() / abs(w_after.mean())
    assert sd_a < sd_b / 5, f"ripple not removed: {sd_b:.4f} -> {sd_a:.4f}"


def test_decentred_orbit_still_takes_the_perspective_path():
    """Regression: roundabout-4046's case must not be diverted into the affine branch."""
    x, y, _, _ = tilted_orbit(ratio=0.88)
    hub = (902.0 - 90.0, 502.0)                 # hub well off the ellipse centre
    _, _, _, meta = rectify(x, y, hub)
    assert meta.hub_offset_px >= MIN_HUB_OFFSET_PX
    assert meta.reason == "vanishing_line", meta.reason


def test_threshold_is_sane():
    assert 0.90 < AFFINE_MIN_AXIS_RATIO < 1.0
