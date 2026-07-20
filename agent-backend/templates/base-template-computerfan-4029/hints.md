# Processing hints — base-template-computerfan-4029

> Read before Step 2. Clip-specific; takes precedence over your defaults.
> Evidence: `docs/tracking-data-quality-2026-07-15.md` §3.8.

**Scene.** A red marker on a PC case-fan blade, spun by hand in bursts. `tracking_mode: color`,
HSV wraps red (168→12). Verified frame-by-frame on 2026-07-15.

## This clip is CLEAN. Do not "fix" it.

Its data is already right — it is one of four phenomena in the corpus we can vouch for.

| signal | value | reading |
|---|---|---|
| hub offset | **8.5 px** | no perspective — do NOT rectify |
| axis ratio / tilt | 1.021 / 11.8° | tilted, but an *affine* view |
| ripple CV | **0.088** | lowest of any real clip |
| phase-lock | **0.075** | no artifact whatsoever |
| largest spin burst | 1.53 s, **6.7 revolutions** | ample to diagnose |

**Do NOT apply projective rectification.** At an 8.5 px hub offset the vanishing line is near
infinity and the homography is near-identity; rectifying would inject numerical error rather
than remove anything. Rectification is for `roundabout-4046` (offset 85.6 px) and nothing else
in this corpus.

## Two traps this clip sets — both of which we fell into

**1. The 13% "missing" coverage is honest.** It is a single contiguous run (`f717–824`,
t = 11.96–13.74 s) where the shot pans off the fan entirely. There is no fan to detect. Do not
retry tracking to "recover" it, and do not treat the clip as low-coverage: restrict to
t < 11.9 s and coverage is ~100%.

**2. The "153 jumps over 100 px" are REAL MOTION, not teleports.** The fan is spun in bursts;
the per-second median step swings from 0.1 px (at rest) to 133 px (4.08 rev/s). At r = 312 px,
4 rev/s *is* 131 px/frame.

> **A fixed pixel step threshold is meaningless.** Judge the step in ANGLE: `ω·r/fps`. Below
> ~90°/frame the point is unambiguous; above 180° the spin is aliased and unrecoverable at that
> fps. This clip peaks at **55°/frame** — nowhere near either limit. A 100 px gate falsely
> condemned this clip, which turned out to be the cleanest in the corpus.

## The motion is bursty — that matters downstream

Six separate spin bursts (1.53 s, 1.2 s, 0.67 s, 0.4 s, 0.4 s, 0.05 s) separated by rest. Do not
average ω over the whole clip: the mean would be diluted by the stationary stretches and mean
nothing. Restrict every summary statistic to the active window (the pipeline's active detection
already does this). Mean |ω| within the largest burst is **27.89 rad/s**.

If you compute a ripple or phase-lock over the whole clip you will divide by a near-zero mean ω
and manufacture an artifact that is not there.
