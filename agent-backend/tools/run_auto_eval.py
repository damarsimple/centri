#!/usr/bin/env python3
"""Preliminary self-contained auto-eval: STS diversity + relevance BERTScore.

Reference for BERTScore = a synthesized authentic-context *interpretation* per modality,
built deterministically from stats.json. This matches P-MAGIC's "relevance" use of BERT
(generated question vs authentic contextual information). The synthesized references are
also written to vinsa_export/<obj>/references/ as a base for Vinsa to refine.

NOTE: numbers are PRELIMINARY — the reference is ours, not Vinsa's agreed reference.

Usage: .venv-eval/bin/python tools/run_auto_eval.py <job_id> [<job_id> ...]
"""
import json, sys, re, pathlib, collections, itertools
import numpy as np
from bert_score import score as bert_score_fn
from sentence_transformers import SentenceTransformer

WS = pathlib.Path("workspaces")
OUT = pathlib.Path("vinsa_export")


def find_ws(jid):
    h = sorted(WS.glob(f"job_{jid}*"))
    return h[0] if h else None


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "scene").lower()).strip("-")[:40]


def fmt(x, n=2):
    try:
        return f"{float(x):.{n}f}"
    except Exception:
        return "n/a"


def interpretations(stats):
    s = stats.get("summary", {}) or {}
    pf = stats.get("period_and_frequency", {}) or {}
    sp = stats.get("stable_phase", {}) or {}
    cal = stats.get("calibration", {}) or {}
    obj = stats.get("object_name") or "the object"
    scene = stats.get("scene_title") or obj
    direction = stats.get("rotation_direction") or "unspecified"
    r = fmt(cal.get("r_fit_m") or s.get("mean_r_m"))
    om, ac, mx = fmt(s.get("mean_omega")), fmt(s.get("mean_ac")), fmt(s.get("max_ac"))
    v, T, f = fmt(s.get("mean_v")), fmt(pf.get("period_s")), fmt(pf.get("frequency_hz"))
    som = fmt(sp.get("stable_mean_omega"))
    text = (f"{scene}: {obj} moves in a circle of radius r = {r} m, rotating {direction}. "
            f"Mean angular velocity omega = {om} rad/s, tangential speed v = {v} m/s, "
            f"centripetal acceleration a_c = {ac} m/s^2 (peak {mx} m/s^2), "
            f"period T = {T} s, frequency f = {f} Hz.")
    image = (f"Annotated image of {obj} rotating about a centre, showing radius r = {r} m, "
             f"the inward centripetal acceleration a_c = {ac} m/s^2, and angular velocity "
             f"omega = {om} rad/s vectors.")
    graph = (f"Time graphs of the motion: angular velocity omega(t) mean {om} rad/s "
             f"(stable phase {som} rad/s) and centripetal acceleration a_c(t) mean {ac}, "
             f"peak {mx} m/s^2.")
    table = (f"Table of measured quantities for {obj}: radius {r} m, angular velocity {om} "
             f"rad/s, tangential speed {v} m/s, centripetal acceleration {ac} m/s^2, "
             f"period {T} s, frequency {f} Hz, direction {direction}.")
    return {"text": text, "image": image, "graph": graph, "table": table}


def diversity(model, stems):
    stems = [s for s in stems if s]
    if len(stems) < 2:
        return float("nan"), float("nan")
    emb = model.encode(stems, normalize_embeddings=True)
    sims = [float(np.dot(emb[i], emb[j])) for i, j in itertools.combinations(range(len(stems)), 2)]
    mean_sim = float(np.mean(sims))
    return mean_sim, 1.0 - mean_sim


