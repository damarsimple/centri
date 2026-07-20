# Tracking & geometry data quality — measured, 2026-07-15

Why the generated curves are jagged where P-MAGIC's are a clean line, measured per template
off the cached tracks and the real frames. This is the evidence base the per-template
`templates/base-template-*/hints.md` files cite. **Everything here was measured or tested; two
of the starting hypotheses did not survive and are recorded as such.**

> **Paper-style writeup (updated 2026-07-18):** `technical-report/centri-video-data-quality.tex`
> (29 pp, compiles clean). Now carries a **per-phenomenon common structure** — Scene → Context
> handed to the agent (sidecar + hints) → How it is calculated (technique + formulas, each on its
> own line) → an annotated **data-point frame** → Found → Verdict (GOLD/SILVER tier) — with a
> **formula-on-frame** annotated figure for every phenomenon. Committed 2026-07-20 (`e0a20d0`).

## Per-template signature

Measured off `analysis_output/data/api_cache.json` (and the video for the visual checks):

| template (mode) | coverage | step p99 | jumps >100px | bbox area CV | dominant defect |
|---|---|---|---|---|---|
| roundabout-4048 `black knob` (color) | 100%* | 241 px | 137 | 2.08 | **detector identity collapse — archived** |
| fan-doll `fan blade` (object) | 100% | — | 93 | 0.61 | **tracked the window louvres** |
| computerfan-4029 `red marker` (color) | 86.9%† | 269 px | 0‡ | 0.30 | **CLEAN — our gate accused it falsely** |
| roundabout-4046 `black ball` (object) | 100% | 90 px | 0 | 0.23 | clean track, **perspective artifact** |
| flick/turntable-3 `red phone` (object) | 100% | 65 px | 0 | 0.24 | clean; near face-on |
| bicycle `red object` (object) | 100% | 90 px | 0 | 0.18 | clean track, **unexplained** ripple |
| fan-4027/4028 `fan blade` (frequency) | 100% | 17 px | 0 | **0.00** | orbit **synthesized**, not measured |

† 4029's missing 13% is one contiguous run where the shot pans off the fan. ‡ Its "153 jumps"
were real 4 rev/s motion (131 px/frame at r=312) mis-flagged by a fixed 100 px threshold; the
angular step peaks at 55°/frame, far below the 180° aliasing limit. **A pixel step threshold is
meaningless — use `ω·r/fps`.**

\* 4048's `track_coverage: 1.0` is reported while ~38% of frames are wrong. **Coverage is not
correctness** — it measures whether the tracker returned a point, not whether the point is the
object.

## GOLDEN SET: 4 phenomena (2026-07-15)

"Golden" = we know the data is right.

| phenomenon | status | basis |
|---|---|---|
| **roundabout-4046** | golden **after** rectification | hub offset 85.6 px, phase-lock 0.94/18.6 rev; fix validated |
| **turntable** (1/2/3) | golden **as-is** | hub offsets 0.7–8.8 px ⇒ perspective impossible; t-1 lock 0.15 = noise |
| **computerfan-4029** | golden **as-is** | hub 99.4%, offset 8.5 px, ripCV 0.088, lock 0.075 |
| **ceiling fan** (4027+4028) | **SILVER** (rate+scale gold, orbit synthesized) | scale MEASURED (ruler 07-16): hub→tip 63.5 cm → px_per_m 559; v/a_c at blade tip; ω(t) sub-bin-smoothed (see below) |
| bicycle | **open** | phase-locked 0.72, not perspective (4.9 px), not occlusion (R²=0.07), gravity wrong phase; scale also estimated (12% cross-check fail) |
| fan-doll | no | cream toy on cream ceiling; green-sprout colour tracking reaches only 51.7% |
| roundabout-4048 | no | information absent from pixels; archived |

**Only one of the four needed the DATA corrected** (4046). Three were won by fixing our own
diagnostics/config: 4029 (angular step bound), turntables (hub offset — static, needs no
revolutions), fans (track the real marker, not a synthesized orbit). **v/a_c for the fans wait on
the marker's real size in metres.**

**RETRACTED: "perspective is systematic."** It is not — see below. Only 4046 has it.

## THE RULE: perspective strength = hub offset, NOT tilt

