# LocateAnything-3B vs SAM3 — tracker ablation, 2026-07-21

Answers one question: **is `turntable-3`'s phase-locked ω ripple caused by our tracker?**

**No.** A structurally different model — LocateAnything-3B, an autoregressive box detector with no
mask, no temporal state and no propagation — reproduces the same locally-detrended ω residual:

| clip | LA usable | mean-ω agreement | ripple correlation |
|---|---|---|---|
| turntable-3 | 90% | 0.10% | **r = +0.980** |
| turntable-1 | 90% | 0.02% | **r = +0.980** |
| turntable-2 | 99% | 0.13% | **r = +0.991** |

The angular tracks sit 0.46° rms apart where the disputed ripple is worth ~1.8°.

## The cue wording dominates everything else here — run `prompt_effect.py`

The first pass used each sidecar's existing cue (`"red phone"`, `"black ball"`) and concluded LA was
too unreliable to use. **That was mostly the wording.** Dropping the colour adjective:

| clip | cue | raw | usable | worst gap | mean-ω |
|---|---|---|---|---|---|
| turntable-3 | `red phone` | 92.6% | 82.3% | 0.70 s | 54% |
| turntable-3 | **`phone`** | **100%** | **90.3%** | **0.25 s** | **0.10%** |
| turntable-1 | `red phone` | 91.9% | 87.5% | 0.25 s | 0.04% |
| turntable-1 | **`phone`** | **96.9%** | **90.3%** | **0.13 s** | 0.02% |
| turntable-2 | `red phone` | 98.4% | 96.0% | 0.08 s | 0.16% |
| turntable-2 | **`phone`** | **100%** | **98.8%** | **0.03 s** | 0.13% |
| roundabout-4046 | `black ball` | 32.4% | 32.4% | 0.58 s | 30% |
| roundabout-4046 | **`ball`** | **84.9%** | **57.2%** | **0.32 s** | **1.4%** |

A bare noun beats the colour-qualified noun on every clip — the same law the corpus already found on
SAM3, now confirmed on an unrelated model. The **failure modes differ too**: `"red phone"` fails by
returning a whole-frame box around everything reddish, `"phone"` fails by returning nothing. A miss
is caught by a coverage gate; a plausible box silently poisons the trajectory.

`trajectories/la_*.json` = original cue, `trajectories/la2_*.json` = bare-noun cue.
`prompt_sweep.py` tests candidate cues on the frames that actually failed (needs the GPU worker).

**What this settles, and what it does not.** It eliminates "our segmentation is buggy". It does *not*
eliminate the angle dependence itself: both trackers are appearance-based, so an imaged extent that
varies with viewing angle is inherited by both. The artifact is a property of the **footage**, not of
the tracker — so the fix is **a better marker, not a better tracker**. See §3.4.1 of
`technical-report/centri-video-data-quality.tex`.

## ⚠ `ripple_test.py` uses the OLD cue — its turntable-3 row is an artifact

`ripple_test.py` reads `trajectories/la_*.json` (original cues) and so prints a 53.99% mean-ω
disagreement for turntable-3. **That is interpolation, not a tracker disagreement**: with
`"red phone"` LA loses the phone for 0.70 s continuously at peak speed, and interpolating a gap that
long discards a whole revolution (0.87 recovered vs 1.88 actual). With `"phone"` the gap falls to
0.25 s, 1.87 of 1.88 revolutions survive, and the disagreement is 0.10%. **Use `prompt_effect.py`
for current numbers.**

## ⚠ Coordinate space

`pipeline_inputs.json` is **not necessarily in the space it declares** — turntable-2 stores a
cropped-video trajectory labelled `display`. These scripts re-resolve it the way `contract.py` does
(radius-CV test against the crop offset). Skipping that step produces a spurious 83.7 px
"disagreement", which is just the y_off=87 crop offset. The shipped guard handles this correctly.

## Files

- `compare_all.py` — coverage, worst gap, centroid agreement, orbit radius, all four clips
- `ripple_test.py` — the decisive test: does the ripple survive a change of tracker?
- `compare_gated.py` — turntable-3 in detail, incl. the bump window
- `trajectories/*.json` — raw LA output, one per clip (regenerating needs the GPU worker)

## Reproducing the raw trajectories

```sh
# worker lives in test/ (gitignored); this dir is under agent-backend/docs/ so it is tracked
/home/damar/miniconda3/envs/locateanything/bin/python test/locateanything_worker.py   # port 8087
# stop it with: pkill -f "locateanything_[w]orker"   <-- the [w] avoids killing your own shell
curl -X POST http://localhost:8087/track \
  -F "file=@<clip>/input_video.mp4" -F 'targets=["red phone"]' -F "stride=1" \
  -o trajectories/la_<job>.json
```

The base conda env is broken for this (torch cu130 vs torchvision cu128). ~0.28 s/frame, so a
350-frame clip is ~100 s. **Stop the worker when done — it holds ~10.7 GB of VRAM that Qwen needs.**
Targets: `red phone` for the turntables, `black ball` for roundabout-4046.
