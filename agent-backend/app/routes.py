import time
import uuid
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from typing import Optional

from .schemas import (
    AnalyzeResponse,
    JobStatusResponse,
    JobResultResponse,
    JobListResponse,
    DeleteResponse,
    FilePaths,
    MotionSeries,
    Worksheet,
    MaterialLevel,
    SceneSuggestion,
    VerifyResponse,
    VerifiedObject,
    FeedbackRequest,
    FeedbackResponse,
)
from .auth import verify_api_key
from . import workspace as ws
from . import job_store

from .limiter import limiter, RATE_LIMIT

router = APIRouter()

MAX_VIDEO_SIZE = 500 * 1024 * 1024
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/x-msvideo", "video/x-matroska"}
MAX_IMAGE_SIZE = 25 * 1024 * 1024


@router.post("/analyze", response_model=AnalyzeResponse)
@limiter.limit(RATE_LIMIT)
async def analyze(
    request: Request,
    video: UploadFile = File(...),
    sidecar: Optional[str] = Form(None),
    template: Optional[str] = Form(None),
    _: None = Depends(verify_api_key),
):
    if video.content_type and video.content_type not in ALLOWED_VIDEO_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported video type: {video.content_type}")

    job_id = str(uuid.uuid4())

    try:
        workspace = ws.create_workspace(job_id, template)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    video_bytes = await video.read()
    if len(video_bytes) > MAX_VIDEO_SIZE:
        raise HTTPException(status_code=400, detail="Video exceeds 500MB limit")
    ws.drop_video(workspace, video_bytes)

    # Seed the frozen kinematics pipeline so the agent runs vetted, deterministic
    # math (`python -m analysis.run`) instead of re-authoring it each job.
    ws.seed_pipeline(workspace)

    object_name = None
    if sidecar:
        import json
        try:
            sidecar_data = json.loads(sidecar)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid sidecar JSON")
        if not isinstance(sidecar_data, dict):
            raise HTTPException(status_code=400, detail="Sidecar must be a JSON object")
        ws.drop_sidecar(workspace, sidecar_data)
        # Human label of the tracked object, for the history list (first visual cue).
        cues = (sidecar_data.get("tracked_object") or {}).get("visual_cues")
        if isinstance(cues, list) and cues and isinstance(cues[0], str):
            object_name = cues[0].strip() or None

    # Record submission so the job shows up in history immediately (queued, before
    # the worker picks it up) with its created time and object label. The worker's
    # later set_state(status="running", ...) merges in and preserves these.
    job_store.set_state(
        job_id,
        status="queued",
        progress_pct=0,
        created_at=time.time(),
        object_name=object_name,
    )

    from worker.tasks import run_pi_analysis
    run_pi_analysis.delay(job_id)

    return AnalyzeResponse(job_id=job_id)


@router.post("/suggest-scene", response_model=SceneSuggestion)
@limiter.limit("20/minute")
async def suggest_scene(
    request: Request,
    image: Optional[UploadFile] = File(None),
    video: Optional[UploadFile] = File(None),
    _: None = Depends(verify_api_key),
):
    """Advisory: propose the moving object, reference, and rotation centre from one
    frame, to pre-fill the annotation form. Send either `image` (a frame) or `video`."""
    from . import scene_suggest

    if image is None and video is None:
        raise HTTPException(status_code=400, detail="Provide an image or a video")

    try:
        if image is not None:
            data = await image.read()
            if len(data) > MAX_IMAGE_SIZE:
                raise HTTPException(status_code=400, detail="Image exceeds 25MB limit")
            frame, w, h = await run_in_threadpool(scene_suggest.frame_from_image, data)
        else:
            data = await video.read()
            if len(data) > MAX_VIDEO_SIZE:
                raise HTTPException(status_code=400, detail="Video exceeds 500MB limit")
            frame, w, h = await run_in_threadpool(scene_suggest.frame_from_video, data)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        # The VLM call blocks for tens of seconds; run it off the event loop so
        # concurrent requests don't serialize behind it.
        result = await run_in_threadpool(scene_suggest.suggest, frame, w, h)
    except Exception as e:
        # The VLM is best-effort; never hard-fail the annotation flow.
        raise HTTPException(status_code=502, detail=f"Scene suggestion failed: {e}")

    return SceneSuggestion(**result)


