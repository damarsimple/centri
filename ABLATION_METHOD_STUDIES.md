# Ablation & Method Studies — measuring rotation better

**Status: EXPLORATORY. Nothing here is wired into the pipeline.** This file is a parking place
for ideas about measuring rotation more accurately than the current
`box centre → atan2 → differentiate` chain, plus the evidence needed to judge them. It is
deliberately separate from `SESSION_CHECKPOINT.md` so an unpromising idea can be dropped without
leaving residue in the project.

Nothing graduates from this document into `workspace_lib/analysis/` without beating the measured
baseline below **on more than one clip**.

Opened 2026-07-21, after the first external validation of the pipeline against a phone's own
gyroscope.

---

## 0. The hard constraint every idea must respect

**The tracker cannot be replaced, only augmented.** Centri does not merely need $\omega(t)$ — it
needs to *draw on the video*: boxes, orbit overlays, the marker dot, the formula-on-frame figures
that the material depends on. A method that yields a superb rotation rate but no object location
breaks annotation, which is a headline contribution of the thesis, not a side feature.

So the shape of an acceptable improvement is:

> keep SAM3 (or LocateAnything) locating the object for annotation, and take the *rotation
> measurement* from something better than that box's centroid.

This rules out "replace tracking with phase correlation" as a wholesale swap. It does **not** rule
out phase correlation *inside the tracked box* — the tracker supplies the region, the correlation
supplies the precision. Hybrids are the target.

---

## 1. The baseline, measured

`turntable-3` now has ground truth: the phone was logging its own gyroscope while being filmed
(`IMG_3075.csv`, 490 samples at ~60 Hz, `gyro_gamma` = rotation about the screen normal = the
turntable axis). Video and sensor align by cross-correlation at **r = 0.955**, sensor leading video
by **1.205 s**.

| quantity | video | gyroscope | error |
|---|---|---|---|
| mean ω, active window | 5.660 rad/s | 5.667 | **0.1%** |
| peak ω | 9.781 | 9.820 | **0.4%** |
| peak a_c | 14.13 m/s² | 14.20 | **0.5%** |
| per-instant ω, RMS | — | — | **~4.0%** |
| spurious climb during coast-down | 0.428 rad/s | 0.000 | — |

**Time-averaged quantities are excellent. Per-instant is ~4%.** The "bump" is a ~5% wiggle, i.e.
it sits *inside* the per-instant error rather than on top of it.

`spurious climb` = the largest cumulative rise in ω during the pure coast-down (2.35–4.00 s).
Nothing drives the turntable there, so the true value is exactly 0. **This is the single best
scalar for scoring a candidate method** — it needs no ground truth at all, only the knowledge that
a coasting body cannot speed up.

---

## 2. Negative results — do not re-litigate these

Each was measured, not argued. Re-running them is waste.

| hypothesis | verdict | evidence |
|---|---|---|
| the tracker's box quality is the limit | **NO** | LocateAnything-3B, a structurally different detector, reproduces the same ripple (r = +0.81 on shared active frames) |
| the box *centroid* specifically is the limit | **NO** | box *orientation*, a different observable from the same box, scores the same (4.09% vs 4.69%) |
| a higher frame rate would fix it | **NO** | error is flat from 15 → 60 fps (0.53/0.68/0.67/0.69° within-segment) |
| the object leaving the frame is the cause | **NO** | it genuinely does, up to 27 px, exactly in the bad window — but clipped frames score 0.472° vs 0.512° for clean ones |
| the ripple is locked to viewing angle | **NOT DEMONSTRABLE** | surrogate test: no clip in the corpus beats its own null (p = 0.12–0.81) |
| the dropped frame explains the bump | **12% ONLY** | removing it leaves 88% of the bump |
| swapping the smoother fixes it | **PARTLY, AT A COST** | moving average removes 58% but doubles overall error (7.49% vs 4.02%) and blunts the real peak |

**What is left unexplained: about a third of the bump**, present in the measured positions, with no
identified cause. It joins `bicycle` in that bucket.

