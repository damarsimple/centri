# Centri evaluation framework (formalized, 2026-07-08)

The single, consolidated description of how Centri-generated material is evaluated. It reconciles
the **two parent rubrics** with Centri's own extensions, and defines the measurement layers and
statistics. Companion docs: `eval-rubric-ika.md` (the scored rubric, single source of truth for the
tools), `related-work-positioning.md` (the niche), `effectiveness-study-blueprint.md` (the later
learning-gains study).

**Sources adopted (for comparability with the lab's published numbers):**
- **Utami (2025)** PhD dissertation — *Authentic MWP Generation* (NCU, advisor Hwang). Rubric
  Tables 8–9; procedure §3.4.3.
- **P-MAGIC** — Hwang, Sari, Purba, Azhar, *J. Educational Computing Research* 2026 (`document-4.pdf`):
  *AI-Enhanced Quality of Multimodal Physics Word Problems*. **Table 2** (22–25-item human rubric,
  organised **by modality**), automatic layer (BERT/STS/LSTM), Pearson auto↔human.

**Unit of evaluation.** A **learning-material passage** at one of three tiers (basic / intermediate
/ advanced), plus its **annotated figures** — *not* a word problem. This is why some problem-only
rubric rows are dropped (below).

---

## The four rubric axes (reconciled)

Every criterion scored **1–5** (5 = excellent). `#` = adopted/kept, `slim` = kept but pruned,
`NEW` = Centri's own.

### Axis 1 — Linguistic / authenticity  *(Utami Table 8 + P-MAGIC "Linguistic")*
motivating_context · language_clarity · cognitive_demand · fluency · completeness.
Keeps Utami's pedagogical rows (motivating context, **cognitive_demand** — a strong tier signal) and
adds P-MAGIC's surface-quality rows (fluency, completeness); **drops** the problem-only
solution-steps / solution-strategy-variety.

### Axis 2 — Structural / comprehension  *(slimmed from Utami Table 9 + P-MAGIC "Physics aspect")*
- **Keep:** comprehension · structure & clarity · concept accuracy · realistic (physically
  plausible, real-world) · **variable-name consistency** (notation used consistently — from P-MAGIC).
- **DROP as problem-only** (our unit is exposition, not a task): problem answerability · solvability
  · multiple solution strategies. *(This retires the "expository-unfair" caveat from the 07-08 deck
  by construction.)*

### Axis 3 — Physics / tier + recognition  *(Centri's own)*
- difficulty_fit (depth matches the tier) · achieved_bloom (vs the tier's Bloom target) ·
  grounding_accuracy (numbers trace to the measured seed).
- **NEW — video_recognition_quality:** how well the tracked kinematics match ground truth. Neither
  parent can score this (AR / phone-IMU sensing, no video CV). We *have* the ground truth (the
  grounding gate), so it is measurable — see the dedicated section below.

### Axis 4 — Multimodal  *(adopted ≈verbatim from P-MAGIC Table 2 + one Centri row)*
Scored per modality present:
- **Image–text:** precision (question/prose refers accurately to the image) · relevancy (image
  supports the concept). *(Otani et al., 2023)*
- **Text–graph:** graph accuracy & proper labeling · scale & proportions · graph sense in physical
  context · relevancy (axis titles/values ↔ text). *(Stefanel, 2019)*
- **Text–table:** clear labels & scales · proportional/predictive reasoning · connection to physics
  concepts · relevancy. *(Stefanel, 2019)*
- **NEW — annotation_correctness (on video):** the per-frame overlays (radius, ω, angle-swept /
  degrees-per-second) point at the right object and read the right value. Centri's differentiated
  artifact — annotation *across the motion*, not one still image.

### Reconciliation at a glance

| Axis | From Utami | From P-MAGIC | Centri-only |
|---|---|---|---|
| 1 Linguistic | Table 8: motivating, clarity, cognitive-demand | Linguistic: fluency, completeness | drops solution-steps/variety (problem-only) |
| 2 Structural/comprehension | Table 9 (structure only) | concept, realistic, variable-name | comprehension framing; drops problem-only rows |
| 3 Physics/tier + recognition | — | difficulty→difficulty_fit | grounding, achieved_bloom, **video_recognition_quality** |
| 4 Multimodal | — | image-text / text-graph / text-table | **annotation_correctness (on video)** |

---

## The measurement layers

**0. Deterministic grounding gate** *(Centri, zero-cost, runs first).* Arithmetic closure,
number-grounding to the seed, tier compliance, motion faithfulness, cross-tier checks
(`material_gate.py`). Produces the **ground truth** consumed by Axes 3–4. No prior work in either
parent line has this.

**1. Automatic (comparability).** BERTScore F1/R/P (candidate vs tier-matched reference), BLEU/ROUGE
(overlap), STS *relevancy* (prompt↔output, higher better) and *diversity* (mean pairwise, lower =
more diverse), and **LSTM** fluency (P-MAGIC's metric — note it correlated **best** with teacher
judgment there, r = 0.628 vs BERT-F1 0.358). Report **per-tier** *and* **per-modality**, mirroring
P-MAGIC's ablation (text-image / text-graph / text-table; annotated vs non-annotated).

**2. Semi-automatic — MLLM-as-judge** *(Axis 4 + physics judging; the "semi-automatic" layer).*
A vision-capable model (mimo-v2.5) receives the **annotated frame(s) + figure + the gate's
ground-truth values as the reference**, and returns a per-criterion 1–5 score + one-line rationale
— the **VideoJudge** recipe (arXiv:2509.21451): frames + response + reference → numeric score +
explanation. **Bootstrap-calibrate** on a small set of teacher-verified items, then **validate the
judge's agreement with teachers** (Spearman/ICC) before trusting it at scale.

**3. Human.** N physics teachers score the **per-modality rubric** (P-MAGIC Table 2) on a 1–5 (or
1–10) Likert sheet — `build_rater_sheet.py` emits it from the *same* CRITERIA the LLM-judge uses, so
human and model score identical rows (precondition for ICC). P-MAGIC used 10 teachers / 150 items.

**4. Correlation & reliability.** `eval_stats.py`: **Cohen's κ** (inter-rater), **ICC(2,k)**
(human↔LLM), **Pearson r** (auto↔human). This is where the layered claim is earned — "automatic can
screen, teachers judge depth," as both P-MAGIC and VLM-QG conclude.

---

## Video-recognition-quality (the new sub-axis, our contribution)

**Why it is new.** Utami senses via AR-Core, P-MAGIC via a phone IMU bolted to the object — neither
recognises motion from *video*, so neither can (or does) evaluate recognition quality. Centri does,
and already computes the ground truth.

**How to score it.** Per tracked quantity (ω, a_c, r, T), correlation / error of the CV-measured
value against ground truth (cf. the pendulum r = 0.99 in the CV-tracking precedent). Framing and
robustness ideas from the video-understanding literature (action/motion benchmarks: Top-k,
Action-Score, MotionBench). The grounding gate's `measurement_quality.reliable` flag already marks
oblique-capture clips where per-instant recognition is untrustworthy — that flag becomes a reported
recognition-quality signal, not just an internal gate.

---

## Contribution ledger (what we adopt vs what is ours)

- **Adopted verbatim for comparability:** Utami Tables 8–9; P-MAGIC Table 2 (esp. the multimodal
  blocks); BERTScore / BLEU / STS / LSTM; κ / ICC / Pearson.
- **Centri's own:** the deterministic grounding gate (Axis 0); depth-based difficulty tiers grounded
  in Bloom + Cognitive Load Theory; the **video-recognition-quality** sub-axis; **annotation on
  video**; and the **MLLM-as-judge over annotated video frames** using gate ground truth as the
  reference.