@router.post("/verify-objects", response_model=VerifyResponse)
@limiter.limit("20/minute")
async def verify_objects(
    request: Request,
    image: UploadFile = File(...),
    targets: str = Form(...),
    _: None = Depends(verify_api_key),
):
    """Ground the given labels in one frame via SAM3 (the same detector the full job
    uses) and return tight boxes. Lets the app confirm a setup before a /analyze job."""
    import json
    from . import sam_client

    try:
        target_list = json.loads(targets)
        if not isinstance(target_list, list) or not target_list:
            raise ValueError
        target_list = [str(t) for t in target_list if str(t).strip()]
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="targets must be a non-empty JSON array")
    if not target_list:
        raise HTTPException(status_code=400, detail="No usable labels provided")

    data = await image.read()
    if len(data) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=400, detail="Image exceeds 25MB limit")

    try:
        raw = await run_in_threadpool(sam_client.segment, data, target_list)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"SAM3 segmentation failed: {e}")

    objects = {}
    for label, det in (raw.get("objects") or {}).items():
        if not det:
            objects[label] = None
            continue
        objects[label] = VerifiedObject(
            cx=det.get("cx"),
            cy=det.get("cy"),
            bbox=sam_client.to_xywh(det.get("bbox")),
        )

    return VerifyResponse(
        frame_w=int(raw.get("frame_w") or 0),
        frame_h=int(raw.get("frame_h") or 0),
        objects=objects,
    )


@router.get("/status/{job_id}", response_model=JobStatusResponse)
@limiter.limit("30/minute")
async def get_status(request: Request, job_id: str, _: None = Depends(verify_api_key)):
    state = job_store.get_state(job_id)
    if not state:
        raise HTTPException(status_code=404, detail="Job not found")

    elapsed_s = None
    if "started_at" in state:
        elapsed_s = int(time.time() - state["started_at"])

    return JobStatusResponse(
        job_id=job_id,
        status=state.get("status", "unknown"),
        step=state.get("step"),
        progress_pct=state.get("progress_pct"),
        message=state.get("message"),
        elapsed_s=elapsed_s,
        # Interactive agentic feed (written by the worker via build_progress).
        phase=state.get("phase"),
        current_action=state.get("current_action"),
        thinking=state.get("thinking"),
        stages=state.get("stages"),
        activities=state.get("activities"),
    )


@router.get("/result/{job_id}", response_model=JobResultResponse)
@limiter.limit("30/minute")
async def get_result(request: Request, job_id: str, _: None = Depends(verify_api_key)):
    state = job_store.get_state(job_id)
    if not state or state.get("status") != "done":
        raise HTTPException(status_code=404, detail="Job not done")

    result = job_store.get_result(job_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    # Structured data for native rendering (charts/tables/worksheet) — read from
    # the workspace files the pipeline already produced. Best-effort: if a file is
    # missing the field is just omitted (the app falls back to the artifact).
    from . import result_data
    series = result_data.load_series(job_id)
    worksheet = result_data.load_worksheet(job_id)
    materials = result_data.load_materials(job_id)

    return JobResultResponse(
        job_id=job_id,
        stats=result["stats"],
        files=FilePaths(**result["files"]),
        series=MotionSeries(**series) if series else None,
        worksheet=Worksheet(**worksheet) if worksheet else None,
        materials={t: MaterialLevel(**m) for t, m in materials.items()} if materials else None,
    )


@router.post("/feedback", response_model=FeedbackResponse)
@limiter.limit("30/minute")
async def submit_feedback(
    request: Request,
    body: FeedbackRequest,
    _: None = Depends(verify_api_key),
):
    """Store a HITL feedback event (setup correction or result feedback)."""
    from . import feedback_store

    if body.type not in ("setup_correction", "result_feedback"):
        raise HTTPException(status_code=400, detail="unknown feedback type")
    fid = feedback_store.store(body.model_dump())
    return FeedbackResponse(stored=True, id=fid)


@router.get("/jobs", response_model=JobListResponse)
@limiter.limit("30/minute")
async def list_jobs(request: Request, _: None = Depends(verify_api_key)):
    return JobListResponse(jobs=job_store.list_jobs())


@router.delete("/job/{job_id}", response_model=DeleteResponse)
@limiter.limit("10/minute")
async def delete_job(request: Request, job_id: str, _: None = Depends(verify_api_key)):
    ws.delete_workspace(job_id)
    job_store.delete_job(job_id)
    return DeleteResponse(deleted=True)