def main(job_ids):
    div_model = SentenceTransformer("all-MiniLM-L6-v2")
    pairs = []                                   # (cand, ref) overall
    per_bucket = collections.defaultdict(lambda: {"c": [], "r": []})
    combined_q = []
    per_job = []

    for jid in job_ids:
        ws = find_ws(jid)
        if not ws:
            print("!! skip", jid); continue
        data = ws / "analysis_output" / "data"
        if not (data / "questions.json").exists():
            print("!! no questions.json", ws.name); continue
        q = json.loads((data / "questions.json").read_text())
        scene = q.get("scenario") if isinstance(q, dict) else None
        qs = q.get("questions", []) if isinstance(q, dict) else q
        stats = json.loads((data / "stats.json").read_text())
        interp = interpretations(stats)
        short = ws.name.replace("job_", "")[:8]
        dest = OUT / f"{slug(scene)}__{short}"
        refdir = dest / "references"; refdir.mkdir(parents=True, exist_ok=True)

        modality_stems = collections.defaultdict(list)
        stems_job = []
        for x in qs:
            stem = (x.get("stem") or x.get("question") or "").replace("\n", " ").strip()
            if not stem:
                continue
            fm = x.get("format", "text"); df = x.get("difficulty", "na")
            ref = interp.get(fm, interp["text"])
            pairs.append((stem, ref))
            per_bucket[f"{df}_{fm}"]["c"].append(stem)
            per_bucket[f"{df}_{fm}"]["r"].append(ref)
            modality_stems[fm].append(stem)
            stems_job.append(stem); combined_q.append(stem)

        # save synthesized reference base (aligned: one ref line per candidate)
        for fm, stems in modality_stems.items():
            (refdir / f"reference_{fm}.txt").write_text(
                "\n".join([interp.get(fm, interp["text"])] * len(stems)) + "\n")

        msim, dv = diversity(div_model, stems_job)
        per_job.append((dest.name, len(stems_job), msim, dv))

    # BERTScore overall + per bucket
    cands = [c for c, _ in pairs]; refs = [r for _, r in pairs]
    P, R, F1 = bert_score_fn(cands, refs, lang="en", verbose=False)
    overall = (P.mean().item(), R.mean().item(), F1.mean().item())
    buckets = {}
    for key, d in sorted(per_bucket.items()):
        p, r, f = bert_score_fn(d["c"], d["r"], lang="en", verbose=False)
        buckets[key] = (p.mean().item(), r.mean().item(), f.mean().item(), len(d["c"]))
    cmsim, cdv = diversity(div_model, combined_q)

    # ---- report ----
    L = []
    L.append("# Preliminary auto-eval (self-contained)\n")
    L.append("> Reference = synthesized authentic-context interpretation (ours), per modality.")
    L.append("> PRELIMINARY — replace references with Vinsa's agreed set for final numbers.\n")
    L.append(f"**BERTScore (relevance), overall, n={len(cands)}:** "
             f"P={overall[0]:.3f}  R={overall[1]:.3f}  F1={overall[2]:.3f}\n")
    L.append("**BERTScore F1 by difficulty_format bucket:**\n")
    L.append("| bucket | n | P | R | F1 |")
    L.append("|---|---|---|---|---|")
    for key, (p, r, f, n) in buckets.items():
        L.append(f"| {key} | {n} | {p:.3f} | {r:.3f} | {f:.3f} |")
    L.append("\n**STS diversity** (1 - mean pairwise cosine; higher = more diverse):\n")
    L.append("| set | n | mean_sim | diversity |")
    L.append("|---|---|---|---|")
    for name, n, ms, dv in per_job:
        L.append(f"| {name} | {n} | {ms:.3f} | {dv:.3f} |")
    L.append(f"| **ALL combined** | {len(combined_q)} | {cmsim:.3f} | {cdv:.3f} |")
    L.append("\n_Note: paper's 'diversity score' may be mean_sim OR 1-mean_sim — match Vinsa's convention._")
    rep = "\n".join(L) + "\n"
    (OUT / "auto_eval_report.md").write_text(rep)
    (OUT / "auto_eval_report.json").write_text(json.dumps({
        "overall_bert": {"P": overall[0], "R": overall[1], "F1": overall[2], "n": len(cands)},
        "bucket_bert": {k: {"P": v[0], "R": v[1], "F1": v[2], "n": v[3]} for k, v in buckets.items()},
        "diversity_per_job": [{"set": n, "n": c, "mean_sim": m, "diversity": d} for n, c, m, d in per_job],
        "diversity_combined": {"n": len(combined_q), "mean_sim": cmsim, "diversity": cdv},
        "note": "PRELIMINARY; reference = synthesized interpretation (ours), not Vinsa's.",
    }, indent=2))
    print(rep)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
