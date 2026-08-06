#!/usr/bin/env python3
"""Deck figures for the omega-sign fix (weekly 2026-08-05).

PROVENANCE — read this before regenerating anything.

The "before" images CANNOT be rebuilt from the current code: they are what the pipeline
shipped while the plotted omega series still carried the tracker's raw sign. They were
copied out of `agent-backend/workspaces/job_fan-4028/analysis_output/plots/` on 2026-07-31
(that workspace is now at
`agent-backend/workspaces-archive/superseded-by-fan4656-20260806/job_fan-4028/` — fan-4028 was
superseded by the fan-4656 re-shoot),
BEFORE the fix was applied, and committed here as `signfix_*_before.png`. Workspaces are
deleted by `cleanup_expired_workspaces`, so a deck figure must never point at one.

  signfix_omega_before.png   omega_t.png, fan-4028, pre-fix  (curve entirely below zero)
  signfix_omega_after.png    omega_t.png, fan-4028, post-fix (angular SPEED)
  signfix_arrows_before.png  annotated_image.png, fan-4028, pre-fix  (v/omega drawn CW)
  signfix_arrows_after.png   annotated_image.png, fan-4028, post-fix (v/omega drawn CCW)
  signfix_rest_tt3.png       ac_t.png, turntable-3, post-fix ("not turning" bands)

This script only CROPS the two annotated frames down to the fan, so the arrow reversal is
legible at slide size — the wide original is mostly ceiling. Everything else is used as-is.

Run:  python3 mk_signfix_figs.py
"""
import pathlib

from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent

# The annotated frame is ~1930x890 with the photo occupying roughly x 465..1480 and the
# callout column to its right. Keep the photo plus a sliver of margin: the arrows sit on
# the right-hand edge of the orbit, so the crop must not clip them. The top edge starts
# BELOW the figure title — the slide supplies its own, and a half-cut line of text reads
# as a rendering fault. The bottom stops above the empty ceiling: side by side on a 16:9
# slide, a taller-than-wide crop pushes the takeaway line off the frame.
CROP = (455, 56, 1400, 700)


def crop_arrows() -> None:
    for side in ("before", "after"):
        src = HERE / f"signfix_arrows_{side}.png"
        if not src.exists():
            raise SystemExit(f"missing {src.name} — see the provenance note in this file; "
                             "the 'before' image cannot be regenerated from current code")
        im = Image.open(src)
        box = tuple(min(v, lim) for v, lim in zip(CROP, (im.width, im.height) * 2))
        im.crop(box).save(HERE / f"signfix_arrows_{side}_crop.png")
        print(f"wrote signfix_arrows_{side}_crop.png  {box}")


if __name__ == "__main__":
    crop_arrows()
