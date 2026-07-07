# Centri evaluation rubric — adapted from Utami (2025)

Single source of truth for the human-rater sheet (`tools/build_rater_sheet.py`) and the
LLM-as-judge (`tools/run_llm_judge.py`). Adopting the parent line's rubric verbatim lets Centri's
numbers sit directly beside the lab's published ones.

> **Source:** Ika Qutsiati Utami, *Authentic MWP Generation using Generative AI with
> Contextualization, Personalization, and Socialization*, PhD dissertation, National Central
> University (advisor Prof. Wu-Yuin Hwang), Oct 2025. Rubric tables §3.4.2 (Tables 8–10);
> Study-2 rubric §3.2.4; BLEU interpretation §3.2.4; evaluation procedure §3.4.3.

Her unit is a *math word problem* (text-vs-text); Centri's unit is a **learning-material passage**
across three tiers (basic / intermediate / advanced). We keep her dimensions verbatim and add a
small physics/tier extension block. Every dimension is scored **1–5** (5 = excellent).

---

## Axis 1 — Authenticity & linguistic (her Table 8, verbatim)

| Dimension | Definition (verbatim) |
|---|---|
| Use of a motivating and engaging context | Each problem presents a meaningful and compelling purpose. |
| Clarity in language and cultural context | Each problem incorporates language and terminology that make it accessible to the reading level of target students. |
| An appropriate number of solution steps to promote reasoning | Each problem requires more than one step to arrive at a solution. |
| A variety of solution strategies | Each problem supports the use of multiple strategies to arrive at a solution. |
| Attention to cognitive demand | Each problem presents an appropriate level of cognitive challenge. |

## Axis 2 — Mathematical (her Table 9, verbatim)

| Dimension | Definition (verbatim) |
|---|---|
| Problem answerability | The problem must have at least one valid solution. The necessary information must be provided without ambiguity. The problem should not have redundant or misleading data unless it is intentional for critical thinking. |
| Problem structure and clarity | The logical flow should allow students to understand the relationship between the given information and the required solution. |
| Multiple solution strategies | Allow multiple methods for solving, encouraging creativity, and being valuable for developing mathematical thinking. |

> **Table 10 (social-cognitive / socialization) is intentionally NOT adopted** — it is Utami's
> Study-4 novel contribution and outside Centri's lane (takeaways doc §5, decision #5).

---

## Axis 3 — Centri physics/tier extension (ours, on top of hers)

These are Centri-specific because our unit is a tiered physics passage measured from video, which
her geometry/AR line does not have. They keep the "our use case" optimization explicit.

| Dimension | Definition |
|---|---|
| difficulty_fit | Does the depth match the asserted tier? **basic** = no equations, one idea at a time; **intermediate** = coordinates a few relations with numbers; **advanced** = integrates change-over-time, limits, proportionality. |
| concept_accuracy | Physics is correct — no misconceptions, relations right. |
| grounding_accuracy | Numbers/figures are internally consistent and match the measured seed values (the semantic complement to the deterministic grounding gate). |
| achieved_bloom | The single Bloom level the passage actually reaches: Remember, Understand, Apply, Analyze, Evaluate, Create. Compared against the tier's asserted Bloom target from the difficulty gate. |

The deterministic gate (`grade_material_grounding.py`, `grade_material_difficulty.py`,
`material_gate.py`) is a **fourth, zero-cost intrinsic axis** Utami does not have — it runs first
and feeds EI/Bloom ground-truth into Axis 3.

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