---

## 3. The evaluation protocol — the reason this document is worth keeping

Before the gyro log, method choices were argued from taste, and two of today's retractions came
from exactly that. Now any candidate can be **scored**:

1. compute ω(t) by the candidate method
2. align to the sensor by cross-correlation
3. report: **RMS vs gyro**, **spurious climb**, **peak preservation**, **mean preservation**
4. repeat on every clip that has a sensor log

A method is promising only if it improves *climb* **without** degrading *RMS* or blunting the real
peak. The moving-average smoother is the cautionary example: it looks like a win on the bump alone
and is a clear loss on the pair.

**Overfitting warning.** Every number above comes from **one clip**. Tuning a method against a
single ground-truth trace is precisely the mistake that produced this session's retractions.
**Nothing graduates on one clip.** The highest-value next input is not a new algorithm — it is
**sensor logs for turntable-1/2, roundabout-4046, and the fans.**

---

## 4. Candidates that keep the tracker

Ordered by expected value, best first.

### 4.1 Global trajectory fit instead of per-frame differentiation ★ most promising

Do not differentiate the data at all. Parameterise ω(t) directly — as a smoothing spline, or as a
physical friction model `dω/dt = −(a + bω)` — integrate it to θ(t), predict the object's position
in every frame, and minimise the residual against *all* observed positions simultaneously.

*Why it should help:* differentiation is the noise amplifier, and the current chain does it on
noisy per-frame angles. A global fit inverts the problem: it never differentiates the measurements,
only the model, which is smooth by construction. It is also far better conditioned — hundreds of
observations constraining a handful of parameters.

*Cost:* a nonlinear least-squares solve per clip. Milliseconds.
*Annotation:* untouched. The tracker still supplies boxes.
*Risk:* the model can absorb real features (see §5). Needs the residual gate.

### 4.2 Chord length instead of absolute angle

Use the frame-to-frame displacement: `|Δp| = 2r·sin(ωΔt/2)`.

*Why it should help:* displacement is a differential quantity, so a **constant** centroid offset
cancels exactly, and the rotation centre is not needed at all — removing one whole error source
(4046 lost 232 px to a centre-space bug). Our bias varies with angle so it will not fully cancel,
but partial cancellation is free.

*Cost:* trivial. *Annotation:* untouched. *Risk:* loses the sign of rotation; needs r.

### 4.3 Phase correlation *inside* the tracked box ★ the hybrid

The tracker supplies the ROI; rotation between consecutive frames is then measured by log-polar
transform + phase correlation (Fourier–Mellin) over the whole patch, not a derived point.

*Why it should help:* a centroid is one number, so a shape change moves it *systematically*. A
whole-patch correlation is many implicitly-averaged measurements, so some of the bias cancels
instead of accumulating. This is the mechanism, and it is not wishful — it is why correlation
methods beat centroiding in astrometry.

*Cost:* ~40 lines with OpenCV; one FFT per frame pair.
*Annotation:* **untouched — this is the point.** The tracker keeps doing its job.
*Risk:* the phone is specular and low-texture; correlation may be weak on it. Would likely work
better on the *turntable disc* (see 4.5) than on the phone.

### 4.4 Mask registration between consecutive frames

The object is rigid. Solve for the rotation that best aligns frame *k*'s mask to frame *k+1*'s,
rather than comparing two centroids.

*Why it should help:* uses the entire silhouette. Robust to the centroid drifting, because it never
computes one.
*Annotation:* untouched — needs the mask the tracker already produces.
*Risk:* fails exactly where the silhouette itself changes with angle, which is our suspected cause.
Might inherit the whole problem. **Cheap to test, so test before theorising.**

### 4.5 Track the turntable, not just the phone ★ cheapest real win

The disc rotates *with* the phone. Its surface carries scratches, moulding rings, and in these clips
**a steel ruler lying across it**. Every one of those is an independent estimate of the same ω, from
footage we already have.

