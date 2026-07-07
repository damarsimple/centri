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


def run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"[PASS] {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} gate tests passed")


if __name__ == "__main__":
    run()
