# Centri — TODO

Opened **2026-08-03** from a critical review of the project done while drafting the IEEE paper
(`paper/centri-ieee.tex`). Companion to `SESSION_CHECKPOINT.md`: the checkpoint records *state*,
this file records *what to do about it*.

**Tags:** `[D]` needs Damar (reshoot, hardware, judgement, people) · `[C]` Claude can do it
· `[DC]` needs both. **Effort:** S = under an hour · M = a few hours · L = a day or more.

> **§7 holds an independent critique of the *paper*** (verdict: weak reject, recoverable);
> the full review is at `paper/REVIEW-2026-08-03.md`. §1.5 is done.

---

> **Progress 2026-08-03 (Claude).** Applied to `paper/centri-ieee.tex`, which recompiles clean:
> §1.1 EI reframed as a conformance check with cognitive demand promoted · §1.2 the three tracking
> modes disclosed in a new table · §1.3/§7.3 annotation downgraded to *frame* annotation and the
> score-against-the-seed limit stated · **§1.4/§7.2 the gyro comparison RE-RUN on both workspaces**
> (new `agent-backend/tools/gyro_compare.py`) · §2.3 n=18 reported · §7.1 the false two-raters claim
> rewritten · §7.4–7.6, §7.9–7.16 all applied. Paper is **13 pp** — still over any IEEE limit; the
> remaining cut is a venue-dependent judgement call. Untouched: §1.2/§1.3 `[D]` decisions, §2.2
> defect injection, §3.1–3.2, §4, §5, §7.8 output figure.

## 0. The one-paragraph summary

Four claims the project currently makes do not survive checking, and all four are in the paper
draft. In severity order: the difficulty ladder is **enforced, not measured**; two of seven clips
have **no measured trajectory**; the video-annotation contribution was **evaluated on still
frames**; and the sensor validation describes a **different workspace** from the one that produced
every other number. None of these are fatal to the project — each has an honest reframing that
costs a smaller claim — but all four must be settled before the paper goes anywhere.

> **Status 2026-08-06.** Two of the four are settled. The synthesized-orbit clips are **gone**
> (§1.2: corpus re-shot and fully regenerated, now **5 clips / 15 worksheets**), and the difficulty
> claim now rests on **cognitive demand**, which rises for both raters and is their best-agreed
> criterion (§1.1). Two remain, and one got worse: the annotation contribution is still scored on
> still frames and **Axis 4 was not re-run** (§1.3), and withdrawing `turntable-3` removed the only
> sensor-validated clip, so §1.4 is no longer "the wrong workspace" but **no workspace at all**.

---

## 1. BLOCKING — claims that are wrong as stated

