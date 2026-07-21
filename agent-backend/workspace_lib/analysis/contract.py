"""Input contract for the frozen pipeline.

The agentic perception steps (scene understanding, SAM tracking, center mark,
reference sizing) are the *only* place pi still writes code. Their single job is
to produce `analysis_output/data/pipeline_inputs.json` matching the schema below.
Everything downstream is deterministic.

Keeping this seam as one well-defined file is what lets us freeze steps 4-8:
same `pipeline_inputs.json` -> byte-identical `stats.json`.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import common

INPUTS_PATH = Path("analysis_output/data/pipeline_inputs.json")

# Where to look for the clip the trajectory was measured from, relative to the job root.
# Only used to read frame timestamps; nothing here decodes pixels.
_VIDEO_CANDIDATES = ("input_video.mp4", "analysis_output/roi/cropped.mp4")

# A frame interval this much longer than the median means the camera dropped a frame.
# Phone captures are nominally constant-rate, so a genuine drop stands out as a clean
# integer multiple; 1.5x separates it from timestamp jitter without catching rounding.
_DROP_RATIO = 1.5

# Required top-level keys; the run aborts loudly if any are missing rather than
# silently inventing values (the old failure mode).
#
# `coordinate_space` + `roi_crop` are required so the display→cropped transform
# lives HERE (deterministic), not in the agent. The agent emits the raw tracker
# trajectory and center in full-frame ("display") space; this module subtracts the
# crop offset from BOTH together, guaranteeing they always share one space. The old
# bug — the LLM crop-subtracting the trajectory inconsistently while the center
# stayed cropped — is structurally impossible once the agent never does the math.
#
# What remained possible is the agent MIS-DECLARING the space it wrote: tracking on
# the cropped video while detecting the centre on the full frame, then labelling the
# pair "display". Doing the transform here does not catch that — both get shifted,
# so they end up an offset apart. `load_inputs` therefore measures the two readings
# against each other and keeps the self-consistent one (see the guard below).
REQUIRED = (
    "fps", "duration_s", "n_raw_frames",
    "object_name", "tracked_label", "ref_label",
    "trajectory_x_px", "trajectory_y_px",
    "center", "reference",
    "coordinate_space", "roi_crop",
)

# Accepted spellings for the two coordinate spaces the contract understands.
_DISPLAY_SPACES = {"display", "full_frame", "full-frame", "original", "full"}
_CROPPED_SPACES = {"cropped", "crop", "cropped-video", "cropped_video"}


class ContractError(ValueError):
    """Raised when pipeline_inputs.json is missing or malformed."""


@dataclass
class Inputs:
    fps: float
    duration_s: float
    n_raw_frames: int
    object_name: str
    tracked_label: str
    ref_label: str
    # Short, human-friendly scene name for artifact titles (plots, report), e.g.
    # "red phone on turntable". Optional in the contract; falls back to
    # "<tracked> on <ref>" so older inputs still produce a usable title.
    scene_title: str
    # Per-frame tracked-object centroid in CROPPED-VIDEO space; null where the
    # detector missed the frame. Both arrays length == n_raw_frames.
    x_px: np.ndarray
    y_px: np.ndarray
    # Rotation center in cropped space + provenance ("user_mark" | "bootstrap").
    cx_px: float
    cy_px: float
    center_source: str
    # Reference object: its measured pixel diameter, the real-world size it maps
    # to (metres), and where that size came from ("sidecar" | "vlm" | "default").
    diameter_px: float
    physical_size_m: float
    physical_size_source: str
    # Opaque passthrough recorded in stats.json for external remapping.
    roi_crop: dict
    # The IMAGED AXLE, when the agent could detect it — the pixel the object turns
    # about, which under real perspective is NOT the centre of the ellipse you see.
    # Optional: absent means "no rectification", never "rectification failed".
    hub_px: tuple[float, float] | None = None


def _arr(values, n: int, field: str) -> np.ndarray:
    if not isinstance(values, list) or len(values) != n:
        raise ContractError(f"{field} must be a list of length n_raw_frames={n}")
    return np.array([np.nan if v is None else float(v) for v in values], dtype=float)


def _radius_cv(x, y, cx, cy) -> float:
    """Spread of the per-frame radius about (cx, cy), as a fraction of its mean.

    A trajectory and a centre that live in the SAME space trace a near-constant
    radius; one shifted against the other sweeps a wide range. That contrast is
    what makes the frame mismatch below detectable without any scene knowledge.
    """
    r = np.hypot(x - cx, y - cy)
    r = r[np.isfinite(r)]
    if r.size < 8:
        return float("nan")
    m = float(r.mean())
    return float(r.std() / m) if m > 1e-9 else float("nan")


def _frame_timestamps(video: Path) -> np.ndarray | None:
    """Presentation timestamps of every frame, or None if they cannot be read.

    Read from the container, so this reports what the CAMERA did, independently of
    how any tracker decoded the file."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "frame=pts_time", "-of", "csv=p=0", str(video)],
            capture_output=True, text=True, timeout=120, check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    t = [s.rstrip(",") for s in out.split() if s.rstrip(",")]
    try:
        ts = np.array([float(v) for v in t], dtype=float)
    except ValueError:
        return None
    return ts if ts.size >= 8 else None