*Why it should help:* independent measurements of one quantity. Their spread is an honest
uncertainty estimate — the first one this project would have that does not require a sensor log.
Disagreement localises the error to a particular object.

*Cost:* one extra tracked target per clip. *Annotation:* untouched, and arguably improved.
*Risk:* none obvious. **This is the highest value-per-effort item in the document.**

### 4.6 Sub-feature tracking within the object

Track something small and localisable *on* the phone — the camera bump, a screen corner, the
charging cable's entry point — instead of the whole slab. The tracker still boxes the phone for
annotation; precision comes from the sub-feature.

*Why it should help:* directly attacks the diagnosed problem. A small feature has far less
angle-dependent extent than a 450 px specular slab.
*Risk:* self-occlusion; the feature leaves view. Needs re-acquisition logic.

---

## 5. Constrained / model-based reconstruction ("authored authentic")

Damar's proposal, 2026-07-21: if the expected physics is known, impose it and produce a clean curve.

**Methods that exist:** isotonic regression (monotone), **unimodal regression** (one rise, one peak,
one fall — via isotonic-up/isotonic-down with a swept peak), physics-model fitting
(`dω/dt = −(a+bω)`; the gyro decay looks close to linear ⇒ dry-friction dominated), constrained
Kalman/RTS smoothing with `α ≤ 0`, monotone splines via QP.

