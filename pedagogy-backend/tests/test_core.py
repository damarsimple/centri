"""Core logic tests (no network / LLM). Run: pytest -q

Uses a temp sqlite db set before importing app modules.
"""
import os
import tempfile

os.environ["PEDAGOGY_DB_PATH"] = os.path.join(tempfile.gettempdir(), "pedagogy_pytest.db")

from app import db, jsonutil, knowledge, misconceptions, scoring, student_model, inquiry_store
from app.inquiry import prompts, schemas, testsets


def setup_module(_module):
    if os.path.exists(os.environ["PEDAGOGY_DB_PATH"]):
        os.remove(os.environ["PEDAGOGY_DB_PATH"])
    db.init_all()


# ── Knowledge graph ──
def test_knowledge_graph():
    assert len(knowledge.core_concepts()) >= 3
    assert knowledge.object_facts("ceiling fan")            # keyword match
    assert knowledge.object_facts("totally unknown") is None
    assert knowledge.formulas()
    assert "CORE CONCEPTS" in knowledge.grounding_block("problem_exploring", "advanced")
    assert knowledge.graph_pattern_facts()


# ── Ability band ──
def test_ability_band():
    assert student_model.compute_ability_band("2/10") == "high"
    assert student_model.compute_ability_band("5/10") == "medium"
    assert student_model.compute_ability_band("9/10") == "low"
    assert student_model.compute_ability_band("") == "neutral"
    assert student_model.compute_ability_band("bad") == "neutral"


# ── Student model ──
def test_student_model_roundtrip():
    student_model.upsert_profile("t_user", iq_rank_order="2/10")
    assert student_model.ability_band("t_user") == "high"
    student_model.increment_questions_answered("t_user")
    assert student_model.get_profile("t_user")["questions_answered"] >= 1
    student_model.add_misconception("t_user", "omega_linear")
    assert "omega_linear" in student_model.get_misconceptions("t_user")


# ── Inquiry persistence ──
def test_inquiry_persistence():
    inquiry_store.save_inquiry("q1", "t_user", "problem_exploring_stage_1",
                               "Q?", "easy", object_label="fan")
    assert inquiry_store.get_inquiry("q1")["inquiry"] == "Q?"
    inquiry_store.save_response("q1", "t_user", "ans", True, "fb", "ns",
                                "omega_linear", ["inward_direction"])
    h = inquiry_store.session_history("t_user")
    assert h["inquiries"] and h["responses"]


# ── Misconception taxonomy ──
def test_misconceptions():
    assert misconceptions.is_valid("centrifugal_confusion")
    assert not misconceptions.is_valid("nope")
    assert len(misconceptions.ids()) == 6


# ── Concept coverage (EN + ID) ──
def test_scoring_bilingual():
    assert "inward_direction" in scoring.covered_concepts("points inward toward the center")
    assert "omega_squared" in scoring.covered_concepts("it depends on omega squared")
    assert "force_source" in scoring.covered_concepts("tegangan tali menariknya")


# ── JSON extraction ──
def test_jsonutil():
    assert jsonutil.first_object('noise {"a": 1} tail') == {"a": 1}
    assert jsonutil.first_array('```json\n[{"x": 1}]\n```') == [{"x": 1}]
    assert jsonutil.first_object("no json here") is None
    assert jsonutil.first_array("{}") is None


# ── The seam: agent stats → MeasurementContext ──
def test_measurement_from_stats():
    mc = schemas.MeasurementContext.from_agent_stats({
        "object_name": "phone", "stable_mean_omega": 6.04, "r_fit_m": 0.15,
        "stable_mean_ac": 5.6, "period_s": 1.04,
    })
    assert mc.object_label == "phone"
    assert mc.mean_omega_rad_s == 6.04
    assert mc.radius_m == 0.15
    # falls back to non-stable keys
    mc2 = schemas.MeasurementContext.from_agent_stats({"mean_omega": 3.0, "mean_r_m": 0.2})
    assert mc2.mean_omega_rad_s == 3.0 and mc2.radius_m == 0.2


# ── Prompt builders ──
def test_prompt_builders():
    pf, d = prompts.problem_finding_generate_messages("low", "id", "centripetal acceleration")
    assert d == "easy" and "Bahasa" in pf[1]["content"]
    s1, _ = prompts.stage1_generate_messages("turntable", "high", "en", "centripetal acceleration")
    assert "turntable" in s1[1]["content"]
    mc = schemas.MeasurementContext(radius_m=0.15, mean_omega_rad_s=6.04,
                                    mean_ac_m_s2=5.6, period_s=1.04)
    pg, _ = prompts.problem_generating_messages(mc, "turntable", "high", "en", "centripetal acceleration")
    assert '"problem"' in pg[1]["content"]


# ── Testsets ──
def test_testsets_loaded():
    assert len(testsets.stage1_rows()) > 0
    assert len(testsets.stage2_rows()) > 0
    block = testsets.fewshot_block(testsets.stage1_rows(), limit=2)
    assert "Inquiry:" in block
