#!/usr/bin/env python3
"""Reference-comparison eval. Treats the English references as a classified gold:
the PROSE learning-material sources are reorganized into our 5-section format (like
OpenStax §6.2) and form the consistent gold; the question/slide/lab sources are kept
as SEPARATE raw buckets (they measure something different — question/figure relevance,
not material relevance). Reports:

  A. Reorganized prose gold   — per-section + whole-passage BERTScore (mean ± SD),
                                plus the OpenStax-only number (the official 0.840).
  B. Reorganized vs RAW       — same prose set, scored both ways → the effect of
                                reorganizing (answers "show two results").
  C. Separate buckets (raw)   — slides / worksheets / labs, whole-passage, reported
                                distinctly.

Raw long PDFs are reduced to their most centripetal-dense ~320-word window.
Metric: raw BERTScore F1 (no baseline rescale), comparable to the prose material eval.

Usage:
  .venv-eval/bin/python tools/run_reference_comparison_eval.py \
      --materials material_work/_eval/material_*.json \
      --reorg-dir material_work/_reference/english_reorganized \
      --openstax-json material_work/_reference/openstax_6.2/reference.json \
      --openstax-raw ../refs/Chapter6_Section2.pdf \
      --raw-dir material_work/_reference/english \
      --out material_work/_eval/reference_comparison_report.md
"""
import argparse, glob, json, pathlib, re, statistics, subprocess
from bert_score import score as bertscore

SECTIONS = ["Scenario", "The variables we measured", "How the variables are related",
            "What the video shows over time", "Reading the figures"]
