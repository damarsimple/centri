#!/usr/bin/env python3
"""Reorganize an authentic physics reference (PDF) into our fixed 5-section format,
so it can be scored section-by-section the same way OpenStax §6.2 is. Grounded
strictly on the source text — the LLM condenses/reorganizes, it does NOT add facts.

Output matches material_work/_reference/openstax_6.2/reference.json:
  {"source": <label>, "sections": {<5 sections>}}

Usage:
  .venv-eval/bin/python tools/build_reference.py \
      --pdf material_work/_reference/english/01_en_mit.pdf \
      --out material_work/_reference/english_reorganized/01_en_mit.json
"""
import argparse, json, pathlib, re, subprocess, requests

URL = "http://192.168.1.205:8083/v1/chat/completions"
KEY = "hwanglabyoungdumbandbreak"
MODEL = "Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf"

SECTIONS = ["Scenario", "The variables we measured", "How the variables are related",
            "What the video shows over time", "Reading the figures"]

PROMPT = """You are reorganizing an AUTHENTIC physics reference about centripetal / \
circular acceleration into a fixed 5-section format, to serve as a neutral scoring \
reference. Use ONLY content present in the SOURCE below — condense and reorganize it \
into clear prose. Do NOT add facts, numbers, or examples that are not in the source. \
If the source does not really cover a section, write ONE short honest sentence noting \
what it focuses on instead (do not fabricate content).

The five sections (each ~60-120 words of plain prose):
1. "Scenario" — the physical setup or context the source uses (e.g. a car on a curve, \
an object on a circle).
2. "The variables we measured" — the quantities it defines: radius r, speed v, \
centripetal acceleration a_c, angular velocity omega, period T, frequency f, etc.
3. "How the variables are related" — the formulas and relationships it states \
(a_c = v^2/r = omega^2 r, v = omega r, T = 2 pi / omega, ...).
4. "What the video shows over time" — any time-dependent / process description, or how \
its worked example unfolds (the source has no video; map to its dynamic/example content).
5. "Reading the figures" — what its diagrams or figures convey.

Output STRICT JSON only, no prose around it, with exactly these five keys:
{"Scenario": "...", "The variables we measured": "...", "How the variables are related": "...", "What the video shows over time": "...", "Reading the figures": "..."}

SOURCE (%(label)s):
%(text)s
"""


def pdf_text(path, max_words=4000):
    out = subprocess.run(["pdftotext", "-q", str(path), "-"],
                         capture_output=True, text=True, timeout=60).stdout
    words = out.split()
    return " ".join(words[:max_words])


def call_llm(prompt):
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 3000, "temperature": 0.2,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    r = requests.post(URL, headers={"Authorization": f"Bearer {KEY}"},
                      json=payload, timeout=300)
    r.raise_for_status()
    msg = r.json()["choices"][0]["message"]
    return (msg.get("content") or "").strip()


def parse_json(txt):
    # strip code fences / find the JSON object
    txt = re.sub(r"^```(?:json)?|```$", "", txt.strip(), flags=re.M).strip()
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        raise ValueError("no JSON object in LLM output")
    d = json.loads(m.group(0))
    return {k: d.get(k, "").strip() for k in SECTIONS}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", default=None)
    args = ap.parse_args()
    label = args.label or pathlib.Path(args.pdf).stem
    text = pdf_text(args.pdf)
    out = call_llm(PROMPT % {"label": label, "text": text})
    sections = parse_json(out)
    miss = [s for s in SECTIONS if not sections.get(s)]
    rec = {"source": label, "sections": sections}
    op = pathlib.Path(args.out)
    op.parent.mkdir(parents=True, exist_ok=True)
    op.write_text(json.dumps(rec, indent=2, ensure_ascii=False))
    wc = {s: len(sections[s].split()) for s in SECTIONS}
    print(f"{label}: " + " | ".join(f"{s.split()[0]}={wc[s]}w" for s in SECTIONS)
          + (f"  MISSING={miss}" if miss else ""))


if __name__ == "__main__":
    main()