def duplicated_frame_indices(video: Path, n_frames: int) -> list[int]:
    """Indices in the EXTRACTED frame sequence that are duplicates of their predecessor.

    A camera that drops a frame leaves a hole in an otherwise constant-rate timeline.
    Frame extraction runs at a constant rate, so ffmpeg fills each hole by repeating the
    previous frame — turntable-3 has one such hole and yields 351 images from 350 real
    frames. The repeat is a perfectly good image, so trackers report it faithfully: the
    object does not move. Downstream, with time assumed uniform, that reads as the object
    momentarily stopping and then making up the distance, i.e. as an acceleration no
    coasting body can produce. This is what put a phantom speed-up in turntable-3's v(t).

    Detecting it from timestamps rather than from the trajectory matters: a frozen
    position is also what a genuinely stationary object looks like, and every clip here
    ends with the object at rest.
    """
    ts = _frame_timestamps(video)
    if ts is None:
        return []
    d = np.diff(ts)
    if d.size < 4:
        return []
    med = float(np.median(d))
    if not (med > 0):
        return []
    dup: list[int] = []
    # Walk the real frames, tracking where each lands once the holes are filled.
    offset = 0
    for i, gap in enumerate(d):
        extra = int(round(gap / med)) - 1
        if gap > _DROP_RATIO * med and extra > 0:
            # Frame i is repeated `extra` times to fill the hole after it; those
            # repeats occupy the next `extra` slots of the extracted sequence.
            dup.extend(range(i + 1 + offset, i + 1 + offset + extra))
            offset += extra
    return [k for k in dup if 0 <= k < n_frames]


