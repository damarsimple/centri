#!/usr/bin/env python3
"""Translate a RENDERED worksheet (.tex) into another language, then it can be compiled to PDF.

Why this exists and `translate_material.py` is not enough: only 17-27% of a rendered worksheet is
the language model's prose (the `sections` of material.<tier>.json). The other 73-83% — "Is this
the right level for you?", the objectives, the worked examples, the checkpoints, "Common traps",
the transfer prompt, "Check your understanding", the honesty box, and every answer in the teacher
key — is deterministic scaffolding emitted by render/report.py as Python string literals. A
teacher panel reads the WORKSHEET, so the worksheet is what has to be translated.

Working on the rendered .tex (rather than adding an `id` string table to the renderer) keeps every
number, figure, layout and page break exactly as the English edition has them, and it covers 100%
of the visible text in one pass.

Safety: the preamble is never sent to the model; the body is translated in section-sized chunks;
and each output is structurally verified against its source (brace balance, \\begin/\\end pairing,
\\includegraphics count, and the full multiset of numbers) before it is written.

Usage:
  python tools/translate_report_tex.py REPORT_DIR [--lang id] [--only student_edition.basic]
"""
import argparse
import json
import os
import pathlib
import re
import sys
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from translate_material import GLOSSARY, LANGS, _glossary_clause  # noqa: E402

BASE = os.environ.get("PI_INFERENCE_URL", "http://192.168.1.205:8083") + "/v1/chat/completions"
KEY = os.environ.get("PI_INFERENCE_API_KEY", "hwanglabyoungdumbandbreak")
MODEL = os.environ.get("PI_MATERIAL_MODEL", "Qwen3.6-35B")

NUM = re.compile(r"-?\d+(?:\.\d+)?")

SYSTEM = (
    "You are a bilingual physics teacher localising a LaTeX worksheet into {lang}. You return "
    "LaTeX, never prose about LaTeX.\n"
    "TRANSLATE: every human-readable word, including text inside \\textbf{{}}, \\emph{{}}, "
    "\\subsection*{{}}, \\section*{{}}, \\caption{{}}, \\item, and table cells.\n"
    "NEVER CHANGE, in any way:\n"
    "1. Any LaTeX command name, brace, bracket, or environment: \\begin{{...}} and \\end{{...}} "
    "must appear the same number of times, in the same order, spelled identically.\n"
    "2. Anything in math mode ($...$, \\[...\\], \\(...\\)) — not one character.\n"
    "3. Any NUMBER, unit or physics symbol anywhere: digits (0.148, 5.79), units (m, s, m/s, "
    "m/s^2, rad/s, Hz, degrees), symbols omega, alpha, pi, a_c, a_t, r, v, T, f. Never translate, "
    "convert, round, recompute, reorder or drop a number.\n"
    "4. File names and labels: \\includegraphics{{...}}, \\label{{...}}, \\ref{{...}}, colour "
    "names, length values (0.8\\textwidth).\n"
    "4a. THE DECIMAL SEPARATOR STAYS A POINT. Write 1.77, never 1,77 — even where the target "
    "language would normally use a comma. The figures on these pages are rendered images whose "
    "axis labels already show points, so comma prose beside point figures contradicts itself on "
    "the same page. This is the single most common way this task is failed.\n"
    "5. Table column specifications and & and \\\\ alignment markers — keep every row the same "
    "shape.\n"
    "Return ONLY the translated LaTeX fragment. No commentary, no code fence."
    "{glossary}"
)


def _call(system, user, max_tokens=12000):
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": 0.2, "max_tokens": max_tokens,
        "chat_template_kwargs": {"enable_thinking": False},
    }).encode()
    req = urllib.request.Request(BASE, data=body, headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {KEY}"})
    with urllib.request.urlopen(req, timeout=900) as resp:
        out = json.loads(resp.read())
    return out["choices"][0]["message"].get("content") or ""


def _strip_fence(s):
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\n?", "", s)
        s = re.sub(r"\n?```$", "", s)
    return s


def _chunks(body):
    """Split the document body at heading boundaries so each request stays small."""
    parts = re.split(r"(?=\\(?:sub)?section\*?\{)", body)
    return [p for p in parts if p.strip()]


def _structurally_same(src, out):
    """Reject a translation that moved any LaTeX scaffolding or any number."""
    problems = []
    for cmd in (r"\\begin\{", r"\\end\{", r"\\includegraphics", r"\\item"):
        a, b = len(re.findall(cmd, src)), len(re.findall(cmd, out))
        if a != b:
            problems.append(f"{cmd} {a}->{b}")
    for env in set(re.findall(r"\\begin\{(\w+\*?)\}", src)):
        a = len(re.findall(rf"\\begin{{{re.escape(env)}}}", src))
        b = len(re.findall(rf"\\begin{{{re.escape(env)}}}", out))
        if a != b:
            problems.append(f"env {env} {a}->{b}")
    if src.count("{") - src.count("}") != out.count("{") - out.count("}"):
        problems.append("brace balance")
    if src.count("&") != out.count("&"):
        problems.append(f"& {src.count('&')}->{out.count('&')}")
    a, b = sorted(NUM.findall(src)), sorted(NUM.findall(out))
    if a != b:
        miss = [x for x in a if x not in b][:4]
        add = [x for x in b if x not in a][:4]
        problems.append(f"numbers missing={miss} added={add}")
    return problems


def translate_tex(path, lang, lang_name):
    text = pathlib.Path(path).read_text()
    marker = "\\begin{document}"
    i = text.find(marker)
    if i == -1:
        return None, ["no \\begin{document}"]
    preamble, body = text[:i + len(marker)], text[i + len(marker):]
    tail = ""
    j = body.rfind("\\end{document}")
    if j != -1:
        body, tail = body[:j], body[j:]

    out_parts, failures = [], []
    for n, chunk in enumerate(_chunks(body), 1):
        if not re.search(r"[A-Za-z]{3,}", re.sub(r"\\[a-zA-Z]+|\{|\}", " ", chunk)):
            out_parts.append(chunk)                      # nothing human-readable in it
            continue
        best = None
        for attempt in range(2):
            got = _strip_fence(_call(SYSTEM.format(lang=lang_name,
                                                   glossary=_glossary_clause(lang)), chunk))
            probs = _structurally_same(chunk, got)
            if not probs:
                best = got
                break
            best = best or got
            if attempt == 1:
                failures.append(f"chunk {n}: {probs[:3]} (kept English)")
                best = chunk                             # safest: leave that chunk untranslated
        out_parts.append(best)
    return preamble + "".join(out_parts) + tail, failures


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("report_dir")
    ap.add_argument("--lang", default="id", choices=sorted(LANGS))
    ap.add_argument("--only", help="basename filter, e.g. student_edition.basic")
    a = ap.parse_args()
    d = pathlib.Path(a.report_dir)
    lang_name = LANGS[a.lang]
    targets = sorted(p for p in d.glob("*.tex") if not p.name.startswith("translated_"))
    if a.only:
        targets = [p for p in targets if p.name.startswith(a.only)]
    if not targets:
        sys.exit(f"!! no .tex to translate in {d}")
    for p in targets:
        out, failures = translate_tex(p, a.lang, lang_name)
        if out is None:
            print(f"  {p.name}: SKIPPED ({failures})")
            continue
        outp = d / f"translated_{p.stem}.{a.lang}.tex"
        outp.write_text(out)
        flag = "" if not failures else f"  ({len(failures)} chunk(s) left English)"
        print(f"  {p.name} -> {outp.name}{flag}")
        for f in failures[:3]:
            print(f"        {f}")


if __name__ == "__main__":
    main()
