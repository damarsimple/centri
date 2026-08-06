#!/usr/bin/env python3
"""The crop rectangle outranks the radius test when deciding coordinate space.

Pins the computerfan-4029-2 defect (2026-08-06). The tracker ran on the CROPPED
video, Step 5 declared "display", and the centre arrived as a `bootstrap` estimate
sitting ~260 px off the hub. The radius test compares the trajectory against that
centre, so BOTH of its readings were bad (cv 0.462 declared vs 0.243 untouched) and
it picked the less-bad wrong one: the trajectory kept its display coordinates.

Nothing downstream could see it. A RANSAC refit then moved the centre onto the
display-space trajectory, so the radius (305.3 px vs 306.9 measured off the video),
omega and a_c all came out RIGHT — while every frame overlay, including the figure
embedded in all three student worksheets, was drawn exactly roi_crop.y_off = 328 px
low, putting the "centre of rotation" on a fan blade.

The rectangle settles it without consulting the centre: the cropped video cannot
contain a detection outside its own frame. Here the trajectory reached y = 1384 in
a crop only 1244 tall.
"""
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workspace_lib"))
from analysis import common, contract

FPS = 60.0
N = 600
CROP_W, CROP_H = 1080.0, 1244.0
Y_OFF = 328.0
R = 380.0
# The true hub in cropped coordinates, as measured off the video by fitting the
# marker directly (RANSAC, 650 inliers, radius CV 0.014).
HUB_CROP = (552.8, 574.4)
HUB_DISPLAY = (HUB_CROP[0], HUB_CROP[1] + Y_OFF)
# The centre Step 5 actually supplied: `bootstrap`, 268 px from the true hub. This
# is what poisoned the radius test — it is wrong in a direction that makes the
# WRONG branch score better.
BAD_CENTRE_DISPLAY = (486.4, 1162.6)
# The ROI crop is fitted to contain ~99.3% of the trajectory, so a genuinely
# display-space orbit has a small tail outside it. That tail is the proof.


def _orbit(cx, cy, rx=R, ry=R, n=N):
    th = np.linspace(0, 8 * np.pi, n)
    return cx + rx * np.cos(th), cy + ry * np.sin(th)


def _write(tmp, x, y, cx, cy, space="display", x_off=0.0, y_off=Y_OFF,
           crop_w=CROP_W, crop_h=CROP_H, source="bootstrap"):
    p = Path(tmp) / "pipeline_inputs.json"
    p.write_text(json.dumps({
        "fps": FPS, "duration_s": len(x) / FPS, "n_raw_frames": len(x),
        "object_name": "red marker", "tracked_label": "red marker",
        "ref_label": "red marker",
        "trajectory_x_px": list(x), "trajectory_y_px": list(y),
        "center": {"cx_px": cx, "cy_px": cy, "source": source},
        "reference": {"diameter_px": 205.0, "physical_size_m": 0.04,
                      "physical_size_source": "sidecar"},
        "coordinate_space": space,
        "roi_crop": {"x_off": x_off, "y_off": y_off,
                     "crop_w": crop_w, "crop_h": crop_h},
    }))
    return p


def _load(path):
    common._validation_flags.clear()
    inp = contract.load_inputs(path)
    return inp, list(common.validation_flags())


# ── the defect ───────────────────────────────────────────────────────────────────
def test_display_trajectory_is_cropped_even_when_the_centre_is_bad():
    """The 4029-2 case: display-space trajectory + a centre 260 px off the hub.

    The radius test alone chooses wrong here. The crop rectangle must override it."""
    with tempfile.TemporaryDirectory() as tmp:
        x, y = _orbit(*HUB_DISPLAY)
        assert y.max() > CROP_H, "fixture must overshoot the crop to exercise the rule"
        inp, flags = _load(_write(tmp, x, y, *BAD_CENTRE_DISPLAY))

        assert "trajectory_space_mismatch" not in flags, flags
        # BOTH shifted, so trajectory and centre still share one space...
        assert abs(inp.y_px[0] - (y[0] - Y_OFF)) < 1e-6
        assert abs(inp.cy_px - (BAD_CENTRE_DISPLAY[1] - Y_OFF)) < 1e-6
        # ...and the trajectory now lands inside the frame the overlay is drawn on,
        # which is the whole point: the picture and the numbers agree again.
        assert np.nanmax(inp.y_px) < CROP_H, np.nanmax(inp.y_px)
        assert abs(np.nanmean(inp.y_px) - HUB_CROP[1]) < 5.0


def test_the_radius_test_alone_would_have_chosen_wrong():
    """Guards the REASON the rule exists, not just its effect.

    The rule only earns its place if the radius test genuinely fails on this input.
    Here every condition of the old branch is met — so without the rectangle the
    trajectory keeps its display coordinates. If this ever stops holding, the fixture
    has drifted off the defect and the test above proves less than it claims."""
    x, y = _orbit(*HUB_DISPLAY)
    cv_declared = contract._radius_cv(x, y, *BAD_CENTRE_DISPLAY)
    cv_untouched = contract._radius_cv(x + 0.0, y + Y_OFF, *BAD_CENTRE_DISPLAY)
    assert cv_declared > 0.15, cv_declared
    assert cv_untouched < 0.6 * cv_declared, (cv_untouched, cv_declared)


