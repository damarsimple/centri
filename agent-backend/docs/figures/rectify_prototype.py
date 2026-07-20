"""The actual fix: projective (not affine) rectification, uncalibrated.

Key geometry: for a circle, the polar line of the circle's CENTRE w.r.t. the circle is
that plane's line at infinity. Both survive projection, so:
    imaged hub h + fitted orbit conic C  ->  vanishing line  l = C h
    H_affine = [[1,0,0],[0,1,0], l]      ->  maps l to infinity (now an AFFINE image)
    then the ellipse->circle axis stretch ->  metric, so atan2 gives the true theta.
No camera intrinsics needed. The per-frame hub also cancels camera drift.

Validation is NOT "is it smoother" -- smoothing can do that. It is: does the PHASE-LOCKED
power (the artifact's signature) collapse while the time-trend survives, and does the
orbit become a circle to within the centroid-noise floor?
"""
import json, math
from pathlib import Path
import numpy as np
from scipy.signal import savgol_filter
import scipy.ndimage
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SP = Path("/tmp/claude-1000/-home-damar-centri/cdef7294-cb8f-4240-aaab-0fdd9f4857c0/scratchpad")
T = Path("/home/damar/centri/agent-backend/templates/base-template-roundabout-4046")
j = json.loads((T / "analysis_output/data/api_cache.json").read_text())
FPS = j["video_info"]["fps"]
tr = {p["frame"]: p for p in j["trajectories"]["black ball"] if p.get("cx") is not None}
hub = {int(r[0]): (r[1], r[2]) for r in np.load(SP / "hub4046.npy")}

frames = sorted(set(tr) & set(hub))
t = np.array(frames, float) / FPS
x = np.array([tr[f]["cx"] for f in frames])
y = np.array([tr[f]["cy"] for f in frames])
hx = np.array([hub[f][0] for f in frames])
hy = np.array([hub[f][1] for f in frames])
# camera drift is slow; the hub detection has its own jitter. Smooth the hub before
# using it as a reference so we subtract DRIFT, not detector noise.
hxs = savgol_filter(hx, 121, 2)
hys = savgol_filter(hy, 121, 2)
print(f"camera drift (smoothed hub): x {hxs.min():.0f}..{hxs.max():.0f} ({np.ptp(hxs):.0f}px), "
      f"y {hys.min():.0f}..{hys.max():.0f} ({np.ptp(hys):.0f}px)")


def fit_conic(x, y):
    xm, ym = x.mean(), y.mean(); s = max(x.std(), y.std(), 1e-9)
    X, Y = (x - xm) / s, (y - ym) / s
    D = np.c_[X * X, X * Y, Y * Y, X, Y, np.ones_like(X)]
    _, _, V = np.linalg.svd(D)
    a, b, c, d, e, g = V[-1]
    # de-normalise the conic back to pixel coords
    Cn = np.array([[a, b / 2, d / 2], [b / 2, c, e / 2], [d / 2, e / 2, g]])
    S = np.array([[1 / s, 0, -xm / s], [0, 1 / s, -ym / s], [0, 0, 1]])
    return S.T @ Cn @ S


def conic_params(C):
    A = C[:2, :2]
    cen = np.linalg.solve(2 * A, [-2 * C[0, 2], -2 * C[1, 2]])
    fp = cen @ A @ cen + 2 * C[:2, 2] @ cen + C[2, 2]
    ev, evec = np.linalg.eigh(A)
    rad = -fp / ev
    if np.any(rad <= 0):
        return None
    ax = np.sqrt(rad); o = np.argsort(-ax)
    return dict(c=cen, A=ax[o][0], B=ax[o][1], R=evec[:, o])


def metric_from_ellipse(x, y):
    """Affine image of a circle -> circle. Enforce det=+1 so handedness (and thus the
    sign of omega) is preserved."""
    p = conic_params(fit_conic(x, y))
    R = p["R"]
    if np.linalg.det(R) < 0:
        R = R[:, ::-1] if False else np.c_[R[:, 0], -R[:, 1]]
    q = np.c_[x - p["c"][0], y - p["c"][1]] @ R
    return q[:, 0], q[:, 1] * (p["A"] / p["B"]), p


