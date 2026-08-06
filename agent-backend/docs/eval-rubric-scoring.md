# Centri scoring rubric — what each score from 1 to 5 means

**Status: NEW 2026-08-06. This is the missing half of the evaluation instrument.**

`eval-rubric-ika.md` defines *what each criterion measures*. It has never defined *what a score
means*. Until today the complete scale definition, in all four places it appears
(`run_llm_judge.py:113`, `:151`, `eval-rubric-ika.md:20`, `eval-framework.md:24`), was:

> "Score each criterion 1–5 (5 = excellent)."

Nothing said what separates a 2 from a 4. This document supplies that, for every criterion on
every axis.

**Audience: teachers first.** It is written to be read on paper by a physics teacher with no
knowledge of the system's internals. The LLM judge is then given the *same* text, so that a human
score and a machine score mean the same thing and `ICC(human, LLM)` compares two readings of one
instrument rather than two different instruments.

---

## 0. Why this exists — read this before scoring

Two independent LLM raters scored the same 15 worksheets on the same criteria. On
`grounding_accuracy` they reached **κ = −0.07 with zero exact agreement on any worksheet.** The
cause was not that the material is ambiguous. It is that the two raters spent the scale
differently:

| score given | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| rater A (Qwen) | **6** | 3 | 1 | 0 | **5** |
| rater B (Claude) | 0 | 2 | 5 | **8** | 0 |

Rater A used the scale as a **detector** — "found a problem → 1, found none → 5", with almost
nothing in between. Rater B never once used 1 or 5. A's most common score is one B never gives;
B's most common is one A never gives, so exact agreement was close to impossible by construction.

That is what an unanchored scale produces, and it is what this document is for. The criteria were
never the problem; the numbers were.

**Where the ranges overlapped, agreement was fine** — `cognitive_demand` (A spans 2–5, B spans
3–5) reached **κ = 0.70**. Agreement tracks whether raters use the same part of the scale.

---

## 1. The scale

Every criterion is scored **1 to 5, whole numbers only**. The shape is the same everywhere:

| | meaning |
|---|---|
| **5** | No defect of this kind. A careful reader would find nothing to correct. |
| **4** | One borderline instance. Technically imperfect, but no reader is misled. |
| **3** | One clear defect, or several borderline ones. A reader notices, and is briefly confused. |
| **2** | Several clear defects, **or one that would actively mislead a student.** |
| **1** | Pervasive. The passage fails on this dimension; the defect is the dominant impression. |

Each criterion below overrides this with its own wording. **Where a criterion's own anchors
disagree with this general ladder, the criterion's anchors win.**

### Six rules that matter more than the anchors

1. **Score one criterion at a time.** A passage with wrong numbers can still be fluent. Do not let
   one bad property drag every row down — that is the single most common way agreement is lost.
2. **Use the whole scale.** If you never give a 1 or never give a 5, your scores cannot be
   compared with anyone else's. If nothing is wrong, 5 is the correct answer, not 4.
3. **A defect must be *in the passage*.** Grade only what is written and shown. Do not deduct for
   what you would have written instead, or for something you know about the clip but the reader
   cannot see.
4. **Severity, not count.** One defect that would teach a student something false is worse (2)
   than three cosmetic ones (3). Ask: *would a student come away with a wrong idea?*
5. **`n/a` is not a low score.** If a modality is absent — no table beside the passage — write
   `n/a`, never 1. A missing figure is not a bad figure. This applies to every Axis 4 row.
6. **Rounding is not an error.** "About 1 turn per second" for 6.68 rad/s (= 1.06 turns/s) is
   correct, stated at the precision the tier calls for. Deduct only when a rounded value would
   lead a student to a materially different answer.

### What these anchors are grounded in

Neither parent published level descriptors (§7), so the anchors below are ours. They are not
invented to taste — each design choice traces to something, and the choices are listed here so a
reviewer can attack them individually.

