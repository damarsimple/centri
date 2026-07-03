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
import os
import re

# Questions (Subagent C) are gated off the deliverable by default — the artifact is the
# learning MATERIAL. Flip PI_RENDER_QUESTIONS=1 to restore the question bank in the report.
RENDER_QUESTIONS = os.environ.get("PI_RENDER_QUESTIONS", "0") == "1"
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

# Per-figure metadata (width fraction, caption) for the interleaved layout, where
# artifacts sit inside the learning-material prose instead of a separate dump.
FIG_META = {
    "annotated_image.png": (0.62, "A single video frame with the fitted circular orbit "
                                  "and the radius marked from the centre of rotation."),
    "annotated_image_basic.png": (0.62, "A frame from the video showing the object on its "
                                        "circular path, with the radius marked from the centre."),
    "trajectory_basic.png": (0.55, "The path the object traced — every tracked point falls on "
                                   "one circle."),
    "trajectory.png":  (0.55, "The tracked path in video space with the fitted circular orbit."),
    "omega_t.png":     (0.78, "Angular velocity $\\omega$ vs.\\ time, phase regions shaded."),
    "ac_t.png":        (0.78, "Centripetal acceleration $a_c$ vs.\\ time."),
    "radius_t.png":    (0.70, "Orbit radius vs.\\ time."),
    "v_t.png":         (0.70, "Tangential speed vs.\\ time."),
    "summary_panel.png": (0.92, "Summary panel: the trajectory, $\\omega(t)$, $a_c(t)$, "
                                "and the key measurements brought together."),
}

# Which artifacts belong with which material section, so the PDF reads like ordinary
# learning material (figures/table next to the prose that discusses them). "__TABLE__"
# is the key-measurements table, rendered inline. Any figure absent on disk is skipped.
SECTION_ARTIFACTS = {
    "Scenario":                       ["annotated_image.png"],
    "The variables we measured":      ["__TABLE__"],
    "What the video shows over time": ["omega_t.png", "ac_t.png"],
    "Reading the figures":            ["summary_panel.png", "trajectory.png",
                                       "radius_t.png", "v_t.png"],
}

# Difficulty-tiered artifacts: each tier shows a figure/table set whose visual load
# matches its prose (CLT). Basic = a simplified frame + the bare path, no time-series,
# no numeric table; intermediate = standard frame + one trend + the core table;
# advanced = the full multi-panel set + the full table (with alpha/calibration rows).
# "__TABLE_CORE__"/"__TABLE_FULL__" select the table depth; missing figures are skipped.
# The figure_allowlist fed to the generator (generate_tier_material.py) MUST match these,
# so "Reading the figures" only narrates plots the tier actually shows.
TIER_ARTIFACTS = {
    "basic": {
        "Scenario":                       ["annotated_image_basic.png"],
        "Reading the figures":            ["trajectory_basic.png"],
    },
    "intermediate": {
        "Scenario":                       ["annotated_image.png"],
        "The variables we measured":      ["__TABLE_CORE__"],
        "What the video shows over time": ["omega_t.png"],
        "Reading the figures":            ["trajectory.png"],
    },
    "advanced": {
        "Scenario":                       ["annotated_image.png"],
        "The variables we measured":      ["__TABLE_FULL__"],
        "What the video shows over time": ["omega_t.png", "ac_t.png"],
        # No summary_panel dump — it re-shows every raw plot (incl. the rippled radius) and
        # duplicates the trajectory; the interleaved figures above already carry the story.
        "Reading the figures":            ["trajectory.png"],
    },
}

