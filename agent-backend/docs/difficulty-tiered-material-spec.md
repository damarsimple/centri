# Difficulty-Tiered Learning Material Generator — Spec (Module D)

> Companion to the **question**-tier spec (Module C). That spec generates *tasks the
> learner performs* (Bloom action verbs). **This** spec generates *expository learning
> material the learner reads* — the 5-section passage Subagent D already produces — at three
> content-depth tiers. Same theory, different genre.
>
> Theory: **Bloom's Revised Taxonomy** (Anderson & Krathwohl, 2001) + **Cognitive Load
> Theory / element interactivity** (Sweller, 1994; 2010).
> Target model: **Qwen3.6-35B-A3B** (sparse MoE, ~3B active) — reasoning ON, big token
> budget. See "LLM-specific notes".

---

## 0. Why this differs from the question spec

The question spec measures difficulty by the **cognitive process the learner is asked to
perform** ("define…", "evaluate…"). A passage the learner *reads* performs no task, so for
material we measure difficulty two ways that must agree:

1. **Content complexity (CLT element interactivity)** — how many physical quantities,
   relations, and time-states the passage integrates *at once*. This is the primary lever
   for exposition.
2. **Bloom OBJECTIVE the material equips** — the highest cognitive process the passage
   *scaffolds the reader to do afterward* (Remember → … → Evaluate). Bloom appears as the
   material's target outcome, **not** as task verbs inside the text. The material never asks
   the reader to do anything (no questions — that is Module C's job).

**Difficulty = how many interacting elements the passage integrates (CLT) × the cognitive
objective it builds toward (Bloom).** Both must point to the same tier; if they disagree the
material is mis-designed — rewrite until they agree.

Everything that made Subagent D good is preserved: **grounded strictly on
`material_seed.json` (never invent a number)**, authentic teacher prose, the fixed 5 section
headers, ~light structure. The tier only changes **which concepts the passage introduces and
how deeply it integrates them** — never the underlying measured facts.

---

## 1. The depth ladder is the seed itself

The seed exposes a natural progression. Each tier is defined by **which seed fields it is
allowed to draw on** — this is what makes the tiers reproducible instead of vibes:

| Tier | Seed fields used | Math | CLT interactivity | Bloom objective built |
|---|---|---|---|---|
| **Basic** | `object_name`, `rotation_direction`, `active_duration_s`, `variables[r]`, `period_s` (as plain seconds), the *qualitative* angle-sweep (degrees/turn per second) + the *idea* of an inward pull | none — words only; angle-over-time and one-turn-time in plain language; may *name* a_c but not manipulate it | **low** — one idea at a time | Remember / Understand |
| **Intermediate** | + `variables[ω, a_c, T, f]` with values, + `relations` (a_c=ω²r, T=2π/ω=1/f); tangential speed v de-emphasised (aside only) | the core angular equations, shown structured to hold for *this object's* numbers | **moderate** — a handful of interacting variables in routine formula relationships | Apply / Analyze |
| **Advanced** | + `angular_acceleration` (α, a_t=αr, spin-up/coast-down), + full `timeline` (time evolution), + the squared-sensitivity a_c ∝ ω², + `calibration_note` (scale-free vs absolute) | all of the above plus rates of change and proportional reasoning | **high** — many quantities integrated *simultaneously and over time*, with caveats/limits | Analyze / Evaluate |

Each tier is **cumulative in rigor but self-contained**: the advanced passage may restate the
basics briefly, but its job is the higher-order integration. The basic passage must stand
alone for a novice with no formula introduced.

> If a seed field a tier wants is `null`/absent (e.g. `angular_acceleration` is null for a
> uniform-motion clip), **omit the sentence that would depend on it** — never claim a
> spin-up that was not measured. An advanced tier on a genuinely uniform clip degrades
> gracefully to "the motion is steady, so α ≈ 0" rather than fabricating dynamics.

---

## 1a. Figures are tiered too — the visual load must match the prose

Reusing the full 7-figure + measurements-table set at every tier breaks the CLT premise: a
basic passage that deliberately strips to one variable but is printed next to an angular-
velocity graph, a quadratic a_c(t) curve, and a 13-row table reintroduces exactly the load
the prose removed. So each tier embeds a **figure allowlist** whose visual complexity matches
its content:

| Tier | Figures embedded | Table |
|---|---|---|
| **Basic** | a simplified annotated frame (`annotated_image_basic.png`: circle + radius arrow, no axes/vectors); the **angle-at-time picture** (`angle_points_basic.png`: coloured dots at 90/180/270/360°, each labelled "1.0 s · 90° · a quarter turn", so the growing angle is concrete); the plain traced path (`trajectory_basic.png`, single colour, no phase legend) | **none** |
| **Intermediate** | standard annotated frame, the turn-rate trend (`omega_t.png`), the traced path | **core** (r, ω, a_c, T, f) |
| **Advanced** | annotated frame, `omega_t.png`, `ac_t.png`, the traced path (no `summary_panel.png` — it re-shows every raw plot and duplicates the trajectory) | **full** (adds peak a_c, α, a_t, ω init→final, calibration) |

This lives in places that **must agree**:
- `render/figures.py` emits the basic-tier variants (`annotated_image_basic`, `angle_points_basic`, `trajectory_basic`) alongside the standard plots.
- `render/report.py` `TIER_ARTIFACTS` selects per tier; `_measurements_table(level=...)` gives
  the core/full table.
- `analysis/material_tiers.py` (authoritative) and `tools/generate_tier_material.py` (imports its
  `TIERS`) feed the **same allowlist** into the prompt, so a tier's `Reading the figures` only
  narrates plots it is actually shown (see HARD CONSTRAINT #10).

The basic angle figure's dots come from `material_seed.angle_milestones()` — the SAME function
whose values the basic prose narrates — so figure and text agree by construction. On an oblique
clip the quarter-turn dots are dropped (projection-distorted); only 180°/360° remain.

> **Generation–render coupling (was a real desync):** the basic prose used to describe
> "graphs showing speed and acceleration climbing" — plots the basic tier no longer shows.
> The generator is now told its figure set; the renderer embeds that same set. Changing one
> without the other reintroduces prose that references absent figures.

---

## 2. TIER DEFINITIONS — apply exactly

### TIER 1 — BASIC
- **Bloom objective:** after reading, the learner can *recall and explain* that the object
  moves in a circle, sweeps around by a growing angle over time, takes a fixed time to
  complete one turn, and needs a constant pull toward the center to stay on it.
- **Element interactivity: LOW.** One concept at a time, introduced in this order: circle →
  radius → angle sweeps around over time → one full turn takes a fixed time → inward pull.
  No equation is manipulated; relate everything to everyday experience (a ball on a string,
  a clock hand, a car turning).
- **Introduces:**
  - the object and its circular path, the rotation direction, the clip length;
  - the radius as "how far out it sits";
  - **angular velocity as a lived idea, NOT a symbol** — the object sweeps around by an
    angle as time passes; describe it in **degrees or fractions of a turn per second**
    (e.g. "about a quarter-turn, roughly 90°, each second"; "after 2 seconds it has swept
    about halfway around"). This is ω taught at the Understand level with no rad/s and no
    formula.
  - **the period** — "one full turn takes about T seconds" — as a concrete, graspable number;
  - qualitatively that *faster spin or a bigger circle means a stronger inward pull*, and the
    name "centripetal acceleration" for that inward pull (named once, in words, not computed).
- **Forbidden:** ω/α **symbols** and rad/s, any formula or numeric substitution (beyond r,
  the duration, the period in seconds, and the qualitative degrees-per-second sweep), and any
  *rate-of-change* discussion of ω itself (speeding up/slowing is conveyed in plain words per
  Constraint 4, but never as an α or a computed rate).
- **WRITER'S TEST:** "Could a learner who has never seen the equations follow every sentence,
  end up holding one idea at a time, and picture the angle sweeping around and one turn
  taking T seconds?" If YES → Tier 1.

### TIER 2 — INTERMEDIATE
- **Bloom objective:** after reading, the learner can *apply* a_c = ω²r and T = 2π/ω = 1/f to
  this object and *analyze* how angular velocity, period, frequency and inward acceleration
  depend on each other.
- **Element interactivity: MODERATE.** Several variables interact, but inside the routine
  formula patterns the learner has seen.
- **Introduces:** **ω, a_c, T, f** with their measured values and units; the relations
  a_c = ω²r and T = 2π/ω = 1/f, shown numerically to hold for THIS object; reading the graph
  and table. **Present the relations in an explicit, structured way** — name each quantity,
  state the relation, then substitute this object's number — so the learner sees *how the
  variables are wired together* (e.g. "ω → (×r, squared) → a_c"), not a wall of prose.
- **Tangential speed v is NOT a headline variable here.** Circular motion at this tier is
  built on the angular quantities (ω, T, f) and the inward acceleration a_c = ω²r. Do **not**
  introduce v = ωr or a_c = v²/r as the main relation; v may appear at most as a one-clause
  aside if it genuinely aids intuition, never as a required step or a listed measured variable.
  (Rationale: v²/r duplicates ω²r and adds an interacting element without new insight at this
  tier — it belongs to the fuller treatment, not the moderate one.)
- **Forbidden:** treating the motion as changing over time as the *main point* (a sentence of
  context is fine), angular-acceleration dynamics, scale-caveat discussion, tangential-speed
  derivations as a core relation.
- **WRITER'S TEST:** "Does the passage coordinate a handful of interacting quantities through
  the standard relations, applied to this object's numbers, within a familiar pattern?"
  If YES → Tier 2.

### TIER 3 — ADVANCED
- **Bloom objective:** after reading, the learner can *analyze and evaluate* how the motion
  evolves — relate α to changing ω, reason about a_c ∝ ω² sensitivity, and judge what the
  numbers do (and do not) establish.
- **Element interactivity: HIGH.** Many quantities integrated at once and across time, with
  trade-offs and limits.
- **Introduces:** angular acceleration α and a_t=αr; the `timeline` spin-up/coast-down and
  what it means physically; the squared sensitivity (doubling ω quadruples a_c); the
  distinction between tangential and centripetal acceleration; the calibration caveat
  (relative kinematics are scale-free; absolute a_c depends on the reference size).
- **WRITER'S TEST:** "Does the passage require the reader to integrate several quantities
  *and their change over time*, and to reason about proportionality, limits, or what the
  measurement does/doesn't pin down?" If YES → Tier 3.

---

## 3. WORKED EXAMPLES (in-domain — fan spin-up, the a2627aa2-style seed)

> In-domain examples beat the generic BST examples for an A3B model: it anchors on the exact
> vocabulary and seed it will see. One short illustrative sentence per tier for the same
> `## How the variables are related` section.

**BASIC** — Bloom: Understand; interactivity: low
> "Because the toy keeps curving back toward the middle of the fan instead of flying off in a
> straight line, something must be pulling it inward the whole time — and the faster it
> whirls around, the harder that inward pull has to be."
> *Why Tier 1: one cause-and-effect idea, everyday language, no symbols or substitution.*

**INTERMEDIATE** — Bloom: Apply; interactivity: moderate
> "Its tangential speed follows v = ωr, so with ω ≈ 6.59 rad/s and r ≈ 1.78 m the toy moves
> at about 12.2 m/s; feeding that into a_c = v²/r gives roughly 88 m/s² of inward
> acceleration — the same value you get from a_c = ω²r, as it must."
> *Why Tier 2: two interacting relations applied to this object's measured numbers, routine
> pattern, cross-checked.*

**ADVANCED** — Bloom: Analyze/Evaluate; interactivity: high
> "Because a_c = ω²r, the centripetal demand rises with the *square* of the angular velocity:
> as the fan spins up at α ≈ 1.18 rad/s² from ω ≈ 3.2 to ≈ 10.2 rad/s, a_c climbs roughly
> nine-fold while r barely moves — so almost all of the growing inward acceleration comes from
> ω, not the radius. Note that these absolute values scale with the assumed reference size;
> the *relative* story (α, the ω²-growth) holds regardless."
> *Why Tier 3: integrates α, the timeline, the squared sensitivity, and the scale caveat —
> several quantities reasoned about over time and at their limits.*

---

## 4. HARD CONSTRAINTS (inherited + new)
1. **Numbers come ONLY from `material_seed.json`** (and `stats.json` if needed). Never
   invent, extrapolate, or introduce a quantity not in the seed. Quote values with units.
2. **No questions, quizzes, "try this", or fill-in-the-blanks.** This is exposition only.
3. **Tier–content agreement:** the CLT interactivity AND the Bloom objective must point to
   the same tier. If they disagree, rewrite. (Most common failure — guard every time.)
4. **Motion-type faithfulness (ALL tiers — validated as the #1 failure).** Read
   `angular_acceleration.motion_type`. If it is `accelerating` or `decelerating`, you MUST
   convey the speed change qualitatively at **every** tier — never write that the motion is
   steady/uniform/constant, or that ω/v/a_c "remain fixed". Only the α **value**, `a_t`,
   `omega_initial/final`, and the `timeline` samples are reserved for the advanced tier:
   - **Basic:** plain words only — "the toy whirls faster and faster" / "gradually slows".
   - **Intermediate:** state the listed ω/v/a_c are **representative (time-averaged)** values
     summarizing a speeding-up (or slowing) motion, and that the detailed time-evolution is
     examined at a deeper level — but give **no** α number or timeline.
   - **Advanced:** full α + timeline.
   - If `motion_type` is `uniform`/null, then "steady" IS correct.
   > Without this rule, basic+intermediate falsely reported the fan as steady (it spins up).
5. **Round numbers in prose to ~3 significant figures** (e.g. 1.78 m, 6.59 rad/s, 88.5 m/s²);
   never print raw float precision from the seed.
5b. **Numeric verification of relations (validated bug).** The summary r/ω/v/a_c are
   **time-averages**. For non-uniform motion they do NOT satisfy the instantaneous identities
   (mean(a_c) = mean(ω²)·r is strictly **greater** than (mean ω)²·r — Jensen). So when you
   show a relation *numerically*, use a **single `timeline` instant**, where v = ωr and
   a_c = ω²r close exactly with the reported r. **Never assert that the summary mean ω, when
   squared, gives the summary a_c** — it won't, and a reader who checks will catch it. The
   reported `r` is the fitted orbit radius (`consistency_note.radius_used`); use it, not
   `measured_radius_m`.
6. **Stay on the requested tier.** Do not drift. A basic passage must introduce no equation;
   an advanced passage must do more than restate intermediate content.
7. **Minimize extraneous load:** clear wording, one idea per sentence at Tier 1, no
   decorative complexity. Difficulty comes from intrinsic content, never confusing prose.
8. **Graceful degradation:** if a seed field a tier needs is null, omit the dependent
   sentence rather than fabricate (esp. `angular_acceleration` on uniform clips).
9. **Same 5 section headers, every tier** — so the eval can score section-by-section across
   tiers and objects.
10. **`Reading the figures` narrates ONLY the tier's figure allowlist (§1a).** Basic has no
    table and no time-series graphs, so its figure section must not mention them; intermediate
    must not mention angular-acceleration graphs or the summary panel. The allowlist is passed
    into the prompt by `generate_tier_material.py` and mirrored by `TIER_ARTIFACTS` in the
    renderer — keep the two in lockstep.
11. **Teach the physics, not the measurement pipeline (learning-focused language).** The
    passage reads as a physics lesson about the phenomenon, never as a tracking/analysis
    report. **Forbidden vocabulary:** "track/tracked/tracking", "pipeline", "detected/
    detection", "coverage", "fps"/"frame rate", "validation flag", "ROI", "pixel", "bounding
    box", "the tool/the model", and any raw figure **filename** (`omega_t.png`, `ac_t.png`, …).
    Refer to figures by what they *show* ("the graph of how the angle grows", "the annotated
    frame"), and speak about the object's motion ("the ball sweeps around…"), not about how it
    was captured. This is intrinsic-vs-extraneous load (Constraint 7): measurement scaffolding
    is pure extraneous load and must be stripped, especially at Basic.
12. **Plain Unicode only — never LaTeX or backslashes in the JSON.** Write symbols as Unicode
    (ω, α, ², ·, →) and subscripts as `a_c`, `a_t`, `v_t` (plain ASCII underscore — the
    renderer turns these into proper subscripts). **Never** emit `$…$`, `\omega`, `\times`, or
    any backslash: a stray `\o`/`\t` is an invalid JSON string escape and makes the whole
    `material.{tier}.json` unparseable (a validated failure mode). If you would write math,
    write it in words or plain Unicode instead.

---

## 5. TASK
1. Read `analysis_output/data/material_seed.json`.
2. You are given **one** `{{TIER}}` per call (basic | intermediate | advanced). Write the
   passage for that tier only, drawing on the seed fields permitted for it (§1/§2).
3. Write under EXACTLY these five headers, in order (same as base Subagent D):
   - `## Scenario`
   - `## The variables we measured`
   - `## How the variables are related`
   - `## What the video shows over time`
   - `## Reading the figures`
   At Tier 1, `What the video shows over time` describes the motion qualitatively (steady /
   speeding up) without α; at Tier 3 it carries the timeline analysis.
4. Write the result to `analysis_output/data/material.{{TIER}}.json` (schema below).

---

## 6. OUTPUT FORMAT
Return ONLY a JSON object — no preamble, no prose outside JSON, no markdown code fences.

```json
{
  "object_name": "<from seed>",
  "scene_title": "<from seed>",
  "tier": "basic | intermediate | advanced",
  "bloom_objective": "Remember | Understand | Apply | Analyze | Evaluate",
  "element_interactivity": "low | moderate | high",
  "concepts_introduced": ["<seed symbols/relations this tier actually used, e.g. r, omega, a_c=omega^2*r>"],
  "sections": {
    "Scenario": "<prose>",
    "The variables we measured": "<prose>",
    "How the variables are related": "<prose>",
    "What the video shows over time": "<prose>",
    "Reading the figures": "<prose>"
  },
  "tier_conflict": false
}
```

- `sections` is the **same schema the existing eval and renderer already consume** — so the
  three tier files plug into `run_material_eval.py` unchanged.
- Use plain Unicode for symbols (ω, α, ², ·); the renderer maps them.
- If a requested tier cannot be honestly reached for this seed (e.g. advanced dynamics on a
  clip with no measured α and no timeline), set `"tier_conflict": true`, explain inside the
  `Scenario` prose, and write the nearest honest tier — never fabricate to fill the tier.

---

## 7. SELF-CHECK before emitting JSON (silently, in reasoning)
1. Did every number come from the seed, with units?
2. Does the content's element interactivity (low/moderate/high) match the requested tier?
3. Does the Bloom objective the passage builds match that same tier?
4. Did I respect the tier's allowed seed fields (no equations at Tier 1; α/timeline only at
   Tier 3)?
5. Are there zero questions/exercises, and is extraneous load minimized?
6. Do the CLT signal and the Bloom signal point to the SAME tier? If not, rewrite.
Only when all six pass, output the JSON.

---

## 8. LLM-specific notes (Qwen3.6-35B-A3B)
- **Reasoning ON**, but budget **`max_tokens ≈ 24000`** (`chat_template_kwargs.enable_thinking=true`).
  With thinking on and too small a budget, the whole budget is spent in `reasoning_content`
  and `content` returns **empty** (observed repeatedly in this project).
- **One tier per call**, not all three in one shot. An A3B model bleeds vocabulary between
  tiers if asked to produce them together (the advanced equations leak into the basic
  passage). Separate calls keep each tier clean and independently grounded; the orchestrator
  loops the subagent three times (basic/intermediate/advanced) writing
  `material.{tier}.json`.
- **JSON-only, no code fences** — the model tends to wrap output in ```json fences with
  thinking on; the instruction above plus a post-parse fence-strip handles it.
- **In-domain few-shot (§3)** rather than the off-domain BST examples — measurably steadier
  tier calibration for a sparse MoE.
- **Poor self-correction on regen (documented limitation).** The 35B drafts well on the FIRST
  pass but corrects poorly when told what failed: given "you used a banned word", it frequently
  re-emits the same word or trades it for another violation (observed `recorded`→`pushes`). So:
  1. **Steer the first pass, not the regen.** Subtle wording nuances live in an editable sidecar
     `workspace_lib/analysis/material_hints.md`, loaded by `material_tiers._load_hints()` and
     injected into the system prompt as a NUANCES block. Add a hint there (no code change) when
     the model reaches for a bad phrasing — e.g. `recorded`→`measured`, "slows down" not "does
     not speed up or slow down", figures by what they SHOW, use only the given milestone times.
  2. **Best-of-N regen as a backstop.** On a gate failure the generator re-rolls up to 2× fed the
     exact faults and keeps the draft with STRICTLY fewer issues (never a lateral trade); the
     cross-tier pass has a SEPARATE regen budget fed both the cross-tier fault and any residual
     per-tier issue. This converges most cases but not all — see the limitation above.
  - Full generalization (a clean gate on every stochastic run) needs a stronger model or a
    review-and-select generation loop (cf. Utami's SocioMathLLM: generate 5 candidates, CoT-review,
    pick 1). Residual flags are proceed-but-flag; the pipeline never hard-blocks.

### Validation run (2026-06-27)
Tested live against the fan seed `a2627aa2` (accelerating, α=1.18) on Qwen3.6-35B
(`192.168.1.205:8083`), one call per tier, thinking ON, `max_tokens=24000`:
- All three tiers returned clean JSON (no fences issue), **no empty-content**, ~7–11 s each.
- Tiers correctly differentiated: basic = no equations + everyday analogy (Understand/low);
  intermediate = 6 variables + relations verified (Apply/moderate); advanced = α + full
  timeline + a_c∝ω² + scale caveat (Analyze/high). Bloom/CLT labels self-assigned correctly.
- **Bug caught & fixed (now constraint #4):** first run, basic+intermediate falsely called
  the spinning-up fan "steady". After adding motion-type faithfulness + rounding (#4, #5),
  re-run was faithful at every tier. This is why per-tier output must be spot-checked on
  accelerating/decelerating clips.

### Validation run (2026-07-05) — full 5-seed sweep
Regenerated all 5 eval seeds (`8110ab0d`, `711fffe8`, `afe0f99f`, `cc9f02ce`, `a2627aa2`) live
on Qwen3.6-35B through the reworked generator (best-of-N regen + hints file active):
- **EI monotonicity 5/5**, **titles equal 5/5**, **cross-tier PASS 4/5**, all tiers fully clean
  **3/5** (13/15 tiers). Gate JSON carries `frame`+`cross_tier` on every run.
- The three original defects are gone: no title drift, no "X on X", advanced ≠ intermediate
  (distinct assigned worked instants), numbers grounded/consistent (T,f quoted not re-derived).
- Residual flags were stochastic single words. Root causes fixed after the sweep: `_STEADY`
  false-positive on "does not speed up"; ω² not grounded (now added); idiom false-positives
  ("on track"/"work together"); and the stubborn `recorded` — killed by a hints-file entry
  (`recorded`→`measured`), live-confirmed 0 occurrences on re-run. See §8's limitation note.

---

## 9. Evaluation hook (note-29's hypothesis) — RESOLVED → (b) tier-matched references
note-29 predicts **basic = high F1, advanced = low F1** vs the reference. With the current
single gold reference (**OpenStax §6.2**, which is itself equation-focused, ~intermediate
level and mostly *linear*/centripetal, not angular), the likely real ordering is
**intermediate ≥ basic ≥ advanced** — the *intermediate* tier will match §6.2 best by
level-and-vocabulary match, and the *advanced* tier (angular α, ω-dynamics) will diverge
because §6.2 barely covers angular kinematics. That is a confound, not a finding.

**MEASURED (2026-06-27, fan a2627aa2, 3 tiers vs §6.2):** basic **0.815**, intermediate
**0.838**, advanced **0.841** — i.e. **advanced ≥ intermediate > basic**, the *reverse* of
note-29's prediction. Confound confirmed: §6.2 is equation-dense, so more-advanced (more
vocabulary-overlapping) material scores higher. Per-section, "how variables relate" (shared
formulas) is highest (0.844) and "what the video shows over time" lowest/most variable
(0.812 ± 0.020 — where tiers diverge most). A single fixed reference therefore measures
**lexical density, not pedagogical quality**.

Two clean options (pick before reporting per-tier numbers):
- **(a) Single fixed reference** — simplest; report the three F1s honestly and *explain* the
  ordering as level-match to an intermediate reference (still a real, defensible result).
- **(b) Tier-matched references** — basic ↔ a conceptual text, intermediate ↔ §6.2, advanced
  ↔ an angular-kinematics text. Cleaner test of note-29's hypothesis.

**DECISION (resolved): (b) tier-matched references.** This is what note-1 asks for ("divide
the 19-reference set by difficulty into three parts, then re-run the eval") and it removes the
lexical-density confound above. `tools/split_references_by_difficulty.py` auto-sorts the 19-
source English set into basic/intermediate/advanced buckets on the SAME element-interactivity
axis (`material_gate.quantities_in`/`relations_in`) the material is scored on; then
`run_multi_reference_eval.py` runs per bucket. Option (a) stays available as a sanity baseline.

Eval runs: `run_material_eval.py --materials material.basic.json material.intermediate.json
material.advanced.json` (per object, grouped by tier), plus the tier-matched multi-reference
runs from the split, plus `run_llm_judge.py` (model-based rubric + achieved Bloom level) and
`grade_material_difficulty.py` (model-free EI ladder) for the difficulty-fit signal note-29
and the deck's "Bloom-level column" call for.

---

## 10. Decisions & future work

- **No fourth tier (note-1).** Three levels (basic / intermediate / advanced) stay the design.
  A fourth tier was considered and declined: the seed's physics (r, ω, a_c, α, T, f + the
  spin-up timeline) saturates at "advanced" (Analyze/Evaluate over time and at limits); a
  fourth level would repeat advanced content without a new cognitive process to scaffold, and
  the A3B model's vocabulary bleed worsens as tiers multiply. Extra difficulty signal comes
  instead from more Bloom/CLT-graded evidence per tier (the EI ladder + LLM-judge), not from
  another tier.
- **Difficulty grounded in literature (note-29).** The ladder maps onto **Anderson &
  Krathwohl (2001)** — basic = Remember/Understand, intermediate = Apply/Analyze, advanced =
  Analyze/Evaluate — and onto **Sweller's Cognitive Load Theory** element interactivity — the
  count of interacting quantities/relations the reader must hold at once rises basic <
  intermediate < advanced. `grade_material_difficulty.py` measures that interactivity directly
  so the ladder is evidence, not an assertion.
- **Future work — advanced two-video / force comparison (note-1, deferred).** The professor's
  richer advanced idea (compare two clips, or bring in the forces) needs a two-clip capture
  and a dynamics extension that this kinematics-only spec deliberately excludes (HARD RULE 8b).
  Recorded here as a deliberate next step, not a gap.
- **Knowledge graph (deferred, paper 2).**