def load_inputs(path: Path = INPUTS_PATH) -> Inputs:
    if not path.exists():
        raise ContractError(
            f"{path} not found — perception steps must write the pipeline input "
            f"contract before `python -m analysis.run`. See analysis/README.md."
        )
    data = json.loads(path.read_text())
    missing = [k for k in REQUIRED if k not in data]
    if missing:
        raise ContractError(f"pipeline_inputs.json missing keys: {missing}")

    n = int(data["n_raw_frames"])
    center = data["center"]
    ref = data["reference"]
    if float(ref.get("physical_size_m", 0)) <= 0:
        raise ContractError("reference.physical_size_m must be > 0 (metres)")
    if float(ref.get("diameter_px", 0)) <= 0:
        raise ContractError("reference.diameter_px must be > 0 (pixels)")

    roi_crop = dict(data["roi_crop"])
    x_px = _arr(data["trajectory_x_px"], n, "trajectory_x_px")
    y_px = _arr(data["trajectory_y_px"], n, "trajectory_y_px")
    cx_px = float(center["cx_px"])
    cy_px = float(center["cy_px"])

    # Optional: the imaged axle, for projective rectification (see rectify.py). Accepted
    # either at the top level or inside `center`, because it is a property of the same
    # observation the centre came from.
    raw_hub = data.get("hub_px", center.get("hub_px"))
    hub_px = None
    if raw_hub is not None:
        try:
            hub_px = (float(raw_hub[0]), float(raw_hub[1]))
        except (TypeError, ValueError, IndexError, KeyError):
            raise ContractError(f"hub_px must be [x, y] in pixels, got {raw_hub!r}")

    # Single source of truth for the display→cropped transform. The agent passes
    # raw full-frame coords; we subtract the crop offset from trajectory AND center
    # together so they can never drift into different spaces (the IMG_3072 bug).
    space = str(data["coordinate_space"]).strip().lower()
    if space in _DISPLAY_SPACES:
        x_off = float(roi_crop.get("x_off", 0) or 0)
        y_off = float(roi_crop.get("y_off", 0) or 0)

        # `coordinate_space` is the agent's WORD for what it wrote, and it can be
        # wrong in a way nothing downstream can see. On roundabout-4046 the tracker
        # ran on the CROPPED video, so the trajectory was already cropped, while the
        # centre came from axle detection on the FULL frame. Both were labelled
        # "display", so subtracting the offset from both left them 232 px apart —
        # which reads as a real-but-eccentric orbit (radius 97→772 px, |ω| spread
        # 57%), not as an error. Only the flags fire, and they blame the physics.
        #
        # The two readings are distinguishable without knowing anything about the
        # scene: a trajectory and a centre in the same space trace a steady radius.
        # Take the declaration at its word unless the alternative is decisively
        # better, and say so out loud when it is.
        traj_needs_crop = True
        if x_off or y_off:
            cv_declared = _radius_cv(x_px, y_px, cx_px, cy_px)
            cv_traj_cropped = _radius_cv(x_px + x_off, y_px + y_off, cx_px, cy_px)
            if (cv_declared == cv_declared and cv_traj_cropped == cv_traj_cropped
                    and cv_declared > 0.15 and cv_traj_cropped < 0.6 * cv_declared):
                traj_needs_crop = False
                common.set_validation_flag("trajectory_space_mismatch")
                common.log(
                    f"[contract] coordinate_space={space!r} but the trajectory is "
                    f"already in cropped space: radius spread {cv_declared:.3f} as "
                    f"declared vs {cv_traj_cropped:.3f} untouched. Cropping the "
                    f"centre only (offset {x_off:g},{y_off:g} px)."
                )

        if traj_needs_crop:
            x_px = x_px - x_off
            y_px = y_px - y_off
        cx_px -= x_off
        cy_px -= y_off
        if hub_px is not None:
            # The hub is a point in the same picture as the centre, so it takes the
            # centre's transform — never the trajectory's.
            hub_px = (hub_px[0] - x_off, hub_px[1] - y_off)
    elif space not in _CROPPED_SPACES:
        raise ContractError(
            f"coordinate_space must be one of {sorted(_DISPLAY_SPACES | _CROPPED_SPACES)}, "
            f"got {data['coordinate_space']!r}"
        )

    # Frames the camera never captured. Blank them so the trajectory carries no
    # position the camera did not measure; the short-gap fill in kinematics
    # interpolates across them, which is the honest reading — the object was
    # somewhere between its neighbours, and we do not know where.
    for cand in _VIDEO_CANDIDATES:
        video = Path(cand)
        if not video.exists():
            continue
        dup = duplicated_frame_indices(video, len(x_px))
        if dup:
            x_px = x_px.copy()
            y_px = y_px.copy()
            x_px[dup] = np.nan
            y_px[dup] = np.nan
            common.set_validation_flag("dropped_source_frames")
            common.log(
                f"[contract] {video.name}: the camera dropped {len(dup)} frame(s); "
                f"extraction filled the hole(s) by repeating the previous image at "
                f"index {dup if len(dup) <= 6 else str(dup[:6]) + '...'}. Blanked, so "
                f"a repeated image cannot read as the object standing still."
            )
        break

    tracked_label = str(data["tracked_label"])
    ref_label = str(data["ref_label"])
    scene_title = str(data.get("scene_title") or "").strip() \
        or f"{tracked_label} on {ref_label}"

    return Inputs(
        fps=float(data["fps"]),
        duration_s=float(data["duration_s"]),
        n_raw_frames=n,
        object_name=str(data["object_name"]),
        tracked_label=tracked_label,
        ref_label=ref_label,
        scene_title=scene_title,
        x_px=x_px,
        y_px=y_px,
        cx_px=cx_px,
        cy_px=cy_px,
        center_source=str(center.get("source", "unknown")),
        diameter_px=float(ref["diameter_px"]),
        physical_size_m=float(ref["physical_size_m"]),
        physical_size_source=str(ref.get("physical_size_source", "unknown")),
        roi_crop=roi_crop,
        hub_px=hub_px,
    )