| clip | tilt | hub offset | phase-lock | rectified |
|---|---|---|---|---|
| roundabout-4046 | 27.1° | **85.6 px** | 0.94 | 0.166 → **0.015** ✓ |
| turntable-1 | 14.9° | 8.8 px | 0.15 | 0.159 → 0.162 (no change) |
| bicycle | 15.0° | 4.9 px | 0.72 | 0.141 → 0.148 (no help) |
| turntable-2 | 11.3° | 3.4 px | — | no perspective |
| turntable-3/flick | 3.8° | **0.7 px** | — | no perspective |

An order-of-magnitude separation with 4046 alone on one side. All are tilted 15–27°: **tilt only
says the orbit *images* as an ellipse; θ from a correctly-centred affine ellipse is already
right.** The offset predicted both nulls in advance. The earlier claim came from a classifier
that read the A1/A2 ratio **without checking phase-lock** — a ratio computed on noise is still a
ratio. **Phase-lock proves orbit-synchrony, not projection** (occlusion, extended-object
centroids and periodic lighting all mimic it); only the hub offset discriminates.

## Tracker provenance: the golden set spans BOTH backends — but caches don't record which

| phenomenon | tracker | cache `method` |
|---|---|---|
| roundabout-4046 | SAM3 | `sam3_object` |
| turntable 1/2/3 | SAM3 | (no cache; fetched fresh 07-15) |
| computerfan-4029 | **colour** (local CPU) | `color` |
| fan-4027/4028 | **neither** | `frequency_synth_windowed` — confirms the orbit is synthesized |
| roundabout-4048 | colour | `color` |

The findings are **not backend-specific**: 4046's perspective artifact came through SAM3, 4029's
clean data through the colour tracker, and both were judged by identical criteria. The hub
offset, harmonic fingerprint and angular step bound all operate on the **trajectory**, not the
tracker.

**HYGIENE GAP — a cache does not record what produced it.** The remote `/track` API returns
`status/request_id/video_id/video_info/trajectories` and **no `method` field**; `method` and
`track_coverage` are stamped on downstream, inconsistently. Three shapes exist in the corpus:

```
4046 :  status, request_id, video_id, video_info, track_coverage, method=sam3_object
flick:  video_file, trajectories, video_info, track_coverage      <- NO method, NO request_id
fresh:  status, request_id, video_id, video_info, trajectories    <- NO method, NO coverage
```

This is how the `flick` = `turntable-3` duplicate stayed invisible: flick's cache carries no
provenance at all. **Recommendation: stamp `method`, source video hash, and tracker version into
every cache at write time.**

**Aside — SAM3 was deterministic here.** A fresh SAM3 fetch of turntable-3 came back
**byte-identical** to flick's cache (350/350 points, both objects, exact float equality), which
is how flick's provenance was identified. The orchestrator's hard rules assume SAM3 is
non-deterministic and wrap it in a bounded-retry loop; that premise did not hold on this clip.
One clip is not a general claim, but it is worth checking.

## Backend-specific failure, one underlying rule

| backend | fails by | example |
|---|---|---|
| SAM3 (text-conditioned) | **semantic / shape** collision | `"fan blade"` → the window's louvre slats |
| colour (HSV) | **hue / value** collision | `"black knob"` → foliage; cream toy → cream ceiling |

Both are the same rule — *the target's defining feature is shared with the background* — with
only the definition of "feature" changing. `fan-doll` fails on **both** backends because the toy
is semantically hard *and* cream-on-cream.

## `frequency` mode FABRICATES the ends of the curve — the fans are recoverable (07-15, Damar's call)

Damar: *"seems using frequency synth windowed is not good in the first place, i place a light red
marker on one of fan blade."* Correct on both counts. Figure:
`docs/figures/fig-fan4027-measured-vs-synth.png`.

**The `frequency` choice was never justified for these clips.** The NOTES give the reason as
*"SAM3 aliases 5 identical blades"* — an **identity** problem, not a speed one. A unique red
marker solves identity outright. And there was never an aliasing risk: at ω≈4 rad/s (4027) the
marker moves ~17 px/frame = **8°/frame**; blade-pass is 3.2 Hz against a 30 Hz Nyquist. The NOTES
even record that the marker *was* colour-tracked to obtain the geometry (orbit CV 0.05) — and the
trajectory was synthesized anyway.

**What the synth gets wrong.** It has a **floor at 1.0 rad/s**: below the minimum detectable
blade-pass frequency it emits 1.0 rad/s regardless of truth.

| | fan-4027 | fan-4028 |
|---|---|---|
| measured \|ω\|, first 2 s | **0.002** rad/s (at rest) | **0.006** rad/s (at rest) |
| measured \|ω\|, last 2 s | **0.070** rad/s (at rest) | **0.132** rad/s (at rest) |
| **synth, both ends** | **1.004 rad/s** | **1.004 rad/s** |

