"""Tiered physics question generation from the student's measured data.

Replicates fastapi-gpt's easy/intermediate/advanced question endpoints, but consumes
our MeasurementContext (video-measured) and grounds questions in the KG difficulty rules
+ formulas. Complements the Socratic inquiry tutor: this is assessment, that is dialogue.
"""
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import jsonutil, knowledge, llm, student_model
from .inquiry.schemas import MeasurementContext

router = APIRouter(prefix="/questions", tags=["questions"])

_DIFFICULTIES = ("easy", "intermediate", "advanced")
_BAND_DIFFICULTY = {"high": "advanced", "medium": "intermediate",
                    "low": "easy", "neutral": "intermediate"}
_LANG = {"en": "English", "id": "Bahasa Indonesia"}


class QuestionGenRequest(BaseModel):
    user_id: str
    measurement: MeasurementContext
    difficulty: Optional[str] = None   # default: derived from the student's ability band
    count: int = 3
    topic: str = "centripetal acceleration"
    language: str = "en"


class Question(BaseModel):
    stem: str
    type: Optional[str] = None
    answer: Optional[str] = None
    solution: Optional[str] = None


class QuestionSet(BaseModel):
    difficulty: str
    questions: List[Question]


def _opt(v):
    return str(v).strip() if v is not None else None


def _messages(measurement, difficulty, count, language, topic):
    m = measurement
    ctx = (f"radius r = {m.radius_m} m, angular velocity w = {m.mean_omega_rad_s} rad/s, "
           f"centripetal acceleration a = {m.mean_ac_m_s2} m/s^2, period T = {m.period_s} s")
    drules = knowledge.difficulty_rules(difficulty)
    system = (
        "You are a physics question author for circular motion. Generate questions grounded in "
        "the student's measured data. Every value a question needs must be stated in its stem. "
        "Never invent measurements.\n\n"
        f"DIFFICULTY RULES ({difficulty}):\n" + "\n".join(f"- {r}" for r in drules)
        + "\n\nFormulas:\n" + "\n".join(f"- {f}" for f in knowledge.formulas())
    )
    lang = _LANG.get((language or "en").lower(), "English")
    user = (
        f"Topic: {topic}\nMeasured data: {ctx}.\n\n"
        f"Write {count} {difficulty} questions in {lang}. Return ONLY a JSON array (no prose):\n"
        '[{"stem": "...", "type": "numeric|conceptual", "answer": "<final answer with unit>", '
        '"solution": "<short worked solution>"}]'
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _generate(req, difficulty):
    count = max(1, min(req.count, 8))
    messages = _messages(req.measurement, difficulty, count, req.language, req.topic)
    try:
        raw = llm.chat(messages, temperature=0.6)
    except llm.LLMError as e:
        raise HTTPException(status_code=502, detail=str(e))
    items = jsonutil.first_array(raw)
    if not items:
        raise HTTPException(status_code=502, detail="Question author returned unparseable output")
    questions = [
        Question(stem=_opt(it.get("stem")), type=_opt(it.get("type")),
                 answer=_opt(it.get("answer")), solution=_opt(it.get("solution")))
        for it in items if isinstance(it, dict) and it.get("stem")
    ]
    if not questions:
        raise HTTPException(status_code=502, detail="No valid questions produced")
    return QuestionSet(difficulty=difficulty, questions=questions)


@router.post("/generate", response_model=QuestionSet)
def generate(req: QuestionGenRequest):
    difficulty = (req.difficulty
                  or _BAND_DIFFICULTY.get(student_model.ability_band(req.user_id), "intermediate")).lower()
    if difficulty not in _DIFFICULTIES:
        raise HTTPException(status_code=400, detail=f"difficulty must be one of {_DIFFICULTIES}")
    return _generate(req, difficulty)


@router.post("/easy", response_model=QuestionSet)
def easy(req: QuestionGenRequest):
    return _generate(req, "easy")


@router.post("/intermediate", response_model=QuestionSet)
def intermediate(req: QuestionGenRequest):
    return _generate(req, "intermediate")


@router.post("/advanced", response_model=QuestionSet)
def advanced(req: QuestionGenRequest):
    return _generate(req, "advanced")
