# Session Checkpoint — 2026-07-21 (4046's "perspective" was mostly a 232 px COORDINATE BUG)

Single source of truth to resume after a context reset. **Compacted 2026-07-15** — completed work
was removed; it lives in `git log -p SESSION_CHECKPOINT.md` (full pre-compact text at `HEAD`),
the memory files (`~/.claude/projects/-home-damar-centri/memory/centri-*.md`), and the docs cited
below. Keep this file short: current state, open work, ops crib — not a diary.

## 00. RESUME HERE — 2026-07-21 (later): the turntable ripple, the trust channel, and a blocked ablation

### ⚠ STATE ON STOPPING — two things are broken/blocked
- **Qwen `192.168.1.205:8083` is DOWN** (`http_code=000`; was `ok` earlier today). Damar took the
  GPU for the LocateAnything ablation. **Nothing that needs the LLM can run**: perception Step 1,
  material generation, the gate.
- **Two e2e jobs are STALLED at 6%** (`job_turntable-2-suppress`, `job_turntable-3-suppress`),
  parked in "Look at the video" waiting on Qwen, and **turntable-2 is holding the Celery worker so
  turntable-3 can never start**. Kill both before queueing anything (`docker compose restart worker`
  if revoke stalls). They were validating the trust-channel change below and **never completed** —
  checks 6 (material prose) and 7 (gate) are UNVERIFIED. Everything deterministic was verified by
  replay.

### THE TURNTABLE RIPPLE — Damar spotted a speed-up that cannot be physical
`job_turntable-3-rect/plots/v_t.png` shows the turntable **speeding up at t≈3.05–3.15 s** mid
coast-down. Chased through every mechanism available; the honest end state is **artifact, cause
unidentified** — it joins `bicycle` in that bucket.

| ruled out | by |
|---|---|
| marker centroid sliding on the phone | the phone's own ORIENTATION carries the same ripple |
| motion blur | imaged size constant to +1% across a 3× speed range |
| perspective | hub offset 0.7 px, orbit round to 1.002 |
| wrong centre | radial residual 2.1 px rms (0.52%) |
| real torque (table not level) | ripple scales as **ω^0.7–1.1**, not ω⁻¹ |

**The scaling test is the discriminator**: a fixed geometric error gives ripple ∝ ω; a fixed torque
gives ∝ 1/ω. **CAUTION — my first run of it was wrong**: a global cubic detrend cannot follow a sharp
decay and inflated the fast half (reported 3.6×; the honest figure with a one-revolution LOCAL
detrend is 1.5–1.9×). Same trap as the computerfan detrend. **Always detrend locally at the
revolution scale.**

**DAMAR'S READ WAS BETTER THAN MINE — box quality varies with ANGLE.** I tested mask size against
SPEED (constant, so "not blur") and never against ORBITAL PHASE. Measured on turntable-3:
- the phone's **measured length varies 432→470 px with angle, 44% phase-locked** (1/rev amp 10.4 px).
  A rigid object's length cannot depend on its angle ⇒ **detector artifact**.
- rigidity check (orientation − orbital angle, which must be CONSTANT for a co-rotating phone):
  **3.7° peak-to-peak, 0.7° rms**, 36% phase-locked.
- I had read "the orientation carries it too" as EXCLUDING a mask problem. It is the **signature** of
  one: a mask that loses an end region at certain angles shifts the centroid AND rotates the fitted
  box together. **Retracted.**
