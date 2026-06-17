"""Thin proxy to the SAM3 tracking server's single-frame /segment endpoint.

Used by /verify-objects so the app can confirm a proposed label actually grounds
in SAM3 (the same detector the full /track job uses) and get a tight box, without
the phone ever talking to the internal GPU box directly.
"""
import json
import os

import requests

TRACKING_API_URL = os.environ.get("TRACKING_API_URL", "http://10.0.0.1:8086").rstrip("/")
SEGMENT_TIMEOUT = int(os.environ.get("SAM_SEGMENT_TIMEOUT", "60"))


def segment(image_bytes: bytes, targets: list[str], *, mime: str = "image/jpeg") -> dict:
    """Return the SAM server's raw /segment response (bboxes as [x0,y0,x1,y1])."""
    resp = requests.post(
        f"{TRACKING_API_URL}/segment",
        files={"image": ("frame.jpg", image_bytes, mime)},
        data={"targets": json.dumps(targets)},
        timeout=SEGMENT_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def to_xywh(bbox):
    """Convert SAM's corner box [x0,y0,x1,y1] to [x, y, w, h]."""
    if not (isinstance(bbox, list) and len(bbox) == 4):
        return None
    x0, y0, x1, y1 = bbox
    return [float(x0), float(y0), float(x1 - x0), float(y1 - y0)]
