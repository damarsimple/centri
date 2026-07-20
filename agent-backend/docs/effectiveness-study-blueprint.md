# Centri effectiveness-study blueprint — adapted from Utami Study 3

Centri's biggest evaluation gap is an effectiveness study (does the generated material actually
improve learning?). Utami's Study 3 is a ready-made, teacher-approved, publishable quasi-experiment
we adapt rather than invent. This doc is the **design spec** — no study is run this week; the point
is to fix the design (and the app instrumentation it requires) before we build.

> Source: Utami (2025) §3.3, Figs 13–14, Tables 3–6.

## Her design (the template)

- **Participants:** 51 fifth-graders (after 1 dropout), two classes, **EG vs CG**, ~26 each,
  different teachers (>10 yrs experience), mean age 10.5.
- **Procedure (6 weeks):** Wk1 train on the app; Wk2 **pre-test** (teacher-validated, 8 open-ended
  items in 3 categories); Wk3–5 learning (EG uses the system with contextual/personalized MWPs;
  CG uses textbook MWPs); Wk6 **post-test** + questionnaire + interviews.
- **Instruments:** pre/post word-problem tests (different items, matched difficulty, to block
  memorization); **TAM questionnaire** (5 subscales — perceived ease of use, usefulness,
  playfulness, intention, attitude; 15 items, 5-point Likert; validity via CVR > 0.79, reliability
  via Cronbach's α; from Hwang et al. 2020); structured interviews (10 students, 5 high / 5 low
  achievement).
- **Analysis:** normality check → parametric; One-Way ANOVA (group means), **ANCOVA on post-test
  with pre-test as covariate** (the key bias-reducing move), Pearson (behavior ↔ performance),
  **stepwise regression** for the strongest predictor of learning performance; qualitative
  narrative analysis of interviews.

## How Centri maps onto it

- **EG** = Centri-generated tiered physics material; **CG** = textbook circular-motion problems.
- **Pre/post** = physics problem-solving items (matched difficulty), teacher-validated.
- **Analysis:** replicate ANCOVA(pre-test covariate) + Pearson + stepwise regression; add
  **per-tier scores** (basic / intermediate / advanced) as the per-category analogue of her
  single-shape / comparison / compound breakdown (her Table 6).
- **TAM:** reuse her questionnaire verbatim (same Hwang lineage) so acceptance numbers are
  comparable.
- **Stats reuse:** ANCOVA/ANOVA/Pearson/stepwise are standard; `tools/eval_stats.py` already
  covers Pearson and can host the correlation/regression helpers when we get there.

## App instrumentation to add (so the behavior analysis is possible)

Her Tables 3–5 log learning-behavior variables; Centri's app must record the analogues **before**
the study, or the behavior↔performance analysis is impossible retroactively. Minimum log schema:

| Variable (her analogue) | What Centri logs |
|---|---|
| Problem-context understanding | per-item time-on-task, replays of the source video |
| Identifying contextual info | which measured quantities the student references in their working |
| Visual-schematic representation (quantity & quality, per difficulty level) | whiteboard/annotation strokes + a rubric score, tagged by tier |
| Math-concept application | formula/relation used vs the tier's target relation |
| Solution agreeability | self-check / correctness against the seeded answer |
| Reflection on past learning / on analytics | opens of the reflection & analytics views, dwell time |
| Performance (her Table 6) | total score + **per-tier** (basic/intermediate/advanced) subscores |

Emit per-student, per-item, per-tier rows (JSON/CSV) so they drop straight into the ANCOVA/Pearson
pipeline. The app already has an annotate/whiteboard analogue to hang the schematic-representation
logging on.

## Sequencing

This is a **later, resource-heavy push** (needs students + teachers + IRB/consent). This week's
job is only to commit this design so, when we build the instrumentation, it already targets the
variables the analysis needs. Precondition: the human-rater rubric pipeline
(`build_rater_sheet.py` → `eval_stats.py`) is validated first (next week's teacher deployment).
