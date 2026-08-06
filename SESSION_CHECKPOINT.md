# Session Checkpoint — 2026-08-06 (corpus regenerated at 5 clips; all three documents updated)

## 00-NEW. DELIVERED THIS SESSION — read this first

**All three documents are rebuilt on the new corpus and compile clean:**
- `presentation/centri-weekly-2026-08-12.{tex,pdf}` (17 slides) + `-memo.md` — **new weekly**
- `technical-report/centri-video-data-quality.pdf` — rev. 2026-08-06, 45 pp
- `paper/centri-ieee.pdf` — 14 pp, 0 undefined refs

**Corpus = 5 clips / 15 worksheets**, all regenerated:
`job_roundabout-4046`, `job_computerfan-4029-2`, `job_turntable-1`, `job_turntable-2`,
`job_fan4656final`. Gate **11/15**; fan-4656 is the only clip clean on all three tiers.

**Headline numbers (all re-derived, none rescaled):**
- BERTScore F1 **0.799 / 0.824 / 0.828**, total 0.817 (n=15)
- Judge A (Qwen) all-12 **3.57 / 3.83 / 4.58**; Judge B (Claude, 5 subagents) **3.72 / 3.72 / 4.18**
- **κ = 0.31 quad / 0.14 unweighted** over 180 pairs; exact 40%, within-1 88%
- **cognitive_demand rises for BOTH raters (2.80→3.60→4.80 and 3.00→3.20→4.20) and is now the
  BEST-agreed criterion, κ = 0.70, r = 0.80** — this carries the difficulty claim
- **grounding_accuracy κ = −0.07 with ZERO exact agreement across 15 worksheets** (within-1 33%)
- EI 5.0 / 22.4 / 36.6, rises 5/5 — ENFORCED. Basic is **exactly 5.0 on every clip**
- FK grade 4.0 / 3.8 / 6.6, rises 2/5. Passage length 469 / 340 / 610

**⚠ The rise counts in the paper's ladder table are per-clip STRICT rises** (cognitive demand
A 3/5, B 0/5). The *means* rise monotonically for both; individual clips tie because the scale is
5 whole points. Both are stated, with a footnote — do not quote one as the other.

**NEW FINDINGS worth carrying:**
1. **The judge caught an arithmetic defect the gate passed.** `turntable-2` intermediate prints
   ω²r = **4.91** where 4.83² × 0.185 = **4.31** (13.7%), then asserts it matches the measured
   average. **The gate passed it correctly** — 4.91 *is* ⟨ω²r⟩ and traces to the seed; ⟨ω²r⟩ ≠
   ⟨ω⟩²r (Jensen). Rater A scored it **5/5 on grounding**; rater B scored it **2** and named it.
2. **The gyro table was misread and is now corrected.** The +25.5% peak-ω error was the tracker
   TELEPORTS, not the missing rectification: excluding 3 of 350 frames takes it to **−4.1%**
   (rectified run −0.6%). The two effects were confounded because the rectified run happens to
   have zero jumps. **This closes TODO §1.4's "separate the two effects".**
3. **The tech report's own jump gate is blind to these jumps by construction** — they are largely
   RADIAL (radius 244→687 px) and their tangential parts land at 85–86° against a 90° bound. The
   *previous* fixed-100px gate would have caught all three; it was replaced because it falsely
   accused 4029. **Each bound was adopted to fix the failure the other one caused.**
4. **RETRACTED in the tech report: "an affine ellipse needs no un-projection".** False —
   a uniform spin imaged at axis ratio k ripples between k and 1/k twice per revolution. It held
   to <3.5% for every clip the report was written about and fails at **19.6%** on fan-4656.

**Remaining stale:** the paper's Axis-4 (multimodal) table is still the OLD 7-clip scoring — it
was not re-run. Everything else is re-derived.

---

## 00-NEWER. 2026-08-06 (later): computerfan-4029-2's overlays were drawn 328 px off

**Found by looking at the annotated video, not by any check we own.** Every frame overlay for
`job_computerfan-4029-2` — including `annotated_image_basic.png`, which is embedded in all three
student worksheets — put the "centre of rotation" on a fan **blade**, with the orbit circle
running off the fan onto the desk and the r/v/a_c arrows nowhere near the marker.

**No taught number was wrong.** Trajectory and centre were shifted *together*, so all relative
geometry survived: `r_fit_px` 305.3 against 306.9 measured off the video by fitting the marker
directly (RANSAC, 650 inliers, radius CV 0.014), and after the fix `mean_omega` is unchanged to
13 significant digits. Only `cy_px` moved: **902.4 → 574.4**, exactly `roi_crop.y_off = 328`.

**Cause.** The tracker ran on the cropped video, Step 5 declared `coordinate_space: "display"`,
and the contract's radius-CV guard concluded the trajectory was already cropped and left it
alone. It was not — the raw trajectory reaches y = 1384 in a crop only 1244 tall. The guard
compares the trajectory against the CENTRE, and the centre it was given was a `bootstrap`
estimate **260 px off the hub**, so both of its readings were bad (cv 0.462 vs 0.243) and it
picked the less-bad wrong one. A RANSAC refit then moved the centre onto the display-space
trajectory, making the result self-consistent and therefore invisible downstream.

**Why nothing caught it.** `verify_figures.py` exists for exactly this bug class, but it compares
the figures against `kinematics.csv` — which was itself in the wrong space. It confirmed
consistency, not correctness. Same trap as the tracker checker: **tracing is not validating.**
A self-consistent frame of reference cannot be audited from inside itself.

**Fix** (`workspace_lib/analysis/contract.py`): the crop rectangle now outranks the radius test.
A trajectory measured on the cropped video cannot contain a detection outside that video's own
frame, so a meaningful overshoot proves display-space **without consulting the centre at all**.
Gated at >4 px and ≥3 points so one freak detection cannot flip it; silent when the trajectory
fits inside the crop (turntable-1/2), where the radius test stays in charge.

**Regression evidence** — the thing to trust here:
- Contract-boundary harness over all 6 workspaces: trajectory and centre **bit-identical** for
  five, changed for `4029-2` alone (y shifted by exactly 328).
- End-to-end re-run of 4 control clips: `stats.json` and `kinematics.csv` **byte-identical**
  (sha256 unchanged) for turntable-1, turntable-2, roundabout-4046 and computerfan-4029.
