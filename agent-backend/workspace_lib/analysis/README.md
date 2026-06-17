# `analysis/` — Frozen Deterministic Kinematics Pipeline

This package is **seeded into every job workspace** by the API
(`app/workspace.py::seed_pipeline`), exactly like `sidecar.json` and the template
video. The orchestrator agent (`pi` + Qwen) does **not** author this code — it
only produces `pipeline_inputs.json` and then runs:

```bash
python -m analysis.run        # from the job workspace root
```

## Why it exists

When the agent re-authored the kinematics each run we observed, across 30 jobs:

- **28 distinct `stats.json` schemas** (different keys/nesting every run),
- **bare `NaN` in 17 of them** (invalid JSON that strict parsers reject),
- **`center_drift_px` swinging 8.9 → 1013 px on the *same* video** (unseeded
  RANSAC), and **`stable_mean_omega` swinging 2.9 → 6.1 rad/s** (two inconsistent
  omega computations).

Freezing the math here makes **"same `pipeline_inputs.json` → byte-identical
`stats.json`"** true by construction. The deterministic backbone was already
accurate — on IMG_3075 the pipeline matches the phone-gyro ground truth to **0.3%**
on mean angular velocity (see `tools/gt_harness.py`).

## The seam

```
 AGENTIC (pi/Qwen)                          FROZEN (this package)
 ─────────────────                          ─────────────────────
 Step 1  scene parse / ffprobe
 Step 2  remote SAM tracking  ─┐
 Step 3  coordinate validation │  perception
 Step 4  center bootstrap      │  artifacts
 Step 5  reference sizing  ────┴─► pipeline_inputs.json ─► analysis.run ─► stats.json
                                                                          kinematics.csv
                                                                          active_mask.npy
```

The agent owns perception (judgment: what to track, where the center is, how big
the reference is). Everything after the trajectory exists is pure arithmetic and
lives here.

## Input contract — `analysis_output/data/pipeline_inputs.json`

Written by the agent's Step 5. Validated by `contract.py` (the run aborts with a
clear error if anything is missing — it never invents values).

| Key | Type | Meaning |
|---|---|---|
| `fps` | float | frames/sec (ffprobe-authoritative) |
| `duration_s` | float | clip duration |
| `n_raw_frames` | int | frame count; both trajectory arrays must match this length |
| `object_name` | str | human label of the moving object |
| `scene_title` | str | *(optional)* short friendly title for artifact titles, e.g. `"red phone on turntable"`; falls back to `"<tracked> on <ref>"` if absent |
| `tracked_label`, `ref_label` | str | tracker labels for moving object / reference |
| `coordinate_space` | str | `"display"` (raw full-frame) \| `"cropped"`. Tells `contract.py` whether to subtract the crop offset. The agent emits `"display"` — see note below. |
| `trajectory_x_px`, `trajectory_y_px` | list[float\|null] | per-frame tracked-object centroid in the space named by `coordinate_space`, `null` where the detector missed |
| `center.cx_px`, `center.cy_px` | float | rotation center, in the space named by `coordinate_space` |
| `center.source` | str | `"user_mark"` \| `"bootstrap"` |
| `reference.diameter_px` | float | reference object pixel diameter (median of its bboxes); size is space-invariant |
| `reference.physical_size_m` | float | real-world size in metres (>0) |
| `reference.physical_size_source` | str | `"sidecar"` \| `"world_knowledge"` (provenance **string**, never the number) |
| `roi_crop` | object | crop offset `{x_off, y_off, crop_w, crop_h, fallback}`; used for the display→cropped conversion **and** passed through to `stats.json` |