- Not fully accounted for: a ~10 px length wobble implies ~5 px of centroid shift, but the tangential
  wander is ~15 px rms / 116 px p-p (25% of the phone's length). Present and phase-locked, magnitude
  unexplained.

### SHIPPED: the trust channel no longer clears what it cannot explain (`3960dec`, `cdaa664`)
`quality_signals` required an **elliptical orbit** before distrusting a phase-locked ripple —
oblique capture being the cause it was derived from on 4046 — so **any phase-locked ripple on a round
orbit was cleared however large**. A synthetic round orbit with **99% of its variance locked to
orbital phase** was declared reliable. Motion cannot repeat with orbital POSITION rather than time,
so that signature now convicts on its own; the axis ratio only decides whether the guidance may NAME
a cause, and on a round orbit it says the cause is unidentified instead of inventing a slant.
Second hole: nothing counted revolutions. Below 2 the statistic fits 4 harmonics to ~1.5 cycles and
can neither convict nor clear — a caveat the tech report states and the code never encoded. New
`per_instant_omega_unverified` + `MIN_REVS_FOR_PHASELOCK=2.0`. Flags exactly turntable-2 (1.5 rev,
23% ripple) and turntable-3 (1.8 rev, 17%); the other five untouched, including the fans whose
30–42% ripple tracks TIME not phase.

**FIGURES: the two reasons want OPPOSITE treatments** (`cdaa664`). Keying the existing 1-rev boxcar
on both flags looked like a one-line win and **was a measured 22% distortion**: the window is
`period_s × fps`, which on turntable-3 spans **44% of the active record** and cut a genuine 1.44 m/s
flick peak to **1.09**. Diagnosed artifacts (long clips — 4046 is 18.6 rev, window 5%) still get the
boxcar; **unverified clips keep the raw measurement and carry a printed note**. The bump stays
visible because it IS the data; what changed is that nothing presents it as physics.
**Tests 58** (`test_quality_signals.py` 7, verified to fail on the old rule).

### LOCATEANYTHING-3B ABLATION — set up, not run
Damar's proposal: swap SAM3 for **LocateAnything-3B** (`locateanything-3b/`, 7.3 GB) as the tracking
server and see if box quality improves. **Motivated** — SAM3's boxes demonstrably vary with angle,
and my "orientation shows it too" test could not separate mask-level effects because both derive
from the SAME SAM3 mask. A different segmentation is the clean test.

- **USE THE `locateanything` CONDA ENV**: `/home/damar/miniconda3/envs/locateanything/bin/python`
  (torch 2.12.1+cu130 / torchvision 0.27.1+cu130 matched, transformers 4.57.1, flash_attn 2.8.3 ⇒
  the faster `la_flash` kernels). **The base env is BROKEN for this** — torch cu130 vs torchvision
  cu128, so `import torchvision` fails outright and `transformers` cannot load. Do not "fix" base.
- Worker: `test/locateanything_worker.py`, port **8087**, has a `/track` endpoint that is already a
  drop-in for SAM3's (returns `{frame,cx,cy,bbox}`) with a `stride` arg for cheap timing.
- **Scope is 4 clips, not 7**: only 4046 + turntable-1/2/3 use SAM3 object tracking.
  computerfan-4029 is COLOUR-thresholded and the fans are FREQUENCY (blade-pass FFT) — no object
  tracking to replace.
- **LA returns axis-aligned BOXES only** (no mask, no oriented box), so the "rigid length vs angle"
  metric does NOT transfer: an axis-aligned box around a rotating rectangle must change size by pure
  geometry. Compare on the TRAJECTORY: ripple CV, phase-locked fraction, radial residual, whether
  the t≈3.1 bump survives, and mean-ω agreement between trackers.
- **SAM3 baseline already measured** (turntable-3): length spread 432–470 px / 44% phase-locked;
  rigidity 0.7° rms; ω ripple CV 0.17, phase-lock 0.26; tangential wander 116 px p-p.
- Prior `test/compare_sam3_vs_locateanything.py` is **single-frame only** (IoU/latency/coverage) —
  it never tested trajectory quality, so it does not answer this.
- **Best metric this gives us**: *does the measured size of a rigid object depend on its viewing
  angle?* It must not. Needs **no ground truth** — the thing the tech report calls the most valuable
  missing piece.

**Workspaces cleaned to the 7 trusted runs** (3.6 G → 2.1 G). Scratch clones deleted after verifying
their archived originals; superseded/failed runs moved to `workspaces-archive/superseded-*`.
`WORKSPACE_TTL_HOURS=720` (30 days), so the checkpoint's "export promptly" is about the mechanism,
not urgency.

## 00a. 2026-07-21 (earlier) — the 4046 coordinate bug; annotation now draws the measurement

Damar looked at `job_roundabout-4046/analysis_output/plots/annotated_image.png` and asked whether
the naive circular projection was only cosmetic or also in the data. **Both — and underneath it
sat a bigger, unrelated defect.** Commit **`d825e61`**. Memory: [[centri-coordinate-space-guard]].

**THE COORDINATE BUG (dominant).** The agent tracked on the CROPPED video but detected the axle on
the FULL frame, then declared the pair `coordinate_space: "display"`. `contract.load_inputs`
subtracted the crop offset from both ⇒ **trajectory and centre 232 px apart**. Verified by
overlaying both candidates on a real frame: the stored point sits on the handle, the used point
floats in mid-air. Nothing downstream could see it — the orbit read as real-but-eccentric, and the
flags that fired (`radius_unstable`, `omega_spike`, `ransac_fit_rejected`) blamed the physics.
Hit `job_roundabout-4046`, `-r3`, and **`-r4`** (the run 07-20 called "the one to show"); the other
9 jobs were clean.

| | before | after |
|---|---|---|
| std_r | 0.114 m | 0.035 m |
| std_ω | 4.47 | 1.16 |
| max a_c | 235.5 | 31.2 |
| r_fit | 0.281 m | 0.254 m |
| mean a_c | 22.78 | 15.83 |
| period vs 2π/ω | 1.072 vs 0.798 ✗ | 0.808 vs 0.804 ✓ |

**THE GUARD.** A trajectory and a centre in the same space trace a steady radius, so the two
readings are separable with no scene knowledge: `contract` compares radius CV both ways and keeps
the self-consistent one, raising `trajectory_space_mismatch`. 4046 = 0.437 vs 0.144; every other
clip's declared reading already wins ⇒ inert (9 jobs load byte-identically; replayed sample shows
**0 numeric diffs**, flags identical). Tests `tools/tests/test_contract_space.py` (7); suite 51.
**Root cause is the AGENT seam** — `prompts/orchestrator.txt:31` makes `pipeline_inputs.json` the
one place in full-frame space while all else is cropped, and the example at :910 pairs
`center_cx_full` with a `traj_x` taken from the cropped video. The guard is a net, not a cure.

**ANNOTATION DREW THE MODEL, NOT THE MEASUREMENT.** Both renderers re-projected the marker onto the
fitted circle (`cx + r_fit*cos θ`) — mean **186 px / max 430** off the handle on 4046 — and drew the
orbit as a circle though a circle filmed off-axis images as an ellipse. Now they plot the measured
`x_px,y_px` and trace a least-squares ellipse (`common.fit_orbit_ellipse`; **drawing only**, every
number still from the circle fit). Fitted ellipticity: 4046 **0.890** (tilt 27°), computerfan-4029
and turntable 0.967, **fan-4028 1.000 — its orbit is SYNTHESIZED** (frequency mode, radius CV
0.0001), so its circle cannot be tightened from the track. Measuring 4028's true swept extent from
the footage is so far unreliable (328–348 px by sweep-energy vs 404–520 px by darkness, both
contaminated by the ceiling lights) — and that measurement IS the independent scale cross-check
OPEN 0 wants.

**PROJECTION — FIXED, Damar chose "give rectification a home" (commit `dc9a36d`).** New
**`analysis/rectify.py`**: uncalibrated vanishing-line construction (the polar of the imaged hub
w.r.t. the fitted orbit conic is the plane's line at infinity → map it to infinity → stretch the
ellipse to a circle). `geometry.calibrate` runs it **before any radius or angle is measured**,
gated on a new **optional `hub_px`** in the contract AND on a 20 px hub-offset floor (corpus
0.7–8.8 px; 4046 85.6; parkwheel 60–73 — so rectifying the near-affine clips would fit `l` to noise).

| 4046, through the real pipeline | before | after |
|---|---|---|
| ripple CV | 0.096 | **0.033** |
| phase-lock | 0.884 | **0.065** |
| 2/rev amplitude | 0.996 | **0.079** |
| radial residual | 5.22% | **3.42%** |
| mean \|ω\| | 7.8077 | 7.7999 (**0.10%**) |

