# Processing hints — base-template-roundabout-4046

> Read before Step 2. These are clip-specific and take precedence over your defaults.
> Validated against this clip's cached track on 2026-07-15; evidence and numbers in
> `docs/tracking-data-quality-2026-07-15.md`.

**Scene.** A yellow 3-spoke wheel on a red arm, one black knob on the rim, hand-spun and
coasting down. Handheld, filmed looking down at the wheel from above and in front.

**Detection is already good — do not "improve" it.** 100% coverage, zero frame-to-frame jumps
over 100 px, bbox area CV 0.23. The knob is the only black object near the rim and it sits
against bright paving. Leave `tracking_mode: object` and the prompt `black ball` alone.

> **This clip is the ONLY one in the corpus with real perspective** (hub offset 85.6 px; every
> other clip is 0.7–8.8 px). Do not generalise anything below to other templates — applying it
> to a near-affine clip injects error. See `docs/tracking-data-quality-2026-07-15.md` §4.1.

## The defect: perspective, not tilt

ω(t) from this clip swings between 5.5 and 12 rad/s, ~18 times in 15 s. **The wheel does not
do that.** It decelerates smoothly from 9.4 to 6.5 rad/s. The swing is a projection artifact
and it is 94% phase-locked to orbital phase.

Do not filter it. It is deterministic — it repeats identically every revolution, so any
low-pass that removes it also destroys the real deceleration you are trying to report.

The instinct "filmed at an angle → the path is an ellipse → squash it back" is **half right and
not sufficient here**. Measured on this clip:

| | ripple CV | 1/rev amp | 2/rev amp |
|---|---|---|---|
| as-is (circle fit) | 0.166 | 1.725 | 0.843 |
| affine ellipse-stretch only | 0.146 | — | — |
| **vanishing-line rectified** | **0.015** | **0.054** | **0.069** |

The orbit *is* an ellipse (axis ratio 1.124). But the dominant ripple is **1 per revolution**,
and pure tilt can only produce **2** per revolution. The 1/rev term is the near side of the
orbit being magnified relative to the far side — true perspective. An affine stretch removes
only the 2/rev half, which is the smaller half: it buys 12% and leaves the artifact.

## The fix: rectify with the vanishing line (no calibration)

For a circle, the polar line of the circle's centre w.r.t. the circle is that plane's line at
infinity. Both survive projection, so the imaged hub + the fitted orbit conic give you the
vanishing line directly — no focal length, no intrinsics.

```python
C = fit_conic(orbit_x, orbit_y)       # image of the orbit (an ellipse)
h = (hub_x, hub_y, 1)                 # the IMAGED AXLE — see the warning below
l = C @ h                             # vanishing line of the wheel's plane
H = [[1,0,0],[0,1,0],[l0,l1,l2]]      # maps l to infinity -> affine image
                                      # then ellipse -> circle by the axis stretch
theta = atan2(...)                    # in the metric-rectified plane
```

Working prototype, end to end, on this exact clip: `docs/figures/rectify_prototype.py`.
Before/after figure: `docs/figures/rectify-4046-before-after.png`.

### The one way to get this wrong

**The hub is NOT the centre of the ellipse you see.** On this clip:

- centre of the elliptical path: **(530.0, 912.3)**
- the actual red axle boss: **(532.3, 997.9)** — **85.6 px lower**
- `sidecar.rotation_center_frac` → (529.5, 909.7) — i.e. **the ellipse centre, 2.6 px off it**

Those two points coincide only under affine viewing. Their offset *is* the perspective and it
is the entire input to the method. **Pass the ellipse centre as `h` and the polar comes back as
the line at infinity, the homography is the identity, and you have silently done nothing.**

So `rotation_center_frac` is unusable as `h` here — a human asked to "mark the centre" taps the
middle of the ring they see, which is exactly the point that carries no information. Detect the
axle instead. It works reliably on this clip: the dark-red boss, HSV ≈ (0–10 / 170–179, 120–255,
40–160), area 400–40000, roundish (aspect 0.55–1.8), nearest the orbit centre → **100% of
frames**.

## Camera drift: remove it, but it is not the ripple

Handheld, so the wheel wanders — the hub moves 53 × 41 px over the clip. Track the axle per
frame and reference the orbit to it (smooth the hub first, ~2 s window, so you subtract drift
and not detector jitter).

But do not expect this to fix ω: drift is uncorrelated with orbital phase, so it cannot make a
phase-locked ripple. Measured here it moved ripple CV 0.166 → 0.164. Do it because it is nearly
free and because it hands you `h` for the rectification — not as a remedy.

## Prove it worked — two checks, both required

"It looks smoother" is not evidence; smoothing does that. Report both of these:

- **Mean ω must be preserved.** Rectification redistributes angle *within* a revolution and
  cannot change how many revolutions happened. This clip: 7.799 → 7.800 rad/s. If your mean
  moves, you are fitting away real signal — stop.
- **Circularity must improve without having been optimized.** `l` comes from the hub, never
  from ω or from the radial residual, so the residual falling (5.20% → 1.68% here) is a free,
  independent confirmation.

A rectification derived from the kinematics it then "improves" is circular. Say which of your
inputs came from the geometry and which from the motion.

## What the material may say once rectified

The honest physics: a smooth coast-down, 9.4 → 6.5 rad/s over 15 s, orbit radius ~0.06 m
reference. Per-instant ω is now reliable — narrate the timeline normally. Do **not** carry over
the `per_instant_omega_unreliable` suppression that the unrectified track triggers; that flag
exists to hide this artifact, and you have removed it rather than hidden it.
