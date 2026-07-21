#!/usr/bin/env python3
"""Frozen video annotation (old Subagent A). Run: python -m analysis.render.annotate

Overlays the orbit, radius, velocity and centripetal-acceleration vectors, the
rotation centre, a fading trajectory trail, and a phase-coloured border onto the
cropped video.

PEDAGOGY RULE: label every quantity by SYMBOL only — r, v⃗, a⃗_c, ω — and show a
definitions legend. NEVER print numeric values (no "v=1.2 m/s"), so the student
measures and reasons instead of reading the answer off the screen.

Layout follows the P-MAGIC teaching diagram students are introduced with (the app's
`image_rotating.png`): one colour per quantity, the symbol drawn BESIDE its arrow
rather than on it, and linear speed v (straight tangent) kept separate from angular
speed ω (small curved arc) instead of collapsing both into one tangential arrow.

All coordinates are cropped-video space (matches kinematics.csv / stats.json).
Symbols are rendered by matplotlib's mathtext, which is the only one of the three
text engines here that can draw them properly: cv2's Hershey fonts are ASCII-only,
and PIL/DejaVu can draw ω but has no subscript or vector accent, so `a_c` used to
render as the literal three characters "a_c". Plain prose (the title and the legend
definitions) still goes through PIL.
"""
import io
import json
import math
import os
from pathlib import Path

import cv2
import numpy as np

from ..common import fit_orbit_ellipse as _fit_orbit_ellipse
from . import palette as _PAL

DATA = Path("analysis_output/data")
OUT_DIR = Path("analysis_output/video_annotation")
OUT_VIDEO = OUT_DIR / "annotated_video.mp4"

# Canonical per-quantity colours and the contrast adaptation live in `palette` — the still figure
# in figures.py derives its colours from the same module and the same footage, so the two artifacts
# show one palette rather than two.
C_ORBIT = _PAL.BASE["orbit"]
C_R = _PAL.BASE["r"]
C_V = _PAL.BASE["v"]
C_AC = _PAL.BASE["ac"]
C_W = _PAL.BASE["w"]
C_CENTRE = _PAL.CENTRE
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


# ── Unicode text via PIL (cv2's Hershey fonts are ASCII-only; we need ω, subscripts) ──
try:
    import matplotlib.font_manager as _fm
    _FONT_PATH = _fm.findfont("DejaVu Sans")
except Exception:  # noqa: BLE001 — fall back to the standard system path
    _FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
_FONT_CACHE: dict = {}


def _font(px: int):
    px = max(10, int(px))
    if px not in _FONT_CACHE:
        _FONT_CACHE[px] = ImageFont.truetype(_FONT_PATH, px)
    return _FONT_CACHE[px]


def _px(base: float) -> int:
    """cv2 fontScale → PIL pixel size (≈ the old Hershey cap height)."""
    return max(10, int(round(base * _S * 30)))


def _measure(text: str, base: float):
    l, t, r, b = _font(_px(base)).getbbox(text)
    return (r - l, b - t)


def _draw_text(img, text, org, color_bgr, base, bg=True):
    """Draw Unicode text in place on a BGR frame via PIL. org = bottom-left baseline (like
    cv2.putText); base = the old cv2 fontScale; color is BGR to match the cv2 call sites."""
    x, y = int(org[0]), int(org[1])
    font = _font(_px(base))
    rgb = (int(color_bgr[2]), int(color_bgr[1]), int(color_bgr[0]))
    pil = Image.fromarray(img[:, :, ::-1])
    d = ImageDraw.Draw(pil)
    if bg:
        l, t, r, b = d.textbbox((x, y), text, font=font, anchor="ls")
        pad = _p(3)
        d.rectangle([l - pad, t - pad, r + pad, b + pad], fill=(0, 0, 0))
    d.text((x, y), text, font=font, anchor="ls", fill=rgb)
    img[:, :, :] = np.asarray(pil)[:, :, ::-1]


# ── real math symbols via matplotlib mathtext ────────────────────────────────
import matplotlib  # noqa: E402
matplotlib.use("Agg")
from matplotlib import mathtext as _mathtext  # noqa: E402

_SPRITE_CACHE: dict = {}


def _sprite(tex: str, px: int, color_bgr):
    """Render a math expression to a cached (BGR, alpha) sprite at `px` em-height.

    mathtext at 12 pt renders one em as dpi/6 pixels, so dpi = 6*px gives the requested size."""
    key = (tex, int(px), tuple(color_bgr))
    if key not in _SPRITE_CACHE:
        buf = io.BytesIO()
        _mathtext.math_to_image(
            tex, buf, dpi=max(30.0, 6.0 * px), format="png",
            color="#%02x%02x%02x" % (color_bgr[2], color_bgr[1], color_bgr[0]))
        arr = np.asarray(Image.open(buf).convert("RGBA"))
        _SPRITE_CACHE[key] = (arr[:, :, 2::-1].copy(),            # RGB -> BGR
                              arr[:, :, 3].astype(np.float32) / 255.0)
    return _SPRITE_CACHE[key]


