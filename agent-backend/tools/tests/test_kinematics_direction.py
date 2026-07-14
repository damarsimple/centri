#!/usr/bin/env python3
"""Offline unit test for the VIEWER-FRAME rotation direction (analysis/kinematics.compute).

Pins C1: theta = arctan2(dy, dx) is measured in image/pixel coordinates where the row index
dy grows DOWNWARD, so a point tracing right -> bottom -> left -> top on screen (increasing
theta, omega > 0) is CLOCKWISE as the viewer sees it. The reported `rotation_direction` must
match what plays on screen (it used to be inverted — a CW clip was labelled "CCW", which the
material prose then narrated against the video)."""
import os
import sys
import tempfile
import types

import numpy as np

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "workspace_lib"))
from analysis import kinematics as K


def _direction_for(theta_sign):
    """Run compute() on a uniform circle whose on-screen sense is set by theta_sign
    (+1 = right->bottom->left->top = clockwise on screen)."""
    fps, R, cx, cy = 60.0, 100.0, 300.0, 300.0
    n = int(3.0 * fps)
    t = np.arange(n) / fps
    theta = theta_sign * 2.0 * np.pi * t          # |omega| ~ 2*pi rad/s
    x = cx + R * np.cos(theta)
    y = cy + R * np.sin(theta)                    # image coords: +y is DOWN on screen
    inp = types.SimpleNamespace(fps=fps, n_raw_frames=n, duration_s=n / fps)
    cal = types.SimpleNamespace(cx_px=cx, cy_px=cy, px_per_m=1000.0,
                                r_fit_m=R / 1000.0, r_fit_px=R)
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "analysis_output/data"))
    cwd = os.getcwd()
    os.chdir(d)
    try:
        return K.compute(inp, cal, x.copy(), y.copy()).rotation_direction
    finally:
        os.chdir(cwd)


def test_clockwise_on_screen_is_labelled_cw():
    # right -> bottom -> left -> top in image coordinates = clockwise as viewed.
    assert _direction_for(+1) == "CW"


def test_counterclockwise_on_screen_is_labelled_ccw():
    assert _direction_for(-1) == "CCW"


if __name__ == "__main__":
    test_clockwise_on_screen_is_labelled_cw()
    test_counterclockwise_on_screen_is_labelled_ccw()
    print("ok")
