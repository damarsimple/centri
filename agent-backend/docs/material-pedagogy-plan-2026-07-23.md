# Material plan from the 07-22 feedback (rough draft, 2026-07-23)

Source: `note-7-22` — Vinsa's review of the 3-tier material + Damar's own reading.
This is the LITE plan for discussion. Deeper scoping is in flight.

Everything below is verified against the current code, not assumed. File references are real.

**Status 2026-07-27: workstreams 1–4 are BUILT, live-validated on all 7 clips, and pushed.**
`21 of 21` worksheets pass every check. The three open questions were decided: three documents with
three graded sections inside each; B3 = "how long to slow from this speed to that one", read off
the graph; C3 = "which claims does this video actually support?"; and the
measurement-and-correction figure is drawn for BOTH adjustments (the camera-angle correction and
the one-revolution average), each naming itself in the legend.

**A second pass followed**, answering a pedagogical audit of the result — see §5 below. The
material was exposition; it now asks the reader to predict before the reveal, clear a checkpoint at
each step, confront the documented misconceptions, and carry the idea to a second setting, with
faded worked examples at the advanced level and a self-placement note at the top of each edition.

Three defects were found on the way and fixed:
- the advanced averaging example compared the shortcut against a third number modelled over a
  *different* averaging window, printing the inequality backwards on both fan clips;
- **four** gate flags turned out to be the checker refusing wording or numbers the pipeline itself
  hands the writer (see §6);
- the **basic** tier scored the *hardest* reading grade of the three, from sentence length rather
  than vocabulary (§7).

---

## In one line

Vinsa says the tiers are right but the **ladder is too coarse**: basic is fine, intermediate jumps to
equations too fast, advanced reads like a graduate paper. We're going to (1) fix what is outright
wrong, (2) lower the reading level of advanced, (3) put a real ramp inside each tier.

---

## Workstream 1 — Correctness first (no design input needed)

**1.1 A slowing fan is being taught as "speeding up."**
Found while chasing Damar's "why is ω negative" note. `kinematics.py:348` decides
speeding-up-vs-slowing-down from the SIGN of the fitted α. Both ceiling-fan clips turn the other way
round, so their ω is negative all through; a coast-down (|ω| falling 9.5 → 0.03 rad/s) fits α = +0.17
and gets labelled **"the object is speeding up."**

- It reaches students: `fan-4027`'s BASIC worksheet lists *"speeding up motion"* as a concept taught.
- The material contradicts its own graph — the phase bands are computed on |ω| and correctly read
  "steady, speeding up, steady, slowing down, steady."
- Affects the 2 fan clips only. The turntables, roundabout and computer fan turn the other way and
  are correct.
- Fix: classify on the trend of |ω|; give a_t its sign relative to the direction of travel.

