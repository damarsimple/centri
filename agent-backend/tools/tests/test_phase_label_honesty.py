"""A phase band's WORD must not contradict the curve underneath it.

Found by the Axis-4 (multimodal) judge on 2026-07-31, not by the gate: `omega_t.png` for
`computerfan-4029` printed "not turning" over a band whose samples reached 24 rad/s. The
segmenter had mis-marked bursts as INACTIVE, and adding rest-band labels earlier that day turned
that silent error into a printed falsehood. The gate never saw it, because the gate checks
annotations against the seed and never asks whether a band label agrees with the plotted series.

The shading may stay — a colour is not a claim. The word must go.
"""
import pathlib
import sys

import numpy as np
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "workspace_lib"))

figures = pytest.importorskip("analysis.render.figures")


def contradicted(y, s, e):
    y = np.asarray(y, dtype=float)
    finite = y[np.isfinite(y)]
    ymax = float(np.nanmax(np.abs(finite))) if finite.size else None
    return figures._rest_label_is_contradicted(y, s, e, ymax)


def test_rest_over_a_genuine_burst_is_contradicted():
    """The computerfan-4029 shape: a long flat stretch that contains a spike to 24 rad/s."""
    y = np.zeros(100)
    y[40:50] = 24.0
    assert contradicted(y, 0, 100) is True


def test_rest_over_true_rest_is_allowed():
    y = np.concatenate([np.zeros(50), np.linspace(0, 20, 50)])
    assert contradicted(y, 0, 50) is False


def test_only_the_band_is_examined_not_the_whole_series():
    """A burst OUTSIDE the band must not suppress a label for a band that really is at rest."""
    y = np.zeros(100)
    y[80:90] = 30.0
    assert contradicted(y, 0, 40) is False
    assert contradicted(y, 75, 95) is True


def test_threshold_is_relative_so_it_holds_for_any_unit():
    """Same shape in rad/s and in m/s^2 must give the same verdict — the check is scale-free."""
    y = np.zeros(100)
    y[10:20] = 1.0
    big = y * 1000.0
    assert contradicted(y, 0, 100) == contradicted(big, 0, 100) is True


def test_small_jitter_inside_rest_does_not_suppress_the_word():
    """Rest bands are never numerically perfect; 1% of full scale must still read as rest."""
    y = np.zeros(100)
    y[0:50] = 0.01 * 20.0     # 1% of the series maximum
    y[60:70] = 20.0
    assert contradicted(y, 0, 50) is False


def test_all_nan_band_is_not_called_contradicted():
    """A tracking dropout is missing data, not evidence of motion."""
    y = np.full(50, np.nan)
    y2 = np.concatenate([y, np.linspace(0, 10, 50)])
    assert contradicted(y2, 0, 50) is False


def test_missing_series_degrades_to_permissive():
    """With no curve to check against, the guard must not silently blank every label."""
    assert figures._rest_label_is_contradicted(None, 0, 10, 5.0) is False
    assert figures._rest_label_is_contradicted(np.zeros(10), 0, 10, None) is False
