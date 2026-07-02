# base-template-roundabout-4046  (SMALL wheel)

Outdoor shoulder-wheel (concentric-ring "arm rotation" device, ~0.5 m across), single
black knob on the rim, hand-spun fast. Source: `New cases/IMG_4046.MOV`, 15 s window
(t=8-23) re-encoded upright → `IMG_4046_15s.mp4` (1080×1920, 60 fps).

**Tracking = SAM3 object mode** ("black ball"). Colour tracking of the black knob was
only 22% (faint/blurs when fast); SAM3 tracks it at **100% coverage, orbit CV 0.052,
0 hop-jumps (clean single knob)**. Full 53 s clip crashed SAM3 (GGML memory pool at
3178 frames) → a 15 s window (899 frames) is used. Pre-cached → cache HIT.

`physical_size = 0.06 m` (knob real size, object-mode scale ref) → orbit radius ≈ 0.25 m
(SMALL). PROVISIONAL; ω/T scale-free.
