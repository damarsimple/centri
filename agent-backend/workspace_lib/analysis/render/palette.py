"""Contrast-adaptive annotation palette, shared by the still figure and the video overlay.

A fixed palette cannot survive arbitrary footage: the orange ω arc used to sit on top of a bright
red phone and effectively disappear. So each quantity keeps its HUE — that is the colour-coding the
legend, the callouts and the material prose all lean on — while its saturation and lightness are
chosen per clip, against the actual pixels that mark will be drawn over.

Two properties are deliberate:

* **Per clip, never per frame.** A colour that re-solves every frame reads as flicker.
* **Same inputs for both renderers.** `clip_palette` samples the cropped video, so `figures.py`
  and `annotate.py` derive the *same* colours for a clip rather than merely the same hue — a
  student comparing the still against the video sees one palette, not two.

Colours are BGR throughout (the cv2 convention); `to_hex` converts for matplotlib.
"""
from __future__ import annotations

import math

import cv2
import numpy as np

# Canonical hues, matched to the P-MAGIC teaching diagram students are introduced with (the app's
# `image_rotating.png`): radius red, linear speed blue, angular speed orange, centripetal
# acceleration purple, fitted orbit green.
BASE = {
    "r": (53, 57, 229),
    "v": (229, 136, 30),
    "w": (0, 140, 251),
    "ac": (170, 36, 142),
    "orbit": (118, 230, 0),
}
CENTRE = (255, 255, 255)


def to_hex(bgr) -> str:
    return "#%02x%02x%02x" % (int(bgr[2]), int(bgr[1]), int(bgr[0]))


def _to_lab(bgr):
    return cv2.cvtColor(np.uint8([[list(bgr)]]), cv2.COLOR_BGR2LAB)[0, 0].astype(np.float32)


def casing(color):
    """Outline colour for a mark: the opposite lightness pole. Even where the fill happens to match
    its background, this keeps a visible edge — the guarantee an adaptive fill alone cannot give."""
    lum = 0.114 * color[0] + 0.587 * color[1] + 0.299 * color[2]
    return (255, 255, 255) if lum < 145 else (25, 25, 25)


def _bg_clusters(samples, k=3):
    """Dominant colours (Lab) of a background patch, with their weights. Clustering rather than
    averaging matters: the mean of a half-black half-white background is mid-grey, and a mid-grey
    mark would be invisible against BOTH halves."""
    if samples is None or len(samples) < 16:
        return []
    px = np.asarray(samples, np.uint8).reshape(-1, 1, 3)
    lab = cv2.cvtColor(px, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)
    if len(lab) > 4000:                # the clusters are stable well below this; cap the work
        lab = lab[np.random.RandomState(0).choice(len(lab), 4000, replace=False)]
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 12, 1.0)
    _, labels, centres = cv2.kmeans(lab, min(k, len(lab)), None, crit, 3, cv2.KMEANS_PP_CENTERS)
    labels = labels.ravel()
    out = [(c, float((labels == i).sum()) / len(labels)) for i, c in enumerate(centres)]
    return [(c, w) for c, w in out if w >= 0.12]      # ignore slivers


def adapt(base_bgr, samples):
    """Pick the variant of `base_bgr` that stays nearest the canonical colour while standing clear
    of every significant background colour. Score = distance to the CLOSEST background cluster,
    less a penalty for straying from the canonical colour, so we move only as far as we must."""
    clusters = _bg_clusters(samples)
    if not clusters:
        return tuple(int(c) for c in base_bgr)
    base_lab = _to_lab(base_bgr)
    h0, _s0, _v0 = cv2.cvtColor(np.uint8([[list(base_bgr)]]), cv2.COLOR_BGR2HSV)[0, 0].astype(float)
    best, best_score = tuple(int(c) for c in base_bgr), -1e9
    for dh in (0, -7, 7):              # OpenCV hue units: ±7 ≈ ±14°, still the same colour name
        for s in (255, 210, 165):
            for v in (255, 215, 170, 125, 85):
                cand = cv2.cvtColor(np.uint8([[[(h0 + dh) % 180, s, v]]]), cv2.COLOR_HSV2BGR)[0, 0]
                lab = _to_lab(cand)
                sep = min(float(np.linalg.norm(lab - c)) for c, _w in clusters)
                score = sep - 0.35 * float(np.linalg.norm(lab - base_lab))
                if score > best_score:
                    best, best_score = tuple(int(x) for x in cand), score
    return best


def _sample_disc(frame, cx, cy, radius, out):
    h, w = frame.shape[:2]
    x0, x1 = max(0, int(cx - radius)), min(w, int(cx + radius) + 1)
    y0, y1 = max(0, int(cy - radius)), min(h, int(cy + radius) + 1)
    if x1 <= x0 or y1 <= y0:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1]
    m = (xx - cx) ** 2 + (yy - cy) ** 2 <= radius ** 2
    if m.any():
        out.append(frame[y0:y1, x0:x1][m])


def _sample_ring(frame, cx, cy, radius, width, out):
    h, w = frame.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    m = np.abs(np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) - radius) <= width
    if m.any():
        out.append(frame[m])


def clip_palette(video_path, thetas, cx, cy, r_fit_px, frames=10) -> dict:
    """Adapt every quantity's colour to the footage it will be drawn on, once per clip.

    Each mark is sampled where it actually lives: v, a_c and ω sit AT the object, so their
    background is the object itself (which is why an orange ω arc lost itself in a red phone); the
    r arrow rotates with the object and so sweeps the disc INTERIOR; the fitted circle rides the
    orbit ANNULUS. Sampling frames spread across the clip covers the object against every
    background it passes over.

    `thetas` is the per-frame orbital angle (NaN where untracked). Any failure to read the video
    falls back to the canonical palette — an annotation with slightly weak contrast is a far better
    outcome than no annotation at all."""
    at_object, at_orbit, at_inside = [], [], []
    try:
        cap = cv2.VideoCapture(str(video_path))
        if cap.isOpened() and len(thetas):
            n = len(thetas)
            idx = sorted({int(round(k * (n - 1) / max(1, frames - 1))) for k in range(frames)})
            for i in idx:
                cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                ok, frame = cap.read()
                if not ok:
                    continue
                th = float(thetas[i])
                if not math.isnan(th):
                    _sample_disc(frame, cx + r_fit_px * math.cos(th), cy + r_fit_px * math.sin(th),
                                 max(6.0, 0.45 * r_fit_px), at_object)
                _sample_ring(frame, cx, cy, r_fit_px, max(4.0, 0.10 * r_fit_px), at_orbit)
                _sample_disc(frame, cx, cy, r_fit_px, at_inside)
        cap.release()
    except Exception:  # noqa: BLE001 — never let colour tuning break the render
        pass
    obj = np.concatenate(at_object) if at_object else None
    orb = np.concatenate(at_orbit) if at_orbit else None
    ins = np.concatenate(at_inside) if at_inside else None
    return {"v": adapt(BASE["v"], obj), "ac": adapt(BASE["ac"], obj), "w": adapt(BASE["w"], obj),
            "r": adapt(BASE["r"], ins), "orbit": adapt(BASE["orbit"], orb), "centre": CENTRE}