def _blit(img, sprite, centre, halo=(255, 255, 255)):
    """Alpha-composite a sprite centred on `centre`, over a halo so a coloured symbol stays readable
    on any footage (the old solid black label boxes punched holes in the frame). `halo` is the halo
    colour, or None for no halo — a light symbol needs a dark halo, not the default white one."""
    bgr, a = sprite
    h, w = a.shape
    x0, y0 = int(round(centre[0] - w / 2)), int(round(centre[1] - h / 2))
    x1, y1 = x0 + w, y0 + h
    sx0, sy0 = max(0, -x0), max(0, -y0)
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(img.shape[1], x1), min(img.shape[0], y1)
    if x1 <= x0 or y1 <= y0:
        return
    a = a[sy0:sy0 + (y1 - y0), sx0:sx0 + (x1 - x0)]
    bgr = bgr[sy0:sy0 + (y1 - y0), sx0:sx0 + (x1 - x0)]
    roi = img[y0:y1, x0:x1].astype(np.float32)
    if halo is not None:
        k = max(3, _p(3)) | 1
        ha = cv2.dilate(a, np.ones((k, k), np.float32))[..., None]
        roi = roi * (1 - ha) + np.float32(halo) * ha
    a3 = a[..., None]
    img[y0:y1, x0:x1] = (roi * (1 - a3) + bgr.astype(np.float32) * a3).astype(np.uint8)


