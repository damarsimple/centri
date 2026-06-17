"""Seeded, deterministic LaTeX report generator (run, don't re-author).

Writing the report `.tex` by hand was the agent's single most fragile task. Two
failures recurred every few jobs:

  * **Images silently missing from the PDF.** `compile_latex.sh` does `cd` into the
    report dir, so a hand-written `\\includegraphics{plots/foo.png}` resolved to
    `report/plots/foo.png` (nonexistent). pdflatex does not error on a missing
    graphic — it ships a blank box — so the job "succeeded" with imageless PDFs.
  * **Garbage macros.** The agent hand-substituted stats it didn't guard for null,
    emitting e.g. `\\newcommand{\\OmegaIncStart}{\\SI{N/A}{rad/s}}` (invalid).

Both are mechanical, so the `.tex` is generated here from `stats.json` +
`questions.json`. `\\graphicspath` is set so graphics resolve no matter the compile
CWD, every value is null-guarded, and all human text is LaTeX-escaped. The agent's
job relaxes to: run this, compile, look at the preview PNGs, only patch prose if it
reads wrong. It must NOT re-author the document or move the graphics paths.

    python -m analysis.render.report     # writes student_edition.tex + teacher_key.tex
"""
from __future__ import annotations

import json
import re
from pathlib import Path

DATA = Path("analysis_output/data")
REPORT = Path("analysis_output/report")

# Graphics live one level up from the report dir; compile_latex.sh cd's into the
# report dir, so `../plots/` is what resolves. The extra entries make it work
# whether compiled from the report dir, the workspace root, or elsewhere — so a
# missing image becomes impossible the way the old hand-written path made it routine.
GRAPHICS_PATH = r"\graphicspath{{../plots/}{plots/}{./plots/}{analysis_output/plots/}}"

# Figures embedded in the report, with widths. Only those that exist are included.
FIGURES = [
    ("summary_panel.png", 0.95, "Summary panel: trajectory, angular velocity, "
                                "centripetal acceleration, and key measurements."),
    ("trajectory.png", 0.6, "Trajectory in cropped-video space with the fitted orbit."),
    ("omega_t.png", 0.8, "Angular velocity vs.\\ time, phase regions shaded."),
    ("ac_t.png", 0.8, "Centripetal acceleration vs.\\ time."),
    ("radius_t.png", 0.8, "Orbit radius vs.\\ time."),
    ("v_t.png", 0.8, "Tangential speed vs.\\ time."),
]

