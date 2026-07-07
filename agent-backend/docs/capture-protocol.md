# Video capture protocol (circular-motion corpus)

How to film a clip so the measurement pipeline produces reliable kinematics and the
learning-material generator has an authentic scene to write about. Written for the corpus
build the professor asked for (10–15 phenomena / ~30 videos) and for anyone recording a new
object.

## Why it matters

The two failure modes we keep hitting are both fixed at capture time, not in software:

1. **Oblique capture.** Filming the orbit at an angle turns the circle into an ellipse in the
   image. The per-instant angular velocity then carries a viewing-angle ripple that is a
   *projection artifact*, not real physics. The pipeline now detects this and hedges
   (`measurement_quality.reliable = false` → the material drops per-instant claims), but a
   face-on clip avoids the whole problem and keeps the quarter-turn angle milestones usable.
2. **No scale reference.** Absolute SI values (radius in metres, a_c in m/s²) need a known
   physical size in frame. Without one, only the scale-free quantities (ω, α, period, ratios)
   survive.

## The protocol

- **Face-on.** Put the camera on the rotation axis, looking straight down the axis at the
  plane of the circle. The orbit should look round on screen, not squashed. This is the single
  most important rule.
- **Phone steady.** Brace the phone or use a small tripod. A moving camera injects apparent
  motion the tracker cannot separate from the object's.
- **Red-tape marker.** Stick a small bright marker (red tape works) on the moving object so
  the tracker has a high-contrast, unambiguous point. A plain simple-noun description of that
  marker ("red tape", "red dot") tracks far more reliably than an elaborate one.
- **A scale reference in frame.** Include an object of known width on or near the turntable
  (a coin, a ruler, the plate itself if you can measure it). Note its real size — it turns
  pixels into metres.
- **Capture the whole story: start → speed-up → steady.** Begin recording *before* the motion
  starts, catch the spin-up, and let it reach a steady rate. The spin-up (constant angular
  acceleration α) is real, useful physics for the advanced tier — don't cut it off.
- **Slow enough to resolve.** Keep the spin slow enough that the marker doesn't blur between
  frames; one turn should take on the order of a second or more, not a fraction of a second.
- **10–15 seconds.** Long enough for several full turns and a clear steady phase; short enough
  to stay in frame and in focus.

## Target corpus

- **10–15 distinct phenomena, ~30 videos**, varying the speed (slow / medium / fast) and the
  radius so the reference set spans a real difficulty range.
- **note-1's "3 scenarios × 3":** three everyday scenarios, three speeds each, for a
  controlled difficulty sweep.
- **Candidate objects** (Zhongli night-market / playground toys and household items):
  spinning playground roundabout, hand-spun turntable / lazy susan, desk-fan blade, bicycle
  wheel with a taped spoke, a top, a ceiling-fan pull, a salad spinner, a merry-go-round toy.

## After capture

Each accepted clip should yield: a clean `kinematics.csv` (high coverage, `active` window that
covers the motion), `measurement_quality.reliable = true` where possible, and a one-line scene
context typed into the app's "What's happening in this video?" field — that free text becomes
the authoritative narrative frame for the generated learning material.
