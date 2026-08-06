# Centri weekly memo — scoring the material

Companion to `centri-weekly-2026-08-05.pdf`. The deck is for the room; this is for reading cold.
Every claim on a slide appears here with its definition, its caveat, and the number behind it.

**What Centri is.** A phone video of something spinning goes in; measured kinematics and a set of
physics worksheets at three difficulty levels come out, with the figures drawn onto the footage
itself. Nothing is typed in by hand. The parent line is the Utami dissertation (SocioMathLLM,
Geo-QG); the sibling app P-MAGIC does the same from phone *sensors* rather than video.

**Vocabulary used below.** *Tier* — one of the three levels (basic / intermediate / advanced).
*Turn rate* (ω) — how fast the object sweeps round its circle, in radians per second. *Inward
pull* (a_c) — the acceleration that holds it on the circle, equal to ω²r. *Checker* — the
automatic program that reads a finished worksheet and refuses it if a number doesn't trace back
to the measurement, an equation doesn't close, or the wording breaks a tier's rules; it contains
no model and gives the same answer every time. *Judge* — a language model scoring the same
worksheets against a written rubric; there are now two, from different model families, scoring
independently. *Cohen's κ* — how much two raters agree beyond what agreeing at random would
produce: 1 is perfect, 0 is chance, below 0 is worse than chance. *Active segment* — the part of a clip where the object is
actually turning, as opposed to the moments before it starts and after it stops.

## The figures disagreed with their own text

Last week's fix made the *prose* read the object's motion from its speed rather than from the
tracker's sign. That fix reached three surfaces and missed two, and the two it missed are both
pictures.

**Why there is a sign at all.** The tracker measures the angle with `atan2` in image coordinates,
where the row index grows *downward*. Increasing angle therefore traces right → bottom → left →
top: **clockwise as the viewer sees it**. A clip filmed from the other side records the same spin
as negative. This is the opposite of the textbook convention, and it is a property of the camera,
not of the object. Both ceiling-fan clips are on that side. Checked directly against the raw pixel
positions — the sign of successive cross-products — `fan-4027` and `fan-4028` have 0% of their
steps going clockwise, and `turntable-1` has 100%. So the label is right: the fans turn
counter-clockwise.

**What still carried the sign.** The plotted turn-rate curve. On both fan clips it sat *entirely*
below zero — 4,639 of 4,639 samples on `fan-4027`, and every one of `fan-4028`'s 4,368 active
samples. So the figure a student read rose steadily toward zero while the passage beside it said
the fan was slowing down. Two further contradictions sat in the same picture: the dashed "clip
average" line was drawn at **+5.70** — above every point on a curve that never rose above −1,
because that number had already been converted to a magnitude — and the shaded band marked
*increasing* was the stretch where the line visibly fell, because the band labels had also
already been converted. Three surfaces of one figure, and only the curve was left signed.

**And the arrows pointed backwards.** The annotated photo draws an arrow for the direction of
travel and a curved arrow for the spin. Both took their direction from the sign of the stored
turn rate — but that value is now a magnitude, so the test was always true and the arrows were
always drawn clockwise. **This was caused by the previous fix**: converting the stored value to a
magnitude silently removed the only signal the drawing code was reading. On the two fan clips
that is all six of their worksheets, at every level, showing both arrows pointing the wrong way
round the circle.

**What changed.** Direction now comes from the rotation label, which the measurement stage has
already resolved into the viewer's frame; the curve is plotted as **angular speed**, and its axis
says so. Nothing was hidden: the signed series is untouched in the data file and in the
diagnostics, where the sign means something. Six new tests pin the rule — anything that needs to
know *which way* reads the direction label, anything that needs to know *how fast* reads a
magnitude, and neither is ever derived from the other. The suite is **92 tests, all passing**.

## Jitter after the object stops