| choice | grounding |
|---|---|
| **Descriptive levels, not evaluative labels.** Every anchor says what the work *looks like* ("one relation does not close on its printed values"), never how good it is ("poor", "adequate"). | Brookhart (2013). "5 = excellent" is an evaluative label, and is precisely the instrument that failed here — it names a judgement without describing the evidence for it. |
| **Analytic, not holistic** — score each criterion separately (rule 1). | Brookhart (2013); Jonsson & Svingby (2007) find analytic scoring with descriptive criteria is where rubric reliability actually comes from. |
| **Five levels.** | Kept from Utami's 5-point rubric so Centri stays comparable within the parent line. Also sits inside the range where added levels stop buying discrimination and start costing agreement. |
| **Level 2 is the "would mislead a student" line**, not a count of defects (rule 4). | The unit being judged is *learning material*. A defect's cost is what a student takes away, so the anchor is pinned to consequence rather than frequency. This is also what separates the 4.91-vs-4.31 case (2) from three vague sentences (3). |
| **Every level-2 anchor names a defect this corpus actually shipped.** | The strongest grounding available to us: the thresholds are calibrated against real, inspectable artifacts — the non-closing ω²r, the "not turning" caption over 24 rad/s, the overlay 328 px off its object — not against hypothetical material. Each is reproducible from the workspaces. |
| **`n/a` for an absent modality** (rule 5). | Follows P-MAGIC's per-modality design: Table 2 rows are scored *per modality present*. Scoring a missing table as 1 would conflate "absent" with "bad" and silently depress the multimodal means. |
| **Report κ, not a difference of means.** | McHugh (2012), already the reference P-MAGIC cites; interpretation bands from Landis & Koch (1977). Our own data is the argument: on `grounding_accuracy` the two raters' means were 3.10 and 3.14 — near-identical — while κ was −0.04. A mean-only comparison would have reported perfect agreement on the criterion with none. |

**References**
- Brookhart, S. M. (2013). *How to Create and Use Rubrics for Formative Assessment and Grading.* ASCD.
- Jonsson, A., & Svingby, G. (2007). The use of scoring rubrics: Reliability, validity and educational consequences. *Educational Research Review*, 2(2), 130–144.
- Landis, J. R., & Koch, G. G. (1977). The measurement of observer agreement for categorical data. *Biometrics*, 33(1), 159–174.
- McHugh, M. L. (2012). Interrater reliability: the kappa statistic. *Biochemia Medica*, 22(3), 276–282.
- Utami, I. Q. (2025). Doctoral dissertation (Tables 8–10; 5-point rubric).
- Hwang et al. (2026). P-MAGIC. *Journal of Educational Computing Research* (Table 2; 25-item, 10-point rubric).

### Calibrating yourself before you start

Score these three real cases first and compare with the stated answer. If you disagree by more
than one point, re-read §1 before scoring anything else. They are drawn from defects the project
actually shipped.

| case | criterion | answer | why |
|---|---|---|---|
| A passage prints ω²r = **4.91** where 4.83² × 0.185 = **4.31**, then says the result matches the measurement. | `grounding_arithmetic` | **2** | The relation does not close on the numbers printed beside it. A student following the page gets a different answer from the page. Misleading → 2, not 1: every quantity is real and traces to the measurement. |
| The same passage, judged on where its numbers came from. | `grounding_provenance` | **5** | 4.91 *is* the measured mean of ω²r. Nothing is invented. **This is why the old combined criterion failed** — the two questions have different answers on the same text. |
| A worksheet figure marks the "centre of rotation" on a fan blade, 328 px from the hub, with the orbit circle running off the fan onto the desk. | `annotation_correctness` | **1** | The overlay points at the wrong object. Everything the figure asserts about where the motion is centred is false. |

---

## 2. Axis 0 — what the machine already checked

