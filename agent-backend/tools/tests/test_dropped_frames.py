#!/usr/bin/env python3
"""Offline unit tests for dropped-source-frame detection in analysis.contract.

Pins the turntable-3 defect. The camera dropped one frame at t=2.99 s, leaving a hole in
an otherwise constant-rate timeline. Frame extraction runs at a constant rate, so ffmpeg
filled the hole by repeating the previous image (351 images from 350 real frames). The
repeat is a valid picture, so trackers reported it faithfully — the object does not move
across it — and two independent trackers agreed on that to the pixel. Downstream, with
time assumed uniform, one motionless step followed by a normal one reads as the turntable
stopping and then speeding back up: an acceleration no coasting body can produce. That is
the phantom v(t) bump.

The detector must (a) find the repeated slots from TIMESTAMPS, never from a frozen
position — every clip in the corpus ends with the object genuinely at rest — (b) place
them at the right indices when the hole is mid-clip, (c) stay silent on a clean
constant-rate clip, and (d) degrade quietly when timestamps cannot be read at all."""
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workspace_lib"))
from analysis import contract

FPS = 59.94005994005994
DT = 1.0 / FPS


def _fake_probe(monkey_ts):
    """Replace the ffprobe call with a canned timestamp list."""
    def _probe(video):
        return None if monkey_ts is None else np.asarray(monkey_ts, dtype=float)
    return _probe


def _uniform(n):
    return np.arange(n) * DT


def _with_drop_at(n, k, missing=1):
    """Constant-rate timestamps with `missing` frames absent after index k."""
    t = list(_uniform(k + 1))
    nxt = t[-1] + (missing + 1) * DT
    for i in range(n - k - 1):
        t.append(nxt + i * DT)
    return np.array(t)


def _run(ts, n_frames=350):
    orig = contract._frame_timestamps
    contract._frame_timestamps = _fake_probe(ts)
    try:
        return contract.duplicated_frame_indices(Path("unused.mp4"), n_frames)
    finally:
        contract._frame_timestamps = orig


def test_clean_clip_reports_nothing():
    assert _run(_uniform(350)) == []


def test_single_drop_is_found_at_the_right_index():
    # turntable-3: one frame missing after index 179
    dup = _run(_with_drop_at(350, 179))
    assert dup == [180], dup


def test_drop_near_the_start():
    assert _run(_with_drop_at(300, 3)) == [4]


def test_two_consecutive_missing_frames_yield_two_repeats():
    assert _run(_with_drop_at(300, 100, missing=2)) == [101, 102]


def test_two_separate_holes_shift_the_second_index():
    """Indices are positions in the EXTRACTED sequence, not in the source. The first
    hole inserts an image, so real frame 99 already sits at extracted slot 100 and its
    repeat lands at 101 — not at 100, which is where counting in source frames would
    put it. Getting this wrong blanks a good frame and leaves the repeat in place."""
    t = list(_uniform(50))
    t += [t[-1] + 2 * DT]                       # hole after real frame 49
    t += [t[-1] + (i + 1) * DT for i in range(49)]
    t += [t[-1] + 2 * DT]                       # hole after real frame 99
    t += [t[-1] + (i + 1) * DT for i in range(50)]
    dup = _run(np.array(t))
    assert dup == [50, 101], dup


def test_at_rest_tail_is_not_mistaken_for_a_drop():
    """Every clip ends with the object stationary — many frames with identical content
    and zero displacement. Timestamps stay uniform there, so nothing may be flagged."""
    assert _run(_uniform(350)) == []


def test_indices_beyond_the_trajectory_are_discarded():
    assert _run(_with_drop_at(350, 340), n_frames=100) == []


def test_unreadable_timestamps_degrade_quietly():
    assert _run(None) == []


def test_jitter_below_the_threshold_is_ignored():
    t = _uniform(200)
    rng = np.random.default_rng(0)
    t = t + rng.normal(0, 0.05 * DT, t.size)    # 5% timing noise, no real drop
    t = np.sort(t)
    assert _run(t) == []


def test_real_turntable3_clip_if_present():
    """Against the actual file, when it is available: exactly one repeat, at 180."""
    v = Path("/home/damar/centri/agent-backend/workspaces/job_turntable-3-rect/input_video.mp4")
    if not v.exists():
        return
    assert contract.duplicated_frame_indices(v, 350) == [180]


def test_real_clean_clip_if_present():
    v = Path("/home/damar/centri/agent-backend/workspaces/job_turntable-2-rect/input_video.mp4")
    if not v.exists():
        return
    assert contract.duplicated_frame_indices(v, 253) == []


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
            print(f"  ok   {name}")
        except AssertionError as e:
            fails += 1
            print(f"  FAIL {name}: {e}")
    print(f"\n{'FAILED' if fails else 'all passed'} ({fails} failures)")
    sys.exit(1 if fails else 0)
