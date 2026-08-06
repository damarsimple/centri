"""The temporal gate must be able to let go.

Regression for the sticky-lock defect found on the fan reshoot (2026-08-06): a miss
left `prev` untouched, so ONE step longer than `max_step_px` froze the lock at a
stale point and the marker was only re-found when its orbit carried it back within
`max_step_px` of that point — once per revolution. Measured on `fan-4656`,
`max_step=90` gave 26.9% coverage where no gate gave 99.99%.

These tests drive `track()` on synthetic footage so they need no clip and no GPU.
"""
import os
import tempfile

import cv2
import numpy as np
import pytest

from workspace_lib.analysis.color_track import track

FPS = 30
W, H = 320, 240
CX, CY, R = 160.0, 120.0, 70.0
HSV_LO, HSV_HI = [10, 90, 90], [35, 255, 255]
MARKER_BGR = (0, 200, 255)   # saturated yellow-orange, inside the band


def _write_clip(path, angles, hide=()):
    """One marker orbiting at the given angles, absent for the frames in `hide`.

    A gap is the realistic trigger, not a teleport. On `fan-4656` the marker dipped
    below `min_area` for a few blurred frames at speed; by the time it came back it
    was most of a revolution from where the frozen lock still expected it.
    """
    vw = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    assert vw.isOpened()
    hide = set(hide)
    for i, a in enumerate(angles):
        frame = np.full((H, W, 3), 245, np.uint8)          # bright, unsaturated background
        if i not in hide:
            x, y = CX + R * np.cos(a), CY + R * np.sin(a)
            cv2.circle(frame, (int(x), int(y)), 11, MARKER_BGR, -1)
        vw.write(frame)
    vw.release()


def _run(path, **kw):
    return track(path, "marker", HSV_LO, HSV_HI, min_area=40, **kw)


@pytest.fixture
def clipdir():
    with tempfile.TemporaryDirectory() as d:
        yield d


def test_sticky_lock_is_gone(clipdir):
    """A short gap must cost a short gap, not the rest of the clip.

    6 deg/frame at R=70 is a ~7 px chord, well inside max_step=40. The marker then
    drops out for 8 frames at a time — 48 deg of orbit, a 57 px chord, outside the
    gate — and does so again before it could have come back round. That recurrence
    is the real mechanism: on `fan-4656` the blurred marker dipped under `min_area`
    on ~5% of frames, and each dip stranded the frozen lock for most of a revolution.
    """
    n = 400
    angles = np.deg2rad(np.arange(n) * 6.0)
    hide = [i for i in range(n) if 0 <= (i % 40) < 8 and i > 30]
    path = os.path.join(clipdir, "gap.mp4")
    _write_clip(path, angles, hide=hide)

    sticky = _run(path, max_step_px=40, relock_after=0)     # old behaviour
    fixed = _run(path, max_step_px=40, relock_after=5)      # shipped default

    # 20% of frames have no marker at all, so ~0.80 is the ceiling.
    assert fixed["track_coverage"] > 0.72, fixed["track_coverage"]
    # The old lock could only re-acquire when the orbit carried the marker back
    # past the frozen point — and the next dropout arrived first.
    assert fixed["track_coverage"] > sticky["track_coverage"] + 0.25, (
        fixed["track_coverage"], sticky["track_coverage"])
    assert fixed["n_relocks"] >= 1
    assert sticky["n_relocks"] == 0


def test_relock_costs_only_the_relock_window(clipdir):
    """Recovery must be bounded by relock_after, not by the orbit period."""
    n = 200
    angles = np.deg2rad(np.arange(n) * 12.0)
    path = os.path.join(clipdir, "gap2.mp4")
    _write_clip(path, angles, hide=range(40, 55))

    res = _run(path, max_step_px=40, relock_after=3)
    misses = [e["frame"] for e in res["trajectories"]["marker"] if e["cx"] is None]
    # the 15 hidden frames, plus at most a few more spent letting the stale lock go
    assert len(misses) <= 15 + 4, misses


def test_clean_clip_never_relocks(clipdir):
    """No false relocks when the gate is comfortable — the count is a real signal."""
    n = 150
    angles = np.deg2rad(np.arange(n) * 6.0)
    path = os.path.join(clipdir, "clean.mp4")
    _write_clip(path, angles)

    res = _run(path, max_step_px=60, relock_after=5)
    assert res["track_coverage"] == 1.0
    assert res["n_relocks"] == 0


def test_gate_still_rejects_a_lookalike(clipdir):
    """Relocking must not defeat the gate's purpose: a rival blob is still refused
    while the lock is live."""
    n = 60
    vw = cv2.VideoWriter(os.path.join(clipdir, "rival.mp4"),
                         cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    for i in range(n):
        frame = np.full((H, W, 3), 245, np.uint8)
        a = np.deg2rad(i * 6.0)
        cv2.circle(frame, (int(CX + R * np.cos(a)), int(CY + R * np.sin(a))), 9, MARKER_BGR, -1)
        if i >= 20:                       # a BIGGER rival appears far away and never moves
            cv2.circle(frame, (30, 210), 14, MARKER_BGR, -1)
        vw.write(frame)
    vw.release()

    res = _run(os.path.join(clipdir, "rival.mp4"), max_step_px=45, relock_after=5)
    pts = [(e["cx"], e["cy"]) for e in res["trajectories"]["marker"] if e["cx"] is not None]
    rad = [np.hypot(x - CX, y - CY) for x, y in pts]
    # every accepted point stayed on the orbit; none jumped to the fat rival
    assert max(rad) < R * 1.35, max(rad)