**Do not spend your attention here.** A deterministic gate runs before you see the passage and
already verified: every number traces to a measured value; banned vocabulary; arithmetic in worked
examples closes on its own printed factors; figure captions do not contradict their own curves.

It is reported to you as context, not for scoring. Its limits are worth knowing, because they are
exactly where your judgement is needed:

- It checks that a number **traces**. It cannot check that a **relation** stated in prose closes.
- It checks that a value came from the measurement. It cannot tell whether that value was the
  **right** one to quote at that point in the passage.
- It cannot see a figure. Every Axis 4 row is yours.

---

## 3. Axis 1 — Linguistic / authenticity
*(Utami Table 8 + P-MAGIC "Linguistic")*

### `motivating_context` — presents a meaningful, compelling purpose
- **5** — A real situation a student would recognise, and a reason to care that is not decoration.
- **4** — A real situation, but the reason to care is generic ("physics is everywhere").
- **3** — The context is present but inert: the scenario could be deleted without loss.
- **2** — The context is a thin wrapper on a bare calculation, or is invented rather than observed.
- **1** — No context, or one that contradicts the scenario shown in the figure.

### `language_clarity` — accessible at the target reading level
- **5** — Every term a student meets is either familiar or defined where it first appears.
- **4** — One undefined term, recoverable from context.
- **3** — Several undefined terms, **or** sentences long enough to need re-reading.
- **2** — The reading level is clearly above the tier; a student at this level would stall.
- **1** — Largely unreadable at this level: jargon, or internal system vocabulary left in.

> **Watch for the trap this project has already hit:** "plain words" is not "plain sentences". A
> basic-tier passage once used the simplest vocabulary in the corpus and was still the *hardest*
> to read, because its sentences were the longest. Judge sentence load, not word choice alone.

### `cognitive_demand` — appropriate level of cognitive challenge
*This is the criterion the tier claim rests on, and the best-agreed one (κ = 0.70). Score it
carefully.*
- **5** — Demands genuine reasoning: the reader must relate quantities, predict, or resolve a
  tension, not just receive statements.
- **4** — Mostly reasoning, with some stretches of pure exposition.
- **3** — Balanced: the reader follows a worked line of thought but is rarely asked to supply one.
- **2** — Almost entirely receptive; the reader is told, and never has to think.
- **1** — Recall only. Nothing is asked of the reader beyond reading.

> Judge the demand the passage **places on the reader**, not the difficulty of the physics.
> An advanced topic explained so thoroughly that nothing is left to do is *low* demand.

### `fluency` — grammatically correct, reads naturally
- **5** — Clean throughout.
- **4** — One or two slips that do not interrupt reading.
- **3** — Noticeable errors, or phrasing that reads as machine-generated.
- **2** — Frequent errors; the reader stumbles repeatedly.
- **1** — Broken text.

### `completeness` — includes the necessary context, conditions, detail
- **5** — A reader has everything needed; nothing essential is assumed.
- **4** — One minor omission a reader can infer.
- **3** — A needed condition or quantity is missing and must be guessed.
- **2** — Several gaps; the passage cannot be followed without outside information.
- **1** — Fragmentary.

---

## 4. Axis 2 — Structural / comprehension
*(slimmed from Utami Table 9 + P-MAGIC "Physics aspect")*

### `comprehension` — a learner at this level can follow it
- **5** — Follows on one reading.
- **4** — One passage needs re-reading.
- **3** — Several places need re-reading, or the order of ideas fights the reader.
- **2** — A learner at this level would need help to get through it.
- **1** — Not followable at this level.

### `structure_clarity` — logical flow; how information and ideas relate is visible
- **5** — Each step follows from the last; the reader always knows why they are being told this.
- **4** — One abrupt transition.
- **3** — The order is defensible but unsignposted; the reader assembles the logic themselves.
- **2** — Ideas arrive out of order, or a conclusion precedes what it rests on.
- **1** — No discernible structure.