**Measured against the current GOLD set** (residual = how far the data must move to obey "one rise,
one peak, one fall"):

| clip | residual | verdict |
|---|---|---|
| turntable-2 | 0.0% | already perfectly unimodal |
| fan-4028 | 0.0% | already perfectly unimodal |
| turntable-1 | 0.5% | safe |
| fan-4027 | 0.7% | safe |
| turntable-3 | 0.7% | safe |
| roundabout-4046 | 2.9% | safe — slow monotone decay + noise |
| **computerfan-4029** | **27.7%** | **would erase a real second spin-up** |

`computerfan-4029` was flicked **twice** (peak 46.5 rad/s at t=5.82, decays; then 37.2 at t=8.82,
decays). A unimodal constraint deletes the second cycle entirely.

### ⚠ The trap that makes this dangerous

**Isotonic regression preserves the mean exactly** — a mathematical property — and preserved the
peak on all seven clips. On computerfan, mean ω, peak ω and peak a_c would come out **identical to
four decimals** while an entire physical event vanished from the curve. **The current gates check
exactly those numbers and would pass it silently.**

### What makes it safe

- **Residual magnitude is a clean discriminator**: 0–2.9% where the constraint is right, 27.7% where
  it is wrong. An order of magnitude, like the hub-offset rule. Fit → measure residual → refuse
  above threshold.
- **Naive model selection does NOT work** — tried and failed. BIC picked k=2 cycles for four
  single-flick clips, because isotonic with enough segments interpolates the data and any complexity
  penalty is overwhelmed. Use the k=1 residual magnitude instead (computerfan SSE 7804 vs ≤11 for
  everything else — three orders of magnitude).
- **A runs test for residual *structure* is useless here**: it fired on all seven clips, because
  smoothed data has autocorrelated residuals by construction. Magnitude is the signal.
- **Overlay, never replace.** Show measured points *and* the fitted curve, labelled. Ordinary
  scientific practice; gives the clean line for teaching without anyone pretending a fit is an
  observation. Carry it as a **provenance field in the data**, not just in prose — the report already
  flags "a generated perfect circle presented to learners as an observation" as a live defect.

### Where the LLM belongs

**Proposes, never disposes.** The number of spin-up cycles is answerable deterministically from
ω(t) with a 10× margin — delegating it buys nothing and adds a failure mode. What an LLM *can*
contribute is what the curve cannot show: is this system **driven or coasting**? Did a hand enter
the frame? Is it even a rotation experiment? That is scene semantics.

The pipeline has been burned twice by unverifiable agent assertions (`coordinate_space` said
"display" when it was cropped → 232 px; `diameter_px` held a radius → every SI value halved). The
decisive difference here is that a regime declaration **is checkable** by the residual. That is what
makes it acceptable where those were not.

---

## 6. Wilder ideas

Recorded because they are cheap to write down and occasionally one of these is the answer.

1. **Sensor fusion as a first-class input.** When a clip ships with a sensor log, fuse it: the video
   supplies *where* (for annotation), the gyro supplies *how fast*. This is "authored authentic" in
   its most defensible form — two real measurements, neither invented. It would also make the
   accuracy claims externally validated by construction. *Probably the single most valuable idea
   here, and the least algorithmically interesting.*
2. **Learn the angle-dependent centroid correction.** With ground truth on a few clips, fit the
   centroid bias as a function of viewing angle and object identity, then apply it to clips without
   sensor logs. Directly attacks the diagnosed mechanism. Risk: may not transfer between objects.
3. **Motion blur as signal, not noise.** A blurred marker's streak length encodes instantaneous
   speed *within a single frame*. Published technique. Would give sub-frame velocity precisely where
   our tracking is worst — at peak speed.
4. **Rolling shutter as a free high-speed clock.** Each image row is exposed at a slightly different
   time, so one frame already contains sub-frame timing information. Exotic, real, and would sidestep
   the frame-rate ceiling entirely. Also: worth checking whether rolling shutter is *contributing*
   to the error (tested once, explained 0.1% with a physically impossible implied readout time —
   probably a dead end).
5. **Use the sensor log to calibrate the smoother, then discard it.** Tune window/polyorder against
   ground truth on the clips that have it, ship the tuned constant. Needs several clips or it is
   overfitting — the current best candidate (savgol `deriv=1`, w=25) is strictly better on both
   metrics (climb 0.266 vs 0.428, RMS 3.88% vs 4.02%) but is tuned on a sample of one.
6. **Uncertainty bands on every plot.** Not an accuracy improvement — an honesty improvement. Draw
   ±4% on ω and a_c so a 5% wiggle visibly reads as measurement error rather than physics. Cheap,
   and it dissolves the "bump" problem for a *learner* without touching the data.
7. **Two markers instead of one.** Gives orientation as well as position, and their separation is a
   rigid-body invariant — a free per-frame self-check. Any frame where the separation changes is a
   frame where the measurement is wrong.
8. **Deliberately film a calibration clip.** A turntable at a known constant RPM (a record player at
   33⅓!) filmed alongside the sensor. Gives absolute accuracy, not just consistency, and takes ten
   minutes.

---

## 7. What would make something graduate

An idea leaves this document when it:

1. beats the baseline on **spurious climb** without worsening **RMS** or blunting the real peak;
2. does so on **at least two clips with sensor logs**;
3. leaves annotation working;
4. carries a provenance field if it produces anything other than a direct measurement.

Until then, it stays here.

---

## 8. Open questions

- **The 12 ms step.** Fitting each half of turntable-3 separately drops box error from 2.13° to
  0.69°/0.24°, implying a ~12 ms timing discontinuity across the dropped frame. Could not be
  attributed: the sensor's own timestamp jitter (±4 ms/sample, ~28 ms accumulated) is larger than
  the step. A 200 Hz+ log, or a clip with a sharp sync event visible in both, would settle it.
- **The unexplained third of the bump.** Not the tracker, not the observable, not the frame rate,
  not frame-edge clipping, not angle-locked. Present in the measured positions.
- **Does any of this generalise past turntable-3?** Everything measured here comes from one clip.

## 9. Files

- Ground truth: `IMG_3075.csv` (paired with `job_turntable-3-rect/input_video.mp4`)
- Tracker ablation and cue sweep: `agent-backend/docs/la-ablation-2026-07-21/`
- Shipped dropped-frame guard: `workspace_lib/analysis/contract.py` (`duplicated_frame_indices`),
  tests in `tools/tests/test_dropped_frames.py`
- Scoring scripts used for the numbers above live in this session's scratchpad and should be moved
  here if any of this is pursued.
