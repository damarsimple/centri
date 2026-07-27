# Material plan from the 07-22 feedback (rough draft, 2026-07-23)

Source: `note-7-22` — Vinsa's review of the 3-tier material + Damar's own reading.
This is the LITE plan for discussion. Deeper scoping is in flight.

Everything below is verified against the current code, not assumed. File references are real.

**Status 2026-07-27: workstreams 1–4 are BUILT and offline-verified** (deterministic stages +
tests + LaTeX compile on all 7 trusted clips). Not yet re-run through the language model, so the
generated prose in existing workspaces is still the old text — a live sweep is the remaining step.
The three open questions below were decided: three documents with three graded sections inside
each; B3 = "how long to slow from this speed to that one", read off the graph; C3 = "which claims
does this video actually support?"; and the measurement-and-correction figure is drawn for BOTH
adjustments (the camera-angle correction and the one-revolution average), each naming itself in
the legend. One extra defect was found and fixed on the way: the advanced averaging example
compared the shortcut against a third number modelled over a different window, which printed the
inequality backwards on both fan clips.

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
