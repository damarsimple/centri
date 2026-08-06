# base-template-fan-4028

5-blade ceiling fan, red-paper marker on one blade tip (same physical fan as
base-template-fan-doll / job 1c183872). Source: `New cases/IMG_4028.MOV`
(1920×1080 landscape, H.264, 59.9 fps, 98.4 s, rotation baked = none).

**Motion:** two-phase — spins UP to peak ω≈11.5 rad/s (~110 rpm) @ t≈20 s, then
coasts DOWN to rest by ~t=80 s.

**Tracking = frequency mode** (SAM3 aliases 5 identical blades; blade-pass FFT is
hop-immune). ω(t) uses **sub-bin parabolic peak interpolation** (`freq_track._peak_hz_parabolic`)
so the curve is smooth — the raw argmax bin quantised ω to 2π·(1/2.5 s)/5 ≈ 0.5 rad/s and
drew a non-physical staircase. Geometry: hub (1012,480) px = frac [0.5271,0.4444]; blade tip
355 px (sd 0.5 across frames); red-paper marker orbits 276 px, inboard of the tip.

**Pre-cached** for the agent: `analysis_output/data/api_cache.json` +
`frequency_meta.json` (windowed ω(t), win 2.5 s / hop 0.5 s). Submitting with this
template → cache HIT, no tracker call (SAM3 not needed).

**Scale = MEASURED (ruler, 2026-07-16).** Hub→blade-tip = 63.5 cm (25″); blade = 20″
(50.8 cm); tip = 355 px → **px_per_m = 559** (same physical fan as 4027). `orbit_radius_px`
(355) and `physical_size` (0.635 m) are pinned to the **blade tip**, so v and a_c are
reported AT THE TIP — the natural maximum (same ω everywhere on the rigid blade; v and a_c
grow with radius, zero at the hub). The tracked red marker sits inboard at ~49 cm, but in
frequency mode ω comes from the blade-pass FFT (not the marker's motion), so tip v/a_c are
exact: ω measured, r_tip measured by ruler. **Peak: v ≈ 7.36 m/s (26.5 km/h),
a_c ≈ 85.2 m/s² (8.69 g).** Relative kinematics (ω, T, α, motion profile) are scale-free.
Two-phase motion → single-regime classifier will label one phase; faithful ω(t) lives in
`frequency_meta.json.omega_t`.
