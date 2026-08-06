#!/usr/bin/env python3
"""Translate generated learning material to another language (default: Bahasa Indonesia).

Centri's material aligns with the P-MAGIC line, whose study and teacher panel are
Bahasa Indonesia — so a bilingual deliverable is on the roadmap (#9). This translates
the grounded English material.{tier}.json sections with the same local 35B the pipeline
uses, PRESERVING every number, unit, and symbol exactly (only the prose is translated,
never a measured value), and keeps the English section keys so the output is structurally
identical and still rendered/scored by the existing tooling. A `section_titles_<lang>`
map carries the translated headings for display.

Usage:
  python tools/translate_material.py analysis_output/data/material.basic.json
  python tools/translate_material.py --workspace analysis_output/data   # all 3 tiers
  python tools/translate_material.py material.basic.json --lang ms       # Bahasa Melayu
"""
import argparse
import json
import os
import pathlib
import re
import sys
import urllib.request

BASE = os.environ.get("PI_INFERENCE_URL", "http://192.168.1.205:8083") + "/v1/chat/completions"
KEY = os.environ.get("PI_INFERENCE_API_KEY", "hwanglabyoungdumbandbreak")
MODEL = os.environ.get("PI_MATERIAL_MODEL", "Qwen3.6-35B")

LANGS = {"id": "Bahasa Indonesia", "ms": "Bahasa Melayu", "zh": "Chinese", "ja": "Japanese"}

# A fixed term list, so every tier and every clip says the SAME word for the same quantity. Left
# free, the model picks "radius" in the beginner passage and "jari-jari" in the intermediate one —
# a reader climbing the tiers then meets two names for one idea, which is precisely the confusion
# the tiers exist to avoid. School register (jari-jari, kecepatan sudut) over loanwords.
GLOSSARY = {
    "id": [("radius", "jari-jari"), ("angle", "sudut"), ("radian", "radian"),
           ("angular velocity", "kecepatan sudut"), ("linear velocity", "kecepatan linear"),
           ("centripetal acceleration", "percepatan sentripetal"), ("period", "periode"),
           ("frequency", "frekuensi"), ("turn rate", "laju putaran"),
           ("full turn", "putaran penuh"), ("clockwise", "searah jarum jam"),
           ("counter-clockwise", "berlawanan arah jarum jam"), ("speed", "kelajuan"),
           ("inward pull", "tarikan ke dalam")],
}

SYSTEM = (
    "You are a bilingual physics teacher translating a short learning passage about circular "
    "motion into {lang}. Translate ONLY the prose. HARD RULES:\n"
    "1. Every NUMBER, unit, and symbol stays EXACTLY as written and in place: digits (0.148, 5.79), "
    "units (m, s, m/s, m/s^2, rad/s, degrees, °), and the physics symbols ω, α, π, ², ·, a_c, a_t, "
    "r, v, T, f. Never translate, convert, round, recompute, or drop a number or symbol.\n"
    "2. Translate technical terms naturally for a student in {lang} (e.g. angular velocity, "
    "centripetal acceleration, radius), but keep the parenthetical symbol if the English has one.\n"
    "2a. A TERM BEING DEFINED IS PROSE, NOT A KEY — translate it too. The beginner passage defines "
    "vocabulary as a list of 'term: explanation' lines ('angular velocity: how fast that angle "
    "grows'). The headword before the colon MUST be translated like everything else, with the "
    "English kept once in brackets so a bilingual class can follow both: "
    "'kecepatan sudut (angular velocity): ...'. Leaving the headword in English defeats the "
    "passage — it is the tier written for the reader with the least English.\n"
    "2b. Use the ACTIVE voice for an object's own motion. In Bahasa Indonesia an object that "
    "sweeps round a centre 'menyapu' or 'bergerak melingkar' — it is never 'disapu', which says "
    "something else swept it (sapu = broom).\n"
    "3. Preserve paragraph breaks and meaning faithfully; do not add, remove, or reorder content, "
    "and never invent a number or fact not in the source.\n"
    "4. Plain Unicode only — never LaTeX or a backslash.\n"
    "Return ONLY a JSON object mapping each given section key (unchanged, in English) to its "
    "translated prose, plus a key \"__titles__\" mapping each section key to a short {lang} "
    "translation of that heading. No prose outside the JSON."
    "{glossary}"
)


