# What We Changed — Determinism Overhaul (start to finish)

> The full story of the 2026-06-05 work: the symptom, what we found, what we built,
> the bug the spot-check caught, and the result. Read this to understand *what
> changed and why*. Reference docs: [agents-behaviour.md](agents-behaviour.md),
> [pipeline-internals.md](pipeline-internals.md),
> [validation-report.md](validation-report.md) (the live numbers),
> [`analysis/README.md`](../workspace_lib/analysis/README.md) (the frozen pipeline).

---

## 0. TL;DR

The agent (`pi` + Qwen) was **re-writing the physics math on every run**, so the same
turntable video produced a different `stats.json` each time — different schema,
different numbers, sometimes invalid JSON. We moved the math out of the LLM's hands
into a **frozen, seeded pipeline**, leaving the LLM only the perception it's good at.

**Result:** the same video now produces **byte-identical** output, matching the phone
gyroscope to **0.2%**. IMG_3071 went from **26% run-to-run period spread → 0%**.

---

## 1. The symptom (what you reported)

"The agents' output `stats.json` should be similar across runs of the same turntable
video, but there are issues." Correct — and worse than it looked.

Across 30 historical jobs:
- **28 distinct `stats.json` schemas** (keys and nesting changed every run)
- **17 contained bare `NaN`** — invalid JSON that strict parsers reject
- On IMG_3071, `period_s` swung **0.793–1.002 s (26%)** on the *same* video
- `center_drift_px` swung **8.9 → 1013 px**, `stable_mean_omega` **2.9 → 6.1 rad/s**

## 2. What we found (root cause)

The orchestrator prompt told the agent to *compute* the kinematics and *write*
`stats.json`, but left the final write as a stub (`# Final stats.json writing … # ...`)
and parts of the math as prose pseudo-code. So the LLM **re-derived the analysis code
every run** — and being an LLM, it derived it differently each time.

Crucially, the *perception* (SAM tracking) was already fine — `mean_omega`/`period`
were accurate where stable. The instability lived entirely in the **agent-authored
math + serialization**. Two specific defects:
- **Unseeded RANSAC** → circle fit varied run-to-run (the 8.9→1013 drift).
- **Two different ω computations** (one for active detection, one for everything else)
  → `stable_mean_omega` instability.

## 3. The decision

Keep the LLM where it adds judgment (scene understanding, tracking, sizing, the
creative subagents); **demote the arithmetic to a fixed library the agent calls** —
seeded into each job exactly like `sidecar.json`. Your framing: *"preseed the
workspace with quality code, just like sidecar behaviour."*

## 4. What we built / changed

| Area | Change |
|---|---|
| **NEW** `workspace_lib/analysis/` | Frozen, deterministic kinematics pipeline (old steps 5–8): `contract.py`, `geometry.py`, `kinematics.py`, `writer.py`, `run.py`, `common.py`, `README.md` |
| **NEW** `tools/gt_harness.py` | Regression harness: determinism check + accuracy vs phone-gyro ground truth |
| **NEW** `tools/monitor_runs.py`, `wait_job.py` | Batch job pollers for live validation |
| `app/workspace.py` | `seed_pipeline()` — copies `analysis/` into every job workspace |
| `app/routes.py` | Calls `seed_pipeline` in `/analyze` beside `drop_video`/`drop_sidecar` |
| `prompts/orchestrator.txt` | **1283 → ~1000 lines**: steps 5–8 pseudo-code replaced by "write `pipeline_inputs.json` → run `python -m analysis.run`"; hard rule forbidding reimplementation |
| `docker-compose.yml` | Mounted `./workspace_lib` into api + worker |
| `templates/basetemplate-turntable-{1,2,3}/sidecar.json` | Reference base diameter **0.3 → 0.4 m** (you confirmed actual size) |
| **Docs** | New `agents-behaviour.md`, `validation-report.md`, this file; updated `pipeline-internals.md`, `data-contract.md`, `architecture-overview.md`, `docs/README.md` |

