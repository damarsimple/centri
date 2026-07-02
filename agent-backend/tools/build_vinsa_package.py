#!/usr/bin/env python3
"""Build the VALIDATION-CENTRIC evaluation package for Vinsa from finished jobs.

Unlike the legacy single-material export, this is organised around what Vinsa actually
does: (1) SCORE — run BERTScore on candidate-vs-reference text; (2) VALIDATE — confirm
our material's numbers are the real MEASURED ones, not fabricated. It ships the three
difficulty tiers per object, the ground-truth seed, a ready-to-score CSV, and our own
result reports so she can reproduce/compare.

Layout produced (default OUT = vinsa_export):
  README.md
  SCORING_SHEET.csv            object,tier,section,candidate,reference   (per-section pairs)
  SCORING_SHEET_whole.csv      object,tier,candidate,reference           (whole-passage pairs)
  _reference/openstax_6.2/     the authentic gold reference (json/md/txt)
  _results/                    our BERTScore + difficulty + grounding reports (to compare)
  <object>__<jobshort>/
    tiers/material.{basic,intermediate,advanced}.{json,md,txt}
    ground_truth/material_seed.json     the measured numbers (validate the prose against these)
    figures/                            annotated frame, plots, tables
    report/student_edition.<tier>.pdf, teacher_key.<tier>.pdf
    annotated_video.mp4

Usage:  python tools/build_vinsa_package.py <job_id> [<job_id> ...] [--out DIR]
"""
import argparse, csv, json, shutil, pathlib

WS = pathlib.Path("workspaces")
REF_SRC = pathlib.Path("material_work/_reference/openstax_6.2")
RESULTS = {  # report name -> source path (copied into _results/ if present)
    "material_eval_report": pathlib.Path("material_work/_eval/tier_all_eval_report"),
    "multireference_report": pathlib.Path("material_work/_eval/tier_all_multiref_report"),
    "tier_difficulty_report": pathlib.Path("material_work/_eval/tier_all_difficulty_report"),
    "grounding_report": pathlib.Path("material_work/_eval/tier_all_grounding_report"),
}
TIERS = ["basic", "intermediate", "advanced"]
SECTIONS = ["Scenario", "The variables we measured", "How the variables are related",
            "What the video shows over time", "Reading the figures"]
FIGS = ["annotated_image.png", "annotated_image_basic.png", "annotated_graph.png",
        "annotated_table.png", "summary_panel.png", "trajectory.png", "trajectory_basic.png",
        "v_t.png", "omega_t.png", "ac_t.png"]


def find_ws(job_id):
    hits = sorted(WS.glob(f"job_{job_id}*"))
    return hits[0] if hits else None


def material_md(mat):
    secs = mat.get("sections", {})
    head = f"# {mat.get('scene_title','')} — {mat.get('tier','')} tier\n"
    head += (f"*Bloom objective: {mat.get('bloom_objective','')} · "
             f"element interactivity: {mat.get('element_interactivity','')}*\n")
    body = [f"## {h}\n\n{secs[h].strip()}\n" for h in SECTIONS if secs.get(h)]
    return head + "\n" + "\n".join(body)


def material_txt(mat):
    secs = mat.get("sections", {})
    return " ".join((secs.get(h) or "").strip() for h in SECTIONS).strip()


