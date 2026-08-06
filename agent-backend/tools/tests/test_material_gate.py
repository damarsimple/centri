#!/usr/bin/env python3
"""Offline unit tests for the shared material gate (analysis/material_gate.py).

Runs standalone (`python tools/tests/test_material_gate.py`) or under pytest. No network,
no LLM — hand-built passing/failing material JSONs exercise every check, and in particular
pin the resolved v=omega*r drift (a material without v=omega*r passes; one missing the
structured a_c=omega^2*r fails)."""
import pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "workspace_lib"))
from analysis import material_gate as G


def _seed(motion="accelerating", reliable=True):
    return {
        "variables": [
            {"symbol": "r", "value": 0.15}, {"symbol": "omega", "value": 2.7},
            {"symbol": "a_c", "value": 1.29}, {"symbol": "T", "value": 2.3},
            {"symbol": "f", "value": 0.43},
        ],
        "timeline": [
            {"t_s": 0.0, "omega_rad_s": 1.2, "v_m_s": 0.18, "a_c_m_s2": 0.22},
            {"t_s": 3.33, "omega_rad_s": 2.2, "v_m_s": 0.33, "a_c_m_s2": 0.73},
            {"t_s": 6.63, "omega_rad_s": 3.19, "v_m_s": 0.48, "a_c_m_s2": 1.53},
            {"t_s": 9.97, "omega_rad_s": 4.19, "v_m_s": 0.63, "a_c_m_s2": 2.63},
        ],
        "angular_acceleration": {"motion_type": motion, "alpha_rad_s2": 0.30},
        "angle_milestones": [{"t_s": 1.17, "angle_deg": 90, "turn": "a quarter turn"}],
        "measurement_quality": {"reliable": reliable},
    }


def test_arithmetic():
    assert any(not c["ok"] for c in G.arithmetic_claims("6.59 × 1.78 = 12.2"))
    assert all(c["ok"] for c in G.arithmetic_claims("2.2² × 0.15 = 0.73"))


def test_chained_equation_no_false_positive():
    # A fuller worked solution restates the ω² intermediate before multiplying by r:
    # "A² · B = <A²> · B = C". The restated intermediate (57.9) must NOT be read as the
    # product of A²·B (a gate false positive that trapped mimo-v2.5 in an infinite regen).
    claims = G.arithmetic_claims("a_c = (7.609)² · 0.148 = 57.9 · 0.148 = 8.57 m/s²")
    assert all(c["ok"] for c in claims)               # no spurious fail
    assert any(abs(c["stated"] - 8.57) < 1e-6 for c in claims)   # the real final step is still checked
    # a genuinely wrong final result is still caught even in chained form:
    assert any(not c["ok"] for c in G.arithmetic_claims("57.9 · 0.148 = 9.99 m/s²"))


def test_intermediate_drift_resolved():
    # v=omega*r alone must NOT satisfy intermediate any more...
    assert G.tier_compliance("intermediate", "The tangential speed v = ω · r describes it.")
    # ...but the structured a_c = omega^2 * r does.
    assert not G.tier_compliance("intermediate", "So a_c = ω²·r closes for this blade.")


def test_basic_symbols_flagged():
    assert G.tier_compliance("basic", "here ω = 2.7 rad/s")
    assert not G.tier_compliance("basic", "it sweeps about a quarter turn each second")


def test_advanced_needs_alpha_and_instant():
    assert G.tier_compliance("advanced", "just a plain description")  # missing both
    assert not G.tier_compliance("advanced", "at t = 6.63 s the spin-up rate alpha is steady")
    # oblique clip: neither is required
    assert not G.tier_compliance("advanced", "a plain description", unreliable=True)


def test_vocab():
    assert [v["kind"] for v in G.vocab_issues("we tracked it in every frame")] == \
        ["tracking", "tracking"]
    assert any(v["kind"] == "dynamics" for v in G.vocab_issues("friction dissipates energy"))
    assert G.vocab_issues("the blade sweeps a quarter turn, pulled inward") == []


def test_motion_faithfulness():
    assert G.motion_faithfulness(_seed("accelerating"), "it moves at a constant speed")
    assert not G.motion_faithfulness(_seed("accelerating"),
                                     "rather than a constant speed, it whirls faster")
    assert not G.motion_faithfulness(_seed("uniform"), "it moves at a constant speed")


