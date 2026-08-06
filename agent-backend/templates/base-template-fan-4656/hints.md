# Processing hints — base-template-fan-4656

> Read before Step 2. Clip-specific; takes precedence over your defaults.
> Evidence: `NOTES.md` in this directory (2026-08-06 tracking study).

**Scene.** A 5-blade ceiling fan with a **yellow card marker taped to one blade**, filmed from
below and to one side against a bright window wall. `tracking_mode: color` — `color_track`
follows the marker's HSV blob, so the trajectory is **measured per frame**, not reconstructed.

This clip **replaces `fan-4027` and `fan-4028`**, which ran in `frequency` mode and had no
tracked point at all. Everything those two could not support — a real orbit, a real per-frame
position, an honest rest band — this clip supports.

## The orbit here is MEASURED. Do not treat it like the old fan clips.

Verified over the full 13,781 frames (2026-08-06):

- **coverage 99.99%**, and **100% of detections lie on the orbit**
- **zero** steps above 8× the clip's median step — no tracker jumps
- **190.8 revolutions**, max |Δθ| per frame **34.3°** against a 180° Nyquist limit (5× margin)
- the `kinematics_from_frequency_synth` flag must **not** appear. If it does, the mode is wrong.

## Do NOT set `max_step` for this clip.

`color_track.track()` freezes its lock when no candidate falls within `max_step_px` of `prev`:
the frame is emitted as a miss, but `prev` is never updated or cleared. One over-step and the
marker is only re-acquired when it orbits back past the stale point — once per revolution.

Measured on this clip: **`max_step` 90 → 26.9% coverage. No `max_step` → 99.99%.**

The ROI disc plus `min_area` already does the rejecting here: nothing else inside 330 px of the
hub passes the yellow band. The wooden window frames and the second fan at the right edge are
outside the ROI. Leave `max_step` out of `tracking_config` until the sticky-lock bug is fixed.

## Calibration: pair the ORBIT with the ORBIT.

`physical_size = 0.44 m` is the **hub-centre → card-centre** distance, so
`reference.diameter_px` must be the orbit radius — specifically the **SEMI-MAJOR axis of the
fitted ellipse**, not the marker's bounding box and **not the median/circle-fit radius**.

**Set `reference.diameter_px = 260.0`. Then `px_per_m` = 591 and `r_fit_m` = 0.440.**
Both are hard checks — if either differs by more than ~1%, the wrong radius was used.

⚠ **This one number has already gone wrong twice, in opposite directions.** The orbit images as
an ellipse (semi-major 260 px, semi-minor 214, circle-fit median 245), so "the orbit radius" has
three candidate values, and two runs from a **byte-identical sidecar** picked differently — 260
and 245 — giving `px_per_m` 591 vs 558 and a **6% swing in the taught `a_c`**. The semi-major is
the right one because it is the direction foreshortening never shortened, and because
rectification pins the corrected orbit to exactly that radius: post-rectification
`r_fit_px` == 260, so pairing it with 0.44 m is the only self-consistent choice.

⚠ **Do not use 0.31.** That is the hand-measured distance to the card's **inner edge**, not its
centre; the card is 25 cm long and lies along the blade, so its centre is ~12.5 cm further out.
Using 0.31 gives `px_per_m` 839 — **40% too high**, which makes every SI length 29% too small.

Do **not** calibrate off the marker's bbox. Measured here, the marker's axis-aligned bbox has
CV 0.23 and its median `(W+H)/2` is 135 px, which at the orbit scale is 16 cm — a span that
matches neither of the card's real dimensions. The axis-aligned box is inflated by the marker's
own rotation; the rotation-invariant (`minAreaRect`) size is 139 × 95 px. Using the bbox would
reintroduce exactly the radius/diameter coin-flip that halved every SI value on `fan-4027`.

## The metre scale: RESOLVED to ±5%. Rate is GOLD; SI carries a ±5% band.

ω, T, f and every ratio are **scale-free and validated** (NOTES.md §3 — 0.03–0.99% against an
independent blade-pass measurement). SI lengths rest on `px_per_m ≈ 591`, good to about ±5%.

The geometry that fixes it, all cross-checked in pixels (NOTES.md §5):

- the card lies **along** the blade (long axis 4.2° off radial) and is 25 cm long;
- **the card's outer edge is the blade tip** — predicted 329.5 px, measured tip 319.3 px,
  agreeing to **3.2%**;
- so the card occupies the outer 25 cm of the blade, its inner edge at 31 cm and its centre
  at ~44 cm from the hub.

**Prediction worth checking with a tape: the blade tip should be ~54 cm from the hub centre.**
An early figure of 51 cm makes the 25 cm card measure 22.2 cm in the same frame; 61 cm makes it
26.6 cm. If a careful hub-axle-to-tip measurement lands well outside 52–56, re-open this section.

`px_per_m` is bounded by its two anchors at **556–615** — quote SI values with that ±5%, and keep
the scale-free quantities for any claim that has to be tight.

## Rectification MUST engage, via the affine branch.

The orbit is a clean ellipse: semi-axes **260.0 / 214.2 px**, axis ratio **0.824** → the fan is
about **34.5° off face-on**. Decentering is negligible — the residual is almost pure 2/rev
(19.3 px) with only 4.1 px at 1/rev — so this is a single clean tilt with nothing confounding it,
unlike `roundabout-4046`.

**Expect `orbit_rectified` in the flags and `rectification.reason = "affine_foreshortening"`.**
Radial residual should fall **7.3% → 3.4%**.

That branch did not exist before 2026-08-06: `rectify` gated only on hub offset (0.05 px here) and
never on axis ratio, so this clip was silently left as an ellipse — which is what made the orbit
radius ambiguous in the first place. A face-on-centred but tilted orbit needs no vanishing line,
only the ellipse's own conic, and `_metric_from_ellipse` preserves handedness so the rotation
direction cannot flip.

## What the clip contains

Five phases, all in one recording — spin-up from rest, a peak near 14 rad/s, a **speed-setting
change** down to a held ~6.2 rad/s, a coast-down, and **rest inside the recording**. That last
is rare in this corpus and makes the rest band real rather than an edge effect.

Approximate |ω| by segment (rad/s): `0 → 14 → 6.2 (held ~120 s) → 5.0 → 1.3 → 0`.

**The rest tail is a trap for the old method, and that is the point.** Over the final window the
marker track correctly reads **0.016 rad/s** while a blade-pass FFT on the same frames reports
**4.69 rad/s** — the frequency-mode floor inventing rotation from noise on a stationary fan.