### The new flow (the seam)

```
 AGENTIC (Qwen) — judgment                 FROZEN (analysis/) — arithmetic
 Step 1 scene parse                        Step 6: python -m analysis.run
 Step 2 SAM tracking      ─┐                 RANSAC clean (seeded RNG)
 Step 3 validation         │ pipeline_         calibration (px_per_m)
 Step 4 center bootstrap   ├─inputs ──────►    kinematics (single ω source)
 Step 5 reference sizing  ─┘ .json             period, phases
                                               locked stats.json (allow_nan=False)
```

### Determinism guarantees baked in
1. **Seeded RANSAC RNG** — identical circle fit every run.
2. **Single ω source** — one ω drives active detection, summary, period, and phases.
3. **Locked schema + `allow_nan=False`** — same keys every run; a stray NaN raises
   instead of shipping invalid JSON.

## 5. The bug the spot-check caught (and the fix)

We re-ran `/analyze` live. The new flow's *plumbing* worked perfectly — valid contract,
locked schema, zero NaN, and the sanity gate fired 7 flags. **But the first job's
numbers were garbage** (`center_drift=8045`, `r_fit=3.13 m`, `mean_omega=0`).

Root cause: seeding RANSAC made it deterministic, but on the fast video it
deterministically locked onto a **degenerate giant circle** (a huge radius is locally
almost straight, so it "fits" arc points), which then poisoned the outlier step and
deleted half the trajectory. *Determinism made it reproducible, not correct.*

**Fix** (`analysis/geometry.py`): when a trusted center exists, derive the orbit radius
and outlier rejection from the **median distance to that center** — never from the
RANSAC radius — and reject any implausible fit (`ransac_fit_rejected` flag). Verified on
the real agent inputs: `mean_omega` 0.0 → **7.372** (gyro 7.357), and byte-identical
across runs. The buggy in-flight batch was cancelled and re-run on the patched pipeline.

> Lesson worth keeping: a deterministic-but-wrong pipeline is still wrong. The spot-check
> is what separated "runs every time" from "right every time."

## 6. Result (before vs after)

| | BEFORE (agent-authored) | AFTER (frozen + patched) |
|---|---|---|
| `stats.json` schemas / 30 runs | 28 distinct | **1 locked** (`schema_version: 1`) |
| Invalid `NaN` JSON | 17 / 30 | **0** |
| IMG_3071 period spread (same video) | 0.793–1.002 s (**26%**) | **0% — byte-identical** |
| IMG_3071 accuracy vs gyro | 6.16–8.25 (brackets 7.36) | **7.372 rad/s (0.2%)** |
| `center_drift_px` range | 8.9 → 1013 | 0.0 (trusted center) |

Live batch, 3× per video, complete (full detail in [validation-report.md](validation-report.md)):

| Video | period spread | mean_ω spread | vs gyro mean_ω | determinism |
|---|---|---|---|---|
| IMG_3071 | **0.0%** | **0.0%** | 7.372 vs 7.357 → **0.2%** | byte-identical ×3 |
| IMG_3072 | **0.0%** | **0.0%** | 4.827 vs 4.806 → **0.4%** | byte-identical ×3 |
| IMG_3075 | 4.3% | 1.7% | 5.794 vs 5.811 → **0.3%** | r1≡r3 identical; r2's *tracking* differed |

Two of three videos are byte-identical across all runs; the one wobble (IMG_3075 run2)
is **perception variance** (its SAM tracking differed), not the math — the exact
separation this redesign was built to create. `mean_omega` is within 0.2–0.4% of the
gyro on every video.

## 7. How to run it / validate going forward

- **Submit a job:** `POST /analyze` (unchanged API) — seeding is automatic.
- **Validate determinism + gyro accuracy:** `python tools/gt_harness.py`
- **After any prompt or pipeline change:** re-run `/analyze` live (the harness can't
  exercise the Qwen perception half) and check `validation-report.md`.
