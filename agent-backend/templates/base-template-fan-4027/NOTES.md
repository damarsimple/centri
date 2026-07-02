# base-template-fan-4027

5-blade ceiling fan, red-paper marker on one blade tip (same physical fan as
base-template-fan-doll / job 1c183872). Source: `New cases/IMG_4027.MOV`
(1920×1080 landscape, H.264, 59.9 fps, 77.4 s, rotation baked = none).

**Motion:** two-phase — spins UP to peak ω≈4.0 rad/s (~34 rpm) @ t≈21 s, then
coasts DOWN to rest by ~t=60 s.

**Tracking = frequency mode** (SAM3 aliases 5 identical blades; blade-pass FFT is
hop-immune). Geometry from color-tracking the red marker: hub (1012,480) px =
frac [0.5271,0.4444]; blade-tip orbit 255 px (CV 0.05).

**Pre-cached** for the agent: `analysis_output/data/api_cache.json` +
`frequency_meta.json` (windowed ω(t), win 2.5 s / hop 0.5 s). Submitting with this
template → cache HIT, no tracker call (SAM3 not needed).

`physical_size = 0.6 m` (orbit radius) is PROVISIONAL — matches the prior fan case
for cross-comparability. Relative kinematics (ω, T, α, motion profile) are scale-free.
Two-phase motion → single-regime classifier will label one phase; faithful ω(t) lives
in `frequency_meta.json.omega_t`.
