#!/usr/bin/env python3
"""Render Centri's evaluation results in the layouts P-MAGIC publishes, so the two sets of
numbers can be read side by side.

Two tables, mirroring Hwang et al. (J. Educational Computing Research 2026, `document-4.pdf`):

  * **Automatic** — their Table 3 ("Automatic Evaluation Results for Different Difficulty
    Levels"): rows are difficulty levels plus a Total, each carrying n and M/SD, columns are
    BERT F1 / BERT R / BERT P / Diversity / LSTM. Centri cannot report the LSTM language-fluency
    score — it needs P-MAGIC's own trained model — so that column is printed as "n/a" rather
    than silently dropped.

  * **Judge** — their Table 7 ("Human Evaluation Results"): sub-dimension rows grouped into
    blocks, columns N / M / SD per difficulty level. Centri's rater is currently an LLM, and the
    same rubric goes to the teacher panel unchanged, so the table shape has to serve both.

SCALES DIFFER, AND THE TABLE SAYS SO. P-MAGIC's teachers scored on a 10-point Likert; Centri
scores 1-5. A 1-5 mean is therefore also printed rescaled to 10 (`M10 = M x 2`) purely so the
columns can be compared at a glance. Rescaling is a linear stretch, not a calibration: it cannot
make two different instruments equivalent, and the caption keeps that caveat attached.

Usage
    .venv-eval/bin/python tools/build_pmagic_tables.py \
        --ref material_work/_reference/openstax_6.2/reference.json \
        --materials 'staged/*.json' \
        --judge-dir material_work/_eval/judge_2026-07-29 \
        --out-md material_work/_eval/pmagic_tables.md \
        --out-tex material_work/_eval/pmagic_tables.tex

`--materials` may be omitted to build the judge table alone (no BERTScore, no venv needed).
"""
import argparse
import glob
import json
import pathlib
import re
import statistics
import sys

TIERS = ("basic", "intermediate", "advanced")
# Our own tier names are used in the tables — relabelling our data with P-MAGIC's words would
# misrepresent whose numbers these are. The correspondence to their levels (Easy / Intermediate /
# Advanced) belongs in the caption, where a reader can see it is a mapping and not an identity.
PMAGIC_ALIAS = {"basic": "basic", "intermediate": "intermediate", "advanced": "advanced"}

# The 12 scored criteria, in rubric order, grouped as docs/eval-rubric-ika.md groups them.
AXES = [
    ("Linguistic / authenticity", [
        "motivating_context", "language_clarity", "cognitive_demand", "fluency", "completeness"]),
    ("Structural / comprehension", [
        "comprehension", "structure_clarity", "concept_accuracy", "realistic",
        "variable_name_consistency"]),
    ("Physics / tier", ["difficulty_fit", "grounding_accuracy"]),
]
CRITERIA = [c for _, cs in AXES for c in cs]

# Axis 4 scores the FIGURES, so it is kept separate from the 12 text criteria above: it is scored
# by a different rater (a vision model — the text judge cannot see an image), its criteria are not
# all applicable to every tier, and there is no second rater for it yet. It still belongs in the
# same results table, because the instrument the teachers receive is all 23 rows, not 12.
MM_AXIS = ("Multimodal / figures", [
    "image_precision", "image_relevancy",
    "graph_accuracy_labeling", "graph_scale_proportions", "graph_sense_physical",
    "graph_relevancy",
    "table_labels_scales", "table_proportional_reasoning", "table_physics_connection",
    "table_relevancy",
    "annotation_correctness"])

