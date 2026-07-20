# Processing hints — base-template-fan-4027

> Read before Step 2. Clip-specific; takes precedence over your defaults.
> Evidence: `docs/tracking-data-quality-2026-07-15.md`.

**Scene.** A 5-blade fan at speed. `tracking_mode: frequency` — `freq_track` measures
blade-pass frequency to recover ω, because the blades under-sample even at 60 fps.

## The orbit here is SYNTHESIZED. It is not a measurement.

`freq_track` recovers ω from blade-pass frequency and then **generates** a circular orbit from
it. The tell-tale signatures on this clip's cached track are values no real capture produces:

- orbit axis ratio **exactly 1.000**
- bbox area CV **exactly 0.00**
- centroid jitter **0.06 px** RMS

Consequences, all of which matter:

- **Never present the trajectory as measured.** The clean circle is drawn from the frequency,
  not observed. ω, T and f are legitimate — a per-frame *position* is not.
- **Never use this clip as the "good data" exemplar** that other clips are compared against.
  Its curves are clean because they are fabricated, not because the capture was good. The
  honest exemplar of a *well-captured* clip is `base-template-flick` (filmed top-down).
- **Do not rectify, stabilize, or de-noise it.** There is no projection artifact to remove from
  a synthesized circle; any geometry "fix" here is operating on your own construction.
- The pipeline flags this — keep the flag. It is the difference between a measurement and a
  reconstruction, and the material must not blur it.

## Calibration: pair a RADIUS with a RADIUS. Do not "correct" `diameter_px`.

The synthesized bbox side is deliberately **`orbit_radius_px` (355 px), not the orbit
diameter** — so the generic Step-5 sizing (median `(W+H)/2`) recovers 355 and pairs directly
with `reference_geometry.physical_size = 0.635 m`, the ruler-measured hub→blade-tip radius.

**px_per_m must come out 559** (`355 / 0.635`) and `r_fit_m` **0.635 m**.

The field is *named* `diameter_px` while it carries a radius, which invites a "fix": doubling
355 to 710 and leaving the metres at 0.635 gives px_per_m 1118 and **halves every SI value** —
`r` 0.317 m, `a_c` 1.83 instead of 3.66 m/s². Observed on a real run (`job_fan-4027-r2`).
Take the median bbox side as-is; change neither number.