def test_omega_squared_intermediate_grounded():
    # ω² is the sanctioned intermediate of a_c = ω²·r; showing it must not read as ungrounded.
    seed = _seed()  # omega=2.7 -> ω²=7.29; timeline omega 4.19 -> ω²=17.56
    allowed = G.allowed_values(seed)
    assert G.grounded(7.29, allowed)    # mean ω²
    assert G.grounded(17.56, allowed)   # instantaneous ω² from the timeline
    assert not G.ungrounded_numbers("squaring 4.19 rad/s gives 17.56 rad^2/s^2", allowed)
    # A decelerating clip that only says it "does not speed up" is TRUE, not a steady
    # claim -> must NOT flag; but "does not speed up or slow down" IS a steady claim.
    assert not G.motion_faithfulness(_seed("decelerating"), "the phone does not speed up")
    assert G.motion_faithfulness(_seed("decelerating"),
                                 "it does not speed up or slow down; it is uniform")


def test_story_fence():
    frame = {"who": "Amir", "where": "the market"}
    obj = {"sections": {"Scenario": "Amir at the market spins it",
                        "How the variables are related": "a_c grows with omega squared"}}
    assert G.story_fence_issues(obj, frame) == []      # names only in Scenario -> ok
    leak = {"sections": {"Scenario": "a spin", "Reading the figures": "Amir sees the market"}}
    assert G.story_fence_issues(leak, frame)           # name outside Scenario -> flagged


def _mat(tier, text):
    return {"tier": tier, "scene_title": "Red Fan Blade",
            "sections": {"What the video shows over time": text}}


def test_cross_tier():
    seed = _seed()
    anchors = {"intermediate": [1], "advanced": [2, 0, 3]}
    # good: distinct instants, rising EI, equal titles
    good = {
        "basic": _mat("basic", "it sweeps a quarter turn then half a turn"),
        "intermediate": _mat("intermediate",
            "at t = 3.33 s, a_c = ω²·r for radius r and period T and frequency f"),
        "advanced": _mat("advanced",
            "at t = 6.63 s and t = 0.0 s and t = 9.97 s, the radius r, tangential speed v, "
            "angular velocity ω, centripetal acceleration a_c = ω²·r, angular acceleration "
            "α = dω/dt, tangential acceleration a_t = α·r, period T = 2π/ω and frequency f = 1/T "
            "all evolve; a_c grows with ω squared."),
    }
    assert G.cross_tier_issues(good, seed, anchors) == []

    # title mismatch
    bad = {k: dict(v) for k, v in good.items()}
    bad["advanced"] = dict(good["advanced"], scene_title="Something Else")
    assert any("scene_title" in i for i in G.cross_tier_issues(bad, seed, anchors))

    # intermediate reuses advanced's instant / misses its own
    bad2 = dict(good)
    bad2["intermediate"] = _mat("intermediate", "at t = 6.63 s, a_c = ω²·r")
    issues = G.cross_tier_issues(bad2, seed, anchors)
    assert any("intermediate" in i for i in issues)


def test_steady_smooth_phrasings_flagged():
    # A1: the critique's "smooth and uninterrupted" / "unchanging pace" must be caught on a
    # decelerating clip, not just the literal "constant speed".
    for phrase in ("it moves in a smooth and uninterrupted circle",
                   "it keeps an unchanging pace", "a steady rhythm the whole time",
                   "it holds its pace throughout"):
        assert G.motion_faithfulness(_seed("decelerating"), phrase), phrase
    # a plain "smooth circle" (shape, not speed) must NOT trip it
    assert not G.motion_faithfulness(_seed("decelerating"), "it traces one smooth circle")


def test_json_sanitizer_recovers_latex_slip():
    from analysis import material_tiers as T
    bad = '{"sections": {"Scenario": "the \\omega spins and \\alpha grows, \\Delta t"}, "tier": "advanced"}'
    obj = T._parse_json(bad)               # would raise without the sanitizer
    assert "omega" in obj["sections"]["Scenario"]
    # valid escapes survive untouched
    assert T._parse_json('{"s": "a\\nb"}')["s"] == "a\nb"


def _num_in(s):
    import re as _re
    m = _re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else None


def _eval_expr(expr):
    import re as _re
    e = (expr.replace("×", "*").replace("·", "*").replace("−", "-")
             .replace("÷", "/").replace("²", "**2"))
    e = e.split("=")[-1]                                  # RHS of "v = 9.28 × 0.148"
    e = _re.sub(r"[^0-9.+\-*/() ]", "", e).strip().rstrip("*/+-. ")
    return eval(e, {"__builtins__": {}}) if e else None   # noqa: S307 — sanitized, digits only


