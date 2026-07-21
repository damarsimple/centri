"""General measurement-quality signals for circular-motion tracks.

NON-hardcoded: no per-clip constants. Operates on any job's kinematics.csv +
stats.json. The key discriminator is whether the omega variation is PHASE-LOCKED
to the orbit (a projection/viewing-angle artifact -> apparent-omega ripple, once
or twice per revolution) versus a slow TIME trend (real spin-up / coast-down).

Real accel/decel is a function of TIME, uncorrelated with orbital phase.
Projection ripple is a function of orbital PHASE, repeating every revolution.
So: remove the smooth time-trend, then ask how much of what's left is explained
by orbital phase (1x + 2x per rev). That fraction is the artifact signature.
"""
from __future__ import annotations
import csv, json, math
from pathlib import Path
import numpy as np

# General thresholds (corpus-level, not clip-tuned). Documented, tunable.
# An oblique-view projection artifact needs BOTH its geometric cause (an elliptical
# image orbit) AND its kinematic symptom (phase-locked omega ripple). Requiring the
# conjunction rejects clip-length-fragile phase-lock on near-circular orbits (short
# turntable clips, a bike marker) where a high phase-lock has some other, lower-
# confidence cause and we should NOT confidently suppress per-instant values.
AXIS_RATIO_OBLIQUE   = 1.08   # image orbit ellipticity consistent with a tilted circle
PHASELOCK_UNRELIABLE = 0.60   # majority of detrended-omega variance explained by orbit phase
RIPPLE_CV_UNRELIABLE = 0.08   # and the ripple is a material fraction of the mean
AXIS_UNRELIABLE      = 1.08   # orbit visibly elliptical (kept: reported, no longer a gate)
MIN_REVS_FOR_PHASELOCK = 2.0  # below this the phase-lock statistic cannot convict OR clear

def _load(csv_path):
    t,x,y,om,rpx=[],[],[],[],[]
    with open(csv_path, newline="") as fh:
        for r in csv.DictReader(fh):
            if r.get("active") not in ("1","1.0","True","true"): continue
            try:  # parse ALL fields first, then append atomically (empty omega on
                  # interpolated frames must not desync the arrays)
                vt=float(r["time_s"]); vx=float(r["x_px"]); vy=float(r["y_px"])
                vo=float(r["omega_rad_s"]); vr=float(r["r_px"])
            except (ValueError,KeyError): continue
            t.append(vt); x.append(vx); y.append(vy); om.append(vo); rpx.append(vr)
    return tuple(np.asarray(a,float) for a in (t,x,y,om,rpx))

def _axis_ratio(x,y):
    D=np.c_[x*x,x*y,y*y,x,y,np.ones_like(x)]
    _,_,V=np.linalg.svd(D); a,b,c,d,e,f=V[-1]
    M=np.array([[2*a,b],[b,2*c]])
    try: cx,cy=np.linalg.solve(M,[-d,-e])
    except np.linalg.LinAlgError: return 1.0
    A=np.array([[a,b/2],[b/2,c]]); const=a*cx*cx+b*cx*cy+c*cy*cy+d*cx+e*cy+f
    ev,_=np.linalg.eigh(A); rad=-const/ev
    if np.any(rad<=0): return 1.0
    ax=np.sqrt(rad); return float(ax.max()/ax.min())

def compute(csv_path, stats):
    t,x,y,om,rpx=_load(csv_path)
    out={"n":int(len(t))}
    if len(t)<30:
        out.update(reliable=True, flags=[], note="too few frames to assess"); return out
    s=np.sign(np.nanmedian(om)) or 1.0
    om=s*om  # work with positive omega
    mean_w=float(np.nanmean(om))
    # smooth TIME trend (real accel/decel): quadratic fit in time
    trend=np.polyval(np.polyfit(t,om,2),t)
    resid=om-trend
    # orbital phase from the trajectory
    phi=np.unwrap(np.arctan2(y-np.mean(y),x-np.mean(x)))
    # explain residual by phase harmonics 1x + 2x per rev
    B=np.c_[np.cos(phi),np.sin(phi),np.cos(2*phi),np.sin(2*phi),np.ones_like(phi)]
    coef,_,_,_=np.linalg.lstsq(B,resid,rcond=None)
    fit=B@coef
    ss_tot=float(np.sum((resid-resid.mean())**2)) or 1e-9
    phaselock=float(np.sum(fit**2)/ss_tot) if ss_tot>0 else 0.0
    phaselock=max(0.0,min(1.0,phaselock))
    ripple_cv=float(np.std(resid)/abs(mean_w)) if mean_w else 0.0
    axis_ratio=_axis_ratio(x,y)

    # How many revolutions the phase-lock statistic actually had to work with. Below ~2 it
    # fits four harmonics to about 1.5 cycles and means nothing either way — it can neither
    # convict a clip nor clear one.
    n_revs=float(np.ptp(phi)/(2*math.pi))

    flags=[]
    if axis_ratio>AXIS_RATIO_OBLIQUE: flags.append("oblique_capture")

    # A phase-locked ripple of material amplitude is not trustworthy per-instant, WHATEVER
    # its cause. This used to also require an elliptical orbit, on the reasoning that oblique
    # capture is what produces the ripple — true of the clip it was derived from, and an
    # assumption everywhere else: it silently cleared any phase-locked ripple on a round
    # orbit. turntable-3 is round to an axis ratio of 1.002 and still carries a ripple that
    # survives every explanation we can test (not the marker centroid, since the object's own
    # orientation shows it too; not motion blur, since its imaged size is constant; not the
    # centre, since the radius holds to 2 px; not a torque, since the amplitude scales with
    # omega rather than against it). Being unable to name the cause is not evidence of health.
    unreliable = (phaselock>=PHASELOCK_UNRELIABLE and ripple_cv>=RIPPLE_CV_UNRELIABLE)

    # Distinct from "known bad": too short to assess. Claiming reliability here asserts
    # something the data cannot support.
    unverified = (not unreliable and n_revs<MIN_REVS_FOR_PHASELOCK
                  and ripple_cv>=RIPPLE_CV_UNRELIABLE)

    if unreliable: flags.append("per_instant_omega_unreliable")
    if unverified: flags.append("per_instant_omega_unverified")
    out.update(
        orbit_axis_ratio=round(axis_ratio,3),
        omega_ripple_cv=round(ripple_cv,3),
        omega_phaselocked_fraction=round(phaselock,3),
        n_revolutions=round(n_revs,2),
        implied_tilt_deg=round(math.degrees(math.acos(min(1.0,1.0/axis_ratio))),1),
        reliable=not (unreliable or unverified),
        flags=flags,
    )
    return out

