#!/usr/bin/env python3
"""Offline unit tests for the trajectory/centre coordinate-space guard in analysis.contract.

Pins the roundabout-4046 defect: the agent tracked on the CROPPED video but detected the
rotation centre on the FULL frame, then labelled the pair "display". `load_inputs` dutifully
subtracted the crop offset from both, leaving them 232 px apart — which reads downstream as a
real-but-eccentric orbit (radius 97->772 px, |omega| spread 57%, a_c 45% high), not as an error.
Only the validation flags fired, and they blamed the physics.

The guard must (a) catch that, (b) leave every correctly-declared clip untouched, and
(c) not fire on a genuine off-axis orbit, whose radius really does vary."""
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workspace_lib"))
from analysis import common, contract

FPS = 60.0
N = 600
CX_FULL, CY_FULL = 540.0, 998.0
Y_OFF, X_OFF = 232.0, 0.0
R = 476.0


def _orbit(cx, cy, rx=R, ry=R):
    th = np.linspace(0, 8 * np.pi, N)
    return cx + rx * np.cos(th), cy + ry * np.sin(th)


def _write(tmp, x, y, cx, cy, space, x_off=X_OFF, y_off=Y_OFF):
    p = Path(tmp) / "pipeline_inputs.json"
    p.write_text(json.dumps({
        "fps": FPS, "duration_s": N / FPS, "n_raw_frames": N,
        "object_name": "marker", "tracked_label": "marker", "ref_label": "marker",
        "trajectory_x_px": list(x), "trajectory_y_px": list(y),
        "center": {"cx_px": cx, "cy_px": cy, "source": "axle_detection"},
        "reference": {"diameter_px": 112.5, "physical_size_m": 0.06,
                      "physical_size_source": "sidecar"},
        "coordinate_space": space,
        "roi_crop": {"x_off": x_off, "y_off": y_off, "crop_w": 1080, "crop_h": 1350},
    }))
    return p


def _radius_cv(inp):
    r = np.hypot(inp.x_px - inp.cx_px, inp.y_px - inp.cy_px)
    r = r[np.isfinite(r)]
    return float(r.std() / r.mean())


def _load(path):
    common._validation_flags.clear()
    inp = contract.load_inputs(path)
    return inp, list(common.validation_flags())


def test_mismatch_is_caught():
    """Trajectory in cropped space, centre in full frame, both declared 'display'."""
    with tempfile.TemporaryDirectory() as tmp:
        x, y = _orbit(CX_FULL, CY_FULL - Y_OFF)          # cropped space
        inp, flags = _load(_write(tmp, x, y, CX_FULL, CY_FULL, "display"))
        assert "trajectory_space_mismatch" in flags, flags
        # centre cropped, trajectory left alone -> they share a space again
        assert _radius_cv(inp) < 0.01, _radius_cv(inp)
        assert abs(inp.cy_px - (CY_FULL - Y_OFF)) < 1e-6


def test_correctly_declared_display_is_untouched():
    """The normal path must keep subtracting the offset from BOTH."""
    with tempfile.TemporaryDirectory() as tmp:
        x, y = _orbit(CX_FULL, CY_FULL)                  # genuinely full-frame
        inp, flags = _load(_write(tmp, x, y, CX_FULL, CY_FULL, "display"))
        assert "trajectory_space_mismatch" not in flags, flags
        assert _radius_cv(inp) < 0.01
        assert abs(inp.y_px[0] - (y[0] - Y_OFF)) < 1e-6
        assert abs(inp.cy_px - (CY_FULL - Y_OFF)) < 1e-6


def test_cropped_declaration_is_untouched():
    with tempfile.TemporaryDirectory() as tmp:
        x, y = _orbit(CX_FULL, CY_FULL)
        inp, flags = _load(_write(tmp, x, y, CX_FULL, CY_FULL, "cropped-video"))
        assert "trajectory_space_mismatch" not in flags, flags
        assert abs(inp.y_px[0] - y[0]) < 1e-6            # no shift at all
        assert abs(inp.cy_px - CY_FULL) < 1e-6


def test_off_axis_orbit_does_not_trip_the_guard():
    """A real circle filmed off-axis images as an ellipse, so its radius genuinely
    varies. That must not be mistaken for a frame mismatch — shifting such a track
    makes it worse, not better, which is exactly what the guard measures."""
    with tempfile.TemporaryDirectory() as tmp:
        x, y = _orbit(CX_FULL, CY_FULL, rx=R, ry=0.60 * R)   # ~53 deg tilt
        inp, flags = _load(_write(tmp, x, y, CX_FULL, CY_FULL, "display"))
        assert "trajectory_space_mismatch" not in flags, flags


def test_no_crop_offset_is_a_no_op():
    with tempfile.TemporaryDirectory() as tmp:
        x, y = _orbit(CX_FULL, CY_FULL)
        inp, flags = _load(_write(tmp, x, y, CX_FULL, CY_FULL, "display",
                                  x_off=0.0, y_off=0.0))
        assert "trajectory_space_mismatch" not in flags, flags


def test_ellipse_fit_degrades_to_a_circle():
    """The drawing helper must not invent eccentricity on a face-on clip."""
    x, y = _orbit(500.0, 400.0, rx=250.0, ry=250.0)
    cx, cy, a, b, _ang = common.fit_orbit_ellipse(x, y)
    assert abs(a - b) < 1.0, (a, b)
    assert abs(a - 250.0) < 1.0 and abs(cx - 500.0) < 1.0 and abs(cy - 400.0) < 1.0
    # and it must recover a real ellipse
    x2, y2 = _orbit(500.0, 400.0, rx=300.0, ry=200.0)
    _cx, _cy, a2, b2, _a = common.fit_orbit_ellipse(x2, y2)
    assert abs(a2 - 300.0) < 1.0 and abs(b2 - 200.0) < 1.0, (a2, b2)
    assert common.fit_orbit_ellipse([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) is None


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"{len(fns)}/{len(fns)} passed")