Looking into the sign question turned up a second defect, and disproved a hypothesis worth
recording. Four clips have negative turn-rate samples that are *not* explained by
counter-clockwise rotation: `computerfan-4029` (198), `turntable-3` (92), `turntable-2` (83),
`turntable-1` (69). The natural guess was that the tracker briefly reverses mid-clip. **It does
not.** Every one of those samples — 442 of 442 — falls *outside* the active segment; inside the
active window those four clips have exactly zero negative samples.

That was being drawn as physics, because the graphs plot the whole recording. Since the inward
pull goes as the *square* of the turn rate the sign cancels, so it comes through as a large
positive spike. The rest periods were already shaded grey but carried no words, so nothing told a
reader what the grey meant. They now say **"not turning"**. Naming them cannot change any claim
the checker verifies — rest periods were already excluded from the phase list the prose is checked
against.

This is the third time the at-rest tail has faked a result; it also inflated the cross-tracker
agreement figures reported on 07-21. **Any statistic over these clips must exclude the dead
segment**, and any figure that shows it must say what it is.

## The tracker jumps — and one clip's published numbers are wrong

Asking *why* those spikes were so large turned out to matter more than the spikes themselves,
and it retracts a claim made earlier in this same memo.

The spikes are not wobble. **The tracked marker teleports.** On `turntable-3` it normally moves
1.4 px between one frame and the next; three times it moves **604, 614 and 713 px in a single
17 ms frame** — four to five hundred times its usual step — flipping between two positions 728 px
apart. Each of the three spikes sits exactly on one of those jumps. They look like smooth
mountains rather than single-frame glitches because the turn rate is computed from a smoothed
angle, and that smoothing is centred: a step gets smeared symmetrically into a ramp either side.
In the raw rows the marker is frozen to within 0.1 px while the turn rate climbs from 0 to
10.2 rad/s — the filter anticipating a jump that has not happened yet.

**One of the three jumps is inside the measured window**, so this is not confined to the dead
tail. Eighteen of `turntable-3`'s 106 active samples are contaminated, and removing them moves
the clip's headline number:

| turntable-3 | as shipped | jumps removed |
|---|---|---|
| mean inward pull | **7.45 m/s²** | **5.85 m/s²** |
| largest inward pull | 31.06 | 18.12 |
| mean turn rate | 5.46 rad/s | 4.95 rad/s |

**The worksheet teaches 7.45 m/s². It is 27% too high.**

Sweeping all seven clips with a detector tuned to each clip's *own* normal step — a fixed pixel
threshold is useless here, because `computerfan-4029` legitimately travels ~240 px between frames
at full speed — gives a contained result:

| clip | jumps | inside the measured window | taught numbers |
|---|---|---|---|
| `turntable-3` | 3 | **1** | **wrong by 27%** |
| `computerfan-4029` | 4 | 0 | unaffected |
| `fan-4027`, `fan-4028`, `roundabout-4046`, `turntable-1`, `turntable-2` | 0 | — | unaffected |

**Five of seven clips are clean, and only `turntable-3`'s published numbers are affected.**

**This does *not* close the long-standing "mid-coast speed-up, cause unidentified" on this clip,
and an earlier draft claiming it probably did was wrong.** That speed-up was reported on 07-21 at
t ≈ 3.05–3.15 s. The delivered data has **no samples at all in that window** — it is a 13-frame
tracking dropout — so the 07-21 observation cannot even be re-tested against the current run; it
was made on an earlier one. The current data does contain a mid-coast rise, at t ≈ 2.28–2.64 s
where the tangential speed climbs 0.73 → 1.92 m/s during what should be a coast-down, and that
rise sits *outside* every contaminated window. **It remains unexplained.** The jumps explain the
three spikes and the inflated average; they do not explain the speed-up.

One limitation of the sweep, recorded so it is not mistaken for a clean bill: **the detector
compares consecutive frames, so a jump that straddles a tracking dropout is invisible to it.**
`turntable-3` re-acquires at t = 3.21 s having moved 521 px since its last fix — but that follows
a 13-frame gap, and at ~6 rad/s the object really would sweep about that far in the interval, so
that one is consistent with genuine motion rather than a jump.

