#!/usr/bin/env python3
"""Block until one job is terminal, then dump its status + stats. Usage: wait_job.py <job_id>"""
import json, sys, time, urllib.request

API = "http://10.0.0.1:8088"
KEY = "changeme-random-secret-key-12345"
jid = sys.argv[1]


def get(path):
    req = urllib.request.Request(API + path, headers={"X-API-Key": KEY})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


deadline = time.time() + 2400  # 40 min safety
last = None
while time.time() < deadline:
    try:
        s = get(f"/status/{jid}")
        stt = s.get("status")
        cur = f"{stt}/{s.get('progress_pct','?')}% {s.get('step','')}"
        if cur != last:
            print(f"[{time.strftime('%H:%M:%S')}] {cur}", flush=True)
            last = cur
        if stt in ("done", "completed", "failed", "error"):
            print(f"\nTERMINAL: {stt}", flush=True)
            if stt in ("done", "completed"):
                res = get(f"/result/{jid}")
                print("STATS_JSON_BEGIN")
                print(json.dumps(res.get("stats"), indent=2))
                print("STATS_JSON_END")
            else:
                print("MESSAGE:", s.get("message"))
            break
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] poll err: {e}", flush=True)
    time.sleep(30)
