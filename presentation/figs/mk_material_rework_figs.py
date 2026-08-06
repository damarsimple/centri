"""Provenance for the before/after figures in the 2026-07-27 decks.

The repo tracks LaTeX and figure GENERATORS, never the PNGs (see .gitignore), so a figure has to
be rebuildable from a run. Two of these are copied straight out of a pipeline run — that is the
point: the decks show real shipped output, not a mock-up.

    python presentation/figs/mk_material_rework_figs.py

`basic-frame-before.png` is the awkward one. It is the basic-tier still as it was drawn BEFORE the
rework (radius only), so it cannot come from the current code, and it must not come from "whatever
that workspace happens to hold" either — the first version of this script did exactly that, and
overwrote the before-figure with the after-figure the moment the workspace was re-rendered. It is
now reconstructed honestly: the pre-rework `figures.py` is checked out of git at PRE_REWORK_REF and
its `fig_annotated_image_basic` is run against the same clip. Same footage, same measurements, only
the drawing code differs — which is exactly what the before/after slide claims.
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path("/home/damar/centri")
AB = REPO / "agent-backend"
# Pinned to the ARCHIVED run (moved 2026-07-29): this figure contrasts two commits of the
# renderer on ONE fixed clip, so the clip must not drift under it.
CLIP = AB / "workspaces-archive/pre-full-e2e-20260729/job_roundabout-4046-final"
OUT = Path(__file__).resolve().parent
# The commit that gave the basic tier the full marked-up frame; its parent is the "before".
PRE_REWORK_REF = "789b60b^"

COPIES = [
    (CLIP / "analysis_output/plots/annotated_image_basic.png", "basic-frame-after.png"),
    (CLIP / "analysis_output/plots/ac_t.png", "wheel-ac-shipped.png"),
]


def _load_pre_rework_module():
    """Import the pre-rework render.figures, without disturbing the working tree."""
    src = subprocess.run(["git", "-C", str(REPO), "show",
                          f"{PRE_REWORK_REF}:agent-backend/workspace_lib/analysis/render/figures.py"],
                         capture_output=True, text=True, check=True).stdout
    pkg = Path(tempfile.mkdtemp()) / "analysis_old"
    (pkg / "render").mkdir(parents=True)
    # The module imports from its package siblings, so bring the current ones along: only the
    # basic-frame drawing changed, and that is the one function we are calling.
    for name in ("__init__.py", "common.py", "palette.py"):
        cur = AB / "workspace_lib/analysis" / name
        if cur.exists():
            shutil.copy(cur, pkg / name)
    for name in ("__init__.py", "palette.py"):
        cur = AB / "workspace_lib/analysis/render" / name
        if cur.exists():
            shutil.copy(cur, pkg / "render" / name)
    (pkg / "render" / "figures.py").write_text(src)
    sys.path.insert(0, str(pkg.parent))
    spec = importlib.util.spec_from_file_location("analysis_old.render.figures",
                                                  pkg / "render" / "figures.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["analysis_old.render.figures"] = mod
    spec.loader.exec_module(mod)
    return mod


def build_before():
    import json
    sys.path.insert(0, str(AB / "workspace_lib"))
    from analysis.common import dedup_display_name
    cwd = os.getcwd()
    os.chdir(CLIP)                       # the render module reads relative paths
    try:
        F = _load_pre_rework_module()
        stats = json.loads(Path("analysis_output/data/stats.json").read_text())
        scene = dedup_display_name(stats.get("scene_title") or stats.get("object_name"))
        F.plt.rcParams.update(F.STYLE)
        F.fig_annotated_image_basic(stats, scene)
        made = CLIP / "analysis_output/plots/annotated_image_basic.png"
        shutil.copy(made, OUT / "basic-frame-before.png")
        print(f"wrote {OUT / 'basic-frame-before.png'}  <-  {PRE_REWORK_REF} figures.py")
    finally:
        os.chdir(cwd)


def restore_workspace():
    """Put the workspace's own basic frame back.

    Rendering the historical figure writes into the clip's plots directory, and leaving the
    old drawing there would poison anything else built from that workspace — the contact sheet
    on the talk deck, for one. Undo it here rather than relying on remembering to."""
    cwd = os.getcwd()
    os.chdir(CLIP)
    try:
        subprocess.run([sys.executable, "-m", "analysis.render.figures"],
                       capture_output=True, check=True)
        print(f"restored {CLIP.name} figures to the current code")
    finally:
        os.chdir(cwd)


if __name__ == "__main__":
    # Order matters: the "before" render overwrites the workspace's own basic frame, so the
    # current one is copied out first and the workspace is restored at the end.
    for src, name in COPIES:
        if not src.exists():
            print(f"MISSING {src} — skipping {name}")
            continue
        shutil.copy(src, OUT / name)
        print(f"wrote {OUT / name}  <-  {src}")
    build_before()
    restore_workspace()