**`turntable-3` should not be treated as trusted until this is fixed.** Its worksheets carry a
number that is wrong by more than a quarter.

## The checker

The checker reads all 21 worksheets and needs no model. **19 of 21 pass** every rule it has
carried until now. The two that do not: one advanced worksheet uses the banned word "frame", and
one intermediate invents an ungrounded "1.8 seconds".

A new rule is now wired in, for a fault the checker previously could not see. One worksheet says a
full turn takes 2.07 s and then that "*that* turn rate" is 0.30 turns per second — which is a
3.34 s turn. Both numbers are real: 2.07 s is the fastest lap, 0.30/s the clip average. Every
number traced, so the old checker passed it; the fault is the pronoun tying an average rate to an
instantaneous period. With that rule on, the score is **13 of 21** — it fires 12 times across six
worksheets, all of them at basic level.

Two things make that number worth trusting. It **agrees with the judge clip for clip**: the same
six flagged, and `turntable-3`, the one basic worksheet it passes, is also the one the judge
scores 5 out of 5 for grounding — where the other six score 1, 1, 1, 2, 2 and 3. Two raters with
no shared code reach the same verdict. And the figure changes described above introduced **no new
checker failures at all**, which is the evidence that redrawing the graphs did not disturb the
text.

Trying to fix the fault by *instruction* — telling the writer not to do it — made things worse:
regenerating dropped the checker from 19/21 to 16/21 and the judge from 4.12 to 3.90 while
clearing only 2 of 6 instances. That generation was discarded. **A prompt rule cannot make a model
careful about a referent**; the fix is to hand the writer a period and a rate already paired to
the same moment, so the contradiction cannot be written.

## Automatic scores, in P-MAGIC's layout

Both tables below are now generated by `agent-backend/tools/build_pmagic_tables.py` in the
layouts P-MAGIC publishes (`refs/document-4.pdf`, Tables 3 and 7), so the two sets of numbers can
be read side by side. Re-running the metric this week reproduced the 07-29 figures exactly
(the per-section F1 of 0.822 ± 0.015 over n = 105; diversity 0.308), a useful reproducibility check
given that a single generation run is not repeatable.

Every metric below except diversity compares our text to **one** reference — OpenStax College
Physics §6.2, reorganised into our section structure. So a high score means *more like OpenStax*,
never *better teaching*.

**What n counts.** The unit is one **worksheet**, so **n = 21 = 7 clips × 3 levels**, and 7 per
level. Some diagnostics are computed per *section* instead, and those report **n = 105 = 21
worksheets × their 5 sections** — the same corpus counted a different way. Last week's memo quoted
both without saying which was which; every n below is worksheets unless it says otherwise.

| Metric | What it is, and how it is computed |
|---|---|
| **BERT F1** | Meaning overlap. RoBERTa-large turns each word into a vector that depends on its context, each of our words is matched to the reference word closest to it, and F1 is the harmonic mean of R and P. Raw scores, not baseline-rescaled, to stay comparable with P-MAGIC. |
| **BERT R** | Recall — of the reference's words, how many ours cover. |
| **BERT P** | Precision — of our words, how many the reference supports. |
| **BLEU-4** | Exact word-sequence overlap up to four words in a row, with a penalty for being short. Near zero unless one text nearly copies the other. |
| **ROUGE-1 / -2 / -L** | Surface overlap by single words, two-word sequences, and longest common subsequence (shared word order with gaps allowed). |
| **Diversity** | The one metric that ignores the reference: how much the passages differ from *each other*. One minus their mean pairwise cosine similarity as MiniLM sentence embeddings. Higher means less repetitive. |
| **LSTM** | P-MAGIC's fifth metric, a fluency score from an LSTM they trained. Reproducing it needs their trained weights, which are not published and which we do not have. Reported as **n/a** rather than dropped, so the gap stays visible in the table. |