def test_seed_worked_examples_arithmetic_closes():
    """The whole point of the critique: the numbers must check out. Every seeded worked
    example's substitute line must actually compute to its stated result."""
    from analysis import material_seed as S
    stats = {
        "object_name": "red ring", "scene_title": "red ring on a wheel",
        "summary": {"mean_r_m": 0.2, "mean_omega": 5.0, "mean_v": 1.0, "mean_ac": 5.0,
                    "max_ac": 8.0, "rotation_direction": "CCW"},
        "period_and_frequency": {"period_s": 1.2, "frequency_hz": 0.83},
        # alpha is fit over a 2 s window, NOT the 15 s clip: (2-8)/2 = -3 closes, (2-8)/15
        # = -0.4 does NOT. Pins the fit-window fix — the alpha example must divide by 2, not 15.
        "angular_acceleration": {"motion_type": "decelerating", "alpha_rad_s2": -3.0,
                                 "alpha_r2": 0.99, "omega_initial": 8.0, "omega_final": 2.0,
                                 "a_t_mean_m_s2": 0.6, "fit_window_s": 2.0},
        "stable_phase": {"stable_mean_omega": 5.0},
        "calibration": {"r_fit_m": 0.2, "px_per_m": 1500.0, "r_fit_px": 300.0},
        "video_info": {"duration_s": 15.0},
        "tracking": {"active_duration_s": 2.0, "active_start_s": 1.0, "active_end_s": 3.0},
    }
    seed = S.build_seed(stats, None)
    # A3: tangential acceleration is re-signed negative for a deceleration.
    assert seed["angular_acceleration"]["a_t_mean_m_s2"] < 0
    # S1.3: stopped ON CAMERA — active window (ends 3.0 s) closes well before the 15 s clip,
    # so a decelerating clip comes to rest even though omega_final (2.0) is not near zero.
    assert seed["comes_to_rest"] is True
    # the alpha example must state the 2 s fit window, never the 15 s clip length.
    alpha_ex = next(e for exs in seed["worked_examples"].values() for e in exs
                    if "angular accel" in e["title"].lower())
    assert "/ 2" in alpha_ex["substitute"] and "15" not in alpha_ex["substitute"]
    for tier, exs in seed["worked_examples"].items():
        for e in exs:
            if "vs" in (e.get("substitute") or ""):        # Jensen: two expressions, checked below
                continue
            got = _eval_expr(e.get("substitute", ""))
            want = _num_in(e.get("result", ""))
            if got is None or want is None:
                continue
            # 3% relative, or 0.5 absolute (some results round to a whole count, e.g. "18 laps").
            assert abs(got - want) <= max(0.5, 0.03 * abs(want)), (tier, e["title"], got, want)


def _a1_stats():
    """A rest -> flick -> coast clip: it turns for only 2.0 s of a 15.0 s clip (A1)."""
    return {
        "object_name": "red ring", "scene_title": "red ring on a wheel",
        "summary": {"mean_r_m": 0.2, "mean_omega": 5.0, "mean_v": 1.0, "mean_ac": 5.0,
                    "max_ac": 8.0, "rotation_direction": "CCW"},
        "period_and_frequency": {"period_s": 1.2, "frequency_hz": 0.83},
        "angular_acceleration": {"motion_type": "decelerating", "alpha_rad_s2": -3.0,
                                 "alpha_r2": 0.99, "omega_initial": 8.0, "omega_final": 2.0,
                                 "a_t_mean_m_s2": 0.6, "fit_window_s": 2.0},
        "stable_phase": {"stable_mean_omega": 5.0},
        "calibration": {"r_fit_m": 0.2, "px_per_m": 1500.0, "r_fit_px": 300.0},
        "video_info": {"duration_s": 15.0},
        "tracking": {"active_duration_s": 2.0, "active_start_s": 1.0, "active_end_s": 3.0},
    }


def test_seed_rate_products_use_turning_window():
    """A1: laps and arc-length must multiply the rate by the TURNING window (2.0 s), never the
    clip length (15.0 s) — f x clip over-counts the laps ~7x here."""
    from analysis import material_seed as S
    seed = S.build_seed(_a1_stats(), None)
    assert abs(seed["turning_duration_s"] - 2.0) < 1e-6
    lap = next(e for e in seed["worked_examples"]["basic"] if "lap" in e["title"].lower()
               and "one lap" not in e["title"].lower())
    assert " 2" in lap["substitute"] and "15" not in lap["substitute"], lap["substitute"]
    assert round(0.83 * 2.0) == _num_in(lap["result"])            # ~2 laps, not ~12
    arc = next(q for q in seed["check_understanding"]["intermediate"]
               if "arc" in q["question"].lower())
    assert "15" not in arc["answer"] and "2" in arc["answer"], arc["answer"]