**The synth claims the fan never stops.** 4027's own NOTES say it *"coasts DOWN to rest by
~t=60 s"*; the shipped curve holds 1.0 rad/s to t=77 s. The synth is also a **staircase** (one ω
per FFT window) where the motion is smooth, draws a **perfect circle** (axis ratio exactly 1.000)
where the real orbit is an ellipse (1.042), and puts the radius at 255 px against a measured
279 px (**8% scale error**) with the centre 24 px off.

**Pedagogical consequence.** `material_hints.md` instructs: *"never [say] it 'comes to rest'
unless the data says it actually stopped in the clip."* With the synth the fan never stops, so
the material is forced to say *"still turning, only slower"* — **which is false**. The measured
marker lets it tell the truth.

**Measured red marker → both fans are SILVER** (rate + scale gold, orbit synthesized).

| | coverage | revs | ripple CV | phase-lock | verdict |
|---|---|---|---|---|---|
| fan-4027 | **100.0%** | 22.6 | 0.084 | 0.121 | clean, no artifact |
| fan-4028 | **99.4%** | 29.0 | **0.054** | 0.197 | clean — **lowest ripple in the corpus** |

Where the synth is in range the two agree (correlation **0.974**, mean ω within 7.7%), so the
fan's mid-range physics was right all along — only the ends are fabricated.

**A sticky-error bug, reproduced in our own tracker.** 4028 first gave 46.7% coverage, collapsing
to 0% from t=50 s — *not* motion blur (100% through the t=20 s peak). It was our predict-and-match
gate going **sticky**: once `prev` was wrong, every candidate was rejected forever. That is
literally the 4048 defect this report documents, re-committed. Adding re-acquisition after 0.4 s
of loss: **46.7% → 99.4%**. Verified there are **zero contiguous teleports** (worst consecutive
step 22°/frame at peak); the only large steps span detection gaps.

**RESOLVED 2026-07-16 — scale MEASURED (ruler).** Hub→blade-tip = **63.5 cm (25″)**, blade = 20″.
Blade tip = 355 px (sd 0.5) → **px_per_m = 559** (retires the provisional `physical_size: 0.6` =
425 guess). Sidecars 4027/4028 now `orbit_radius_px 355` / `physical_size 0.635`, so v and a_c are
reported **at the blade tip** — the student-natural maximum, and exact because ω is rigid-body
(same everywhere) and comes from the blade-pass FFT (not the marker): v_tip = ω·r_tip with both
inputs measured. Peaks: 4027 v≈2.68 m/s, a_c≈**11.3 m/s² (1.15 g)**; 4028 v≈7.36 m/s,
a_c≈**85.2 m/s² (8.69 g)**. The `tracking_mode: color` flip is NOT needed for v/a_c (the marker
orbits inboard at ~49 cm; the tip is the reported point). Verified via real `analysis.run` +
tests 33/33.

**ω(t) STAIRCASE fixed (07-16).** The synth's one-ω-per-window staircase was **FFT-bin
quantization** — Δf = 1/2.5 s on the blade-pass line ⇒ ω steps of 2π·Δf/n_blades ≈ 0.5 rad/s.
A pure method artifact (only `frequency` mode shows it; per-frame 4029/flick come out smooth).
Fix = sub-bin parabolic peak interpolation (`freq_track._peak_hz_parabolic`) → smooth, physical
ω(t). Figures: `docs/figures/{omega_method_compare,ac_t_fans}.png`. A staircase reads to a student
as "constant speed, then jumps" — false; the fan accelerates smoothly.

The per-frame **orbit remains synthesized** (no resolvable point on a blurred identical-blade
rotor) — hence **SILVER, not GOLD**: teach ω/T/f/v/a_c freely, but present the orbit as a model,
never as measured data.

## bicycle: a scale cross-check that FAILS (07-15, Damar's idea)

Damar proposed using the phone (a known-size object) as the scale reference. Two clarifications
and one real finding.

**Scale is NOT why bicycle isn't golden.** ω, T and f are **scale-free** (pure angle/time;
`px_per_m` never enters). Bicycle fails on its **ω ripple** (phase-lock 0.72, cause unknown). A
perfect scale leaves that ripple byte-for-byte identical. Scale only affects v = ωr and a_c = ω²r.