| Level | n | BERT F1 | BERT R | BERT P | BLEU-4 | ROUGE-1 | ROUGE-L | Diversity |
|---|---|---|---|---|---|---|---|---|
| basic | 7 | 0.800 ± 0.003 | 0.792 | 0.809 | 0.015 | 0.276 | 0.142 | **0.227** |
| intermediate | 7 | 0.824 ± 0.003 | 0.827 | 0.822 | 0.032 | 0.369 | 0.168 | 0.317 |
| advanced | 7 | 0.831 ± 0.004 | 0.832 | 0.829 | 0.040 | 0.411 | 0.179 | 0.322 |
| **all** | 21 | **0.818 ± 0.014** | 0.817 | 0.820 | 0.029 | 0.352 | 0.163 | 0.310 |

The n-gram columns are far lower than the BERT ones by construction: BLEU-4 at 0.029 means our
text almost never repeats four of the reference's words in a row, which is what you would want
from generated material that is not copying. They move in the same direction as BERTScore across
levels — BLEU-4 rises 0.015 → 0.040 and ROUGE-1 0.276 → 0.411 — so all seven similarity columns
are telling one story rather than seven.

Two further things are visible only once it is broken out by level. **The spread within a level is
±0.003; across all 21 it is ±0.014.** Almost all the variation is between levels, not between
videos — the score is reading which tier you handed it, not which clip the worksheet came from.
And **the basic tier's diversity is 0.227 against 0.317 and 0.322**: diversity here is one minus
the average similarity between passages, so the seven beginner worksheets resemble each other
considerably more than the harder ones do. Making the beginner text simple has also made it
formulaic. That is a genuine weakness, and it is the first measurement that shows it.

The ordering — basic lowest, advanced highest — is not a quality ranking. The metric rewards
resemblance to a *college* textbook, so **making the beginner level more readable lowers its
score**. Changing the reference text moves the number by 0.04, eight times what the entire
pedagogy rework moved it. Report it; never optimise it.

For context, P-MAGIC report BERT F1 around 0.877–0.885 and diversity around 0.51. Ours are lower
on both, and the reasons are structural rather than qualitative: their 150 problems span many
contexts while our 21 worksheets describe seven clips of broadly similar circular motion, which
depresses diversity directly. P-MAGIC's fifth metric, an LSTM fluency score, is reported as **not
available** rather than dropped — it requires their own trained model, which we do not have.

## The LLM judge, on all three axes

**The judge is a language model, not a person.** Two of them now. Each is shown one worksheet at a
time together with the written rubric and the measured values the worksheet was built from, and
returns an integer 1–5 for each of the twelve criteria plus a rationale and a Bloom level. One
pass per worksheet, no averaging over repeated runs.

- **`Qwen3.6-35B`**, run locally on the lab machine (`192.168.1.205:8083`) at temperature 0,
  scored **2026-07-29**. This is the model that also *wrote* the material, so on its own it is
  grading its own work.
- **`Claude Opus 5`** (model ID `claude-opus-5` — the Opus tier, not Sonnet or Haiku), a different
  model from a different vendor, scored **2026-07-31**. Run as seven independent raters, one per
  clip, each shown only its own three worksheets and told nothing about the other judge's scores
  or any existing evaluation.

Both model versions are named in full deliberately: "an LLM judged it" is not a reproducible
statement, and a family name without a version silently changes meaning as models are replaced.

Both were handed the **same question, character for character**. The prompt is built once and
written to a file (`tools/export_judge_prompts.py`); every rater is then sent that file verbatim.
This matters more than it sounds: if two raters are assembled two prompts, any difference in their
scores could be a difference in the question rather than in the judgement.

| Axis | basic | intermediate | advanced |
|---|---|---|---|
| Linguistic / authenticity | 3.97 / 3.31 | 3.91 / 3.23 | 4.49 / 3.94 |
| Structural / comprehension | 4.20 / 3.46 | 4.11 / 3.57 | 4.46 / 3.94 |
| Physics / tier | 3.50 / 3.79 | 3.43 / 3.57 | 4.43 / 4.07 |
| **all 12 criteria** | **3.99 / 3.45** | **3.92 / 3.43** | **4.46 / 3.96** |

