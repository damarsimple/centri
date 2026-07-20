#!/usr/bin/env python3
"""Build human-rater sheets for teachers to score Centri material on the reconciled rubric
(Utami 2025 + P-MAGIC 2026; see docs/eval-framework.md).

Emits ONE CSV per teacher, pre-filled with (item × rubric-dimension) rows and a blank `score`
column for the teacher to fill 1–5. The CSV columns are exactly the tidy shape `eval_stats.py`
consumes (item,dimension,rater,role,score), so once teachers return their sheets they flow
straight into Cohen's κ / ICC / Pearson with zero rework. Also writes a companion
`passages.md` so raters can read each passage while scoring.

Rubric dimensions are imported from run_llm_judge.py so the human sheet and the LLM judge score
the SAME text criteria — the precondition for ICC(human vs LLM). Humans ALSO score Axis 4
(multimodal) from the rendered figures/PDF; that axis is compared against the vision MLLM-judge,
not the text judge.

Usage:
  .venv-eval/bin/python tools/build_rater_sheet.py \
      --materials vinsa_export/*/tiers/material.*.json \
      --raters teacher_a teacher_b \
      --outdir material_work/_eval/rater_sheets
"""
import argparse, csv, glob, json, pathlib

from run_llm_judge import CRITERIA, AXES, MULTIMODAL  # shared rubric = same criteria as the LLM judge

# One-line teacher-facing definition per dimension (from docs/eval-rubric-ika.md).
DEFN = {
    # Axis 1 — linguistic / authenticity
    "motivating_context": "Presents a meaningful, compelling purpose.",
    "language_clarity": "Language/terminology accessible to the target reading level.",
    "cognitive_demand": "An appropriate level of cognitive challenge.",
    "fluency": "Grammatically correct and reads naturally.",
    "completeness": "Includes the necessary context, conditions, and detail.",
    # Axis 2 — structural / comprehension
    "comprehension": "Understandable at the target reading level; a learner can follow it.",
    "structure_clarity": "Logical flow links the given information to the ideas.",
    "concept_accuracy": "Physics is correct — no misconceptions.",
    "realistic": "Scenario/quantities physically plausible, tied to a real situation.",
    "variable_name_consistency": "Symbols/notation used consistently and to standard (ω, a_c…).",
    # Axis 3 — physics / tier
    "difficulty_fit": "Depth matches the asserted tier (basic/intermediate/advanced).",
    "grounding_accuracy": "Numbers/figures consistent with the measured values.",
    # Axis 4 — multimodal (score from the rendered figures / PDF)
    "image_precision": "The text refers to the image/photo accurately and clearly.",
    "image_relevancy": "The image supports the passage's concept.",
    "graph_accuracy_labeling": "Graph plots the data correctly; axes labelled with right quantities + units.",
    "graph_scale_proportions": "Appropriate scale, evenly spaced intervals matching the data range.",
    "graph_sense_physical": "Conclusions from the graph are consistent with physical principles.",
    "graph_relevancy": "Axis titles/values in the graph align with the text.",
    "table_labels_scales": "Rows/columns clearly labelled with quantities + units; readable.",
    "table_proportional_reasoning": "Table supports proportional/predictive reasoning between variables.",
    "table_physics_connection": "Table connects to fundamental physics concepts and real-world context.",
    "table_relevancy": "Column titles/values align with and support the text.",
    "annotation_correctness": "Frame overlays (radius, ω, angle/deg-per-sec) point at the right object and read the right value.",
}
AXIS_OF = {c: axis for axis, cs in AXES.items() for c in cs}
AXIS_OF.update({c: "multimodal" for c in MULTIMODAL})
# Humans score the text axes AND the multimodal axis (the latter from the rendered figures/PDF).
ROWS = CRITERIA + MULTIMODAL


def _expand(patterns):
    paths = []
    for m in patterns:
        paths += sorted(glob.glob(m)) if any(c in m for c in "*?[") else [m]
    return [p for p in paths if "report" not in pathlib.Path(p).stem]


def _item_id(path, mat):
    """Stable id like 'spinning-fan-blade-toy.basic' from the export path + tier."""
    p = pathlib.Path(path)
    tier = mat.get("tier") or mat.get("difficulty_level") or p.stem.split(".")[-1]
    # parent-of-'tiers' dir is usually the object slug in vinsa_export
    obj = p.parent.parent.name if p.parent.name == "tiers" else p.parent.name
    return f"{obj}.{tier}"


def _passage(mat):
    secs = mat.get("sections", mat)
    return "\n\n".join(f"### {k}\n{v}" for k, v in secs.items() if isinstance(v, str))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--materials", nargs="+", required=True)
    ap.add_argument("--raters", nargs="+", required=True, help="teacher ids, e.g. teacher_a teacher_b")
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()

    paths = _expand(args.materials)
    mats = [(p, json.loads(pathlib.Path(p).read_text())) for p in paths]
    items = [(_item_id(p, m), m) for p, m in mats]

    outdir = pathlib.Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)

    # companion passages the teachers read while scoring
    pm = ["# Passages to rate\n",
          "Score each passage 1–5 on every dimension in your CSV (5 = excellent). The multimodal "
          "dimensions (image/graph/table/annotation) are scored from the rendered figures in the "
          "PDF, not the text below. See docs/eval-rubric-ika.md for definitions.\n"]
    for iid, m in items:
        pm.append(f"## {iid}  (asserted tier: {m.get('tier') or m.get('difficulty_level')})\n")
        pm.append(_passage(m) + "\n")
    (outdir / "passages.md").write_text("\n".join(pm) + "\n")

    for rater in args.raters:
        fp = outdir / f"sheet_{rater}.csv"
        with open(fp, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["item", "dimension", "rater", "role", "score", "axis", "definition"])
            for iid, _ in items:
                for c in ROWS:
                    w.writerow([iid, c, rater, "human", "", AXIS_OF[c], DEFN.get(c, "")])
        print(f"rater sheet -> {fp}  ({len(items)} items × {len(ROWS)} dimensions)")

    print(f"passages    -> {outdir / 'passages.md'}")
    print("Teachers fill the empty `score` column (1–5), then feed the sheets to eval_stats.py.")


if __name__ == "__main__":
    main()
