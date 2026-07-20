# Material critique — flick job `e6fed2e9` vs P-MAGIC (2026-07-14)

Judgment of the generated 3-tier learning material (`workspaces/job_e6fed2e9-b757-4c4a-9320-8c68e8ef282b/
analysis_output/report/student_edition.{basic,intermediate,advanced}.pdf`) against Vinsa's paper
`document-4.pdf` (P-MAGIC, J. Educ. Computing Research): its Fig 4/5 example MPPs, Table 2 teacher
rubric (linguistic / physics / image-text / text-graph / text-table), and Table 7 results (teachers
scored their MPPs 8.2–8.6 / 10, κ 0.63–0.83).

**Part A** = correctness / alignment defects → fix backlog (each with evidence, root cause, fix path).
**Part B** = pedagogical *design* critique → discussion items (spec decisions, not bugs).

> **STATUS (updated 2026-07-14).** This document is the original audit record. All of **A1–A8** and
> **C1–C5**, plus the agreed Part-B items (**#2** answers→teacher key, **#3** qualitative basic answer,
> **#5** tangent-release misconception item), are now **FIXED, committed, and live-validated** in golden
> job **`9ed918d0`**; the render-aware `annotation_correctness` gate (Axis 4) is **built**. Remaining is
> **design/pedagogy only** — A7 two-scenario comparison, a per-phase colour-coded table (C4 upgrade),
> the predict/POE box, contextualising definitions, noticing prompts, magnitude anchoring, and Bahasa
> deployment. Current status source-of-truth: `SESSION_CHECKPOINT.md` §00.

Verdict in one line: the tier architecture, grounding, worked examples and honesty box are ahead of
P-MAGIC; but Part A items A1–A3 are silent correctness failures (grounded numbers narrating a motion
that didn't happen that way), and none of A1–A8 is a 35B limitation — they are seed/prompt/gate/renderer
bugs that would bite GPT-4o too.

---

## Part A — correctness & alignment defects (fix backlog, priority order)

### A1. Rate × whole-clip duration (wrong by ~2.4×) — HIGHEST
**Evidence.**
- Basic, Worked example 2: “laps = turns each second × seconds: **0.91 × 5.87 s ⇒ ≈ 5 laps**” and
  “the red phone goes round about 5 times.”
- Intermediate, CYU Q3: “How far does the red phone travel along its arc during the whole 5.87 s clip?
  Answer: **s = v·t ≈ 0.856 × 5.87 ≈ 5.02 m**.”

**Why wrong.** The phone is at rest until t≈2.1 s and stopped by t≈4.5 s (visible in the ω(t) figure);
it turns for only ~2.4 s. f = 0.907 Hz and v̄ = 0.856 m/s are averages over the ACTIVE window, so
laps ≈ 0.907 × 2.4 ≈ **2.2** (not 5) and arc ≈ **~2.1 m** (not 5.02 m). The material's own scenario
narrates rest → flick → stop, so it contradicts itself. Teaches students exactly the misuse of
averages the honesty box warns against.

**Root cause.** The prompt facts give clip length + rates but never state the turning time or a rule.
`tracking.active_start_s/active_end_s` have been persisted in the seed since the 07-08 commit — they
are just not surfaced as a constraint. The gate's arithmetic check verifies the product *computes*
(0.91×5.87 ≈ 5.3 ✓) but not that the *duration is the right one* → a gate blind spot (modeling error,
not arithmetic error).

**Fix.**
1. `material_tiers._facts`: add “it turns for {active_dur} s of the {clip_len} s clip” + hard rule:
   any laps/distance/rate×time claim uses the turning time, never the clip length.
2. `material_gate`: new check class — for non-uniform/impulsive clips, flag any rate-quantity ×
   duration≈clip_length product when active_dur < ~0.9×clip_len; run `seed_consistency`-style
   verification over CYU answers too (s = v·t is machine-checkable).
3. Offline-verifiable against this job's material JSON before any live run.

### A2. Clip-average period attached to the peak moment (all 3 tiers)
**Evidence.** Shared Scenario paragraph: “Right after that flick, **it reaches its fastest pace,
completing a full circle about every 1.1 seconds** as it begins to coast.”

**Why wrong.** 1.102 s = 2π/⟨ω⟩ is the clip average. At the post-flick peak (ω≈9.37 rad/s) a lap takes
2π/9.37 ≈ **0.67 s**. Average-as-instant confusion embedded in every tier's opening paragraph.

**Root cause.** `FRAME_SYSTEM` is handed only the average period; no peak period, no steer. The model
attached the only number it had to the most dramatic moment.

**Fix.** Hand the frame both numbers with labels (“at its fastest a lap takes ~0.67 s; averaged over
the whole spin, ~1.1 s”) + rule “clip-average values describe the whole spin, never ‘right after the
flick’”. Optional gate heuristic: peak/fastest wording within N chars of the average-period value.

### A3. Advanced timeline instants straddle the peak → self-contradictory narrative
**Evidence.** Advanced, “What the video shows over time”: opens “distinct phases of **decay**”, then
“Early in the clip at t = 2.09 s … ω = 2.687 rad/s … at t = 3.37 s the turn rate **has climbed** to
4.802 rad/s”, then in the same paragraph “the turn rate **decreases linearly** with time.”

**Why wrong.** t = 2.09 s is on the impulsive RISE; ω actually went 2.687 → ~9.8 (peak ~2.3 s) → 4.802.
“Climbed” between those instants misdescribes the motion and directly contradicts the α<0 linear-decay
claim two sentences later. Every number is grounded; the connective narrative is false — second gate
blind spot (grounding ≠ narrative faithfulness between instants).

**Root cause.** `TIER_ANCHORS` worked-instant selection is phase-unaware; it sampled instants on both
sides of the peak.

**Fix.** Constrain anchor selection to within one phase (post-peak/coast-down for impulsive clips) —
`stats.json.phases` is reliable post-`4cba56f`. Optional gate check: if the narrative is decay-framed,
the sampled (t, ω) sequence must be monotone non-increasing.

### A4. Basic tier figure–text misalignments (P-MAGIC “image–text precision” dimension)
**Evidence.**
- Figure 2 caption (deterministic, `FIG_META`): “…so the angle **grows steadily with time**” — on a
  decelerating clip whose learning objective is *“See from the picture that the red phone is gradually
  slowing down.”*
- Same caption says “Where the object is **after each second**” but the dots are quarter-turn
  milestones spanning only the first ~0.8 s of motion.
- CYU Q2: “The dots **marking each second** sit a little closer together **near the end of the clip**…”
  — that visual feature exists in NO figure (the model faithfully repeated a stale figure description
  we handed it).
- Figure 1 label “radius **0.15 m**” vs prose 0.148 m; milestone label “**0.6 s**” vs prose 0.58 s.
- Basic Scenario begins “Red Phone on a Black Circular Base The red phone rests…” — story title
  concatenated into the first sentence with no separator (render bug, basic only).

**Root cause.** Caption text written for uniform clips; manifest/prompt figure description stale
(describes per-second dots from an older figure design); inconsistent rounding between figure labels
and prose; `report.py` title join.

**Fix.** Motion-aware caption; correct the manifest `shows`/prompt text to milestone semantics; unify
rounding; fix the title separator. This is also the natural first customer for the planned
deterministic `annotation_correctness` gate check (prose figure-references validated against
`figure_qa.json`) — the Axis-4 eval.

### A5. Phase-figure labeling + unreconciled means (P-MAGIC “graph accuracy & proper labeling”)
**Evidence.**
- Int/adv prose: “highlights **three distinct phases: speeding up, steady, and slowing down**” — the
  rendered ω(t) shows only ONE printed band label (“slowing down”); the INCREASE band is shaded but
  unlabelled, STABLE is not discernible.
- The DECREASE band ends ~4.0 s while the curve visibly declines to ~4.5 s (sub-threshold tail counted
  INACTIVE — defensible, but the student sees the curve still falling in a “no phase” zone).
- a_c(t) dashed line legend “**stable mean**” (~8.5) vs Table 1 “Mean centripetal acceleration
  **5.69**” — two different means, never reconciled (ω(t) correctly says “clip average”).

**Fix.** `figures.py`: print every band's label (stagger or legend); align the a_c reference line with
the canonical mean (or legend it honestly + footnote); prose should enumerate only phases that render.

### A6. Authentic-context gap (known; prof-req)
**Evidence.** Scenario is a lab-ish contrived scene (no who/where/why). Every P-MAGIC example wraps
the data in a learner role and purpose (“You are analyzing the spinning mechanism of a vegetable
washer **for your physics project**…”; easy item: “You are observing an outdoor fitness double
wheel…”). Their “Realistic” rubric dimension would be Centri's weakest score.

**Fix (known path).** `FRAME_SYSTEM` already builds the 5W+1H story when the sidecar carries a
learner's note — the flick sidecar has none. Write one, or use real-phenomenon videos (prof:
playground toys).

### A7. Structural absences vs P-MAGIC
1. **The table is the unannotated modality.** Their tables have phase-colored rows (green/yellow/red,
   Fig 4/5); our Table 1 is a static summary. Matters because the thesis contribution is *multimodal
   annotation*.
2. **No two-scenario comparison at advanced.** Their advanced level = compare Fan Exp1 (0.13 m) vs
   Exp2 (0.17 m) across phases — Analyze-level, multi-step. Single-video Centri can't produce it;
   our advanced CYU items are plug-in computations (Apply), below the tier's own exposition level.
   Options: pair two jobs/clips; or a within-clip comparative hypothetical (“same flick on a base
   twice as wide…”); or compare two phases of the same clip quantitatively.

### A8. Minor wording / precision issues
- “the **inward pull** … which is 5.686 **meters per second squared**” (basic): force language with
  acceleration units — seeds the classic force/acceleration confusion; teacher raters may dock
  “concept understanding”.
- 4-sig-fig precision at basic (0.907, 1.102, 5.686) — cognitive-load overkill for the tier (P-MAGIC's
  easy level deliberately omits specialist detail; it scored *higher* on readability for it).
- “with its **outer edge** about 0.148 m from the center” — the tracked point is the phone body, not
  its outer edge; invented detail.
- Advanced figure chip **“a”** is ambiguous where the tier also introduces a_t (prose “a = 5.69 m/s²”
  vs table a_t = −0.62 m/s²). Consider a_c on the chip, or state the chip convention.
- Intermediate “The variables we measured” paragraph repeats Table 1 verbatim — duplication with no
  added interpretation.
- Intermediate “What the video shows over time” is ONE sentence (thin; the phase-shaded graph sits
  right under it, unnarrated). Steerable: minimum-content rule “tie each rendered phase to a number
  from the manifest.”

### Fix order (suggested)
A1 (seed fact + gate check) → A3 (phase-constrained anchors) → A2 (frame numbers) → A4/A5
(captions/manifest/labels) → A6 (sidecar note) → A7/A8 as design capacity allows.
A1–A5 are offline-verifiable against this job's artifacts. Live regen does NOT need SAM3 (down):
the flick template is cache-HIT — lab2 API/worker/redis + Qwen 35B suffice.

---

## Part B — pedagogical design critique (discussion items, not bugs)

These are spec-level decisions about what the material IS, prompted by reading it next to P-MAGIC's
items and their teacher rubric.

1. **Genre: a measurement report wearing a textbook's clothes.** The recurring frame is “We measured X,
   which is Y” — the learner is a spectator of our pipeline. P-MAGIC consistently casts the learner as
   the agent (“You are analyzing… for your physics project”). Nothing in our material asks the learner
   to DO anything with the video — the one artifact that differentiates Centri is treated as a data
   source, not a learning activity.
2. **CYU answers are printed in the STUDENT edition**, in italics directly under each question. Zero
   retrieval-practice value — the student reads the answer before attempting. The teacher key exists
   precisely to hold answers. (Move answers to teacher key only, or end-of-doc inverted.)
3. **Assessment tests untaught content (basic).** CYU Q1 answer asserts the inward pull “**doubles**
   when the radius doubles” — a quantitative proportionality the basic tier never taught (its
   relations section is qualitative by design). Assessment–instruction misalignment.
4. **Bloom misalignment at advanced.** Objectives and exposition are Analyze-level; all three CYU items
   are Apply-level plug-ins. (Ties to A7.2.)
5. **No misconception work.** The circular-motion literature is dominated by ONE misconception
   (centrifugal “outward throw” / what happens on release). The material never confronts it — no
   “if the phone were released, which way would it fly?” item. Cheap to generate, high value, and a
   natural CYU upgrade.
6. **Definitions are a decontextualized glossary.** The basic “What these words mean” section is
   correct but never mentions the red phone; each definition could bind to the visible object
   (“the radius here is the distance from the base's centre to the phone — the yellow line in
   Figure 1”). CLT pre-training argument supports the placement; contextualizing strengthens it.
7. **“Reading the figures” does the interpreting FOR the student.** It transcribes each figure into
   prose, leaving nothing to notice. P-MAGIC's rubric explicitly rewards “creativity and critical
   thinking … deeper insights based on interpretation of graphical data.” Convert (partly) into guided
   noticing prompts (“find where the curve is steepest — what is the phone doing there?”).
8. **Magnitude anchoring is uneven.** “About the pace of a brisk walk” (intermediate, for v) is exactly
   right — but 5.69 m/s² gets no anchor (≈0.6 g, “about half of gravity's pull”), nor does 5.79 rad/s
   (“just under one turn per second”). Extend the anchoring pattern to a_c and ω.
9. **Language.** Target learners are Indonesian high-schoolers; P-MAGIC evaluated in Bahasa. Our
   `tools/translate_material.py` (Bahasa, numbers preserved) exists but is not wired into the pipeline
   or the eval story.

**Kept strengths (don't regress):** definitions-first basic; measurable Bloom/CLT ladder (FK grades
7.8→8.1→11.7); worked examples that close arithmetically; Measurement-honesty box (Jensen, calibration
independence — no P-MAGIC analogue); “Ready for more?” tier links; Vinsa-style annotated frame +
phase-shaded graphs.

---

## Part C — multimodal artifact inspection + student walkthrough (same day, full-res artifact pass)

Inspected the actual generated artifacts (`analysis_output/plots/*.png`, frames from
`video_annotation/annotated_video.mp4`), not just their appearance in the PDFs. Converges with the
user's own `note-7-9` (peak stars, arrow-placement gate, all-three-phase labels).

### C1. ⚠ CORRECTNESS — the video turns CLOCKWISE on screen; all prose says counter-clockwise
Frames at t = 2.15 / 2.35 / 2.55 s show the phone at LEFT → TOP → RIGHT: **clockwise as viewed.**
The header (“Direction: CCW”), the scenario (“sending it turning counter-clockwise”, ×3 tiers) and
basic's over-time narrative all say counter-clockwise. `stats.rotation_direction="CCW"` is computed
in y-down image coordinates (or y-up math on image data) and never converted to the VIEWER frame —
the same CW-inversion family as the `_phases` signed-ω bug fixed in `4cba56f`, surviving in the
display string. The milestone figure (`angle_points_basic.png`) has its y-axis correctly inverted to
match the video, so its displayed dot sequence ALSO reads clockwise — the words are the only wrong
channel. A student who watches the video and reads the text gets a direct contradiction on the very
first physical fact. **Fix:** convert `rotation_direction` to viewer frame at the seed boundary (one
sign flip) + a deterministic gate check (direction word in prose vs viewer-frame sign). Also: NO
artifact actually shows the turn direction (see C3) — the annotation that should settle this is missing.

### C2. Phase rendering on ω(t)/`annotated_graph.png` — manifest promises 3, render delivers 1
Full-res `omega_t.png`: INCREASE band (orange, 2.1–2.72 s) has **no printed label**; a STABLE band is
**not visible at all**; only DECREASE prints “slowing down”; the DECREASE shading ends at 4.0 s while
the curve visibly falls to zero until ~4.55 s (sub-threshold tail unshaded — the student sees the
line still dropping in a “no phase” zone). Meanwhile `figure_qa.json` for omega_t lists all three
phases (increase/stable/decrease) — which is what the material prose quotes (“three distinct
phases”). **The manifest and the render disagree** → the planned `annotation_correctness` gate must
verify the RENDERED artifact, not prose-vs-manifest only. Also unexplained on the graph: the
pre-flick NEGATIVE dip (ω≈−0.4 rad/s at 1.6–2.0 s — the hand touching) and the small bump at ~3.1 s
inside “slowing down” — both are exactly what a curious student asks about, and prime honesty-box /
noticing-prompt material. `annotated_graph.png` is `omega_t.png` with a different title — a duplicate.

### C3. Annotation conventions are inconsistent across modalities and never taught
- **Still image** (`annotated_image.png`): symbol chips WITH values (r 0.148 m / ω 5.79 rad/s /
  a 5.69 m/s²). **Video overlay**: symbol chips WITHOUT values (r, v, a_c, ω + legend header).
  Opposite conventions; P-MAGIC's app is unit-only. Pick one story.
- The still image pins **clip-average values onto one frozen frame with no qualifier** — Table 1 says
  “(clip average)”, the chip doesn't. On a clip where ω ran 0→9.8, the figure quietly contradicts the
  honesty box. Either unit-only chips (Vinsa) or “ω̄ 5.79 rad/s (avg)”.
- The video border is **phase-coded** (orange during spin-up frames, red during slow-down) — a nice
  hidden feature that NOTHING documents (not the legend, not the prose). Undocumented channel = noise.
- The video's v/a_c arrows are ~30 px — barely legible; directions look correct (v tangential, a_c
  inward) but need length/width scaling. No curved direction arrow exists on the video at all, and
  the still's ω arrow is small — no artifact answers “which way does it turn?” (ties to C1).
- Video legend says “v = tangential velocity” vs intermediate prose “speed along the path” (minor).

### C4. The table modality is neither annotated nor delivered
`annotated_table.png` is a **plain** table (no phase-coloured rows — P-MAGIC colours table rows
green/yellow/red by phase, Fig 4/5), is embedded in **no** student edition (`\includegraphics` audit:
only ac_t, angle_points_basic, annotated_image[_basic], omega_t, trajectory[_basic]), and leaks
internal vocabulary the typeset Table 1 correctly avoids (“Std radius”, “Stable centripetal accel.
8.55”, literal “m/s^2”, three radii: mean 0.147 / fitted 0.148 / std 0.001). Of the four claimed
annotated modalities (image, graph, table, video), the table is unannotated + orphaned and the graph
is partially labelled — the multimodal-annotation thesis claim currently holds for ~2.5 of 4.

### C5. Basic-tier figure set fails its own objective (student walkthrough, basic)
Objective 4 promises “**See from the picture** that the red phone is gradually slowing down” — no
basic figure can show it: Figure 1 is static; the milestone figure covers only the first ~0.8 s with
near-evenly-spaced dots (so it shows *steady* turning); the trajectory has no time axis. CYU Q2 then
asks about per-second dots bunching near the end — the **phantom figure is exactly the missing
artifact**. One change closes objective + caption + CYU simultaneously: make `fig_angle_points` plot
full-clip per-SECOND dots (they visibly bunch as it slows) instead of quarter-turn milestones of the
first turn.
Also in basic: `annotated_image_basic.png`'s radius arrow points RIGHT from the centre toward empty
base — where the **metal ruler** happens to lie (the calibration prop, mentioned nowhere in any
tier). The phone is at bottom-left; the student's eye follows the arrow to the ruler. The chip-style
r-line (toward the phone) is better; and “radius 0.15 m” label vs 0.148 m prose (A4).

### C6. Student walkthrough, intermediate/advanced (sequencing)
Intermediate: Figure 1 chip asserts ω = 5.79; two pages later Example 1 uses ω = 7.61 “at t = 2.72 s”.
The average-vs-instant resolution lives in the honesty box at the END — the confusion is created
before the tool to resolve it is given. Cheap fix = the “(avg)” qualifier on the chip (C3) + one
clause at first use. Advanced: same, plus the A3 “climbed” contradiction, plus the a_c(t) “stable
mean” dashed line (8.55) vs Table “Mean centripetal acceleration 5.69” with no reconciliation — the
orphaned annotated_table shows both under distinct names, but the student never sees it.

### What Part C adds to the fix backlog
- **C1 → promote to top-3 with A1** (direction sign to viewer frame + gate check).
- The `annotation_correctness` gate (A4) must be **render-aware** (manifest ↔ rendered labels), not
  prose↔manifest only — C2 is the proof case.
- Unify chip convention across still/video (values-with-qualifier or unit-only) + document the
  phase-border; enlarge vector arrows (C3; user note-7-9 “arrow … placed correctly (need separate
  gate)” = the same ask).
- Phase-colour the table rows and EMBED the annotated table (or drop the artifact) (C4).
- `fig_angle_points` → full-clip per-second dots (C5; fixes A4's phantom-dots CYU legitimately).
- Kill peak stars (user note-7-9) — still present on ac_t.