Angle redistributed within a revolution, revolution count untouched — the check that separates this
from smoothing. Using the ellipse CENTRE instead of the axle is **worse** (0.163): no
centre-shifting shortcut exists, and `rectify` now refuses that input rather than silently
no-op'ing. **`r_fit_m` 0.254 → 0.260** — the rectified plane is pinned to the imaged ellipse's
MAJOR semi-axis (the direction perspective never shortened) so `px_per_m` keeps its meaning; the
conservative alternative (preserve the median radius, so only ω(t) moves) is a one-line change.
**`per_instant_omega_unreliable` no longer applies to 4046 once rectified.**

**THE DEADLOCK WAS BROKEN BY INVERSION.** The hints used to hand the agent a rectification recipe
*with code*; it built its own `rectify.py` and blew the **1024 MB runaway guard** twice
(`roundabout-4046-coordfix` at 244 s; `-r2` on 07-20), each time leaving a **garbage contract**
(x range 0.0–0.1, y ≈ 232 constant, mean ω 0.0). On the one run that finished (07-20) it wrote
`rectified_trajectory.json` and shipped the RAW track anyway, because the contract had nowhere to
put the other one. Now the agent's whole part is **detect the axle, pass `hub_px`** — stated in
`prompts/orchestrator.txt` (new FROZEN rule) and rewritten into the 4046 hints.

**NaN TRAP (nearly shipped):** `writer.py` dumps with `allow_nan=False`, and a *skipped*
rectification leaves every diagnostic NaN ⇒ `stats.json` truncated mid-write. Caught only by
re-running the clips the change was meant NOT to touch (Damar's "randomly sample existing jobs").
Fixed in `Rectification.as_dict()`, with a test. **Regression proof:** turntable-2/-3,
fan-4027-r3, fan-4028, computerfan-4029 all **0 numeric diffs + identical flags**, each now
recording *why* rectification was skipped. Tests **51** (`test_rectify.py` 8: uniform-rate recovery
through a known homography to machine precision, sign-of-ω preservation, ellipse-centre refusal,
JSON-safety).

**SEED ARITHMETIC (`32ae15e`)** — `material_seed.py` worked examples must close on the figures they
PRINT. 4046's basic tier showed `1.2 × 15 s` and concluded `≈ 19 laps` (it computed from
f = 1.2479 × 14.998 = 18.72 while displaying rounded factors), so the gate failed the tier —
correctly. **Only fires when rounded and unrounded products straddle a .5 boundary**: across 13
seeds exactly ONE tripped it, and the tail replay of the SAME clip printed 18 correctly because a
19 px difference in the detected hub moved f to 1.2296. A defect that surfaces on a coin flip is
worse than one that always fires ⇒ fixed the mechanism (`_shown()` round-trips through `_g`), not
the rounding. Circumference had the same shape (`2 × 3.14 × r` displayed, `math.pi` × full-precision
r computed). Test drives the real `build_seed` on a real `stats.json`, verified to FAIL on the old
code. **Suite 51.**

**FULL E2E SWEEP RE-RUN, all 7 clips on the fixed code — 7/7 GATE-CLEAN.** Trusted set =
`workspaces/job_{roundabout-4046-final, turntable-1-final, turntable-2-rect, turntable-3-rect,
computerfan-4029-rect, fan-4027-rect, fan-4028-rect}`. Exactly ONE clip rectifies — 4046 (hub offset 84.6 px, agent-detected axle
`[532.13, 996.92]`; three independent axle detections across the day — 07-20's `[532.3, 997.9]`,
an e2e's `[513.6, 1006.9]`, and this one — all reproduce tilt 27.1°, r_fit_m 0.2601, mean ω 7.800,
residual 3.42%, so the method is insensitive to ~20 px of hub jitter). computerfan-4029 + turntable-1 skip on `no_hub_px`; **fan-4027/4028 + turntable-2/3
ACTIVELY DECLINE on `hub_offset_below_20px`** — the agent supplied a hub and the pipeline refused,
which is the threshold's first exercise outside a unit test. Non-rectified clips: 0 numeric
diffs >1% vs archive.

**⚠ THE GUARD IS LOAD-BEARING, NOT DEFENSIVE.** `turntable-2`'s agent **independently reproduced the
coordinate error today** (trajectory 87 px = its own `y_off` below the centre; CV 0.188 as declared
vs 0.015 corrected). The guard caught it mid-e2e and recovered numbers matching the known-good
archive exactly. **So the 232 px bug is a RECURRING stochastic failure at the contract seam — two
clips, two sessions — not a 4046 one-off** (an earlier claim in this session that it was a one-off
is RETRACTED). Without the guard that run ships a 19% radius spread with the flags blaming the
physics, which is precisely how 4046 passed a 7-clip sweep, a gate, and reached the deck.

**Old runs archived** to `agent-backend/workspaces-archive/pre-coordfix-20260721-145038/` (all 12).

### WHAT TO TRY NEXT — the limit is now the MARKER, not the projection model

Damar asked whether to model the 3D path / camera angle, since fitting a circle-or-ellipse to a
scene that "isn't a flat surface" feels wrong. **Measured on 4046 after rectification, it is not
the geometry that limits us:**
- radial residual **16.67 px (3.42%)**, of which only **1.3% is phase-locked** — a wrong surface
  model would show up exactly there as a stubborn 1/rev or 2/rev term. Harmonics are 0.45 / 0.45 /
  2.57 px. **No hidden geometry left to model.**
- but the tracked handle images as a **108 × 119 px blob whose apparent size is 75–82%
  phase-locked** (width ±19 px, area CV 0.227) — we see different faces of a 3D knob as it turns.
- so the 16.7 px scatter is **~15% of the marker's own size**: "where is the handle?" is genuinely
  ill-defined for an extended body, and **a 3D path model, curved-surface fit or better conic would
  not move it.** The fix is at CAPTURE — a small, flat, high-contrast marker, the same lesson the
  red marker taught on both fans and the green tape specced for parkwheel.
- loose thread: largest surviving harmonic is **3/rev at 2.57 px on a 3-SPOKE wheel** — smells like
  the tracker being tugged as a spoke passes behind the knob. Tiny; do not chase unless 4046
  misbehaves again.

