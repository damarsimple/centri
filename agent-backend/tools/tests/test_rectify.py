#!/usr/bin/env python3
"""Offline unit tests for analysis.rectify — projective un-projection of a circular orbit.

The ground truth here is synthetic: take a circle turning at a KNOWN uniform rate, push it
through a KNOWN homography with a perspective term, and check that rectification gives the
uniform rate back. That is a stronger claim than "the curve got smoother", which any filter
can deliver — see the prototype's docstring and roundabout-4046's hints."""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workspace_lib"))
from analysis import rectify as RC

N = 600
R_WORLD = 1.0
TURNS = 4.0


def _project(H, x, y):
    P = np.c_[x, y, np.ones_like(x)] @ H.T
    return P[:, 0] / P[:, 2], P[:, 1] / P[:, 2]


def _scene(h31=-0.20, h32=-0.15, scale=400.0, offset=(700.0, 700.0)):
    """A circle turning uniformly, imaged by a camera with real perspective."""
    th = np.linspace(0, TURNS * 2 * np.pi, N)
    xw, yw = R_WORLD * np.cos(th), R_WORLD * np.sin(th)
    H = np.array([[scale, 0.0, offset[0]],
                  [0.0, scale, offset[1]],
                  [h31, h32, 1.0]])
    xi, yi = _project(H, xw, yw)
    hub = _project(H, np.array([0.0]), np.array([0.0]))       # image of the world centre
    return th, xi, yi, (float(hub[0][0]), float(hub[1][0]))


def _omega_uniformity(x, y, cx, cy):
    """Spread of the per-step angular increment, relative to its mean. Zero for a
    uniformly turning object measured in a metric plane."""
    th = np.unwrap(np.arctan2(y - cy, x - cx))
    d = np.diff(th)
    return float(np.std(d) / abs(np.mean(d)))


def test_recovers_a_uniform_rate_through_a_known_homography():
    _th, xi, yi, hub = _scene()
    before = _omega_uniformity(xi, yi, *hub)
    xr, yr, cen, meta = RC.rectify(xi, yi, hub)
    assert meta.applied, meta.reason
    after = _omega_uniformity(xr, yr, *cen)
    assert after < before / 5.0, (before, after)
    assert after < 0.02, after


def test_mean_rate_is_preserved():
    """Rectification redistributes angle WITHIN a revolution; it cannot change how many
    revolutions happened. A mean that moves means real signal is being fitted away."""
    _th, xi, yi, hub = _scene()
    xr, yr, cen, meta = RC.rectify(xi, yi, hub)
    tot_before = abs(np.unwrap(np.arctan2(yi - hub[1], xi - hub[0]))[-1]
                     - np.unwrap(np.arctan2(yi - hub[1], xi - hub[0]))[0])
    tot_after = abs(np.unwrap(np.arctan2(yr - cen[1], xr - cen[0]))[-1]
                    - np.unwrap(np.arctan2(yr - cen[1], xr - cen[0]))[0])
    assert abs(tot_after - tot_before) / tot_before < RC.MAX_MEAN_OMEGA_DRIFT
    assert abs(tot_before - TURNS * 2 * np.pi) < 0.2      # sanity: the scene is what we think


def test_rotation_direction_is_preserved():
    """The metric stage must keep det=+1, or omega flips sign and the material narrates
    the video backwards."""
    for sign in (+1.0, -1.0):
        th = np.linspace(0, sign * TURNS * 2 * np.pi, N)
        xw, yw = R_WORLD * np.cos(th), R_WORLD * np.sin(th)
        H = np.array([[400.0, 0, 700.0], [0, 400.0, 700.0], [-0.20, -0.15, 1.0]])
        xi, yi = _project(H, xw, yw)
        hub = _project(H, np.array([0.0]), np.array([0.0]))
        hub = (float(hub[0][0]), float(hub[1][0]))
        xr, yr, cen, meta = RC.rectify(xi, yi, hub)
        assert meta.applied
        d = np.diff(np.unwrap(np.arctan2(yr - cen[1], xr - cen[0])))
        assert math.copysign(1.0, np.mean(d)) == math.copysign(1.0, sign), sign


def test_face_on_clip_is_left_alone():
    """No perspective => nothing to undo, and fitting the vanishing line to noise would
    inject error. The corpus's near-affine clips sit at 0.7-8.8 px of hub offset."""
    _th, xi, yi, hub = _scene(h31=0.0, h32=0.0)
    xr, yr, cen, meta = RC.rectify(xi, yi, hub)
    assert not meta.applied
    assert "hub_offset_below" in meta.reason, meta.reason
    assert xr is xi and yr is yi


def test_no_hub_is_not_an_error():
    _th, xi, yi, _hub = _scene()
    xr, yr, cen, meta = RC.rectify(xi, yi, None)
    assert not meta.applied and meta.reason == "no_hub_px"
    assert cen is None and xr is xi


def test_nans_survive_and_do_not_break_the_fit():
    _th, xi, yi, hub = _scene()
    xi, yi = xi.copy(), yi.copy()
    xi[10:40] = np.nan
    yi[10:40] = np.nan
    xr, yr, cen, meta = RC.rectify(xi, yi, hub)
    assert meta.applied, meta.reason
    assert np.all(np.isnan(xr[10:40])) and np.all(np.isnan(yr[10:40]))
    assert np.isfinite(xr[50:]).all()


def test_meta_is_json_safe_when_skipped():
    """writer.py dumps stats.json with allow_nan=False. A skipped rectification leaves
    every diagnostic NaN, which truncated stats.json mid-write until as_dict cleaned it."""
    _th, xi, yi, _hub = _scene()
    _xr, _yr, _cen, meta = RC.rectify(xi, yi, None)
    json.dumps(meta.as_dict(), allow_nan=False)          # must not raise
    _th2, xi2, yi2, hub2 = _scene()
    _a, _b, _c, meta2 = RC.rectify(xi2, yi2, hub2)
    json.dumps(meta2.as_dict(), allow_nan=False)


def test_ellipse_centre_as_hub_is_refused_or_inert():
    """THE classic error: pass the centre of the ellipse you SEE instead of the imaged
    axle. Its polar is the line at infinity, the homography is the identity, and you have
    silently done nothing. The hub-offset gate must catch that rather than pretend."""
    _th, xi, yi, _hub = _scene()
    p = RC.conic_params(RC.fit_conic(xi, yi))
    ellipse_centre = (float(p["c"][0]), float(p["c"][1]))
    _xr, _yr, _cen, meta = RC.rectify(xi, yi, ellipse_centre)
    assert not meta.applied, "using the ellipse centre must not count as rectification"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"{len(fns)}/{len(fns)} passed")
