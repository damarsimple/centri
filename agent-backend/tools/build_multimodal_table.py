#!/usr/bin/env python3
"""Aggregate the Axis-4 (multimodal) judge scores into a per-modality results table.

P-MAGIC reports its multimodal rubric BY MODALITY (image-text / text-graph / text-table), so this
mirrors that shape. The one thing it must get right is the **absent modality**: the basic tier
prints no table, so its four table criteria are *not applicable*. They are reported `n/a` and are
excluded from every mean — counting them as zero, or as 1, would invent a penalty for a figure the
tier deliberately never showed, and would make basic look worse the more correctly it was designed.

Usage:
  python tools/build_multimodal_table.py --prompts /tmp/mm_prompts --scores /tmp/judge_mm \
      --out-md material_work/_eval/multimodal_axis4.md --out-tex ../presentation/axis4_table.tex
"""
import argparse
import json
import pathlib
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run_llm_judge import MULTIMODAL_DEFS, MULTIMODAL_MODALITIES  # noqa: E402 — one rubric

TIERS = ["basic", "intermediate", "advanced"]
MODALITY_LABEL = {"image": "Image--text", "graph": "Text--graph", "table": "Text--table",
                  "video": "On video"}
CRIT_LABEL = {
    "image_precision": "Precision", "image_relevancy": "Relevancy",
    "graph_accuracy_labeling": "Accuracy \\& labelling",
    "graph_scale_proportions": "Scale \\& proportions",
    "graph_sense_physical": "Physical sense", "graph_relevancy": "Relevancy",
    "table_labels_scales": "Labels \\& scales",
    "table_proportional_reasoning": "Proportional reasoning",
    "table_physics_connection": "Physics connection", "table_relevancy": "Relevancy",
    "annotation_correctness": "Annotation correctness",
}
NA = "n/a"


def load(prompts_dir, scores_dir):
    """[(clip, tier, {criterion: score}, set(present_modalities))]."""
    rows = []
    for p in sorted(pathlib.Path(prompts_dir).glob("*.json")):
        spec = json.loads(p.read_text())
        sp = pathlib.Path(scores_dir) / f"{spec['clip']}.json"
        if not sp.exists():
            print(f"!! no scores for {spec['clip']}")
            continue
        scored = json.loads(sp.read_text())
        if isinstance(scored, dict):
            scored = scored.get("rows", [])
        rec = next((r for r in scored if r.get("tier") == spec["tier"]), None)
        if rec is None:
            print(f"!! {spec['clip']}.{spec['tier']}: missing")
            continue
        scores = {}
        for c in spec["criteria"]:
            v = rec.get(c)
            if not isinstance(v, int) or not 1 <= v <= 5:
                print(f"!! {spec['clip']}.{spec['tier']}.{c}: not an integer 1-5 ({v!r})")
                v = None
            scores[c] = v
        rows.append((spec["clip"], spec["tier"], scores, set(spec["modalities_present"])))
    return rows