**3D IS recoverable if we ever want it** (tested, not implemented): the orbit's vanishing line meets
the imaged circle at that plane's circular points, which must also lie on the image of the absolute
conic ⇒ with square pixels + centred principal point, one unknown. On 4046 that gives **f ≈ 1116 px,
FOV 51.6°, plane normal [-0.016,-0.460,0.888], plane-vs-image angle 27.4°** — independently
confirming the planar route's **27.1°**. It buys **nothing for ω** (planar rectification already
recovers in-plane angle up to a similarity, and ω is similarity-invariant). It would pay for
**SCALE** (a reference at a different depth/orientation than the orbit → the fan's 2× coin flip,
the bicycle's 12% conflict) and for **FIGURES** (draw the tilted orbit in 3D, render a synthetic
face-on view — a multimodal-annotation artifact). Ill-conditioned on near-circular ellipses, so only
4046 and parkwheel qualify; two-fold mirror ambiguity; f 1116 vs an expected 1300–1700 means it is
approximate, not calibration-grade.

**CHEAP TEST FOR THE BICYCLE (OPEN 2).** Its unexplained 0.72 phase-lock: check whether it lives in
the RADIAL RESIDUAL (⇒ a geometry problem, worth the 3D tooling) or tracks the MARKER'S APPARENT
SIZE (⇒ the same extended-object limit, and no modelling will fix it). Same few lines as above.

## 00a. 2026-07-20 (annotation reworked to the P-MAGIC convention; all 7 golden clips re-run e2e; tech report COMMITTED)

Prof steered off pedagogy back to **data quality** (P-MAGIC's ω curve is a clean line, ours is
jagged). Full evidence + every number: **`agent-backend/docs/tracking-data-quality-2026-07-15.md`**.
Paper-style writeup: **`technical-report/centri-video-data-quality.tex`** (**29 pp**, compiles
clean twice; per-phenomenon common structure + formula-on-frame figures — **COMMITTED `e0a20d0`**,
figures force-added past the repo-wide `*.png` rule because their one-off generators are gone).
Per-clip guidance: **`agent-backend/templates/*/hints.md`**
(all 10). Archived clip + re-shoot spec: **`agent-backend/templates-reshoot/README.md`**.
Memory: [[centri-tracking-data-quality]] (+ correction to [[centri-detection-prompt-wording]]).

**TRUSTED SET = 4 phenomena / 7 clips.** Two tiers:
- **GOLD** = the per-frame *trajectory* is measured; every quantity is a direct observation.
- **SILVER** = the *rate* and *scale* are measured, so ω/T/f/v/a_c are trustworthy and teachable,
  but the per-frame *trajectory* is **reconstructed from the rate** (no resolvable point) — present
  the orbit as a model, never as measured data. ("Gold numbers, reconstructed picture.")

| # | phenomenon | tier | how |
|---|---|---|---|
| 1 | roundabout-4046 | GOLD | **rectified** — the only clip with real perspective |
| 2 | turntable (t-1/2/3, = flick) | GOLD | as-is (per-frame marker) |
| 3 | computerfan-4029 | GOLD | as-is (per-frame red marker) — our own gate had falsely condemned it |
| 4 | ceiling fan (4027+4028) | **SILVER** | scale MEASURED (ruler 07-16) → px_per_m 559; v/a_c at blade tip; ω(t) sub-bin-smoothed. Rate+scale gold, orbit synthesized |
**Only #1 needed the DATA corrected**; the rest were won by fixing our diagnostics/config.

**THE RULE: perspective strength = HUB OFFSET (imaged axle ↔ centre of the elliptical path), NOT
tilt.** 4046 = 85.6px; every other clip 0.7–8.8px. Rectifying the others does nothing — correctly.
An earlier "perspective is systematic" claim is **RETRACTED** (classifier read the A1/A2 ratio
without checking phase-lock).

**DONE 07-16 (pointer only — full detail in [[centri-tracking-data-quality]] + `git show 6605c11
58dd3c6`):** ruler gives hub→blade-tip **63.5 cm** = 355 px ⇒ **px_per_m 559**, so the fans' v/a_c
are reported AT THE BLADE TIP (4027 a_c≈11.3 m/s²; 4028 ≈85.2) and the clips are **SILVER**; the
ω(t) **staircase was FFT-bin quantization**, killed by sub-bin parabolic peak interp in
`freq_track._peak_hz_parabolic` (only `frequency` mode ever showed it).

**DONE 07-18 → COMMITTED 07-20 `e0a20d0` — technical report** (29 pp): per-phenomenon common
structure (Scene → context handed to the agent → how it is calculated, formulas each on their own
line → annotated data-point frame → Found → GOLD/SILVER/OPEN/REJECTED verdict), §2.3 formulas
(Eqs 1–7), and a formula-on-frame figure for every phenomenon. The tex + the 15 figures it uses are
tracked (force-added past the `*.png` rule — the one-off generator scripts are gone, so the PNGs are
the only copy); `fig-track-4048` / `fig-track-bicycle` are unused and stay untracked; the built PDF
is ignored like `paper/*.pdf`.

**DONE 07-20 — annotation reworked to the P-MAGIC convention + first full 7-clip sweep:**
- **`1040ad2`** — both annotation artifacts follow the diagram students are taught with (the
  P-MAGIC app's angular-motion intro): **v and ω are SEPARATE marks** (straight tangent arrow vs
  small curved arc — the old single curved arrow labelled ω conflated a linear and an angular
  quantity), symbols sit BESIDE their arrow never on it, names+values move to **margin callouts**
  with leader lines that never cross, app wording ("linear speed"), and **real math symbols** on
  the video via matplotlib mathtext (cv2's Hershey fonts are ASCII-only, so `a_c` used to draw as
  three literal characters). Two bugs fell out: arrow lengths were pinned to a literal 60 px while
  every other overlay dimension scaled with the frame; ω's mark could land outside the image.
- **`2474a8c`** — optional `job_name` on `POST /analyze` ⇒ `workspaces/job_turntable-1` instead of
  `job_2f8e…`, which is what makes a batch of template runs reviewable at all.
- **`78d1b64`** — ω arc/symbol fall back to a small arc about the centre when the preferred
  1.16r/1.40r spot leaves the frame (found on 4046, whose handle rides the rim).
