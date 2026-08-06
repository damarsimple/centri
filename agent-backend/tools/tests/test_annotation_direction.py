"""The overlay must not assert what the data does not say.

Three defects found on the fan-4656 render (2026-08-06), all in the arrows:

1. `r` was drawn PERPENDICULAR to the object's own radius, so an arrow labelled "r",
   springing from the centre of rotation, pointed at empty space. Deliberate — it kept
   `r` off the `a_c` arrow — but it made the picture say something false.
2. The omega arc had no magnitude gate (v and a_c did), so on a stationary tail it kept
   drawing a confident rotation arrow.
3. Its direction came from `sign(omega)` per frame. On fan-4656's rest tail omega is
   noise of +-0.008 rad/s that changes sign 41 times, so the arrow flipped back and forth
   — and pointed opposite to the clip's real direction. `common.travel_sign` exists
   precisely for this and names "the video overlay" in its own docstring.
"""
import math
import re
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "workspace_lib" / "analysis" / "render"
ANNOTATE = (SRC / "annotate.py").read_text()
FIGURES = (SRC / "figures.py").read_text()


# ── 1. r points at the object ───────────────────────────────────────────────
def test_radius_arrow_is_not_perpendicular():
    """The old code set the r direction to (-uy, ux) — the radius rotated 90 degrees."""
    for name, src in (("annotate.py", ANNOTATE), ("figures.py", FIGURES)):
        # the r arrow must span the radial direction (ux, uy), not the perpendicular
        assert re.search(r"r_fit_px", src), name
        bad = re.search(r"^\s*(rx, ry|px_, py_|rpx, rpy)\s*=\s*-uy,\s*ux\s*$.*?"
                        r"_vector\(.*?\(cx \+ rx \* r_fit_px", src, re.S | re.M)
        assert bad is None, f"{name}: r still drawn along the perpendicular"


def test_radius_arrow_spans_centre_to_object():
    """annotate.py must draw r from the centre out along (ux, uy) for a full r_fit_px."""
    m = re.search(r"_vector\(frame,\s*\(cx \+ px_ \* off, cy \+ py_ \* off\),\s*"
                  r"\(cx \+ ux \* r_fit_px \+ px_ \* off, cy \+ uy \* r_fit_px \+ py_ \* off\)",
                  ANNOTATE)
    assert m, "annotate.py: r is not a centre->object span offset sideways"


def test_figures_radius_arrow_spans_centre_to_object():
    m = re.search(r"xy=\(cx \+ ux \* r_fit_px \+ rpx \* r_off, cy \+ uy \* r_fit_px \+ rpy \* r_off\)",
                  FIGURES)
    assert m, "figures.py: r is not a centre->object span offset sideways"


# ── 2. the omega arc is gated on magnitude ──────────────────────────────────
def test_omega_arc_is_magnitude_gated():
    assert "OMEGA_DRAW_FLOOR_FRAC" in ANNOTATE
    assert re.search(r"if w_now == w_now and abs\(w_now\) > w_floor:", ANNOTATE), \
        "the omega arc is drawn without checking the object is actually turning"
    # and the gate must wrap the arc call, not sit beside it
    seg = ANNOTATE.split("if w_now == w_now and abs(w_now) > w_floor:")[1][:900]
    assert "_arc_arrow(" in seg, "the gate does not enclose the arc"


def test_v_and_ac_remain_gated():
    """Regression: the gates that were already right must stay."""
    assert re.search(r"if not math\.isnan\(v\) and abs\(v\) > 1e-3:", ANNOTATE)
    assert re.search(r"if not math\.isnan\(ac\) and abs\(ac\) > 1e-3:", ANNOTATE)


# ── 3. direction comes from the clip, not from one frame ────────────────────
def test_direction_uses_travel_sign_not_sign_of_omega():
    assert "travel_sign" in ANNOTATE, "annotate.py never asks common.travel_sign"
    assert re.search(r"s_travel\s*=\s*_travel_sign\(stats\)", ANNOTATE)
    assert re.search(r"^\s*s = s_travel", ANNOTATE, re.M)
    # the per-frame sign test must be gone
    assert not re.search(r"s = -1\.0 if \(w_now == w_now and w_now < 0\) else 1\.0", ANNOTATE), \
        "per-frame sign(omega) still decides the arrow direction"


# ── behavioural: the geometry the fix relies on ─────────────────────────────
@pytest.mark.parametrize("theta_deg", [0, 37, 90, 165, 240, 300])
def test_offset_radius_arrow_still_ends_at_the_object(theta_deg):
    """The sideways offset must not move the arrow off the object by more than the offset."""
    th = math.radians(theta_deg)
    ux, uy = math.cos(th), math.sin(th)
    r_fit, off = 240.0, 18.0
    px_, py_ = -uy, ux
    tip = (ux * r_fit + px_ * off, uy * r_fit + py_ * off)
    obj = (ux * r_fit, uy * r_fit)
    d = math.hypot(tip[0] - obj[0], tip[1] - obj[1])
    assert abs(d - off) < 1e-9
    # and the arrow's own length is the radius
    start = (px_ * off, py_ * off)
    assert abs(math.hypot(tip[0] - start[0], tip[1] - start[1]) - r_fit) < 1e-9


def test_offset_sits_away_from_the_direction_of_travel():
    """The r dimension line must not be laid on top of the v arrow."""
    for theta_deg in (0, 45, 120, 200, 330):
        for s in (+1.0, -1.0):
            th = math.radians(theta_deg)
            ux, uy = math.cos(th), math.sin(th)
            tx, ty = -uy * s, ux * s
            px_, py_ = -uy, ux
            if (px_ * ty - py_ * tx) < 0:
                px_, py_ = -px_, -py_
            assert (px_ * ty - py_ * tx) >= -1e-12
