"""Coverage + agreement for LocateAnything-3B vs SAM3 across the four SAM3-tracked clips."""
import json, math, pathlib
import numpy as np

S = str(pathlib.Path(__file__).resolve().parent / "trajectories")
W = "/home/damar/centri/agent-backend/workspaces"

CLIPS = [
    ("turntable-3-rect", "red phone", "la_turntable-3-rect.json"),
    ("turntable-1-final", "red phone", "la_turntable-1-final.json"),
    ("turntable-2-rect", "red phone", "la_turntable-2-rect.json"),
    ("roundabout-4046-final", "black ball", "la_roundabout-4046-final.json"),
]

print(f"{'clip':<24}{'raw hit%':>9}{'usable%':>9}{'longest gap':>13}"
      f"{'agree med':>11}{'agree p95':>11}{'radius SAM3':>13}{'radius LA':>11}")
print("-" * 101)

rows = []
for job, tgt, f in CLIPS:
    p = json.load(open(f"{W}/job_{job}/analysis_output/data/pipeline_inputs.json"))
    fps = float(p["fps"])
    cx, cy = p["center"]["cx_px"], p["center"]["cy_px"]
    xs = np.array(p["trajectory_x_px"], float)
    ys = np.array(p["trajectory_y_px"], float)

    # The stored trajectory may be in cropped-video coordinates while declaring
    # "display" — the contract guard's case. LA always reports full-frame display
    # coordinates, so resolve SAM3 into display space the same way before comparing.
    crop = json.load(open(f"{W}/job_{job}/analysis_output/data/roi_crop_meta.json"))
    xo, yo = crop["x_off"], crop["y_off"]
    if xo or yo:
        def _cv(a, b):
            r = np.hypot(a - cx, b - cy)
            return float(np.nanstd(r) / np.nanmean(r))
        cv_dec, cv_crop = _cv(xs, ys), _cv(xs + xo, ys + yo)
        if cv_dec > 0.15 and cv_crop < 0.6 * cv_dec:
            xs, ys = xs + xo, ys + yo
            print(f"  [{job}] resolved to cropped-video space "
                  f"(radius CV {cv_dec:.4f} -> {cv_crop:.4f})")

    pts = json.load(open(f"{S}/{f}"))["trajectories"][tgt]
    xl = np.array([q["cx"] if q["cx"] is not None else np.nan for q in pts], float)
    yl = np.array([q["cy"] if q["cy"] is not None else np.nan for q in pts], float)
    area = np.array([(b[2]-b[0])*(b[3]-b[1]) if b else np.nan
                     for b in [q["bbox"] for q in pts]], float)

    n = min(len(xs), len(xl))
    xs, ys, xl, yl, area = xs[:n], ys[:n], xl[:n], yl[:n], area[:n]
    raw_hit = float(np.mean(np.isfinite(xl)))
    med = np.nanmedian(area)
    good = np.isfinite(xl) & np.isfinite(area) & (area < 1.8*med) & (area > 0.45*med)

    # longest contiguous rejected run, in seconds
    bad = np.where(~good)[0]
    longest = 0
    if len(bad):
        run = 1
        for i in range(1, len(bad)):
            run = run + 1 if bad[i] == bad[i-1] + 1 else 1
            longest = max(longest, run)
        longest = max(longest, 1)

    d = np.hypot(xs - xl, ys - yl)[good]
    rs = np.hypot(xs - cx, ys - cy)[good]
    rl = np.hypot(xl - cx, yl - cy)[good]

    print(f"{job:<24}{100*raw_hit:>8.1f}%{100*good.mean():>8.1f}%"
          f"{longest/fps:>11.2f}s{np.median(d):>10.1f}p{np.percentile(d,95):>10.1f}p"
          f"{np.mean(rs):>9.1f}+-{np.std(rs):<3.1f}{np.mean(rl):>7.1f}+-{np.std(rl):<3.1f}")
    rows.append(dict(job=job, raw_hit=raw_hit, usable=float(good.mean()),
                     longest_gap_s=longest/fps, agree_med=float(np.median(d)),
                     agree_p95=float(np.percentile(d, 95)),
                     r_sam3=float(np.mean(rs)), r_la=float(np.mean(rl))))

json.dump(rows, open(f"{S}/ablation_summary.json", "w"), indent=2)
print()
print("usable% = detected AND box area within [0.45, 1.8] x clip median")
print("agree   = per-frame centroid distance SAM3 vs LA, on usable frames only")