*Qwen / Claude. The per-criterion table, with κ and M (SD) per level in P-MAGIC's Table 7 shape,
is in `agent-backend/material_work/_eval/pmagic_tables.md`.*

**The two raters agree on the ordering and disagree on the score.** Both put advanced top and both
separate it from the two lower levels. But Claude marks lower everywhere — by 0.54, 0.49 and 0.50
of a point at the three levels, a bias so nearly constant that it looks like a different calibration
of the same scale rather than a different reading of the worksheets. Over all 252 paired ratings
(21 worksheets × 12 criteria) the two give **the identical integer 33% of the time, and land within
one point 88%** of the time.

The criterion that carries the claim that the levels differ is **cognitive demand: 2.86 → 3.86 →
4.71** for Qwen, 2.43 → 2.86 → 4.14 for Claude — it rises for both, and it is also the criterion
the two agree on most closely (κ = 0.59, correlation 0.78). The achieved Bloom level — the kind of
thinking the passage asks for — is Understand / **Apply** / Analyze, though only the basic tier is
unanimous across the seven clips: intermediate reaches Apply on 5 of 7 and Analyze appears on 6 of
7 advanced worksheets, with the remainder falling back to Understand in both cases.

**The weakest column is grounding — 2.14 / 2.71 / 4.43 — and it needs reading criterion by
criterion, because the judge was wrong once and right once.**

It marked `turntable-1` wrong for writing 8.04² × 0.438 = 28.3, which is correct to three
figures. That is the judge's own arithmetic failing, and it is the reason not to use a model to
audit sums.

It marked `turntable-3` wrong for an average inward pull of 7.45 m/s² when squaring the average
turn rate gives 5.82. **An earlier draft of this memo defended that passage, on the grounds that
the gap between the two numbers is exactly what it teaches — that the average of the squares is
not the square of the average. That defence was wrong and is retracted.** The 7.45 is a tracker
artifact (see above); the honest figure is 5.85. The averaging effect is real and survives at a
smaller size — with the jumps removed the two quantities are 5.85 and 4.99, a gap of 17% rather
than 28% — but the specific number the worksheet prints is not sound, and the judge was right to
flag it.

**The deterministic checker could never have caught this**, and that is worth stating plainly: it
verifies that every number *traces back to the measurement*, and 7.45 does trace. It has no way to
ask whether the measurement itself is sound. **Tracing a number is not validating it.** So the
earlier formulation — "where the judge and the checker disagree, the checker has been right" — is
also withdrawn. They answer different questions, and on this clip the model caught what the
checker by construction cannot.

**The second judge caught the same defect in a tier the first one passed.** `turntable-3`'s
contaminated 7.45 appears in both its intermediate and its advanced worksheet. The local judge
flagged the intermediate one (grounding 2) and gave the advanced one full marks (5). Claude
flagged both (2 and 2), on the stated reason that the arithmetic does not close — ω²r = 5.82
against a printed 7.45, and 2π/ω = 1.18 s against a printed 1.469 s. So the one worksheet in the
corpus whose numbers are known to be wrong was rated *perfectly grounded* by one judge and
*badly grounded* by the other. A single rater would have reported whichever of those it happened
to be.

The first judge is still the same model family that wrote the material, so it remains evidence
rather than proof; the second is independent of the writer, which is the main thing it adds
beyond a reliability figure.

## Axis 4 — judging the figures

Everything above scores the **prose**. The rubric has a fourth axis, eleven more criteria, that
scores the **figures** — whether a graph plots the data correctly and is labelled with the right
quantities and units, whether a table supports reasoning, whether the arrows drawn on the video
frame point at the right object and read the right value. It needs a rater that can *see*, so it
had never been run on the current material: the only previous Axis-4 scores date from June, before
both the pedagogy rework and this month's figure corrections, and describe figures that no longer
exist. Twelve text criteria plus eleven figure criteria is the full instrument: **23**.

