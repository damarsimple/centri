# Centri weekly memo — the three levels, reworked

Companion to `centri-weekly-2026-07-27.pdf`. The deck is for the room; this is for reading cold.
Every claim on a slide appears here with its definition, its caveat, and the number behind it.

**What Centri is.** A phone video of something spinning goes in; measured kinematics and a set of
physics worksheets at three difficulty levels come out, with the figures drawn onto the footage
itself. Nothing is typed in by hand. The parent line is the Utami dissertation (SocioMathLLM,
Geo-QG); the sibling app P-MAGIC does the same from phone *sensors* rather than video.

**Vocabulary used below.** *Tier* — one of the three levels (basic / intermediate / advanced).
*Seed* — the file of measured values the writing is built from; every number in a worksheet must
trace back to it. *Gate* — the automatic checker that reads a finished worksheet and refuses it if
a number doesn't trace, an equation doesn't close, or the wording breaks a tier's rules. *Element
interactivity* — from cognitive load theory: how many distinct quantities, plus the relations
linking them, a reader must hold at once.

## The direction-sign defect

`motion_type` was read from the sign of the fitted angular acceleration. Both ceiling-fan clips
turn in the direction the tracker calls negative, so a coast-down fitted a *positive* value and one
basic worksheet taught "speeding up motion" over a graph that plainly showed slowing. It is now
read from d|ω|/dt — the rate of change of *speed*, which has no sign convention to get wrong — and
a single reader-facing view (`common.motion_along_travel`) is the only thing the writing sees.
**Two of seven clips were affected; the other five are unchanged to the digit.**

## Reading level

The material used words no high-school reader has: *calibration-independent*, *scale-free*,
*Jensen's inequality*, ⟨ω⟩. These are now banned from student text, with the formal statement
re-routed to a teacher-only block. Basic went from **15.8 to 8.2 words per sentence, reading grade
7.2 to 4.3**.

The cause was not vocabulary. Syllables per word barely move between levels (1.41 / 1.43 / 1.51);
sentence length does. Basic read hardest because it *explains* in long sentences where the other
levels state things in short ones. **"Plain words" and "plain sentences" are not the same thing.**

## What the reader now does

The material was exposition — a passage to read. Reading is among the weakest routes into physics,
so five things were added, all computed rather than written, with every answer held back for the
teacher's copy: a **prediction** demanded before any measurement is shown; a **checkpoint** closing
each of the three steps; the **common wrong answers** named and asked about; a **transfer** question
set on a different object; and a **self-placement** block so a reader can tell whether they are on
the right level. Advanced additionally **fades** its worked examples — the first is worked in full,
later ones stop before the last step.

## Measuring the ladder

Whether the levels really get harder is measured from the finished prose, not asserted.

| | basic | intermediate | advanced | verdict |
|---|---|---|---|---|
| ideas held at once | 4.9 | 13.9 | 44.9 | **rises on 7/7 clips** |
| words per sentence | 8.3 | 7.1 | 12.4 | advanced longest, not basic |
| reading grade | 4.6 | 4.3 | 6.6 | advanced hardest, not basic |

**The reading-grade ladder does not exist and should not be claimed** — it rises on 1 of 7 clips,
and intermediate reads easiest of the three. This is not a defect in the material. Flesch-Kincaid
sees only sentence length and syllables per word, so it cannot see an equation: `a_c = ω²r` is a
handful of short tokens. The level whose difficulty is carried by symbols therefore scores as the
easiest prose, while element interactivity — which counts the relations too — ranks it correctly.
Report reading grade; never optimise it.

## Checking every worksheet

**19 of 21 worksheets pass every check.** The residue: one advanced tier used the banned word
"frame"; one intermediate invented an ungrounded "1.8 seconds"; `computerfan-4029` reuses another
tier's worked instant; `turntable-3` states a period of 1.469 s against 2π/ω = 1.176 s without
flagging it as an average.

Two cautions. The gate **flags but does not withhold** — all 21 worksheets shipped as PDFs with
their issues recorded. And **21/21 does not reproduce**: an earlier offline run scored 21/21, a
true end-to-end re-run scored 19/21. The difference is the writer's randomness, so single-run
figures should be quoted with the run named, or replaced with a mean across runs.

## A defect the gate could not see

One worksheet says a full turn takes 2.07 s, then that "**that** turn rate" is 0.30 turns per
second — which is a 3.34 s turn. Both numbers are real: 2.07 s is the fastest lap, 0.30/s is the
clip average. Every number traces to the seed, so the gate passed it; the fault is the pronoun
tying an average rate to an instantaneous period. A new deterministic rule now catches it: it fires
on six of the 21 worksheets, all of them at basic level, and it agrees with an independent LLM
judge clip for clip — the same six flagged, the same one clean.