- **Change the output schema:** edit `analysis/writer.py::build_stats`, bump
  `schema_version`, update `data-contract.md`.

## 8. Follow-on improvements (same session)

Beyond the kinematics overhaul, two adjacent areas were tidied:

**Flutter setup UI (`app/`):**
- Removed the `bbox_center_px` sidecar field — it was **dead** (backend read it into
  `ref_cx`/`ref_cy`, never used), **redundant** (the app filled it from the
  rotation-centre tap, same as `rotation_center_frac`), and **mislabeled**. Dropped from
  `models/sidecar.dart`, `annotate_screen.dart`, and the orchestrator's dead read.
- **De-jargoned** for students/teachers: "SAM3" wording replaced ("Check the app can see
  them", "The app can see both objects ✓", etc.).

**Subagent definitions (kept as LLM agents — not frozen):**
- All three defs now carry a HARD RULE against copying the prompt's example numbers
  (read only this job's `stats.json`/`kinematics.csv`).
- **Annotation = symbol-only**: labels `r`/`v`/`ac`/`w` + a definitions legend, never
  numeric values, so students measure rather than read answers. A vetted reference is
  seeded at `workspace_lib/analysis/render/annotate.py` for the subagent to run/adapt.
- Stale file refs fixed (`phases.json` → `stats["phases"]`, `cropped.mp4`).

## 9. What is NOT solved (honest scope)

- **Perception is still Qwen** and can vary run-to-run. The frozen pipeline guarantees
  identical output *for identical tracking*; if a video ever shows residual spread,
  it points at tracking, not the math — which is the separation we built.
- The gyro CSVs are **developer ground truth only** — never seeded, never seen by the
  agent. The product is tracking-only.
- **Reference physical size matters for linear values.** The bicycle sidecar has no size
  → defaults to 0.3 m (a real tyre is ~0.67 m), so its `v`/`aᶜ` are scaled off; ω/period
  are scale-free and correct. Add a size to sidecars where `v`/`aᶜ` matter.

---

## 10. Follow-up: the coordinate-space determinism bug (2026-06-07)

Re-running the validation batch (2× per turntable, flutter flow) after the schema/RANSAC
work, **IMG_3071 and IMG_3075 came out byte-identical — but IMG_3072 diverged hard**:
`mean_ω` agreed (0.7%) yet `period_s` spread **14.6%** and `stable_mean_omega` spread
**81%** across two runs of the same video.

**Root cause — *not* SAM variance.** The raw tracker output was byte-identical between the
two runs (same 253 detections, same display-space coordinates). The divergence was a
**constant 87 px offset** on every trajectory frame — exactly the crop `y_off`. The agent's
Step 5 built `pipeline_inputs.json` by crop-subtracting the trajectory **by hand**, and the
LLM did it **inconsistently**: run1 left the trajectory in full-frame space, run2 subtracted
the offset — while the center was always cropped. Trajectory-in-display vs center-in-cropped
= 87 px mismatch → wrong radius → wrong phase segmentation → garbage `stable_mean_omega`.
(`mean_ω` survived because an angular mean is roughly offset-invariant.) IMG_3071/3075 only
looked clean because the model *happened* to pick the same path in both their runs — luck.

**The fix — move the last transform off the LLM.** The contract now carries the trajectory
**and** center in raw full-frame (`"display"`) space plus `coordinate_space` + `roi_crop`;
the frozen `analysis/contract.py` performs the single display→cropped subtraction for both
together, so they can never drift into different spaces.

| Area | Change |
|---|---|
| `workspace_lib/analysis/contract.py` | `coordinate_space` + `roi_crop` now required; subtracts `roi_crop.{x_off,y_off}` from trajectory + center together when space is `"display"` |
| `prompts/orchestrator.txt` (Step 5) | emits raw `trajectories_full` + center in display space + `coordinate_space:"display"`; removed the hand crop-subtraction; added a HARD RULE |
| **Docs** | this section; `data-contract.md` §3.1a, `analysis/README.md` contract table + determinism guarantees, `agents-behaviour.md` |

**Offline proof on the real IMG_3072 inputs:** both runs converge to identical physics
(`mean_ω=4.8268`, `period=1.4376`, `stable_ω=1.2983`) — run1's old wrong values
(4.862 / 1.665 / 3.066) snap to match run2. The only residual byte-diff was
`video_info.duration_s` (4.22 vs 4.222), a report-only metadata field used in no
computation. A live re-run batch (v2) confirms the fix end-to-end.

> Lesson, again: determinism bugs hide in the *last* place a human still does arithmetic.
> The frozen-math seam only holds if **every** position-space conversion lives inside it.

---

## 11. Figure coordinate fix, gap-fill & a latent crash (2026-06-07)

A real phone-submitted job surfaced three issues in the *rendering/robustness* layer
(the math was correct throughout):

**(a) The fitted circle floated ~`y_off` px off the trajectory points.** The figure
subagent plotted points from `api_cache.json` (raw **full-frame**) but drew the
centre/circle from `stats.json` (**cropped**) — a `roi_crop.y_off` mismatch. Fix: the
frozen pipeline now writes cropped `x_px,y_px` into `kinematics.csv` (the exact series
the kinematics used), and the figures subagent plots geometry from those, never from
`api_cache.json`. Verified: centre-to-orbit gap 178 px → 15 px (the residual is the
user's centre-tap offset).

**(b) `np.gradient` crash on isolated frames.** A lone valid frame between tracking
gaps is a 1-point segment; numpy 2.4.6's `np.gradient` raises on `<2` points. Guarded
→ such frames get `NaN` ω (undefined), not a crash.

**(c) Missing ω(t) line during fast spins = blur dropouts.** SAM3 loses the phone on
motion-blurred frames, leaving `NaN` gaps. Added **bounded polar gap-fill**
(`kinematics._fill_short_gaps`): interpolate interior gaps `≤ MAX_GAP_S` (0.2 s) in
`(θ, r)` about the centre — so filled points land *on* the orbit, not on a chord —
between two real detections only (never extrapolate the ends), flagged
`interpolated_short_gaps`, counted in `tracking.n_interpolated_frames`. Real-detection
`coverage_pct` is unchanged (computed before the fill). Plus an app capture tip
(briefing): brighter light / don't spin too fast.

| Area | Change |
|---|---|
| `workspace_lib/analysis/writer.py` | `kinematics.csv` gains `x_px,y_px` (cropped, cleaned+filled); `stats.tracking.n_interpolated_frames` |
| `workspace_lib/analysis/kinematics.py` | `_fill_short_gaps` (polar, bounded); `np.gradient` <2-pt guard; `Kinematics.x_px/y_px/n_interpolated` |
| `.pi/agent/agents/figures-gen-subagent.md` | HARD RULE: plot geometry from `kinematics.csv` `x_px,y_px`, never `api_cache.json`; trajectory snippet rewritten |
| `app/lib/screens/briefing_screen.dart` | capture tips: bright light, moderate spin |

**Determinism preserved:** gap-fill is a pure function of the input (no RNG). Clean
videos with no interior gaps are byte-identical (IMG_3071 7.3722/0.8387, IMG_3075
5.7941/1.102 unchanged). IMG_3072 (5 filled frames) moved period 1.44 → **1.37 s**,
*closer* to the gyro (1.307). Phone job: ω `NaN` 35 → 15, period now resolves.

### Figure verification flow (a + c)

A prompt HARD RULE did not stop the figures subagent re-plotting the trajectory from
`api_cache.json` (full-frame) — the circle floated off the points *again* on a live
phone job. So correctness is now **enforced**, not requested:

- **(c) Deterministic gate — always, instant** (`analysis/verify_figures.py`): the
  subagent must write `plots/figure_qa.json` with the min/max of the exact x/y arrays it
  scattered; the gate recomputes the truth from `kinematics.csv` and fails if they differ
  (a full-frame plot is off by `roi_crop.y_off`). Tested: PASS on cropped, FAIL on +161 px.
- **(a) Visual QA subagent — retry-only** (`.pi/agent/agents/figure-qa-subagent.md`): a
  multimodal reviewer that looks at the PNGs ("is the circle on the points? labels OK?").
  It runs **only when the deterministic gate fails**, as part of the fix — so the happy
  path stays fast (the VLM pass ~doubled back-half time).
- **Retry loop** (orchestrator, ≤2): on a gate failure, spawn visual QA → re-spawn
  figures-gen with the combined feedback → re-check. Still failing → flag
  `figures_unverified`, never silently ship.

**Verified end-to-end** on the phone job (3rd re-push): deterministic gate passed, and
the trajectory circle sits exactly on the ring with the centre mid-orbit.

---

## 12. Seeded rendering layer — figures, LaTeX report & video (2026-06-12)

The determinism work froze the *math*; the *rendering* (figures, the LaTeX report, the
annotated video) stayed agent-authored. A real job (`job_bee2a06c`) exposed what that
costs: the agent hand-wrote `student_edition.tex` with `\includegraphics{plots/...}`,
but `compile_latex.sh` `cd`s into the report dir so the path resolved to
`report/plots/...` (nonexistent) — pdflatex emits a blank box, not an error, so the job
**"succeeded" with zero images in the PDF**. It also hand-substituted unguarded stats
(`\SI{N/A}{rad/s}`). Same class of fragility the kinematics freeze removed, one layer up.

**Decision (your framing):** *"preseed the code, let the agent be the verifier — but
relaxed vs the kinematics: it has to make it look good and make sense."* So the renderers
are now seeded, deterministic modules the agent **runs and verifies**, not authors.

### What we built

| Area | Change |
|---|---|
| **NEW** `workspace_lib/analysis/render/figures.py` | Deterministic generator of all 9 plots + `summary_panel.png` + `figure_qa.json`, from `stats.json`/`kinematics.csv`, in cropped space (passes `verify_figures` by construction). `python -m analysis.render.figures` |
| **NEW** `workspace_lib/analysis/render/report.py` | Deterministic `student_edition.tex` + `teacher_key.tex` from `stats.json` + `questions.json`. Sets `\graphicspath{{../plots/}…}` (images resolve regardless of compile CWD — kills the missing-image bug), null-guards every value, LaTeX-escapes all text (maps unicode π/ω/²), teacher key gets answers+hints. `python -m analysis.render.report` |
| `workspace_lib/analysis/render/annotate.py` | Overlay sizes now **scale to the frame** (`_S = max(w,h)/720`) so labels aren't hairlines; the title+legend moved into a **banner above the video** (`_render_banner`) so the info box never covers the tightly-cropped footage; on-frame label uses `scene_title` |
| `contract.py`, `writer.py`, `prompts/orchestrator.txt` (Step 5) | **`scene_title`** ("red phone on turntable") threaded `pipeline_inputs.json → contract → stats.json →` plots, report, video. Deterministic fallback `"<tracked> on <ref>"` |
| `prompts/orchestrator.txt` (parallel wave) | **STEP 0**: orchestrator runs the three seeded renderers **inline** (`render.figures` → `verify_figures` → `render.annotate`) as a required step — the mechanism already 100% reliable for the report. Subagents demoted to **verify-only** |
| `.pi/agents/{video-annotation,figures-gen}-subagent.md` | Rewrote the **short-path** defs pi actually loads (they were stale — injected hardcoded numbers, a "draw a timestamp" instruction) to "run the seeded module, then verify," with a hard no-numeric-values rule |

### The bug the live test caught (duplicate subagent defs)

First live re-run: report + figures came through the seeded path, but the **video was
hand-rolled** — tiny overlays, no banner, and it **printed numeric values** (breaking the
symbol-only rule). Root cause: the duplicate-dir hazard. pi loads the video subagent def
from the **short path `.pi/agents/`**, but the run-and-verify wording had only been added
to `.pi/agent/agents/`. The short-path def was a stale version that literally instructed a
timestamp overlay and injected example numbers.

**Fix:** (1) corrected the short-path defs, and (2) more robustly, made the orchestrator
run all three renderers **inline as STEP 0** so correctness no longer depends on which
subagent def loads. Report is immune to this because it always ran inline.

### Result — verified on the live agent stack (turntable, 3 jobs)

- `student_edition.pdf` / `teacher_key.pdf`: **0 images → 11–12 images** embedded.
- Annotated video: hand-rolled-with-numbers → **seeded banner render**, 1080×1428 →
  **1080×1734 (+306 px banner)**, symbols-only, scene title on-frame. Event log confirms
  the agent invoked `analysis.render.{figures,annotate}` via STEP 0.
- `scene_title` ("red phone on black circular base") on plots, report, and video.
- Question generation (Subagent C) **stays a real LLM subagent** — it is genuine pedagogy
  content, not layout, and its output was already good.

> Lesson: freezing the math wasn't enough — *layout* is just as mechanical, and an LLM
> re-deriving it re-introduces the same drift (missing images, wrong space, stray numbers).
> Seed every mechanical artifact; reserve the LLM for judgment (perception, questions).

> Open follow-up (not done): `.pi/agents/` still holds stale variant files
> (`*_updated.md`, `*.orchestrator-injected.md`); harmless now that STEP 0 doesn't depend
> on them, but worth cleaning up to avoid future confusion.

---

## Update — 2026-06-21: off-axis centre recovery + non-uniform motion

A second pass triggered by the ceiling-fan clip, whose kinematics first looked
"noise-dominated." Two distinct causes, neither was noise:

1. **Off-axis rotation centre.** The user-tapped axis sat **158 px** off the true
   orbit centre, so r/θ/ω were computed about the wrong point — faking an unstable
   radius (CV **0.39**) and scrambling ω (flags `radius_unstable`, `center_mismatch`,
   `high_center_drift`). The RANSAC fit was already good (1.6% residual) but policy was
   "always trust the mark." **Fix (`geometry.py`):** adopt the fit over a user/bootstrap
   mark only when unambiguously better — tight inlier residual **and** radius CV cut to
   <0.6× the mark's. New `center_source="ransac_override"` + flag
   `center_overridden_from_mark`. Self-guarding: a good mark (low CV) is never overruled.
   Fan radius CV **0.39 → 0.10**.

2. **Real non-uniform motion (not noise).** The fan is *spinning up* at constant
   α≈**1.18 rad/s²** (θ(t) quadratic fit R²=**0.9999**, ω 3.2→10.2). The pipeline only
   modelled uniform rotation, so `period_mismatch` / `unstable_phase_linearity` fired
   correctly. **Added** a motion-model classifier (`_motion_model` in `kinematics.py`):
   line-vs-parabola fit on θ(t) → `motion_type` ∈ {uniform, accelerating, decelerating},
   new `angular_acceleration` stats block (`alpha_rad_s2`, `alpha_r2`,
   `omega_initial/final`, `a_t_mean_m_s2 = |α|·r`). Those two flags are now gated on
   `motion_type`. Fitting θ (an integral) is robust where thresholding dω/dt flickered
   and had mislabelled the spin-up STABLE.

**Regression check:** deterministic re-run of all 10 workspaces — no crashes, no new
flags; turntables correctly reclassify as **decelerating** (α≈−4, hand-spun coast-down),
bicycle stays **uniform** (behaviour identical), fans **accelerating**. The exported fan
(`a2627aa2`) now carries only the informational `center_overridden_from_mark`.

Schema/docs updated: [data-contract.md](data-contract.md) §3.2 (new block + `center_source`
value), [pipeline-internals.md](pipeline-internals.md) §Step 6.

> Caveat unchanged: absolute metric results (r, v, a_c) still depend on the reference
> size (the fan's 1.3 m is provisional); angular results (ω, α, T) are exact regardless.