It was scored by `Claude Opus 5` reading the rendered images themselves, seven raters, one clip
each.

| Modality | basic | intermediate | advanced |
|---|---|---|---|
| Image–text | 3.71 | 3.50 | 3.86 |
| Text–graph | 3.36 | 3.14 | 3.25 |
| Text–table | *n/a* | 3.36 | 3.25 |
| **The annotated video frame** | **4.29** | **4.43** | **4.29** |
| **all criteria scored** | 3.59 | 3.40 | 3.45 |

**`n/a` is not a low score.** The basic tier prints no table — deliberately, to keep the number of
things on the page low. Its four table criteria therefore do not apply and are left out of every
average. Scoring an absent figure as a bad one would have penalised the basic tier for being
correctly designed, and would have made it look worse the more carefully it was built.

**Two things this says.** First, **the annotated video frame is the strongest single row in the
entire evaluation.** That is the part of Centri that is genuinely its own — the overlays drawn onto
the footage — and a rater that was never told anything had been fixed independently checked every
printed value against the measurement and every arrow against the fitted circle, and found them
right. Second, **the figures do not get harder by level** (3.59 / 3.40 / 3.45, no ladder). The same
drawing code serves all three tiers, so this is unsurprising, but it means the claim that the
levels differ rests on the prose alone and cannot be supported by pointing at the figures.

## A caption that denied its own curve

Axis 4 immediately caught something no other check could, and it was a defect introduced this same
week. Bands where the object is at rest were given a printed caption, "not turning", so that small
jitter inside them would not be misread as motion. But the software that decides which parts of a
clip count as "at rest" marks some moving stretches as rest — so on one clip a band captioned
**"not turning" contained the object moving at 24 radians per second**, its fastest of the whole
recording. **Eleven of the twelve rest bands in the collection carried a caption their own curve
contradicted.**

The caption did not create that error; it made a silent one into a printed claim, and a reader
believes the words over the line. The fix is a rule: a caption is dropped whenever the data
underneath it disagrees. The grey shading stays, because a colour is not a claim. All seven clips
were redrawn.

**This retracts something stated earlier in this memo's own week.** The redraw of the figures was
reported as introducing "zero new failures", offered as evidence that the figure work had not
disturbed anything. The automatic checker was indeed clean — but it checks that labelled values
trace back to the measurement, and never asks whether a caption agrees with the curve beneath it.
**A clean check is evidence about the check.** It took a rater that could look at the picture.

**Still wrong, and open:** the underlying decision about which stretches count as "at rest" is
itself inaccurate — on one clip the rest band begins about half a second before the object actually
stops. Suppressing the caption stops the figure asserting something false; it does not make the
boundary right.

The same run found four other figure defects that are real and not yet fixed: the dashed line
labelled "clip average" is actually the average over the *turning* part only, which on one clip
puts it far above almost the whole curve; two of the basic turns-vs-time graphs show the object
speeding up beneath a caption saying it slows; the measurements table lists an inward pull that
does not equal turn-rate-squared times radius, and the intermediate tier walks the reader through
that multiplication and states the wrong result; and on three clips the fitted circle sits 9–21%
of a radius away from the traced points, so the basic passage's "every point falls on one circle"
is visibly untrue.

## One rubric, two kinds of rater

The instrument itself is twelve criteria in three groups. **Ten are adopted from the parent line**
— five from the Utami dissertation's Tables 8 and 9, five from P-MAGIC — so that our rows line up
with theirs and the two papers' results tables can be read against each other. **Two are Centri's
own**, because neither parent measures a tiered passage read off video:

| Group | Criteria | Adopted from |
|---|---|---|
| Linguistic / authenticity | motivating context, language clarity, cognitive demand | Utami Table 8 |
| | fluency, completeness | P-MAGIC |
| Structural / comprehension | structure clarity | Utami Table 9 |
| | comprehension, concept accuracy, realistic, variable-name consistency | P-MAGIC |
| Physics / tier | difficulty fit, grounding accuracy | Centri |

