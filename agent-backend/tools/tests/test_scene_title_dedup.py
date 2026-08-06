#!/usr/bin/env python3
"""The degenerate "<X> on <X>" scene title must not reach a learner-facing surface.

`prompts/orchestrator.txt` composes the title as "<tracked> on <ref>". That reads fine until
the tracked object IS the scale reference — on computerfan-4029 the 4 cm red marker is both, so
the title shipped as **"red marker on red marker"**.

`common.dedup_display_name` was written for exactly this, and its own docstring says it is "the
shared helper so figures.py, the seed, and the report all collapse it identically". The flaw was
that it is opt-in: `render/annotate.py` never called it, so the video banner carried the duplicate
while the figure rendered beside it did not. A shared helper that every surface must remember to
call is a convention, not a guarantee.

So this pins two things:
  1. the contract normalises the title ONCE at the seam, and
  2. no surface reads a raw scene_title out of stats.json without deduping it.
"""
import ast
import json
import re
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "workspace_lib"))
from analysis import common, contract

LIB = ROOT / "workspace_lib" / "analysis"


# ── the helper itself ────────────────────────────────────────────────────────────
def test_dedup_collapses_only_a_true_duplicate():
    assert common.dedup_display_name("red marker on red marker") == "red marker"
    assert common.dedup_display_name("Red Marker on red marker") == "Red Marker"  # case-insensitive
    assert common.dedup_display_name("  red  marker on red marker ") == "red marker"
    # genuinely different halves must survive untouched
    assert common.dedup_display_name("red phone on black circular base") == \
        "red phone on black circular base"
    assert common.dedup_display_name("a black handle on a playground wheel") == \
        "a black handle on a playground wheel"
    # a shared WORD is not a duplicate
    assert common.dedup_display_name("fan blade on fan hub") == "fan blade on fan hub"
    assert common.dedup_display_name(None) == ""
    # idempotent
    once = common.dedup_display_name("red marker on red marker")
    assert common.dedup_display_name(once) == once


# ── normalised at the seam, so a new surface cannot reintroduce it ──────────────
def _inputs(tmp, scene_title, tracked="red marker", ref="red marker"):
    n = 60
    th = np.linspace(0, 2 * np.pi, n)
    p = Path(tmp) / "pipeline_inputs.json"
    body = {
        "fps": 60.0, "duration_s": 1.0, "n_raw_frames": n,
        "object_name": tracked, "tracked_label": tracked, "ref_label": ref,
        "trajectory_x_px": list(500 + 100 * np.cos(th)),
        "trajectory_y_px": list(400 + 100 * np.sin(th)),
        "center": {"cx_px": 500.0, "cy_px": 400.0, "source": "user_mark"},
        "reference": {"diameter_px": 205.0, "physical_size_m": 0.04,
                      "physical_size_source": "sidecar"},
        "coordinate_space": "cropped-video",
        "roi_crop": {"x_off": 0, "y_off": 0, "crop_w": 1080, "crop_h": 1244},
    }
    if scene_title is not None:
        body["scene_title"] = scene_title
    p.write_text(json.dumps(body))
    return p


def test_contract_collapses_the_supplied_title():
    with tempfile.TemporaryDirectory() as tmp:
        common._validation_flags.clear()
        inp = contract.load_inputs(_inputs(tmp, "red marker on red marker"))
        assert inp.scene_title == "red marker", inp.scene_title


def test_contract_collapses_the_fallback_title():
    """No scene_title at all: the fallback builds '<tracked> on <ref>' — which is the
    degenerate form precisely when the marker is also the reference."""
    with tempfile.TemporaryDirectory() as tmp:
        common._validation_flags.clear()
        inp = contract.load_inputs(_inputs(tmp, None))
        assert inp.scene_title == "red marker", inp.scene_title


def test_contract_leaves_a_real_title_alone():
    with tempfile.TemporaryDirectory() as tmp:
        common._validation_flags.clear()
        inp = contract.load_inputs(_inputs(tmp, "a red marker on a computer fan blade",
                                           tracked="red marker", ref="fan blade"))
        assert inp.scene_title == "a red marker on a computer fan blade"


# ── no display surface may read the title raw ───────────────────────────────────
def _stats_title_reads(path: Path):
    """Yield (lineno, line) for every read of scene_title straight out of `stats`.

    Scoped deliberately to `stats.*`, the contract's output surface, which is where the
    annotate.py miss lived. Reads from `seed` are already normalised upstream by
    `material_seed.build_seed`, and reads from the LLM-authored `frame` dict are deduped
    where that dict is built (`material_tiers._frame`) — asserting on those would be
    testing a value's provenance from the wrong end and would fail for no defect."""
    for i, line in enumerate(path.read_text().splitlines(), 1):
        if re.search(r'\bstats\w*\.get\(\s*["\']scene_title["\']', line):
            yield i, line.strip()


def test_no_surface_reads_scene_title_raw_from_stats():
    """Structural guard: this is how the annotate.py miss would have been caught."""
    offenders = []
    for path in sorted(LIB.rglob("*.py")):
        for lineno, line in _stats_title_reads(path):
            if "dedup_display_name" in line or "_dedup(" in line:
                continue
            offenders.append(f"{path.relative_to(ROOT)}:{lineno}: {line}")
    assert not offenders, (
        "scene_title read from stats without dedup_display_name — the 'red marker on red "
        "marker' class:\n  " + "\n  ".join(offenders))


def test_the_guard_would_have_caught_the_annotate_miss():
    """Pins the guard to the defect: the pre-fix line must be rejected by the same rule."""
    pre_fix = 'scene_label = stats.get("scene_title") or stats.get("object_name") or ""'
    assert re.search(r'\bstats\w*\.get\(\s*["\']scene_title["\']', pre_fix)
    assert "dedup_display_name" not in pre_fix and "_dedup(" not in pre_fix


def test_annotate_imports_the_shared_helper():
    """The specific surface that was missed. Import-level so it survives refactors of main()."""
    src = (LIB / "render" / "annotate.py").read_text()
    tree = ast.parse(src)
    imported = {
        (alias.asname or alias.name)
        for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        for alias in node.names
        if alias.name == "dedup_display_name"
    }
    assert imported, "render/annotate.py must import dedup_display_name from ..common"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"{len(fns)}/{len(fns)} passed")
