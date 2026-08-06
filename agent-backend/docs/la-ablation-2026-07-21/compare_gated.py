"""Decisive test: on frames where LocateAnything tracks cleanly, does the same
phase-locked omega ripple appear?

If YES  -> the ripple is in the footage; SAM3's masks are exonerated.
If NO   -> SAM3's masks are the cause.
Gate: reject boxes whose area departs from the clip median (detector failures on
motion blur), then interpolate. Compares only on the frames LA got right.
"""
import json, math, pathlib
import numpy as np

JOB = "/home/damar/centri/agent-backend/workspaces-archive/pre-full-e2e-20260729/job_turntable-3-rect"
S = str(pathlib.Path(__file__).resolve().parent / "trajectories")
CX, CY = 543.024, 878.016

p = json.load(open(f"{JOB}/analysis_output/data/pipeline_inputs.json"))
fps = float(p["fps"])
xs = np.array(p["trajectory_x_px"], float)
ys = np.array(p["trajectory_y_px"], float)

la = json.load(open(f"{S}/la_full.json"))
pts = la["trajectories"]["red phone"]
xl = np.array([q["cx"] if q["cx"] is not None else np.nan for q in pts], float)
yl = np.array([q["cy"] if q["cy"] is not None else np.nan for q in pts], float)
area = np.array([(b[2]-b[0])*(b[3]-b[1]) if b else np.nan for b in [q["bbox"] for q in pts]], float)

n = min(len(xs), len(xl))
xs, ys = xs[:n], ys[:n]
xl, yl, area = xl[:n], yl[:n], area[:n]
t = np.arange(n) / fps

med = np.nanmedian(area)
good = np.isfinite(xl) & np.isfinite(area) & (area < 1.8*med) & (area > 0.45*med)
print(f"LA usable frames: {good.sum()}/{n} ({100*good.sum()/n:.1f}%)")

# interpolate the rejected frames so gradients exist, but remember which are real
xg = np.interp(t, t[good], xl[good])
yg = np.interp(t, t[good], yl[good])


def stats(x, y, label, mask=None):
    phi = np.unwrap(np.arctan2(y - CY, x - CX))
    om = np.gradient(phi, t)
    s = np.sign(np.nanmedian(om)) or 1.0
    om = s * om
    mean_w = float(np.nanmean(om))
    period = 2*math.pi/abs(mean_w)
    w = max(5, int(round(period*fps)) | 1)
    trend = np.convolve(np.pad(om, w//2, mode="edge"), np.ones(w)/w, mode="valid")
    resid = om - trend
    phic = np.unwrap(np.arctan2(y - np.mean(y), x - np.mean(x)))
    sel = np.ones(len(t), bool) if mask is None else mask
    B = np.c_[np.cos(phic), np.sin(phic), np.cos(2*phic), np.sin(2*phic), np.ones_like(phic)][sel]
    r = resid[sel]
    coef, _, _, _ = np.linalg.lstsq(B, r, rcond=None)
    fit = B @ coef
    ss_tot = float(np.sum((r - r.mean())**2)) or 1e-9
    pl = max(0.0, min(1.0, float(np.sum(fit**2)/ss_tot)))
    rad = np.hypot(x - CX, y - CY)
    print(f"{label:<26} mean|w| {mean_w:6.3f} rad/s | revs {np.ptp(phic)/(2*math.pi):5.2f} | "
          f"rippleCV {np.std(r)/abs(mean_w):6.3f} | phase-locked {pl:5.3f} | "
          f"r {np.nanmean(rad[sel]):6.1f}+-{np.nanstd(rad[sel]):.1f} px")
    return om, resid, mean_w


print()
print("--- compared on the SAME frames (LA's usable set) ---")
om_s, res_s, mw_s = stats(xs, ys, "SAM3 (on LA-usable)", good)
om_l, res_l, mw_l = stats(xg, yg, "LocateAnything (gated)", good)
print()
print(f"mean-omega agreement on shared frames: "
      f"{100*abs(mw_l-mw_s)/abs(mw_s):.2f}%")

# do the two residuals track each other?
r_s, r_l = res_s[good], res_l[good]
cc = float(np.corrcoef(r_s, r_l)[0, 1])
print(f"correlation of the two detrended ripples: r = {cc:+.3f}")

# the bump
m = good & (t > 2.6) & (t < 3.6)
print()
print("bump window 2.6-3.6 s (usable frames only):")
for nm, om in [("SAM3", om_s), ("LA", om_l)]:
    w_, tw = om[m], t[m]
    base = np.polyval(np.polyfit(tw, w_, 1), tw)
    ex = w_ - base
    print(f"  {nm:<5} peak above local decay {ex.max():+.3f} rad/s at t={tw[np.argmax(ex)]:.2f}s "
          f"({100*ex.max()/w_.mean():.1f}% of mean |w| {w_.mean():.2f})")
