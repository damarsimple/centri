#!/usr/bin/env python3
"""Offline unit tests for the direction convention every reader-facing arrow depends on
(analysis/common.travel_sign) and for the rest-band wording on the shaded graphs.

Pins a bug that shipped: the arrows asked ``sign(canonical_omega(stats))``, but
canonical_omega returns a MAGNITUDE, so the test was always True and v / omega were drawn
CLOCKWISE on every clip. Both ceiling fans turn counter-clockwise, so all six of their
worksheets pointed the arrows backwards along the orbit — while the prose, the measurement
table and the phase-band words had already been resolved to speed. The general rule these
tests defend: anything that must know WHICH WAY reads `rotation_direction`; anything that
must know HOW FAST reads a magnitude; the two are never derived from each other."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "workspace_lib"))
from analysis.common import canonical_omega, travel_sign
from analysis.render.figures import PHASE_WORDS, REST_WORDS


def _stats(direction, mean_omega, motion="decelerating"):
    return {
        "summary": {"rotation_direction": direction, "mean_omega": mean_omega},
        "angular_acceleration": {"motion_type": motion},
        "stable_phase": {},
    }


# ── travel_sign reads the direction label, not the sign of a magnitude ───────

def test_clockwise_travels_with_increasing_theta():
    # theta = atan2 in image coords (y down) => increasing theta is CW on screen.
    assert travel_sign(_stats("CW", 7.19)) == 1.0


def test_counter_clockwise_travels_against_increasing_theta():
    assert travel_sign(_stats("CCW", -5.70)) == -1.0


def test_direction_survives_a_positive_stored_omega():
    """The regression itself: fan-4028 is CCW, and canonical_omega hands back +5.70.
    Anything deriving direction from that value gets CW and draws the arrows backwards."""
    st = _stats("CCW", -5.70)
    omega_val, _ = canonical_omega(st)
    assert omega_val > 0                      # canonical_omega is a magnitude ...
    assert travel_sign(st) == -1.0            # ... and must not decide direction


def test_missing_direction_defaults_to_clockwise_not_a_crash():
    assert travel_sign({}) == 1.0
    assert travel_sign({"summary": {}}) == 1.0


# ── a rest band has to say it is a rest band ─────────────────────────────────

def test_rest_bands_carry_a_word():
    """An unlabelled grey band let marker jitter read as physics: on turntable-3 the
    inactive samples reach a_c 21.3 m/s^2 — 68% of that clip's largest ACTIVE value."""
    assert REST_WORDS["INACTIVE"] == "not turning"
    assert REST_WORDS["IDLE"] == "not turning"


def test_rest_words_stay_out_of_phase_words():
    """PHASE_WORDS membership also gates `_phase_significant`, which drops slivers, and a
    rest band must keep its shading however short it is. It is likewise excluded from the
    prose phase sequence, so naming it cannot change any phase COUNT the gate checks."""
    assert not (set(REST_WORDS) & set(PHASE_WORDS))
