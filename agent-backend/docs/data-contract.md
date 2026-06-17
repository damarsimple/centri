# Data Contract — Inputs, Outputs, and the Pedagogy Seam

> Every data shape that crosses a boundary: into the pipeline, between its stages,
> out via the API, and **across to the inquiry tutor (`fastapi-gpt`)**. This is the
> document the modality-substitution and the accuracy pilot depend on. Companions:
> [pipeline-internals.md](pipeline-internals.md),
> [architecture-overview.md](architecture-overview.md),
> [change-spec-phase0.md](change-spec-phase0.md).

## 1. Input — `POST /analyze`

Multipart form (`app/routes.py`):

| Field | Type | Notes |
|---|---|---|
| `video` | file | mp4/mov/avi/mkv, ≤ 500 MB; content-type checked |
| `sidecar` | string (JSON) | scene geometry, see below |
| `template` | string | template dir name (e.g. `basetemplate-turntable-1`) |

Header `X-API-Key` required. Returns `{ "job_id": "<uuid>" }` and enqueues a Celery
task. **Sidecar schema** (matches the app's `SidecarJson` and Step 1 of the orchestrator):

```jsonc
{
  "tracked_object":     { "visual_cues": ["red ball"] },
  "reference_geometry": {
    "label":          "lazy susan",
    "physical_size":  0.30          // metres; optional → estimated if absent
  },
  "rotation_center_frac": [0.52, 0.43],  // user-marked spin axis, frac of frame (authoritative)
  "display_w": 1080, "display_h": 1920, "video_w": 1080, "video_h": 1920
}
```

> The old `reference_geometry.bbox_center_px` field was **removed** (2026-06): the
> backend never used it (the reference centre comes from tracking; the axis from
> `rotation_center_frac`), and the app filled it with the same tap as the axis. The
> orchestrator no longer reads it.

> Note: `REPORT.md §3.1` shows a *different* richer sidecar (title/theory/inferences
> text). The **orchestrator only reads the `tracked_object` / `reference_geometry`
> shape above**; the report-text fields are not consumed by the pipeline. Treat the
> shape above as authoritative.

## 2. Tracking API contract (the one external call)

`POST {TRACKING_API_URL}/track` — multipart `file` (video) + `targets`
(JSON array of labels, e.g. `["red ball", "lazy susan"]`).

Response:

```jsonc
{
  "status": "success",
  "trajectories": {
    "<label>": [ { "frame": int, "cx": float, "cy": float,
                   "bbox": [x0,y0,x1,y1], "obox": [[x,y],...]? }, ... ]
  },
  "video_info": { "width": int, "height": int, "nb_frames": int,
                  "fps": float, "rotation": 0|90|180|270 }
}
```

Cached verbatim to `data/api_cache.json`. `cx`/`cy` are detection centers in display
space; the pipeline converts to crop space by subtracting the crop offset.

## 3. Internal data files

Produced by the sequential phase, consumed by subagents. All pixel values in
**cropped-video space**.

### 3.1 `data/kinematics.csv` — the canonical per-frame series

One row per frame, blank where tracking missing:

```
time_s, r_px, r_m, theta_rad, omega_rad_s, v_m_s, ac_m_s2, active, x_px, y_px
```

This is written by the **frozen pipeline** (`analysis/writer.py`) and served under
`/files/...`. It is the single most important file for everything downstream of
measurement.

> `x_px, y_px` (added 2026-06) are the tracked centroid in **cropped-video space**,
> after outlier removal **and** short-gap interpolation — i.e. the exact series the
> kinematics were computed from. **Figures must plot geometry from these columns**,
> never from `api_cache.json` (raw full-frame → offset from the centre by
> `roi_crop.y_off`, which made the fitted circle float off the points).

### 3.1a `data/pipeline_inputs.json` — the perception→math handoff

The agent's Steps 1–5 write this; the frozen `analysis/` pipeline reads it. It is the
**one** schema the agent is responsible for, and the seam that makes the kinematics
deterministic. Full field table in
[`analysis/README.md`](../workspace_lib/analysis/README.md). Shape:

```jsonc
{
  "fps": 59.94, "duration_s": 5.87, "n_raw_frames": 350,
  "object_name": "red phone", "scene_title": "red phone on turntable",   // optional; fallback "<tracked> on <ref>"
  "tracked_label": "red phone", "ref_label": "black circular base",
  "coordinate_space": "display",            // "display" (raw full-frame) | "cropped"
  "trajectory_x_px": [207.1, null, ...],    // FULL-FRAME (display) space, null where missing
  "trajectory_y_px": [933.4, null, ...],
  "center":    { "cx_px": 543.0, "cy_px": 878.0, "source": "user_mark" },  // also full-frame
  "reference": { "diameter_px": 1078.0, "physical_size_m": 0.30, "physical_size_source": "sidecar" },
  "roi_crop":  { "x_off": 0, "y_off": 161, "crop_w": 1080, "crop_h": 1438, "fallback": false }
}
```

> **`coordinate_space` + the display→cropped transform (2026-06).** The agent emits the
> trajectory **and** center in **full-frame (`"display"`) space** — the raw tracker
> output, *not* crop-subtracted — and the frozen `analysis/contract.py` subtracts
> `roi_crop.{x_off,y_off}` from both *together*. This moved the last coordinate
> arithmetic off the LLM. Before, the agent crop-subtracted the trajectory by hand and
> did it **inconsistently** across runs (one subtracted the offset, one didn't) while the
> center stayed cropped → a `y_off`-sized mismatch that corrupted `period_s` /
> `stable_mean_omega` on IMG_3072. `"cropped"` is still accepted (no conversion) for
> already-converted inputs. Everything downstream of the contract remains cropped-space.

### 3.2 `data/stats.json` — summary (locked schema, `schema_version: 1`)

Written **once** in `analysis/writer.py::build_stats` with `json.dump(..., allow_nan=False)`.
Nesting is the contract; missing values are JSON `null`, never `NaN`. This replaced the
old agent-authored output (28 distinct schemas / 17 with invalid NaN).

```jsonc
{
  "schema_version": 1,
  "object_name": "red phone", "scene_title": "red phone on turntable",
  "tracked_label": "red phone", "ref_label": "black circular base",
  "coordinate_space": "cropped-video",
  "video_info":  { "fps": 59.94, "duration_s": 5.87, "n_raw_frames": 350 },
  "tracking":    { "coverage_pct": 100.0, "n_valid_frames": 350, "n_inliers": 282,
                   "n_outliers_rejected": 0, "active_duration_s": 1.92,
                   "n_interpolated_frames": 0 },
  "calibration": { "cx_px": 543.0, "cy_px": 717.0, "center_source": "user_mark",
                   "center_drift_px": 8.9, "px_per_m": 3593.3, "diameter_px": 1078.0,
                   "physical_size_m": 0.30, "physical_size_source": "sidecar",
                   "r_fit_px": 406.5, "r_fit_m": 0.1131 },
  "summary":     { "mean_r_m": 0.110, "std_r_m": 0.0006, "mean_omega": 5.83, "std_omega": 2.20,
                   "mean_v": 0.66, "mean_ac": 4.39, "max_ac": 10.82, "rotation_direction": "CCW" },
  "period_and_frequency": { "period_s": 1.10, "frequency_hz": 0.91, "T_primary": 1.10,
                            "T_fft": 1.10, "period_discrepancy": 0.0 },
  "stable_phase":    { "stable_mean_omega": 5.74, "stable_mean_ac": 4.30,
                       "stable_omega_r2": 0.999, "stable_omega_std_err": 0.058, "n_stable_segments": 9 },
  "phase_boundaries":{ "increase_start_omega": null, "increase_end_omega": null, "decrease_end_omega": null },
  "roi_crop":   { "x_off": 0, "y_off": 161, "crop_w": 1080, "crop_h": 1438, "fallback": false },
  "validation_flags": [ "fft_skipped_insufficient_data", ... ],
  "phases":     { "phase_labels": ["STABLE", ...], "stable_segments": [[0, 350]] }
}
```

> The orchestrator unpacks the nested values into flat locals (`mean_omega`, `cx_px`,
> `period_s`, …) for the LaTeX macros and subagent injection — see
> [agents-behaviour.md](agents-behaviour.md). Bump `schema_version` and update this
> table together when the schema changes.

### 3.3 Other

- `data/active_mask.npy` — boolean per frame.
- `data/questions.json` — the static 8-question worksheet (see [subagents.md](subagents.md)).
- Phase segments are embedded in `stats.json["phases"]` (no separate `phases.json`).
- **Rendered artifacts** (`plots/*.png` + `figure_qa.json`, `report/*.tex`+`*.pdf`,
  `video_annotation/annotated_video.mp4`) are produced by the **seeded, deterministic**
  `analysis/render/{figures,report,annotate}.py` modules — read from the frozen
  `stats.json` / `kinematics.csv`, not authored by the agent (see [subagents.md](subagents.md)).

## 4. Output — `GET /result/{job_id}`

`app/schemas.py`:

```python
class FilePaths(BaseModel):
    student_pdf: str
    teacher_pdf: str
    annotated_video: str
    summary_panel: str

class JobResultResponse(BaseModel):
    job_id: str
    stats: Dict[str, Any]      # the full stats.json
    files: FilePaths
```

So today `/result` exposes **the summary `stats` + four file URLs** only. The four
files are resolved by the extractor agent (`prompts/job-output-extractor.txt`) and
URL-rewritten in `worker/tasks.py:_parse_extractor_output`. Static files are served
at `/files/job_{id}/...`.

**`kinematics.csv` is NOT exposed** — even though it exists on disk and is already
served statically. That is the entire gap Phase 0 closes.

## 5. The seam — agent-backend ⇄ `fastapi-gpt` pedagogy

Her inquiry tutor and her question endpoints consume sensor data as a CSV with
**these exact headers** (from `fastapi-gpt`, `nokia 1.csv`):

```
Time (s), Angular velocity (rad/s), Acceleration (m/s^2)
```

Mapping from our series to hers:

| Her column | Our `kinematics.csv` column | Note |
|---|---|---|
| `Time (s)` | `time_s` | identical |
| `Angular velocity (rad/s)` | `omega_rad_s` | identical quantity; she may want `abs()` |
| `Acceleration (m/s^2)` | `ac_m_s2` | her "Acceleration" = centripetal aᶜ = ω²r — same quantity Step 8 derives |
| *(radius, used elsewhere)* | `r_m` / `stats.r_fit_m` | her stack gets radius from image; we have it directly |
| *(object label)* | sidecar `tracked_object` / `stats.object_name` | for stage-1 object context |

**Implication:** if the pipeline emits a CSV with her three headers (a column rename
of `time_s, omega_rad_s, ac_m_s2`), video output is a **drop-in** for her sensor
pedagogy — no change to her endpoints. There is one real subtlety: the gyroscope
measures aᶜ directly, while we *derive* aᶜ = ω²r; both are valid, and comparing them
is itself a useful pilot signal.

Two ways to produce the her-schema CSV (decide in Phase 0):
- **(a)** rename columns at the consumption side (when feeding her endpoints), or
- **(b)** have the pipeline additionally write `data/series.csv` with her headers.

(b) is cleaner for the pilot (one canonical, ready-to-diff artifact); (a) avoids
touching the orchestrator. See [change-spec-phase0.md](change-spec-phase0.md).

## 6. The pilot — why the schema match matters

The accuracy pilot compares **video** (this pipeline) against **sensor** (stock
phyphox gyroscope export). If both emit `Time (s), Angular velocity (rad/s),
Acceleration (m/s^2)`, comparison is a column-for-column diff:

- **Summary-stat comparison** (recommended first): mean ω, period, revolutions over
  the same spin → only needs trial-ID matching, no clock sync.
- **Time-series comparison** (later): align `omega_rad_s(t)` vs gyro ω(t) by
  cross-correlation (robust to phone-clock offset).

`kinematics.csv` + a known-RPM source gives absolute ground truth for both methods.
See [architecture-overview.md](architecture-overview.md) "Pilot".
