"""Provenance for the three figures in the 2026-07-27 weekly deck.

The repo tracks LaTeX and figure GENERATORS, never the PNGs (see .gitignore), so a figure has
to be rebuildable from a run. These three are not plotted here — they are copied straight out
of a pipeline run, which is the point: the deck shows real shipped output, not a mock-up.

    python presentation/figs/mk_material_rework_figs.py

`basic-frame-before.png` is the one exception: it is the basic-tier still as it was drawn
BEFORE the rework (radius only), so it can only come from a workspace that has not been
re-rendered with the current code. Keep `PRE_REWORK` pointing at such a run, or drop the
before/after slide rather than redraw it from memory.
"""
import shutil
from pathlib import Path

AB = Path("/home/damar/centri/agent-backend")
OUT = Path(__file__).resolve().parent

# A run rendered with the CURRENT code — the reworked basic frame and the ω(t)/a_c(t) plots that
# draw the measurement together with the camera-angle correction.
REWORKED = AB / "workspaces/job_roundabout-4046-final/analysis_output/plots"
# The same clip's shipped output from BEFORE the rework (basic frame = radius only).
PRE_REWORK = AB / "workspaces/job_roundabout-4046-final/analysis_output/plots"

COPIES = [
    (PRE_REWORK / "annotated_image_basic.png", "basic-frame-before.png"),
    (REWORKED / "annotated_image_basic.png", "basic-frame-after.png"),
    (REWORKED / "ac_t.png", "wheel-ac-shipped.png"),
]

if __name__ == "__main__":
    for src, name in COPIES:
        if not src.exists():
            print(f"MISSING {src} — skipping {name}")
            continue
        shutil.copy(src, OUT / name)
        print(f"wrote {OUT / name}  <-  {src}")
