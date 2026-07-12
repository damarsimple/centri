#!/usr/bin/env python3
"""Automated detection-prompt micro-sweep for the SAM3 tracker.

Detection-prompt wording dominates tracking reliability (the lesson in
docs/object-detection-prompts.md: "toy" tracked 100% of frames while
"cream colored doll" tracked 6%). Finding a good prompt was a MANUAL
probe against the live /track endpoint. This automates it: given a video
and candidate prompts, it tracks each (on a short clip, for speed), ranks
them by coverage, and prints the winner.

Contract mirrors orchestrator Step 2 exactly:
  POST {TRACKING_API_URL}/track
    files={"file": (name, bytes, "video/mp4")}
    data ={"targets": json.dumps([prompt, ...])}
  -> {"status":"success","video_info":{"nb_frames":N},
      "trajectories":{prompt:[{"cx":..,"cy":..}, ...]}}

SAM3 coverage can decay over a server's lifetime. Pass --reset to recycle it
between probes (POST /reset, then wait for /health) — the same recycling the
orchestrator's retry loop uses. It is OFF by default: /reset EXITS the server
for its supervisor to relaunch, and if the relaunch is slow or fails the shared
server goes down, so only opt in when you know the supervisor restarts it.

Example:
  python tools/prompt_sweep.py --video clip.mp4 \
      --prompts "yellow toy" "hanging toy" "toy" "cream colored doll" \
      --clip-seconds 4
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

DEFAULT_URL = os.environ.get("TRACKING_API_URL", "http://10.0.0.1:8086")


def _clip(video, seconds, start):
    """Trim to a short clip so each probe is fast; returns a temp mp4 path."""
    out = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    cmd = ["ffmpeg", "-y", "-ss", str(start), "-i", video, "-t", str(seconds),
           "-c", "copy", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.getsize(out):
        # -c copy can fail on non-keyframe cuts; fall back to a re-encode.
        subprocess.run(["ffmpeg", "-y", "-ss", str(start), "-i", video, "-t",
                        str(seconds), out], capture_output=True, text=True, check=True)
    return out


def _post_track(url, video_path, prompt, timeout, attempts=3):
    """POST one /track. A recent /reset may have the server mid-relaunch, which drops the
    connection (RemoteDisconnected); wait for /health and retry through that transient state."""
    import requests
    last = None
    for k in range(attempts):
        try:
            with open(video_path, "rb") as vf:
                r = requests.post(f"{url}/track",
                                  files={"file": ("input.mp4", vf, "video/mp4")},
                                  data={"targets": json.dumps([prompt])}, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.ConnectionError as e:
            last = e
            _wait_health(url)
            time.sleep(3)
    raise last


def _coverage(res, prompt):
    nbf = (res.get("video_info") or {}).get("nb_frames") or 0
    dets = (res.get("trajectories") or {}).get(prompt, [])
    valid = [d for d in dets if d.get("cx") is not None]
    return (len(valid) / nbf if nbf else 0.0), len(valid), nbf, valid


def _orbit_spread(valid):
    """Rough spread of the detected centres (px), a quick sanity signal: a real
    orbiting track spreads out; a stuck/degenerate one collapses to a point."""
    if len(valid) < 2:
        return 0.0
    xs = [d["cx"] for d in valid]
    ys = [d["cy"] for d in valid]
    return ((max(xs) - min(xs)) ** 2 + (max(ys) - min(ys)) ** 2) ** 0.5


def _wait_health(url, tries=40):
    import requests
    for _ in range(tries):
        try:
            if requests.get(f"{url}/health", timeout=5).status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


def _reset(url):
    import requests
    try:
        requests.post(f"{url}/reset", timeout=10)
    except Exception:
        pass
    _wait_health(url)
    time.sleep(3)  # settle after the supervisor relaunches, before the next track


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True)
    ap.add_argument("--prompts", nargs="+", help="candidate detection prompts")
    ap.add_argument("--prompts-file", help="one prompt per line (alternative to --prompts)")
    ap.add_argument("--clip-seconds", type=float, default=4.0,
                    help="probe on the first N seconds for speed (0 = whole video)")
    ap.add_argument("--clip-start", type=float, default=0.0)
    ap.add_argument("--api-url", default=DEFAULT_URL)
    ap.add_argument("--reset", action="store_true", help="recycle SAM3 (/reset) between probes; "
                    "OFF by default — /reset exits the server and relies on its supervisor to relaunch")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--out", help="write the ranked results as JSON here")
    a = ap.parse_args()

    prompts = list(a.prompts or [])
    if a.prompts_file:
        prompts += [ln.strip() for ln in open(a.prompts_file) if ln.strip()
                    and not ln.startswith("#")]
    if not prompts:
        sys.exit("!! no prompts given (use --prompts or --prompts-file)")

    probe = _clip(a.video, a.clip_seconds, a.clip_start) if a.clip_seconds > 0 else a.video
    print(f".. sweeping {len(prompts)} prompts on {a.api_url} "
          f"({'clip %.1fs' % a.clip_seconds if a.clip_seconds > 0 else 'whole video'})\n", flush=True)

    rows = []
    for i, p in enumerate(prompts):
        if a.reset and i > 0:
            _reset(a.api_url)
        try:
            res = _post_track(a.api_url, probe, p, a.timeout)
            cov, valid, nbf, dets = _coverage(res, p)
            spread = _orbit_spread(dets)
            rows.append({"prompt": p, "coverage": round(cov, 3), "valid": valid,
                         "frames": nbf, "orbit_spread_px": round(spread, 1)})
            print(f"  {cov*100:5.1f}%  ({valid:3d}/{nbf:3d})  spread={spread:6.1f}px  \"{p}\"",
                  flush=True)
        except Exception as e:
            rows.append({"prompt": p, "coverage": 0.0, "error": str(e)[:120]})
            print(f"  ERROR  \"{p}\": {str(e)[:100]}", flush=True)

    rows.sort(key=lambda r: r.get("coverage", 0.0), reverse=True)
    print("\n=== RANKED (best prompt first) ===")
    for r in rows:
        tag = "  <-- best" if r is rows[0] and r.get("coverage", 0) > 0 else ""
        print(f"  {r.get('coverage',0)*100:5.1f}%  \"{r['prompt']}\"{tag}")
    best = rows[0] if rows and rows[0].get("coverage", 0) > 0 else None
    print(f"\nBEST: {best['prompt']!r} @ {best['coverage']*100:.1f}%" if best
          else "\nNo prompt tracked the object — try different wording (see "
               "docs/object-detection-prompts.md).")

    if a.out:
        json.dump({"video": a.video, "clip_seconds": a.clip_seconds, "ranked": rows},
                  open(a.out, "w"), indent=2)
        print(f".. wrote {a.out}")
    if a.clip_seconds > 0 and probe != a.video:
        os.unlink(probe)


if __name__ == "__main__":
    main()
