# Processing hints — base-template-flick

> Read before Step 2. Clip-specific; takes precedence over your defaults.
> Evidence: `docs/tracking-data-quality-2026-07-15.md`.

**Scene.** A red phone flicked on a black circular base, filmed nearly top-down. At rest,
then one flick (~t = 2.1 s), then a coast-down to a stop. This is the golden template
(job `9ed918d0`).

> **DUPLICATE:** this template is `basetemplate-turntable-3`'s video, re-skinned with a
> narrative `scene_context`. Cached tracks are byte-identical (350/350 points). It ships **no
> video**, so a cache HIT means any video uploaded here silently reports turntable-3's
> trajectory. Hub offset **0.7 px** ⇒ no perspective; do NOT rectify.

## This clip is close to the best case — do not "fix" it

| signal | value | reading |
|---|---|---|
| coverage | 100% | no dropouts |
| steps > 100 px | 0 | no identity switches |
| bbox area CV | 0.24 | stable blob |
| orbit axis ratio | 1.005 (~5.6° tilt) | **essentially face-on** |
| ω phase-locked fraction | 0.26 | no projection artifact |
| constant-α fit R² | 0.9999 | the coast-down is almost perfectly linear |

**Do not apply vanishing-line rectification here.** At an axis ratio of 1.005 the orbit is
already a circle to within the noise; the conic's axes are ill-conditioned, the polar line is
numerically unstable, and rectifying would inject error rather than remove it. Rectification
is for the obliquely-filmed clips (see `base-template-roundabout-4046/hints.md`). Near
face-on, leave the geometry alone.

This is *why* this clip looks good, and it is the honest lesson to draw from it: it was filmed
top-down. The data quality was decided at capture, not in post.

## The residual jaggedness here is detector noise, and it is small

r(t) wobbles ~±1% (4.2 px RMS on a 398 px radius) — broadband, not phase-locked. That is SAM3's
mask centroid breathing frame to frame, and it is the noise floor, not an artifact with a fix.

One honest artifact of it: ω dips to about **−0.4 rad/s at t ≈ 1.75 s, while the phone is still
at rest.** That is centroid jitter differentiated, not motion. It is why `active` detection
matters — do not narrate it, and do not let the material describe pre-flick motion.

## What the material may say

Per-instant ω is reliable — narrate the timeline normally. The physics: at rest, one flick to a
peak of ~9.4 rad/s, then a clean constant-α coast-down (α ≈ −4.18 rad/s², R² = 0.9999) to rest.
`impulsive_start` is set, so the peak is the real peak — not a parabola's extrapolated
intercept.