- **`dc6ef2f`** — the `annotated_image` manifest entry said how the figure is DRAWN; the material
  writer copied it and tripped its own `annotate` vocabulary gate. Now says WHAT is marked; the
  layout detail still reaches the Axis-4 judge via each entry's `target`.
- **7-clip sweep** (`workspaces/job_{roundabout-4046,turntable-1/2/3,computerfan-4029,fan-4027,
  fan-4028}`) — full 3-tier material + PDFs for every trusted clip. **5/7 gate-clean**; the two
  failures are fixed below.

**DONE 07-20 (later) — the two sweep failures were OUR spec contradicting OUR gate:**
- **fan-4027 advanced arithmetic** (`0.057 × 0.635 → 0.0362`, stated `0.04`): the measurements
  table formatted with a fixed 2 decimals, so a_t = 0.0365 printed as **"0.04" — one significant
  figure**, disagreeing with the seed's own worked example (0.0575 × 0.635 = 0.0365) and closing
  no identity. `render/report.py:num()` now falls back to 3 **significant** figures when the
  fixed-decimal rendering would leave fewer than two. Table now reads α 0.0575 / a_t 0.0365.
- **4046 `filmed` / `annotated frame`**: the spec ASKED for words its own gate bans —
  `material_tiers._quality_policy` dictated "the orbit was filmed at an oblique angle" and the tier
  specs described the picture as "an annotated frame", while `material_gate.TRACKING_VOCAB` bans
  `film(ed)`, `annotate`, `frame`. Reworded to "seen at a slant rather than face-on" / "a marked-up
  still" (also in `quality_signals` guidance, which is pasted into the prompt verbatim).
- **the shared story poisons every tier at once**: `_generate_frame` was ungraded, but all three
  tiers MUST open by retelling it — so its "feeling the quiet fade of its **energy**" failed basic
  AND advanced on the same run. FRAME_SYSTEM now carries rule 5b (the dynamics blocklist, rendered
  from `G.DYNAMICS_VOCAB_HUMAN` so prompt and check cannot drift) and `_generate_frame` screens the
  story, retries once naming the offending words, then falls back to the deterministic template.
- **a squared UNIT read as division** — `"3.85 rad²/s²"` parsed as "3.85 squared ÷ 2" (= 7.41),
  so a CORRECT a_c substitution written as an arrow chain (`ω = 1.962 → squared → 3.85 rad²/s² →
  (× r = 0.317) → a_c = 1.22`) was flagged. `material_gate._neutralize_units` now collapses a
  squared unit pair before the division patterns run. A wrong product in the same notation still
  fails.
- **the raw duration leaked into the story** — "Over the next **14.998317 seconds**" (and
  "77.415 seconds" on the fan). Both prompt sites (`_facts`, `_frame_user`) now pass
  `_sig(active_duration_s, 3)` ⇒ "15.0 s", well inside the gate's 2% grounding tolerance.
- **Regression tests** (`tools/tests/test_material_gate.py`, now **36/36**): what a tier is TOLD to
  write must survive the gate that grades it; the fallback story must be clean for every motion
  type; a squared unit is not division. Each was verified to FAIL on the old code, not vacuously
  pass.
- **VERIFIED LIVE** by replaying the deterministic tail (see §4) on the two trusted workspaces:
  - **`job_roundabout-4046-r4` — gate `all_passed: true`** (basic/int/adv + cross-tier + seed all
    clean), story reads "Over the 15.0 s clip". This is the run to show.
  - **`job_fan-4027-r3`** — advanced PASSES and its table now reads **α 0.0575 / a_t 0.0365**
    (was 0.06 / 0.04) at r 0.635 m, story "77.4 seconds". Basic + intermediate failed on the
    KNOWN stochastic leaks ('tracked'; "steady rhythm" on a speeding-up clip) after exhausting
    both regenerations — 35B sampling, not a spec contradiction.
  The per-tier leaks the gate caught and fixed by regeneration ('recording', 'annotate', a stray
  `=`) are the loop working as designed, not deterministic defects.

**RULE (Damar, 07-21): `templates/` is GOLD ONLY.** A clip earns a place there once its per-frame
trajectory is measured AND verified on real frames — not on promise. Anything else waits in
`templates-reshoot/` (inert: `app/workspace.py` resolves templates by name under `templates/`).
First case: **`base-template-parkwheel-4091`** — park exercise wheel, 27.4 rev, the corpus's only
coast-to-REST, and parked anyway because nothing tracks it (SAM3 empty on 6 cues; colour locks onto
the rig's own red base at "100% coverage, zero rotation"; frequency returns a flat ω contradicting
the visible slow-down) and its hub offset is 60–73 px = real perspective. Evidence + re-shoot spec:
`templates-reshoot/README.md`. Fix = one strip of bright-green tape on ONE knob + a tape measure on
the rim. **By this rule `templates/base-template-fan-doll` (detection returns nothing) and probably
`base-template-bicycle` (OPEN) should move too — ASK first, they are live templates.**
See [[centri-templates-gold-only]].

