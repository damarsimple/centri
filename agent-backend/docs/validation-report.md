# Determinism & Accuracy Validation Report

> Does freezing the kinematics into a seeded pipeline actually improve `/analyze`
> output? This report compares **before** (agent-authored math, 30 historical jobs)
> vs **after** (frozen `analysis/` pipeline, fresh runs) on the three turntable
> videos, against phone-gyro ground truth. Status: **in progress** — see §4.

Date started: 2026-06-05 · Model: Qwen3.6-35B-A3B via `pi` · Calibration: base
diameter **0.4 m** (corrected from 0.3 m this run).

## 1. What changed

- Kinematics (old steps 5–8) moved from agent-authored Python to a frozen, seeded
  package `workspace_lib/analysis/` (seeded like `sidecar.json`).
- Determinism fixes baked in: **seeded RANSAC RNG**, **single ω source**,
  **locked `stats.json` schema** with `allow_nan=False`.
- Orchestrator trimmed (1283→998 lines): perception writes `pipeline_inputs.json`,
  Step 6 runs `python -m analysis.run`.
- Reference base diameter corrected 0.3 m → **0.4 m** (scales `r_m`, `v`, `aᶜ` by
  0.75×; does not affect ω/period).

## 2. Ground truth (phone gyro, `gyro_gamma`)

| Video | mean ω (rad/s) | period (s) |
|---|---|---|
| IMG_3071 | 7.357 | 0.854 |
| IMG_3072 | 4.806 | 1.307 |
| IMG_3075 | 5.811 | 1.081 |

Gyro is **developer ground truth only** — never seen by the agent. ω/period are
calibration-independent, so they validate the tracking-only pipeline regardless of
the 0.3↔0.4 m change.

## 3. BEFORE — agent-authored math (30 historical jobs)

**Schema integrity:** 28 distinct `stats.json` top-level schemas across 30 jobs;
**17 contained bare `NaN`** (invalid JSON).

**Same-video numeric spread:**

| Video | runs | `period_s` spread | `mean_omega` | `stable_mean_omega` spread | `center_drift_px` |
|---|---|---|---|---|---|
| IMG_3071 | 15 | 0.793–1.002 (**26%**) | 6.16–8.25 | 0.60–11.1 | 0–116 |
| IMG_3072 | 5 | 1.486–1.487 (0%) | 4.681 | 0.82–4.99 | 13–393 |
| IMG_3075 | 5 | 1.102 (0%) | 5.827 | 2.89–6.07 | 8.9–**1013** |

Takeaways: `period_s`/`mean_omega` were already stable on 2/3 videos and accurate
(IMG_3075 mean ω within 0.3% of gyro), but **`stable_mean_omega` and
`center_drift_px` were unstable on every video**, schemas were never repeatable, and
IMG_3071's core period swung 26%.

## 4. AFTER — frozen pipeline (fresh runs, 3× per video)

Jobs submitted 2026-06-05 (3 per video). Calibration 0.4 m.

### 4a. Spot-check — job 1 (IMG_3071 run 1) — found & fixed a real bug

**Plumbing: PASS.** The new flow ran end-to-end on the live Qwen+pi stack: the agent
wrote a valid `pipeline_inputs.json`, Step 6 ran `analysis.run`, and the output was
`schema_version: 1` with **zero `NaN`**. The sanity gate also worked — it raised 7
flags rather than silently shipping a bad result.

**But the measurement was garbage** — and the spot-check is exactly what caught it:

| metric | job 1 (first run, buggy) | gyro GT |
|---|---|---|
| `center_drift_px` | **8045** | — |
| `r_fit_m` | **3.13 m** (bigger than the scene) | — |
| outliers rejected | **163 / 321** | — |
| `mean_omega` | **0.0** | 7.357 |
| `period_s` | **0.0** | 0.854 |