### `concept_accuracy` — the physics is correct
- **5** — Correct throughout, including the informal phrasings.
- **4** — A simplification that is imprecise but not wrong at this level.
- **3** — One statement that is loose enough to be misread (e.g. speed and velocity used
  interchangeably where the distinction matters).
- **2** — **A statement that would install a misconception** — centripetal acceleration described
  as pushing outward; "not turning" said of a moving object.
- **1** — Multiple conceptual errors, or the passage's central claim is wrong.

> This is a **severity** criterion. One misconception outweighs three vague sentences.

### `realistic` — the scenario and quantities are physically plausible
- **5** — Scenario and every quantity are plausible for the object shown.
- **4** — Plausible, but a quantity is quoted more precisely than the situation supports.
- **3** — One quantity is implausible for the object, though not impossible.
- **2** — A quantity is physically implausible, or the scenario could not have produced it.
- **1** — The scenario is impossible, or contradicts the video it claims to describe.

### `variable_name_consistency` — standard, consistent notation
- **5** — Standard symbols (ω, a_c, r, T, v), used consistently, defined at first use.
- **4** — Standard and consistent, but one symbol is never defined.
- **3** — One symbol changes meaning or form partway through, **or** a quantity is named in words
  where the tier expects a symbol.
- **2** — Several inconsistencies, or a symbol conflicts with standard use (a for a_c).
- **1** — Notation is arbitrary.

> Basic tier is deliberately allowed to avoid symbols. Do **not** deduct for words instead of
> symbols at basic; deduct only for *inconsistency*.

---