# Display name + lineage, for the criteria table (P-MAGIC's Table 2 shape). Sources are as
# recorded in docs/eval-rubric-ika.md: rows kept verbatim from a parent keep the parent's name
# in brackets so the two papers' tables can be lined up row by row.
CRITERION_META = {
    "motivating_context":        ("Motivating context", "Utami T8"),
    "language_clarity":          ("Language clarity", "Utami T8 / P-MAGIC"),
    "cognitive_demand":          ("Cognitive demand", "Utami T8"),
    "fluency":                   ("Fluency", "P-MAGIC"),
    "completeness":              ("Completeness", "P-MAGIC"),
    "comprehension":             ("Comprehension", "P-MAGIC (ling.\\ complexity)"),
    "structure_clarity":         ("Structure clarity", "Utami T9"),
    "concept_accuracy":          ("Concept accuracy", "P-MAGIC (concept underst.)"),
    "realistic":                 ("Realistic", "P-MAGIC"),
    "variable_name_consistency": ("Variable-name consistency", "P-MAGIC"),
    "difficulty_fit":            ("Difficulty fit", "Centri"),
    "grounding_accuracy":        ("Grounding accuracy", "Centri"),
    # Axis 4 — P-MAGIC Table 2's modality blocks, plus our annotation row.
    "image_precision":              ("Image precision", "P-MAGIC (image--text)"),
    "image_relevancy":              ("Image relevancy", "P-MAGIC (image--text)"),
    "graph_accuracy_labeling":      ("Graph accuracy \\& labelling", "P-MAGIC (text--graph)"),
    "graph_scale_proportions":      ("Graph scale \\& proportions", "P-MAGIC (text--graph)"),
    "graph_sense_physical":         ("Graph physical sense", "P-MAGIC (text--graph)"),
    "graph_relevancy":              ("Graph relevancy", "P-MAGIC (text--graph)"),
    "table_labels_scales":          ("Table labels \\& scales", "P-MAGIC (text--table)"),
    "table_proportional_reasoning": ("Table proportional reasoning", "P-MAGIC (text--table)"),
    "table_physics_connection":     ("Table physics connection", "P-MAGIC (text--table)"),
    "table_relevancy":              ("Table relevancy", "P-MAGIC (text--table)"),
    "annotation_correctness":       ("Annotation correctness", "Centri (on video)"),
}
# With a single judge there is no second rater to agree with, so Cohen's kappa is undefined and
# this dash stands in. The column is KEPT even then, because the teacher panel scores this same
# instrument and will fill it — dropping it would hide that the reliability figure is missing.
# Pass a second --judge-dir-b and the column fills with real per-criterion kappa.
AGREEMENT_PLACEHOLDER = "--"

# What each automatic metric is and how it is computed — every one of these is a similarity to
# ONE reference text (OpenStax College Physics §6.2, reorganised into our five sections), so all
# of them measure resemblance, not correctness and not teaching quality.
METRIC_DEFS = [
    ("n", "How many texts the row averages. The unit is one WORKSHEET: n = (clips x 3 levels), "
          "so one third of the Total per level. A per-SECTION figure instead multiplies that by "
          "the 5 document sections. The counts printed in the table are computed from the "
          "materials actually supplied, never assumed."),
    ("BERT F1", "Meaning overlap. RoBERTa-large turns each word into a context-aware vector and "
                "matches it to its closest reference word; F1 is the harmonic mean of R and P "
                "below. Raw, not baseline-rescaled, to match P-MAGIC."),
    ("BERT R", "Recall: of the reference's words, how many our text covers."),
    ("BERT P", "Precision: of our words, how many the reference supports."),
    ("BLEU-4", "Exact word-sequence overlap up to 4 words in a row, with a brevity penalty. "
               "Near zero for any text that is not a near-copy."),
    ("ROUGE-1", "Single-word overlap with the reference (F1)."),
    ("ROUGE-2", "Two-word-sequence overlap (F1)."),
    ("ROUGE-L", "Longest common subsequence — shared word order, gaps allowed (F1)."),
    ("Diversity", "How much the passages differ from EACH OTHER, not from the reference: one "
                  "minus their mean pairwise cosine similarity (MiniLM embeddings). Higher means "
                  "less repetitive. Within a level, and over every worksheet for Total."),
    ("LSTM", "P-MAGIC's fifth metric: a fluency score from an LSTM they trained. Needs their "
             "weights, which are unpublished — marked n/a rather than dropped, so the gap "
             "stays visible."),
]
METRIC_NOTE = (
    "> **What these mean.** " + "  ".join(f"**{k}** — {v}" for k, v in METRIC_DEFS) +
    "\n>\n> Every metric except diversity is similarity to a single reference text, so a higher "
    "score means *more like OpenStax*, not *better teaching*."
)


