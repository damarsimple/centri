"""Old cue vs simple-noun cue, all four object-tracked clips."""
import json, math
import numpy as np

S = "/tmp/claude-1000/-home-damar-centri/509c1604-d98b-48fe-9583-739af875437b/scratchpad"
W = "/home/damar/centri/agent-backend/workspaces"
R = "/home/damar/centri/agent-backend/docs/la-ablation-2026-07-21/trajectories"

ROWS = [
    ("turntable-3-rect", "red phone", f"{R}/la_turntable-3-rect.json", "phone", f"{S}/la2_turntable-3-rect.json"),
    ("turntable-1-final", "red phone", f"{R}/la_turntable-1-final.json", "phone", f"{S}/la2_turntable-1-final.json"),
    ("turntable-2-rect", "red phone", f"{R}/la_turntable-2-rect.json", "phone", f"{S}/la2_turntable-2-rect.json"),
    ("roundabout-4046-final", "black ball", f"{R}/la_roundabout-4046-final.json", "ball", f"{S}/la2_roundabout-4046-final.json"),
]


def load(job):
    p = json.load(open(f"{W}/job_{job}/analysis_output/data/pipeline_inputs.json"))
    cx, cy = p["center"]["cx_px"], p["center"]["cy_px"]
    xs = np.array(p["trajectory_x_px"], float)
    ys = np.array(p["trajectory_y_px"], float)
    c = json.load(open(f"{W}/job_{job}/analysis_output/data/roi_crop_meta.json"))
    xo, yo = c["x_off"], c["y_off"]
    if xo or yo:
        def rr(a, b):
            r = np.hypot(a - cx, b - cy)
            return float(np.nanstd(r) / np.nanmean(r))
        if rr(xs, ys) > 0.15 and rr(xs + xo, ys + yo) < 0.6 * rr(xs, ys):
            xs, ys = xs + xo, ys + yo
    return float(p["fps"]), cx, cy, xs, ys


def metrics(job, tgt, f):
    fps, cx, cy, xs, ys = load(job)
    pts = json.load(open(f))["trajectories"][tgt]
    xl = np.array([q["cx"] if q["cx"] is not None else np.nan for q in pts], float)
    yl = np.array([q["cy"] if q["cy"] is not None else np.nan for q in pts], float)
    ar = np.array([(b[2]-b[0])*(b[3]-b[1]) if b else np.nan for b in [q["bbox"] for q in pts]], float)
    n = min(len(xs), len(xl))
    xs, ys, xl, yl, ar = xs[:n], ys[:n], xl[:n], yl[:n], ar[:n]
    t = np.arange(n) / fps
    med = np.nanmedian(ar)
    g = np.isfinite(xl) & np.isfinite(ar) & (ar < 1.8 * med) & (ar > 0.45 * med)
    bad = np.where(~g)[0]
    longest = run = 0
    for i in range(len(bad)):
        run = run + 1 if i and bad[i] == bad[i-1] + 1 else 1
        longest = max(longest, run)
    xg = np.interp(t, t[g], xl[g])
    yg = np.interp(t, t[g], yl[g])

    def rip(x, y):
        phi = np.unwrap(np.arctan2(y - cy, x - cx))
        om = np.gradient(phi, t)
        s = np.sign(np.nanmedian(om)) or 1.0
        om = s * om
        mw = float(np.nanmean(om))
        w = max(5, int(round((2 * math.pi / abs(mw)) * fps)) | 1)
        tr = np.convolve(np.pad(om, w // 2, mode="edge"), np.ones(w) / w, mode="valid")
        return om - tr, mw, float(np.ptp(phi) / (2 * math.pi))

    ra, mwa, va = rip(xs, ys)
    rb, mwb, vb = rip(xg, yg)
    return dict(raw=100*np.mean(np.isfinite(xl)), usable=100*g.mean(), gap=longest/fps,
                dom=100*abs(mwb-mwa)/abs(mwa), r=float(np.corrcoef(ra[g], rb[g])[0, 1]),
                rs=va, rl=vb)


print(f"{'clip':<22}{'prompt':>11}{'raw':>7}{'usable':>8}{'gap':>7}{'mean-w':>8}{'ripple r':>10}{'revs S/LA':>13}")
print("-" * 86)
for job, t1, f1, t2, f2 in ROWS:
    for tg, ff in ((t1, f1), (t2, f2)):
        m = metrics(job, tg, ff)
        print(f"{job:<22}{tg:>11}{m['raw']:>6.1f}%{m['usable']:>7.1f}%{m['gap']:>6.2f}s"
              f"{m['dom']:>7.2f}%{m['r']:>+10.3f}{m['rs']:>8.2f}/{m['rl']:<5.2f}")
    print()