**But bicycle's sidecar has NO `physical_size` at all** — only `label: "rear bicycle tire"` and a
bbox centre. Per the data contract, absent ⇒ **the agent estimates it**. So bicycle's metres are
currently *guessed*, and its v/a_c are untrustworthy independently of the ripple.

**The cross-check fails by ~12%.** Using the phone's oriented box (rotation-invariant; long side
123.9 px, CV 0.021 — better than the axis-aligned bbox's 0.034) against the tracked tire
(outer diameter 484 px in image):

| assumed phone body length | → px/m | → derived tire outer diameter |
|---|---|---|
| 140 mm (the 5.5″ **screen diagonal** — wrong dimension) | 885 | 54.7 cm |
| **150 mm (typical 5.5″ body)** | **826** | **58.6 cm** |
| 158 mm | 784 | 61.7 cm |

A real wheel is **66–70 cm** outer (26″ MTB ≈ 66, 700c ≈ 68). Inverting: for a standard 66 cm
wheel the phone body would have to be **169 mm** — a large phone, not a 5.5″ one.

**Two independent references disagree by 12% ⇒ one is wrong.** Prime suspect: **the phone is
threaded through the spokes, so the spokes occlude it** — the mask covers only the unobstructed
part and the obox is systematically short. Note this is independent evidence that the phone's
mask is not clean, which is suggestive for the unexplained ripple (though the area-vs-phase
occlusion test came back R² = 0.07, so it is not confirmation).

**Trap:** *"5.5 inch" is the screen diagonal, not a physical edge.* The obox long side measures the
phone's **body length**. Confusing them is a ~7% scale error straight into v and a_c.

**To settle it:** measure the phone's body length with a ruler and confirm the wheel size. Agree ⇒
scale validated. Still disagree ⇒ the mask is clipped and bicycle has a second, separate defect.

## The headline result: perspective rectification on 4046

`docs/figures/rectify-4046-before-after.png` — prototype: `docs/figures/rectify_prototype.py`.

| metric | baseline | + drift removed | + projective rectified |
|---|---|---|---|
| ripple CV | 0.166 | 0.164 | **0.015** |
| 1/rev amplitude A1 | 1.725 | 1.727 | **0.054** |
| 2/rev amplitude A2 | 0.843 | 0.844 | **0.069** |
| phase-lock fraction | 0.942 | 0.976 | **0.304** |
| orbit radial residual | 5.20% | — | **1.68%** |
| mean \|ω\| | 7.799 | 7.799 | **7.800** |

The baseline is deliberately generous: the *best least-squares circle*, not the sidecar mark,
plus the pipeline's exact savgol+median smoothing. The gain is geometry, not a nobbled
baseline.

**The pedagogical stake.** Unrectified, ω(t) swings 5.5→12 rad/s ~18 times in 15 s, telling a
student the wheel repeatedly speeds up and slows down. It does not: it coasts smoothly from 9.4
to 6.5 rad/s. The current pipeline *detects* this artifact (`quality_signals.py`) and responds
by **forbidding the material from mentioning ω(t)** — suppressing a symptom it could have
removed.

## Hypothesis 1 (rejected): "oblique tilt → ellipse → squash it back"

The orbit **is** an ellipse (axis ratio 1.124). The affine fix — fit the ellipse, stretch the
minor axis to the major — gives ripple CV 0.166 → 0.146. **12%. Effectively nothing.**

Simulating each candidate cause against a known-uniform spin gives each a fingerprint:

| cause (simulated) | A1/A2 |
|---|---|
| affine tilt 27° | 0.01 — pure **2**/rev |
| perspective tilt 27° | 1.40 — mixed |
| wrong centre (d = 20…92 px) | 30–56 — pure **1**/rev |
| **real 4046** | **2.43 — mixed** |

Pure tilt can only make a **2**/rev ripple; 4046's dominant term is **1**/rev, twice the size of
its 2/rev term. Confirmed independently on the radius: r(t)'s 2/rev amplitude is 26.4 px, which
matches the fitted ellipse's (A−B)/2 = 26.9 px exactly, while its 1/rev amplitude is 2.8 px —
so **the centre is right** and the 1/rev in ω is not a centring error. It is true perspective:
the near side of the orbit magnified relative to the far side. Affine rectification is
structurally incapable of removing it.

## Hypothesis 2 (real but minor): camera drift

Handheld — the hub wanders 53 × 41 px over 15 s. But removing it moved ripple CV 0.166 → 0.164,
because drift is uncorrelated with orbital phase and therefore **cannot** produce a phase-locked
ripple. Worth removing (it is nearly free, and it hands you `h`), but not a remedy.