> **The display→cropped transform lives HERE, not in the agent (2026-06).** The agent
> emits the **raw tracker trajectory and center in full-frame (`"display"`) space**;
> `contract.py` subtracts `roi_crop.{x_off,y_off}` from the trajectory **and** the
> center *together*, so they can never land in different spaces. Previously the agent
> crop-subtracted the trajectory by hand and did it **inconsistently** (one run
> subtracted, one didn't) while the center stayed cropped → an `y_off`-sized mismatch
> that wrecked radius / phase / `stable_mean_omega` on IMG_3072. Moving the one
> subtraction into the frozen contract makes that class of bug structurally
> impossible. (`"cropped"` is still accepted for already-converted inputs.)

## Output contract — `analysis_output/data/stats.json` (schema_version 1)

Locked nesting; written once in `writer.py::build_stats` with
`json.dump(..., allow_nan=False)`. Missing values serialize as JSON `null`, never
`NaN`. Top-level keys:

```
schema_version, object_name, scene_title, tracked_label, ref_label, coordinate_space,
video_info:            { fps, duration_s, n_raw_frames }
tracking:              { coverage_pct, n_valid_frames, n_inliers, n_outliers_rejected, active_duration_s, n_interpolated_frames }
calibration:           { cx_px, cy_px, center_source, center_drift_px, px_per_m,
                         diameter_px, physical_size_m, physical_size_source, r_fit_px, r_fit_m }
summary:               { mean_r_m, std_r_m, mean_omega, std_omega, mean_v, mean_ac, max_ac, rotation_direction }
period_and_frequency:  { period_s, frequency_hz, T_primary, T_fft, period_discrepancy }
stable_phase:          { stable_mean_omega, stable_mean_ac, stable_omega_r2, stable_omega_std_err, n_stable_segments }
phase_boundaries:      { increase_start_omega, increase_end_omega, decrease_end_omega }
roi_crop:              { ... passthrough ... }
validation_flags:      [ ... ]
phases:                { phase_labels, stable_segments }
```

Also writes `kinematics.csv` (`time_s, r_px, r_m, theta_rad, omega_rad_s, v_m_s,
ac_m_s2, active, x_px, y_px`) and `active_mask.npy`. `x_px,y_px` are the cropped-space
centroid after outlier removal + short-gap fill — the series the kinematics used;
figures plot geometry from these (never `api_cache.json`). `tracking` also carries
`n_interpolated_frames`.

**Short-gap fill (deterministic).** `kinematics._fill_short_gaps` bridges interior
tracking gaps `≤ MAX_GAP_S` (0.2 s) by interpolating `(θ, r)` about the centre — filled
points land on the orbit, not on a chord. Only between two real detections (no end
extrapolation); gaps over the limit stay `NaN`. Pure function of the input (no RNG), so
determinism holds; `coverage_pct` reflects real detections only, the fill is reported
separately and flagged `interpolated_short_gaps`.

## Determinism guarantees

1. **Seeded RNG** (`common.RANDOM_SEED`) — RANSAC draws from `common.RNG`, so the
   circle fit is identical every run. (This was the root cause of the drift swing.)
2. **Single omega source** — `kinematics.compute` derives ω once (unwrap →
   Savitzky-Golay → gradient → median filter) and uses it for active detection,
   summary, period, *and* phases. The old code used two different ω series.
3. **`allow_nan=False`** — a stray NaN raises instead of shipping invalid JSON.
4. **Coordinate transform owned by the contract** — `contract.py` performs the one
   display→cropped subtraction for trajectory and center together (`coordinate_space`),
   so they always share one space. Removed the last agent-side arithmetic that varied
   run-to-run (the IMG_3072 `y_off` mismatch).

## Module map

| File | Responsibility |
|---|---|
| `contract.py` | load + validate `pipeline_inputs.json` → `Inputs`; owns the deterministic display→cropped transform (`coordinate_space` + `roi_crop`) |
| `geometry.py` | RANSAC circle fit (seeded), outlier rejection, center selection, `px_per_m` (old steps 5–6) |
| `kinematics.py` | ω/v/aᶜ, active detection, period+FFT, phase detection, summary (old steps 7–8) |
| `writer.py` | locked `stats.json` (allow_nan=False) + `kinematics.csv` + sanity gate |
| `run.py` | `python -m analysis.run` entry point; emits progress markers |
| `common.py` | seeded RNG, logging, validation flags, step markers |
| `render/figures.py` | **seeded, deterministic** plot generator — 9 plots + `summary_panel.png` + `figure_qa.json` from `stats.json`/`kinematics.csv` (cropped space; scene title). `python -m analysis.render.figures` |
| `render/report.py` | **seeded, deterministic** LaTeX generator — `student_edition.tex` + `teacher_key.tex` from `stats.json` + `questions.json`; `\graphicspath` so images always resolve, null-guarded, escaped. `python -m analysis.render.report` |
| `render/annotate.py` | **seeded, deterministic** annotated-video renderer — symbol-only overlays (no numeric values) scaled to the frame, title+legend in a banner above the footage. `python -m analysis.render.annotate` |

> **The `render/` subpackage** is seeded the same way and run the same way — the
> orchestrator runs these modules (parallel-wave STEP 0) and the figure/video subagents
> only *verify/lightly adapt* their output. They consume the frozen `stats.json` /
> `kinematics.csv`; they do not compute physics. Unlike the kinematics, small aesthetic
> edits are allowed — but plotting from `api_cache.json` (wrong space) and drawing numeric
> values on the video are not. See [docs/subagents.md](../../docs/subagents.md).

## Changing the schema

`build_stats` in `writer.py` **is** the public contract. Downstream consumers
(LaTeX report macros in `prompts/orchestrator.txt`, the three subagents,
`app/result_data.py`) read these exact paths. Bump `schema_version` and update
[../../docs/data-contract.md](../../docs/data-contract.md) when you change it.

## Validating changes

```bash
python tools/gt_harness.py     # determinism (byte-identical x2) + gyro accuracy
```

The gyro CSVs in `/home/damar/new-case/` are **developer ground truth only** — they
are never seeded into a workspace and never reach the agent. The product is
tracking-only.