# Symbol -> definition. Definitions only; no values. Names are worded as the P-MAGIC app words
# them for students ("kecepatan linier" = linear speed), not as our internal jargon
# ("tangential velocity"). Velocity and acceleration are vectors, so they carry the vector accent.
LEGEND = [
    ("r", r"$r$", "radius"),
    ("v", r"$\vec{v}$", "linear speed"),
    ("ac", r"$\vec{a}_c$", "centripetal acceleration"),
    ("w", r"$\omega$", "angular speed"),
    ("centre", "+", "centre of rotation"),
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


def _label(img, tex, pos, color):
    """A quantity's symbol, centred on `pos` — always placed BESIDE its arrow by the caller."""
    _blit(img, _sprite(tex, _px(0.9), color), pos, halo=_PAL.casing(color))


def _line(img, p1, p2, color, th):
    """Line with a contrasting casing under it."""
    cv2.line(img, p1, p2, _PAL.casing(color), th + 2 * max(1, _t(1.2)), cv2.LINE_AA)
    cv2.line(img, p1, p2, color, th, cv2.LINE_AA)


def _arrow_head(img, tip, ux, uy, color):
    th, ah = _t(3), _p(16)
    px, py = -uy, ux
    for s in (0.4, -0.4):
        _line(img, tip, (int(tip[0] - ux * ah + px * ah * s), int(tip[1] - uy * ah + py * ah * s)),
              color, th)


def _vector(img, start, end, color, tex=None, off_dir=None):
    """Straight arrow. `off_dir` is the unit direction the SYMBOL is pushed in, away from the shaft
    — the label never sits on the arrow, and never right at its tip where the head is busiest."""
    sx, sy = int(round(start[0])), int(round(start[1]))
    ex, ey = int(round(end[0])), int(round(end[1]))
    _line(img, (sx, sy), (ex, ey), color, _t(3))
    dx, dy = ex - sx, ey - sy
    n = math.hypot(dx, dy)
    if n < 1:
        return
    ux, uy = dx / n, dy / n
    _arrow_head(img, (ex, ey), ux, uy, color)
    if tex:
        ox, oy = off_dir if off_dir else (-uy, ux)
        gap = _p(26)
        _label(img, tex, (sx + dx * 0.62 + ox * gap, sy + dy * 0.62 + oy * gap), color)


def _orbit_ellipse_args(xs, ys):
    """`common.fit_orbit_ellipse` in the argument shape cv2.ellipse wants."""
    fit = _fit_orbit_ellipse(xs, ys)
    if fit is None:
        return None
    ex, ey, semi_major, semi_minor, ang = fit
    if min(semi_major, semi_minor) <= 1:
        return None
    return (int(round(ex)), int(round(ey))), \
           (int(round(semi_major)), int(round(semi_minor))), ang


def _arc_arrow(img, cx, cy, radius, th0, s, color, span=0.30):
    """Curved arrow centred on bearing `th0`, curling the way the object turns — the ANGULAR
    quantity ω. Kept a separate mark from the straight tangent v, as in the reference diagram."""
    d = span
    a0, a1 = th0 - s * d, th0 + s * d
    args = ((int(cx), int(cy)), (int(radius), int(radius)), 0,
            math.degrees(min(a0, a1)), math.degrees(max(a0, a1)))
    cv2.ellipse(img, *args, _PAL.casing(color), _t(3) + 2 * max(1, _t(1.2)), cv2.LINE_AA)
    cv2.ellipse(img, *args, color, _t(3), cv2.LINE_AA)
    tip = (int(cx + radius * math.cos(a1)), int(cy + radius * math.sin(a1)))
    _arrow_head(img, tip, -math.sin(a1) * s, math.cos(a1) * s, color)


def _render_banner(vw: int, scene_label: str, palette: dict) -> np.ndarray:
    """Build a standalone info banner (title + legend) the video is stacked under.

    Drawn OUTSIDE the video frame so the legend never covers the (tightly-cropped) footage. The
    legend items are packed into rows that fit the frame width, and drawn in the SAME adapted
    colours as the marks on the video — a legend in the canonical hue would key the student to a
    colour the footage never shows."""
    margin = _p(16)
    _, title_h = _measure(scene_label or "M", 0.95)  # title font
    _, item_h = _measure("Mg", 0.6)                  # legend font
    gap = _p(28)
    row_h = item_h + _p(16)
    max_w = vw - 2 * margin

    # Pre-measure each "sym = definition" item (PIL metrics — match the PIL drawing below),
    # then greedily pack into rows.
    items = []
    for key, sym, definition in LEGEND:
        color = palette[key]
        # Math symbols are sprites (mathtext); "+" is a plain glyph and stays PIL text.
        # Rendered a shade larger than the surrounding prose: mathtext measures a full em box, so
        # a short glyph like "r" reads noticeably smaller than the "= radius" beside it otherwise.
        spr = _sprite(sym, _px(0.82), color) if sym.startswith("$") else None
        sw = (spr[0].shape[1] + _p(6)) if spr is not None else _measure(sym + " ", 0.6)[0]
        dw, _ = _measure("= " + definition, 0.6)
        items.append((sym, definition, color, sw, dw, sw + _p(6) + dw, spr))
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
    _draw_text(banner, scene_label, (margin, margin + title_h), (255, 255, 255), 0.95, bg=False)
    y = margin + title_h + _p(12) + item_h
    for row in rows:
        x = margin
        for sym, definition, color, sw, dw, tot, spr in row:
            if spr is not None:
                _blit(banner, spr, (x + sw / 2, y - item_h * 0.42), halo=None)
            else:
                _draw_text(banner, sym, (x, y), color, 0.6, bg=False)
            _draw_text(banner, "= " + definition, (x + sw + _p(6), y), (220, 220, 220), 0.6, bg=False)
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
    # The orbit is always green now: which WAY it turns is carried by the v arrow and the ω arc,
    # so the circle no longer has to double as a direction cue (red for CW collided with the
    # radius colour, and a red circle on a red-marker clip was invisible).
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
    # Longest arrow in the clip is sized against the ORBIT, not against a fixed 60 reference pixels
    # — on a ~1400 px-tall crop that constant drew a 60 px stub barely longer than its own
    # arrowhead. Same proportions as the still figure, so the two artifacts read alike.
    v_scale = 0.78 * r_fit_px / max([x for x in v_vals if x == x] + [1e-6])
    ac_scale = 0.62 * r_fit_px / max([x for x in ac_vals if x == x] + [1e-6])

    # A circular orbit seen off-axis images as an ELLIPSE, so a drawn circle can only
    # hug the path on a face-on clip. Trace the shape the track actually has — this is
    # the picture only; every number still comes from the circle fit in geometry.py.
    orbit_ellipse = _orbit_ellipse_args([col(r, "x_px") for r in rows],
                                        [col(r, "y_px") for r in rows])

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

    # Colours adapted to this clip's own footage (see render.palette).
    palette = _PAL.clip_palette(_cropped_video(),
                                [col(r, "theta_rad") for r in rows],
                                cx, cy, r_fit_px)

    # The info box goes in a banner ABOVE the video, not over it (the ROI crop is
    # tight, so an in-frame legend would cover the footage). Output is banner+video.
    banner = _render_banner(vw, scene_label, palette)
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
        # The marker goes where the object WAS MEASURED, not where the fitted circle
        # says it should be. Those differ whenever the orbit images as an ellipse: on
        # roundabout-4046 the circle-projected point sat a mean 186 px (max 430) off
        # the handle, so the figure quietly showed the model instead of the data.
        # Fall back to the circle only when a frame has no finite centroid.
        ox, oy = col(r, "x_px"), col(r, "y_px")
        if math.isnan(ox) or math.isnan(oy):
            ox = cx + r_fit_px * math.cos(theta)
            oy = cy + r_fit_px * math.sin(theta)

        phase = phase_labels[i] if i < len(phase_labels) else "STABLE"
        pc = PHASE_C.get(phase, C_ORBIT)
        bw = _p(4)  # phase border thickness
        for p1, p2 in (((0, 0), (vw, bw)), ((0, vh - bw), (vw, vh)),
                       ((0, 0), (bw, vh)), ((vw - bw, 0), (vw, vh))):
            cv2.rectangle(frame, p1, p2, pc, -1)

        # Orbit is the most prominent element — thickest stroke.
        if orbit_ellipse is not None:
            e_args = (orbit_ellipse[0], orbit_ellipse[1], orbit_ellipse[2], 0, 360)
            cv2.ellipse(frame, *e_args, _PAL.casing(palette["orbit"]),
                        _t(4) + 2 * max(1, _t(1.2)), cv2.LINE_AA)
            cv2.ellipse(frame, *e_args, palette["orbit"], _t(4), cv2.LINE_AA)
        else:
            cv2.circle(frame, (int(cx), int(cy)), int(r_fit_px), _PAL.casing(palette["orbit"]),
                       _t(4) + 2 * max(1, _t(1.2)), cv2.LINE_AA)
            cv2.circle(frame, (int(cx), int(cy)), int(r_fit_px), palette["orbit"], _t(4), cv2.LINE_AA)

        trail.append((ox, oy))
        trail = trail[-30:]
        for j, (tx, ty) in enumerate(trail):
            a = (j + 1) / len(trail)
            cv2.circle(frame, (int(tx), int(ty)), max(1, _p(4 * a)),
                       (int(255 * a), int(200 * a), int(100 * a)), -1)

        cv2.drawMarker(frame, (int(cx), int(cy)), C_CENTRE, cv2.MARKER_CROSS, _p(32), _t(2))

        # Unit vectors at the object: outward along the radius, and along the direction of travel.
        ux, uy = math.cos(theta), math.sin(theta)
        w_now = col(r, "omega_rad_s")
        s = -1.0 if (w_now == w_now and w_now < 0) else 1.0
        tx, ty = -uy * s, ux * s

        # r — drawn PERPENDICULAR to the object's own radius. Pointing it at the object would lay it
        # exactly under the a_c arrow (which runs along that same radius): that overlap is why the
        # two used to be unreadable whenever the object crossed the left of the frame.
        rx, ry = -uy, ux
        if ry < 0:                       # prefer the downward side, as in the reference diagram
            rx, ry = -rx, -ry
        _vector(frame, (cx, cy), (cx + rx * r_fit_px, cy + ry * r_fit_px), palette["r"],
                r"$r$", off_dir=(ry, -rx))

        # v — straight tangent arrow at the object, pointing the way it travels.
        if not math.isnan(v) and abs(v) > 1e-3:
            _vector(frame, (ox, oy), (ox + tx * v * v_scale, oy + ty * v * v_scale), palette["v"],
                    r"$\vec{v}$", off_dir=(ux, uy))
        # a_c — straight arrow from the object toward the centre.
        if not math.isnan(ac) and abs(ac) > 1e-3:
            _vector(frame, (ox, oy), (ox - ux * ac * ac_scale, oy - uy * ac * ac_scale), palette["ac"],
                    r"$\vec{a}_c$", off_dir=(tx, ty))

        # ω — curved arrow showing the turning (direction only). Preferred spot is just OUTSIDE the
        # orbit at the object, as in the reference diagram; on a tight ROI crop that lands off the
        # frame, so it falls back to a small arc about the centre of rotation — on the opposite side
        # from the r arrow, hence clear of both r and the (radial) a_c arrow.
        wx, wy = cx + 1.40 * r_fit_px * ux, cy + 1.40 * r_fit_px * uy
        pad = _p(30)
        if pad <= wx <= vw - pad and pad <= wy <= vh - pad:
            _arc_arrow(frame, cx, cy, r_fit_px * 1.16, theta, s, palette["w"])
        else:
            th_w = math.atan2(-ry, -rx)
            _arc_arrow(frame, cx, cy, r_fit_px * 0.32, th_w, s, palette["w"], span=0.9)
            wx, wy = cx - rx * 0.52 * r_fit_px, cy - ry * 0.52 * r_fit_px
        _label(frame, r"$\omega$", (wx, wy), palette["w"])
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