def test_wrong_duration_products_flags_clip_length():
    """A1 gate: a rate multiplied by ~clip-length is flagged; the same rate x turning window
    passes; and a clip that spins throughout (turning ~= clip) is never flagged."""
    seed = {"active_duration_s": 15.0, "turning_duration_s": 2.0,
            "variables": [{"symbol": "f", "value": 0.83}, {"symbol": "v", "value": 1.0},
                          {"symbol": "omega", "value": 5.0}]}
    assert G.wrong_duration_products("laps = 0.83 × 15 ≈ 12", seed)        # wrong duration
    assert G.wrong_duration_products("s = v·t ≈ 1.0 × 15 ≈ 15 m", seed)    # wrong duration
    assert not G.wrong_duration_products("laps = 0.83 × 2 ≈ 2", seed)      # correct duration
    spins_throughout = dict(seed, turning_duration_s=14.6)
    assert not G.wrong_duration_products("0.83 × 15", spins_throughout)    # clip IS the turn time


def test_rate_period_referent_flagged():
    """A9 gate: a lap time and a turns-per-second rate from different moments, written as one
    ('That turn rate...'), is flagged even though both numbers are individually grounded. The
    real fan-4027 basic sentence is the fixture."""
    seed = {"angular_acceleration": {"motion_type": "decelerating",
                                     "omega_initial": 3.033, "omega_final": 0.127},
            "variables": [{"symbol": "T", "value": 3.34}]}
    bad = ("Right after that first flick, it completes a full turn in just 2.07 seconds. "
           "That turn rate is about 0.30 full turns each second.")
    assert G.rate_period_referent(bad, seed)
    # same two numbers, each placed at its own moment -> fine
    assert not G.rate_period_referent(
        "Right after the flick a full turn takes 2.07 seconds; averaged over the whole clip it "
        "makes about 0.30 full turns each second.", seed)
    # reciprocal pair -> fine (0.30 turns/s IS a 3.34 s lap)
    assert not G.rate_period_referent(
        "One full turn takes about 3.34 seconds, so it makes about 0.30 full turns each second.",
        seed)
    # a cumulative milestone is not a period claim -> must not fire
    assert not G.rate_period_referent(
        "It makes about 0.30 full turns each second. After 5.17 seconds it has completed one "
        "full turn.", seed)
    assert not G.rate_period_referent("It turns steadily throughout the clip.", seed)
    # a rate that states its OWN period in the same clause is self-anchored, even when a
    # different lap time (the peak) appears elsewhere in the document
    assert not G.rate_period_referent(
        "At its fastest a lap takes 0.67 s. A revolution takes T = 0.805 s, or about 1.242 "
        "full turns each second.", seed)


def test_average_period_as_peak_flagged():
    """A2 gate: the clip-average period pinned to a peak/fastest moment is flagged; the same
    number attributed to the whole-spin average passes; and a clip whose peak lap barely
    differs from the average never fires."""
    seed = {"angular_acceleration": {"motion_type": "decelerating", "impulsive_start": True,
                                      "omega_initial": 9.37, "omega_final": 2.04},
            "variables": [{"symbol": "T", "value": 1.1}]}
    # peak lap ~= 2pi/9.37 = 0.67 s vs average T = 1.1 s
    assert G.average_period_as_peak(
        "Right after that flick it reaches its fastest pace, one full circle every 1.1 s", seed)
    assert not G.average_period_as_peak(
        "At its fastest a lap takes 0.67 s; averaged over the whole spin about 1.1 s", seed)
    assert not G.average_period_as_peak("It coasts at a steady rate", seed)   # no period value
    # a near-uniform clip (peak lap ~= average) must not fire even with fastest wording
    steady = dict(seed, angular_acceleration={"motion_type": "decelerating",
                                              "omega_initial": 5.9, "omega_final": 5.6})
    assert not G.average_period_as_peak("at its fastest one turn every 1.1 s", steady)


def test_annotation_issues_phase_count_and_phantom():
    """Axis-4 render-aware annotation gate: the prose may not claim more phases — or a phase word
    — than the figure draws; an empty phase list (uniform/oblique) disables the check."""
    ph = ["speeding up", "slowing down"]
    # C2 regression: three claimed, two rendered, plus a phantom "steady"
    bad = G.annotation_issues(
        "The graph highlights three distinct phases: speeding up, steady, and slowing down.", ph)
    assert any("3 phase" in b for b in bad)
    assert any("steady" in b for b in bad)
    # correct prose passes
    assert not G.annotation_issues("Two phases: speeding up then slowing down.", ph)
    assert not G.annotation_issues("It speeds up, then coasts and slows down.", ph)
    # no false positive when "steady" is not part of a phase enumeration
    assert not G.annotation_issues("Unlike a steady spin, the motion has clear phases here.", ph)
    # empty phases (uniform / oblique) => no check
    assert not G.annotation_issues("three distinct phases of speeding up and steady", [])