The judge and the teacher panel score these **same twelve criteria on the same 1–5 scale**, so the
instrument is already built and already runs on all 21 worksheets; only the human raters are
missing. Three caveats attach to that plan.

**The Cohen's κ column now has numbers in it, and they are not reassuring.** κ measures how often
two independent raters give the same score, corrected for how often they would agree by chance; it
is the standard evidence that a rubric was applied consistently rather than idiosyncratically.
P-MAGIC report it per dimension, averaging 0.76 across their ten teachers, which counts as good
agreement. Until there was a second rater ours could only be a dash. With two judges it is
computable, and **overall it is 0.34** — weak. Read it with three cautions.

*It is weighted.* On a 1–5 scale, scoring a 4 where the other rater said 5 is a near miss and
should not count the same as 1 against 5, so κ here is **quadratic-weighted**. The unweighted
value, which demands the exact same integer, is **0.08** — barely above chance. The weighted
figure is the fairer one; the unweighted one is the reminder of how far apart the raters are on
any single worksheet.

*It is model-vs-model.* P-MAGIC's 0.76 is between *people*. Two models agreeing would show that
the rubric is legible to a machine, not that its scores mean anything about teaching. The human
column is still empty and this does not fill it.

*It is uneven across criteria, in a way that is itself the finding.* Agreement is best on
**cognitive demand (κ = 0.59)** — the criterion the tier claim rests on. It is worst, by far, on
**grounding accuracy (κ = −0.04, correlation −0.05)**: the two judges land within one point of each
other on only 52% of worksheets, against 88% overall, and they disagree by a full three points in
five places, in both directions. This is the criterion that asks whether the numbers hold up — the
one a physics worksheet most needs — and the two raters are, in effect, reading different
documents. Some of that is real: the seed values for several clips do not satisfy the relations
the worksheets print (ω²r ≠ a_c, because one is an average of squares and the other a square of
an average, and on `turntable-3` because the measurement is contaminated). One rater penalises the
worksheet for stating a relation that does not close; the other accepts it as a faithful report of
what was measured. Both readings are defensible, which is precisely why a single number from a
single judge should not be quoted as a quality score.

**The practical consequence:** the LLM judge is usable for *ranking* — it reproduces the tier
ordering across two unrelated models — and not for *level*. Any absolute figure ("4.12 of 5",
"8.2 of 10") is a property of the rater as much as of the material, and the ×2 rescaling onto
P-MAGIC's 10-point scale inherits that on top of the stretch problem described above.

**A control worth recording:** re-running the local judge on the frozen prompts two days after the
original run reproduced it **exactly — all 21 worksheets, all 252 ratings identical, not one
digit different, κ = 1.00.** The local judge is therefore deterministic, which matters twice. The
gap between the two judges is a genuine difference between raters and not run-to-run noise. And
the original run must have been given the same prompt this comparison uses, which is what licenses
comparing them at all.

It is worth setting that against the *writer*, which does not reproduce: regenerating the same
worksheets moved the checker from 19/21 to 16/21. **The model that grades is stable; the model
that writes is not.** Single-run judge numbers can be quoted with the run named; single-run
generation numbers need a mean across runs.

**The scales differ from P-MAGIC's.** Their ten teachers scored on a 10-point Likert with a
25-item rubric, reaching relevancy means of 8.58 / 8.21 / 8.18. Ours is 1–5. The generated tables
therefore print a doubled column beside each mean so the columns can be compared at a glance, and
label it as what it is: a linear stretch, not a calibration. Our overall 4.12 of 5 becomes 8.2 of
10, which lands inside their 8.2–8.6 band — but that coincidence carries no weight, because
doubling cannot make two instruments equivalent and one of the raters is a model.