**1.2 Explain the minus sign (Damar's item).** Negative ω currently appears with no explanation —
in one advanced tier it shows as "ω runs from −9.51 to −0.03 rad/s" next to "clip-average ω = 5.7
rad/s." Add one plain sentence: the minus sign only says which way round it turns, not "less than
nothing."

---

## Workstream 2 — Vinsa's two direct asks

**2.1 Advanced is written above high-school level.** Confirmed — the *spec* demands it, so the model
is doing what it was told. Three places name terms she flagged:

| where | what the student currently reads |
|---|---|
| `material_seed.py:224` | objective: "State which measured quantities are independent of the calibration" |
| `material_seed.py:495` | a question: "Which reported quantities are calibration-independent?" |
| `material_seed.py:529–533` | honesty box: "scale-free", "**a Jensen inequality**" |

Plan: keep the *idea*, drop the *vocabulary*, and move the formal version to the **teacher key** —
which already exists as a separate PDF per tier, so this is a re-routing, not new machinery.
Student version says it conceptually ("the angle measurements don't depend on how we sized the
scene; the metre values do"). Jensen leaves the student edition entirely.

**2.2 Read the graph before the equations (intermediate).** Right now intermediate goes
scenario → variables → relations → figures. Vinsa wants interpret-the-graph first, equations after.
Reorder so the turn-rate graph is read in words, and the formula arrives as the compact way to say
what the reader already saw.

---

## Workstream 3 — What each tier shows

**3.1 Basic's picture is too thin.** Basic gets a stripped figure with *only* the radius drawn
(`figures.py:469`); intermediate and advanced get the full marked-up still with speed, turn rate and
inward pull. Damar's call: basic should get the richer picture too. Keeping basic's no-symbols rule,
so labels stay in words.

**3.2 Show the measurement AND the correction.** Where we adjust a curve, draw both — the raw
measurement and our improved version — instead of silently shipping one. Makes the honesty visible
rather than stated.

---

## Workstream 4 — The real ask: sub-levels and bridges

Damar's structure, three steps inside each tier instead of one jump:

| | A — Basic | B — Intermediate | C — Advanced |
|---|---|---|---|
| **1** | which variables are used | apply the equation | compare |
| **2** | how each variable is used | apply it to this clip's data | compare the phases |
| **3** | which equation goes with them | *(open)* | *(open)* |

Plus a **bridge** carrying A3 → B1 and B3 → C1, so the tiers are one staircase, not three separate
documents. Today there is only a one-line teaser at the end of each tier (`material_seed.py:168`).

Advanced also needs to stop being "intermediate plus more numbers" — the differentiator is
**comparison and analysis** (Bloom: Analyze / Evaluate), e.g. *how long does it take to slow from
this speed to that one*, phase-against-phase, scenario-against-scenario. That question type is
already half-built as an advanced check-yourself item and can be promoted.

---

## Open — needs a decision

1. **Nine documents, or three documents with three graded sections inside each?** This changes how
   much of the pipeline moves.
2. **What are B3 and C3?** The note trails off on both.
3. **"Draw our measurement and our adjusted"** — the perspective-corrected roundabout specifically,
   or raw-vs-smoothed on every turn-rate graph?

---

## Suggested order

1 → 2 → 3 are contained and testable without the language model running (we can replay the
deterministic tail of an existing clip in ~5 min per run). 4 is the design conversation — worth
settling 1–3 first so the restructure lands on material that is already correct and readable.

---
---

# Second pass (2026-07-27) — what a pedagogical audit of the reworked material found

Workstreams 1–4 fixed what was *wrong* and what was *unreadable*. They did not change what the
material fundamentally is. This section records the audit of the result and what was built from it.

## 5. It was exposition, and now it is not

`material_tiers.SYSTEM_TMPL` HARD RULE 2 says it outright: *"This is exposition ONLY — no
questions, quizzes, 'try this', or exercises."* The check-yourself items were appended at the end.
So the artefact was a well-graded passage to **read**, and reading is among the weakest routes into
physics. A worksheet built from a video can do better, because a textbook cannot stop before the
reveal and a video can.

Five additions, all deterministic (`material_seed.py`), all with the answer held for the teacher
copy:

| block | seed function | where it renders |
|---|---|---|
| predict before the measurement is shown | `_predict_first` | before the first section |
| a checkpoint closing each of the three steps | `TIER_STEPS[*]["after"/"check"]` | at the section that step ends at |
| the documented misconceptions | `_misconceptions` | after the honesty box |
| a transfer prompt in a different setting | `_transfer` | before the closing questions |
| self-placement ("is this the right level for you?") | `_placement` | first thing in the document |

Plus **faded worked examples** at advanced (`fade` on every example after the first): the first is
worked in full as a model, the rest show the setup and stop. A fully worked example is what a
novice needs and what stops helping once the schema is there.

**The kinematics fence is the honest limit.** Gate rule 8b bans naming a cause, so the misconception
cluster that lives in the dynamics — centrifugal force as a real outward push, centripetal force as
an extra force rather than a net one — is out of reach. `_misconceptions` poses only the three a
motion-only treatment can actually correct, and says so in its docstring. **Whether to move that
fence is a teaching decision, not a code change.**

## 6. THE recurring class of bug: the pipeline asks for what its own gate refuses

First identified 2026-07-20 (two instances). The full regeneration raised it **four more times in
one run** — it is now the dominant fault class, and it matters more than the pass rate because it
costs quality silently on every run. Each time, the checker refused wording or a number the
pipeline had itself handed the writer:

1. the elapsed time between two timeline instants — which is the answer to the new B3 step;
2. *"a brief steady spin"*, on a clip whose ω(t) figure DRAWS a steady band, prints the word on it,
   and whose phase list we feed the writer;
3. `(average ω)²·r` read as a rate × the clip length, because the exponent looked like a factor and
   turntable-3's 5.79 rad/s happens to sit within 3% of its 5.87 s clip;
4. *"this clip covers only 1.47 revolutions"* — a sentence `_quality_policy` **dictates**.

All four are fixed and pinned by a test that also checks the real fault still fires.
**Rule: before adding a check, ask what the pipeline already puts in the writer's mouth.**

## 7. Plain words are not plain sentences

The **basic** passage scored the highest Flesch-Kincaid grade of the three tiers — the level aimed
at the least fluent reader was the hardest to read. The comfortable reading ("sentence difficulty is
the wrong ruler for a tier whose job is to avoid compression") is wrong, and decomposing the score
settles it:

| | basic | intermediate | advanced |
|---|---|---|---|
| syllables per word | 1.41 | 1.43 | 1.51 |
| words per sentence **(before)** | **15.8** | 10.1 | 11.5 |
| words per sentence **(after)** | **8.2** | 7.2 | 12.0 |
| FK grade (before → after) | 7.2 → **4.3** | 5.2 → 3.7 | 6.7 → 6.6 |

Vocabulary is flat across tiers; sentence length is not. Basic read hard because it **explains** in
long sentences where the other tiers state in short ones. A per-tier `sentences` policy asks basic
for ~12 words, and `material_gate.readability` reports words/sentence, ease and FK grade into the
gate JSON with a warning above 14 words at basic.

**Reported, never enforced** — this is a style signal, not a correctness one. Note also that the
first threshold written for it (22 words) would never have fired on any clip: measure the
distribution before setting a threshold.

**Stated precisely:** the three are still not strictly ordered by reading grade (intermediate reads
easiest). What changed is that the level for the weakest reader is no longer the hardest to read.
The ladder that *does* hold everywhere is element interactivity: 5 → 19 → 44, rising on 7/7 clips.

## 8. What is still unproven

Everything measured is a property of the **text** — are its numbers right, is it readable, does it
ask enough of the reader. **Nothing yet measures whether anybody learns from it.** P-MAGIC has ten
teachers and a rating of 8.2–8.6/10; this material has one expert reader. Teacher ratings are the
next step and the only one that answers the question.
