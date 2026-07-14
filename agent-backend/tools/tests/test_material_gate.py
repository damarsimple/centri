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


def run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"[PASS] {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} gate tests passed")


if __name__ == "__main__":
    run()
