# Processing hints — basetemplate-turntable-1

> Read before Step 2. Clip-specific; takes precedence over your defaults.
> Evidence: `docs/tracking-data-quality-2026-07-15.md` §3.3–3.4, §4.1.

**Scene.** A red phone on a black turntable, filmed from above. Verified frame-by-frame
2026-07-15: the tracker locks onto the phone in every sampled frame.

## This clip's data is already right. Do not correct it.

The turntable is one of four phenomena in the corpus we can vouch for, and it needed **no**
fix.

**Do NOT apply projective rectification.** The platter's bright metal spindle was detected in
100% of frames and sits **0.7–8.8 px** from the centre of the elliptical path (per clip: t-1
8.8 px, t-2 3.4 px, t-3 0.7 px). Those two points coincide only under an affine view — so a
near-zero offset means the projection **is** affine, the vanishing line lies near infinity, and
the recovered homography is near-identity. There is nothing to undo, and rectifying an
ill-conditioned near-circular orbit injects error. Rectification is for `roundabout-4046`
(offset 85.6 px) and nothing else in this corpus.

## The clip IS tilted — and that is not a problem

Tilt is 3.8°–14.9° depending on the clip, so the orbit images as an ellipse. **Tilt only means
the orbit is an ellipse; it does not mean the projection is perspective.** θ read from a
correctly-centred ellipse is already right. Do not treat a visible ellipse as evidence that
something needs fixing.

## The residual ripple is noise, not an artifact

turntable-1: ripple CV 0.159 but **phase-lock 0.147** — the variation is broadband detector
noise, not locked to orbital phase, so no geometric fix applies. An earlier analysis classified
this clip as "perspective" from its 1/rev-to-2/rev ratio alone; that was wrong. **A harmonic
ratio computed on noise is still a ratio** — always check phase-lock before attributing a ripple
to geometry.

## Too short to fingerprint (t-2, t-3)

Active motion is only ~1.4 rev (t-2) and ~1.8 rev (t-3), below the 2-revolution floor needed to
separate the 1/rev and 2/rev signatures. Report the fingerprint as **undecidable**, not clean —
but note the hub offset is a *static* measurement needing no revolutions, and it already rules
out perspective here.

## Duplicate warning

`base-template-flick` is **this same video** (turntable-3): byte-identical cached tracks
(350/350 points) and the same `rotation_center_frac [0.5028, 0.4573]`. `flick` is a
re-skin with a narrative `scene_context`. The reference golden run (`9ed918d0`) is
turntable-3's data.