- The rule fires *informationally* on 4046 (15 pts / 16 px) and 4029 (8 pts / 147 px), which were
  already being cropped — it confirms their existing decision rather than changing it.
- Tests **151 passing** (`tools/tests/test_contract_crop_bounds.py`, 9 new). Mutation-checked:
  disarming the rule makes them fail. One test blinds the rule and asserts the OLD wrong call, so
  cause stays pinned to effect.

**Gate outcome unchanged**: 4029-2 basic still fails the same `rate-period-referent` rule,
intermediate and advanced still pass — the corpus stays **11/15**. No document number changed,
so the deck, paper and tech report needed no renumbering; only this clip's figures were rebuilt.

**Also fixed in the same pass — the "red marker on red marker" title.** `common.dedup_display_name`
already existed for the degenerate `"<X> on <X>"` composite and is called by the seed, the report
and figures; **`render/annotate.py` never called it**, so the video banner carried the duplicate
while the figure beside it did not. A shared helper every surface must *remember* to call is a
convention, not a guarantee — so the contract now normalises the title once at the seam, annotate
uses the helper, and `templates/base-template-computerfan-4029/sidecar.json` gained
`object_name` + `scene_title` ("a red marker on a computer fan blade") so a future run gets a
descriptive title rather than a merely collapsed one. Geometry unchanged for all 5 clips; only
4029-2's title moved. Tests **158** (`test_scene_title_dedup.py`, 7 new, incl. a structural check
that no surface reads `scene_title` raw out of `stats`).

**Artifact sweep over all 5 workspaces** (`scratchpad/sweep.py`: registration vs video, degenerate
names, placeholder rot, artifact presence/freshness, gate):
- **Found: 18 worksheet PDFs were 6 days stale.** `roundabout-4046`, `turntable-1`, `turntable-2`
  had `.tex` regenerated 08-06 but PDFs left at 07-31 — the full regen never recompiled them.
  **Recompiled.** The judges read `material.*.json`, so no score was affected.
- Registration now verified against the video for every clip. The sweep's flag on 4046 is **its
  own detector failing** (fits r = 14.4 px at CV 0.441 — it locks onto the big saturated
  playground frame, not the small dark handle); 4046 was confirmed correct by eye.
- Gate tally **11/15 unchanged**: fan-4656 3/3, the other four 2/3 (basic fails).
- **Still open: 18 Bahasa PDFs** (`translated_*.id.pdf`, 07-30) predate the current `.tex` on
  those three clips. Regenerating needs the translation tool + LLM; not done.

**Documents updated for this finding** (no number changed anywhere — the physics did not move):
- **paper** 14 pp — new row in the defects table (`none; author inspection`) plus a passage
  qualifying "each layer caught a defect the others passed", which this defect is a counterexample
  to. This is the honest bound on §sec:defects and partly answers TODO §2.2.
- **tech report** 46 pp — new §`sec:cropbounds`, and a provenance note on
  `fig-frame-4029.png`, which is rendered from the **archived** pre-sticky-lock run while the
  numbers beside it come from `-2`.