def main(job_ids, out):
    out = pathlib.Path(out)
    out.mkdir(exist_ok=True)
    ref = json.loads((REF_SRC / "reference.json").read_text()).get("sections", {})

    # reference + result reports
    rdst = out / "_reference" / "openstax_6.2"
    rdst.mkdir(parents=True, exist_ok=True)
    for f in REF_SRC.glob("*"):
        if f.is_file():
            shutil.copy2(f, rdst / f.name)
    res = out / "_results"
    res.mkdir(exist_ok=True)
    for name, base in RESULTS.items():
        for ext in (".md", ".json"):
            if base.with_suffix(ext).exists():
                shutil.copy2(base.with_suffix(ext), res / (name + ext))

    sec_rows, whole_rows, summary = [], [], []
    for jid in job_ids:
        ws = find_ws(jid)
        if not ws:
            print(f"!! no workspace for {jid}"); continue
        data = ws / "analysis_output" / "data"
        tiers = {t: data / f"material.{t}.json" for t in TIERS
                 if (data / f"material.{t}.json").exists()}
        if not tiers:
            print(f"!! {ws.name}: no tier materials"); continue
        # name the object dir from the first tier's scene
        first = json.loads(next(iter(tiers.values())).read_text())
        slug = __import__("re").sub(r"[^a-z0-9]+", "-",
                                   (first.get("scene_title") or first.get("object_name") or "scene").lower()).strip("-")[:40]
        short = ws.name.replace("job_", "")[:8]
        dest = out / f"{slug}__{short}"
        (dest / "tiers").mkdir(parents=True, exist_ok=True)
        (dest / "ground_truth").mkdir(exist_ok=True)
        (dest / "figures").mkdir(exist_ok=True)
        (dest / "report").mkdir(exist_ok=True)

        for t, p in tiers.items():
            mat = json.loads(p.read_text())
            shutil.copy2(p, dest / "tiers" / f"material.{t}.json")
            (dest / "tiers" / f"material.{t}.md").write_text(material_md(mat))
            cand_whole = material_txt(mat)
            (dest / "tiers" / f"material.{t}.txt").write_text(cand_whole + "\n")
            whole_rows.append([slug, t, cand_whole, " ".join((ref.get(s) or "") for s in SECTIONS)])
            for s in SECTIONS:
                sec_rows.append([slug, t, s, (mat.get("sections", {}).get(s) or "").strip(),
                                 (ref.get(s) or "").strip()])
        # ground truth + figures + pdfs + video
        if (data / "material_seed.json").exists():
            shutil.copy2(data / "material_seed.json", dest / "ground_truth" / "material_seed.json")
        if (data / "material_tiers_gate.json").exists():
            shutil.copy2(data / "material_tiers_gate.json", dest / "ground_truth" / "grounding_gate.json")
        plots = ws / "analysis_output" / "plots"
        for f in FIGS:
            if (plots / f).exists():
                shutil.copy2(plots / f, dest / "figures" / f)
        rep = ws / "analysis_output" / "report"
        for t in tiers:
            for kind in ("student_edition", "teacher_key"):
                src = rep / f"{kind}.{t}.pdf"
                if src.exists():
                    shutil.copy2(src, dest / "report" / f"{kind}.{t}.pdf")
        avid = ws / "analysis_output" / "video_annotation" / "annotated_video.mp4"
        if avid.exists():
            shutil.copy2(avid, dest / "annotated_video.mp4")
        summary.append(f"{dest.name}: {len(tiers)} tiers "
                       f"({', '.join(sorted(tiers))}), seed={'y' if (data/'material_seed.json').exists() else 'n'}")

    # scoring sheets
    with open(out / "SCORING_SHEET.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["object", "tier", "section", "candidate", "reference"])
        w.writerows(sec_rows)
    with open(out / "SCORING_SHEET_whole.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["object", "tier", "candidate", "reference"])
        w.writerows(whole_rows)

    (out / "README.md").write_text(README)
    print("\n".join(summary))
    print(f"\nSCORING_SHEET.csv: {len(sec_rows)} section pairs; "
          f"SCORING_SHEET_whole.csv: {len(whole_rows)} whole-passage pairs")
    print(f"package -> {out.resolve()}")


README = """# Centri -> Vinsa: tiered learning-material evaluation package

Generated learning material from Centri (video-based centripetal-motion pipeline). Every
object now has **three difficulty tiers** (basic / intermediate / advanced), grounded in
Bloom's Revised Taxonomy + Cognitive Load Theory. This package is built so you can both
**score** it and **validate** that the numbers are real.

## 1. To SCORE (BERTScore, as in your method)
- `SCORING_SHEET.csv` — one row per (object, tier, **section**): the `candidate` cell is our
  material, the `reference` cell is the matching OpenStax section. Run BERTScore row-wise for
  per-section F1, or group by (object,tier) for whole-passage.
- `SCORING_SHEET_whole.csv` — one row per (object, tier): whole candidate vs whole reference.
- Raw text per tier is also in `<object>/tiers/material.<tier>.txt` (sections joined).
- Reference: `_reference/openstax_6.2/` — authentic OpenStax College Physics 6.2, reorganized
  into our 5 sections, built independently of our pipeline.

## 2. To VALIDATE that our material is faithful (not fabricated)
- `<object>/ground_truth/material_seed.json` — the **measured** numbers (radius, omega, v,
  a_c, T, f, angular acceleration, a time-anchored timeline). Every number in the material
  must trace to this seed. Identities (v=omega*r, a_c=omega^2*r) close at any single timeline
  instant (not on the time-averaged means — Jensen).
- `<object>/ground_truth/grounding_gate.json` — our automatic gate verdict per tier.
- `<object>/figures/` + `annotated_video.mp4` — visual evidence the tracked motion is real.
- `<object>/report/student_edition.<tier>.pdf` + `teacher_key.<tier>.pdf` — human-readable.

## 3. Our own results (so you can compare to your scoring)
`_results/`:
- `material_eval_report.md` — our BERTScore F1 (P/R/F1) per object-tier + per section, vs the
  reorganized OpenStax §6.2 gold (the section-aligned headline metric).
- `multireference_report.md` — the same candidates scored against the **full English reference
  set** (1 reorganized gold + ~18 raw PDFs), as a robustness band. Per tier: gold §6.2 0.811 /
  0.831 / 0.828; full-set 0.798 / 0.806 / 0.800 (basic / intermediate / advanced). The ranking is
  stable across references — §6.2 is not cherry-picked.
- `tier_difficulty_report.md` — an INDEPENDENT, model-free difficulty signal (Flesch
  readability + element-interactivity count). It shows the tiers really differ — and that a
  single fixed reference scores by lexical density, not pedagogical quality.
- `grounding_report.md` — our deterministic check that every number computes and traces to
  the seed (catches arithmetic that BERTScore is blind to).

## Open questions to confirm so the numbers match your method
1. **Reference** — is OpenStax 6.2 the right gold, or add another (e.g. 6.1 for period/
   frequency / angular velocity)? Should tiers be scored against **tier-matched** references?
2. **Granularity & aggregation** — whole-passage vs per-section; how to aggregate across tiers.
3. **Scaling** — raw BERTScore (as here, comparable to your paper) vs baseline-rescaled.
"""


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("job_ids", nargs="+")
    ap.add_argument("--out", default="vinsa_export")
    a = ap.parse_args()
    main(a.job_ids, a.out)
