# Centri evaluation rubric — reconciled from Utami (2025) + P-MAGIC (2026)

Single source of truth for the human-rater sheet (`tools/build_rater_sheet.py`) and the
LLM-as-judge (`tools/run_llm_judge.py`). Adopting the parent line's rubric rows verbatim lets
Centri's numbers sit directly beside the lab's published ones. The full method (layers, stats,
video-recognition sub-axis, MLLM-judge) is in **`eval-framework.md`**; this file is just the scored
rows.

> **Sources:**
> - Ika Qutsiati Utami, *Authentic MWP Generation using Generative AI with Contextualization,
>   Personalization, and Socialization*, PhD dissertation, NCU (advisor Prof. Wu-Yuin Hwang), Oct
>   2025. Tables 8–10 §3.4.2; Study-2 §3.2.4; BLEU §3.2.4; procedure §3.4.3.
> - **P-MAGIC** — Hwang, Sari, Purba, Azhar, *J. Educational Computing Research* 2026
>   (`document-4.pdf`). **Table 2** — a human rubric organised **by modality** (linguistic, physics,
>   image-text, text-graph, text-table); the multimodal blocks are the source for **Axis 4**.

Their unit is a *word problem*; Centri's unit is a **learning-material passage** across three tiers
(basic / intermediate / advanced) **plus its annotated figures**. So we **keep the linguistic and
multimodal rows verbatim**, **drop the problem-only rows** (a passage has no "answer"), and **add**
Centri's physics/tier + video-recognition rows. Every dimension is scored **1–5** (5 = excellent).

---

## Axis 1 — Linguistic / authenticity (Utami Table 8 + P-MAGIC "Linguistic")

| Dimension | Definition | Source |
|---|---|---|
| motivating_context | Presents a meaningful and compelling purpose. | Utami Table 8 |
| language_clarity | Language/terminology accessible to the target reading level. | Utami Table 8 / P-MAGIC |
| cognitive_demand | An appropriate level of cognitive challenge (a strong tier signal). | Utami Table 8 |
| fluency | Grammatically correct and reads naturally. | P-MAGIC |
| completeness | Includes the necessary context, conditions, and detail. | P-MAGIC |

> **Dropped as problem-only:** *appropriate # of solution steps*, *variety of solution strategies*
> — both assume a task to solve. Kept the authenticity + reading-level rows that fit exposition.

## Axis 2 — Structural / comprehension (slimmed from Utami Table 9 + P-MAGIC "Physics aspect")

Our unit is **exposition, not a task**, so the problem-only rows are dropped and the transferable
structural/physics rows kept.

| Dimension | Definition | Source |
|---|---|---|
| comprehension | The passage is understandable at its target reading level; a learner can follow it. | ours / P-MAGIC "linguistic complexity" |
| structure_clarity | Logical flow — the reader sees how the given information and the ideas relate. | Utami Table 9 |
| concept_accuracy | Physics is correct — no misconceptions, relations right. | P-MAGIC "concept understanding" |
| realistic | The scenario/quantities are physically plausible and tied to a real situation. | P-MAGIC "realistic" |
| variable_name_consistency | Symbols/notation used consistently and to standard (ω for angular velocity, a_c, …). | P-MAGIC "variable's name consistency" |

> **Dropped as problem-only** (no "answer" in an exposition passage): *problem answerability*,
> *solvability*, *multiple solution strategies*. This retires the "expository-unfair" caveat from
> the 07-08 deck by construction.
>
> **Utami Table 10 (socialization) remains NOT adopted** — her Study-4 contribution, outside
> Centri's lane (takeaways doc §5, decision #5).

---

## Axis 3 — Physics / tier + recognition (Centri's own)

Centri-specific because our unit is a **tiered physics passage measured from video**, which neither
parent (Utami = AR, P-MAGIC = phone IMU) has.

| Dimension | Definition |
|---|---|
| difficulty_fit | Does the depth match the asserted tier? **basic** = no equations, one idea at a time; **intermediate** = coordinates a few relations with numbers; **advanced** = integrates change-over-time, limits, proportionality. |
| achieved_bloom | The single Bloom level the passage actually reaches (Remember … Create), compared against the tier's asserted Bloom target from the difficulty gate. |
| grounding_accuracy | Numbers/figures are internally consistent and match the measured seed values (the semantic complement to the deterministic grounding gate). |
| **video_recognition_quality** *(NEW)* | How well the CV-measured kinematics (ω, a_c, r, T) match ground truth — correlation/error vs the seed, plus the gate's `measurement_quality.reliable` flag for oblique-capture clips. Neither parent can score this; we can, because we compute the ground truth. |