- **deck** 18 slides — new slide "An overlay that agreed with itself" (before/after figure,
  generator `presentation/figs/mk_overlay_fix_fig.py` reading committed frozen copies, never a live
  workspace), the layers slide retitled and given a `none of them` row, and "Caught this week"
  → "What it caught" (rule #1). Memo §6.6 carries all of it cold. All slides ≤60 words of prose.

**Still open on this clip (NOT fixed):** the camera **pans off the fan** for the last ~1 s and the
overlay keeps drawing an orbit and a radius arrow across a MacBook box. Needs an "object left the
scene" test; none exists.

---

## 00-NEWEST. 2026-08-06: the scoring rubric never defined what a score MEANS

**`docs/eval-rubric-scoring.md` is new and is now the document raters read.** Until it existed, the
complete scale definition — in all four places it appeared (`run_llm_judge.py:113`, `:151`,
`eval-rubric-ika.md:20`, `eval-framework.md:24`) — was **"Score each criterion 1–5 (5 = excellent)"**.
Nothing said what a 2 or a 4 was. `eval-rubric-ika.md` defines the *criteria*, never the *scores*.

**This is the cause of the grounding κ, and it is bigger than the two-questions story.** The two
raters spent the scale differently:

| score | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| A (Qwen) | **6** | 3 | 1 | 0 | **5** |
| B (Claude) | 0 | 2 | 5 | **8** | 0 |

A used it as a **detector** (found a problem → 1, none → 5); B never gave a 1 or a 5. A's modal
score is one B never uses and vice versa, so **exact agreement was near-impossible by
construction** — hence 0% exact, κ −0.07. **κ tracks whether the raters' used ranges overlap**:
`cognitive_demand` (A 2–5, B 3–5) reaches 0.70. Not all of A's 1s are even defensible — it floored
fan-4656 basic for "~1 turn per second" when 6.68 rad/s *is* 1.06 turns/s.

**Neither parent could supply anchors — checked in the source PDFs, not assumed:**
- **Utami**: "a 5-point rubric **derived from the criteria** outlined in Table 8, Table 9, and
  Table 10" (p. 46). Those tables are Item + Definition. Appendices are pre/post-test,
  questionnaire, MWP examples — no rating instrument.
- **P-MAGIC**: teachers used "a 25-item rubric with a **10-point Likert scale**" (p. 23); Table 2
  is Dimension/Criteria/Reference/Description.
- **They do not share a scale** (5-point vs 10-point vs our 5-point), so there was nothing to
  inherit. ⚠ A Centri mean on 1–5 is **not** comparable with a P-MAGIC mean on 1–10 — compare
  orderings and agreement statistics, and always state the scale.
- P-MAGIC still reached **κ = 0.76** with ten senior physics teachers on that anchorless scale.
  That is evidence about their *rater pool* (shared professional framing supplies anchors
  implicitly), not evidence anchors are unnecessary — two unrelated LLMs share no such frame.

**What the new doc contains:** all **24 scored criteria** across the 4 axes, five *descriptive*
(not evaluative) levels each; `grounding_accuracy` **split into `grounding_provenance` +
`grounding_arithmetic`** (the 4.91-vs-4.31 case scores 5 and 2 — same text, different questions,
which is exactly why the combined criterion failed); six scoring rules incl. **`n/a` is not a low
score**; three calibration cases drawn from defects this corpus actually shipped; and the design
grounding for every choice (Brookhart 2013; Jonsson & Svingby 2007; McHugh 2012; Landis & Koch
1977). Teacher-first wording, intended for the LLM verbatim so `ICC(human, LLM)` compares two
readings of *one* instrument.

**Wired:** `build_rater_sheet.py` now points teachers at it; `eval-rubric-ika.md` and
`eval-framework.md` cross-link it.
**NOT wired (deliberate — user's sequencing is teachers first, LLM after):** `run_llm_judge.py`
still carries the one-line rubric and the single combined `grounding_accuracy`. Adopting it means
12 → 13 criteria and invalidates every stored judge result. **Do that as a controlled experiment**
— change only the anchors, re-run both judges on the frozen prompts, and see whether κ moves. If
it does not, the anchors were not the problem, and that is far cheaper to learn before a teacher
panel than after. TODO §4.3.

---


Single source of truth to resume after a context reset. **Compacted 2026-07-27** (was 663 lines) —
completed work was removed; it lives in `git log -p SESSION_CHECKPOINT.md`, the memory files
(`~/.claude/projects/-home-damar-centri/memory/centri-*.md`), and the docs cited below. Keep this
file short: current state, open work, ops crib — not a diary.

---

## 00a. LATEST — 2026-08-06: the ceiling fans were re-shot and the corpus swapped

**The two synthesized-orbit fan clips are gone from the active corpus** (`TODO.md` §1.2 closed by
option (c)). Damar re-filmed with a **yellow card marker** on one blade; four clips arrived in
`drive-download-20260805T075107Z-1-001/`.

- **`templates/base-template-fan-4656`** is the winner and is now in the corpus.
  `tracking_mode: color` — **99.99% coverage, 100% of detections on-orbit, ZERO jumps, 190.8
  revolutions**, max Δθ 34.3° against a 180° Nyquist limit. Verified through the shipped
  `color_track` using **only the keys the orchestrator forwards**, so no code change is needed.
  Full record: `templates/base-template-fan-4656/NOTES.md`.
- **ω is independently validated for the first time on a fan.** A blade-pass FFT (no marker, no
  tracker) agrees with the marker track to **0.03 / 0.16 / 0.99%** on steady windows. On the
  stationary tail the marker track reads **0.016 rad/s** and the FFT reports **4.69** — the
  `frequency`-mode rate floor, measured rather than asserted, and the argument for the swap.
- **`fan-4027` / `fan-4028` moved to `templates-reshoot/`** (parked, not deleted — repo policy).
  Their `analysis_output/data/api_cache.json` must be deleted if either is ever revived.
- **✅ A REAL BUG IN THE SHIPPED TRACKER, FOUND AND FIXED.** `color_track.py` — when no candidate
  fell within `max_step_px` of `prev`, the frame was a miss but **`prev` was never updated or
  cleared**, so one over-step froze the lock and the marker was re-acquired only once per
  revolution. Measured: **`max_step` 90 → 26.9% coverage; no `max_step` → 99.99%.**
  Fixed by `relock_after` (default 5): a lock that has explained nothing for N consecutive frames
  is dropped. **Same failing config now gives 92.6%**, and the run reports `n_relocks` (170 there)
  as a signal the gate is too tight. `relock_after=0` restores the old behaviour.
  4 tests in `tools/tests/test_color_track_relock.py`. **Suite now 141 passing.**
- **THE METRE SCALE IS RESOLVED to ±5% — `px_per_m ≈ 591`, `physical_size = 0.44 m`.** No ruler
  and no re-shoot: the card **is** the ruler once its geometry is pinned. Two facts did it — the
  card lies **along** the blade (long axis 4.2° off radial) and **its outer edge is the blade
  tip** (predicted 329.5 px vs 319.3 px measured from 800 independent tip points, **3.2%**). So
  the card covers the blade's outer 25 cm: inner edge 31 cm, **centre ~44 cm**, outer edge = tip.
  **Prediction to check with a tape: blade tip ≈ 54 cm from the hub centre** (51 makes the 25 cm
  card measure 22.2; 61 makes it 26.6).
- **⚠ A 40% CALIBRATION ERROR CAUGHT BEFORE ANY WORKSHEET.** The sidecar first read Damar's 31 cm
  as hub→card **centre** when it is hub→card **inner edge** — `px_per_m` 839 vs the correct 591,
  making every SI length **29% too small**, `a_c` with it. *"Distance to the marker" is ambiguous
  the moment the marker is bigger than a point.*
- **TWO RETRACTIONS, same session:** (1) *"marker width 18.5 cm ↔ 150 px = 811 px/m, agreeing with
  the orbit to 3.4%"* — used the **axis-aligned** bbox, inflated by the marker's own rotation;
  rotation-invariant it is 95 px. **Use `minAreaRect` to size a rotating marker, never the
  axis-aligned bbox.** (2) *"HSV under-segments the card, biasing the centroid inward"* — a
  one-frame observation; over a full window SAM3 and HSV agree on the orbit radius to **0.3%**.
  **One frame is not a measurement.**
- **Tilt: 34.5° off face-on** (axis ratio 0.824), residual almost pure 2/rev with only 4.1 px at
  1/rev — a clean single tilt, so rectification should engage with nothing confounding it.
- **SAM3 works** (Damar fixed it mid-session) at **10.0.0.1:8086**; install is
  **`/home/damar/centri/sam3/`** (the §4 file-map path was stale). Cue sweep on the yellow card:
  **every marker noun MISSES** (`card`, `yellow card`, `paper`, `sticky note`, `tag`, `label`,
  `sponge`, `block`, `marker`); **`yellow object` hits**, as do `fan blade` and `ceiling fan`.
  `/track` did 179/179 frames in 24 s and agrees with the HSV tracker on orbit radius to **0.3%**.
  **Colour still wins here** (no GPU, no cue tuning), so the sidecar stays `color`.
- **`turntable-3` WITHDRAWN 2026-08-06** (Damar's call). Its tracked point teleports 604–713 px in
  a single frame against a 1.4 px normal step, one jump inside the active window, and the
  worksheets taught an `a_c` **27% above** the jump-free value. Template parked in
  `templates-reshoot/`, workspace archived. **⚠ CONSEQUENCE: the project now has NO
  sensor-validated clip.** The gyro comparison (`TODO.md` §1.4, §7.2) was *entirely* about
  turntable-3, so the paper's validation story has to be rebuilt, not trimmed. Its removal also
  deletes the most striking row of §7.1's rater-disagreement table (it was the only basic
  worksheet Qwen scored 5/5 on grounding), which must be **recomputed, not edited**.
- **The corpus is now 5 clips**: roundabout-4046, computerfan-4029, turntable-1, turntable-2,
  fan-4656. Every aggregate published to date describes a different set and must be re-derived.
- **⚠ A 6% SCALE SWING FROM A BYTE-IDENTICAL SIDECAR — found, root-caused, fixed 08-06.**
  Two `fan-4656` e2e runs chose different values for "the orbit radius": semi-major **260 px**
  vs circle-fit median **245 px** → `px_per_m` **591 vs 558**, mean `a_c` **20.99 vs 22.24**.
  Cause: the orbit images as an ELLIPSE (axis ratio 0.823) and rectification was skipped, so
  three plausible radii existed and nothing picked between them. This is §7.2's agentic
  run-to-run variance with a named mechanism and a measured cost. Two fixes:
  1. **`rectify.py` gained an AFFINE branch.** It gated only on hub offset (decentering) and
     ignored `axis_ratio`, which it measured two lines above — so a centred-but-TILTED orbit was
     returned untouched. Now, when hub offset < 20 px and axis ratio < `AFFINE_MIN_AXIS_RATIO`
     (0.95), it de-foreshortens using the ellipse's own conic (no vanishing line needed;
     `_metric_from_ellipse` preserves handedness so ω's sign cannot flip). On fan-4656: residual
     **7.29% → 3.41%**, `r_fit_px` → **260.0**, and with the paired `physical_size` the chain
     closes at **px_per_m 590.9 / r_fit_m 0.4400** — matching the tape exactly.
     **Blast radius is exactly one clip**: roundabout-4046 (hub 95.7 px) stays on the perspective
     path, turntable-2 (ratio 0.992) is round enough to skip, turntable-1 has `no_hub_px`.
     13 tests in `test_rectify_affine.py` incl. revolution-count preservation + direction safety.
  2. **`reference_geometry.diameter_px` is now an optional SIDECAR field** (orchestrator Step 5 +
     `docs/data-contract.md`), used verbatim when present, bbox sizing unchanged when absent.
     The calibrated span is sometimes not any object's bbox — an orbit radius measured with a
     tape — and prose in `hints.md` is not a contract.
  - **⚠ Amended an existing test.** `test_ellipse_centre_as_hub_is_refused_or_inert` encoded the
    old behaviour. Its real invariant (passing the ellipse centre must never be reported as a
    *perspective* rectification) is kept; a companion test now **documents a limit**: a
    mis-supplied hub and a genuinely centred one are NOT distinguishable from the trajectory, and
    `radial_residual_after_pct` is **TAUTOLOGICAL in the affine branch** (any ellipse
    circularises under its own conic) so it must never be quoted as evidence.
- **`computerfan-4029-2` re-run e2e and the relock fix landed**: coverage **0.869 → 0.9927**,
  `n_relocks: 1`. Its numbers moved as expected — mean ω 22.90 → 24.25, mean `a_c` 35.84 → 43.29
  (**+21%**) from the 102 recovered frames. A tail replay could NOT have delivered this.
- **NEXT: finish the regen, then the eval layers** (BERTScore, EI, both judges, Axis 4).

---

## 00. RESUME HERE — state on stopping, 2026-07-31

**UNCOMMITTED.** Working tree carries the 07-29→07-31 work; last commit is `90f1d1c`. Tests green:
**99 passing** (86 + 6 `test_figure_direction.py` + 7 `test_judge_agreement.py`).

**There are now TWO LLM judges** on the same 12-criterion rubric: **Qwen3.6-35B** at
`192.168.1.205:8083` (which also *wrote* the material) and **Claude Opus 5** (7 subagents, one per
clip, blind). The 7-clip material sweep of 07-27 is still the run every number describes; no
worksheet was regenerated this session.

### What landed 2026-07-29 → 07-31
- **The 07-27 direction-sign fix reached only 3 of 5 surfaces; the other 2 are fixed now.** Prose,
  measurement table and phase-band words had been resolved to speed; the **plotted ω curve** and
  the **direction arrows** had not. fan-4028 shipped a figure whose "clip average" line sat at
  +5.70 above a curve that never rose above −1, in a band labelled "increasing" where it fell.
  The arrows were worse: they read `sign(canonical_omega)`, which **returns a magnitude**, so the
  test was always true and v/ω were drawn CLOCKWISE on every clip — wrong on all six ceiling-fan
  worksheets. Direction now comes from `common.travel_sign(stats)` (reads `rotation_direction`);
  ω plots as **angular speed**. Rest bands are labelled **"not turning"**.
- **A jump sweep of the corpus found turntable-3's numbers are wrong** (see the 07-21 block below).
- **Eval tables rebuilt in P-MAGIC's published layouts** (their Tables 2/3/7) by the new
  `tools/build_pmagic_tables.py` → `material_work/_eval/pmagic_tables.{md,tex}` and
  `presentation/pmagic_tables.tex`. Adds per-level BLEU/ROUGE and per-level diversity, which the
  07-29 report did not break out.
- **A SECOND LLM judge, and the κ column is no longer a dash.** Claude Opus 5 scored all 21
  worksheets blind (7 subagents, one clip each). Both raters were sent the **byte-identical**
  prompt — built once by `tools/export_judge_prompts.py`, replayed by
  `tools/run_judge_from_prompts.py` (`--model` for the endpoint, `--from-json` for agent output),
  agreement by `tools/judge_agreement.py`, table by `build_pmagic_tables.py --judge-dir-b`.
  **Overall κ = 0.34 quadratic-weighted, 0.08 unweighted; exact 33%, within-1 88%.** Claude is
  harsher by a near-constant 0.5 at every level. **The ORDERING survives (both put advanced top),
  the SCORE does not** — never quote an absolute judge number as a quality figure.
  Best-agreed criterion = cognitive demand (κ 0.59, r 0.78); worst = **grounding accuracy
  (κ −0.04, within-1 only 52%)**. Control: re-running Qwen on the frozen prompts reproduced 07-29
  **exactly — 252/252 ratings, zero differences, κ = 1.00** (`judge_qwen_2026-07-31/`), so the
  local judge is deterministic and the gap is the rater. **The JUDGE reproduces; the WRITER does
  not** (19/21 vs 16/21) — quote a single-run judge number, never a single-run generation number.
- **AXIS 4 SCORED for the first time on the current figures** (`Claude Opus 5`, 7 blind vision
  agents). By modality basic/int/adv: image 3.71/3.50/3.86, graph 3.36/3.14/3.25, table
  n/a/3.36/3.25, **annotation 4.29/4.43/4.29**, all 3.59/3.40/3.45. **Modalities are per TIER and
  an absent one is `n/a`, NEVER a low score** (basic ships no table by design). **No tier ladder
  in Axis 4** → the difficulty claim rests on the PROSE; do not cite Axis 4 for it.
  **`annotation_correctness` is the strongest row in the whole eval** = the independent evidence
  the direction fix landed. Tools: `export_multimodal_prompts.py`, `build_multimodal_table.py`.
  Full record `docs/axis4-multimodal-2026-07-31.md`.
- **⚠ REGRESSION I SHIPPED AND FIXED THE SAME DAY.** The 07-31 `REST_WORDS` change printed
  "not turning" on rest bands; the segmenter marks bursts as INACTIVE, so `computerfan-4029` shipped
  a band captioned "not turning" over samples at **24.14 rad/s**. **11 of the corpus's 12 rest bands
  carried a caption their own curve contradicted** (the 12th is an all-NaN dropout, correctly kept).
  Fixed by `figures._rest_label_is_contradicted` — word suppressed above 5% of series max, shading
  kept; `tools/tests/test_phase_label_honesty.py` (7 tests); all 7 clips re-rendered,
  `verify_figures` clean. **The SEGMENTATION is still wrong and is open.**
- **Deck + memo for 2026-08-05** written (`presentation/centri-weekly-2026-08-05.{tex,pdf}` +
  `-memo.md`), 17 frames. CLAUDE.md rule #5 amended: the ≤60-word budget covers **prose only**,
  tables and figures are exempt.
- All 42 English worksheets regenerated and recompiled; **the 42 Bahasa PDFs are STALE** (they
  embed pre-fix figures).

### ⚠ PIPELINE TRAP — a renderer edit does NOT reach a workspace
**Every workspace carries a FROZEN COPY of `analysis/`**, and re-rendering from inside one imports
THAT copy (CWD leads `sys.path`), not `workspace_lib/`. Editing
`workspace_lib/analysis/render/figures.py` and re-rendering appeared to succeed and changed
nothing — the PNG came back byte-identical with the false caption still on it. Sync first:
`for d in workspaces/job_*/; do cp workspace_lib/analysis/render/figures.py "$d/analysis/render/figures.py"; done`
then re-render. **Confirm by diffing the two copies, never by re-running and hoping.**

### ⚠ Claims RETRACTED 07-31 — do not repeat
0. **"The redraw of the figures introduced ZERO new gate failures — that is the evidence the figure
   work did not disturb the text."** The gate was clean and the figure was FALSE (see the
   "not turning" regression above). The gate checks that annotations trace to the seed; it never
   asks whether a band caption agrees with the curve beneath it. **A clean gate is evidence about
   the gate's questions.** Only Axis 4 (a rater that sees the image) caught it.
1. **"Where the judge and the deterministic checker disagree about a number, the checker has been
   right."** False. The checker verifies a number *traces to the seed*; it cannot ask whether the
   measurement is sound. On turntable-3 the LLM judge caught a contaminated 7.45 m/s² that the
   checker passed. **Tracing is not validating.**
2. **"turntable-3's 7.45 vs 5.82 gap is the Jensen lesson the passage teaches."** The gap is
   inflated by a tracker artifact. Jump-free the two are 5.85 and 4.99 (17%, not 28%).
3. **"The tracker jumps explain turntable-3's mid-coast speed-up."** They do not — see below.
4. **"Cognitive demand is the one judge row that climbs cleanly."** Five of twelve rise
   monotonically (cognitive_demand, completeness, concept_accuracy, variable_name_consistency,
   grounding_accuracy); one falls (realistic); six neither.

### What landed this session
The 07-23 pedagogy plan (`agent-backend/docs/material-pedagogy-plan-2026-07-23.md`) is **built in
full**, plus a second pass answering a pedagogical audit of the result:

- **The direction-sign defect is fixed.** `motion_type` came off `sign(alpha)`; both ceiling-fan
  clips turn the way the tracker calls negative, so a coast-down fitted α = +0.17 and one BASIC
  worksheet taught *"speeding up motion"* over a graph reading "slowing down".
  `kinematics.alpha_along_rad_s2` = d|ω|/dt decides it now, and `common.motion_along_travel(stats)`
  is the ONE reader-facing view (α along travel, a_t signed against motion, endpoint ω as SPEEDS).
  It back-derives from the ω endpoints, so an archived `stats.json` renders correctly. Exactly 2 of
  7 clips flip.
- **Reading level, order, staircase**: rule 8c bans calibration / scale-free / Jensen / ⟨·⟩ with the
  formal version re-routed to a teacher-copy-only `teacher_notes` block; intermediate reads the
  graph before the equation (`SECTIONS_INTERMEDIATE` + `report._material_order` — do not let those
  drift); `TIER_STEPS` gives three graded steps per level, each ending in a checkpoint rendered
  where the step really ends, with bridges naming the next step.
- **Figures**: basic gets the same four-arrow frame as the other tiers via
  `fig_annotated_image(plain=True)`, labelled in words; a rectified clip carries `*_uncorrected`
  CSV columns so ω(t) and a_c(t) draw the measurement AND the correction.
- **The reader now does something** (second pass): predict-before-the-reveal, step checkpoints,
  the documented misconceptions, a transfer prompt, self-placement, and faded worked examples at
  advanced. All deterministic; every answer held for the teacher copy.

### Numbers that are current
- **Gate: 19/21 on the rules as shipped; 13/21 with the new same-moment rule wired in.** The A9
  `rate_period_referent` rule fires 12× across 6 worksheets, all BASIC. The 2 non-A9 failures are
  a banned "frame" (fan-4027 advanced) and an ungrounded "1.8 seconds" (turntable-1 intermediate).
  **The redraw of the figures introduced ZERO new gate failures** — that is the evidence the
  figure work did not disturb the text. (The older "21/21" was an offline run; do not quote it.)
- **A9 agrees with the LLM judge clip for clip**: the same six flagged; turntable-3 — the one it
  passes — is also the only basic worksheet the judge scores 5/5 on grounding (the other six score
  1,1,1,2,2,3). Two raters, no shared code.
- **LLM judge (Qwen3.6-35B), 12 criteria × 21 worksheets, 1–5**: axis means
  linguistic 3.97/3.91/4.49, structural 4.20/4.11/4.46, physics-tier 3.50/3.43/4.43;
  all-12 **3.99 / 3.92 / 4.46**. Cognitive demand 2.86→3.86→4.71. Grounding 2.14/2.71/4.43.
- **Second judge (Claude Opus 5), same rubric, same frozen prompt**: all-12
  **3.45 / 3.43 / 3.96**; cognitive demand 2.43→2.86→4.14; grounding 3.14/3.00/3.29.
  **κ = 0.34** (quad) / 0.08 (unweighted) over 252 pairs. Quote the ORDERING, never the level.
  On `turntable-3` advanced — the worksheet whose numbers are wrong — Qwen scored grounding **5**
  and Claude **2**; a single rater would have reported whichever it drew.
- **BERTScore vs OpenStax §6.2**: F1 by level 0.800 / 0.824 / 0.831, all 21 **0.818 ± 0.014**.
  Within-level SD is ±0.003 — nearly all the variance is BETWEEN levels, so the metric reads the
  tier, not the clip. Diversity 0.227 / 0.317 / 0.322 (basic is the most formulaic). BLEU-4
  0.015/0.032/0.040. **n = 21 counts WORKSHEETS** (7 clips × 3 levels); a per-section figure is
  n = 105 — say which.
- **Element interactivity rises 7/7 clips**: 4.9 → 13.9 → 44.9 (mean). **CORRECTED 08-03** —
  recomputed from the 21 shipped worksheets via `material_gate.ei_score`; the old "5 → 19 → 44"
  was wrong at intermediate. **⚠ And the 7/7 is ENFORCED, not observed**: `cross_tier_issues`
  fails a set whose EI does not rise and `material_tiers.main()` regenerates the implicated
  tier. Cite it as a conformance check; the difficulty claim rests on cognitive demand
  (rises for BOTH judges, κ 0.59). See `TODO.md` §1.1.
- **Readability**: basic went 15.8 → 8.2 words/sentence, FK 7.2 → 4.3. Advanced is now the hardest
  of the three on both. They are still NOT strictly ordered by reading grade (intermediate reads
  easiest) — do not claim monotonic.

### ⚠ Two claims RETRACTED this session — do not quote the old ones
1. **The 07-23 plan deck's "reading grade 7.8 / 8.1 / 11.7" does not hold** and is not repeated.
   Measured on the trusted set the FK ladder rose on **1/7** clips (recomputed 08-03: FK
   4.59 / 4.31 / 6.63, w/s 8.33 / 7.06 / 12.41; the "0/7" written here earlier was wrong). Report FK; do not optimise it.
2. **`presentation/figs/mk_corrected_ac_fig.py` overstates the correction.** Its "before" comes
   from the archived pre-coordfix run, so it also carries the 232 px coordinate bug (peak ~60
   m/s²). The shipped figure isolates the camera angle alone: swing 7.8–31.8 → 9.8–23.0, mean
   essentially unmoved (16.2 → 16.1).

### ⚠ Still binding from 07-21 — read before quoting any ripple number
- **Cross-tracker agreement figures were inflated by the at-rest tail.** Honest values on the 79
  shared ACTIVE frames: ripple correlation **r = +0.81 (not 0.98)**, mean-ω agreement **1.7% (not
  0.10%)**. Any agreement statistic must exclude the dead segment.
- **turntable-3's ripple is NOT demonstrably phase-locked.** No clip in the corpus beats its own
  surrogate null; on a 1.5-revolution clip the statistic invents 20–30% of variance from noise, and
  the shipped `PHASELOCK_UNRELIABLE = 0.60` has a **5.2% false-positive rate**. 4046's
  pre-rectification 0.94 over 18.6 revs *is* real. Recommended, not built: per-clip surrogate test
  instead of the constant.
- **turntable-3's mid-coast speed-up is an artifact, cause unidentified** — it joins `bicycle` in
  that bucket. Ruled out: marker centroid, motion blur, perspective, wrong centre, real torque, and
  SAM3's masks specifically (LocateAnything-3B reproduces it). **07-31: still open, and the
  07-21 sighting can no longer be re-tested** — t≈3.05–3.15 s is now a 13-frame tracking dropout
  with no samples. The current run has its own coast-phase rise (v 0.73→1.92 m/s over
  t≈2.28–2.64 s) that is NOT inside any jump-contaminated window. The tracker jumps below do NOT
  explain it; a draft that said they probably did was wrong.
- **⚠ 07-31 turntable-3 IS NOT TRUSTED — its published numbers are wrong by 27%.** The tracked
  marker teleports: normal step 1.4 px, but **604 / 614 / 713 px in a single frame** at
  t = 0.85 / 1.74 / 2.08 s, flipping between two positions 728 px apart. One jump is INSIDE the
  active window, so 18 of 106 active samples are contaminated. Smoothing spreads each step into a
  symmetric ramp (~±12 frames), which is why they render as mountains, and why ω climbs 0→10.2
  rad/s while the position is frozen to 0.1 px. Effect: **mean a_c 7.45 → 5.85, max 31.06 →
  18.12**. The worksheets teach **7.45, which is 27% ABOVE the jump-free value** (quote it that
  way round — the same pair is a 21% drop measured off the shipped number, and mixing the two
  bases is how this gets misquoted).
- **Corpus sweep (07-31): 5 of 7 clips are CLEAN.** Only turntable-3 (3 jumps, 1 active) and
  computerfan-4029 (4 jumps, all in the dead tail, headline numbers unaffected). Detect per clip
  against its OWN local median step — a fixed px threshold is useless because computerfan-4029
  legitimately moves ~240 px/frame at peak. **The detector compares consecutive frames, so a jump
  straddling a NaN dropout is invisible to it** (turntable-3's 521 px re-acquisition at t=3.21 s
  follows a 13-frame gap and is consistent with real motion). Generator:
  `presentation/figs/mk_jump_fig.py`. **Nothing in the delivered pipeline rejects a jump — a guard
  is UNBUILT.**
- **The accuracy limit is the MARKER, not the projection model.** The next real gain is a small
  flat high-contrast sticker — camera work, not mathematics.

---

## 1. Open work

**Teaching (needs people, not code)**
- **Teacher ratings.** The only thing that answers "does this teach?". Everything measured so far is
  a property of the text. P-MAGIC has 10 teachers at 8.2–8.6/10; Centri has one expert reader.
- **Should the no-forces rule (gate rule 8b) stay?** It keeps every claim inside what the video
  measures, and it puts the commonest circular-motion misconceptions out of reach.
- **Are the three steps the right three?** The staircase is built and climbable; its shape is a
  teaching judgement.
- **Bahasa Indonesia edition** — built (42 documents, `translations_id_20260730/`), but the PDFs
  are stale after the figure fix and need re-running.

**Measurement / model**
- **⚠ FIRST: decide what happens to turntable-3.** Either reject the 3 jumps before the statistics
  are computed and regenerate, or withdraw the clip until it is re-tracked. Its 21 → 18 worksheets
  currently teach a number 27% too high.
- **⚠ Build a jump guard.** The sweep that found this was written by hand for the 08-05 memo;
  nothing in the delivered pipeline rejects a marker that moves 500× its usual step, and nothing
  would catch it on the next clip. Detect against the clip's OWN local median, and handle the
  NaN-dropout case the hand sweep misses.
- **Why the detector jumps is UNKNOWN** — needs the raw detection boxes, not the kinematics.
  turntable-3 alternates between two positions 728 px apart; the scene has one red phone, a metal
  ruler and a hand entering frame, so a second candidate is plausible but unproven.
- **Re-run the 42 Bahasa documents** — they embed the pre-fix figures.
- **A stronger writer or a select-from-K loop.** The one remaining failure class is the local 35B
  repeating a banned word when told to fix it. Durable lever stays first-pass steering via
  `analysis/material_hints.md`.
- ~~**Re-film two clips** with a flat high-contrast sticker~~ **DONE 08-06** — see §00a; both
  ceiling fans replaced by `fan-4656`. **The ruler half is NOT done and is now the blocker:** a
  ruler or known-length tape flat on a blade **in the plane of rotation**, which validates rate
  and scale in one shot.
- **⚠ CORRECTED 08-03: `IMG_3075.csv` is the TURNTABLE trace, not a ceiling fan, and its video
  half WAS shot and analysed.** It pairs with `job_turntable-3-rect/input_video.mp4` (archived at
  `workspaces-archive/pre-full-e2e-20260729/`), 490 samples ~60 Hz, `gyro_gamma` = the turntable
  axis. **The sensor validation is therefore on the RECTIFIED workspace, NOT the shipped one:**
  rect `r_fit_m` 0.1477 / mean ω 5.794 / mean a_c 5.686 / max a_c **14.13** (= the ablation doc's
  "peak a_c") vs shipped `job_turntable-3` `r_fit_m` **0.2037** / mean ω 5.458 / mean a_c 7.449 /
  max a_c 31.06. The radius differs by 38%, so a SECOND ~31% effect sits on this clip's headline
  number beside the tracker jumps, and the two have never been separated — see `TODO.md` §1.4.
  Four different mean-ω values for this clip exist across the docs (5.458 / 5.660 / 5.794 / 5.811);
  **always name the workspace beside the number.** A ceiling-fan-with-sensors clip is still
  UNSHOT and is still wanted.
- **One unexplained clip** (bicycle) — repeating wobble that is not the camera angle.

**Known, low priority**
- `PHASELOCK_UNRELIABLE` should become a per-clip surrogate test (see above).
- The park wheel waits in `templates-reshoot/base-template-parkwheel-4091/` — no validated tracker
  follows it yet, however good the footage.

---

## 2. Who & what / goal

MSc thesis, Hwang lab. **Centri** = phone video of circular motion → measured kinematics → tiered
physics worksheets with annotated figures. Sibling app **P-MAGIC** does the same from phone
*sensors*; the parent line is the **Utami dissertation** (SocioMathLLM, Geo-QG). The contribution is
video-based generation plus multimodal annotation, and the honesty layer around the measurement.

---

## 3. Ops quick-reference
- **Submit job:** `POST 10.0.0.2:8088/analyze` `-F "video=@f;type=video/mp4" -F "sidecar=$(cat
  sc.json)"`, header `X-API-Key: $(grep ^API_KEY= agent-backend/.env|cut -d= -f2)` (octet-stream
  rejected). **Re-enqueue:** `docker compose exec -T -w /app worker python -c "from worker.tasks
  import run_pi_analysis; run_pi_analysis.delay('<job_id>')"` (idempotent).
- **Workspaces carry a STALE `analysis/` copy** (seeded at job creation, root-owned): `cp` fixed
  `workspace_lib/analysis/*` into `workspaces/job_*/analysis/` before re-running a stage;
  `rm -rf analysis/render/__pycache__` first. New jobs via `POST /analyze` reseed from current
  `workspace_lib`.
- **TAIL REPLAY — test a material/figure change with no agent and no SAM3 (~5 min).** Clone a
  workspace with a good `pipeline_inputs.json`, drop in current code, run the deterministic steps.
  The worker mounts workspaces at the HOST path (`/home/damar/centri/agent-backend/workspaces`):
  ```
  W=/home/damar/centri/agent-backend/workspaces
  docker compose exec -T worker bash -c "cp -a $W/job_X $W/job_X-r2 && rm -rf $W/job_X-r2/analysis \
    && cp -a /app/workspace_lib/analysis $W/job_X-r2/analysis \
    && find $W/job_X-r2/analysis -name __pycache__ -exec rm -rf {} +"
  docker compose exec -T -w $W/job_X-r2 worker bash -c 'python -m analysis.run && \
    python -m analysis.render.figures && python -m analysis.material_tiers && python -m analysis.render.report'
  ```
  **Offline variant used all this session** (no Docker at all): copy `analysis_output` + current
  `workspace_lib/analysis` into a scratch dir and run `python3 -m analysis.material_seed`,
  `analysis.render.figures`, `analysis.render.report`, `analysis.material_tiers` in it.
- **⚠ `workspaces-archive/` IS NOT BIND-MOUNTED — archiving from inside the container writes to
  the container's EPHEMERAL LAYER** (08-06, nearly lost 1.7 GB). Only `${WORKSPACE_DIR}`
  (`workspaces/`) is mounted, at the same path on both sides, which is what makes an in-container
  `mv workspaces/job_X workspaces-archive/...` look like it worked: the source is shared, the
  destination is not. A `docker compose down` would have destroyed `job_fan-4027`,
  `job_fan-4028` and `job_turntable-3`. Recovered with
  `docker cp <worker>:/…/workspaces-archive/<dir> workspaces-archive/`.
  **Archive from the HOST** (workspaces are root-owned, so `sudo`), or `docker cp` straight out.
  Corollary: `ls`/`find` run through `docker compose exec` shows the CONTAINER's view of any
  unmounted path — an archive dir can look empty or missing when the host copy is fine. Check
  from the host before concluding anything is lost.
- **⚠ A TAIL REPLAY CANNOT DELIVER A TRACKER FIX** (learned 08-06). `analysis.run` reads
  **`pipeline_inputs.json`**, not `api_cache.json`, and the trajectory is baked into it by the
  agentic half — so re-running the tracker and rewriting `api_cache.json` changes nothing
  downstream. Compounding it: the workspace's frozen `analysis/` shadows `workspace_lib`, so a
  sync list missing the file you changed runs the OLD tracker while appearing to work
  (`grep -c relock_after` both copies); and tracking is in CROPPED coordinates, so re-tracking the
  full frame produces a bogus "hundreds of px changed" comparison. **A tail replay is valid only
  for changes DOWNSTREAM of the trajectory** — figures, material, report. Perception needs e2e.
- **A full e2e re-run of 4046 is not free:** it died on the 1024 MB runaway guard in the track phase
  (the injected hints send the agent prototyping rectification). Prefer the tail replay for
  material work; keep e2e for perception changes.
- **Worker kills:** `celery revoke --terminate` stalls the prefork pool → `docker compose restart
  worker`; `pkill -9 -f "[m]aterial_tiers"` (bracket trick — a plain pattern self-kills); long
  in-container runs: launch `docker exec -d` (a foreground "timeout" leaves orphans racing on files).
- **`cleanup_expired_workspaces` (hourly) + job deletion REMOVE workspaces** — export promptly.
- Calibration `px_per_m = reference.diameter_px / physical_size_m` — **the two must describe the
  SAME span**; in `frequency` mode both are RADII despite the field name. zsh: `status` is read-only.
- Detection cues = simple nouns (`docs/object-detection-prompts.md`); `tools/prompt_sweep.py` ranks
  cues on a short clip (`--reset` kills SAM3 — leave OFF).

---

## 4. File map (pointers)
- **Material pipeline:** `workspace_lib/analysis/{material_seed,material_tiers,material_gate,
  kinematics,common,quality_signals}.py`, `render/{report,figures,annotate}.py`, first-pass steering
  `analysis/material_hints.md`, spec `docs/difficulty-tiered-material-spec.md`, orchestrator
  `prompts/orchestrator.txt`. Pedagogy plan + status:
  `docs/material-pedagogy-plan-2026-07-23.md`; earlier critique
  `docs/material-pedagogy-critique-2026-07-14.md`.
- **Tests** (all offline, no LLM): `agent-backend/tools/tests/test_*.py`. `test_material_gate.py` is
  the big one and pins every gate rule including the four "the pipeline asked for what its own gate
  refuses" fixes.
- **Data quality (07-15/07-21):** evidence `agent-backend/docs/tracking-data-quality-2026-07-15.md`;
  report `technical-report/centri-video-data-quality.tex`; per-clip guidance
  `agent-backend/templates/*/hints.md`; re-shoot spec `agent-backend/templates-reshoot/README.md`;
  ablation `ABLATION_METHOD_STUDIES.md`.
- **Eval:** `tools/{run_material_eval,run_multi_reference_eval,grade_material_grounding,
  grade_material_difficulty,run_llm_judge,build_rater_sheet,eval_stats}.py` (`.venv-eval`);
  framework docs `agent-backend/docs/eval-*.md`.
- **Two-judge reliability (07-31):** full record + reproduction in
  `agent-backend/docs/judge-reliability-2026-07-31.md`; method layer in `eval-framework.md` §4a;
  log entry in `eval-progress.md` "Update 3". Tools:
  `tools/{export_judge_prompts,run_judge_from_prompts,judge_agreement}.py` — **freeze the prompt
  once and replay it**, or a score gap between raters cannot be attributed to the judgement.
  `build_pmagic_tables.py --judge-dir-b` fills the κ column. **Staging gotcha:** `--materials`
  keys on the filename stem and every clip's file is `material.basic.json`, so glob the workspaces
  directly and 21 worksheets collapse to 3 — stage as `<clip>__<tier>.json` (auto table must show
  n = 7 per level, n = 21 total).
- **Decks:** weeklies `presentation/centri-weekly-*.tex` (latest `2026-07-27`); general-audience
  overview `centri-talk-intro-2026-07-27.tex`; plan deck `centri-plan-2026-07-23.tex` (never
  presented). **6 treatment rules in repo `CLAUDE.md`** — they govern WEEKLIES; the talk deck
  departs from rule #5 on purpose and says so in its header. Figure generators live beside the
  figures (`presentation/figs/mk_*.py`) because PNGs are gitignored.
- **Research docs:** `PAPER_GAP_ASSESSMENT.md`, `PAPER2_LEARNING_STUDY.md`, `refs/document-3.pdf`
  (P-MAGIC preprint), `refs/document-4.pdf` (P-MAGIC journal), notes `note-*`.
- **Trackers:** SAM3-CPP prod **`/home/damar/centri/sam3/`** (`api_master_sam3.py`, `api_master.py`,
  `run_sam3.sh`) — corrected 08-06; `run_sam3.sh` and the worker/model paths inside still point at
  the dead `/home/damar/sams2/sam3cpp/`, which is why `/track` 500s;
  LA experiment `test/locateanything_worker.py` (:8087, slow — not adopted).
- **Memory files** (cross-session context): `~/.claude/projects/-home-damar-centri/memory/` —
  `centri-{tiered-material,annotation-reorder-progress,e2e-run-plan,eval-plan,
  eval-multimodal-pivot,thesis-contribution-titles,pmagic-alignment,utami-dissertation,
  second-pc-lab2,sam3-chunk-fix,detection-prompt-wording,kinematics-center-and-spinup,
  video-literature-review,presentation-style,deck-axis-terminology,tracking-data-quality,
  checkpoint-hygiene,team-pedagogy-gap,phaselock-null,phaselock-trust-channel,dropped-frame-guard,
  coordinate-space-guard,locateanything-ablation,templates-gold-only}.md`.