def test_seed_consistency_catches_broken_closure():
    # A self-consistent seed passes: v = omega*r, T = 2pi/omega, and Jensen <omega^2> >= <omega>^2.
    good = {
        "variables": [{"symbol": "r", "value": 0.15}, {"symbol": "omega", "value": 5.0},
                      {"symbol": "v", "value": 0.75}, {"symbol": "a_c", "value": 4.0},
                      {"symbol": "T", "value": 1.257}],
        "worked_examples": {}, "check_understanding": {},
        "measurement_honesty": {"intermediate": ""},
    }
    assert G.seed_consistency_issues(good) == []
    # The red-phone failure: the table quotes omega=2.89 but keeps v/T built from omega~5.79,
    # so v != omega*r and T != 2pi/omega. Both must be flagged.
    bad = dict(good, variables=[{"symbol": "r", "value": 0.15}, {"symbol": "omega", "value": 2.89},
                                {"symbol": "v", "value": 0.856}, {"symbol": "a_c", "value": 5.69},
                                {"symbol": "T", "value": 1.1}])
    issues = G.seed_consistency_issues(bad)
    assert any("v = omega*r broken" in i for i in issues), issues
    assert any("2pi/omega" in i for i in issues), issues
    # ...but if the honesty box flags the period as an average, the T gap is allowed (Jensen).
    noted = dict(bad, measurement_honesty={"intermediate": "the average period is not simply 2pi/omega"})
    assert not any("2pi/omega" in i for i in G.seed_consistency_issues(noted))


def test_period_identity_checked_when_unreliable():
    # On an oblique clip the arithmetic gate used to be skipped WHOLESALE, so a false
    # "2pi/omega = period" closure slipped through. The scale-free period identity must
    # still be checked (only per-instant v=omega*r / a_c=omega^2*r are exempt).
    seed = {"measurement_quality": {"reliable": False}, "variables": []}
    obj = {"tier": "intermediate",
           "sections": {"How the variables are related": "2π / 7.813 rad/s ≈ 0.837 s"}}
    issues = G.tier_gate(obj, seed)
    assert any("2pi / 7.813" in i and "arithmetic" in i for i in issues), issues


def test_reading_level_vocab_is_flagged_but_the_plain_version_is_not():
    """Rule 8c: three phrases a physics teacher flagged as beyond a high-school reader.

    Each reached the student only because our own spec asked for it, so the fix is a wording
    change — but it has to be enforceable, or the next run puts them straight back."""
    flagged = [
        "which reported quantities are calibration-independent",
        "the angular quantities are scale-free",
        "formally ⟨ω²⟩ ≥ ⟨ω⟩², a Jensen inequality",
    ]
    for text in flagged:
        kinds = [v["kind"] for v in G.vocab_issues(text)]
        assert "reading-level" in kinds, f"not flagged: {text!r}"
    plain = ("The angle measurements do not depend on how we sized the scene; the values in "
             "metres do. Squaring an average is not the same as averaging the squares, so "
             "putting the average turn rate in falls short.")
    assert G.vocab_issues(plain) == [], G.vocab_issues(plain)


def test_seed_student_text_is_at_reading_level_but_the_teacher_copy_is_not():
    """The formal version is re-routed, not deleted: the teacher notes still name Jensen's
    inequality and the calibration, and only they do."""
    import analysis.material_seed as S
    ctx = {"obj": "the toy", "motion": "decelerating", "unreliable": False,
           "px_per_m": 559.0, "omega": 5.7, "a_c": 26.9, "r": 0.635}
    for tier, text in S._honesty(ctx).items():
        assert G.vocab_issues(text) == [], f"{tier} honesty box: {G.vocab_issues(text)}"
    for tier, objs in S._objectives(dict(ctx, obj="the toy")).items():
        joined = " ".join(objs)
        assert G.vocab_issues(joined) == [], f"{tier} objectives: {G.vocab_issues(joined)}"
    notes = S._teacher_notes(ctx)
    body = " ".join(n["title"] + " " + n["body"] for n in notes["advanced"])
    assert "Jensen" in body and "calibrat" in body, body


