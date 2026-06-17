"""Student profile endpoints — set ability (from IQ rank) and read misconception history."""
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from . import student_model

router = APIRouter(prefix="/students", tags=["students"])


class ProfileUpsert(BaseModel):
    user_id: str
    grade_level: Optional[str] = None
    iq_rank_order: Optional[str] = None  # "A/Total" → ability band (high/medium/low)
    ability_band: Optional[str] = None   # or set the band directly


@router.post("/profile")
def upsert_profile(req: ProfileUpsert):
    student_model.upsert_profile(
        req.user_id, req.grade_level, req.iq_rank_order, req.ability_band)
    return student_model.get_profile(req.user_id)


@router.get("/profile/{user_id}")
def get_profile(user_id: str):
    return student_model.get_profile(user_id) or {"user_id": user_id, "exists": False}


@router.get("/misconceptions/{user_id}")
def get_misconceptions(user_id: str):
    return {"user_id": user_id, "misconceptions": student_model.get_misconceptions(user_id)}