def test_the_rule_is_what_prevents_it():
    """Same input with the rectangle rule disabled must reproduce the old, wrong call.

    Pins cause to effect: if some later refactor makes the radius test right on this
    input, the guard above would pass for a reason that has nothing to do with it."""
    with tempfile.TemporaryDirectory() as tmp:
        x, y = _orbit(*HUB_DISPLAY)
        path = _write(tmp, x, y, *BAD_CENTRE_DISPLAY)
        real = contract._overshoot_px
        contract._overshoot_px = lambda *a, **k: (0.0, 0)   # blind the rule
        try:
            inp, flags = _load(path)
        finally:
            contract._overshoot_px = real
        assert "trajectory_space_mismatch" in flags, flags
        assert abs(inp.y_px[0] - y[0]) < 1e-6              # trajectory left in display
        assert np.nanmax(inp.y_px) > CROP_H                # ...and off the frame


# ── no regression on the clips that were already right ───────────────────────────
def test_trajectory_inside_the_crop_leaves_the_radius_test_in_charge():
    """turntable-1/2: display-space trajectory that happens to fit inside the crop.

    The rectangle proves nothing there, so behaviour must be exactly as before."""
    with tempfile.TemporaryDirectory() as tmp:
        x, y = _orbit(540.0, 700.0, rx=380.0, ry=380.0)
        assert y.min() > 0 and y.max() < CROP_H, "fixture must sit inside the crop"
        inp, flags = _load(_write(tmp, x, y, 540.0, 700.0, y_off=116.0,
                                  source="user_mark"))
        assert "trajectory_space_mismatch" not in flags, flags
        assert abs(inp.y_px[0] - (y[0] - 116.0)) < 1e-6


def test_genuine_mismatch_is_still_caught_when_the_rectangle_is_silent():
    """The roundabout-4046 defect must keep firing: cropped trajectory, full-frame
    centre, both labelled 'display'. The trajectory sits inside the crop, so only the
    radius test can see it — the new rule must not have disarmed it."""
    with tempfile.TemporaryDirectory() as tmp:
        cx_full, cy_full = 540.0, 998.0
        x, y = _orbit(cx_full, cy_full - 232.0, rx=476.0, ry=476.0)
        inp, flags = _load(_write(tmp, x, y, cx_full, cy_full, y_off=232.0,
                                  crop_w=1080.0, crop_h=1350.0,
                                  source="axle_detection"))
        assert "trajectory_space_mismatch" in flags, flags
        assert abs(inp.y_px[0] - y[0]) < 1e-6           # trajectory left alone
        assert abs(inp.cy_px - (cy_full - 232.0)) < 1e-6


def test_cropped_declaration_never_consults_the_rectangle():
    """A clip that says 'cropped' is taken at its word; the rule is display-only."""
    with tempfile.TemporaryDirectory() as tmp:
        x, y = _orbit(HUB_CROP[0], HUB_CROP[1] + Y_OFF + 100.0)
        inp, flags = _load(_write(tmp, x, y, 500.0, 900.0, space="cropped-video"))
        assert "trajectory_space_mismatch" not in flags, flags
        assert abs(inp.y_px[0] - y[0]) < 1e-6           # no shift at all


# ── the rule's own edges ─────────────────────────────────────────────────────────
def test_one_freak_point_outside_is_not_proof():
    """A single wild detection must not flip the decision; the bar is 3 points."""
    x, y = _orbit(540.0, 600.0, rx=300.0, ry=300.0)
    y = y.copy()
    y[17] = CROP_H + 400.0
    over, n_out = contract._overshoot_px(x, y, CROP_W, CROP_H)
    assert over > contract._OUTSIDE_MIN_PX and n_out == 1
    assert not (over > contract._OUTSIDE_MIN_PX and n_out >= contract._OUTSIDE_MIN_PTS)


def test_sub_pixel_rounding_is_not_an_overshoot():
    """Detection centroids are sub-pixel; that must not read as outside the frame."""
    x = np.array([0.0, CROP_W - 1.0 + 0.4, 500.0, 500.0])
    y = np.array([500.0, 500.0, -0.3, CROP_H - 1.0 + 0.9])
    _over, n_out = contract._overshoot_px(x, y, CROP_W, CROP_H)
    assert n_out == 0, n_out


def test_overshoot_ignores_nan_and_missing_crop_dims():
    x = np.array([100.0, np.nan, 200.0])
    y = np.array([np.nan, 300.0, 400.0])
    over, n_out = contract._overshoot_px(x, y, CROP_W, CROP_H)
    assert over == 0.0 and n_out == 0
    # a crop of unknown size can prove nothing
    over, n_out = contract._overshoot_px(np.array([9e4]), np.array([9e4]), 0.0, 0.0)
    assert over == 0.0 and n_out == 0


def test_real_4029_2_inputs_are_recognised_as_display():
    """The shipped pipeline_inputs.json, not a fixture — the numbers from the defect."""
    p = (Path(__file__).resolve().parents[2] / "workspaces" / "job_computerfan-4029-2"
         / "analysis_output" / "data" / "pipeline_inputs.json")
    if not p.exists():                       # workspace archived away; fixtures still cover it
        return
    d = json.loads(p.read_text())
    x = np.array([np.nan if v is None else float(v) for v in d["trajectory_x_px"]])
    y = np.array([np.nan if v is None else float(v) for v in d["trajectory_y_px"]])
    rc = d["roi_crop"]
    over, n_out = contract._overshoot_px(x, y, float(rc["crop_w"]), float(rc["crop_h"]))
    assert over > 100.0, over
    assert n_out >= contract._OUTSIDE_MIN_PTS, n_out


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"{len(fns)}/{len(fns)} passed")
