# Processing hints — base-template-parkwheel-4091

> Read before Step 2. Clip-specific; takes precedence over your defaults.
> Evidence: `NOTES.md` in this directory, `docs/tracking-data-quality-2026-07-15.md` for the rules.

## PARKED — no validated tracking method. Not selectable; if it is ever moved back, report `failed`.

The footage is good. **Nothing we have follows the knob**, and three methods were tried on the
30 s cut and measured, not guessed:

| method | result |
|---|---|
| **SAM3 object** | **returns NOTHING.** Six cues on a 4 s probe — `ball`, `orange ball`, `handle`, `knob`, `orange knob`, `grip` — all empty. Same as the fan-doll clip. The knob is ~38 px across in a 1080×1920 frame. |
| **colour (`color_track`)** | locks onto the rig's own red parts. Unconstrained it reports **100% coverage while completely stationary** (the sunlit red base, 9000 px, and a yellow sign both outscore a 38 px knob under `area × mean_saturation`). Constrained by an annulus and a size ceiling the track becomes real — orbit radius 507 px, 4°/frame, no π jumps — but coverage falls to **11–52%**. |
| **frequency (`freq_track`)** | with the knob-pass band it returns a nearly **flat ω ≈ 3.1–3.3 rad/s**, which contradicts the visible coast-down and the independent measurement below. Not usable. |

**Do not process this clip with any of them.** A stationary 100%-coverage track is exactly the
"coverage ≠ correctness" failure the corpus already has one example of, and it would ship a
lesson about a wheel that never turns.

## What IS known about the motion (measured, method outside the pipeline)

The two knobs are 180° apart, i.e. a physical diameter, so the line joining their images passes
through the image of the axle whatever the viewing angle. Intersecting 205 such chords, and
reading the pair-axis angle mod π (immune to the 180° identity swap):

- **27.4 revolutions in 65 s** of source; ω **4.85 → 2.43 rad/s** over 0–45 s, then at rest.
- Hub **(547, 977) px**, orbit radius **510 px**, axis ratio 0.96 (tilt ≈ 16.5°).
- **HUB OFFSET ≈ 60–73 px ⇒ REAL PERSPECTIVE.** Same class as the roundabout clip (85.6 px);
  clips needing no correction sit at 0.7–8.8 px. Even with a working tracker, per-instant ω here
  carries a 1/rev projection ripple, so this clip is **OPEN**, never GOLD, until rectification
  exists.

## What would fix it, cheapest first

1. **Wrap one knob in coloured tape** — a flat, saturated colour that is not the rig's red
   (bright green works: the rig is red/silver/yellow). This fixes detection AND identity in one
   move, exactly as the red marker did for the ceiling fan and the computer fan.
2. **Fill the frame with the wheel** so the knob is more than ~38 px, which may also bring SAM3
   into play.
3. **Tape the rim diameter** — there is no object of known size in frame, so every SI value is
   provisional (ω, T, f are scale-free and fine).

Until (1), keep this template parked and report `failed` if it is submitted.
