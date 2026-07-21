"""Does the phase-locked omega ripple survive a change of tracker?

Only meaningful where LA's coverage is dense enough that interpolation cannot
invent or erase the signal — so run it on the clips with short worst-case gaps.
Detrends LOCALLY at the revolution scale (a global polynomial has produced two
false conclusions in this analysis).
"""
import json, math, pathlib
import numpy as np

S = str(pathlib.Path(__file__).resolve().parent / "trajectories")
W = "/home/damar/centri/agent-backend/workspaces"

CLIPS = [
    ("turntable-2-rect", "red phone", "la_turntable-2-rect.json"),
    ("turntable-1-final", "red phone", "la_turntable-1-final.json"),
    ("turntable-3-rect", "red phone", "la_turntable-3-rect.json"),
]


def ripple(t, x, y, cx, cy, fps, sel):
    phi = np.unwrap(np.arctan2(y - cy, x - cx))
    om = np.gradient(phi, t)
    s = np.sign(np.nanmedian(om)) or 1.0
    om = s * om
    mean_w = float(np.nanmean(om))
    period = 2 * math.pi / abs(mean_w)
    w = max(5, int(round(period * fps)) | 1)
    trend = np.convolve(np.pad(om, w // 2, mode="edge"), np.ones(w) / w, mode="valid")
    resid = om - trend
    B = np.c_[np.cos(phi), np.sin(phi), np.cos(2 * phi), np.sin(2 * phi), np.ones_like(phi)][sel]
    r = resid[sel]
    coef, _, _, _ = np.linalg.lstsq(B, r, rcond=None)
    fit = B @ coef
    ss = float(np.sum((r - r.mean()) ** 2)) or 1e-9
    return (max(0.0, min(1.0, float(np.sum(fit ** 2) / ss))),
            float(np.std(r) / abs(mean_w)), mean_w,
            float(np.ptp(phi) / (2 * math.pi)), resid)


for job, tgt, f in CLIPS:
    p = json.load(open(f"{W}/job_{job}/analysis_output/data/pipeline_inputs.json"))
    fps = float(p["fps"])
    cx, cy = p["center"]["cx_px"], p["center"]["cy_px"]
    xs = np.array(p["trajectory_x_px"], float)
    ys = np.array(p["trajectory_y_px"], float)
    crop = json.load(open(f"{W}/job_{job}/analysis_output/data/roi_crop_meta.json"))
    xo, yo = crop["x_off"], crop["y_off"]
    if xo or yo:
        rr = lambda a, b: float(np.nanstd(np.hypot(a - cx, b - cy)) / np.nanmean(np.hypot(a - cx, b - cy)))
        if rr(xs, ys) > 0.15 and rr(xs + xo, ys + yo) < 0.6 * rr(xs, ys):
            xs, ys = xs + xo, ys + yo

    pts = json.load(open(f"{S}/{f}"))["trajectories"][tgt]
    xl = np.array([q["cx"] if q["cx"] is not None else np.nan for q in pts], float)
    yl = np.array([q["cy"] if q["cy"] is not None else np.nan for q in pts], float)
    area = np.array([(b[2]-b[0])*(b[3]-b[1]) if b else np.nan for b in [q["bbox"] for q in pts]], float)
    n = min(len(xs), len(xl))
    xs, ys, xl, yl, area = xs[:n], ys[:n], xl[:n], yl[:n], area[:n]
    t = np.arange(n) / fps
    med = np.nanmedian(area)
    good = np.isfinite(xl) & np.isfinite(area) & (area < 1.8 * med) & (area > 0.45 * med)
    xg = np.interp(t, t[good], xl[good])
    yg = np.interp(t, t[good], yl[good])

    pl_s, cv_s, mw_s, rev_s, res_s = ripple(t, xs, ys, cx, cy, fps, good)
    pl_l, cv_l, mw_l, rev_l, res_l = ripple(t, xg, yg, cx, cy, fps, good)
    cc = float(np.corrcoef(res_s[good], res_l[good])[0, 1])

    print(f"\n=== {job}  (LA usable {100*good.mean():.0f}%) ===")
    print(f"  {'':<14}{'phase-locked':>14}{'ripple CV':>12}{'mean |w|':>11}{'revs':>7}")
    print(f"  {'SAM3':<14}{pl_s:>14.3f}{cv_s:>12.3f}{mw_s:>11.3f}{rev_s:>7.2f}")
    print(f"  {'LocateAnything':<14}{pl_l:>14.3f}{cv_l:>12.3f}{mw_l:>11.3f}{rev_l:>7.2f}")
    print(f"  mean-omega agreement: {100*abs(mw_l-mw_s)/abs(mw_s):.2f}%"
          f"   ripple correlation r = {cc:+.3f}")