def _pedagogy_ctx(**over):
    ctx = {"obj": "black handle", "motion": "decelerating", "unreliable": False,
           "px_per_m": 1875.0, "omega": 7.8, "a_c": 16.05, "r": 0.26, "T": 0.814,
           "f": 1.23, "dur": 15.0, "turning_dur": 15.0, "comes_to_rest": False,
           "tl": [{"t_s": 0.0, "omega_rad_s": 9.32, "v_m_s": 2.42, "a_c_m_s2": 22.6},
                  {"t_s": 5.0, "omega_rad_s": 8.40, "v_m_s": 2.18, "a_c_m_s2": 18.3},
                  {"t_s": 10.0, "omega_rad_s": 7.40, "v_m_s": 1.92, "a_c_m_s2": 14.2},
                  {"t_s": 15.0, "omega_rad_s": 6.26, "v_m_s": 1.63, "a_c_m_s2": 10.2}]}
    ctx.update(over)
    return ctx


def test_the_reader_is_asked_to_predict_before_the_measurement_is_revealed():
    """A worksheet built from a video should stop before the reveal — that is the one thing
    the medium buys that a textbook cannot. Every prediction has to be about THIS clip's data
    and must never carry its own answer on the student page."""
    import analysis.material_seed as S
    p = S._predict_first(_pedagogy_ctx())
    for tier in ("basic", "intermediate"):
        assert p[tier], f"{tier} has no prediction"
    for tier, items in p.items():
        for it in items:
            assert it["prompt"] and it["answer"]
            assert G.vocab_issues(it["prompt"]) == [], it["prompt"]
    # A decelerating clip must not be handed the accelerating prediction, or the answer is wrong.
    assert "fewer" in p["basic"][0]["answer"].lower()
    assert "more" in S._predict_first(_pedagogy_ctx(motion="accelerating"))["basic"][0]["answer"].lower()
    assert "quarter" in p["intermediate"][0]["answer"].lower()   # the square law, pre-committed


def test_misconceptions_stay_inside_the_kinematics_fence():
    """The material never names a cause (rule 8b), so the dynamics misconceptions are out of
    reach. The ones we DO pose have to survive the gate that grades the passage they sit in."""
    import analysis.material_seed as S
    m = S._misconceptions(_pedagogy_ctx())
    assert all(m[t] for t in ("basic", "intermediate", "advanced"))
    for tier, items in m.items():
        for it in items:
            assert it["misconception"] and it["question"] and it["answer"]
            assert G.vocab_issues(it["question"]) == [], (tier, it["question"])
            assert G.vocab_issues(it["answer"]) == [], (tier, it["answer"])
    # A uniform clip has no tangential acceleration, so it must not be asked to compare the two.
    uni = S._misconceptions(_pedagogy_ctx(motion="uniform"))["advanced"]
    assert not any("along the direction of travel" in i["question"] for i in uni), uni


def test_transfer_moves_the_idea_off_this_one_object():
    """One clip binds the concept to one object. The transfer prompt has to name a DIFFERENT
    setting, and must not invent numbers for a scene we never measured."""
    import analysis.material_seed as S
    import re as _re
    t = S._transfer(_pedagogy_ctx())
    for tier, items in t.items():
        for it in items:
            assert G.vocab_issues(it["question"]) == [], (tier, it["question"])
            # No fabricated measurement: only bare ratios ("three times") are allowed.
            nums = _re.findall(r"\d+\.\d+", it["question"])
            assert not nums, (tier, nums)


def test_advanced_worked_examples_fade_after_the_first():
    """Expertise reversal: the first example is the model, the rest are completion problems."""
    import analysis.material_seed as S
    adv = S._worked_examples(_pedagogy_ctx(alpha=-0.204, omega_i=9.32, omega_f=6.26,
                                           a_t=-0.0532, fit_dt=15.0))["advanced"]
    assert len(adv) >= 2, adv
    assert not adv[0].get("fade"), "the first example must stay fully worked"
    assert all(e.get("fade") for e in adv[1:]), "every later example should fade"


def test_a_number_the_quality_policy_dictates_counts_as_grounded():
    """Found on turntable-2. On a clip with too few revolutions to verify the within-turn
    detail, the writer is INSTRUCTED to say "this clip covers only 1.47 revolutions" — and was
    then failed for the 1.47. Anything the pipeline puts in the writer's mouth is grounded."""
    seed = _seed(motion="decelerating")
    seed["measurement_quality"] = {"reliable": False, "n_revolutions": 1.47,
                                   "omega_phaselocked_fraction": 0.517, "orbit_axis_ratio": 1.021}
    allowed = G.allowed_values(seed)
    assert G.grounded(1.47, allowed)
    assert not G.grounded(3.91, allowed), "an unrelated number must still be ungrounded"