def msd(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return (None, None, 0)
    return (statistics.mean(xs), statistics.pstdev(xs) if len(xs) > 1 else 0.0, len(xs))


def cell(rows, tier, crits):
    """(M, SD, n) over the given criteria for one tier — None when the modality is absent."""
    vals = [r[2][c] for r in rows if r[1] == tier for c in crits if c in r[2]]
    return msd(vals)


def build(rows):
    """[(kind, label, [(M, SD, n) per tier])] — kind in {modality, crit, agg}."""
    body = []
    for mod, crits in MULTIMODAL_MODALITIES.items():
        body.append(("modality", MODALITY_LABEL[mod], []))
        for c in crits:
            body.append(("crit", c, [cell(rows, t, [c]) for t in TIERS]))
        body.append(("agg", f"{MODALITY_LABEL[mod]} --- mean",
                     [cell(rows, t, crits) for t in TIERS]))
    allc = [c for cs in MULTIMODAL_MODALITIES.values() for c in cs]
    body.append(("agg", "All criteria scored", [cell(rows, t, allc) for t in TIERS]))
    return body


def _fmt(c, bold=False):
    m, s, n = c
    if m is None:
        return NA
    return (f"\\textbf{{{m:.2f}}}" if bold else f"{m:.2f}") + f" \\tiny({s:.2f})"


def md(body, rows):
    L = ["# Axis 4 — multimodal judge (the figures), by modality\n",
         "Scored 1–5 on the rubric in `docs/eval-rubric-ika.md` Axis 4 (P-MAGIC Table 2 rows plus",
         "our annotation row), by a vision LLM reading the rendered figures themselves.\n",
         "**`n/a` is not a low score.** The basic tier prints no table, so its four table criteria",
         "are not applicable and are excluded from every mean. Counting them would penalise the",
         "tier for a figure it was designed not to show.\n",
         "| Modality / dimension | basic | intermediate | advanced |", "|---|---|---|---|"]
    for kind, label, cells in body:
        if kind == "modality":
            L.append(f"| **{label.replace('--', '–')}** | | | |")
            continue
        b = "**" if kind == "agg" else ""
        name = label.replace("--", "–").replace("\\&", "&")
        name = CRIT_LABEL.get(label, name).replace("\\&", "&") if kind == "crit" else name
        cs = []
        for m, s, n in cells:
            cs.append(NA if m is None else f"{b}{m:.2f}{b} ({s:.2f}, n={n})")
        L.append(f"| {b}{name}{b} | " + " | ".join(cs) + " |")
    L += ["", f"n = worksheets scored per cell (7 clips × 1 worksheet per tier). "
              f"{len(rows)} worksheets total.", "",
          "## Criterion definitions", "", "| Criterion | Definition |", "|---|---|"]
    for c, d in MULTIMODAL_DEFS.items():
        L.append(f"| {c} | {d} |")
    return "\n".join(L) + "\n"


def tex(body):
    out = ["% Generated by tools/build_multimodal_table.py — do not edit by hand.",
           r"\newcommand{\axisFourTable}{%",
           r"\begin{tabular}{@{}l ccc@{}}", r"\toprule", r"\rowcolor{cInfra!12}",
           r"\textbf{Modality / dimension} & \textbf{\color{cBasic}basic} & "
           r"\textbf{\color{cInter}intermediate} & \textbf{\color{cAdv}advanced} \\", r"\midrule"]
    for kind, label, cells in body:
        if kind == "modality":
            out.append(rf"\multicolumn{{4}}{{@{{}}l}}{{\textbf{{{label}}}}} \\")
            continue
        agg = kind == "agg"
        cs = " & ".join(_fmt(c, agg) for c in cells)
        if agg:
            lbl = (r"\textbf{All criteria scored}" if label.startswith("All")
                   else rf"\quad\textbf{{{label}}}")
            out += [r"\addlinespace[1pt]", f"{lbl} & {cs} \\\\", r"\addlinespace[3pt]"]
        else:
            out.append(rf"\quad {CRIT_LABEL[label]} & {cs} \\")
    out += [r"\bottomrule", r"\end{tabular}}", ""]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompts", required=True)
    ap.add_argument("--scores", required=True)
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--out-tex")
    args = ap.parse_args()

    rows = load(args.prompts, args.scores)
    print(f"worksheets: {len(rows)}")
    body = build(rows)
    pathlib.Path(args.out_md).write_text(md(body, rows))
    print(f"wrote {args.out_md}")
    if args.out_tex:
        pathlib.Path(args.out_tex).write_text(tex(body))
        print(f"wrote {args.out_tex}")
    for kind, label, cells in body:
        if kind == "agg":
            print(f"  {label:34s} " + "  ".join(
                NA if m is None else f"{m:.2f}" for m, _, _ in cells))


if __name__ == "__main__":
    main()
