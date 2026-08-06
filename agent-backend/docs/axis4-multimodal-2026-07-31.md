# Axis 4 — the multimodal judge, and what it found (2026-07-31)

> ⚠ **FROZEN RECORD — superseded 2026-08-06, and NOT re-run.** Everything below describes the
> **7-clip / n = 21** corpus, which no longer exists (see `SESSION_CHECKPOINT.md`). The corpus is
> now **5 clips / n = 15** and **Axis 4 has not been re-scored on it** — this is the one part of
> the evaluation that has not been re-derived, and the paper's multimodal table still carries
> these numbers.
>
> Two specific cautions before quoting `annotation_correctness` (4.29–4.43, the strongest row in
> the whole evaluation):
> 1. It was scored on a **still frame**, never on `annotated_video.mp4` (TODO §1.3).
> 2. On 2026-08-06 a clip shipped **every overlay drawn 328 px off its object** — the centre of
>    rotation on a fan blade — in the very figure this axis rates. The scored run was a
>    correctly-registered predecessor of that clip, so **this row is not evidence that the defect
>    class would be caught.** Put a deliberately mis-registered overlay in front of the raters
>    before quoting it again.

**Axis 4 had never been scored on the current material.** Axes 1–3 are text and are judged by
`run_llm_judge.py`; Axis 4 asks whether the *figures* are correct, and needs a rater that can see
them. The only Axis-4 output that existed (`multimodal_eval_report.md`) was dated 2026-06-25 —
before the pedagogy rework and before the figure fixes of 07-27/07-31, so it described figures
that no longer exist.

This is the first Axis-4 run on the shipped figures. **It found a defect class that both the text
judges and the deterministic checker are structurally blind to, including one regression
introduced the same day.** Companion: `judge-reliability-2026-07-31.md` (axes 1–3, two raters),
`eval-rubric-ika.md` (the rubric), `eval-framework.md` (the method).

---

## 1. Design

| | |
|---|---|
| **Unit** | one worksheet — 21 = 7 clips × 3 tiers |
| **Instrument** | 11 criteria in 4 modality blocks, 1–5 (`eval-rubric-ika.md` Axis 4) |
| **Rater** | `Claude Opus 5` (`claude-opus-5`), 7 agents, one clip each, blind — scored 2026-07-31 |
| **Inputs per worksheet** | the passage, the measured ground truth, **the figure PNGs**, and the renderer's own manifest of what each figure claims to show (`plots/figure_qa.json`) |

Prompts are frozen the same way as axes 1–3 (`tools/export_multimodal_prompts.py`), so a second
rater can be scored on the identical question later.

### 1.1 Modalities are per TIER, and absence is not failure

`render/report.py TIER_ARTIFACTS` decides what is printed beside each tier. **The basic tier ships
no table at all** — by design, to keep its visual load low (cognitive load theory).

| tier | image | graph | table | criteria scored |
|---|---|---|---|---|
| basic | `annotated_image_basic` | `angle_points_basic`, `trajectory_basic` | — | **7** |
| intermediate | `annotated_image` | `omega_t`, `trajectory` | `annotated_table` | 11 |
| advanced | `annotated_image` | `omega_t`, `ac_t`, `trajectory` | `annotated_table` | 11 |

So basic's four table criteria are **`n/a`, and excluded from every mean**. Scoring an absent
modality — as 1, or as 0 — would invent a penalty for a figure the tier was deliberately designed
not to show, and would make the basic tier look *worse* the more correctly it was built. This is
the single most important implementation detail in `tools/build_multimodal_table.py`.

---

## 2. Results, by modality

| Modality | basic | intermediate | advanced |
|---|---|---|---|
| Image–text | 3.71 | 3.50 | 3.86 |
| Text–graph | 3.36 | 3.14 | 3.25 |
| Text–table | *n/a* | 3.36 | 3.25 |
| **On video — annotation correctness** | **4.29** | **4.43** | **4.29** |
| **All criteria scored** | 3.59 | 3.40 | 3.45 |