_NORM = {"ω": "omega", "α": "alpha", "θ": "theta", "Δ": "delta", "π": "pi",
         "²": "^2", "³": "^3", "·": "*", "×": "x", "≈": "approx", "→": "to",
         "−": "-", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"}
KW = re.compile(r"centripetal|circular|angular|accelerat|radius|velocit|"
                r"rotat|tangent|omega|\bv\^?2\b|period", re.I)

# Classification of the raw english/ sources into buckets (prose ones are reorganized
# in english_reorganized/; non-prose stay raw here).
PROSE = ["01_en_mit", "07_en_arxiv", "16_en_emu", "18_en_alabama", "30_en_pmt",
         "15_en_usna", "23_en_flippingphysics_intro", "24_en_flippingphysics_deriv"]
BUCKETS = {
    "slides":    ["13_en_uiuc", "14_en_osu", "20_en_sydney", "21_en_hawaii"],
    "worksheet": ["19_en_coloradomesa", "25_en_bu", "26_en_aplusphysics", "29_en_ubc"],
    "lab":       ["22_en_oklahoma", "28_en_usc"],
}


def _norm(s):
    for k, v in _NORM.items():
        s = s.replace(k, v)
    return s


def load_sections(path):
    d = json.loads(pathlib.Path(path).read_text())
    secs = d.get("sections", d)
    return {k: _norm(secs.get(k, "")) for k in SECTIONS}


def load_material(path):
    return load_sections(path)


def keyword_window(text, n=320):
    words = _norm(text).split()
    if len(words) <= n:
        return " ".join(words)
    hits = [1 if KW.search(w) else 0 for w in words]
    pref = [0]
    for h in hits:
        pref.append(pref[-1] + h)
    best_i, best = 0, -1
    for i in range(0, len(words) - n + 1, 20):
        sc = pref[i + n] - pref[i]
        if sc > best:
            best, best_i = sc, i
    return " ".join(words[best_i:best_i + n])


def pdf_window(path):
    out = subprocess.run(["pdftotext", "-q", str(path), "-"],
                         capture_output=True, text=True, timeout=60).stdout
    return keyword_window(out)


def _t(s, n=320):
    return " ".join(s.split()[:n])


def bsf1(cands, refs):
    _, _, F = bertscore([_t(c) for c in cands], [_t(r) for r in refs],
                        lang="en", rescale_with_baseline=False)
    return F.tolist()


def msd(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return (None, None)
    return (statistics.mean(xs), statistics.pstdev(xs) if len(xs) > 1 else 0.0)


def whole(secs):
    return " ".join(secs.get(s, "") for s in SECTIONS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--materials", nargs="+", required=True)
    ap.add_argument("--reorg-dir", required=True)
    ap.add_argument("--openstax-json", required=True)
    ap.add_argument("--openstax-raw", required=True)
    ap.add_argument("--raw-dir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    mat_paths = []
    for m in args.materials:
        mat_paths += sorted(glob.glob(m)) if any(c in m for c in "*?[") else [m]
    mat_paths = [p for p in mat_paths if "report" not in pathlib.Path(p).stem]
    mats = [(pathlib.Path(p).stem.replace("material_", ""), load_material(p)) for p in mat_paths]
    cand_whole = [whole(s) for _, s in mats]

    # ----- prose-gold references (reorganized, 5-section) -----
    reorg = {"openstax_6.2": load_sections(args.openstax_json)}
    for name in PROSE:
        p = pathlib.Path(args.reorg_dir) / f"{name}.json"
        if p.exists():
            reorg[name] = load_sections(p)
    prose_names = list(reorg)

    # raw counterpart text for the SAME prose sources
    raw_prose = {"openstax_6.2": pdf_window(args.openstax_raw)}
    for name in PROSE:
        raw_prose[name] = pdf_window(pathlib.Path(args.raw_dir) / f"{name}.pdf")

    # A. reorganized prose gold: whole + per-section, averaged over prose refs
    # whole-passage F1[candidate][ref]
    Wre = {c: {} for c, _ in mats}
    for ref in prose_names:
        rw = whole(reorg[ref])
        for (c, _), f in zip(mats, bsf1(cand_whole, [rw] * len(mats))):
            Wre[c][ref] = f
    # per-section F1 averaged over prose refs (candidate[sec] vs ref[sec])
    sec_scores = {s: [] for s in SECTIONS}
    for ref in prose_names:
        for s in SECTIONS:
            rsec = reorg[ref].get(s, "").strip()
            if not rsec:
                continue
            cs = [m.get(s, "") for _, m in mats]
            sec_scores[s] += bsf1(cs, [rsec] * len(mats))

    # B. reorganized vs raw, per prose ref (set means)
    Wraw = {c: {} for c, _ in mats}
    for ref in prose_names:
        for (c, _), f in zip(mats, bsf1(cand_whole, [raw_prose[ref]] * len(mats))):
            Wraw[c][ref] = f

    # C. separate buckets (raw) — keep per-reference mean ± SD too
    bucket_scores = {}
    bucket_per_ref = {}
    for bname, refs in BUCKETS.items():
        vals = []
        for ref in refs:
            pf = pathlib.Path(args.raw_dir) / f"{ref}.pdf"
            if not pf.exists():
                continue
            rw = pdf_window(pf)
            rv = bsf1(cand_whole, [rw] * len(mats))
            vals += rv
            bucket_per_ref[ref] = {"bucket": bname, "mean": msd(rv)[0], "sd": msd(rv)[1]}
        bucket_scores[bname] = msd(vals)

    # ----- aggregates -----
    os_whole = msd([Wre[c]["openstax_6.2"] for c, _ in mats])
    reorg_set_mean = msd([v for c, _ in mats for v in Wre[c].values()])
    raw_set_mean = msd([v for c, _ in mats for v in Wraw[c].values()])
    # per-candidate mean over reorganized prose gold
    per_cand_reorg = {c: msd(list(Wre[c].values()))[0] for c, _ in mats}

    L = ["# Reference-comparison eval — reorganized prose gold, raw, and separate buckets\n",
         "English references are **classified**. The prose learning-material sources are "
         "**reorganized into our 5-section format** (the same treatment as OpenStax §6.2) and "
         "form the consistent gold; question / slide / lab sources are kept as **separate raw "
         "buckets** (they measure question/figure relevance, not material relevance). Metric: "
         "raw BERTScore F1.\n",
         f"Candidates: {len(mats)}. Prose gold refs (reorganized): {len(prose_names)}. "
         f"Buckets: {', '.join(f'{k}={len(v)}' for k,v in BUCKETS.items())}.\n"]

    # A
    L.append("## A. Reorganized prose gold (the consistent gold)\n")
    L.append("| Measure | BERTScore F1 |")
    L.append("|---|---|")
    L.append(f"| OpenStax §6.2 only (official headline) | **{os_whole[0]:.3f} ± {os_whole[1]:.3f}** |")
    L.append(f"| Whole prose gold set (mean over {len(prose_names)} reorganized refs) | "
             f"**{reorg_set_mean[0]:.3f} ± {reorg_set_mean[1]:.3f}** |")
    L.append("\n**Per-section (mean ± SD over candidates × reorganized prose refs):**\n")
    L.append("| Section | F1 mean ± SD | n |")
    L.append("|---|---|---|")
    for s in SECTIONS:
        m, sd = msd(sec_scores[s])
        L.append(f"| {s} | {m:.3f} ± {sd:.3f} | {len(sec_scores[s])} |"
                 if m is not None else f"| {s} | — | 0 |")

    # B  (per-reference mean ± SD across candidates, both reorganized and raw)
    per_ref = {}
    L.append("\n## B. Reorganized vs raw — same prose sources, mean ± SD (two results)\n")
    L.append("| Prose reference | reorganized F1 (M ± SD) | raw F1 (M ± SD) | Δ |")
    L.append("|---|---|---|---|")
    for ref in prose_names:
        rem, res = msd([Wre[c][ref] for c, _ in mats])
        ram, ras = msd([Wraw[c][ref] for c, _ in mats])
        per_ref[ref] = {"reorg_mean": rem, "reorg_sd": res, "raw_mean": ram, "raw_sd": ras}
        L.append(f"| {ref} | {rem:.3f} ± {res:.3f} | {ram:.3f} ± {ras:.3f} | {rem-ram:+.3f} |")
    L.append(f"| **set mean** | **{reorg_set_mean[0]:.3f} ± {reorg_set_mean[1]:.3f}** | "
             f"**{raw_set_mean[0]:.3f} ± {raw_set_mean[1]:.3f}** | "
             f"**{reorg_set_mean[0]-raw_set_mean[0]:+.3f}** |")

    # C
    L.append("\n## C. Separate buckets (raw, reported distinctly — NOT the material gold)\n")
    L.append("| Bucket | whole-passage F1 mean ± SD | n refs |")
    L.append("|---|---|---|")
    for bname, refs in BUCKETS.items():
        m, sd = bucket_scores[bname]
        L.append(f"| {bname} | {m:.3f} ± {sd:.3f} | {len(refs)} |")
    L.append("\n**Per-reference (raw, mean ± SD across candidates):**\n")
    L.append("| Reference | bucket | F1 (M ± SD) |")
    L.append("|---|---|---|")
    for ref, v in bucket_per_ref.items():
        L.append(f"| {ref} | {v['bucket']} | {v['mean']:.3f} ± {v['sd']:.3f} |")

    L.append("\n> **Reading it:** (A) reorganizing makes every prose reference comparable "
             "section-by-section, so the gold is a real *set*, not one section. (B) reorganized "
             "scores sit above raw — reorganization aligns format, removing the scope/length "
             "noise of whole PDFs. (C) question/slide/lab sources are reported on their own; "
             "they describe problems and figures, not five-section learning material, so they "
             "are diagnostics, not the gold. Same floor caveat as the prose eval (shared domain "
             "vocabulary).")

    out = pathlib.Path(args.out)
    out.write_text("\n".join(L) + "\n")
    json.dump({"openstax_only": {"mean": os_whole[0], "sd": os_whole[1]},
               "reorg_set": {"mean": reorg_set_mean[0], "sd": reorg_set_mean[1]},
               "raw_set": {"mean": raw_set_mean[0], "sd": raw_set_mean[1]},
               "per_section": {s: msd(sec_scores[s]) for s in SECTIONS},
               "buckets": bucket_scores,
               "per_ref": per_ref,
               "bucket_per_ref": bucket_per_ref,
               "per_cand_reorg": per_cand_reorg,
               "prose_refs": prose_names},
              open(out.with_suffix(".json"), "w"), indent=2)
    print(f"openstax-only   = {os_whole[0]:.3f} ± {os_whole[1]:.3f}")
    print(f"reorg set mean  = {reorg_set_mean[0]:.3f} ± {reorg_set_mean[1]:.3f}")
    print(f"raw set mean    = {raw_set_mean[0]:.3f} ± {raw_set_mean[1]:.3f}")
    for b, (m, sd) in bucket_scores.items():
        print(f"bucket {b:9s} = {m:.3f} ± {sd:.3f}")
    print(f"report -> {out}")


if __name__ == "__main__":
    main()