## 5. Axis 3 — Physics / tier
*(Centri's own — neither parent evaluates a tiered passage measured from video)*

### `difficulty_fit` — depth matches the asserted tier
The tier is stated on the sheet. Score against **that** tier, not against your preference.

- **basic** = no equations, one idea at a time.
- **intermediate** = coordinates a few relations, with numbers.
- **advanced** = integrates change over time, limits, proportionality.

- **5** — Sits squarely in its tier.
- **4** — In tier, with one element from the tier above or below.
- **3** — Straddles two tiers; a reader could not tell which it was written for.
- **2** — Clearly in the wrong tier — equations at basic; single-step arithmetic at advanced.
- **1** — Bears no relation to the asserted tier.

### `achieved_bloom` — *not a 1–5 score*
Record the **single** Bloom level the passage actually reaches: Remember, Understand, Apply,
Analyze, Evaluate, Create. Record what it *reaches*, not what it aims at.

### `grounding_provenance` — do the numbers come from the measurement?
*The measured values are printed on your sheet. Compare against them.*
- **5** — Every quantity traces to a measured value, at a sensible precision.
- **4** — All quantities trace; one is rounded harder than the tier needs.
- **3** — A quantity is stated whose origin is unclear, though it is plausible.
- **2** — **Two different moments of the clip are conflated as one** (an initial period quoted
  beside an average rate, with nothing marking them as different moments), or a quantity does not
  match any measured value.
- **1** — Quantities are invented, or contradict the measurement.

### `grounding_arithmetic` — does the arithmetic printed beside them close?
*Check the numbers **as printed on the page**, using only the factors the page shows.*
- **5** — Every relation closes on its own printed values.
- **4** — Closes once rounding is taken into account, and the rounding is stated or obvious.
- **3** — A relation closes only approximately, with no acknowledgement — a student checking it
  would find a small discrepancy.
- **2** — **A relation does not close** on the values printed beside it, and the text asserts it
  does. (The 4.91-vs-4.31 case in §1.)
- **1** — Multiple relations fail, or a result is asserted with no derivation that supports it.

> **These two were one criterion until 2026-08-06**, worded "numbers and described figures are
> internally consistent and match the measured values". That sentence asks two questions, and on
> real material they get different answers — which is how two raters reached κ = −0.07 while both
> being defensible. **Score them separately. Never average them.**

---

## 6. Axis 4 — Multimodal
*(P-MAGIC Table 2, plus one Centri row)*

**Score from the rendered figures in the PDF, not from the text.** If a modality is absent, write
**`n/a`** — never 1. Rule 5 in §1 exists because a missing table has been scored as a bad table.

### Image–text

**`image_precision`** — the prose refers to the image accurately and clearly
- **5** — Every reference to the image is accurate and locatable.
- **4** — Accurate, but one reference is vague ("as shown").
- **3** — A reference is hard to match to anything in the image.
- **2** — A reference describes something the image does not show.
- **1** — The prose describes a different image.

**`image_relevancy`** — the image supports the passage's concept
- **5** — The image carries information the prose needs.
- **4** — Supportive but partly decorative.
- **3** — Decorative; removing it costs nothing.
- **2** — Distracting or off-topic.
- **1** — Contradicts the passage.

### Text–graph

**`graph_accuracy_labeling`** — plots the data correctly; axes labelled with the right quantities and units
- **5** — Correct data, both axes labelled with quantity **and** unit.
- **4** — Correct data; one unit missing.
- **3** — Correct data; labels incomplete or ambiguous.
- **2** — A label names the wrong quantity, or a unit is wrong.
- **1** — The plotted data does not match the measurement.

**`graph_scale_proportions`** — appropriate scale, even intervals matching the data range
- **5** — Range and intervals suit the data; the phenomenon is visible.
- **4** — Slightly compressed or stretched.
- **3** — Scale obscures the feature under discussion.
- **2** — Uneven intervals, or a range that misrepresents the trend.
- **1** — The scale makes the graph unreadable or actively misleading.

**`graph_sense_physical`** — conclusions drawn from the graph are physically sound
- **5** — Every claim about the curve is physically correct.
- **4** — Correct, with one over-general statement.
- **3** — A claim is unsupported by the curve shown.
- **2** — **A claim contradicts the curve beneath it** — a band captioned "not turning" containing
  samples at 24 rad/s.
- **1** — The physics read off the graph is wrong throughout.

**`graph_relevancy`** — axis titles and values align with the text
- **5** — Graph and text use the same quantities, symbols and values.
- **4** — Aligned; one symbol differs in form.
- **3** — The reader must work to connect graph and text.
- **2** — Values in the graph disagree with values in the text.
- **1** — The graph belongs to a different passage.

### Text–table

**`table_labels_scales`** — rows/columns clearly labelled with quantities and units
- **5** — Every row and column labelled with quantity and unit, readable.
- **4** — One unit missing.
- **3** — Labels present but ambiguous.
- **2** — A label names the wrong quantity or unit.
- **1** — Unlabelled.

**`table_proportional_reasoning`** — supports proportional/predictive reasoning between variables
- **5** — The layout makes a relationship visible and invites prediction.
- **4** — The relationship is present but must be sought.
- **3** — A list of values; no relationship supported.
- **2** — The arrangement obscures a relationship that exists in the data.
- **1** — Suggests a relationship the data does not support.

**`table_physics_connection`** — connects to physics concepts and real context
- **5** — Each column is tied to a concept and to the observed situation.
- **4** — Tied to concepts; the real context is implicit.
- **3** — Numbers only; the connection is left to the reader.
- **2** — The connection asserted is not the one the numbers show.
- **1** — No physical meaning.

**`table_relevancy`** — column titles and values align with the text
- **5** — Table and text agree throughout.
- **4** — Agree; one heading is phrased differently.
- **3** — The reader must reconcile table and text.
- **2** — A value in the table disagrees with the text.
- **1** — The table belongs to a different passage.

### On video

**`annotation_correctness`** — the overlays point at the right object and read the right value,
**across the motion**
*This is Centri's own row and the one claim no comparable system makes. Score it hardest.*
- **5** — Every overlay sits on the object it labels and reads the right value, in every frame
  checked.
- **4** — Correct throughout; one label is placed awkwardly but unambiguously.
- **3** — An overlay is ambiguous — an arrow whose base could be either of two points.
- **2** — An overlay reads a wrong value, or drifts off its object during the motion while being
  correct at the start.
- **1** — **An overlay is attached to the wrong object** — a "centre of rotation" marked on a fan
  blade rather than the hub; an orbit circle that does not pass through the tracked marker; an
  overlay still drawn after the object has left the frame.

> **Check more than the first frame.** The defect this row exists to catch was invisible in a
> still: the geometry was self-consistent and every number correct, and only the *position*
> against the video was wrong. If you are given sampled frames, check the last as well as the
> first.

---

## 7. Provenance — what is inherited and what is new

| part | source |
|---|---|
| Axis 1 criteria | Utami (2025) Table 8 |
| Axis 2 criteria | Utami Table 9 + P-MAGIC Table 2 "Physics aspect" |
| Axis 4 criteria | P-MAGIC Table 2, ≈verbatim, with its citations (Otani et al. 2023; Stefanel 2019) |
| Axis 3, `annotation_correctness`, Axis 0 | Centri's own |
| **All 1–5 anchors in this document** | **Centri's own — neither parent published level descriptors.** |

That last row is the finding behind this document, and it should be stated in the paper rather
than glossed. Both parents describe their rubric by its *criteria*:

- **Utami** used "a 5-point rubric **derived from the criteria** outlined in Table 8, Table 9, and
  Table 10" (p. 46). Tables 8–10 give Item + Definition. No level descriptors; the appendices are
  the pre-test, post-test, questionnaire, and MWP examples.
- **P-MAGIC** teachers used "a 25-item rubric with a **10-point Likert scale**" (p. 23). Table 2
  gives Dimension / Criteria / Reference / Description. No level descriptors.

**The two parents do not even share a scale** — Utami is 5-point, P-MAGIC is 10-point, and Centri
is 5-point. There was no anchor set to inherit.

**⚠ Comparability:** because of that, a Centri mean on 1–5 is **not** comparable with a P-MAGIC
mean on 1–10, and rescaling one into the other would be inventing precision. Compare *orderings*
and *agreement statistics*, and state the scale wherever a mean from either study is quoted.

**Why P-MAGIC reached κ = 0.76 without anchors, and why we cannot:** its ten raters were senior
physics teachers who routinely write assessments — a shared professional frame that supplies
anchors implicitly. Two unrelated language models share no such frame, and neither will a panel
recruited on different terms. Their κ is evidence about their rater pool, not evidence that
anchors are unnecessary.

---

## 8. Using this with the LLM judge

The judge must be given **this document's anchors**, not a bare "5 = excellent", or human and
machine scores are not measuring the same thing and `ICC(human, LLM)` means nothing.

Not yet wired up — `run_llm_judge.py` still carries the one-line rubric and a single combined
`grounding_accuracy`. To adopt:

1. Inject the §3–§6 anchors into `run_llm_judge.py`'s `SYSTEM` and `MULTIMODAL_SYSTEM`.
2. Replace `grounding_accuracy` with `grounding_provenance` + `grounding_arithmetic` in `AXES`
   (this changes the criterion count from 12 to 13, and every stored result).
3. Point `build_rater_sheet.py` at this file rather than `eval-rubric-ika.md`, which defines
   criteria but not scores.
4. **Re-run both judges on the frozen prompts and compare κ before and after.** Only the anchors
   change; everything else stays byte-identical. That is a clean measurement of whether anchoring
   is what was missing — and it is worth doing *before* any teacher time is spent, because if κ
   does not move, the problem is not the anchors and the panel would be spent finding that out.

**Do not re-scale or re-map any historical score to this rubric.** Scores collected under
"5 = excellent" were produced against a different instrument; they must be re-run, not adjusted.