Trying to fix it by *instruction* — telling the writer not to do this — made things worse:
regenerating dropped the gate from 19/21 to 16/21, the judge from 4.12 to 3.90, and broke the
element-interactivity ladder on one clip, while clearing only 2 of 6 instances. That generation was
discarded. **The lesson is that a prompt rule cannot make a model careful about a referent**; the
fix is to hand the writer a period and rate already paired to the same moment, so the contradiction
cannot be written.

## Automatic scores, and what they are worth

BERTScore against an authentic textbook (OpenStax §6.2): **0.818 ± 0.014** whole-passage (n=21),
0.822 ± 0.015 per section (n=105), precision 0.820, recall 0.816, diversity 0.308. N-gram overlap,
reported alongside because the parent line reports it: BLEU-4 0.029, ROUGE-1 0.352, ROUGE-L 0.163.
Against 19 independent references: 0.798 ± 0.006, with the textbook still the best match at 0.818.
P-MAGIC's fifth metric, an LSTM fluency score, is **not reported** — it needs their trained model,
which we do not have.

These numbers did not move when the material was reworked — the entire pedagogy change shifted them
by 0.005, less than one standard deviation, slightly downward. Per level they run basic 0.799 <
intermediate 0.824 < advanced 0.830, because the metric rewards resemblance to a college textbook:
**making the beginner text more readable makes this score worse.** Choosing a different reference
moves it by 0.04 — eight times what the rework did. BERTScore belongs in the results table as the
row that lets these numbers sit beside P-MAGIC's, and nowhere else.

The LLM judge — 21 worksheets scored 1–5 on twelve criteria, the rubric reconciled from Utami and
P-MAGIC — is the one automatic measure that responds: cognitive demand 2.86 → 3.86 → 4.71 up the
levels, and the achieved Bloom level is now
Understand / **Apply** / Analyze, where intermediate previously stalled at Understand. Grounding
accuracy at advanced rose from 1.0 to 4.43. It is scored by the same model family that wrote the
material, so it is evidence, not proof.

> **⚠ RETRACTED 2026-07-31 — the paragraph below is wrong about `turntable-3`.** The 7.45 m/s² it
> defends is a tracking artifact: the marker teleports 604–713 px in single frames three times in
> that clip, one of them inside the measured window, and the jump-free figure is 5.85. The judge
> was right to flag it. The averaging effect is real but smaller (5.85 vs 4.99, a 17% gap, not
> 28%). The sentence "where the judge and the checker disagree, the checker has been right" is
> also withdrawn: the checker verifies that a number *traces to the measurement*, which 7.45 does,
> and cannot ask whether the measurement is sound. **Tracing is not validating.** The `turntable-1`
> arithmetic point below still stands. See `centri-weekly-2026-08-05-memo.md`.

Its weakest column is grounding — 2.1 / 2.7 / 4.4 up the levels — and that column must be read with
care, because part of it is the judge's own arithmetic failing. It marked `turntable-1` wrong for
writing 8.04² × 0.438 = 28.3, which is right to three figures. It marked `turntable-3` wrong for
giving an average inward acceleration of 7.45 m/s² when squaring the average turn rate gives 5.82 —
but the gap between those two numbers *is* the point that passage teaches, that the average of the
squares is not the square of the average, and the text labels both as clip averages. Where the
judge and the deterministic checker disagree about a number, the checker has so far been right;
where the judge saw something the checker could not, it was the referent defect above. **Use the
judge for whether a passage teaches, not for whether it computes.**

## Bahasa Indonesia edition

All 42 documents (7 clips × 3 levels × student and teacher) are built in Bahasa Indonesia for the
teacher panel, beside the English as `translated_*.id.pdf`. Translation runs on the rendered
worksheet, not the model's prose alone — only 17–27% of a page is that prose; the rest is the
scaffolding described above. Every number and symbol is verified against the English before a file
is kept, and a fixed glossary holds the terms steady across levels (*jari-jari*, *kecepatan sudut*,
*percepatan sentripetal*). Decimals stay in international form (0.26, not 0,26) so the
number-preservation check remains valid; localise at display time if the panel prefers commas.

## What is still unproven

Everything measured so far is a property of the **text**: whether its numbers are right, whether it
can be read, whether it asks anything of the reader. **Nothing measures whether anybody learns from
it.** P-MAGIC has ten teachers rating at 8.2–8.6/10; Centri has one expert reader and one model
judge, and the model cannot stand in for either a teacher or a learner. Teacher ratings
are the next step, and they are the only thing that answers the question the project is actually
asking.
