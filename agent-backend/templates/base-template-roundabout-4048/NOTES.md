# base-template-roundabout-4048  (BIG wheel)

Outdoor 8-spoke wheel on a red axle (~1 m across), black knob on the rim, spun slowly
(~1 revolution). Source: `New cases/IMG_4048.MOV` (1080×1920 after cv2 auto-rotate, 60 fps).

**Tracking = color mode** (black knob, single-knob gated). SAM3 was tried but the big
wheel's 2 opposed knobs risk hopping; color at **100% coverage, orbit CV 0.069** on a
gated single knob is cleaner and unambiguous. Only ~1 revolution (slow spin) — one full
clean circle. Pre-cached → cache HIT.

`physical_size = 0.06 m` (knob real size) → orbit radius ≈ 0.45 m (BIG, vs 0.25 m small).
PROVISIONAL; ω/T scale-free.
