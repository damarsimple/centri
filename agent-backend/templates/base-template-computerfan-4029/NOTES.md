# base-template-computerfan-4029

~140 mm computer case fan (~11 grey blades, black frame) with a RED tape marker on
one blade, hand/desk spun. Source: `New cases/IMG_4029.MOV` (1080×1920 after cv2
auto-rotates the -90 metadata; H.264, 60 fps, 13.8 s).

**Tracking = color mode** (red marker). SAM3 is down and would alias 11 identical
blades anyway; frequency mode risks aliasing (11 blades × fast spin can exceed
fps/2). The red marker color-tracks cleanly: **87% coverage, orbit CV 0.066**,
orbit 312 px. Pre-cached at `analysis_output/data/api_cache.json` → cache HIT.

`physical_size = 0.04 m` = the red marker's real size (color mode uses the marker as
the scale reference); yields orbit radius ≈ 0.06 m (fan radius). PROVISIONAL.
Relative kinematics (ω, T, motion profile) are scale-free.