## The method: vanishing-line rectification, uncalibrated

For a circle, the polar line of the circle's centre w.r.t. the circle is that plane's line at
infinity. Both survive projection, so the imaged hub + the fitted orbit conic give the vanishing
line — no focal length, no intrinsics, no EXIF.

```
C = fit_conic(orbit)   #   image of the orbit (ellipse)
h = imaged axle        #   NOT the ellipse centre
l = C @ h              #   vanishing line
H = [[1,0,0],[0,1,0],l]#   -> affine image; then ellipse->circle axis stretch
```

**The trap: the hub is not the ellipse centre.** On 4046 the axle sits **85.6 px below** the
centre of the elliptical path. They coincide only under affine viewing; their offset *is* the
perspective and is the method's entire input. Pass the ellipse centre and the polar returns the
line at infinity — the homography is the identity and you have silently done nothing.

`sidecar.rotation_center_frac` is therefore unusable as `h`: it sits 2.6 px from the ellipse
centre and 85.6 px from the real axle. A human asked to "mark the centre" taps the middle of the
ring they see — exactly the point carrying no information. Detecting the axle by colour worked
on **100%** of 4046's frames.

### Why this isn't circular reasoning

- **Mean ω is preserved** (7.799 → 7.800). Rectification redistributes angle within a revolution
  and cannot change the revolution count. A moving mean would mean signal was being fitted away.
- **Circularity improves without being optimized.** `l` is derived from the hub — never from ω,
  never from the radial residual — so the residual falling 5.20% → 1.68% is a free, independent
  confirmation.

## 4048: two defects stacked, and the clip is still unusable

`docs/figures/mask-4048-foliage.png`.

Real tracker bugs, worth fixing in `color_track.py` regardless:

1. **`area × mean_saturation` scoring is invalid for a dark target.** Black is defined by low
   *value*; its saturation is noise. The score degenerates to "biggest dark blob" — a tree, a
   shadow, the rig. Detected bbox widths range 8→658 px.
2. **`max_step: 250` where the knob moves 8.3 px/frame** (`ω·r/fps` = 1.1×450/60) — 30× too
   loose. Observed p99 step: 240.9 px, i.e. the tracker uses its full allowance to teleport.
   Because `prev` then follows the wrong blob, the error is **sticky**.

Fixing both (annulus gate + `max_step` 25 + predict-and-match scoring) → **137 jumps → 0**, bbox
area CV 2.08 → 0.68. And coverage 100% → **14%**, because:

**The clip is unrecoverable.** The target's defining feature is darkness and the background is
dark foliage that the orbit crosses for the top half of every revolution. ~33 competing dark
blobs per frame inside the rim annulus alone (74,463 over 2,220 frames). The information is not
in the pixels. The fix is capture-side: a coloured marker, or framing against ground/sky.

**Corollary:** any geometry number computed from a contaminated track is meaningless. 4048's
cached track yields "axis ratio 1.143 / 29° tilt" — that is a conic fitted to trees. This
document's first draft asserted that tilt as real; the frame-by-frame check killed it. Diagnose
detection before geometry.

## The fans' clean curves are synthesized

`freq_track` recovers ω from blade-pass frequency and then **generates** a circular orbit from
it. Hence axis ratio exactly 1.000, bbox area CV exactly 0.00, jitter 0.06 px — values no real
capture produces. Legitimate for ω/T/f; **not** a measured trajectory, and **not** the "good
data" exemplar to compare other clips against. The honest exemplar of a well-captured clip is
`flick` — and the reason it is clean is that it was filmed top-down (axis ratio 1.005). Its data
quality was decided at capture, not in post.

## What the frame-by-frame check caught that metrics did not

Two of this investigation's claims died on contact with the actual frames, both of them mine:

- "4048 is filmed at 29° tilt" — a conic fitted to a cloud of trees and shadows.
- "fit the ellipse and stretch it" — right about the ellipse, wrong about the remedy.

Both were plausible, quantitative, and wrong. Numbers computed from a track that was never
visually verified describe the tracker's failures, not the scene. **Overlay the cached points on
the real frames before trusting any statistic derived from them.**

## Open: where these fixes belong

Rectification is deterministic geometry — arguably it belongs in `geometry.py` (testable, same
every run) rather than being re-derived per job by a 35B agent. The per-clip judgments (mode,
params, "this clip is unusable") are genuinely agent work and belong in `hints.md`. Current
state: hints only. See `templates/base-template-*/hints.md`.
