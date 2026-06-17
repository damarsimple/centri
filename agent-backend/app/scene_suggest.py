"""Scene reconnaissance for interactive annotation.

Extracts a representative frame from the uploaded media and asks the vision LLM to
propose the moving object, the reference / rotation platform, and the rotation
centre — so the app can PRE-FILL the annotation form instead of leaving the student
to guess. The VLM is good at *semantics* (what each object is, which is the
platform, where the centre is) but its boxes are loose, so we then ground its
labels through SAM3 (the same detector the full /analyze job uses) to return tight
boxes. This is advisory only; the student confirms/edits before the real job runs.
"""
import logging
import tempfile
from typing import Optional

import cv2
import numpy as np

from . import llm, sam_client

log = logging.getLogger(__name__)

# Cap the frame we send the VLM: enough detail to identify objects, small enough to
# keep the call fast. Coordinates returned are in this (possibly downscaled) space,
# and we report it back as frame_w/frame_h so the client can scale correctly.
MAX_EDGE = 1024
JPEG_QUALITY = 88

_PROMPT = """You are helping a student set up a CIRCULAR MOTION physics measurement from a single video frame.

The image is {w} pixels wide and {h} pixels tall. The origin (0,0) is the TOP-LEFT corner.

Identify three things:
1. moving_object — the object that travels in a circle (e.g. a ball, marble, toy, bottle cap, figure on a turntable). Give a short visual description usable as a tracking cue (colour + noun, e.g. "red ball").
2. reference_object — the spinning platform itself (lazy susan, turntable, vinyl record, CD, dinner plate, wheel/tire), used to convert pixels to metres. This is the object the moving thing rotates on/around — NOT a separate ruler or coin. Estimate its real size in METRES from common knowledge, and say what that estimate is based on.
3. rotation_center_px — the pixel coordinate of the point the moving object circles around (the pivot / centre of the platform).

For each object also give a bounding box [x, y, width, height] in pixels and a confidence from 0 to 1.

Respond with ONLY this JSON object and nothing else. Use null for anything not visible:
{{
  "moving_object": {{"label": "<text>", "bbox": [x, y, w, h], "confidence": <0..1>}},
  "reference_object": {{"label": "<text>", "bbox": [x, y, w, h], "physical_size_m": <number>, "size_basis": "<why>", "confidence": <0..1>}},
  "rotation_center_px": [cx, cy],
  "notes": "<one short sentence, or empty>"
}}"""


def _encode(frame: np.ndarray) -> tuple[bytes, int, int]:
    h, w = frame.shape[:2]
    scale = min(1.0, MAX_EDGE / max(w, h))
    if scale < 1.0:
        frame = cv2.resize(
            frame, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA
        )
        h, w = frame.shape[:2]
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    if not ok:
        raise ValueError("failed to encode frame")
    return buf.tobytes(), w, h


def frame_from_image(image_bytes: bytes) -> tuple[bytes, int, int]:
    frame = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("could not decode image")
    return _encode(frame)


def frame_from_video(video_bytes: bytes) -> tuple[bytes, int, int]:
    # A few frames in, to skip black/auto-exposure intro frames.
    with tempfile.NamedTemporaryFile(suffix=".mp4") as tf:
        tf.write(video_bytes)
        tf.flush()
        cap = cv2.VideoCapture(tf.name)
        try:
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            target = min(5, max(0, total - 1)) if total else 0
            if target:
                cap.set(cv2.CAP_PROP_POS_FRAMES, target)
            ok, frame = cap.read()
            if not ok or frame is None:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame = cap.read()
            if not ok or frame is None:
                raise ValueError("could not read a frame from the video")
            return _encode(frame)
        finally:
            cap.release()


def _clean_obj(d: Optional[dict]) -> Optional[dict]:
    if not isinstance(d, dict):
        return None
    out = {
        "label": d.get("label") if isinstance(d.get("label"), str) else None,
        "bbox": d.get("bbox") if isinstance(d.get("bbox"), list) and len(d["bbox"]) == 4 else None,
        "confidence": d.get("confidence") if isinstance(d.get("confidence"), (int, float)) else None,
    }
    if "physical_size_m" in d or "size_basis" in d:
        psize = d.get("physical_size_m")
        out["physical_size_m"] = psize if isinstance(psize, (int, float)) and psize > 0 else None
        out["size_basis"] = d.get("size_basis") if isinstance(d.get("size_basis"), str) else None
    return out


def _tighten_with_sam(frame_bytes: bytes, w: int, h: int, *objects: Optional[dict]) -> None:
    """Replace the VLM's loose boxes with tight SAM3 boxes, in place.

    The VLM already named the objects; we ask SAM3 to ground those exact labels in
    the same frame and swap in its tight box wherever it finds one. Best-effort: if
    SAM is unavailable or misses a label, that object keeps its VLM box (the
    fallback). Object *centroids* from SAM are not used for the rotation centre —
    that stays the VLM's pivot estimate, which is a different point.
    """
    targets = [o for o in objects
               if o and isinstance(o.get("label"), str) and o["label"].strip()]
    if not targets:
        return
    try:
        raw = sam_client.segment(frame_bytes, [o["label"] for o in targets])
    except Exception as e:  # noqa: BLE001 — SAM is best-effort here
        log.warning("scene_suggest: SAM3 box-tighten skipped (%s)", e)
        return

    dets = raw.get("objects") or {}
    # SAM reports the dims of the frame it scored; we sent the same (w,h) frame, but
    # scale defensively in case the server normalises coordinates.
    sw = float(raw.get("frame_w") or 0) or float(w)
    sh = float(raw.get("frame_h") or 0) or float(h)
    sx, sy = (w / sw if sw else 1.0), (h / sh if sh else 1.0)

    for obj in targets:
        det = dets.get(obj["label"])
        box = sam_client.to_xywh(det.get("bbox")) if det else None
        if not box:
            continue
        if sx != 1.0 or sy != 1.0:
            box = [box[0] * sx, box[1] * sy, box[2] * sx, box[3] * sy]
        obj["bbox"] = box


def suggest(frame_bytes: bytes, w: int, h: int) -> dict:
    prompt = _PROMPT.format(w=w, h=h) + "\n\n/no_think"
    raw = llm.vision_chat(frame_bytes, prompt, max_tokens=100000, temperature=1.0, timeout=60)
    parsed = llm.extract_json(raw)

    center = parsed.get("rotation_center_px")
    if not (isinstance(center, list) and len(center) == 2
            and all(isinstance(v, (int, float)) for v in center)):
        center = None

    moving = _clean_obj(parsed.get("moving_object"))
    reference = _clean_obj(parsed.get("reference_object"))
    # Ground the VLM's labels through SAM3 for tight boxes (the loose VLM boxes were
    # the complaint). Mutates the dicts in place; falls back to VLM boxes on miss.
    _tighten_with_sam(frame_bytes, w, h, moving, reference)

    return {
        "moving_object": moving,
        "reference_object": reference,
        "rotation_center_px": center,
        "frame_w": w,
        "frame_h": h,
        "notes": parsed.get("notes") if isinstance(parsed.get("notes"), str) else None,
    }