def test_a_squared_exponent_is_not_a_rate_times_the_clip_length():
    """Found on turntable-3. The advanced averaging example writes "(average omega)^2 * r = 5.79
    ...", which offered the wrong-duration check a bare "2" as a rate and the 5.79 rad/s turn
    rate beside it as a time — and on that clip 5.79 sits within 3% of the 5.87 s clip length.
    An exponent is not a factor. The real fault it exists to catch must still fire."""
    seed = _seed(motion="decelerating")
    seed.update({"active_duration_s": 5.87, "turning_duration_s": 1.94})
    seed["variables"] = [{"symbol": "r", "value": 0.148}, {"symbol": "omega", "value": 5.79},
                         {"symbol": "f", "value": 0.92}]
    ok = "(average ω)²·r = 5.79² × 0.148 = 4.96"
    assert G.wrong_duration_products(ok, seed) == [], G.wrong_duration_products(ok, seed)
    bad = "laps = 0.92 × 5.87 ≈ 5.4"
    assert G.wrong_duration_products(bad, seed), "a rate times the CLIP length must still fail"


def test_a_steady_PHASE_the_figure_draws_is_not_a_faithfulness_error():
    """Found live on the fan clip. The omega(t) figure draws a steady band and prints the word
    "steady" on it, and we hand the writer that phase list — then failed the passage for
    narrating it. A steady PHASE named alongside the other phases is allowed; calling the whole
    motion constant is still an error, and so is a steady phrase on a clip with no steady band."""
    seed = _seed(motion="decelerating")
    drawn = ["speeding up", "steady", "slowing down", "steady"]
    ok = ("The motion unfolds in four phases: an initial speed-up right after the flick, a "
          "brief steady spin, a long coasting slowdown, and a final steady pause.")
    assert G.motion_faithfulness(seed, ok, drawn) == [], G.motion_faithfulness(seed, ok, drawn)
    bad = "Throughout the clip the blade turns at a constant rate."
    assert G.motion_faithfulness(seed, bad, drawn), "a blanket constant-rate claim must still fail"
    # No steady band on the figure -> the carve-out does not apply, however it is phrased.
    assert G.motion_faithfulness(seed, ok, ["speeding up", "slowing down"])
    assert G.motion_faithfulness(seed, ok, [])


def test_b3_elapsed_time_between_two_grounded_instants_is_grounded():
    """Step B3 asks the reader to read two instants off the graph and say how long the fall
    took. The first live run flagged that answer as a fabricated number: the seed's timeline is
    at 22.21/40.38 s, so 18.2 s IS the exercise. Differences between grounded instants count;
    an unrelated number still does not."""
    seed = _seed(motion="decelerating")
    seed["timeline"] = [{"t_s": 22.21, "omega_rad_s": 11.586},
                        {"t_s": 40.38, "omega_rad_s": 6.417},
                        {"t_s": 58.56, "omega_rad_s": 2.923},
                        {"t_s": 76.73, "omega_rad_s": 1.16}]
    allowed = G.allowed_values(seed)
    assert G.grounded(18.2, allowed), "elapsed time between two timeline instants"
    assert G.grounded(36.4, allowed), "elapsed time across two steps"
    assert G.grounded(5.17, allowed), "the drop in turn rate over that stretch"
    assert not G.grounded(47.3, allowed), "an unrelated number must still be ungrounded"


def test_each_level_is_a_three_step_staircase_with_a_bridge_onto_the_next():
    """WS-4: three graded steps inside every level, and a bridge that names the step it hands
    over to. A bridge that only advertises "the next edition" is what left the three tiers
    reading as three separate documents rather than one staircase."""
    import analysis.material_seed as S
    for tier in ("basic", "intermediate", "advanced"):
        steps = S.TIER_STEPS[tier]
        assert len(steps) == 3, f"{tier}: {len(steps)} steps"
        for s in steps:
            assert s["title"] and s["goal"]
            assert G.vocab_issues(s["title"] + " " + s["goal"]) == [], s
    # basic -> B1 and intermediate -> C1 each name the step they lead into.
    assert "step 1" in S.TIER_BRIDGE["basic"].lower()
    assert "step 1" in S.TIER_BRIDGE["intermediate"].lower()
    assert S.TIER_BRIDGE["advanced"] == ""      # the top of the ladder leads nowhere
    # The writer is told the same order the reader is shown, or the map won't match the terrain.
    from analysis import material_tiers as T
    seed = {"tier_steps": S.TIER_STEPS}
    for tier in ("basic", "intermediate", "advanced"):
        pol = T._steps_policy(tier, seed)
        assert all(s["title"] in pol for s in S.TIER_STEPS[tier]), tier