def _glossary_clause(lang):
    """The fixed EN->target term list, as a prompt clause. Empty for languages without one."""
    pairs = GLOSSARY.get(lang)
    if not pairs:
        return ""
    return ("\n5. USE EXACTLY THESE TERMS — the same word every time, across every tier, so a "
            "reader moving up the levels never meets two names for one quantity:\n"
            + "\n".join(f"   {en} -> {tgt}" for en, tgt in pairs))


def _call(system, user, max_tokens=8000):
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": 0.2, "max_tokens": max_tokens,
        "chat_template_kwargs": {"enable_thinking": False},
    }).encode()
    req = urllib.request.Request(BASE, data=body, headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {KEY}"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        out = json.loads(resp.read())
    return out["choices"][0]["message"].get("content") or ""


def _parse_json(s):
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-z]*\n?|\n?```$", "", s)
    i, j = s.find("{"), s.rfind("}")
    return json.loads(s[i:j + 1])


def translate(material, lang_name, lang=None):
    secs = material.get("sections", {})
    if not secs:
        return None
    user = ("Translate these section values into " + lang_name + ". Keys are English and stay "
            "unchanged; also return the \"__titles__\" heading map.\n\n"
            + json.dumps(secs, ensure_ascii=False, indent=2))
    obj = _parse_json(_call(SYSTEM.format(lang=lang_name,
                                      glossary=_glossary_clause(lang)), user))
    titles = obj.pop("__titles__", {})
    # Keep only the known section keys; drop anything the model hallucinated.
    translated = {k: obj[k] for k in secs if k in obj and isinstance(obj[k], str)}
    missing = [k for k in secs if k not in translated]
    return translated, titles, missing


def _one(path, lang, lang_name, out_dir=None):
    material = json.loads(pathlib.Path(path).read_text())
    res = translate(material, lang_name, lang)
    if not res:
        print(f"  {path}: no sections, skipped")
        return
    translated, titles, missing = res
    out = dict(material)
    out["sections"] = translated
    out[f"section_titles_{lang}"] = titles
    out["language"] = lang
    name = re.sub(r"\.json$", f".{lang}.json", pathlib.Path(path).name)
    outp = str(pathlib.Path(out_dir) / name) if out_dir else re.sub(r"\.json$", f".{lang}.json", str(path))
    pathlib.Path(outp).write_text(json.dumps(out, indent=2, ensure_ascii=False))
    flag = "" if not missing else f"  (MISSING {missing})"
    print(f"  {pathlib.Path(path).name} -> {pathlib.Path(outp).name}  "
          f"({len(translated)}/{len(material.get('sections',{}))} sections){flag}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("material", nargs="?", help="a material.{tier}.json to translate")
    ap.add_argument("--workspace", help="a data dir; translates material.{basic,intermediate,advanced}.json")
    ap.add_argument("--lang", default="id", choices=sorted(LANGS))
    ap.add_argument("--out-dir", help="write outputs here instead of beside the input "
                    "(use when the input dir is read-only, e.g. a root-owned workspace)")
    a = ap.parse_args()
    lang_name = LANGS[a.lang]
    if a.out_dir:
        pathlib.Path(a.out_dir).mkdir(parents=True, exist_ok=True)

    files = []
    if a.workspace:
        for t in ("basic", "intermediate", "advanced"):
            p = pathlib.Path(a.workspace) / f"material.{t}.json"
            if p.exists():
                files.append(str(p))
    elif a.material:
        files = [a.material]
    if not files:
        sys.exit("!! nothing to translate (pass a material.json or --workspace DIR)")

    print(f".. translating {len(files)} file(s) to {lang_name} via {MODEL}\n")
    for f in files:
        _one(f, a.lang, lang_name, a.out_dir)


if __name__ == "__main__":
    main()