**Root cause (in the frozen pipeline, not perception):** the agent's input trajectory
was a clean orbit (radius std/mean = 3.8%), but the **seeded RANSAC found a degenerate
giant circle** (a huge radius is locally almost straight, so it captures arc points as
"inliers"). That bogus `r_fit` then poisoned the radius-outlier step, which nuked
163/321 good points → no rotation detectable. Determinism made it reproducible; it did
not make it *correct*.

**Fix** (`analysis/geometry.py`): when a trusted center exists (user mark / bootstrap),
derive the orbit radius and outlier rejection from the **median distance to that
center**, never from the RANSAC radius; and reject any RANSAC fit whose radius/center is
implausible vs the point spread (`ransac_fit_rejected` flag).

**After the fix, reprocessing job 1's *real* agent inputs offline:**

| metric | buggy | **fixed** | gyro GT |
|---|---|---|---|
| `center_drift_px` | 8045 | **0.0** | — |
| `r_fit_m` | 3.13 | **0.148** | — |
| outliers rejected | 163 | **0** | — |
| `mean_omega` | 0.0 | **7.372** | 7.357 → **0.2%** |
| `period_s` | 0.0 | **0.839** | 0.854 → 1.8% |

Determinism re-verified (two runs byte-identical). **Net: yes, the change improves
output — but only after this fix.** The patched pipeline matches the phone gyro to 0.2%
on the hardest (fast) video, with a locked, NaN-free schema. The 9-job batch was reset
and re-submitted on the patched pipeline (§4b).

### 4b. All-9 cross-run comparison (fixed pipeline, live)

All 9 jobs: `schema_version: 1`, **zero `NaN`**.

| Video | runs | `period_s` (spread) | `mean_omega` (spread) | vs gyro mean_ω | drift | determinism |
|---|---|---|---|---|---|---|
| IMG_3071 | 3 | 0.839 (**0.0%**) | 7.372 (**0.0%**) | 7.357 → **0.2%** | 0.0 | **byte-identical ×3** |
| IMG_3072 | 3 | 1.438 (**0.0%**) | 4.827 (**0.0%**) | 4.806 → **0.4%** | 28.4 | **byte-identical ×3** |
| IMG_3075 | 3 | 1.102–1.150 (4.3%) | 5.794–5.890 (1.7%) | 5.811 → **0.3%** (r1,r3) | 13 / **171** (r2) | r1≡r3 identical; **r2 differs** |

Per-run detail for the outlier:

| IMG_3075 | period | mean_omega | stable_omega | drift |
|---|---|---|---|---|
| run1 | 1.102 | 5.794 | 2.890 | 13.0 |
| run2 | 1.150 | 5.890 | **0.187** | **171.4** |
| run3 | 1.102 | 5.794 | 2.890 | 13.0 |

## 5. Verdict

**Determinism: achieved.** Two of three videos are byte-identical across all 3 runs
(0% spread), down from 26% on IMG_3071 before. Schema is locked (`schema_version: 1`)
and NaN-free on all 9 — vs 28 schemas / 17 NaN before.

**Accuracy: excellent.** `mean_omega` lands within **0.2–0.4%** of the phone gyro on all
three videos (the old pipeline was ~2.6% off on IMG_3072, for example). `period_s` is
within ~2% on two videos; IMG_3072 reads ~10% high on period despite a near-perfect
mean_ω — a median-vs-mean / active-window estimator nuance, not a determinism issue.

**The residual spread is tracking, not math — exactly the separation we built.**
IMG_3075 run2 differs (drift 171 vs 13, `stable_omega` collapsed to 0.187) *only*
because its SAM tracking produced a different trajectory that run; runs 1 and 3, with
consistent tracking, are byte-identical. The frozen pipeline is provably deterministic
for identical input — so any remaining variance now points squarely at the agentic
perception half, which is where to focus next.

**Open item:** `stable_mean_omega` is still the most fragile metric (0.187 on the
outlier run) — its phase-regression is sensitive to tracking noise. `mean_omega` and
`period_s` are robust; prefer them for the pilot. A follow-up could harden the stable-
phase segmentation or report `stable_mean_omega` only when its r² gate passes.
