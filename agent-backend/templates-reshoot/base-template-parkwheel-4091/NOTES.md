# base-template-parkwheel-4091 — park exercise wheel ("大輪"), two orange knobs

Outdoor arm-exercise wheel on a post: a silver spoked wheel, roughly 1 m across, with **two
salmon-orange grip knobs on the rim, 180° apart**. Hand-spun once, then left to coast.
Source: `cases2/IMG_4091.MOV` (65 s, 1080×1920, 59.92 fps), window **t = 5–35 s** re-encoded to
`IMG_4091_30s.mp4` (1798 frames).

## Why this window

The clip is usable for its first ~45 s and not after. Camera drift, measured on the static red
base of the rig:

| window | drift vs median | imaged wheel diameter |
|---|---|---|
| 5–35 s | within ±15 px | 1021 px, CV 0.057 |
| 35–50 s | +37 → +66 px | 986 → 973 px |
| 60–65 s | +44 px | **762 px** — the operator pulled back |

A single calibration only holds while the framing does. 5–35 s keeps scale drift near the ±4%
that the tilt alone accounts for, and still contains **~20 revolutions**.

## What the motion does

Measured over the source clip, from the knob-pair axis angle (immune to the 180° swap):

| window | median ω |
|---|---|
| 0–20 s | 4.6–4.9 rad/s |
| 20–35 s | 4.2 → 3.2 |
| 35–45 s | 2.8 → 2.4 |
| 45–65 s | 0.03–0.65 — at rest |

**27.4 revolutions in 65 s**, a clean monotonic coast-down, and the corpus's only clip that
actually **comes to rest inside the recording**. The 30 s cut holds the fast, smooth part.

## Geometry (measured, not assumed)

- **Rotation centre (imaged hub) = (547, 977) px → `rotation_center_frac` [0.5063, 0.5089]**.
  Recovered by intersecting 205 knob-pair chords: the two knobs are a physical diameter, so the
  line joining their images passes through the image of the axle whatever the viewing angle.
  This is more reliable than eyeballing the spoke crossing, and it does not assume affinity.
- **Orbit radius 510 px** (pair separation 1020 px, CV 0.044).
- **Axis ratio 0.96 → tilt ≈ 16.5°** — mid-range for the corpus.
- **HUB OFFSET ≈ 60–73 px.** This clip has REAL PERSPECTIVE. The rule from
  `docs/tracking-data-quality-2026-07-15.md`: perspective strength is the distance between the
  imaged axle and the centre of the imaged ellipse — 4046 = 85.6 px, every clip needing no
  correction = 0.7–8.8 px. **Its per-instant ω will carry a 1/rev ripple that is projection, not
  physics**, so this clip is **OPEN**, not GOLD, until rectification lands (see the checkpoint's
  OPEN 3). It is the second clip that makes that fix worth doing.

## Scale — NOT yet measured

There is **no object of known size in frame**. `physical_size` is a placeholder and every SI
value (r, v, a_c) is provisional; ω, T, f and the whole shape of the motion are scale-free and
unaffected. **To settle it: put a tape across the wheel's rim diameter** — one number, and the
same fix the ceiling fan needed before its v/a_c could be trusted.
