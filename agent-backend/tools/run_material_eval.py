#!/usr/bin/env python3
"""Material-relevance evaluation: Centri's generated learning material vs an
authentic textbook reference (OpenStax College Physics 6.2), via BERTScore, plus
semantic diversity across the generated set.

Reports per-section and overall BERTScore F1 as mean +/- SD (the candidate's
section scored against the SAME section of the reference), and an STS diversity
score across the material passages.

Usage:
  .venv-eval/bin/python tools/run_material_eval.py \
      --ref material_work/_reference/openstax_6.2/reference.json \
      --materials material_work/_eval/*.json \
      --out material_work/_eval/material_eval_report.md
"""
import argparse, json, glob, statistics, pathlib
from bert_score import score as bertscore
from sentence_transformers import SentenceTransformer, util

SECTIONS = [
    "Scenario",
    "The variables we measured",
    "How the variables are related",
    "What the video shows over time",
    "Reading the figures",
]


_NORM = {"ω": "omega", "α": "alpha", "θ": "theta", "Δ": "delta", "π": "pi",
         "²": "^2", "³": "^3", "·": "*", "×": "x", "≈": "approx", "→": "to",
         "−": "-", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", " ": " "}


def _norm(s):
    if not isinstance(s, str):
        return ""
    for k, v in _NORM.items():
        s = s.replace(k, v)
    return s


# ---- pure-Python BLEU + ROUGE (complementary n-gram overlap columns) ----------
# The lab .venv-eval has no sacrebleu/rouge/nltk/evaluate and installs there aren't
# assumed, so these are self-contained. They are complementary diagnostics, NOT the
# headline metric (BERTScore stays the headline, comparable to P-MAGIC).
import math, re, collections


def _tok(s):
    return re.findall(r"[a-z0-9]+", _norm(s).lower())


def _ngrams(toks, n):
    return collections.Counter(tuple(toks[i:i + n]) for i in range(len(toks) - n + 1))


def sentence_bleu(cand, ref, max_n=4):
    """BLEU-4 with a brevity penalty and add-1 smoothing on higher-order n-grams."""
    c, r = _tok(cand), _tok(ref)
    if not c or not r:
        return 0.0
    w, log_sum = 1.0 / max_n, 0.0
    for n in range(1, max_n + 1):
        cc, rc = _ngrams(c, n), _ngrams(r, n)
        overlap = sum(min(v, rc[g]) for g, v in cc.items())
        total = max(1, sum(cc.values()))
        smooth = 0.0 if n == 1 else 1.0  # add-1 for n>1 so a single miss isn't a hard zero
        log_sum += w * math.log(max((overlap + smooth) / (total + smooth), 1e-9))
    bp = 1.0 if len(c) > len(r) else math.exp(1 - len(r) / max(1, len(c)))
    return bp * math.exp(log_sum)


def rouge_n(cand, ref, n):
    """ROUGE-N F1 (n-gram recall/precision harmonic mean)."""
    c, r = _ngrams(_tok(cand), n), _ngrams(_tok(ref), n)
    overlap = sum(min(v, c[g]) for g, v in r.items())
    prec = overlap / max(1, sum(c.values()))
    rec = overlap / max(1, sum(r.values()))
    return 2 * prec * rec / max(1e-9, prec + rec)


def _lcs_len(a, b):
    dp = [0] * (len(b) + 1)
    for x in a:
        prev = 0
        for j, y in enumerate(b, 1):
            cur = dp[j]
            dp[j] = prev + 1 if x == y else max(dp[j], dp[j - 1])
            prev = cur
    return dp[-1]


def rouge_l(cand, ref):
    """ROUGE-L F1 (longest-common-subsequence overlap)."""
    c, r = _tok(cand), _tok(ref)
    if not c or not r:
        return 0.0
    lcs = _lcs_len(c, r)
    prec, rec = lcs / max(1, len(c)), lcs / max(1, len(r))
    return 2 * prec * rec / max(1e-9, prec + rec)


def load_sections(path):
    d = json.loads(pathlib.Path(path).read_text())
    secs = d.get("sections", d)
    return {k: _norm(v) for k, v in secs.items() if isinstance(v, str)}


def msd(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return (None, None)
    m = statistics.mean(xs)
    s = statistics.pstdev(xs) if len(xs) > 1 else 0.0
    return (m, s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--materials", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    mat_paths = []
    for m in args.materials:
        mat_paths += sorted(glob.glob(m)) if any(c in m for c in "*?[") else [m]
    mat_paths = [p for p in mat_paths if "report" not in pathlib.Path(p).stem]
    ref = load_sections(args.ref)
    ref_full = " ".join((ref.get(s) or "") for s in SECTIONS)
    mats = [(pathlib.Path(p).stem.replace("material_", ""), load_sections(p)) for p in mat_paths]
    print(f"ref sections={len(ref)}  candidates={len(mats)}")

    # Raw BERTScore (NOT baseline-rescaled) to stay comparable with P-MAGIC's reported
    # numbers and the rest of our eval. Truncate to a safe word count — RoBERTa caps at
    # 512 tokens and the py3.14 tokenizer build errors on over-long input.
    def _t(s, n=320):
        return " ".join(s.split()[:n])

    def bsprf(cands, refs):
        """Return (P, R, F1) lists — all three BERTScore components, to mirror
        P-MAGIC's Table 3 (BERT P / R / F1), not just F1."""
        cands = [_t(c) for c in cands]
        refs = [_t(r) for r in refs]
        P, R, F = bertscore(cands, refs, lang="en", rescale_with_baseline=False)
        return P.tolist(), R.tolist(), F.tolist()

    def bsf1(cands, refs):
        return bsprf(cands, refs)[2]

    # PRIMARY: whole-document relevance — full material vs full reference, per object.
    # Keep P and R as well so we can report the full BERTScore triple like P-MAGIC.
    whole, whole_p, whole_r = {}, {}, {}
    cands_full = [" ".join((secs.get(s) or "") for s in SECTIONS) for _, secs in mats]
    wp, wr, wf = bsprf(cands_full, [ref_full] * len(mats))
    for (name, _), pv, rv, fv in zip(mats, wp, wr, wf):
        whole[name] = fv; whole_p[name] = pv; whole_r[name] = rv

    # DIAGNOSTIC: per-section BERTScore, candidate[sec] vs reference[sec].
    f1 = {name: {} for name, _ in mats}
    for sec in SECTIONS:
        cands, names = [], []
        for name, secs in mats:
            c = (secs.get(sec) or "").strip()
            if c and ref.get(sec):
                cands.append(c); names.append(name)
        if not cands:
            continue
        for name, fv in zip(names, bsf1(cands, [ref[sec]] * len(cands))):
            f1[name][sec] = fv

    # Diversity: embed each object's full material (sections joined), pairwise cosine.
    embedder = SentenceTransformer("all-MiniLM-L6-v2")
    passages = [" ".join((secs.get(s) or "") for s in SECTIONS) for _, secs in mats]
    emb = embedder.encode(passages, convert_to_tensor=True, normalize_embeddings=True)
    sims = []
    for i in range(len(passages)):
        for j in range(i + 1, len(passages)):
            sims.append(float(util.cos_sim(emb[i], emb[j])))
    mean_sim, _ = msd(sims)
    diversity = (1 - mean_sim) if mean_sim is not None else None

    # ---- report ----
    wm, ws_ = msd(list(whole.values()))
    L = ["# Material evaluation — Centri learning material vs authentic textbook reference\n",
         "Reference: **OpenStax College Physics §6.2 (Centripetal Acceleration)**, reorganized",
         "into our format. Candidate: each object's generated learning material.",
         "Metric: raw BERTScore F1 (comparable to P-MAGIC).\n"]

    # Whole-document relevance per object (the headline)
    L.append("## Material relevance — whole passage vs reference (mean ± SD across objects)\n")
    L.append("| Object | BERTScore F1 |")
    L.append("|---|---|")
    for name, _ in mats:
        L.append(f"| {name} | {whole[name]:.3f} |")
    L.append(f"| **mean ± SD** | **{wm:.3f} ± {ws_:.3f}** |")

    # Per-section table (mean +/- SD across objects)
    L.append("\n## BERTScore F1 by section (diagnostic; mean ± SD across objects)\n")
    L.append("| Section | mean ± SD | n |")
    L.append("|---|---|---|")
    for sec in SECTIONS:
        vals = [f1[name].get(sec) for name, _ in mats]
        m, s = msd(vals)
        nn = len([v for v in vals if v is not None])
        L.append(f"| {sec} | {m:.3f} ± {s:.3f} | {nn} |" if m is not None else f"| {sec} | — | 0 |")

    # Per-object table
    L.append("\n## BERTScore F1 by object (mean ± SD across sections)\n")
    L.append("| Object | mean ± SD |")
    L.append("|---|---|")
    for name, _ in mats:
        m, s = msd(list(f1[name].values()))
        L.append(f"| {name} | {m:.3f} ± {s:.3f} |")

    # Overall + diversity (the small autoeval summary, at the end)
    allvals = [v for name, _ in mats for v in f1[name].values()]
    om, os_ = msd(allvals)
    # Full BERTScore triple (P / R / F1) on the whole passage, to mirror P-MAGIC Table 3.
    pm, ps_ = msd(list(whole_p.values()))
    rm, rs_ = msd(list(whole_r.values()))
    L.append("\n## BERTScore triple — whole passage vs reference (mean ± SD, n=%d)\n" % len(mats))
    L.append("| Metric | mean ± SD |")
    L.append("|---|---|")
    L.append(f"| BERT Precision (P) | {pm:.3f} ± {ps_:.3f} |")
    L.append(f"| BERT Recall (R)    | {rm:.3f} ± {rs_:.3f} |")
    L.append(f"| BERT F1            | **{wm:.3f} ± {ws_:.3f}** |")

    # Complementary n-gram overlap (BLEU / ROUGE), whole passage vs reference, per object.
    # Surface-form overlap — much lower than BERTScore by nature; a diagnostic, not headline.
    L.append("\n## N-gram overlap vs reference — complementary (whole passage, per object)\n")
    L.append("| Object | BLEU-4 | ROUGE-1 | ROUGE-2 | ROUGE-L |")
    L.append("|---|---|---|---|---|")
    bleu_v, r1_v, r2_v, rl_v = [], [], [], []
    for (name, _), cf in zip(mats, cands_full):
        b = sentence_bleu(cf, ref_full)
        r1 = rouge_n(cf, ref_full, 1)
        r2 = rouge_n(cf, ref_full, 2)
        rl = rouge_l(cf, ref_full)
        bleu_v.append(b); r1_v.append(r1); r2_v.append(r2); rl_v.append(rl)
        L.append(f"| {name} | {b:.3f} | {r1:.3f} | {r2:.3f} | {rl:.3f} |")
    bm, bs = msd(bleu_v); r1m, r1s = msd(r1_v); r2m, r2s = msd(r2_v); rlm, rls = msd(rl_v)
    L.append(f"| **mean ± SD** | **{bm:.3f} ± {bs:.3f}** | {r1m:.3f} ± {r1s:.3f} | "
             f"{r2m:.3f} ± {r2s:.3f} | {rlm:.3f} ± {rls:.3f} |")

    L.append("\n## Summary\n")
    L.append("| Metric | Value |")
    L.append("|---|---|")
    L.append(f"| Material relevance (whole passage, BERTScore F1) | **{wm:.3f} ± {ws_:.3f}** (n={len(mats)}) |")
    L.append(f"| Material relevance (whole passage, BERTScore P) | {pm:.3f} ± {ps_:.3f} (n={len(mats)}) |")
    L.append(f"| Material relevance (whole passage, BERTScore R) | {rm:.3f} ± {rs_:.3f} (n={len(mats)}) |")
    L.append(f"| Material relevance (per-section, BERTScore F1) | {om:.3f} ± {os_:.3f} (n={len(allvals)}) |")
    L.append(f"| Semantic diversity across materials (1 − mean pairwise cos) | {diversity:.3f} (n={len(mats)}) |")
    L.append("\n> LSTM language-fluency score (P-MAGIC's 5th metric) is **not reported**: it "
             "requires P-MAGIC's own trained LSTM model, which we do not have. BERT P/R/F1 "
             "and diversity are the directly reproducible metrics from their Table 3.")

    out = pathlib.Path(args.out)
    out.write_text("\n".join(L) + "\n")
    json.dump({"f1": f1, "overall": {"mean": om, "sd": os_, "n": len(allvals)},
               "whole_passage": {"f1_mean": wm, "f1_sd": ws_,
                                 "p_mean": pm, "p_sd": ps_,
                                 "r_mean": rm, "r_sd": rs_, "n": len(mats)},
               "diversity": diversity},
              open(out.with_suffix(".json"), "w"), indent=2)
    print(f"\nOVERALL material relevance F1 = {om:.3f} ± {os_:.3f} (n={len(allvals)})")
    print(f"diversity = {diversity:.3f}")
    print(f"report -> {out}")


if __name__ == "__main__":
    main()
