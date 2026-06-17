"""Staged inquiry endpoints — the interactive tutor.

Flow: problem-finding → problem-exploring stage-1 (object) → stage-2 (data) →
problem-generating. Every generated inquiry is persisted; submit-response can look it
up by id, evaluates the answer (non-revealing feedback + next step + concept coverage),
records misconceptions, and logs the turn.
"""
import uuid

from fastapi import APIRouter, HTTPException

from .. import inquiry_store, llm, misconceptions, scoring, student_model
from . import prompts, schemas

router = APIRouter(prefix="/inquiry", tags=["inquiry"])


def _clean_question(text):
    """Keep the first non-empty line; strip quotes/fences the model may add."""
    line = next((l.strip() for l in text.splitlines() if l.strip()), text.strip())
    return line.strip().strip('"').strip("`").strip()


def _generate(messages, difficulty, stage, user_id, object_label=None, measurement=None):
    try:
        text = llm.chat(messages, temperature=0.7)
    except llm.LLMError as e:
        raise HTTPException(status_code=502, detail=str(e))
    resp = schemas.GenerateInquiryResponse(
        inquiry_id=str(uuid.uuid4()), stage=stage,
        inquiry=_clean_question(text), difficulty=difficulty)
    inquiry_store.save_inquiry(resp.inquiry_id, user_id, stage, resp.inquiry, difficulty,
                               object_label, measurement)
    return resp


@router.post("/generate/problem-finding", response_model=schemas.GenerateInquiryResponse)
def generate_problem_finding(req: schemas.GenerateProblemFindingRequest):
    band = student_model.ability_band(req.user_id)
    messages, difficulty = prompts.problem_finding_generate_messages(band, req.language, req.topic)
    return _generate(messages, difficulty, "problem_finding", req.user_id)


@router.post("/generate/problem-exploring-stage-1", response_model=schemas.GenerateInquiryResponse)
def generate_stage1(req: schemas.GenerateStage1Request):
    band = student_model.ability_band(req.user_id)
    messages, difficulty = prompts.stage1_generate_messages(
        req.object_label, band, req.language, req.topic)
    return _generate(messages, difficulty, "problem_exploring_stage_1", req.user_id,
                     object_label=req.object_label)


@router.post("/generate/problem-exploring-stage-2", response_model=schemas.GenerateInquiryResponse)
def generate_stage2(req: schemas.GenerateStage2Request):
    band = student_model.ability_band(req.user_id)
    messages, difficulty = prompts.stage2_generate_messages(
        req.measurement, band, req.language, req.topic)
    return _generate(messages, difficulty, "problem_exploring_stage_2", req.user_id,
                     object_label=req.measurement.object_label, measurement=req.measurement)


@router.post("/generate/problem-exploring-stage-2/from-job/{job_id}",
             response_model=schemas.GenerateInquiryResponse)
def generate_stage2_from_job(job_id: str, user_id: str, language: str = "en",
                             topic: str = "centripetal acceleration"):
    from .. import measurement  # lazy: pulls `requests` only when this path is used
    try:
        m = measurement.fetch_measurement(job_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not fetch measurement for job {job_id}: {e}")
    band = student_model.ability_band(user_id)
    messages, difficulty = prompts.stage2_generate_messages(m, band, language, topic)
    return _generate(messages, difficulty, "problem_exploring_stage_2", user_id,
                     object_label=m.object_label, measurement=m)


@router.post("/generate/problem-generating", response_model=schemas.GeneratedProblem)
def generate_problem(req: schemas.GenerateProblemGeneratingRequest):
    band = student_model.ability_band(req.user_id)
    messages, difficulty = prompts.problem_generating_messages(
        req.measurement, req.object_label, band, req.language, req.topic)
    try:
        data, _raw = llm.chat_json(messages, temperature=0.5)
    except llm.LLMError as e:
        raise HTTPException(status_code=502, detail=str(e))
    if not data or not data.get("problem"):
        raise HTTPException(status_code=502, detail="Problem author returned unparseable output")

    def _s(v):
        return str(v).strip() if v is not None else None

    return schemas.GeneratedProblem(
        problem=_s(data.get("problem")),
        answer=_s(data.get("answer")),
        solution=_s(data.get("solution")),
        difficulty=difficulty,
    )


@router.post("/submit-response", response_model=schemas.SubmitResponseResult)
def submit_response(req: schemas.SubmitResponseRequest):
    inquiry_text = req.inquiry
    object_label = req.object_label
    if not inquiry_text and req.inquiry_id:
        stored = inquiry_store.get_inquiry(req.inquiry_id)
        if stored:
            inquiry_text = stored.get("inquiry")
            object_label = object_label or stored.get("object_label")
    if not inquiry_text:
        raise HTTPException(status_code=400, detail="Provide `inquiry` text or a known `inquiry_id`")

    prior = student_model.get_misconceptions(req.user_id)
    covered = scoring.covered_concepts(req.user_answer)
    messages = prompts.submit_feedback_messages(
        inquiry_text, req.user_answer, object_label, req.measurement,
        req.language, prior, covered)
    try:
        data, _raw = llm.chat_json(messages, temperature=0.3)
    except llm.LLMError as e:
        raise HTTPException(status_code=502, detail=str(e))
    if not data:
        raise HTTPException(status_code=502, detail="Tutor returned an unparseable response")

    student_model.increment_questions_answered(req.user_id)

    mid = data.get("detected_misconception")
    mid = str(mid).strip() if mid is not None else ""
    if mid.lower() in ("null", "none", "") or not misconceptions.is_valid(mid):
        mid = None
    if mid:
        student_model.add_misconception(req.user_id, mid, req.inquiry_id)

    is_correct = bool(data.get("is_correct", False))
    feedback = str(data.get("feedback", "")).strip()
    next_step = str(data.get("next_step", "")).strip()
    inquiry_store.save_response(req.inquiry_id, req.user_id, req.user_answer,
                                is_correct, feedback, next_step, mid, covered)

    return schemas.SubmitResponseResult(
        is_correct=is_correct,
        feedback=feedback,
        next_step=next_step,
        detected_misconception=mid,
        concept_coverage=covered or None,
    )


@router.get("/history/{user_id}")
def history(user_id: str):
    return inquiry_store.session_history(user_id)
