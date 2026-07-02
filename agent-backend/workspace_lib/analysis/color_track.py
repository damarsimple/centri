"""Color-marker tracking — a local alternative to remote SAM3 object tracking.

For scenes with a distinctly-coloured marker (e.g. a red/orange paper wrapped on
one fan blade), this follows the marker by HSV colour instead of appearance. It
emits the **exact same response schema as the remote `/track` endpoint**, so the
orchestrator writes it straight to `api_cache.json` and everything downstream
(calibration, kinematics, figures) is unchanged. Runs on CPU (OpenCV) — no GPU,
no remote call.

When to prefer this over SAM3 object tracking:
  - The moving object is one of several **identical** shapes (5 identical fan
    blades) that an appearance tracker cannot tell apart — it aliases / hops.
    A unique colour follows the *right* one.
  - You marked the object yourself with a coloured tag of known size (which also
    doubles as the calibration reference).

When NOT to use it (use `freq_track` instead):
  - Heavy **motion blur** smears the marker into a faint streak so no concentrated
    blob survives — typical of a fast multi-blade fan. Higher fps does not fix
    blur. Frequency analysis recovers omega without tracking a point.

This module is deterministic: a given video + parameters always yields the same
trajectory (no RNG), preserving the pipeline's "same inputs → same stats" guarantee.
"""
from __future__ import annotations

import argparse
import json
import sys

import cv2
import numpy as np


def _band_mask(hsv: np.ndarray, lo, hi) -> np.ndarray:
    """inRange with red-hue wraparound: if lo_h > hi_h, OR two bands across 0/180."""
    lo = np.asarray(lo, np.uint8)
    hi = np.asarray(hi, np.uint8)
    if lo[0] <= hi[0]:
        return cv2.inRange(hsv, lo, hi)
    lo1 = lo.copy(); hi1 = hi.copy(); hi1[0] = 179
    lo2 = lo.copy(); hi2 = hi.copy(); lo2[0] = 0
    return cv2.bitwise_or(cv2.inRange(hsv, lo1, hi1), cv2.inRange(hsv, lo2, hi2))


def track(
    video_path: str,
    label: str,
    hsv_lo,
    hsv_hi,
    roi_center_px=None,
    roi_radius_px=None,
    min_area: float = 60.0,
    max_step_px=None,
) -> dict:
    """Follow the coloured marker per frame; return the remote-/track schema.

    `roi_center_px`/`roi_radius_px` (optional) confine detection to a disc around
    the rotation centre, which rejects static coloured clutter elsewhere in the
    frame (door frames, skin, glare). `min_area` drops specks.

    Blob selection is robust to look-alike clutter (e.g. brown fan blades share
    the marker's hue when the threshold is loosened for coverage):
      - candidates are scored by **area × mean saturation** so the vivid marker
        beats the duller blades;
      - once locked, `max_step_px` keeps only candidates within that radius of the
        previous centroid (temporal continuity) — the marker moves smoothly, so a
        sudden jump to a blade is rejected. Set `max_step_px=None` to disable
        gating (pure best-score per frame).

    Frames with no qualifying blob are emitted as misses (`cx`/`cy`/`bbox` = null),
    exactly as the remote tracker reports occlusions.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"could not open video: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    open_k = np.ones((3, 3), np.uint8)
    close_k = np.ones((7, 7), np.uint8)
    roi_mask = None
    traj = []
    w = h = None
    i = 0
    prev = None
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        h, w = fr.shape[:2]
        if roi_center_px is not None and roi_radius_px and roi_mask is None:
            roi_mask = np.zeros((h, w), np.uint8)
            cv2.circle(roi_mask, (int(roi_center_px[0]), int(roi_center_px[1])),
                       int(roi_radius_px), 255, -1)
        hsv = cv2.cvtColor(fr, cv2.COLOR_BGR2HSV)
        m = _band_mask(hsv, hsv_lo, hsv_hi)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, open_k)
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, close_k)
        if roi_mask is not None:
            m = cv2.bitwise_and(m, roi_mask)
        cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        sat = hsv[:, :, 1]
        cands = []
        for c in cnts:
            area = cv2.contourArea(c)
            if area < min_area:
                continue
            mom = cv2.moments(c)
            if mom["m00"] <= 0:
                continue
            cx = mom["m10"] / mom["m00"]
            cy = mom["m01"] / mom["m00"]
            blob = np.zeros((h, w), np.uint8)
            cv2.drawContours(blob, [c], -1, 255, -1)
            mean_s = float(cv2.mean(sat, mask=blob)[0])
            x, y, bw, bh = cv2.boundingRect(c)
            cands.append((cx, cy, area * mean_s, [float(x), float(y), float(x + bw), float(y + bh)]))
        chosen = None
        if cands:
            if prev is not None and max_step_px:
                near = [c for c in cands if (c[0] - prev[0]) ** 2 + (c[1] - prev[1]) ** 2 <= max_step_px ** 2]
                pool = near if near else None
            else:
                pool = cands
            if pool:
                chosen = max(pool, key=lambda c: c[2])
        if chosen is not None:
            prev = (chosen[0], chosen[1])
            traj.append({"frame": i, "cx": chosen[0], "cy": chosen[1], "bbox": chosen[3]})
        else:
            traj.append({"frame": i, "cx": None, "cy": None, "bbox": None})
        i += 1
    cap.release()
    n_valid = sum(1 for e in traj if e["cx"] is not None)
    return {
        "status": "success",
        "trajectories": {label: traj},
        "video_info": {"width": w, "height": h, "rotation": 0,
                       "nb_frames": len(traj), "fps": fps},
        "track_coverage": (n_valid / len(traj)) if traj else 0.0,
        "method": "color",
    }


def _main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Local HSV colour-marker tracker (SAM3 /track schema).")
    ap.add_argument("--video", required=True)
    ap.add_argument("--label", required=True, help="trajectory key, e.g. 'orange marker'")
    ap.add_argument("--hsv-lo", required=True, help="H,S,V lower, e.g. 0,90,100")
    ap.add_argument("--hsv-hi", required=True, help="H,S,V upper, e.g. 22,255,255")
    ap.add_argument("--roi-center", default=None, help="cx,cy px of rotation centre (optional ROI)")
    ap.add_argument("--roi-radius", type=float, default=None, help="ROI disc radius px (optional)")
    ap.add_argument("--min-area", type=float, default=60.0)
    ap.add_argument("--max-step", type=float, default=None,
                    help="max centroid jump px between frames (temporal gate); omit to disable")
    ap.add_argument("--out", default=None, help="write JSON here (default stdout)")
    a = ap.parse_args(argv)
    lo = [int(x) for x in a.hsv_lo.split(",")]
    hi = [int(x) for x in a.hsv_hi.split(",")]
    rc = [float(x) for x in a.roi_center.split(",")] if a.roi_center else None
    res = track(a.video, a.label, lo, hi, rc, a.roi_radius, a.min_area, a.max_step)
    out = json.dumps(res)
    if a.out:
        with open(a.out, "w") as f:
            f.write(out)
        vi = res["video_info"]
        print(f"[color_track] {a.label}: coverage={res['track_coverage']:.3f} "
              f"frames={vi['nb_frames']} fps={vi['fps']} → {a.out}")
    else:
        sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
