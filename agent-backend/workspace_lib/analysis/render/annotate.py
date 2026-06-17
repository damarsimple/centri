#!/usr/bin/env python3
"""Frozen video annotation (old Subagent A). Run: python -m analysis.render.annotate

Overlays the orbit, radius, velocity and centripetal-acceleration vectors, the
rotation centre, a fading trajectory trail, and a phase-coloured border onto the
cropped video.

PEDAGOGY RULE: label every quantity by SYMBOL only — `r`, `v`, `ac`, `w` — and
show a definitions legend. NEVER print numeric values (no "v=1.2 m/s"), so the
student measures and reasons instead of reading the answer off the screen.

All coordinates are cropped-video space (matches kinematics.csv / stats.json).
ASCII labels only — cv2's Hershey fonts can't render Unicode (omega, subscripts).
"""
import json
import math
import os
from pathlib import Path

import cv2
import numpy as np

DATA = Path("analysis_output/data")
OUT_DIR = Path("analysis_output/video_annotation")
OUT_VIDEO = OUT_DIR / "annotated_video.mp4"

# BGR colours.
C_ORBIT = (0, 255, 0)        # green orbit / CCW
C_ORBIT_CW = (0, 0, 255)     # red orbit / CW
C_V = (255, 255, 0)          # cyan velocity (tangent)
C_AC = (0, 165, 255)         # orange centripetal accel (inward)
C_R = (200, 200, 255)        # light radius line
C_CENTRE = (255, 255, 255)   # white centre
FONT = cv2.FONT_HERSHEY_SIMPLEX

# All overlay geometry is hardcoded in pixels below at a reference resolution; on a
# real (often ~1080-wide) cropped frame that renders tiny and unreadable. `_S` scales
# every size to the actual frame — set once in main() from the frame's larger side
# against a 720 px reference, floored at 1.0 so small clips are never shrunk.
_S = 1.0


def _f(base: float) -> float:
    """Scaled cv2 font scale."""
    return base * _S


def _t(base: float) -> int:
    """Scaled stroke thickness (>=1)."""
    return max(1, int(round(base * _S)))


def _p(base: float) -> int:
    """Scaled pixel length."""
    return int(round(base * _S))

# Symbol -> definition. Definitions only; no values.
LEGEND = [
    ("r", "radius", C_R),
    ("v", "tangential velocity", C_V),
    ("ac", "centripetal acceleration", C_AC),
    ("w", "angular velocity", C_ORBIT),
    ("+", "centre of rotation", C_CENTRE),
]


def _cropped_video() -> Path:
    """Resolve the cropped video path, tolerating the iter-suffixed variants."""
    roi = Path("analysis_output/roi")
    for name in ("cropped.mp4",):
        if (roi / name).exists():
            return roi / name
    cands = sorted(roi.glob("cropped*.mp4"))
    if cands:
        return cands[-1]
    raise FileNotFoundError("no cropped video under analysis_output/roi/")


def _label(img, text, pos, color):
    x, y = int(pos[0]), int(pos[1])
    fs, th = _f(0.7), _t(2)
    (tw, t_h), _ = cv2.getTextSize(text, FONT, fs, th)
    pad = _p(3)
    cv2.rectangle(img, (x - pad, y - t_h - pad), (x + tw + pad, y + pad), (0, 0, 0), -1)
    cv2.putText(img, text, (x, y), FONT, fs, color, th, cv2.LINE_AA)


def _vector(img, start, end, color, label=None):
    sx, sy = int(round(start[0])), int(round(start[1]))
    ex, ey = int(round(end[0])), int(round(end[1]))
    th = _t(3)
    cv2.line(img, (sx, sy), (ex, ey), color, th, cv2.LINE_AA)
    dx, dy = ex - sx, ey - sy
    n = math.hypot(dx, dy)
    if n < 1:
        return
    ux, uy = dx / n, dy / n
    px, py = -uy, ux
    ah = _p(16)  # arrowhead length
    for s in (0.4, -0.4):
        cv2.line(img, (ex, ey),
                 (int(ex - ux * ah + px * ah * s), int(ey - uy * ah + py * ah * s)),
                 color, th, cv2.LINE_AA)
    if label:
        _label(img, label, (ex + _p(8), ey), color)