def test_c3_claims_task_is_advanced_only_and_grounded_in_this_clip():
    """The honesty argument as a TASK (advanced step 3), not as vocabulary — and built from
    what this clip measured, so it is never a generic list."""
    import analysis.material_seed as S
    ctx = {"obj": "black handle", "motion": "decelerating", "unreliable": False,
           "px_per_m": 1875.0, "omega": 7.8, "a_c": 16.05, "r": 0.26, "T": 0.814,
           "f": 1.23, "dur": 15.0, "turning_dur": 15.0, "comes_to_rest": False,
           "tl": [{"t_s": 0.0}, {"t_s": 5.0}, {"t_s": 10.0}, {"t_s": 15.0}]}
    review = S._claims_review(ctx)
    assert review["basic"] == [] and review["intermediate"] == []
    items = review["advanced"]
    assert len(items) >= 4, items
    for it in items:
        assert it["claim"] and it["verdict"] and it["why"]
        assert G.vocab_issues(it["claim"]) == [], it["claim"]
    joined = " ".join(it["claim"] for it in items)
    assert "0.814" in joined and "16" in joined, joined       # this clip's own numbers
    # An unreliable clip trades the steady-rate claim for a per-instant one, pinned to a real
    # instant from this clip's own timeline rather than an invented time.
    unreliable = " ".join(i["claim"] for i in S._claims_review(dict(ctx, unreliable=True))["advanced"])
    assert "perfectly steady rate" not in unreliable
    assert "at t = 5 s" in unreliable.lower(), unreliable


def test_tier_spec_never_hands_the_writer_banned_vocabulary():
    """What a tier is TOLD to write must survive the gate that grades it.

    The spec used to describe the advanced tier's picture as "an annotated frame" and the
    oblique-clip caveat as "the orbit was filmed at an oblique angle" — both built out of
    words on TRACKING_VOCAB, so the writer dutifully echoed them and failed its own gate on
    the roundabout clip. Any wording the prompt asks for has to be sayable."""
    from analysis import material_tiers as T
    from analysis import quality_signals as Q
    for tier, spec in T.TIERS.items():
        for field in ("seed_fields", "forbidden", "figures", "sentences"):
            hits = G._vocab_scan(G._TRACKING_RE, spec[field], "tracking")
            hits += G._vocab_scan(G._READING_RE, spec[field], "reading-level")
            assert not hits, f"{tier}.{field} asks for banned vocabulary: {hits}"
    unreliable = T._quality_policy({"measurement_quality": {"reliable": False,
                                                            "guidance": Q.__doc__ or ""}})
    assert unreliable, "oblique policy should be non-empty"
    # The instruction body may NAME a banned word to forbid it (rule 8 does), but the
    # sentence it asks for must not be built from one: check the phrasing it dictates.
    dictated = unreliable.split("include ONE plain sentence that the", 1)[-1].split("(say it")[0]
    hits = G._vocab_scan(G._TRACKING_RE, dictated, "tracking")
    assert not hits, f"oblique caveat dictates banned vocabulary: {hits}"


def test_squared_units_are_not_read_as_division():
    """"3.85 rad^2/s^2" is a unit, not "3.85 squared divided by 2" (= 7.41). The fan clip's
    correct a_c substitution, written as an arrow chain, was flagged on that misreading."""
    ok = ("ω = 1.962 rad/s → (squared) → 3.85 rad²/s² → (× r = 0.317 m) → "
          "a_c = 1.22 m/s², which matches the measured value.")
    assert all(c["ok"] for c in G.arithmetic_claims(ok)), G.arithmetic_claims(ok)
    # the same notation with a wrong product must still fail
    bad = "ω = 2.0 rad/s → (squared) → 4.0 rad²/s² → (× r = 0.5 m) → a_c = 9.9 m/s²"
    assert any(not c["ok"] for c in G.arithmetic_claims(bad)), G.arithmetic_claims(bad)


def test_frame_fallback_story_is_sayable_by_every_tier():
    """All three tiers must open by retelling the shared story, so the story is held to the
    same vocabulary they are graded on. The deterministic fallback is the floor: it has to be
    clean for every motion type, or a network blip poisons all three tiers at once."""
    from analysis import material_tiers as T
    for mt in ("decelerating", "accelerating", "uniform"):
        for rest in (True, False):
            seed = {"object_name": "the black handle", "scene_title": "Spinning Black Handle",
                    "angular_acceleration": {"motion_type": mt}, "comes_to_rest": rest}
            story = T._frame_fallback(seed)["scenario_story"]
            assert not G.vocab_issues(story), f"{mt}/{rest}: {G.vocab_issues(story)}"


def run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"[PASS] {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} gate tests passed")


if __name__ == "__main__":
    run()