def build_quality_block(sig, stats):
    """Machine-readable trust channel injected into the seed for the agent."""
    aa=stats.get("angular_acceleration",{}) or {}
    mt=aa.get("motion_type")
    flags=sig.get("flags",[])
    unreliable="per_instant_omega_unreliable" in flags
    unverified="per_instant_omega_unverified" in flags
    suppress = unreliable or unverified
    usable=["mean angular velocity (time-average)","period T","frequency f","mean centripetal acceleration"]
    do_not=[]
    if mt in ("accelerating","decelerating") and not suppress:
        usable.append(f"the overall {mt} trend of omega over the clip (angular acceleration)")
    if suppress:
        do_not=["per-instant / timeline omega values","the shape of the omega(t) curve",
                "any claim that the object speeds up and slows down within each revolution"]
    block={
        "reliable": not suppress,
        "flags": flags,
        "orbit_axis_ratio": sig.get("orbit_axis_ratio"),
        "omega_phaselocked_fraction": sig.get("omega_phaselocked_fraction"),
        "n_revolutions": sig.get("n_revolutions"),
        "usable_quantities": usable,
        "do_not_claim": do_not,
    }
    pct=int(100*(sig.get("omega_phaselocked_fraction") or 0))
    if unreliable:
        # Name the cause only when the geometry supports it. An elliptical image orbit is
        # evidence of oblique capture; a round one is not, and the ripple still disqualifies
        # per-instant claims — we simply cannot say why.
        oblique = (sig.get("orbit_axis_ratio") or 1.0) >= AXIS_UNRELIABLE
        cause=("The orbit is seen at a slant, not face-on (image path is an ellipse, axis ratio "
               f"{sig.get('orbit_axis_ratio')}), and {pct}% of the per-instant angular-velocity "
               "variation is locked to orbital phase — a viewing-angle projection artifact, NOT "
               "real motion.") if oblique else (
               f"{pct}% of the per-instant angular-velocity variation repeats with orbital "
               "position rather than with time. Motion of the object itself cannot do that, so "
               "this is a measurement artifact; its cause on this clip is not identified.")
        block["guidance"]=(
            cause+" Report only the time-AVERAGE quantities and the qualitative fact of "
            "rotation. Do NOT narrate the timeline or claim the object speeds up/slows down "
            "during a revolution. State one honest sentence that per-instant angular velocity "
            "is not reliably recoverable from this clip."
        )
    elif unverified:
        block["guidance"]=(
            f"This clip covers only {sig.get('n_revolutions')} revolutions, too few to establish "
            "whether the variation in per-instant angular velocity repeats with orbital position "
            "(an artifact) or with time (real motion) — the test needs at least "
            f"{MIN_REVS_FOR_PHASELOCK:g}. The variation is not small "
            f"({int(100*(sig.get('omega_ripple_cv') or 0))}% of the mean), so it cannot be "
            "dismissed either. Report the time-AVERAGE quantities and the qualitative fact of "
            "rotation; do NOT narrate the timeline. This is a limit of the recording, not a "
            "finding about the motion."
        )
    else:
        block["guidance"]="Per-instant angular velocity is reliable; narrate the timeline normally."
    return block

if __name__=="__main__":
    import sys
    for ws in sys.argv[1:]:
        p=Path(ws)/"analysis_output/data"
        stats=json.loads((p/"stats.json").read_text())
        sig=compute(p/"kinematics.csv", stats)
        aa=stats.get("angular_acceleration",{}) or {}
        print(f"{Path(ws).name[4:12]}  obj={stats.get('object_name','?'):14.14} "
              f"motion={aa.get('motion_type','?'):12.12} "
              f"axis={sig.get('orbit_axis_ratio','?')!s:5} phaselock={sig.get('omega_phaselocked_fraction','?')!s:5} "
              f"rippleCV={sig.get('omega_ripple_cv','?')!s:5} -> {sig['flags']}")