**A model rater cannot substitute for a human one.** It cannot report whether a passage taught
anybody anything, and it is not independent of the system that wrote the text.

## Bahasa Indonesia edition

All 42 documents (7 clips × 3 levels × student and teacher) are built in Bahasa Indonesia for the
teacher panel, beside the English. Translation runs on the *rendered* worksheet rather than the
model's prose alone — measured across the 21 worksheets, only 17–32% of a page is that prose
(mean 26%, counting words in the generated sections against words in the rendered document); the
rest is scaffolding the pipeline
generates. Every number and symbol is verified against the English before a file is kept, and a
fixed glossary holds the terms steady across levels (*jari-jari*, *kecepatan sudut*, *percepatan
sentripetal*). Decimals stay in international form (0.26, not 0,26) so the number-preservation
check remains valid; localise at display time if the panel prefers commas.

## What is still unproven

Almost everything measured so far is a property of the **text**: whether its numbers trace to the
measurement, whether its figures agree with it, whether it can be read, whether it asks anything
of the reader. This week added the one check that goes behind the text — whether the measurement
itself is sound — and it found one clip of seven where it is not.

**Nothing yet measures whether anybody learns from it.** P-MAGIC has ten teachers rating at
8.2–8.6/10; Centri has one expert reader and two model judges, and a model cannot stand in for
either a teacher or a learner. Adding the second judge did not move that: it bought a reliability
figure and an independent rater, and what it mostly demonstrated is how far two competent readers
of the same rubric can sit apart. Teacher ratings are the next step, and they are the only thing
that answers the question the project is actually asking.

## Open, in priority order

1. **`turntable-3` is not trusted.** Its worksheets teach a number that is 27% too high. Either
   the three jumps are rejected before the statistics are computed, or the clip is withdrawn from
   the set until it is re-tracked.
2. **A jump guard belongs in the pipeline.** The sweep that found this was written by hand for
   this memo; nothing in the delivered system rejects a marker that moves five hundred times its
   usual step, and nothing would have caught it on the next clip.
3. **Why the detector jumps is unknown.** It needs the raw detection boxes, not the kinematics.
4. **The grounding-accuracy criterion needs splitting before the teacher panel runs.** It is the
   one criterion the two judges cannot agree on at all (κ = −0.04), and the likeliest reason is
   that it silently asks two questions: *do the numbers trace back to the measurement?* and *do
   the relations printed beside them close?* Those come apart whenever a worksheet correctly
   reports two measured averages that do not satisfy the formula linking them — which is common
   here, because an average of squares is not the square of an average. The deterministic checker
   separates the two questions; the rubric does not. If teachers are handed it as written, the
   human κ inherits the same ambiguity and will be uninterpretable. This is cheap to fix and it
   blocks the measurement the whole project is waiting on.
5. **The "at rest" boundaries are wrong, not just their caption.** The caption is now suppressed
   wherever the curve contradicts it, which stops the figure asserting something false — but the
   decision about which stretches count as at rest is still inaccurate (on one clip the rest band
   begins about half a second before the object stops, and the traced-path plot confirms it
   independently: its grey "inactive" points cover about 0.28 m of real arc). Suppressing a caption
   is not the same as fixing the thing it was describing.
6. **Four figure defects found by the figure judge and not yet fixed.** In order of how much they
   mislead: the dashed line labelled **"clip average" is really the average over the turning part
   only** — on one clip it sits far above almost the entire curve, so a reader taking the average
   off the graph is badly wrong, and it is mislabelled on *every* time-series plot; two of the
   basic turns-vs-time graphs show the object speeding up beneath a caption saying it slows; the
   measurements table lists an inward pull that does not equal turn-rate-squared times radius, and
   the intermediate tier walks the reader through that multiplication and states the wrong result
   (the same ambiguity as item 4); and on three clips the fitted circle sits 9–21% of a radius
   from the traced points while the basic passage says "every point falls on one circle".
7. The 42 Bahasa documents embed the pre-fix figures and need a re-run.