Full per-criterion table: `material_work/_eval/multimodal_axis4_2026-07-31.md`.

**Three things to read off this.**

**(a) There is no tier ladder in Axis 4** — 3.59 / 3.40 / 3.45, flat and non-monotonic. The text
axes show advanced clearly ahead; the figures do not improve with level. That is expected on
reflection (the same renderer draws all three) but it means **the tier claim rests on the prose
alone**, and Axis 4 cannot be cited to support it.

**(b) `annotation_correctness` is the strongest row in the whole evaluation (4.29–4.43).** This is
Centri's own contribution row — the overlays drawn on the video frame. Every rater independently
verified the printed values against ground truth and the arrow geometry against the fitted circle:
values match to three significant figures, the velocity arrow is perpendicular to the radius to
within ~1°, and the direction is correct. **This is the strongest evidence yet that the 07-31
direction fix landed**, and it comes from a rater that was never told a fix had happened.

**(c) The weakest row is `graph_sense_physical` (2.29–2.71)** — "conclusions drawn from the graph
are consistent with physical principles". That is precisely the defect below. The rubric row that
measures figure-versus-physics contradiction is the lowest-scoring row in the axis.

---

## 3. The defect Axis 4 exists to catch

### 3.1 A phase band labelled "not turning" over a curve reaching 24 rad/s — a same-day regression

On 2026-07-31, rest bands were given a printed word so that "the jitter inside them cannot be read
as motion":

```python
REST_WORDS = {"INACTIVE": "not turning", "IDLE": "not turning"}
```

The segmenter, however, marks spans INACTIVE that contain real motion. Measured across the corpus,
`|ω|` inside rest-labelled samples:

| clip | rest samples | max abs(ω) inside | >1 rad/s | >5 rad/s |
|---|---|---|---|---|
| `computerfan-4029` | 631 | **24.14 rad/s** | 36% | 22% |
| `turntable-3` | 244 | **10.22 rad/s** | 21% | 9% |
| `fan-4028` | 1530 | 1.16 rad/s | 82% | 0% |
| `turntable-1` | 185 | 2.28 rad/s | 12% | 0% |
| `turntable-2` | 145 | 1.64 rad/s | 7% | 0% |

Two different underlying causes: genuine mis-segmentation (`computerfan-4029`, `turntable-3`,
where bursts fall inside a rest span) and the known **1.0 rad/s frequency-synthesis floor** on
`fan-4028`, where the curve never reaches zero so "not turning" sits over a line pinned at 1.0.

**The label did not create the segmentation error — it made a silent error into a printed
falsehood.** A reader trusts the word over the line.

**Scale of it: 11 of the 12 rest bands in the corpus carried a label their own curve contradicted.**
The feature was wrong essentially everywhere it appeared.

**Fix shipped** (`_rest_label_is_contradicted`, `render/figures.py`): a rest word is suppressed
when the band's own samples exceed 5% of the series maximum. The **shading stays** — a colour is
not a claim — and the word goes. Threshold is relative to the series so it holds for rad/s and
m/s² alike. Pinned by `tools/tests/test_phase_label_honesty.py` (7 tests), including that a burst
*outside* the band must not suppress a legitimate label, and that an all-NaN dropout is missing
data rather than evidence of motion. All 7 clips re-rendered; `verify_figures` clean on all 7.

**Still open: the segmentation itself.** Suppressing the word stops the figure lying; it does not
make the phase boundaries right. `turntable-1`'s rest band still begins ~0.5 s before ω reaches
zero, and the trajectory plot corroborates it independently — its grey "Inactive" points span
≈0.28 m of real arc.

### 3.2 Why neither existing layer could catch it

- **The deterministic checker** verifies that annotations trace to the seed. It never asks whether
  a *band label agrees with the curve beneath it*. It returned clean.