def _render_banner(vw: int, scene_label: str) -> np.ndarray:
    """Build a standalone info banner (title + legend) the video is stacked under.

    Drawn OUTSIDE the video frame so the legend never covers the (tightly-cropped)
    footage. The legend items are packed into rows that fit the frame width."""
    margin = _p(16)
    tf, tth = _f(0.95), _t(2)                       # title font
    lf, lth = _f(0.6), _t(2)                        # legend font
    (_, title_h), _ = cv2.getTextSize(scene_label or "M", FONT, tf, tth)
    (_, item_h), _ = cv2.getTextSize("Mg", FONT, lf, lth)
    gap = _p(28)
    row_h = item_h + _p(16)
    max_w = vw - 2 * margin

    # Pre-measure each "sym = definition" item, then greedily pack into rows.
    items = []
    for sym, definition, color in LEGEND:
        (sw, _), _ = cv2.getTextSize(sym + " ", FONT, lf, lth)
        (dw, _), _ = cv2.getTextSize("= " + definition, FONT, lf, lth)
        items.append((sym, definition, color, sw, dw, sw + _p(6) + dw))
    rows, cur, cur_w = [], [], 0
    for it in items:
        w = it[5]
        if cur and cur_w + gap + w > max_w:
            rows.append(cur); cur, cur_w = [], 0
        cur.append(it); cur_w += (gap if cur_w else 0) + w
    if cur:
        rows.append(cur)

    banner_h = margin + title_h + _p(12) + len(rows) * row_h + margin
    banner = np.full((banner_h, vw, 3), 28, np.uint8)
    cv2.putText(banner, scene_label, (margin, margin + title_h), FONT, tf,
                (255, 255, 255), tth, cv2.LINE_AA)
    y = margin + title_h + _p(12) + item_h
    for row in rows:
        x = margin
        for sym, definition, color, sw, dw, tot in row:
            cv2.putText(banner, sym, (x, y), FONT, lf, color, lth, cv2.LINE_AA)
            cv2.putText(banner, "= " + definition, (x + sw + _p(6), y), FONT, lf,
                        (220, 220, 220), _t(1), cv2.LINE_AA)
            x += tot + gap
        y += row_h
    return banner


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stats = json.loads((DATA / "stats.json").read_text())
    cal, summ = stats["calibration"], stats["summary"]
    # Descriptive scene name for the on-frame label (e.g. "red phone on turntable"),
    # falling back to object_name for older stats.json without scene_title.
    scene_label = stats.get("scene_title") or stats.get("object_name") or ""
    cx, cy = cal["cx_px"], cal["cy_px"]
    r_fit_px = cal["r_fit_px"]
    ccw = summ["rotation_direction"] == "CCW"
    orbit_color = C_ORBIT if ccw else C_ORBIT_CW
    phase_labels = stats.get("phases", {}).get("phase_labels", [])

    # Per-frame series (symbol geometry only — magnitudes drive arrow length, but
    # no number is ever drawn).
    rows = list(__import__("csv").DictReader(open(DATA / "kinematics.csv")))

    def col(r, k):
        v = r.get(k, "")
        try:
            return float(v)
        except (TypeError, ValueError):
            return float("nan")

    v_vals = [abs(col(r, "v_m_s")) for r in rows]
    ac_vals = [abs(col(r, "ac_m_s2")) for r in rows]
    v_scale = 60.0 / max([x for x in v_vals if x == x] + [1e-6])
    ac_scale = 60.0 / max([x for x in ac_vals if x == x] + [1e-6])

    cap = cv2.VideoCapture(str(_cropped_video()))
    if not cap.isOpened():
        raise RuntimeError("cannot open cropped video")
    vw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    vh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    # Scale every overlay to this frame so labels/lines are readable on the real
    # (full-resolution) cropped video instead of the reference-pixel hairlines.
    global _S
    _S = max(1.0, max(vw, vh) / 720.0)
    fps = cap.get(cv2.CAP_PROP_FPS) or stats["video_info"]["fps"]

    # The info box goes in a banner ABOVE the video, not over it (the ROI crop is
    # tight, so an in-frame legend would cover the footage). Output is banner+video.
    banner = _render_banner(vw, scene_label)
    bh = banner.shape[0]
    out = cv2.VideoWriter(str(OUT_VIDEO), cv2.VideoWriter_fourcc(*"mp4v"), fps, (vw, vh + bh))

    PHASE_C = {"STABLE": C_ORBIT, "INCREASE": (0, 165, 255),
               "DECREASE": (0, 0, 255), "INACTIVE": (128, 128, 128)}
    trail = []
    i = 0
    while i < len(rows):
        ret, frame = cap.read()
        if not ret:
            break
        r = rows[i]
        theta = col(r, "theta_rad")
        v, ac = col(r, "v_m_s"), col(r, "ac_m_s2")
        if math.isnan(theta):
            out.write(frame); i += 1; continue
        ox = cx + r_fit_px * math.cos(theta)
        oy = cy + r_fit_px * math.sin(theta)

        phase = phase_labels[i] if i < len(phase_labels) else "STABLE"
        pc = PHASE_C.get(phase, C_ORBIT)
        bw = _p(4)  # phase border thickness
        for p1, p2 in (((0, 0), (vw, bw)), ((0, vh - bw), (vw, vh)),
                       ((0, 0), (bw, vh)), ((vw - bw, 0), (vw, vh))):
            cv2.rectangle(frame, p1, p2, pc, -1)

        # Orbit is the most prominent element — thickest stroke.
        cv2.circle(frame, (int(cx), int(cy)), int(r_fit_px), orbit_color, _t(4), cv2.LINE_AA)

        trail.append((ox, oy))
        trail = trail[-30:]
        for j, (tx, ty) in enumerate(trail):
            a = (j + 1) / len(trail)
            cv2.circle(frame, (int(tx), int(ty)), max(1, _p(4 * a)),
                       (int(255 * a), int(200 * a), int(100 * a)), -1)

        cv2.drawMarker(frame, (int(cx), int(cy)), C_CENTRE, cv2.MARKER_CROSS, _p(32), _t(2))
        # radius line, labelled "r" at its midpoint
        cv2.line(frame, (int(cx), int(cy)), (int(ox), int(oy)), C_R, _t(2), cv2.LINE_AA)
        _label(frame, "r", ((cx + ox) / 2, (cy + oy) / 2), C_R)

        if not math.isnan(v) and abs(v) > 1e-3:
            tx, ty = -math.sin(theta), math.cos(theta)
            if col(r, "omega_rad_s") < 0:
                tx, ty = -tx, -ty
            _vector(frame, (ox, oy), (ox + tx * v * v_scale, oy + ty * v * v_scale), C_V, "v")
        if not math.isnan(ac) and abs(ac) > 1e-3:
            dx, dy = cx - ox, cy - oy
            n = math.hypot(dx, dy) or 1.0
            _vector(frame, (ox, oy),
                    (ox + dx / n * ac * ac_scale, oy + dy / n * ac * ac_scale), C_AC, "ac")

        # angular-velocity symbol near the top of the orbit (direction only).
        _label(frame, "w", (cx - 8, cy - r_fit_px - 12), orbit_color)
        # Stack the static info banner above the annotated video frame.
        out.write(np.vstack([banner, frame]))
        i += 1

    cap.release()
    out.release()
    if not OUT_VIDEO.exists() or OUT_VIDEO.stat().st_size == 0:
        raise RuntimeError("annotated video not written")
    print(f"OK annotated_video.mp4 ({OUT_VIDEO.stat().st_size} bytes, {i} frames, symbols-only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