**OPEN (needs Damar, do NOT guess):**
-1. **⚠ SILVER IS UNDECLARED IN THE DATA — the fans tell students a manufactured path is evidence.**
   Found 07-21 auditing the trusted set by overlaying every run's track on real frames. The fans'
   marker sits on **empty ceiling** because their trajectory is SYNTHESIZED (measured radius CV
   **0.000115**; a real track is ~0.05) — correct for frequency mode, but **nothing shipped says so**.
   The sidecar knows (`tracking_mode: frequency`, `frequency_meta.json` exists) yet
   `pipeline_inputs.json` carries **no mode**, so `stats.json` and `material_seed` cannot tell a
   measured path from a generated one ⇒ `measurement_quality.reliable: true`, **`do_not_claim: []`**,
   guidance *"narrate the timeline normally"*. Result, in the shipped **basic** worksheet for
   fan-4028: *"The third picture shows the traced path, and you can see that **every single point
   falls perfectly on one circle**."* The points fall on a circle because the software drew one.
   This is exactly what the GOLD/SILVER rule forbids ("present the orbit as a model, never as
   measured data") — and that rule currently exists only in this file, with **no representation in
   the data**. It passed every gate because no check knows synthesized paths exist. **PRE-EXISTING,
   not from the 07-21 work, but live in all 7 "trusted" runs.** Fix needs a decision because it
   touches the frozen handover: carry a `path_is_measured` flag sidecar → `pipeline_inputs.json` →
   seed, so `do_not_claim` populates itself and a check can reject evidentiary claims about a
   generated orbit. **Damar 07-21: deferred, do later.**
   (Audit also confirmed CLEAN: internal arithmetic on all 7 — v=ωr, a_c=ω²r, r=px/ppm,
   ppm=diameter/size; marker lands ON the object for 4046, turntable-1/2/3, computerfan-4029.
   Period vs 2π/ω differs >5% only on turntable-2 and fan-4027, legitimate — both have ω varying
   3–4×, so a measured lap time ≠ 2π/mean ω.)
0. **NEW 07-20 — the fan's measured scale is a coin flip across runs.** `freq_track` sizes the
   synthesized bbox at `orbit_radius_px` (355 px) so the generic Step-5 sizing pairs it with
   `physical_size = 0.635 m` (the ruler-measured hub→blade-tip RADIUS) ⇒ px_per_m 559. But the
   contract field is *named* `diameter_px`, so the agent "corrects" it: this morning's run wrote
   710 px **and** doubled the metres to 1.27 (⇒ 559 ✓); the afternoon re-run wrote 710 px and left
   0.635 (⇒ **1118, every SI value halved** — r 0.317 m, a_c 1.83 not 3.66). Nothing catches it:
   both are internally consistent as far as the pipeline can see. Stop-gap shipped = a calibration
   section in `templates/base-template-fan-402{7,8}/hints.md` (hints DO reach Steps 1–5). **Real
   fix needs a decision:** rename/duplicate the contract field as `reference.radius_px` +
   `radius_m`, or have `geometry.calibrate` cross-check px_per_m against the fitted orbit radius
   whenever `ref_label == tracked_label` (true in frequency mode by construction) and flag a 2×.
   Until then a fan re-run can silently halve the SILVER-tier scale claim.
1. **Ruler on the phone body** (NOT the 5.5" screen diagonal) + confirm the wheel → settles
   bicycle's 12% scale cross-check (phone→tire gives 58.6cm vs a real 66–70cm wheel ⇒ one
   reference is wrong; suspect the spokes clip the phone's mask).
2. **bicycle stays OPEN** — phase-lock 0.72 that is NOT perspective (4.9px), NOT occlusion
   (area-vs-phase R²=0.07), gravity has right sign but wrong phase (138° off). Cause unknown.
3. ~~**Decide:** implement rectification in `geometry.py` gated on a new `hub_px` field.~~
   **DONE 07-21 (`dc9a36d`)** — Damar chose "give rectification a home"; see §00. Follow-ups:
   (a) **parkwheel-4091** is the second clip with real perspective (hub offset 60–73 px) and would
   now be rectified automatically once it has a working tracker — it stays in `templates-reshoot/`
   on the GOLD-only rule, unchanged; (b) the scale pinning (major semi-axis ⇒ `r_fit_m` +2.4%) is
   a deliberate choice, revisit if the conservative variant is preferred; (c) the prototype's
   per-frame hub (camera-drift removal) is NOT implemented — we use the static detected axle,
   which is why the radial residual lands at 3.42% rather than the prototype's 1.68%.
4. `color_track.py` bugs worth fixing regardless: `area × mean_saturation` is invalid for a DARK
   target; `max_step` must come from `ω·r/fps`, not a round number.

**HINT DELIVERY (07-15, still uncommitted):** `worker/tasks.py:_inject_clip_hints()` substitutes
each template's `hints.md` into `{{CLIP_HINTS}}` in `prompts/orchestrator.txt`. Hints must be
**injected, not read** — told to "read hints.md" the agent logged "hints.md found — AUTHORITATIVE"
and never opened it (0 tool calls).

**METHOD LESSON (cost 4 wrong claims):** overlay the cached track on REAL frames before trusting
ANY statistic. Killed: "4048 is at 29° tilt" (a conic fitted to trees), "squash the ellipse"
(right about the ellipse, wrong remedy), "perspective is systematic", "4029 is contaminated".
**Coverage ≠ correctness** (4048 reports 1.0 while ~38% wrong; 4031 reports 100% tracking a
motion-blur smear).

---

## 00b. 2026-07-14 — material-quality backlog (DONE; kept only as a pointer)

Critique of `e6fed2e9` vs P-MAGIC → `agent-backend/docs/material-pedagogy-critique-2026-07-14.md`
(Part A correctness, B design, C multimodal).

**The ENTIRE correctness/annotation backlog (A1–A8, C1–C5) + agreed Part-B items are DONE,
committed and live-validated** on branch `feat/video-annotation-phase-labeller`. Golden =
**`9ed918d0`** (int+adv gate CLEAN; basic
only the known stochastic vocab/`²` leak). Per-item detail, commit hashes and the new deterministic
gates (`wrong_duration_products`, `average_period_as_peak`, `_phase_significant`,
render-aware `annotation_issues` `2c24a0d`) live in **[[centri-tiered-material]]** +
**[[centri-annotation-reorder-progress]]** and `git log -p`.

**REMAINING (design/pedagogy only, not correctness):** A7 two-scenario contrast, per-phase
colour-coded table (C4 upgrade), predict-box, contextualize/noticing/anchor, Bahasa. See the
critique doc §Part B.

## 1. Current state & in-flight (as of 2026-07-20)
- **Branch `feat/video-annotation-phase-labeller`, PR #1 still OPEN**
  (https://github.com/damarsimple/centri/pull/1) — **32 commits ahead of `origin/main`** (which is
  still at `57818aa`), and **25 ahead of the pushed branch** `origin/feat/…` (`2bbb8db`), so the
  07-16..07-20 work is local-only. Local `main` has been fast-forwarded to `30ce433` but never
  pushed — don't read local `main` as "what's on GitHub".
- **Stack:** lab2 API/worker/redis UP (`docker compose -f docker-compose.yml -f compose.lab2.yml up
  -d api worker redis`, API `10.0.0.2:8088`); Qwen3.6-35B `192.168.1.205:8083` UP;
  **SAM3 `10.0.0.1:8086` is UP** (verified 07-15; tracked 5 clips + prompt sweeps). If it dies again:
  a `prompt_sweep.py --reset` POSTs `/reset` which EXITS the server and `run_sam3.sh` doesn't relaunch;
  source `/home/damar/sams2/sam3cpp/api_master_sam3.py`. **API key is `changeme-random-secret-key-12345`**
  (`.env` `API_KEY`, NOT `PI_INFERENCE_API_KEY`); `/analyze` needs `;type=video/mp4` on the -F upload.
- **Golden validation job:** flick **`9ed918d0`** (regen 2026-07-14, ALL fixes incl. A6 authentic story
  + misconception + CYU→teacher + A8.2 precision + (avg) chips; done 100%; int+adv gate CLEAN, basic
  only the stochastic vocab/`²` leak). Its figures/material are referenced ON the weekly deck for a live
  walk-through. Prior golden `fa790a23` = A1–A5 only; `5e41d8d9` = A1+C1+restyle; `e6fed2e9` = pre-fix.
  Template `templates/base-template-flick/` (sidecar now carries `scene_context` for A6) + `api_cache.json`
  → cache HIT, no re-track; worker volume-mounts `./workspace_lib` so host edits are live (no rebuild).
  Re-submit crib: POST /analyze with `input_video.mp4` (any flick workspace) + `-F template=base-template-flick`.
- **Weekly deck:** NEW `presentation/centri-weekly-2026-07-15.tex` COMMITTED (`aa8e33e`) — standalone,
  6 slides (material-quality + multimodal annotation, current-state). **CLAUDE.md now has a 5th deck
  rule — STANDALONE/self-explanatory** (committed `865b76c`; see [[centri-presentation-style]]).
- **Reviewable run set:** `workspaces/job_<name>` from the 07-20 sweep — `roundabout-4046`,
  `turntable-1/2/3`, `computerfan-4029`, `fan-4027`, `fan-4028` (readable names via the new
  `job_name`). Post-fix re-runs: **`job_roundabout-4046-r4`** (gate all-clean, the one to show)
  and `job_fan-4027-r3`. **`job_fan-4027-r2` is the 2× SCALE-ERROR run — do not use it** (OPEN 0);
  `job_roundabout-4046-r2` failed on the runaway guard (see §4).
- **UNCOMMITTED (working tree):** the 07-15 data-quality workstream (`worker/tasks.py`,
  `prompts/orchestrator.txt`, 10 × `templates/*/hints.md`, `templates-reshoot/`, `docs/figures/`,
  `docs/tracking-data-quality-2026-07-15.md`) + today's material fixes
  (`workspace_lib/analysis/{material_gate,material_seed,material_tiers,quality_signals,
  render/report}.py`, `tools/tests/test_material_gate.py`, fan `hints.md` calibration sections)
  + the prior-session eval-framework workstream + `docs/material-pedagogy-critique-2026-07-14.md`
  + `compose.lab2.yml` + `document-4.pdf` + this checkpoint. Only `technical-report/` (`e0a20d0`)
  has been committed from this whole stretch. Eval files:
  `docs/{eval-framework,eval-progress,eval-rubric-ika,related-work-positioning,effectiveness-study-blueprint}.md`,
  `tools/{run_llm_judge,build_rater_sheet,eval_stats,generate_tier_material}.py`.

## 2. Who & what / goal
- **Damar** (MSc, builds Centri) · **Vinsa** (labmate/team leader, P-MAGIC author side, owns
  evaluation, physics-teaching background, Bahasa) · **Prof. Wu-Yuin Hwang** (advisor).
- **Centri** = video CV tracking (not IMU) → kinematics → seeded 3-tier learning material +
  multimodal annotation; FastAPI+Celery+Redis (Docker), `pi` agent CLI, local Qwen3.6-35B.
  P-MAGIC (`document-4.pdf`) = sibling app (GPT-4o + phone sensors, 3-level multimodal problems,
  BERT/STS/LSTM + 10-teacher eval). Parent line = Ika Utami's dissertation (SocioMathLLM, Geo-QG).
- **Goal:** comparable evaluation / joint paper. Paper 1 = video-vs-sensor validity +
  material-quality eval; Paper 2 = learning study (`PAPER2_LEARNING_STUDY.md`).
- Thesis contribution = video-based generation + multimodal annotation; eval Axes 1–4 in
  `docs/eval-framework.md` (Axis 4 = annotation correctness / multimodal).

## 3. Parked / older open items (still live, low priority)
- **BLEU/ROUGE decision pending** — if run, expect LOW (lexical vs paraphrase) and frame as
  motivating BERTScore; `pip install sacrebleu rouge-score` into `.venv-eval`.
- **IMG_3750 fan (prof's recapture):** freq job `1c183872` verified good (two-phase, peak ω≈3.5);
  **physical scale PROVISIONAL 0.6 m** — rescale when blade-tip orbit measured; object job
  `8d95a817` is the BROKEN ROI run (do not use). Single-regime classifier mislabels two-phase
  `motion_type` — extending it is roadmap; faithful ω(t) lives in `frequency_meta.json`.
- **Questions module (Subagent C) is GATED OFF** by default (`report.py RENDER_QUESTIONS`,
  env `PI_RENDER_QUESTIONS`); re-enable for a P-MAGIC question comparison.
- Deck consolidation (fold `centri-cases-eval.tex` into main deck?) undecided; deck rules =
  repo `CLAUDE.md` + [[centri-presentation-style]].
- `/suggest-scene` + AnnotateScreen should emit simple-noun cues (prompt-wording lesson).
- Multilingual eval parked (English-only official; 23-PDF multilingual + 18-PDF English reference
  sets live under `material_work/_reference/` with READMEs).

## 4. Ops quick-reference
- **Submit job:** `POST 10.0.0.2:8088/analyze` `-F "video=@f;type=video/mp4" -F "sidecar=$(cat
  sc.json)"`, header `X-API-Key: $(grep ^API_KEY= agent-backend/.env|cut -d= -f2)` (octet-stream
  rejected). **Re-enqueue:** `docker compose exec -T -w /app worker python -c "from worker.tasks
  import run_pi_analysis; run_pi_analysis.delay('<job_id>')"` (idempotent — runs only missing artifacts).
- **Workspaces carry a STALE `analysis/` copy** (seeded at job creation, root-owned): `cp` fixed
  `workspace_lib/analysis/*` into `workspaces/job_*/analysis/` (inside the worker container) before
  re-running a stage; `rm -rf analysis/render/__pycache__` first (stale .pyc served old code once).
  New jobs via `POST /analyze` reseed from CURRENT workspace_lib.
- **Deterministic PDF recovery** (after runaway-guard fails at report): `docker compose exec worker …
  python -m analysis.render.report` in the workspace, then `pdflatex ×2` (teacher key needs
  **lualatex** for ✓). Qwen is reachable from the WORKER container, not the host sandbox.
- **TAIL REPLAY — test a material/figure change WITHOUT the agent (~5 min, no SAM3, no runaway
  risk).** Clone a workspace that already has a good `pipeline_inputs.json`, drop in current code,
  and run the deterministic steps. **The worker mounts workspaces at the HOST path**
  (`/home/damar/centri/agent-backend/workspaces`), NOT `/app/workspaces`:
  ```
  W=/home/damar/centri/agent-backend/workspaces
  docker compose exec -T worker bash -c "cp -a $W/job_X $W/job_X-r2 && rm -rf $W/job_X-r2/analysis \
    && cp -a /app/workspace_lib/analysis $W/job_X-r2/analysis \
    && find $W/job_X-r2/analysis -name __pycache__ -exec rm -rf {} +"
  docker compose exec -T -w $W/job_X-r2 worker bash -c 'python -m analysis.run && \
    python -m analysis.render.figures && python -m analysis.material_tiers && python -m analysis.render.report'
  ```
  Steps 1–5 (perception) are untouched, so the trajectory and calibration are identical — which is
  the point: it isolates the change AND removes agent nondeterminism from the comparison.
- **A full e2e re-run of 4046 is not free:** `roundabout-4046-r2` died on the **1024 MB
  runaway guard** in the track phase — the injected hints tell the agent about the hub offset and
  it starts prototyping rectification. Prefer the tail replay for material work; keep e2e for
  perception changes.
- **Worker kills:** `celery revoke --terminate` stalls the prefork pool → `docker compose restart
  worker`; a DELETEd job's pi process keeps running (kill the `pi` PID in-container);
  `pkill -9 -f "[m]aterial_tiers"` (bracket trick — plain pattern self-kills); long in-container
  runs: launch `docker exec -d` (foreground “timeout” leaves orphans racing on files).
- **`cleanup_expired_workspaces` (hourly) + job deletion REMOVE workspaces** — export promptly.
- Calibration `px_per_m = reference.diameter_px / physical_size_m` — **the two must describe the
  SAME span**; in `frequency` mode both are RADII despite the field name (OPEN 0). zsh: `status`
  is read-only.
- Detection cues = simple nouns (`docs/object-detection-prompts.md`); `tools/prompt_sweep.py` ranks
  cues on a short clip (`--reset` kills SAM3 — leave OFF).

## 5. File map (pointers)
- **Data quality (07-15):** evidence + every number `agent-backend/docs/tracking-data-quality-2026-07-15.md`;
  report `technical-report/centri-video-data-quality.tex` (+`.pdf`, `figures/`); working rectification
  prototype `agent-backend/docs/figures/rectify_prototype.py`; per-clip guidance
  `agent-backend/templates/*/hints.md` (10); archived clip + re-shoot spec
  `agent-backend/templates-reshoot/README.md`; hint injection `worker/tasks.py:_inject_clip_hints()`
  + `{{CLIP_HINTS}}` in `prompts/orchestrator.txt`.
- **Material pipeline:** `workspace_lib/analysis/{material_seed,material_tiers,material_gate,
  quality_signals}.py`, `render/{report,figures,annotate}.py`, hints `analysis/material_hints.md`,
  spec `docs/difficulty-tiered-material-spec.md`, orchestrator `prompts/orchestrator.txt`.
- **Eval:** `tools/{run_material_eval,run_multimodal_eval,run_multi_reference_eval,
  run_reference_comparison_eval,grade_material_grounding,grade_material_difficulty,run_llm_judge,
  build_rater_sheet,eval_stats}.py` (`.venv-eval`); references + reports under `material_work/`;
  framework docs `agent-backend/docs/eval-*.md`; **critique
  `docs/material-pedagogy-critique-2026-07-14.md`**.
- **Decks:** `presentation/centri-end-to-end.tex` (advisor), `centri-cases-eval.tex` (focused),
  weeklies `centri-weekly-*.tex` (latest `2026-07-15` = material-quality+annotation, standalone) —
  **5 treatment rules** in repo `CLAUDE.md` (rule #5 = standalone/self-explanatory).
- **Research docs:** `PAPER_GAP_ASSESSMENT.md`, `PAPER2_LEARNING_STUDY.md`, `document-3.pdf`
  (P-MAGIC preprint), `document-4.pdf` (P-MAGIC journal), notes `note-*`.
- **Export:** `agent-backend/vinsa_export/` (validation-centric, `tools/build_vinsa_package.py`).
- **Trackers:** SAM3-CPP prod `/home/damar/sams2/sam3cpp/` (`api_master_sam3.py`, `run_sam3.sh`);
  LA experiment `test/locateanything_worker.py` (:8087, DOWN; slow — not adopted).
- **Memory files** (cross-session context): `centri-{tiered-material,annotation-reorder-progress,
  e2e-run-plan,eval-plan,eval-multimodal-pivot,thesis-contribution-titles,pmagic-alignment,
  utami-dissertation,second-pc-lab2,sam3-chunk-fix,detection-prompt-wording,
  kinematics-center-and-spinup,video-literature-review,presentation-style,deck-axis-terminology,
  tracking-data-quality,checkpoint-hygiene,team-pedagogy-gap}.md`.
