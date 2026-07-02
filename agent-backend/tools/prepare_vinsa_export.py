#!/usr/bin/env python3
"""Build the learning-material evaluation package for Vinsa from finished jobs.

The deliverable is **material evaluation**: each object's generated learning
material (the candidate) plus an authentic textbook reference (OpenStax College
Physics 6.2) and the BERTScore relevance report.

For each job workspace it emits, under ``vinsa_export/``:
  <object-slug>__<jobshort>/
    material/material.json     the generated learning material (5 sections)
    material/material.md       the same, rendered for reading
    material/material.txt      sections joined (one BERTScore candidate per object)
    figures/                   annotated image | graph | table + summary panel
    report/                    student_edition.pdf, teacher_key.pdf (Learning Material leads)
    annotated_video.mp4        the annotated motion video
  _reference/openstax_6.2/     the authentic gold reference (reference.json/.md) + side-by-side
  material_eval_report.md      BERTScore F1 (material vs reference), mean +/- SD
  _combined/materials.txt      all objects' material concatenated (at-scale BERTScore)

Usage:  python tools/prepare_vinsa_export.py <job_id> [<job_id> ...]
"""
import json, shutil, sys, re, pathlib

WS = pathlib.Path("workspaces")
OUT = pathlib.Path("vinsa_export")
REF_SRC = pathlib.Path("material_work/_reference/openstax_6.2")
EVAL_SRC = pathlib.Path("material_work/_eval/material_eval_report.md")
FIGS = ["annotated_image.png", "annotated_graph.png", "annotated_table.png", "summary_panel.png"]
SECTIONS = ["Scenario", "The variables we measured", "How the variables are related",
            "What the video shows over time", "Reading the figures"]


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "scene").lower()).strip("-")[:40]


def find_ws(job_id):
    hits = sorted(WS.glob(f"job_{job_id}*"))
    return hits[0] if hits else None


def material_md(mat):
    secs = mat.get("sections", {})
    out = [f"# Learning material — {mat.get('scene_title','')}\n"]
    for h in SECTIONS:
        if secs.get(h):
            out.append(f"## {h}\n\n{secs[h].strip()}\n")
    return "\n".join(out)


def material_txt(mat):
    secs = mat.get("sections", {})
    return " ".join((secs.get(h) or "").strip() for h in SECTIONS).strip()


def main(job_ids):
    OUT.mkdir(exist_ok=True)
    # top-level reference + eval
    if REF_SRC.exists():
        dst = OUT / "_reference" / "openstax_6.2"
        dst.mkdir(parents=True, exist_ok=True)
        for f in REF_SRC.glob("*"):
            if f.is_file():
                shutil.copy2(f, dst / f.name)
    if EVAL_SRC.exists():
        shutil.copy2(EVAL_SRC, OUT / "material_eval_report.md")
        if EVAL_SRC.with_suffix(".json").exists():
            shutil.copy2(EVAL_SRC.with_suffix(".json"), OUT / "material_eval_report.json")

    combined, summary = [], []
    for jid in job_ids:
        ws = find_ws(jid)
        if not ws:
            print(f"!! no workspace for {jid}"); continue
        data = ws / "analysis_output" / "data"
        mpath = data / "material.json"
        if not mpath.exists():
            print(f"!! {ws.name}: no material.json (Subagent D not run?)"); continue
        mat = json.loads(mpath.read_text())
        scene = mat.get("scene_title") or mat.get("object_name") or "scene"
        short = ws.name.replace("job_", "")[:8]
        dest = OUT / f"{slug(scene)}__{short}"
        (dest / "material").mkdir(parents=True, exist_ok=True)
        (dest / "figures").mkdir(exist_ok=True)
        (dest / "report").mkdir(exist_ok=True)

        shutil.copy2(mpath, dest / "material" / "material.json")
        (dest / "material" / "material.md").write_text(material_md(mat))
        txt = material_txt(mat)
        (dest / "material" / "material.txt").write_text(txt + "\n")
        combined.append(txt)

        plots = ws / "analysis_output" / "plots"
        for f in FIGS:
            if (plots / f).exists():
                shutil.copy2(plots / f, dest / "figures" / f)
        avid = ws / "analysis_output" / "video_annotation" / "annotated_video.mp4"
        if avid.exists():
            shutil.copy2(avid, dest / "annotated_video.mp4")
        rep = ws / "analysis_output" / "report"
        for f in ("student_edition.pdf", "teacher_key.pdf"):
            if (rep / f).exists():
                shutil.copy2(rep / f, dest / "report" / f)

        nsec = len([h for h in SECTIONS if mat.get("sections", {}).get(h)])
        summary.append(f"{dest.name}: {nsec} material sections, {len(txt.split())} words")

    cdir = OUT / "_combined"
    cdir.mkdir(parents=True, exist_ok=True)
    (cdir / "materials.txt").write_text("\n\n".join(combined) + "\n")

    (OUT / "README.md").write_text(README)
    print("\n".join(summary))
    print(f"\nexport -> {OUT.resolve()}")


README = """# Centri -> Vinsa: learning-material evaluation package

Generated learning material from Centri (video-based centripetal-motion pipeline),
for **material relevance** evaluation comparable to P-MAGIC.

## Layout
```
<object>__<jobid>/
  material/material.json    generated learning material, 5 sections
  material/material.md      readable version
  material/material.txt     sections joined -> the BERTScore candidate
  figures/                  annotated image | graph | table + summary panel
  report/                   student_edition.pdf, teacher_key.pdf (Learning Material leads)
  annotated_video.mp4
_reference/openstax_6.2/    authentic gold reference (OpenStax College Physics 6.2),
                           reorganized into our 5-section format (reference.json/.md)
                           + side_by_side_fan.md (reference vs our material)
material_eval_report.md     BERTScore F1 (material vs reference), mean +/- SD
_combined/materials.txt     all objects' material (at-scale scoring)
```

## Metric
Raw BERTScore F1 of each object's `material.txt` vs `_reference/.../reference.txt`
(whole passage, and per section). Current set (5 objects): **F1 0.840 +/- 0.002**.

## Three things to confirm so the numbers match your method
1. **Reference** -- is the OpenStax 6.2 section the right gold, or do you want a
   different/added reference (e.g. angular-velocity 6.1 for period/frequency)? It is
   independent of our pipeline either way.
2. **Granularity** -- whole-passage F1 (headline) vs per-section F1 (diagnostic). Send
   your aggregation convention.
3. **Scaling** -- raw BERTScore (as here, comparable to your paper) vs baseline-rescaled.
"""


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