def msd(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return (None, None)
    return (statistics.mean(xs), statistics.pstdev(xs) if len(xs) > 1 else 0.0)


# ── the judge table (P-MAGIC Table 7 shape) ──────────────────────────────────

def read_judge(judge_dir):
    """[(clip, tier, {criterion: score}, bloom)] parsed from the per-clip judge reports."""
    rows = []
    for p in sorted(pathlib.Path(judge_dir).glob("judge_*.md")):
        clip = p.stem.replace("judge_", "")
        for line in p.read_text().splitlines():
            if not line.startswith("| material."):
                continue
            c = [x.strip() for x in line.strip().strip("|").split("|")]
            tier = c[1]
            if tier not in TIERS:
                continue
            scores = {}
            for name, cell in zip(CRITERIA, c[2:2 + len(CRITERIA)]):
                try:
                    scores[name] = int(cell)
                except ValueError:
                    scores[name] = None
            rows.append((clip, tier, scores, c[2 + len(CRITERIA)] if len(c) > 14 else ""))
    return rows


def judge_table(rows):
    """(header, body_rows) where a body row is (kind, label, cells...).

    kind is 'axis' for a block heading, 'crit' for a scored row, 'agg' for a summary line."""
    body = []
    for axis, crits in AXES:
        body.append(("axis", axis, []))
        for crit in crits:
            cells = []
            for tier in TIERS:
                vals = [r[2].get(crit) for r in rows if r[1] == tier]
                m, s = msd(vals)
                cells.append((len([v for v in vals if v is not None]), m, s))
            body.append(("crit", crit, cells))
        # the axis mean, over every criterion in the block
        cells = []
        for tier in TIERS:
            vals = [r[2].get(c) for r in rows if r[1] == tier for c in crits]
            m, s = msd(vals)
            cells.append((len([v for v in vals if v is not None]), m, s))
        body.append(("agg", f"{axis} — mean", cells))
    cells = []
    for tier in TIERS:
        vals = [r[2].get(c) for r in rows if r[1] == tier for c in CRITERIA]
        m, s = msd(vals)
        cells.append((len([v for v in vals if v is not None]), m, s))
    body.append(("agg", "All 12 criteria — mean", cells))
    return body


def mm_table(prompts_dir, scores_dir):
    """The Axis-4 block, in the same (kind, label, cells) shape as judge_table.

    Only ONE rater exists for it — the text judge cannot see a figure — so the caller pairs these
    cells with an empty column rather than inventing a second. A criterion the tier does not print
    (the basic tier ships no table) yields no samples and renders as `n/a`, never as a low score.
    """
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from build_multimodal_table import load

    rows = load(prompts_dir, scores_dir)
    label, crits = MM_AXIS
    body = [("axis", label, [])]
    for crit in crits:
        cells = []
        for tier in TIERS:
            vals = [sc[crit] for _, t, sc, _ in rows if t == tier and crit in sc]
            m, s = msd(vals)
            cells.append((len([v for v in vals if v is not None]), m, s))
        body.append(("crit", crit, cells))
    cells = []
    for tier in TIERS:
        vals = [sc[c] for _, t, sc, _ in rows if t == tier for c in crits if c in sc]
        m, s = msd(vals)
        cells.append((len([v for v in vals if v is not None]), m, s))
    body.append(("agg", f"{label} — mean", cells))
    return body


def empty_like(body):
    """The same rows with no data — the column for a rater that did not score this axis."""
    return [(kind, label, [(0, None, None)] * len(TIERS)) for kind, label, _ in body]


# ── two raters: the kappa column stops being a placeholder ───────────────────

def kappa_map(rows_a, rows_b):
    """{row-label: quadratic-weighted kappa} for every criterion, axis block and the total.

    Keyed the same way judge_table labels its rows, so the table code can look each one up
    without knowing how agreement is computed. Ordinal 1-5 ratings get QUADRATIC weights: a 4
    against a 5 is a near miss and must not count the same as a 1 against a 5.
    """
    from judge_agreement import kappa  # local: the builder still works with a single rater

    a = {(clip, tier): sc for clip, tier, sc, _ in rows_a}
    b = {(clip, tier): sc for clip, tier, sc, _ in rows_b}
    keys = sorted(set(a) & set(b))

    def k_for(crits):
        pairs = [(a[k].get(c), b[k].get(c)) for k in keys for c in crits
                 if a[k].get(c) is not None and b[k].get(c) is not None]
        return kappa(pairs, "quadratic")

    out = {"All 12 criteria — mean": k_for(CRITERIA)}
    for axis, crits in AXES:
        out[f"{axis} — mean"] = k_for(crits)
        for crit in crits:
            out[crit] = k_for([crit])
    return out, len(keys)


# ── the automatic table (P-MAGIC Table 3 shape) ──────────────────────────────

def score_materials(ref_path, material_globs):
    """{name: {metric: value}} whole-passage, plus per-level and overall diversity.

    BLEU / ROUGE are imported from `run_material_eval` rather than reimplemented, so the two
    reports cannot drift apart on the definition of a metric."""
    import bert_score
    from sentence_transformers import SentenceTransformer, util

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from run_material_eval import rouge_l, rouge_n, sentence_bleu

    SECTIONS = ["Scenario", "The variables we measured", "How the variables are related",
                "What the video shows over time", "Reading the figures"]

    def _norm(s):
        return re.sub(r"\s+", " ", s or "").strip()

    def load_sections(path):
        d = json.loads(pathlib.Path(path).read_text())
        secs = d.get("sections", d)
        return {k: _norm(v) for k, v in secs.items() if isinstance(v, str)}

    paths = []
    for m in material_globs:
        paths += sorted(glob.glob(m)) if any(c in m for c in "*?[") else [m]
    paths = [p for p in paths if "report" not in pathlib.Path(p).stem]
    ref = load_sections(ref_path)
    ref_full = " ".join((ref.get(s) or "") for s in SECTIONS)
    mats = [(pathlib.Path(p).stem, load_sections(p)) for p in paths]

    def _t(s, n=320):
        return " ".join(s.split()[:n])

    # BERTScore truncates to 320 words (RoBERTa's 512-token cap); BLEU/ROUGE run on the whole
    # passage, exactly as run_material_eval does it, so the two reports agree number for number.
    full = [" ".join((secs.get(s) or "") for s in SECTIONS) for _, secs in mats]
    cands = [_t(c) for c in full]
    P, R, F = bert_score.score(cands, [_t(ref_full)] * len(mats), lang="en",
                               rescale_with_baseline=False)
    triples = {}
    for (name, _), p, r, f, cf in zip(mats, P.tolist(), R.tolist(), F.tolist(), full):
        triples[name] = {"P": p, "R": r, "F1": f,
                         "BLEU": sentence_bleu(cf, ref_full),
                         "ROUGE1": rouge_n(cf, ref_full, 1),
                         "ROUGE2": rouge_n(cf, ref_full, 2),
                         "ROUGEL": rouge_l(cf, ref_full)}

    embedder = SentenceTransformer("all-MiniLM-L6-v2")
    emb = embedder.encode(cands, convert_to_tensor=True, normalize_embeddings=True)

    def diversity(idxs):
        sims = [float(util.cos_sim(emb[i], emb[j]))
                for a, i in enumerate(idxs) for j in idxs[a + 1:]]
        return (1 - statistics.mean(sims)) if sims else None

    names = [n for n, _ in mats]
    div = {t: diversity([i for i, n in enumerate(names) if n.endswith(f"__{t}")]) for t in TIERS}
    div["__all__"] = diversity(list(range(len(names))))
    return triples, div


METRICS = ("F1", "R", "P", "BLEU", "ROUGE1", "ROUGE2", "ROUGEL")


def auto_table(triples, div):
    """[(label, n, {metric: (M, SD)}, diversity)] per level, then a Total row."""
    body = []
    for tier in TIERS:
        vals = [v for k, v in triples.items() if k.endswith(f"__{tier}")]
        body.append((PMAGIC_ALIAS[tier], len(vals),
                     {m: msd([v[m] for v in vals]) for m in METRICS}, div.get(tier)))
    allv = list(triples.values())
    body.append(("Total", len(allv),
                 {m: msd([v[m] for v in allv]) for m in METRICS}, div.get("__all__")))
    return body


# ── emit ─────────────────────────────────────────────────────────────────────

def _n(x, prec=3):
    return "—" if x is None else f"{x:.{prec}f}"


def md(judge_body, auto_body, judge_body_b=None, kappas=None,
       label_a="judge A", label_b="judge B", n_worksheets=None):
    L = ["# Centri evaluation results in P-MAGIC table layouts\n",
         "Generated by `tools/build_pmagic_tables.py`. Layouts mirror Hwang et al. 2026",
         "(`refs/document-4.pdf`) Tables 3 and 7 so the two sets of numbers can be read",
         "side by side.\n"]

    if auto_body:
        L += ["## Automatic evaluation, by difficulty level (their Table 3)\n",
              "| Difficulty level | n | Statistic | BERT F1 | BERT R | BERT P | BLEU-4 | "
              "ROUGE-1 | ROUGE-2 | ROUGE-L | Diversity | LSTM |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for name, n, m, d in auto_body:
            L.append(f"| {name} | {n} | M | " + " | ".join(
                _n(m[k][0]) for k in METRICS) + f" | {_n(d)} | n/a |")
            L.append("| | | SD | " + " | ".join(
                _n(m[k][1]) for k in METRICS) + " | — | n/a |")
        L += ["", METRIC_NOTE, ""]

    L += ["## Judge evaluation, by criterion (their Table 7)\n",
          "Every dimension scored **1–5**. P-MAGIC's teachers used a **10-point** scale, so a",
          "rescaled mean (`M×2`) is given for comparison only — a linear stretch cannot make two",
          "instruments equivalent.\n"]

    if judge_body_b is not None:
        n_ws = n_worksheets if n_worksheets is not None else "the same"
        L += [f"Two judges, **{label_a}** and **{label_b}**, scored the same {n_ws} worksheets on the "
              "same 12 criteria, so Cohen's κ is a real number rather than a placeholder. It is "
              "**quadratic-weighted** (a 4 against a 5 is a near miss) and is **model-vs-model**: "
              "P-MAGIC's κ = 0.76 is between *human* raters, and two models agreeing would show "
              "the rubric is legible, not that its scores are valid.\n",
              "| Sub-dimension | κ | N | " + " | ".join(
                  f"{PMAGIC_ALIAS[t]} {label_a} | {PMAGIC_ALIAS[t]} {label_b}" for t in TIERS)
              + " |",
              "|---" * (3 + 2 * len(TIERS)) + "|"]
        for (kind, label, cells_a), (_, _, cells_b) in zip(judge_body, judge_body_b):
            if kind == "axis":
                L.append(f"| **{label}** |" + " |" * (2 + 2 * len(TIERS)))
                continue
            bold = "**" if kind == "agg" else ""
            k = (kappas or {}).get(label)
            cs = []
            for (na, ma, sa), (nb, mb, sb) in zip(cells_a, cells_b):
                cs += [f"{bold}{_n(ma, 2)}{bold} ({_n(sa, 2)})",
                       f"{bold}{_n(mb, 2)}{bold} ({_n(sb, 2)})"]
            # N comes from whichever rater actually scored the row (Axis 4 has only one), and
            # from the fullest tier — a criterion the basic tier does not print still has an N.
            n = max([c[0] for c in cells_a] + [c[0] for c in cells_b])
            L.append(f"| {bold}{label}{bold} | {'n/d' if k is None else f'{k:.2f}'} | "
                     f"{n} | " + " | ".join(cs) + " |")
        return "\n".join(L) + "\n"

    L += ["| Sub-dimension | " + " | ".join(
              f"{PMAGIC_ALIAS[t]} N | {PMAGIC_ALIAS[t]} M | {PMAGIC_ALIAS[t]} SD | "
              f"{PMAGIC_ALIAS[t]} M×2" for t in TIERS) + " |",
          "|---" * (1 + 4 * len(TIERS)) + "|"]
    for kind, label, cells in judge_body:
        if kind == "axis":
            L.append(f"| **{label}** |" + " |" * (4 * len(TIERS)))
            continue
        bold = "**" if kind == "agg" else ""
        cs = []
        for n, m, s in cells:
            cs += [str(n), f"{bold}{_n(m, 2)}{bold}", _n(s, 2),
                   "—" if m is None else f"{m * 2:.2f}"]
        L.append(f"| {bold}{label}{bold} | " + " | ".join(cs) + " |")
    return "\n".join(L) + "\n"


def tex(judge_body, auto_body, judge_body_b=None, kappas=None,
        label_a="judge A", label_b="judge B"):
    """Three COMPLETE booktabs tables, ready to \\input into a slide or a paper, laid out the way
    P-MAGIC lays out its Tables 2, 3 and 7 so the two papers can be read side by side.

    Emitted as \\newcommand wrappers rather than bare tabulars so a deck can place each one
    without caring how many columns it has."""
    out = ["% Generated by tools/build_pmagic_tables.py — do not edit by hand.",
           "% Layouts mirror Hwang et al. 2026 (refs/document-4.pdf) Tables 2, 3 and 7.", ""]

    # ── Table 2 shape: the instrument itself ────────────────────────────────
    out += [r"\newcommand{\pmagicCriteria}{%", r"\begin{tabular}{@{}llp{4.5cm}@{}}", r"\toprule",
            r"\rowcolor{cInfra!12}",
            r"\textbf{Dimension} & \textbf{Criterion} & \textbf{Adopted from} \\", r"\midrule"]
    for axis, crits in AXES:
        for i, c in enumerate(crits):
            name, src = CRITERION_META[c]
            dim = f"\\textbf{{{axis}}}" if i == 0 else ""
            # No hard-coded size: the caller picks one for the whole table, and an absolute
            # \footnotesize here renders LARGER than a \scriptsize table around it.
            out.append(f"{dim} & {name} & {src} \\\\")
        out.append(r"\addlinespace[2pt]")
    out += [r"\bottomrule", r"\end{tabular}}", ""]

    # ── Table 3 shape: automatic, M and SD on their own rows ────────────────
    if auto_body:
        out += [r"\newcommand{\pmagicAuto}{%",
                r"\begin{tabular}{@{}llc" + "c" * len(METRICS) + r"cc@{}}", r"\toprule",
                r"\rowcolor{cMeas!12}",
                r"\textbf{Level} & \textbf{n} & \textbf{Stat.} & "
                r"\textbf{BERT F1} & \textbf{BERT R} & \textbf{BERT P} & \textbf{BLEU-4} & "
                r"\textbf{ROUGE-1} & \textbf{ROUGE-2} & \textbf{ROUGE-L} & "
                r"\textbf{Diversity} & \textbf{LSTM} \\", r"\midrule"]
        for name, n, m, d in auto_body:
            lb = rf"\textbf{{{name}}}" if name == "Total" else name
            out.append(f"{lb} & {n} & M & " + " & ".join(_n(m[k][0]) for k in METRICS)
                       + f" & {_n(d)} & n/a \\\\")
            out.append(" & & SD & " + " & ".join(_n(m[k][1]) for k in METRICS)
                       + " & --- & n/a \\\\")
            out.append(r"\addlinespace[2pt]")
        out += [r"\bottomrule", r"\end{tabular}}", ""]

        # A compact glossary the deck can drop beside the table. The definitions are written once,
        # for both outputs, so plain-text arithmetic ("21 x 5") is lifted into real maths here
        # rather than being duplicated in two spellings.
        def _texify(s):
            return (s.replace(" x ", r" $\times$ ").replace(" - ", " -- ")
                     .replace("1 -- ", r"$1-$").replace("&", r"\&"))
        out += [r"\newcommand{\pmagicMetricDefs}{%",
                r"\begin{tabular}{@{}lp{9.4cm}@{}}", r"\toprule", r"\rowcolor{cMeas!12}",
                r"\textbf{Metric} & \textbf{What it is, and how it is computed} \\", r"\midrule"]
        for k, v in METRIC_DEFS:
            out.append(f"\\textbf{{{k}}} & {_texify(v)} \\\\")
        out += [r"\bottomrule", r"\end{tabular}}", ""]

    # ── Table 7 shape, two raters: kappa + M(SD) per level per judge ────────
    if judge_body_b is not None:
        ncol = 3 + 2 * len(TIERS)

        def _cell(c, bold=False):
            n, m, s = c
            if m is None:
                return "---"
            body = rf"\textbf{{{m:.2f}}}" if bold else f"{m:.2f}"
            return rf"{body} \tiny({s:.2f})"

        def emit(cmd, pairs):
            """One tabular over a SUBSET of the rows, with the full header.

            All 23 criteria will not fit on one 16:9 frame at a readable size, and shrinking to
            fit turned the text illegible. The table is therefore split across frames with an
            identical header on each — the same table continued, not two different ones. Which
            rows go where is the caller's choice, so the split is presentational only.
            """
            block = [rf"\newcommand{{{cmd}}}{{%",
                     r"\begin{tabular}{@{}l c c " + "cc " * len(TIERS) + r"@{}}", r"\toprule",
                     r"\rowcolor{cPed!12}",
                     r"& \textbf{Cohen's} & & " + " & ".join(
                         rf"\multicolumn{{2}}{{c}}{{\textbf{{\color{{c{a}}}{b}}}}}"
                         for a, b in (("Basic", "basic"), ("Inter", "intermediate"),
                                      ("Adv", "advanced"))) + r" \\",
                     r"\rowcolor{cPed!12}",
                     r"\textbf{Sub-dimension} & $\boldsymbol{\kappa}$ & \textbf{N} & " +
                     " & ".join([rf"\textbf{{{label_a}}} & \textbf{{{label_b}}}"] * len(TIERS))
                     + r" \\", r"\midrule"]
            for (kind, label, cells_a), (_, _, cells_b) in pairs:
                if kind == "axis":
                    block.append(rf"\multicolumn{{{ncol}}}{{@{{}}l}}{{\textbf{{{label}}}}} \\")
                    continue
                k = (kappas or {}).get(label)
                kt = "n/d" if k is None else f"{k:.2f}"
                agg = kind == "agg"
                cs = " & ".join(_cell(a, agg) + " & " + _cell(b, agg)
                                for a, b in zip(cells_a, cells_b))
                # N from whichever rater scored the row (Axis 4 has one), fullest tier.
                n = max([c[0] for c in cells_a] + [c[0] for c in cells_b])
                if agg:
                    name = label.split(" — ")[0]
                    lbl = rf"\quad\textbf{{{name} --- mean}}" if name != "All 12 criteria" \
                        else r"\textbf{All 12 criteria}"
                    block += [r"\addlinespace[1pt]", f"{lbl} & {kt} & {n} & {cs} \\\\",
                              r"\addlinespace[3pt]"]
                else:
                    block.append(rf"\quad {CRITERION_META[label][0]} & {kt} & {n} & {cs} \\")
            return block + [r"\bottomrule", r"\end{tabular}}", ""]

        pairs = list(zip(judge_body, judge_body_b))
        mm_names = {MM_AXIS[0]} | set(MM_AXIS[1]) | {f"{MM_AXIS[0]} — mean"}
        mm_pairs = [p for p in pairs if p[0][1] in mm_names]
        text_pairs = [p for p in pairs if p[0][1] not in mm_names]
        out += emit(r"\pmagicJudge", text_pairs)
        if mm_pairs:
            out += emit(r"\pmagicJudgeMM", mm_pairs)
        return "\n".join(out) + "\n"

    # ── Table 7 shape: every criterion, agreement + N/M/SD per level ────────
    ncol = 2 + 3 * len(TIERS)
    # The agreement column keeps P-MAGIC's own name, "Cohen's kappa", rather than a paraphrase:
    # split over two header lines as "Agree-/ment" it read as an unexplained word, and kappa is
    # what an advisor holding their paper is looking for.
    out += [r"\newcommand{\pmagicJudge}{%",
            r"\begin{tabular}{@{}l c " + "ccc " * len(TIERS) + r"@{}}", r"\toprule",
            r"\rowcolor{cPed!12}",
            r"& \textbf{Cohen's} & " + " & ".join(
                rf"\multicolumn{{3}}{{c}}{{\textbf{{\color{{c{a}}}{b}}}}}"
                for a, b in (("Basic", "basic"), ("Inter", "intermediate"),
                             ("Adv", "advanced"))) + r" \\",
            r"\rowcolor{cPed!12}",
            r"\textbf{Sub-dimension} & $\boldsymbol{\kappa}$ & " +
            " & ".join([r"\textbf{N} & \textbf{M} & \textbf{SD}"] * len(TIERS)) + r" \\",
            r"\midrule"]
    for kind, label, cells in judge_body:
        if kind == "axis":
            out.append(rf"\multicolumn{{{ncol}}}{{@{{}}l}}{{\textbf{{{label}}}}} \\")
            continue
        if kind == "agg":
            name = label.split(" — ")[0]
            lbl = rf"\quad\textbf{{{name} --- mean}}" if name != "All 12 criteria" \
                else r"\textbf{All 12 criteria}"
            cs = " & ".join(f"{n} & \\textbf{{{_n(m, 2)}}} & {_n(s, 2)}" for n, m, s in cells)
            out += [r"\addlinespace[1pt]", f"{lbl} & {AGREEMENT_PLACEHOLDER} & {cs} \\\\",
                    r"\addlinespace[3pt]"]
            continue
        name = CRITERION_META[label][0]
        cs = " & ".join(f"{n} & {_n(m, 2)} & {_n(s, 2)}" for n, m, s in cells)
        out.append(rf"\quad {name} & {AGREEMENT_PLACEHOLDER} & {cs} \\")
    out += [r"\bottomrule", r"\end{tabular}}", ""]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge-dir", required=True)
    ap.add_argument("--judge-dir-b", help="second rater; fills the Cohen's kappa column")
    ap.add_argument("--judge-label", default="judge A")
    ap.add_argument("--judge-label-b", default="judge B")
    ap.add_argument("--mm-prompts", help="Axis-4 frozen prompts (export_multimodal_prompts.py)")
    ap.add_argument("--mm-scores", help="Axis-4 scores dir (<clip>.json per clip)")
    ap.add_argument("--mm-rater", choices=("a", "b"), default="b",
                    help="which column scored Axis 4; the other is left blank")
    ap.add_argument("--ref")
    ap.add_argument("--materials", nargs="*", default=[])
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--out-tex")
    args = ap.parse_args()

    rows = read_judge(args.judge_dir)
    print(f"judge rows: {len(rows)}")
    jb = judge_table(rows)

    jb_b, kap = None, None
    if args.judge_dir_b:
        rows_b = read_judge(args.judge_dir_b)
        print(f"judge-B rows: {len(rows_b)}")
        jb_b = judge_table(rows_b)
        kap, paired = kappa_map(rows, rows_b)
        print(f"paired worksheets: {paired}; overall kappa = {kap['All 12 criteria — mean']:.2f}")

    # Axis 4 goes into the SAME table: the instrument the teachers receive is 23 rows, not 12.
    # Only the VISION rater scored it — a text judge cannot see a figure — so the other column is
    # left empty there. That is an absence with a reason, which a dash states and a missing block
    # would hide. The "All 12 criteria" total stays over the text criteria only, so it remains
    # comparable with runs that had no Axis 4; the multimodal block carries its own mean.
    if args.mm_prompts and args.mm_scores:
        mb = mm_table(args.mm_prompts, args.mm_scores)
        print(f"axis-4 rows: {len(mb) - 2} criteria")
        blank = empty_like(mb)
        jb = jb[:-1] + (mb if args.mm_rater == "a" else blank) + jb[-1:]
        if jb_b is not None:
            jb_b = jb_b[:-1] + (mb if args.mm_rater == "b" else blank) + jb_b[-1:]

    ab = []
    if args.materials and args.ref:
        triples, div = score_materials(args.ref, args.materials)
        print(f"scored materials: {len(triples)}")
        ab = auto_table(triples, div)

    n_ws = len(set((c, t) for c, t, _, _ in rows))
    kw = dict(judge_body_b=jb_b, kappas=kap,
              label_a=args.judge_label, label_b=args.judge_label_b)
    pathlib.Path(args.out_md).write_text(md(jb, ab, n_worksheets=n_ws, **kw))
    print(f"wrote {args.out_md}")
    if args.out_tex:
        pathlib.Path(args.out_tex).write_text(tex(jb, ab, **kw))
        print(f"wrote {args.out_tex}")


if __name__ == "__main__":
    main()