### 1.1 `[C]` `S` — The element-interactivity ladder is circular
**Verified.** `material_gate.cross_tier_issues()` emits
`"element interactivity not rising: ..."`, and `material_tiers.main()` **regenerates the implicated
tier** when it fires (`_implicated_tiers` has a dedicated branch: *"EI monotonicity: fix the tier
that's too low"*). On top of that, `ei_score()` counts *distinct quantities + relations*, and the
tier spec **defines** tiers by which quantities and relations they may use — basic is forbidden
equations, so its relation count is structurally ~0.

So **"EI rises on 7/7 clips" is a conformance check, not a measurement.** The pipeline requires the
ladder and re-rolls until it has one.

- [x] Reframe in the paper: EI = *the generator met its spec*, not *the tiers are harder*.
- [x] Promote **cognitive demand** to carry the difficulty claim — it rises for **both** judges
      (**2.80→3.60→4.80** and **3.00→3.20→4.20** on the current 5-clip corpus; the 7-clip figures
      were 2.86→3.86→4.71 and 2.43→2.86→4.14) and is their best-agreed criterion
      (**κ = 0.70, r = 0.80**, up from 0.59). That is
      genuine independent evidence; EI is not.
- [ ] Optional stronger fix: report EI **as generated, before cross-tier regeneration**, which
      would be a real measurement. Requires logging the pre-regen passage — currently discarded.

### 1.2 `[DC]` `M` — Two of seven clips have a synthesized orbit
**Verified from the sidecars.**

| tracking mode | clips | what it measures |
|---|---|---|
| `object` (the promptable tracker) | roundabout-4046, turntable-1, turntable-2, ~~turntable-3~~ *(withdrawn 08-06)* | **3** — real trajectory |
| `color` (classical HSV) | computerfan-4029, **fan-4656** *(new 08-06)* | **2** — real trajectory |
| ~~`frequency` (blade-pass FFT)~~ | ~~fan-4027, fan-4028~~ — **parked 08-06** | **0** — was rate only, orbit synthesized |

The fans have no tracked point. Their "trajectory" is manufactured from a rate, then drawn on the
frame as an annotation and used to build six worksheets. `frequency` mode also has a known
**~1.0 rad/s floor** that reports spinning while the object is at rest.

- [x] `[C]` Disclose the three modes in the paper with this table. Not disclosing it is the kind
      of omission that ends a review badly.
- [x] `[D]` Decide: do the fans stay in the corpus? **RESOLVED 2026-08-06 — option (c), re-shot.**
      Damar filmed a yellow card marker on one blade. `fan-4027` and `fan-4028` are parked in
      `templates-reshoot/`; `templates/base-template-fan-4656` replaces both, tracking in
      **`color`** mode (not `object` — SAM3 was unreachable and colour wins on this footage).
      **99.99% coverage, 100% of detections on-orbit, zero jumps, 190.8 revolutions**, and ω
      agrees with an independent blade-pass measurement to **<1%** on every steady window.
      Evidence: `templates/base-template-fan-4656/NOTES.md`.
- [x] `[D]` If re-shooting: a flat high-contrast marker on one blade. **Done** — and the rate
      floor is now measured rather than asserted: on the stationary tail the marker track reads
      **0.016 rad/s** where a blade-pass FFT on the same frames reports **4.69**.
- [x] `[C]` **Regenerate the corpus. DONE 2026-08-06.** The corpus is **5 clips / 15 worksheets**
      (`roundabout-4046`, `computerfan-4029-2`, `turntable-1`, `turntable-2`, `fan4656final`) —
      not 6: `turntable-3` was withdrawn as well. Worksheets, judge means, BERTScore, the EI
      ladder and κ are all re-derived from scratch, none rescaled. Gate **11/15**.
      **The one exception is Axis 4, which was NOT re-run** — the paper's multimodal table still
      carries the old 7-clip scoring. That is now the only stale aggregate; see §1.3.
- [x] `[D]` **The ruler. RESOLVED 2026-08-06 — no re-shoot needed.** The card lies *along* the
      blade and ends at the tip, so it measures itself: fitting the hub-to-near-edge span (31 cm /
      190.5 px) together with the card length (25 cm / 139.0 px) gives **px_per_m 591**, and the
      hub-to-card-centre radius **0.44 m / 260.0 px**. The earlier 38% disagreement was a reading
      error — "distance to the marker" is ambiguous once the marker is bigger than a point, and
      31 cm is its *near edge*, not its centre. Taking it as the centre would have made every
      distance 29% too small. **Open sub-item:** the blade tip is *predicted* at ≈54 cm (319.3 px);
      51 cm would make the 25 cm card measure 22.2 cm in the same frame. One tape measurement
      settles it.

### 1.3 `[DC]` `M` — The video-annotation contribution was never evaluated
**Verified.** `tools/export_multimodal_prompts.py` feeds the rater `annotated_image.png` /
`annotated_image_basic.png`, and declares `VIDEO_MODALITY_NEEDS = "image"` with the comment
*"The annotated frame carries the overlays."* **`annotated_video.mp4` was never scored.**

So `annotation_correctness = 4.29–4.43`, the strongest row in the whole evaluation and the row the
"annotation across the motion" claim rests on, describes a **still frame** — exactly what P-MAGIC
also produces. The evaluation does not test the differentiator.

- [ ] `[C]` Either score the annotated video (sample N frames across the motion, ask whether the
      overlay tracks the object *and stays correct as it moves*), or
- [x] `[C]` Stop calling it evidence for video annotation and downgrade the claim to *frame*
      annotation, which is honest and still fine.
- [ ] `[D]` Judgement call: which of those two. Scoring the video properly is the stronger paper.

**2026-08-06 — this stopped being hypothetical.** `computerfan-4029-2` shipped every overlay
drawn one crop offset ($328$\,px) low: the "centre of rotation" sat on a fan blade and the orbit
ran onto the desk, in `annotated_image_basic.png` — the still frame the rater *is* given — and in
the video. It was found by opening the video by hand, not by any check we own
(tech report §`sec:cropbounds`; fixed in `contract.py`, physics unaffected).

Two things follow, and they cut in opposite directions:
- A rater looking at that frame should have scored `annotation_correctness` on the floor. The
  scored corpus used the OLD `job_computerfan-4029`, which is correctly registered, so the
  evaluation never saw it — the 4.29–4.43 row is not evidence that this class gets caught.
- It is now concrete that a *still* frame is enough to expose this defect. Scoring the video is
  still the stronger claim, but "the rater would have caught it from one frame" is defensible,
  which lowers the cost of the honest downgrade already taken above.
- [ ] `[C]` When Axis 4 is re-run on the 5-clip corpus, confirm the raters flag a deliberately
      mis-registered overlay. If they do not, `annotation_correctness` is measuring style, not
      correctness — and that would be the most important negative result in the evaluation.

### 1.4 `[C]` `M` — The gyroscope validation is from a different workspace
**Verified, and it turned up a second, undocumented effect.** The ablation numbers come from
`workspaces-archive/pre-full-e2e-20260729/job_turntable-3-rect` — a **rectified** workspace.
The shipped worksheets come from `workspaces/job_turntable-3`, **unrectified**.

| | shipped `job_turntable-3` | validated `job_turntable-3-rect` |
|---|---|---|
| `r_fit_m` | **0.2037** | **0.1477** |
| mean ω | 5.458 | 5.794 |
| mean a_c | **7.449** | **5.686** |
| max a_c | **31.06** | **14.13** (= the ablation doc's "peak a_c 14.13") |
| period | 1.469 s | 1.102 s |

Two consequences:

1. **The paper's Table III does not describe the pipeline the paper describes.** It must be
   re-run against the shipped workspace, or removed.
2. **A second ~31% effect on `turntable-3`'s headline number is undocumented.** The memo attributes
   the wrong `a_c` entirely to tracker jumps (7.45 → 5.85, "27% too high"). But `a_c ∝ r`, and the
   radius differs by **38%** between the two workspaces (0.2037 / 0.1477 = 1.38). The rectified run
   gives mean a_c 5.686 — close to the jump-free 5.85, but arrived at by a completely different
   route. **Rectification and jump-rejection may be double-counting the same error, or may be two
   independent ~30% errors.** Nobody has separated them.

- [ ] `[C]` Separate the two effects: run the jump filter on the *rectified* workspace and see
      whether 5.686 moves. If it does not, the jump story is largely a radius story.
- [x] `[C]` **Drop or relabel the `a_c` row of the gyro table regardless.** A phone gyroscope
      measures angular rate only; the "gyroscope a_c" is ω²_gyro × r using *the same r as the video
      leg*, so the radius cancels and the 0.5% agreement carries no information beyond the ω
      agreement. It is not an independent validation and should not be presented as one.
- [ ] `[D]` **The metre scale is validated by nothing.** It has already failed twice (the fan
      radius/diameter coin flip; the bicycle's 12% cross-check failure). A turntable at a known
      fixed RPM plus a ruler of known length in frame would validate rate *and* scale in one shot.

### 1.5 ~~`[C]` `S` — Fix the stale checkpoint line about `IMG_3075.csv`~~ **DONE 08-03**
`SESSION_CHECKPOINT.md:218` says it is *"the phone accel/gyro trace for the ceiling fan; the video
half is not yet shot."* It is not — it is the **turntable** trace, paired with
`job_turntable-3-rect/input_video.mp4`, and it has been analysed (`docs/validation-report.md`
reports it at 0.3% on mean ω). Three different mean-ω values for this clip exist in the docs
(5.458 shipped / 5.660 ablation / 5.794 rect / 5.811 validation-report) and nothing says which run
each belongs to.

- [ ] Correct the checkpoint line.
- [ ] Add the workspace name beside every quoted number in the ablation doc.

---

## 2. Paper claims to reframe (not wrong, but overreaching)

### 2.1 `[C]` `S` — "Video can replace the sensor"
What is demonstrated is that video recovers **angular rate** well, on **one** clip. Rate is
scale-free. Everything reported in SI — v, a_c, a_t — rides on an unvalidated metre scale.
- [x] Lead with *relative* kinematics as the validated claim; treat SI values as a secondary
      product with a stated multiplier uncertainty.

### 2.2 `[DC]` `L` — "Each evaluation layer caught a defect the others missed"
Currently five anecdotes found opportunistically over several weeks, with **no counterfactual** —
we have no idea what each layer *missed*. It is the paper's proudest methodological claim and its
most attackable one.
- [ ] `[C]` Convert it into a real result: **defect injection**. Take clean worksheets, inject N
      known defects per class (ungrounded number, non-closing arithmetic, banned vocabulary, wrong
      motion direction, contaminated measurement, figure/caption contradiction), run all four
      layers, report a **per-layer detection matrix** with recall per defect class.
- [ ] `[D]` Sanity-check the defect taxonomy before it is built — the classes should be ones a
      teacher would recognise, not ones the gate happens to have rules for.
- **This is the single highest-value experiment available.** It turns the weakest argument into
      the strongest, and it needs no new footage, no teachers, and no model access.

### 2.3 ~~`[C]` `S` — Every aggregate mixes 6 good clips with 1 known-bad one~~ **RESOLVED 2026-08-06**
`turntable-3` is **withdrawn from the corpus** (Damar's call). Its contaminated numbers no longer
flow into the gate score, either judge, BERTScore, the EI ladder or Axis 4. Template parked at
`agent-backend/templates-reshoot/basetemplate-turntable-3/` with the full verdict in that
directory's README section; workspace archived.
- [x] Report every headline table **with and without** `turntable-3` — superseded: it is simply out.
- [ ] `[C]` **Every published number that included it must be re-derived, not adjusted.** It was
      1 of 7 in every aggregate quoted to date (14%), and it was the *only* basic worksheet the
      Qwen judge scored 5/5 on grounding — so §7.1's rater-disagreement table loses its most
      striking row and must be recomputed, not edited.
- [ ] `[C]` §1.4's gyro comparison was **entirely** about this clip. With it withdrawn, the
      project has **no sensor-validated clip at all** — that is a bigger hole than the one §1.4
      described, and the paper's validation story has to be rewritten around it, not trimmed.

### 2.4 `[C]` `S` — The corpus is ~4 scenes, not 7 independent phenomena
Three turntable clips of the same object and setup, two ceiling fans (both synthesized), one
computer fan, one roundabout.
- [ ] Say so. In particular, the finding *"the basic tier is formulaic (diversity 0.227)"* may be
      substantially a property of seven near-identical scenes rather than of the generator, and the
      draft currently attributes it to the generator.

### 2.5 `[C]` `S` — Disclose two conflicts of interest
- [ ] The single expert reader is the author of the sibling system being compared against.
- [ ] The "independent" second judge is the same model family used to develop the project and to
      draft this paper; "blind" rests on instructing sub-agents not to open files, which is weaker
      than it sounds. Both are fine disclosed and fatal if a reviewer finds them first.

---

## 3. Statistics and reproducibility

### 3.1 `[C]` `M` — No error bar on the axis that actually varies
Every SD in the paper is **across clips**. Generation demonstrably does **not** reproduce
(19/21 → 16/21 on the gate, 4.12 → 3.90 on the judge). So every generation-derived number —
BERTScore, EI, judge means, gate score — is a **single draw** presented without run-to-run
variance.
- [ ] Regenerate the corpus **3×** and report mean ± SD **across runs** for every generation-derived
      figure. Cheap (tail replay, no SAM3, no e2e) and it is the difference between a number and a
      measurement.

### 3.2 `[C]` `M` — The judge is single-pass
One pass per worksheet per rater, no repeats. The local judge is verified deterministic (κ = 1.00
on re-run), so this is defensible **for that rater**; the API rater's run-to-run variance is
unmeasured.
- [ ] Re-run rater B once on the frozen prompts and report its self-agreement, the same control
      already run for rater A.

### 3.3 `[C]` `S` — BERTScore against OpenStax may not be worth reporting at all
By the project's own measurement, **changing the reference text moves the score by 0.04 — eight
times what the entire pedagogy rework moved it.** A metric dominated by an arbitrary choice of
reference is not measuring the system.
- [ ] Keep it *only* as an explicit comparability row against P-MAGIC, labelled as such, and never
      let it appear in a sentence that sounds like a quality judgement.

---

## 4. Pedagogy — needs people, not code `[D]`

### 4.1 `L` — Is the basic tier below its own curriculum?
It bans ω, α, rad/s and all numeric substitution. **Indonesian Grade-11 physics teaches ω in
rad/s.** So the accessible on-ramp may be teaching content the syllabus does not contain, in a
vocabulary the exam will not use.
- [ ] Check the basic tier against the actual Grade-11 syllabus, with a teacher.

### 4.2 `L` — Does the no-forces rule make the material incoherent?
Gate rule 8b bans *all* dynamics vocabulary — no force, motor, friction, brake. But Grade-11
circular motion is largely **about centripetal force**. A worksheet that names an "inward pull" and
is forbidden from ever calling it a force may be pedagogically incoherent.
- [ ] This is listed in the checkpoint as an open question; it is arguably a **design error**, and
      it is the first thing a physics teacher would notice. It needs a teacher's answer before the
      panel runs, not after.

### 4.3 `M` — Split `grounding_accuracy` before the teacher panel  *(rubric DRAFTED 2026-08-06)*
Already known and already blocking: the two judges have **zero agreement** on it because it
silently asks two questions — *do the numbers trace to the measurement?* and *do the relations
printed beside them close?* Hand it to teachers as written and the human κ inherits the same
ambiguity.

**Re-measured 2026-08-06 on the 5-clip corpus and it got worse, not better: κ = −0.07 with
ZERO exact agreement across all 15 worksheets** (within-1 only 33%, against 88% overall). The
07-31 figure was κ = −0.04. Two raters, fifteen worksheets, and not once the same number — this
is now the least reliable criterion in the rubric by a clear margin, and the only one whose
disagreement is *structural* rather than noisy.

**2026-08-06 — the cause is bigger than the split, and the fix is drafted.** The scale itself was
never defined: the complete definition in all four places it appears was *"1–5 (5 = excellent)"*,
with no statement of what a 2 or a 4 means. The two raters therefore spent the scale differently —
Qwen used it as a detector (six 1s, five 5s, nothing between), Claude never left 2–4 — so their
most-used scores were scores the other never gave, and exact agreement was near-impossible by
construction. κ tracks range overlap: `cognitive_demand`, where the ranges do overlap, reaches 0.70.

**Neither parent rubric could supply the anchors.** Utami used "a 5-point rubric derived from the
criteria" (Tables 8–10 = Item + Definition, no level descriptors); P-MAGIC used "a 25-item rubric
with a **10-point** Likert scale" (Table 2 = Dimension/Criteria/Reference/Description). They do not
even share a scale, so there was nothing to inherit.

- [x] `[C]` **Write the anchors.** `docs/eval-rubric-scoring.md` — all 24 scored criteria across
      4 axes, five descriptive levels each, `grounding_accuracy` split into `grounding_provenance`
      and `grounding_arithmetic`, three calibration cases drawn from defects this corpus actually
      shipped, and the design grounding for every choice (Brookhart 2013; Jonsson & Svingby 2007;
      McHugh 2012; Landis & Koch 1977).
- [x] `[C]` Point the teacher sheet at it (`build_rater_sheet.py`) and cross-link the two rubric docs.
- [ ] `[C]` **Wire the LLM judge**: inject the anchors into `run_llm_judge.py`, replace
      `grounding_accuracy` with the two split criteria in `AXES` (12 → 13 criteria; invalidates
      every stored result), and **re-run both judges on the frozen prompts with nothing else
      changed**. That is a clean test of whether anchoring is what was missing — worth doing
      *before* any teacher time is spent, because if κ does not move, the panel would be spent
      discovering that.
- [ ] `[D]` Vinsa to review the anchors before the panel — she is the pedagogy oracle and the
      wording has to survive a teacher reading it cold.
- [ ] `[C]` can draft the split wording; `[D]` must approve it.

### 4.4 `L` — The teacher panel itself
The instrument is built, the sheets generate, Bahasa is done. This has been "the next step" since
2026-07-08. It is the only thing that answers the question the project is asking, and nothing else
in this file substitutes for it.

---

## 5. Engineering safeguards

### 5.1 `[C]` `M` — Build the jump guard
Nothing in the delivered pipeline rejects a marker that moves 500× its usual step. The sweep that
found the `turntable-3` jumps was written by hand for a memo. Detect against each clip's **own**
local median step (a fixed px threshold is useless — one clip legitimately moves ~240 px/frame),
and handle the NaN-dropout case the hand sweep misses.

### 5.2 `[C]` `S` — Test that the spec and the gate agree
The *"our own spec asks for words our own gate bans"* failure has occurred at least **six** times
across two sweeps. The prompt's allowed vocabulary and the gate's banned lists are maintained
separately and drift. A test that runs one against the other would have caught every instance and
does not exist.

### 5.3 `[C]` `S` — Decide what "the gate" means
`material_tiers.main()` returns 0 with *"proceed-but-flag: never hard-block the pipeline on prose."*
So the gate is a **measurement instrument, not quality control** — all 21 worksheets shipped,
6 of them with a known referent fault. Defensible for research; the paper should say it plainly
rather than implying material is verified *before* rendering.

### 5.4 `[C]` `M` — Fix the four open figure defects
Already catalogued in the 08-05 memo, in order of how badly they mislead: the dashed **"clip
average"** is really the turning-window mean on *every* time-series plot; two basic turns-vs-time
graphs contradict their own captions; the measurements table lists an `a_c` that does not equal
ω²r while the intermediate tier walks the reader through that multiplication and states the wrong
result; and on three clips the fitted circle sits 9–21% of a radius from the traced points while
the basic passage asserts every point falls on one circle.

### 5.5 `[C]` `M` — The "at rest" boundaries are wrong, not just their caption
Suppressing a false caption stopped the figure asserting something untrue; it did not fix the
segmentation. On one clip the rest band begins about half a second before the object stops.

### 5.6 `[D]` `S` — Re-run the 42 Bahasa documents
They embed pre-fix figures.

---

## 6. Open questions worth brainstorming `[D]`

- **Why does the detector jump?** Needs the raw detection boxes, not the kinematics.
  `turntable-3` alternates between two positions 728 px apart; the scene holds a red phone, a steel
  ruler and a hand entering frame, so a second candidate is plausible but unproven.
- **The unexplained mid-coast speed-up** on `turntable-3` (v 0.73 → 1.92 m/s during a coast-down),
  outside every jump-contaminated window. Still open. `bicycle` has its own unexplained wobble.
- **A stronger writer, or generate-K-and-select.** The one remaining failure class is the local 35B
  repeating a banned word when told to fix it. Select-from-K is implemented behind a flag and is
  not the default. Trying a larger model is the cheapest test of whether this is a model-capacity
  limit or a prompt limit.
- **Track the turntable, not just the phone.** The disc rotates *with* the phone and carries
  scratches, moulding rings and a steel ruler — every one an independent estimate of the same ω,
  from footage already shot. Their spread would be the project's first honest uncertainty estimate
  that needs no sensor log. Listed in `ABLATION_METHOD_STUDIES.md` as the highest value-per-effort
  item and still not done.

---

## 7. Paper-specific findings

Full review: **`paper/REVIEW-2026-08-03.md`**. Verdict: **weak reject, borderline, recoverable** —
the fixes are mostly subtraction plus one re-run. Only the items needing action are listed here.

### 7.1 `[C]` `S` — **"Two raters with no shared code reach the same verdict" is FALSE.** *(verified)*
The draft's best corroboration of the referent rule. Basic-tier `grounding_accuracy`:

| clip | Qwen (rater A — **wrote the material**) | Claude (rater B) |
|---|---|---|
| computerfan-4029 | 1 | 4 |
| fan-4027 | 1 | 2 |
| fan-4028 | 2 | 2 |
| roundabout-4046 | 1 | 4 |
| turntable-1 | 2 | 2 |
| turntable-2 | 3 | 4 |
| **turntable-3** (the one the rule passes) | **5** | **4** |

Rater A separates perfectly; **rater B does not separate at all** — the passed worksheet ties three
flagged ones and beats three. So the "two raters" are the deterministic rule and *the model that
wrote the material*, on the criterion reported at κ = −0.04. And the passed clip is `turntable-3`,
which the paper elsewhere declares untrusted.
- [x] Rewrite. The true version is a **stronger** argument for two raters than the false one.
- [x] Adopt the consequence: **rater A cannot be trusted on grounding.** Draw every grounding
      conclusion from rater B or the deterministic gate.

### 7.2 `[C]` `M` — The gyro table's problem is worse than §1.4 said *(verified)*
Beyond the workspace mismatch: on the **shipped** run, peak ω is 12.35 vs the gyro's 9.820
(**+26%**) and peak a_c is **+119%** — not 0.4% and 0.5%. And the divergence came from the
**agentic half**: `pipeline_inputs.json` differs in `fps`, `hub_px`, `reference.diameter_px`
(1025 vs 1078) and `roi_crop` **from an identical sidecar**. So §III-A's *"the same measurement
twice"* is true of the frozen half and misleading about the delivered product.
- [x] Publish the honest numbers. Means within a few percent with instants +26% **fits the paper's
      own thesis better** than 0.1–0.5% does.
- [x] Add a paragraph on agentic-half run-to-run variance — it is arguably the paper's most
      original engineering finding and it is currently hidden.

### 7.3 `[C]` `S` — Annotation correctness is scored **against the seed** *(verified logic)*
So on `turntable-3` an annotation faithfully drawing a 27%-wrong measurement scores full marks.
**The paper's own "tracing is not validating" lesson applies to its strongest row and is not
applied.** Combined with §1.3 (it was scored on still frames), the headline contribution has two
independent problems.
- [x] Argue the annotation contribution from the **deterministic** checks (`verify_figures` clean
      7/7, plus the 6 + 7 pinning tests) with the rater as corroboration, not from the score.

### 7.4 `[C]` `S` — Four smaller factual fixes *(relayed, spot-checked)*
- [x] **`difficulty_fit` is P-MAGIC's, not ours.** `eval-framework.md`'s own table says
      *"From P-MAGIC: difficulty→difficulty_fit"* and their Table 2 has it with κ = 0.750. Only
      `grounding_accuracy` is defensibly new.
- [x] **"no clip or generated text leaves the lab" is false** — rater B is a hosted API and the
      Axis-4 rater was sent rendered frames of the footage. Restrict to the generation pipeline.
- [x] **P-MAGIC's annotation ablation is on an automatic relevancy metric**, not teachers and not
      learning. As written it reads as evidence annotation helps *people*. Also "image-bearing
      modalities beating graph/table" is 2 of 15 comparisons at p < .05.
- [x] **"8.18–8.58/10" is their *linguistic relevancy* row**, not an overall band; their 25 rows
      span 1.54–8.99. Name the row or drop the comparison.
- [x] Smoothing window is **≈fps/3** (`2*(fps//6)+1` = 21 frames at 60 fps), not fps/6.
- [x] 24.14 rad/s is the max *inside the rest-labelled samples*; `computerfan-4029` peaks at
      **46.5**. Drop the "fastest moment of the whole recording" superlative.

### 7.5 `[C]` `S` — Report the judge's **false positive**, not just its catch
Both memos record the judge marking `turntable-1` wrong for 8.04² × 0.438 = 28.3, *which is
correct*. Omitting it while featuring the turntable-3 catch weakens the defect table and the
paper's honesty stance simultaneously.

### 7.6 `[C]` `S` — Put a CI on the κ values, and carry the source's own caveat
`judge-reliability-2026-07-31.md` §6: *"n = 21 is small for a per-criterion κ… read as
**indicative**."* The paper quotes grounding κ = −0.04 in bold four times. With n = 21 the CI spans
most of [−0.4, 0.4]; **the honest claim is "no detectable agreement," not a point estimate.**

### 7.7 `[C]` `M` — Length: 11 pages, 7,738 prose words
System Design is **37%** of the prose; Discussion — where the contribution lives — is **6%**, shorter
than the frozen-kinematics subsection. Cut §III-D's constants, the cue-wording sweep, the
workspace-copy ops note, Table I (duplicates Fig. 1); merge Tables IV and V. Grow §VI, §V-C, and
§II-C (100 words with three `\todo` citations, carrying the paper's entire reason to exist).

### 7.8 `[DC]` `M` — **Add an output figure. Largest single omission.**
One figure in the whole paper and it is a tracker-jump diagnostic. No worksheet excerpt, no
annotated frame, no three-tier side-by-side. *"Would do more for acceptance than any three pages of
§III."*

### 7.9 `[C]` `S` — The generator is never specified
Named only in §IV-C, in a sentence about the *judge*. No decoding parameters, temperature, seed,
context length or serving stack. Not reproducible as written.

### 7.10 `[C]` `S` — Repair-loop statistics, from data already on disk
How many of 21 needed a retry; fixed on retry 1 vs 2; discarded by strict-improvement; cross-tier
fires. It is all in each workspace's `material_tiers_gate.json`, and it is the direct evidence for
Alg. 1's four currently-asserted properties.

### 7.11 `[C]` `M` — **Zero LLM-as-a-judge citations.** Biggest bibliography gap.
The central methodological claim is about judge reliability and the paper cites neither the
paradigm, nor self-preference bias (directly relevant — writer and rater A are one family), nor
position/verbosity bias, nor judge–human agreement work. Also missing: an AQG survey, CLT/worked-
example literature beyond one Sweller, a citation for the known failure of readability formulas,
and the SAM 3 release (`\cite{sam}` currently points at SAM 1).
- [x] Pair it with the **self-preference analysis already latent in the data**: rater A is *not*
      more generous on `grounding_accuracy` (3.10 vs 3.14) or `difficulty_fit` (4.48 vs 4.48); the
      big gaps are `fluency` (−1.05), `structure_clarity` (−1.00), `comprehension` (−0.90) — surface
      rows, where harshness is the more parsimonious account than self-preference.

### 7.12 `[C]` `S` — Cut three of the four retractions
An IEEE reviewer has not seen the plan deck, "the week", or the offline run. Retracting claims the
reader never heard reads as an unfinished project. **The finding survives without the retraction in
every case.** Keep exactly one — the reading-grade one, which is the paper's credibility anchor.

### 7.13 `[C]` `S` — Three overclaiming phrases to soften
*"the strongest empirical claim"* (it is the weakest); *"independently checked… and found them
right"* (a single rater's self-report — *"the rater reported checking"*); *"the single most
consequential design decision"* (undercut by 7.2).

### 7.14 `[C]` `S` — Ethics and artifact availability
No IRB/ethics statement, no code or data statement, no prompt appendix. P-MAGIC (same institution)
carries IRB approval and informed consent. Note: footage includes a playground roundabout and a hand
entering frame, and rendered frames went to a third-party API.
`judge-reliability-2026-07-31.md` §7 already holds a working reproduction script — paste it as an
appendix.

### 7.15 `[C]` `S` — Threats to validity not covered
Order/anchoring (rater B saw 3 worksheets per agent, rater A saw 21 in one pass — the source itself
notes B *"could not calibrate its scale across the corpus"*, a plausible partial explanation of the
−0.5 offset the paper attributes to calibration); rater B's test–retest was never measured, so only
one side of the comparison is pinned; and the OpenStax reference was *"reorganised into our section
structure"* — by whom, and does that inflate BERTScore?

### 7.16 `[C]` `S` — Two Results-section inconsistencies
- Table X's reading-grade row calls a "defect" what §V-C says *"is not a defect in the material."*
- Table VIII's `N` column (7/35/14/84) sits beside a κ computed on a different denominator (21 per
  criterion, 252 overall) and will be read as "your overall κ is on n = 84."

### 7.17 Resolved, no action
- **FK ladder 0/7 vs 1/7** and **EI intermediate 19 vs 13.9**: recomputed from the shipped
  worksheets — **1/7 and 13.86**. The draft is right; `SESSION_CHECKPOINT.md` is stale (now fixed).
- **Passage length 484/330/668**: the reviewer could not find a source; the values are correct
  (recomputed). But the row still invites a question the paper never answers — *why is intermediate
  32% shorter than basic?*
- **The 22-vs-25 rubric resolution is correct** and silently fixes a contradiction inside P-MAGIC
  itself (their p.18 says 22, p.23 says 25). Worth a footnote — it makes the paper look careful.
