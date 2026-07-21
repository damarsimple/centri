"""Does the wording of the detection cue explain LocateAnything's coverage failures?

Tests candidate prompts on the frames LA actually failed on (plus a control set it
already handled), rather than on the whole clip -- the failures are what's in question.
A prompt "works" on a frame if it returns a box of plausible size for that object.
"""
import glob, io, json, os
import numpy as np
import requests

P = "/tmp/claude-1000/-home-damar-centri/509c1604-d98b-48fe-9583-739af875437b/scratchpad/probe"
URL = "http://localhost:8087/segment"

# expected object extent, from the median box each clip's original cue produced
EXPECT = {"turntable-3-rect": 193560.0, "roundabout-4046-final": None}

PROMPTS = {
    "turntable-3-rect": ["red phone", "phone", "red screen", "red rectangle",
                         "smartphone", "red object", "mobile phone"],
    "roundabout-4046-final": ["black ball", "ball", "dark ball", "black sphere",
                              "black circle", "sphere", "round object", "black object"],
}


def median_area(job):
    S = "/home/damar/centri/agent-backend/docs/la-ablation-2026-07-21/trajectories"
    tgt = "red phone" if "turntable" in job else "black ball"
    pts = json.load(open(f"{S}/la_{job}.json"))["trajectories"][tgt]
    a = np.array([(b[2]-b[0])*(b[3]-b[1]) if b else np.nan
                  for b in [q["bbox"] for q in pts]], float)
    return float(np.nanmedian(a))


for job, prompts in PROMPTS.items():
    med = median_area(job)
    fails = sorted(glob.glob(f"{P}/{job}_fail_*.png"))
    ctrls = sorted(glob.glob(f"{P}/{job}_ctrl_*.png"))
    print(f"\n=== {job} ===  (plausible box area = {0.45*med:.0f}-{1.8*med:.0f} px^2)")
    print(f"{'prompt':<16}{'on FAILING frames':>19}{'on control frames':>19}   notes")
    print("-" * 78)
    for pr in prompts:
        res = {}
        for tag, files in [("fail", fails), ("ctrl", ctrls)]:
            hit = miss = bad = 0
            for f in files:
                with open(f, "rb") as fh:
                    r = requests.post(URL, files={"image": fh},
                                      data={"targets": json.dumps([pr])}, timeout=120)
                o = r.json()["objects"].get(pr)
                if not o:
                    miss += 1
                    continue
                x1, y1, x2, y2 = o["bbox"]
                a = (x2-x1)*(y2-y1)
                if 0.45*med < a < 1.8*med:
                    hit += 1
                else:
                    bad += 1
            res[tag] = (hit, bad, miss, len(files))
        h1, b1, m1, n1 = res["fail"]
        h2, b2, m2, n2 = res["ctrl"]
        note = []
        if b1: note.append(f"{b1} wrong-size")
        if m1: note.append(f"{m1} no-detect")
        print(f"{pr:<16}{f'{h1}/{n1}':>19}{f'{h2}/{n2}':>19}   {', '.join(note)}")