- **The text judges (axes 1–3)** are shown the prose, never the image. They cannot see it.

This retracts a claim made earlier the same day: *"the redraw introduced zero new gate failures —
that is the evidence the figure work did not disturb the text."* The gate was clean and the figure
was false. **A clean gate is evidence about the gate's questions, not about the figure.**

### 3.3 Other defects found, none of them mine

Corroborated by several raters independently, listed because they are now open work:

1. **"clip average" is the active-window mean, on every time-series figure.** On
   `computerfan-4029` the dashed line reads 22.9 rad/s while the trace is near zero for two-thirds
   of the clip; a student reading the mean off the graph gets ~4–5. The label is simply wrong —
   it is a turning-window average.
2. **The basic turns-vs-time graphs contradict their own printed captions.** `fan-4027` and
   `fan-4028` are visibly concave-**up** (a spin-up) under a caption reading "climbs steeply, then
   bends flatter".
3. **The tabulated `a_c` does not close under `a_c = ω²r`** using the table's own rows — on every
   clip, because `a_c` is a mean of squares and ω is a mean. Advanced hedges this correctly;
   **intermediate walks the student through the substitution and asserts a false result**. This is
   the same ambiguity that gave `grounding_accuracy` κ = −0.04 in the text axes.
4. **Fitted-circle offsets.** `roundabout-4046`'s centre marker sits ~21% of a radius off the
   fitted circle's centre, so the radius arrow overshoots the path; `turntable-1` and `turntable-2`
   show the traced points 9–13% outside the dashed fit. The basic passages claim "every point
   falls on one circle", which the images contradict. On `turntable-3` the scatter runs ±30% off
   with a dense knot — an independent visual signature of the tracker jumps.
5. **Render bugs**: `annotated_table.png` titles clipped mid-word on several clips, header row not
   spanning the label column; the basic angle plot's takeaway box overlapping the axes and
   clipping at the canvas edge; trajectory y-axis silently inverted (image coordinates) under a
   label reading "distance up/down (m)"; `ac_t.png` writing `m/s^2` in ASCII where every other
   figure uses `m/s²`.

---

## 4. A pipeline hazard this exposed, worth more than the finding

**Every workspace carries its own frozen copy of `analysis/`**, and re-rendering from inside a
workspace picks that copy up (the CWD leads `sys.path`) — *not* `workspace_lib/`. Editing
`workspace_lib/analysis/render/figures.py` and re-rendering appeared to succeed and silently
changed nothing; the figure came back byte-for-byte identical with the false label still on it.

**To make a renderer change reach a workspace you must sync the frozen copy first:**

```bash
for d in workspaces/job_*/; do cp workspace_lib/analysis/render/figures.py "$d/analysis/render/figures.py"; done
```

Verify a change actually landed by diffing the two copies, not by re-running and hoping. This is
the same trap recorded for `analysis/` hints in the tracking notes, in a new place.

---

## 5. Reproducing

```bash
cd agent-backend
python3 tools/export_multimodal_prompts.py --workspaces 'workspaces/job_*' --out /tmp/mm_prompts
#   -> 21 prompts; basic 7 criteria / 3 images, int+adv 11 criteria / 4-5 images
#   agents score them blind, one clip each, writing <clip>.json into /tmp/judge_mm
python3 tools/build_multimodal_table.py --prompts /tmp/mm_prompts --scores /tmp/judge_mm \
    --out-md material_work/_eval/multimodal_axis4_<date>.md --out-tex ../presentation/axis4_table.tex
```

---

## 6. Bottom line

Axis 4 is worth having. On its first run against current figures it caught a false statement
printed on essentially every time-series plot in the corpus — one that the deterministic checker
passed and that no text judge could see — and it independently confirmed that the annotated frames,
the project's own contribution, are the strongest artifact in the evaluation.

It also says something the text axes cannot: **the figures do not get better by tier.** The
difficulty ladder is carried by the prose, and Axis 4 should not be cited as evidence for it.