# Unicode that creeps into LLM-generated question text → pdflatex-safe LaTeX.
_UNICODE = {
    "π": r"$\pi$", "ω": r"$\omega$", "θ": r"$\theta$", "α": r"$\alpha$",
    "β": r"$\beta$", "Δ": r"$\Delta$", "σ": r"$\sigma$", "μ": r"$\mu$",
    "·": r"$\cdot$", "×": r"$\times$", "÷": r"$\div$", "±": r"$\pm$",
    "≈": r"$\approx$", "≤": r"$\leq$", "≥": r"$\geq$", "≠": r"$\neq$",
    "→": r"$\rightarrow$", "°": r"$^\circ$", "√": r"$\sqrt{\,}$",
    "²": r"\textsuperscript{2}", "³": r"\textsuperscript{3}",
    "⁻": r"\textsuperscript{-}", "¹": r"\textsuperscript{1}",
    "₀": r"\textsubscript{0}", "₁": r"\textsubscript{1}", "₂": r"\textsubscript{2}",
    "₃": r"\textsubscript{3}", "ₐ": r"\textsubscript{a}", "ᶜ": r"\textsubscript{c}",
    "“": "``", "”": "''", "‘": "`", "’": "'", "–": "--", "—": "---",
    "−": "-", " ": " ",
}
_SPECIALS = {
    "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
    "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def tex_escape(s) -> str:
    if s is None:
        return ""
    s = str(s)
    out = []
    for ch in s:
        if ch in _UNICODE:
            out.append(_UNICODE[ch])
        elif ch in _SPECIALS:
            out.append(_SPECIALS[ch])
        else:
            out.append(ch)
    return "".join(out)


def num(x, prec=2):
    """Plain number string, or 'N/A' when missing — never 'None'/'nan'."""
    if x is None:
        return "N/A"
    try:
        xf = float(x)
    except (TypeError, ValueError):
        return "N/A"
    if xf != xf or xf in (float("inf"), float("-inf")):
        return "N/A"
    return f"{xf:.{prec}f}"


def si(x, prec, unit):
    """`\\SI{v}{unit}` when the value is real, else a plain italic N/A (so a null
    phase boundary degrades gracefully instead of producing `\\SI{N/A}{...}`)."""
    v = num(x, prec)
    return f"\\SI{{{v}}}{{{unit}}}" if v != "N/A" else r"\textit{N/A}"


def _measurements_table(stats) -> str:
    s, pf = stats["summary"], stats["period_and_frequency"]
    cal, st = stats["calibration"], stats["stable_phase"]
    rows = [
        ("Mean orbit radius", si(s.get("mean_r_m"), 3, "m")),
        ("Stable angular velocity", si(st.get("stable_mean_omega"), 2, r"rad/s")),
        ("Mean centripetal acceleration", si(s.get("mean_ac"), 2, r"m/s^2")),
        ("Maximum centripetal acceleration", si(s.get("max_ac"), 2, r"m/s^2")),
        ("Mean tangential speed", si(s.get("mean_v"), 2, r"m/s")),
        ("Period", si(pf.get("period_s"), 2, "s")),
        ("Frequency", si(pf.get("frequency_hz"), 2, "Hz")),
        ("Calibration", f"{num(cal.get('px_per_m'), 0)} px/m"),
        ("Fitted radius", f"{num(cal.get('r_fit_m'), 3)} m "
                          f"({num(cal.get('r_fit_px'), 1)} px)"),
    ]
    body = " \\\\\n".join(f"{k} & {v}" for k, v in rows)
    return ("\\begin{tabular}{ll}\n\\toprule\n"
            "\\textbf{Quantity} & \\textbf{Value} \\\\\n\\midrule\n"
            + body + " \\\\\n\\bottomrule\n\\end{tabular}")


def _figures_block() -> str:
    out = []
    for name, width, cap in FIGURES:
        if not (REPORT.parent / "plots" / name).exists():
            continue
        out.append(
            "\\begin{figure}[H]\n  \\centering\n"
            f"  \\includegraphics[width={width}\\textwidth]{{{name}}}\n"
            f"  \\caption{{{cap}}}\n"
            "\\end{figure}")
    return "\n\n".join(out)


def _preamble(title: str, subtitle: str) -> str:
    return (
        "\\documentclass[12pt]{article}\n"
        "\\usepackage[utf8]{inputenc}\n"
        "\\usepackage[T1]{fontenc}\n"
        "\\usepackage{siunitx}\n\\usepackage{graphicx}\n\\usepackage{booktabs}\n"
        "\\usepackage{amsmath}\n\\usepackage{geometry}\n\\usepackage{hyperref}\n"
        "\\usepackage{enumitem}\n\\usepackage{float}\n\\usepackage{caption}\n"
        "\\usepackage{fixltx2e}\n"
        "\\geometry{margin=1in}\n"
        f"{GRAPHICS_PATH}\n"
        "\\sisetup{per-mode=symbol}\n"
        "\\begin{document}\n"
        f"\\section*{{{title}}}\n"
        f"{subtitle}\n")


def _header_block(stats) -> str:
    s, trk = stats["summary"], stats["tracking"]
    vi = stats["video_info"]
    return (
        f"\\noindent\\textbf{{Object:}} {tex_escape(stats.get('object_name'))} \\\\\n"
        f"\\noindent\\textbf{{Rotation direction:}} {tex_escape(s.get('rotation_direction'))} \\\\\n"
        f"\\noindent\\textbf{{Tracking coverage:}} {num(trk.get('coverage_pct'), 1)}\\% \\\\\n"
        f"\\noindent\\textbf{{Active duration:}} {num(trk.get('active_duration_s'), 2)} s "
        f"(at {num(vi.get('fps'), 2)} fps)\n")


def _flags_block(stats) -> str:
    flags = stats.get("validation_flags") or []
    if not flags:
        return "No data-quality flags were raised."
    return "Validation flags raised: " + ", ".join(tex_escape(f) for f in flags)


def _questions_block(questions, with_answers: bool) -> str:
    items = []
    for q in questions:
        stem = tex_escape(q.get("question", ""))
        line = f"  \\item {stem}"
        if with_answers:
            ans = tex_escape(q.get("answer", ""))
            extra = [f"\n  \\textbf{{Answer:}} {ans}"]
            hints = q.get("hints") or []
            if hints:
                hl = "; ".join(tex_escape(h) for h in hints)
                extra.append(f"\\\\\n  \\textit{{Hints:}} {hl}")
            bl = q.get("bloom_level")
            pts = q.get("points")
            tag = []
            if bl:
                tag.append(tex_escape(bl))
            if pts is not None:
                tag.append(f"{tex_escape(pts)} pts")
            if tag:
                extra.append(f"\\\\\n  \\textit{{({', '.join(tag)})}}")
            line += "".join(extra)
        items.append(line)
    return ("\\begin{enumerate}[leftmargin=*]\n" + "\n".join(items) +
            "\n\\end{enumerate}")


def _build(stats, questions, *, scene, with_answers: bool) -> str:
    title = "Circular Motion Analysis" + (" — Teacher Key" if with_answers
                                          else " Report")
    subtitle = (f"\\noindent\\textbf{{Scene:}} {tex_escape(scene)}\\\\[4pt]\n"
                if scene else "")
    parts = [
        _preamble(title, subtitle),
        _header_block(stats),
        "\n\\section*{Key Measurements}\n",
        _measurements_table(stats),
        "\n\\section*{Data Quality Notes}\n",
        _flags_block(stats),
        "\n\\section*{Visual Analysis}\n",
        _figures_block(),
        "\n\\section*{Questions}\n",
        _questions_block(questions, with_answers),
        "\n\\end{document}\n",
    ]
    return "\n".join(parts)


def main() -> int:
    REPORT.mkdir(parents=True, exist_ok=True)
    stats = json.loads((DATA / "stats.json").read_text())
    qpath = DATA / "questions.json"
    questions = json.loads(qpath.read_text()) if qpath.exists() else []
    if isinstance(questions, dict):  # tolerate {"questions": [...]} shape
        questions = questions.get("questions", [])
    scene = stats.get("scene_title") or stats.get("object_name") or ""

    student = _build(stats, questions, scene=scene, with_answers=False)
    teacher = _build(stats, questions, scene=scene, with_answers=True)
    (REPORT / "student_edition.tex").write_text(student)
    (REPORT / "teacher_key.tex").write_text(teacher)
    n_fig = student.count("\\includegraphics")
    print(f"REPORT OK — student_edition.tex + teacher_key.tex written "
          f"({len(questions)} questions, {n_fig} figures, scene='{scene}')")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