# Unicode that creeps into LLM-generated question text → pdflatex-safe LaTeX.
_UNICODE = {
    "π": r"$\pi$", "ω": r"$\omega$", "θ": r"$\theta$", "α": r"$\alpha$",
    "β": r"$\beta$", "Δ": r"$\Delta$", "σ": r"$\sigma$", "μ": r"$\mu$",
    "·": r"$\cdot$", "×": r"$\times$", "÷": r"$\div$", "±": r"$\pm$",
    "≈": r"$\approx$", "≤": r"$\leq$", "≥": r"$\geq$", "≠": r"$\neq$",
    "→": r"$\rightarrow$", "°": r"$^\circ$", "√": r"$\sqrt{\,}$",
    "∝": r"$\propto$", "∞": r"$\infty$", "≡": r"$\equiv$", "∴": r"$\therefore$",
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


# Physics subscripts the LLM writes as plain ASCII (a_c, a_t, …). Rendered as real
# math subscripts instead of a literal escaped underscore ("a\_c"). Guarded so a
# filename like "omega_t.png" (letter before, extension after) is NOT matched.
_SUBSCRIPT_TOKENS = {
    "a_c": r"$a_{\mathrm{c}}$", "a_t": r"$a_{\mathrm{t}}$",
    "a_r": r"$a_{\mathrm{r}}$", "v_t": r"$v_{\mathrm{t}}$",
    "v_c": r"$v_{\mathrm{c}}$",
}
_SUBSCRIPT_RE = re.compile(r"(?<![A-Za-z0-9])(?:" + "|".join(_SUBSCRIPT_TOKENS) + r")(?![A-Za-z0-9])")


def tex_escape(s) -> str:
    if s is None:
        return ""
    s = str(s)
    # Protect physics subscript tokens from the char-wise underscore escape, then
    # restore them as math after escaping (sentinels use NUL, never in real text).
    sentinels = {}

    def _stash(m):
        key = f"\x00{len(sentinels)}\x00"
        sentinels[key] = _SUBSCRIPT_TOKENS[m.group(0)]
        return key

    s = _SUBSCRIPT_RE.sub(_stash, s)
    out = []
    for ch in s:
        if ch in _UNICODE:
            out.append(_UNICODE[ch])
        elif ch in _SPECIALS:
            out.append(_SPECIALS[ch])
        else:
            out.append(ch)
    res = "".join(out)
    for key, val in sentinels.items():
        res = res.replace(key, val)
    return res


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


def _measurements_table(stats, level="full", unreliable=False) -> str:
    """Key-measurements tabular. ``level="core"`` keeps the six routine quantities an
    intermediate passage uses (r, $\\omega$, $a_c$, v, T, f) and drops the peak/
    calibration/angular-acceleration rows, which belong to the advanced tier.
    ``unreliable=True`` (oblique-capture clip) drops the per-instant PEAK row (max a_c is
    the ripple's high point — an artifact) so the table never contradicts the caveat."""
    s, pf = stats["summary"], stats["period_and_frequency"]
    cal, st = stats["calibration"], stats["stable_phase"]
    aa = stats.get("angular_acceleration", {})
    if level == "core":
        # Intermediate is built on the ANGULAR quantities + a_c = omega^2 r; tangential
        # speed v is de-emphasised at this tier (spec TIER 2), so it is not tabled here.
        rows = [
            ("Orbit radius", si(s.get("mean_r_m"), 3, "m")),
            ("Angular velocity", si(st.get("stable_mean_omega"), 2, r"rad/s")),
            ("Centripetal acceleration", si(s.get("mean_ac"), 2, r"m/s^2")),
            ("Period", si(pf.get("period_s"), 2, "s")),
            ("Frequency", si(pf.get("frequency_hz"), 2, "Hz")),
        ]
        body = " \\\\\n".join(f"{k} & {v}" for k, v in rows)
        return ("\\begin{tabular}{ll}\n\\toprule\n"
                "\\rowcolor{accent!12}\\textbf{Quantity} & \\textbf{Value} \\\\\n\\midrule\n"
                + body + " \\\\\n\\bottomrule\n\\end{tabular}")
    rows = [
        ("Mean orbit radius", si(s.get("mean_r_m"), 3, "m")),
        ("Stable angular velocity", si(st.get("stable_mean_omega"), 2, r"rad/s")),
        ("Mean centripetal acceleration", si(s.get("mean_ac"), 2, r"m/s^2")),
        # Max a_c is the per-instant ripple peak — drop it on an oblique clip.
        *([] if unreliable else
          [("Maximum centripetal acceleration", si(s.get("max_ac"), 2, r"m/s^2"))]),
        ("Mean tangential speed", si(s.get("mean_v"), 2, r"m/s")),
        ("Period", si(pf.get("period_s"), 2, "s")),
        ("Frequency", si(pf.get("frequency_hz"), 2, "Hz")),
        ("Calibration", f"{num(cal.get('px_per_m'), 0)} px/m"),
        ("Fitted radius", f"{num(cal.get('r_fit_m'), 3)} m "
                          f"({num(cal.get('r_fit_px'), 1)} px)"),
    ]
    # Non-uniform spins (fan spin-up, turntable coast-down) additionally report the
    # angular acceleration and the tangential acceleration it produces.
    if aa.get("motion_type") in ("accelerating", "decelerating"):
        rows[1:1] = [
            (f"Motion type", aa["motion_type"].capitalize()),
            ("Angular acceleration", si(aa.get("alpha_rad_s2"), 2, r"rad/s^2")),
            ("Tangential acceleration", si(aa.get("a_t_mean_m_s2"), 2, r"m/s^2")),
            (r"$\omega$ initial $\rightarrow$ final",
             f"{num(aa.get('omega_initial'), 2)} $\\rightarrow$ "
             f"{num(aa.get('omega_final'), 2)} rad/s"),
        ]
    body = " \\\\\n".join(f"{k} & {v}" for k, v in rows)
    return ("\\begin{tabular}{ll}\n\\toprule\n"
            "\\rowcolor{accent!12}\\textbf{Quantity} & \\textbf{Value} \\\\\n\\midrule\n"
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


_MATERIAL_ORDER = [
    "Scenario",
    "The variables we measured",
    "How the variables are related",
    "What the video shows over time",
    "Reading the figures",
]


def _inline_figure(name: str) -> str:
    """A single captioned figure, or "" if the plot is missing on disk."""
    if not (REPORT.parent / "plots" / name).exists():
        return ""
    width, cap = FIG_META.get(name, (0.8, ""))
    cap_tex = f"  \\caption{{{cap}}}\n" if cap else ""
    return ("\\begin{figure}[H]\n  \\centering\n"
            f"  \\includegraphics[width={width}\\textwidth]{{{name}}}\n"
            f"{cap_tex}\\end{{figure}}")


def _inline_table(stats, level="full", unreliable=False) -> str:
    """The key-measurements table as a captioned, centred float for inline use."""
    return ("\\begin{table}[H]\n  \\centering\n"
            "  \\caption{Key measurements for this scene.}\n  "
            + _measurements_table(stats, level, unreliable) + "\n\\end{table}")


_TABLE_KEYS = {"__TABLE__": "full", "__TABLE_FULL__": "full", "__TABLE_CORE__": "core"}


def _section_artifacts(heading: str, stats, tier=None, unreliable=False) -> str:
    """LaTeX for the figures/table that belong with a material section. When ``tier``
    names a known difficulty tier, its (lighter/heavier) artifact set is used instead
    of the default; otherwise the untiered default applies."""
    amap = TIER_ARTIFACTS.get(tier, SECTION_ARTIFACTS) if tier else SECTION_ARTIFACTS
    out = []
    for key in amap.get(heading, []):
        if key in _TABLE_KEYS:
            tex = _inline_table(stats, _TABLE_KEYS[key], unreliable)
        else:
            tex = _inline_figure(key)
        if tex:
            out.append(tex)
    return ("\n\n" + "\n\n".join(out)) if out else ""


def _material_block(material, stats=None, unreliable=False) -> str:
    """Render Subagent D's grounded learning passage (material.json sections), with
    the relevant figures and the measurements table interleaved into each section so
    the document reads like ordinary learning material rather than prose then a figure
    dump. Pass ``stats`` to enable interleaving; omit it for prose only."""
    if not material:
        return ""
    sections = material.get("sections", material) if isinstance(material, dict) else {}
    if not isinstance(sections, dict) or not sections:
        return ""
    # A tiered material.json carries "tier": basic|intermediate|advanced, which selects
    # the difficulty-matched figure/table set; untiered material keeps the default set.
    tier = material.get("tier") if isinstance(material, dict) else None
    ordered = [h for h in _MATERIAL_ORDER if h in sections]
    ordered += [h for h in sections if h not in _MATERIAL_ORDER]  # tolerate extras
    out = []
    for h in ordered:
        body = (sections.get(h) or "").strip()
        if not body:
            continue
        paras = [tex_escape(p.strip()) for p in re.split(r"\n\s*\n", body) if p.strip()]
        block = f"\\subsection*{{{tex_escape(h)}}}\n" + "\n\n".join(paras)
        if stats is not None:
            block += _section_artifacts(h, stats, tier, unreliable)
        out.append(block)
    return "\n\n".join(out)


# Per-tier accent colour (basic = calm green, intermediate = blue, advanced = deep
# purple); untiered/legacy reports use a neutral teal. Drives headings, rules, the
# level badge and the table header tint, so difficulty reads at a glance.
_TIER_ACCENT = {"basic": "2E7D32", "intermediate": "1565C0", "advanced": "6A1B9A"}
_DEFAULT_ACCENT = "00695C"


def _preamble(tier=None) -> str:
    accent = _TIER_ACCENT.get(tier, _DEFAULT_ACCENT)
    return (
        "\\documentclass[11pt]{article}\n"
        "\\usepackage[utf8]{inputenc}\n"
        "\\usepackage[T1]{fontenc}\n"
        # expansion=false: the worker has no scalable CM (no lmodern), and microtype font
        # EXPANSION fatally errors on bitmap fonts under pdflatex. Protrusion is safe.
        "\\usepackage[protrusion=true,expansion=false]{microtype}\n"
        "\\usepackage[table,dvipsnames]{xcolor}\n"
        "\\usepackage{siunitx}\n\\usepackage{graphicx}\n\\usepackage{booktabs}\n"
        "\\usepackage{amsmath}\n\\usepackage{geometry}\n\\usepackage{hyperref}\n"
        "\\usepackage{enumitem}\n\\usepackage{float}\n\\usepackage{caption}\n"
        "\\usepackage{titlesec}\n\\usepackage{setspace}\n\\usepackage{fixltx2e}\n"
        "\\geometry{margin=1in}\n"
        f"\\definecolor{{accent}}{{HTML}}{{{accent}}}\n"
        "\\definecolor{inkgray}{HTML}{555555}\n"
        f"{GRAPHICS_PATH}\n"
        "\\sisetup{per-mode=symbol}\n"
        "\\setstretch{1.06}\n"
        "\\renewcommand{\\arraystretch}{1.25}\n"
        "\\hypersetup{colorlinks=true,linkcolor=accent,urlcolor=accent}\n"
        # accent sans-serif headings; a thin accent rule trails each \section
        "\\titleformat{\\section}{\\sffamily\\Large\\bfseries\\color{accent}}{}{0em}{}"
        "[{\\vspace{2pt}{\\color{accent!35}\\titlerule[1.2pt]}}]\n"
        "\\titleformat{\\subsection}{\\sffamily\\large\\bfseries\\color{accent!88!black}}{}{0em}{}\n"
        "\\titlespacing*{\\section}{0pt}{1.5em}{0.6em}\n"
        "\\titlespacing*{\\subsection}{0pt}{1.0em}{0.35em}\n"
        "\\captionsetup{font=small,labelfont={bf,color=accent!65!black},labelsep=period}\n"
        "\\begin{document}\n")


def _titleblock(title: str, scene: str, tier=None) -> str:
    """Styled masthead: an accent rule, the title in large sans, then a difficulty
    badge (when tiered) and the scene, closed by a thin rule."""
    badge = ""
    if tier in _TIER_ACCENT:
        badge = ("\\colorbox{accent}{\\textcolor{white}{\\sffamily\\bfseries\\small~"
                 + tier.upper() + " LEVEL~}}")
    scene_tex = (f"\\textcolor{{inkgray}}{{\\sffamily {tex_escape(scene)}}}" if scene else "")
    sub = (f"\\noindent {badge}\\hfill {scene_tex}\\\\[3pt]\n"
           if (badge or scene_tex) else "")
    return (
        "\\noindent{\\color{accent}\\rule{\\linewidth}{2.5pt}}\\\\[3pt]\n"
        f"\\noindent{{\\sffamily\\bfseries\\LARGE\\color{{accent!85!black}} {title}}}\\\\[5pt]\n"
        f"{sub}"
        "\\noindent{\\color{accent!35}\\rule{\\linewidth}{0.6pt}}\\\\[8pt]\n")


def _header_block(stats, learning: bool = False) -> str:
    s, trk = stats["summary"], stats["tracking"]
    vi = stats["video_info"]
    if learning:
        # Learning-material edition: physics context only — no coverage/fps/tracking
        # scaffolding (extraneous cognitive load; not part of the lesson).
        bits = [
            f"\\textbf{{Object:}} {tex_escape(stats.get('object_name'))}",
            f"\\textbf{{Direction:}} {tex_escape(s.get('rotation_direction'))}",
            f"\\textbf{{Clip length:}} {num(vi.get('duration_s'), 1)}\\,s",
        ]
    else:
        bits = [
            f"\\textbf{{Object:}} {tex_escape(stats.get('object_name'))}",
            f"\\textbf{{Rotation:}} {tex_escape(s.get('rotation_direction'))}",
            f"\\textbf{{Coverage:}} {num(trk.get('coverage_pct'), 1)}\\%",
            f"\\textbf{{Duration:}} {num(trk.get('active_duration_s'), 2)}\\,s "
            f"@ {num(vi.get('fps'), 2)}\\,fps",
        ]
    sep = " \\;{\\color{accent!45}\\textbar}\\; "
    return ("\\noindent\\textcolor{inkgray}{\\small\\sffamily "
            + sep.join(bits) + "}\\\\[6pt]\n")


def _flags_block(stats) -> str:
    flags = stats.get("validation_flags") or []
    if not flags:
        return "No data-quality flags were raised."
    return "Validation flags raised: " + ", ".join(tex_escape(f) for f in flags)


# P-MAGIC difficulty tiers, rendered in this order.
_LEVEL_ORDER = ["easy", "intermediate", "advanced"]


def _questions_block(questions, with_answers: bool) -> str:
    # Group by difficulty (easy -> intermediate -> advanced); anything without a
    # recognised level (incl. legacy bloom-tagged questions) falls under "other".
    groups = {}
    for q in questions:
        lvl = (q.get("difficulty") or "other").lower()
        groups.setdefault(lvl, []).append(q)
    order = ([l for l in _LEVEL_ORDER if l in groups] +
             [l for l in groups if l not in _LEVEL_ORDER])

    sections = []
    for lvl in order:
        items = []
        for q in groups[lvl]:
            # App reads `stem`; legacy/report data may carry `question` instead.
            stem = tex_escape(q.get("stem") or q.get("question", ""))
            fmt = q.get("format")
            line = f"  \\item {stem}"
            if fmt:
                line += f" \\textit{{[{tex_escape(fmt)}]}}"
            if with_answers:
                ans = tex_escape(q.get("answer", ""))
                extra = [f"\n  \\textbf{{Answer:}} {ans}"]
                sol = q.get("solution")
                if sol:
                    extra.append(f"\\\\\n  \\textit{{Solution:}} {tex_escape(sol)}")
                hints = q.get("hints") or []
                if hints:
                    hl = "; ".join(tex_escape(h) for h in hints)
                    extra.append(f"\\\\\n  \\textit{{Hints:}} {hl}")
                line += "".join(extra)
            items.append(line)
        if not items:
            continue
        heading = lvl.capitalize() if lvl != "other" else "Questions"
        sections.append(
            f"\\subsection*{{{tex_escape(heading)}}}\n"
            "\\begin{enumerate}[leftmargin=*]\n" + "\n".join(items) +
            "\n\\end{enumerate}")
    return "\n".join(sections)


def _build(stats, questions, *, scene, with_answers: bool, material=None,
           unreliable: bool = False) -> str:
    tier = material.get("tier") if isinstance(material, dict) else None
    # With material, the figures/table are interleaved into the prose (textbook-style),
    # so we drop the separate Key Measurements / Visual Analysis dumps. Without material,
    # fall back to the standalone data + figures sections so nothing is lost.
    material_tex = _material_block(material, stats, unreliable)
    # The student edition of a tiered job IS the learning material: a clean, student-facing
    # lesson — no report framing, no data-quality flags, no questions (those live in the
    # teacher key / a separate worksheet). The teacher key keeps the full report.
    learning = bool(material_tex) and not with_answers
    if with_answers:
        title = "Circular Motion Analysis — Teacher Key"
    elif learning:
        title = "Circular Motion — Learning Material"
    else:
        title = "Circular Motion Analysis Report"
    parts = [
        _preamble(tier),
        _titleblock(title, scene, tier),
        _header_block(stats, learning=learning),
    ]
    if material_tex:
        # The grounded learning passage (with its inline figures/table) leads the document.
        # In learning mode the masthead already says "Learning Material" — no extra heading.
        if not learning:
            parts.append("\n\\section*{Learning Material}\n")
        parts.append(material_tex)
    else:
        parts += [
            "\n\\section*{Key Measurements}\n",
            _measurements_table(stats),
            "\n\\section*{Visual Analysis}\n",
            _figures_block(),
        ]
    # Data-quality notes are for the instructor only (measurement caveats), never on the
    # student learning material.
    if with_answers:
        parts += ["\n\\section*{Data Quality Notes}\n", _flags_block(stats)]
    # Questions are gated OFF by default — the deliverable is the learning MATERIAL, not a
    # worksheet (Subagent C). Set PI_RENDER_QUESTIONS=1 to bring the question bank back
    # (e.g. for a P-MAGIC question comparison); the generator code stays intact.
    if RENDER_QUESTIONS and questions:
        parts += ["\n\\section*{Questions}\n", _questions_block(questions, with_answers)]
    parts.append("\n\\end{document}\n")
    return "\n".join(parts)


def _load_material():
    mpath = DATA / "material.json"
    if not mpath.exists():
        return None
    try:
        return json.loads(mpath.read_text())
    except (ValueError, OSError):
        return None


_TIERS = ("basic", "intermediate", "advanced")


def _load_tiers():
    """Return {tier: material} for every material.<tier>.json present (difficulty-tiered
    path). Empty dict when the job is untiered (legacy single material.json)."""
    out = {}
    for t in _TIERS:
        p = DATA / f"material.{t}.json"
        if p.exists():
            try:
                out[t] = json.loads(p.read_text())
            except (ValueError, OSError):
                pass
    return out


def _emit(stats, questions, scene, material, *, suffix="", unreliable=False):
    """Write student_edition{suffix}.tex + teacher_key{suffix}.tex for one material."""
    student = _build(stats, questions, scene=scene, with_answers=False,
                     material=material, unreliable=unreliable)
    teacher = _build(stats, questions, scene=scene, with_answers=True,
                     material=material, unreliable=unreliable)
    (REPORT / f"student_edition{suffix}.tex").write_text(student)
    (REPORT / f"teacher_key{suffix}.tex").write_text(teacher)
    return student.count("\\includegraphics")


def _is_unreliable(stats) -> bool:
    """Per-instant omega an oblique-capture artifact? Drives table/figure hedging."""
    try:
        from .. import quality_signals
        sig = quality_signals.compute(DATA / "kinematics.csv", stats)
        return "per_instant_omega_unreliable" in sig.get("flags", [])
    except Exception:
        return False


def main() -> int:
    REPORT.mkdir(parents=True, exist_ok=True)
    stats = json.loads((DATA / "stats.json").read_text())
    qpath = DATA / "questions.json"
    questions = json.loads(qpath.read_text()) if qpath.exists() else []
    if isinstance(questions, dict):  # tolerate {"questions": [...]} shape
        questions = questions.get("questions", [])
    scene = stats.get("scene_title") or stats.get("object_name") or ""
    # De-duplicate the "<X> on <X>" scene title that arises when the tracked label
    # equals the reference label (e.g. "black ball on black ball" -> "black ball").
    m = re.fullmatch(r"(.+?) on \1", scene.strip())
    if m:
        scene = m.group(1)
    unreliable = _is_unreliable(stats)

    tiers = _load_tiers()
    if tiers:
        # Difficulty-tiered path: one PDF pair per tier (suffix .basic / .intermediate / ...).
        for tier, material in tiers.items():
            n_fig = _emit(stats, questions, scene, material, suffix=f".{tier}",
                          unreliable=unreliable)
            n_mat = len(material.get("sections", {}))
            print(f"REPORT OK [{tier}] — student_edition.{tier}.tex + teacher_key.{tier}.tex "
                  f"({n_mat} material sections, {n_fig} figures)")
        print(f"REPORT OK — {len(tiers)} tier(s) rendered ({len(questions)} questions, "
              f"scene='{scene}')")
        return 0

    # Legacy / untiered single material.json.
    material = _load_material()
    n_fig = _emit(stats, questions, scene, material, unreliable=unreliable)
    n_mat = len((material or {}).get("sections", {})) if material else 0
    print(f"REPORT OK — student_edition.tex + teacher_key.tex written "
          f"({len(questions)} questions, {n_mat} material sections, "
          f"{n_fig} figures, scene='{scene}')")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
