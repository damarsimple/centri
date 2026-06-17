from pydantic import BaseModel
from typing import Optional, Dict, Any, List


class AnalyzeResponse(BaseModel):
    job_id: str


class DetectedObject(BaseModel):
    label: Optional[str] = None
    bbox: Optional[List[float]] = None  # [x, y, w, h] in frame pixels
    confidence: Optional[float] = None


class ReferenceObject(DetectedObject):
    physical_size_m: Optional[float] = None
    size_basis: Optional[str] = None


class SceneSuggestion(BaseModel):
    """Advisory annotation pre-fill from a single-frame VLM pass (/suggest-scene)."""
    moving_object: Optional[DetectedObject] = None
    reference_object: Optional[ReferenceObject] = None
    rotation_center_px: Optional[List[float]] = None  # [cx, cy] in frame pixels
    frame_w: int
    frame_h: int
    notes: Optional[str] = None


class VerifiedObject(BaseModel):
    cx: Optional[float] = None
    cy: Optional[float] = None
    bbox: Optional[List[float]] = None  # [x, y, w, h] in frame pixels


class VerifyResponse(BaseModel):
    """SAM3 single-frame grounding result, keyed by the requested label.
    A null value means SAM3 could not find that label in the frame."""
    frame_w: int
    frame_h: int
    objects: Dict[str, Optional[VerifiedObject]]


class FeedbackRequest(BaseModel):
    """HITL signal: 'setup_correction' (implicit) or 'result_feedback' (explicit)."""
    type: str
    job_id: Optional[str] = None
    user_id: Optional[str] = None
    role: Optional[str] = None  # 'student' | 'teacher'
    payload: Dict[str, Any] = {}


class FeedbackResponse(BaseModel):
    stored: bool
    id: str


class ActivityItem(BaseModel):
    """One concrete action the agent took, for the live feed."""
    seq: int
    kind: str           # run | read | write | track
    title: str
    detail: Optional[str] = None
    status: str         # running | done | error


class StageItem(BaseModel):
    """A named pipeline stage shown as a checklist."""
    key: str
    label: str
    status: str         # pending | active | done


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    step: Optional[str] = None
    progress_pct: Optional[int] = None
    message: Optional[str] = None
    elapsed_s: Optional[int] = None
    # Interactive agentic feed
    phase: Optional[str] = None
    current_action: Optional[str] = None
    thinking: Optional[str] = None
    stages: Optional[List[StageItem]] = None
    activities: Optional[List[ActivityItem]] = None


class FilePaths(BaseModel):
    student_pdf: str
    teacher_pdf: str
    annotated_video: str
    summary_panel: str
    # Per-frame kinematics time-series (time_s, omega_rad_s, ac_m_s2, ...).
    # Optional so older cached results (written before this field existed) still deserialize.
    kinematics_csv: Optional[str] = None


class MotionSeries(BaseModel):
    """Per-frame kinematics time-series, parsed from kinematics.csv, so the app can
    render its own native charts instead of a baked summary_panel.png."""
    t_s: List[float]
    omega_rad_s: List[float]
    ac_m_s2: List[float]
    v_m_s: List[float]
    r_m: List[float]
    theta_rad: List[float]
    active: List[int]


class QuestionItem(BaseModel):
    """One generated practice question (student sees the stem; teacher sees answer+solution)."""
    id: Optional[Any] = None
    bloom_level: Optional[str] = None
    format: Optional[str] = None
    difficulty: Optional[str] = None
    stem: Optional[str] = None
    given: Optional[Dict[str, Any]] = None
    answer: Optional[Any] = None
    answer_exact: Optional[Any] = None
    unit: Optional[str] = None
    solution: Optional[str] = None
    tolerance_pct: Optional[float] = None


class Worksheet(BaseModel):
    """The report content, structured for native rendering (no PDF)."""
    object_name: Optional[str] = None
    scenario: Optional[str] = None
    questions: List[QuestionItem] = []


class JobResultResponse(BaseModel):
    job_id: str
    stats: Dict[str, Any]
    files: FilePaths
    # Structured data so the Flutter app renders native charts/tables/worksheet
    # rather than the pipeline's PNG/PDF (the annotated_video stays a file artifact).
    series: Optional[MotionSeries] = None
    worksheet: Optional[Worksheet] = None


class JobListItem(BaseModel):
    job_id: str
    status: Optional[str] = None
    step: Optional[str] = None
    progress_pct: Optional[int] = None
    elapsed_s: Optional[int] = None
    object_name: Optional[str] = None
    created_at: Optional[float] = None  # unix epoch seconds (submission time)


class JobListResponse(BaseModel):
    jobs: list[JobListItem]


class DeleteResponse(BaseModel):
    deleted: bool