**Axis 0 — the deterministic gate** (`material_gate.py`, `grade_material_difficulty.py`) is a
**zero-cost intrinsic layer** neither parent has — it runs first and feeds EI/Bloom/number
ground-truth into Axes 3–4.

---

## Axis 4 — Multimodal (adopted ≈verbatim from P-MAGIC Table 2 + one Centri row)

Scored per modality present beside the passage. Rows and citations are P-MAGIC's; the last is ours.

| Modality | Dimension | Definition | Source |
|---|---|---|---|
| Image–text | precision | The prose refers to the image accurately and clearly. | Otani et al. 2023 |
| Image–text | relevancy | The image supports the passage's concept/objective. | Otani et al. 2023 |
| Text–graph | graph_accuracy_labeling | Graph plots the data correctly; axes labelled with the right quantities and units. | Stefanel 2019 |
| Text–graph | scale_proportions | Appropriate scale, evenly spaced intervals matching the data range. | Stefanel 2019 |
| Text–graph | graph_sense_physical | Conclusions from the graph are consistent with physical principles. | Stefanel 2019 |
| Text–graph | relevancy | Axis titles/values in the graph align with the text. | Stefanel 2019 |
| Text–table | clear_labels_scales | Each row/column clearly labelled with quantities + units; readable scale. | Stefanel 2019 |
| Text–table | proportional_reasoning | The table supports proportional/predictive reasoning between variables. | Stefanel 2019 |
| Text–table | physics_connection | The table connects to fundamental physics concepts and real-world context. | Stefanel 2019 |
| Text–table | relevancy | Column titles/values align with and support the text. | Stefanel 2019 |
| **On video** | **annotation_correctness** *(NEW)* | The per-frame overlays (radius, ω, angle-swept / degrees-per-second) point at the right object and read the right value — annotation *across the motion*, not one still image. | ours |

> Scored by the human panel **and** the semi-automatic MLLM-as-judge (vision model, gate ground
> truth as reference) — see `eval-framework.md` §"measurement layers". Report per-modality, and
> annotated-vs-non-annotated, mirroring P-MAGIC's ablation.

---

## Study-2 linguistic/mathematical sub-criteria (reference, §3.2.4)

Her earlier Study-2 rubric (kept for lineage; Tables 8–9 supersede it as the scored rubric):
- **Linguistic**: relevance, language fluency, language comprehensibility, linguistic complexity,
  completeness.
- **Mathematical**: answerability (solvability + #corrections), mathematical applicability,
  difficulty level, realistic level.

## Automatic metrics (comparability with the lab)

- **BERTScore** (precision/recall/F1) — the headline auto metric, candidate vs tier-matched
  reference. Already emitted by `run_material_eval.py` / `run_multi_reference_eval.py`.
- **BLEU** (n-gram precision) + **ROUGE** — complementary overlap columns.
- **STS** two ways: *relevancy* (input prompt vs output, higher = better) and *diversity* (mean
  pairwise STS across the generated set, **lower = more diverse**).

**BLEU interpretation scale (her §3.2.4, reported on her 0–6+ presentation scale):**

| BLEU | Interpretation |
|---|---|
| <1.0 | Undesired outcome |
| 1.0–1.9 | Difficult to obtain the gist |
| 2.0–2.9 | Gist clear, but significant grammatical errors |
| 3.0–4.0 | Understandable to good |
| 4.0–5.0 | High quality |
| 5.0–6.0 | Very high quality, adequate, fluent |
| >6.0 | Often better than human |

## Correlation & reliability statistics (§3.4.3, computed by `tools/eval_stats.py`)

- **Cohen's κ + % agreement** — inter-rater reliability across human raters.
- **ICC** (Intraclass Correlation Coefficient) — human-vs-LLM agreement; her Study-4 reports
  per-dimension ICC (values ICC > 0.75 read as high agreement).
- **Pearson r** — correlation between automatic scores and human scores (her Study-2 RQ3).

Scale of her studies for reference: Study 2 = 10 teachers / 200 problems; Study 4 = 5 teachers.
