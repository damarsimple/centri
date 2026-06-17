from typing import List, Optional

from pydantic import BaseModel


class MeasurementContext(BaseModel):
    """Physics measured from the student's video — the seam from agent-backend."""
    object_label: Optional[str] = None
    radius_m: Optional[float] = None
    mean_omega_rad_s: Optional[float] = None
    mean_ac_m_s2: Optional[float] = None
    period_s: Optional[float] = None

    @classmethod
    def from_agent_stats(cls, stats):
        """Build from agent-backend's /result `stats` dict (prefers stable-phase values)."""
        def g(*keys):
            for k in keys:
                v = stats.get(k)
                if v is not None:
                    return v
            return None
        return cls(
            object_label=g("object_name"),
            radius_m=g("r_fit_m", "mean_r_m"),
            mean_omega_rad_s=g("stable_mean_omega", "mean_omega"),
            mean_ac_m_s2=g("stable_mean_ac", "mean_ac"),
            period_s=g("period_s"),
        )


class GenerateProblemFindingRequest(BaseModel):
    user_id: str
    topic: str = "centripetal acceleration"
    language: str = "en"


class GenerateStage1Request(BaseModel):
    user_id: str
    object_label: str
    topic: str = "centripetal acceleration"
    language: str = "en"


class GenerateStage2Request(BaseModel):
    user_id: str
    measurement: MeasurementContext
    topic: str = "centripetal acceleration"
    language: str = "en"


class GenerateProblemGeneratingRequest(BaseModel):
    user_id: str
    measurement: MeasurementContext
    object_label: Optional[str] = None
    topic: str = "centripetal acceleration"
    language: str = "en"


class GenerateInquiryResponse(BaseModel):
    inquiry_id: str
    stage: str
    inquiry: str
    difficulty: str


class GeneratedProblem(BaseModel):
    problem: str
    answer: Optional[str] = None
    solution: Optional[str] = None
    difficulty: str


class SubmitResponseRequest(BaseModel):
    user_id: str
    user_answer: str
    inquiry: Optional[str] = None      # the question answered; or omit and pass inquiry_id
    inquiry_id: Optional[str] = None   # if set and stored, the inquiry text is looked up
    stage: str = "problem_exploring_stage_1"
    object_label: Optional[str] = None
    measurement: Optional[MeasurementContext] = None
    language: str = "en"


class SubmitResponseResult(BaseModel):
    is_correct: bool
    feedback: str
    next_step: str
    detected_misconception: Optional[str] = None
    concept_coverage: Optional[List[str]] = None