def omega_of(theta, t):
    th = np.unwrap(theta)
    w = max(11, 2 * (int(FPS) // 6) + 1)
    if w % 2 == 0: w += 1
    th = savgol_filter(th, w, 3)
    om = np.gradient(th, t)
    return scipy.ndimage.median_filter(om, size=max(5, int(FPS // 10)), mode="nearest")


def diag(t, om, phase, label):
    trend = np.polyval(np.polyfit(t, om, 3), t)
    resid = om - trend
    B = np.c_[np.cos(phase), np.sin(phase), np.cos(2 * phase), np.sin(2 * phase), np.ones_like(phase)]
    coef, *_ = np.linalg.lstsq(B, resid, rcond=None)
    ss = float(np.sum((resid - resid.mean()) ** 2)) or 1e-9
    pl = float(np.clip(np.sum((B @ coef) ** 2) / ss, 0, 1))
    A1 = np.hypot(coef[0], coef[1]); A2 = np.hypot(coef[2], coef[3])
    print(f"{label:32} |w|={abs(np.mean(om)):6.3f}  rippleCV={np.std(resid)/abs(np.mean(om)):6.3f}  "
          f"phaselock={pl:5.3f}  A1={A1:5.3f}  A2={A2:5.3f}")
    return dict(cv=float(np.std(resid) / abs(np.mean(om))), pl=pl, A1=A1, A2=A2)


# ── A. baseline: static best-fit circle centre, raw image coords ─────────────
def fit_circle(x, y):
    M = np.c_[2 * x, 2 * y, np.ones_like(x)]
    sol, *_ = np.linalg.lstsq(M, x**2 + y**2, rcond=None)
    return sol[0], sol[1], math.sqrt(sol[2] + sol[0]**2 + sol[1]**2)


cx0, cy0, r0 = fit_circle(x, y)
th_A = np.arctan2(y - cy0, x - cx0)
om_A = omega_of(th_A, t)
phase = np.unwrap(th_A)

# ── B. + camera-drift removal (per-frame hub as the reference point) ─────────
xs = x - hxs + hxs.mean()
ys = y - hys + hys.mean()

# ── C. + projective rectification via the vanishing line ────────────────────
C = fit_conic(xs, ys)
h = np.array([hxs.mean(), hys.mean(), 1.0])          # imaged circle centre (hub)
l = C @ h                                            # polar of the hub = vanishing line
l = l / np.linalg.norm(l[:2])
print(f"vanishing line l = [{l[0]:+.5f}, {l[1]:+.5f}, {l[2]:+.2f}]  "
      f"(hub->ellipse-centre offset drives it)")
Ha = np.array([[1, 0, 0], [0, 1, 0], [l[0], l[1], l[2]]])
P = np.c_[xs, ys, np.ones_like(xs)] @ Ha.T
xr, yr = P[:, 0] / P[:, 2], P[:, 1] / P[:, 2]
xm, ym, pm = metric_from_ellipse(xr, yr)
th_C = np.arctan2(ym, xm)
om_C = omega_of(th_C, t)

# B alone (drift removed, still circle-fit atan2) for attribution
cxb, cyb, rb = fit_circle(xs, ys)
om_B = omega_of(np.arctan2(ys - cyb, xs - cxb), t)

print()
a = diag(t, om_A, phase, "A baseline (circle fit)")
b = diag(t, om_B, phase, "B + camera-drift removed")
c = diag(t, om_C, phase, "C + projective rectified")

# circularity: does the rectified orbit become a circle?
rr_A = np.hypot(x - cx0, y - cy0)
rr_C = np.hypot(xm, ym)
print(f"\norbit radial residual:  baseline {np.std(rr_A):5.2f}px ({100*np.std(rr_A)/rr_A.mean():.2f}%)"
      f"   ->  rectified {np.std(rr_C):5.2f}px ({100*np.std(rr_C)/rr_C.mean():.2f}%)")
print(f"phase-locked ripple A1: {a['A1']:.3f} -> {c['A1']:.3f}   A2: {a['A2']:.3f} -> {c['A2']:.3f}")
print(f"phase-lock fraction   : {a['pl']:.3f} -> {c['pl']:.3f}")

fig, ax = plt.subplots(1, 3, figsize=(16, 4.6))
ax[0].plot(t, np.abs(om_A), lw=1.0, color="#d1495b", label=f"A baseline  (CV {a['cv']:.3f}, lock {a['pl']:.2f})")
ax[0].plot(t, np.abs(om_C), lw=1.4, color="#2a9d8f", label=f"C rectified (CV {c['cv']:.3f}, lock {c['pl']:.2f})")
ax[0].set_xlabel("time (s)"); ax[0].set_ylabel("|ω| (rad/s)")
ax[0].set_title("roundabout-4046 — angular velocity"); ax[0].legend(fontsize=8); ax[0].grid(alpha=.3)
ax[1].plot(x, y, ".", ms=2, color="#d1495b", label="image orbit (ellipse)")
ax[1].plot(hxs, hys, "-", lw=2, color="#264653", label="hub (camera drift)")
ax[1].set_aspect("equal"); ax[1].invert_yaxis(); ax[1].legend(fontsize=8); ax[1].grid(alpha=.3)
ax[1].set_title("as filmed")
ax[2].plot(xm, ym, ".", ms=2, color="#2a9d8f")
ax[2].set_aspect("equal"); ax[2].invert_yaxis(); ax[2].grid(alpha=.3)
ax[2].set_title(f"rectified orbit — radial resid {100*np.std(rr_C)/rr_C.mean():.2f}%")
plt.tight_layout(); plt.savefig(SP / "proj4046.png", dpi=110)
print("wrote proj4046.png")
