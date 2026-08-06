#!/usr/bin/env python3
"""Side-by-side of the computerfan-4029 overlay, before and after the crop-bounds fix.

Both inputs are FROZEN COPIES committed beside this script:
  src-overlay-before-4029.png — from the shipped run before 2026-08-06 (centre 328 px low)
  src-overlay-after-4029.png  — the same figure after the fix

They are deliberately NOT read from a live workspace. The "before" state no longer exists
there — regenerating that workspace is exactly what removed it — so a path into
`agent-backend/workspaces/` would silently start rendering two identical panels.

Run:  python3 mk_overlay_fix_fig.py      →  overlay-fix-4029.png
"""
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE / "overlay-fix-4029.png"

BAR_H = 62
FONT = cv2.FONT_HERSHEY_SIMPLEX


def photo_box(im: np.ndarray) -> tuple[int, int, int, int]:
    """Bounding box of the embedded video frame, found rather than hard-coded.

    The two panels place their callout boxes differently — matplotlib lays them out by
    whatever space is free — so one fixed crop slices a label box off one panel and not
    the other. The photo is the only large block of non-white pixels, so detect it: take
    the biggest connected non-white component and return its box."""
    nonwhite = (im < 246).any(axis=2).astype(np.uint8) * 255
    nonwhite = cv2.morphologyEx(nonwhite, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
    n, _lab, st, _cen = cv2.connectedComponentsWithStats(nonwhite)
    if n < 2:
        return 0, 0, im.shape[1], im.shape[0]
    k = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    x, y, w, h = (int(st[k, i]) for i in (cv2.CC_STAT_LEFT, cv2.CC_STAT_TOP,
                                          cv2.CC_STAT_WIDTH, cv2.CC_STAT_HEIGHT))
    return x, y, w, h


def panel(path: Path, title: str, accent) -> np.ndarray:
    im = cv2.imread(str(path))
    if im is None:
        raise SystemExit(f"missing input: {path.name} (must sit beside this script)")
    x, y, w, h = photo_box(im)
    im = im[y:y + h, x:x + w]
    im = cv2.copyMakeBorder(im, BAR_H, 6, 6, 6, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    cv2.rectangle(im, (6, 0), (im.shape[1] - 6, BAR_H - 8), accent, -1)
    cv2.putText(im, title, (22, 42), FONT, 1.05, (255, 255, 255), 2, cv2.LINE_AA)
    return im


def main() -> None:
    # BGR. Red for the broken state, green for the repaired one.
    left = panel(HERE / "src-overlay-before-4029.png", "shipped: centre on a blade", (52, 52, 200))
    right = panel(HERE / "src-overlay-after-4029.png", "fixed: centre on the hub", (72, 150, 60))
    h = min(left.shape[0], right.shape[0])
    left, right = left[:h], right[:h]
    gap = np.full((h, 26, 3), 255, np.uint8)
    cv2.imwrite(str(OUT), np.hstack([left, gap, right]))
    print(f"wrote {OUT.name}  {np.hstack([left, gap, right]).shape}")


if __name__ == "__main__":
    main()
