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

> **Prompt wording is the #1 tracking-reliability lever.** `visual_cues` and `label` become
> the detector's text query — use the **simplest common category noun** (e.g. `"toy"`, not
> `"cream colored doll"`; 6%→100% on the same clip). See
> [object-detection-prompts.md](object-detection-prompts.md).

```jsonc
{
  "tracked_object":     { "visual_cues": ["toy"] },
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

### 1a. Tracking mode (optional) — `object` | `color` | `frequency`

The trajectory in Step 2 can be produced three ways. **All three write the same
`api_cache.json` schema**, so Steps 3–6 (calibration, kinematics, figures, material)
are identical regardless. Selected by `tracking_mode` (sidecar flag); if absent the
agent defaults to `object` and may override only with clear scene evidence.

| mode | producer | use when | needs |
|---|---|---|---|
| `object` (default) | remote SAM3 `/track` | one distinct moving object | `visual_cues`, `physical_size` |
| `color` | local `analysis.color_track` (CPU) | the mover is one of several **identical** shapes a shape-tracker aliases (5 fan blades); a uniquely-coloured marker you placed. Needs the marker visible per frame (it can go sparse if often occluded). | HSV range, ROI; marker doubles as the size reference (`physical_size` = marker size m) |
| `frequency` | local `analysis.freq_track` (CPU) | a fast, identical-blade rotor that **under-samples even at 60 fps** (blade-pass nears `fps/2`), or you need ω(t) without a per-frame point. Measures blade-pass freq → ω, then synthesizes a clean orbit (flagged). | `n_blades`, ring radius, rotation centre; `physical_size` = **orbit radius (m)** |

> **Try `object` at 60 fps first for a fast multi-blade fan.** The `IMG_3750.MOV` failure at
> 30 fps was **under-sampling (wagon-wheel), not motion blur** — at 60 fps SAM3 `"fan blade"`
> tracked the peak window cleanly (the marker stays sharp). Reach for `color`/`frequency` only
> when fps alone can't recover a clean per-frame point.

```jsonc
// colour-marker example (e.g. orange paper on a fan blade)
{
  "tracked_object":     { "visual_cues": ["orange marker"] },
  "reference_geometry": { "label": "orange marker", "physical_size": 0.08 },  // marker real size, m
  "rotation_center_frac": [0.40, 0.48],
  "tracking_mode": "color",
  "tracking_config": { "hsv_lo": [165,60,70], "hsv_hi": [12,255,255],  // H wraps 165→12 = red
                       "roi_radius": 360, "max_step": 100, "min_area": 60 }
}
// frequency example (fast multi-blade fan at peak speed)
{
  "tracked_object":     { "visual_cues": ["fan rotor"] },
  "reference_geometry": { "label": "fan rotor", "physical_size": 0.30 },      // ORBIT radius, m
  "rotation_center_frac": [0.40, 0.48],
  "tracking_mode": "frequency",
  "tracking_config": { "n_blades": 5, "ring_radius": 200, "orbit_radius_px": 250, "n_probes": 12 }
}
// explicit pixel span (when the calibrated span is NOT any object's bbox)
{
  "tracked_object":     { "visual_cues": ["yellow marker"] },
  "reference_geometry": { "label": "hub-to-marker orbit radius",
                          "physical_size": 0.44,      // tape: hub centre -> card centre, m
                          "diameter_px": 260.0 },     // the SAME span in px, used verbatim
  "rotation_center_frac": [0.47, 0.46],
  "tracking_mode": "color",
  "tracking_config": { "hsv_lo": [10,90,90], "hsv_hi": [35,255,255],
                       "roi_radius": 330, "min_area": 300 }
}
```

> **`reference_geometry.diameter_px` (optional).** When present it is used **verbatim** and
> nothing is measured. Use it whenever the span paired with `physical_size` is not the
> bounding box of a detectable object — an orbit radius, a tape mark, a span across two
> features. `px_per_m = diameter_px / physical_size`, so **the two must describe the SAME
> span**, and stating both removes the pipeline's freedom to choose a different one.
> Omit it and the generic bbox sizing is unchanged.
>
> This exists because a tilted orbit images as an ellipse, so "the orbit radius" has three
> plausible values — semi-major, semi-minor, circle-fit median. On `fan-4656` two runs from
> a byte-identical sidecar picked 260 px and 245 px, giving `px_per_m` 591 vs 558 and a 6%
> swing in the taught `a_c`. Prose in `hints.md` is not a contract; this field is.

> `color`/`frequency` run locally (OpenCV, no GPU) and **assume rotation is baked into
> the pixels** (no rotation metadata) — our portrait clips are exported that way.
> `frequency` mode also writes `data/frequency_meta.json` (per-probe blade-pass
> agreement = confidence) and flags `kinematics_from_frequency_synth`; the synth orbit
> is a perfect circle, so the trajectory-consistency flags (`period_mismatch`,
> `unstable_phase_linearity`) are not meaningful there — trust `frequency_meta.json`.
> Nyquist: `blade_pass_hz < fps/2` (use 60 fps for a fast fan).

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
                   // center_source ∈ {user_mark, bootstrap, ransac_fit, ransac_override}.
                   // "ransac_override" = a user/bootstrap mark was off-axis and the
                   // RANSAC fit replaced it (tight residual AND much lower radius CV);
                   // see geometry.py and the "center_overridden_from_mark" flag.
  "summary":     { "mean_r_m": 0.110, "std_r_m": 0.0006, "mean_omega": 5.83, "std_omega": 2.20,
                   "mean_v": 0.66, "mean_ac": 4.39, "max_ac": 10.82, "rotation_direction": "CCW" },
  "period_and_frequency": { "period_s": 1.10, "frequency_hz": 0.91, "T_primary": 1.10,
                            "T_fft": 1.10, "period_discrepancy": 0.0 },
  "stable_phase":    { "stable_mean_omega": 5.74, "stable_mean_ac": 4.30,
                       "stable_omega_r2": 0.999, "stable_omega_std_err": 0.058, "n_stable_segments": 9 },
  "phase_boundaries":{ "increase_start_omega": null, "increase_end_omega": null, "decrease_end_omega": null },
  "angular_acceleration": { "motion_type": "uniform", "alpha_rad_s2": -0.10, "alpha_r2": 0.998,
                            "omega_initial": 5.1, "omega_final": 5.0, "a_t_mean_m_s2": 0.0 },
                   // motion_type ∈ {uniform, accelerating, decelerating}, from a
                   // parabola-vs-line fit on theta(t) (constant alpha => theta is quadratic).
                   // When non-uniform, period_mismatch / unstable_phase_linearity are
                   // suppressed (they only apply to steady rotation) and a_t = |alpha|*r.
  "roi_crop":   { "x_off": 0, "y_off": 161, "crop_w": 1080, "crop_h": 1438, "fallback": false },
  "validation_flags": [ "fft_skipped_insufficient_data", ... ],
                   // newer flags: "center_overridden_from_mark" (off-axis mark replaced by fit)
  "phases":     { "phase_labels": ["STABLE", ...], "stable_segments": [[0, 350]] }
}
```

> The orchestrator unpacks the nested values into flat locals (`mean_omega`, `cx_px`,
> `period_s`, …) for the LaTeX macros and subagent injection — see
> [agents-behaviour.md](agents-behaviour.md). Bump `schema_version` and update this
> table together when the schema changes.

### 3.3 Other

- `data/active_mask.npy` — boolean per frame.
- `data/questions.json` — difficulty-tiered (easy/intermediate/advanced), multimodal 9–12 question bank; dict shape `{object_name, scenario, questions:[…]}` (see [subagents.md](subagents.md)).
- `data/material_seed.json` — **deterministic** seed for Module D, written by Step 6
  (`analysis/material_seed.py`): `{variables, relations, angular_acceleration, timeline (time-anchored ω(t)), figures, calibration_note}`. Same inputs → identical seed.
- `data/material.json` — the generated **learning material** (Subagent D); dict shape
  `{object_name, scene_title, sections:{<5 fixed headers>: <prose>}}`. Rendered as the
  leading **Learning Material** PDF section; the BERTScore candidate for material eval.
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
