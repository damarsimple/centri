#!/usr/bin/env python3
"""Compare a workspace's measured omega(t) against a phone-gyroscope log.

Written 2026-08-03 for TODO §1.4 / §7.2, after it emerged that the sensor
validation in ABLATION_METHOD_STUDIES.md was computed on the ARCHIVED rectified
workspace (`job_turntable-3-rect`) and not on the shipped one — so the paper's
sensor table did not describe the pipeline the rest of the paper describes.

The sensor measures ANGULAR RATE ONLY. It cannot validate the radius or the
metre scale, so this tool deliberately reports nothing about v or a_c: a
"gyroscope a_c" would be omega_gyro^2 * r using the SAME r as the video leg,
the radius would cancel, and the agreement would carry no information beyond
the omega agreement. Do not add one.

Usage:
    python3 tools/gyro_compare.py GYRO.csv WORKSPACE [WORKSPACE ...]

    python3 tools/gyro_compare.py ../IMG_3075.csv \
        workspaces-archive/pre-coordfix-20260721-145038/job_turntable-3 \
        workspaces-archive/pre-full-e2e-20260729/job_turntable-3-rect

Gyro CSV: `timestamp` (ms) + `gyro_gamma` (deg/s, rotation about the screen
normal = the turntable axis). Magnitudes are compared, so the sign convention
of neither leg matters.
"""
import csv
import sys
import pathlib
import numpy as np

GRID_HZ = 240.0          # resampling grid for the alignment
LAG_MAX_S = 2.5          # the phone starts logging before recording begins
LAG_STEP_S = 0.005
MOTION_FRAC = 0.2        # the sensor's own motion window, as a fraction of its peak


def load_gyro(path):
    ts, g = [], []
    for row in csv.DictReader(open(path)):
        ts.append(int(row["timestamp"]))
        g.append(float(row["gyro_gamma"]))
    t = (np.array(ts, float) - ts[0]) / 1000.0
    return t, np.abs(np.array(g)) * np.pi / 180.0      # deg/s -> rad/s


def load_video(ws):
    p = pathlib.Path(ws) / "analysis_output" / "data" / "kinematics.csv"
    t, w = [], []
    for row in csv.DictReader(open(p)):
        v = row["omega_rad_s"]
        if v in ("", "nan", "NaN"):
            continue                                    # gaps stay gaps
        t.append(float(row["time_s"]))
        w.append(abs(float(v)))
    return np.array(t), np.array(w)


def align(grid, V, tg, wg):
    """Best lag by correlation. Scanned, not argmax'd off a raw cross-correlation:
    both series are mostly zero, so a plain correlate() locks onto a spurious peak."""
    best = (None, -2.0)
    for lag in np.arange(0.0, LAG_MAX_S, LAG_STEP_S):
        G = np.interp(grid + lag, tg, wg, left=0.0, right=0.0)
        if G.std() < 1e-9:
            continue
        r = float(np.corrcoef(V, G)[0, 1])
        if r > best[1]:
            best = (float(lag), r)
    return best


def compare(ws, tg, wg):
    tv, wv = load_video(ws)
    grid = np.arange(0.0, tv[-1], 1.0 / GRID_HZ)
    V = np.interp(grid, tv, wv)
    lag, r = align(grid, V, tg, wg)
    G = np.interp(grid + lag, tg, wg, left=0.0, right=0.0)

    m = G > MOTION_FRAC * G.max()                       # the sensor's motion window
    Va, Ga = V[m], G[m]
    err = (Va - Ga) / Ga
    return {
        "workspace": str(ws), "lag_s": lag, "r": r, "n": int(m.sum()),
        "mean_video": Va.mean(), "mean_gyro": Ga.mean(),
        "mean_err_pct": 100 * (Va.mean() - Ga.mean()) / Ga.mean(),
        "peak_video": V.max(), "peak_gyro": G.max(),
        "peak_err_pct": 100 * (V.max() - G.max()) / G.max(),
        "rms_pct": 100 * float(np.sqrt((err ** 2).mean())),
        "median_abs_pct": 100 * float(np.median(np.abs(err))),
    }


def main(argv):
    if len(argv) < 3:
        sys.exit(__doc__)
    tg, wg = load_gyro(argv[1])
    out = [compare(ws, tg, wg) for ws in argv[2:]]
    w = max(len(pathlib.Path(o["workspace"]).name) for o in out)
    print(f"{'workspace':{w}}  {'lag':>6} {'r':>7} {'mean err':>9} {'peak err':>9} {'RMS':>7} {'med':>7}")
    for o in out:
        print(f"{pathlib.Path(o['workspace']).name:{w}}  {o['lag_s']:5.3f}s {o['r']:7.4f} "
              f"{o['mean_err_pct']:+8.1f}% {o['peak_err_pct']:+8.1f}% "
              f"{o['rms_pct']:6.1f}% {o['median_abs_pct']:6.1f}%")
    print()
    for o in out:
        print(f"{pathlib.Path(o['workspace']).name}: "
              f"mean |w| video {o['mean_video']:.3f} vs gyro {o['mean_gyro']:.3f} rad/s; "
              f"peak {o['peak_video']:.3f} vs {o['peak_gyro']:.3f}; n={o['n']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
