import os
import uuid
import shutil
import time
import json
import subprocess
import asyncio
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
import uvicorn

app = FastAPI(title="SAM 3 CPP API")

# Semaphore to allow parallel processing (utilizing RTX 5090 VRAM)
WORKER_LOCK = asyncio.Semaphore(1)
UPLOAD_DIR = "/home/damar/sams2/api_data_sam3"
os.makedirs(UPLOAD_DIR, exist_ok=True)

WORKER_BIN = "/home/damar/sams2/sam3cpp/build/examples/sam3_api_worker_hybrid"

@app.post("/track")
async def track_video(
    file: UploadFile = File(None),
    targets: str = Form(...),
    video_id: str = Form(None),
    crop: str = Form(None),
):
    request_id = str(uuid.uuid4())
    request_dir = os.path.join(UPLOAD_DIR, request_id)
    os.makedirs(request_dir, exist_ok=True)
    
    # --- Resolve video source: new upload or cached ---
    if video_id:
        cached_video = os.path.join(UPLOAD_DIR, video_id, "input.mp4")
        if not os.path.exists(cached_video):
            raise HTTPException(status_code=404, detail=f"video_id '{video_id}' not found")
        video_path = cached_video
    elif file:
        video_path = os.path.join(request_dir, "input.mp4")
        with open(video_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    else:
        raise HTTPException(status_code=400, detail="Provide 'file' or 'video_id'")
    
    # --- Server-side crop (optional) ---
    crop_applied = None
    if crop:
        try:
            crop_p = json.loads(crop)
            cropped_path = os.path.join(request_dir, "cropped.mp4")
            crop_proc = subprocess.run([
                "ffmpeg", "-y", "-i", video_path,
                "-vf", f"crop={crop_p['w']}:{crop_p['h']}:{crop_p['x']}:{crop_p['y']}",
                "-c:v", "libx264", "-crf", "18", "-preset", "fast",
                cropped_path
            ], capture_output=True)
            if crop_proc.returncode != 0:
                raise HTTPException(status_code=500,
                    detail=f"ffmpeg crop failed: {crop_proc.stderr.decode()[:500]}")
            video_path = cropped_path
            crop_applied = crop_p
        except json.JSONDecodeError:
            raise HTTPException(status_code=422,
                detail='crop must be JSON: {"x":int,"y":int,"w":int,"h":int}')
    
    # Get video info for chunking
    try:
        probe_cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=nb_frames,r_frame_rate,duration,width,height:side_data",
            "-of", "json", video_path
        ]
        probe_out = subprocess.check_output(probe_cmd).decode()
        probe_data = json.loads(probe_out)
        stream = probe_data['streams'][0]
        
        # Get FPS
        fps_num, fps_den = map(int, stream['r_frame_rate'].split('/'))
        fps = fps_num / fps_den
        
        # Get frame count
        if 'nb_frames' in stream:
            nb_frames = int(stream['nb_frames'])
        else:
            duration = float(stream.get('duration', 0))
            nb_frames = int(duration * fps)
        if nb_frames <= 0: nb_frames = 1
        
        # Detect rotation and dimensions (for metadata)
        rotation = 0
        width = stream['width']
        height = stream['height']
        if 'side_data_list' in stream:
            for side_data in stream['side_data_list']:
                if 'rotation' in side_data:
                    rotation = int(side_data['rotation'])
                    break
    except Exception as e:
        print(f"[{request_id}] Failed to probe video: {e}", flush=True)
        nb_frames = 1
        fps = 30
        rotation = 0
        width, height = 1920, 1080

    num_chunks = 1
    chunk_size = (nb_frames + num_chunks - 1) // num_chunks
    
    tasks = []
    for i in range(num_chunks):
        start_f = i * chunk_size
        if start_f >= nb_frames: break
        n_f = min(chunk_size, nb_frames - start_f)
        
        worker_cmd = [
            WORKER_BIN,
            "--model3", "/home/damar/sams2/sam3cpp/models/sam3-q4_0.ggml",
            "--model2", "/home/damar/sams2/sam3cpp/models/sam2.1_hiera_large_f16.ggml",
            "--video", video_path,
            "--targets", targets,
            "--start-frame", str(start_f),
            "--n-frames", str(n_f),
            "--threads", "4"
        ]
        
        async def run_worker(cmd, cid, sf, nf):
            async with WORKER_LOCK:
                print(f"[{request_id}] Starting Worker Chunk {cid} ({sf}-{sf+nf})...", flush=True)
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                return stdout, stderr, process.returncode

        tasks.append(run_worker(worker_cmd, i, start_f, n_f))

    try:
        results_list = await asyncio.gather(*tasks)
        merged_trajectories = {}
        for stdout, stderr, returncode in results_list:
            if returncode != 0:
                print(f"[{request_id}] Chunk failed: {stderr.decode()}", flush=True)
                continue
            try:
                output = stdout.decode()
                start = output.find('{')
                end = output.rfind('}') + 1
                if start == -1: continue
                data = json.loads(output[start:end])
                for label, traj in data.get('trajectories', {}).items():
                    if label not in merged_trajectories:
                        merged_trajectories[label] = []
                    # Just append the RAW points from the worker
                    merged_trajectories[label].extend(traj)
            except Exception as e:
                print(f"[{request_id}] Error merging chunk: {e}", flush=True)

        for label in merged_trajectories:
            merged_trajectories[label].sort(key=lambda x: x['frame'])

        response = {
            "status": "success",
            "request_id": request_id,
            "video_id": video_id or request_id,
            "video_info": {
                "width": width,
                "height": height,
                "rotation": rotation,
                "nb_frames": nb_frames,
                "fps": fps
            },
            "trajectories": merged_trajectories
        }
        if crop_applied:
            response["crop_applied"] = crop_applied
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # shutil.rmtree(request_dir)
        pass

@app.post("/segment")
async def segment_frame(
    image: UploadFile = File(None),
    file: UploadFile = File(None),
    targets: str = Form(...),
    frame: int = Form(0),
):
    """Single-frame, text-prompted detection. Reuses the tracking worker on exactly
    one frame so the app can verify/sharpen a proposed object box before committing
    to a full /track job. Send `image` (a frame) or `file` (a video + `frame` index)."""
    try:
        target_list = json.loads(targets)
        if not isinstance(target_list, list) or not target_list:
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=422, detail='targets must be a non-empty JSON array')

    request_id = str(uuid.uuid4())
    request_dir = os.path.join(UPLOAD_DIR, request_id)
    os.makedirs(request_dir, exist_ok=True)
    start_frame = max(0, int(frame))

    # --- Resolve to a video the worker can read ---
    if image is not None:
        img_path = os.path.join(request_dir, "frame.jpg")
        with open(img_path, "wb") as buf:
            shutil.copyfileobj(image.file, buf)
        video_path = os.path.join(request_dir, "frame.mp4")
        enc = subprocess.run([
            "ffmpeg", "-y", "-loop", "1", "-i", img_path, "-frames:v", "1",
            "-pix_fmt", "yuv420p", "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
            video_path,
        ], capture_output=True)
        if enc.returncode != 0:
            raise HTTPException(status_code=400,
                detail=f"could not wrap image as frame: {enc.stderr.decode()[:300]}")
        start_frame = 0
    elif file is not None:
        video_path = os.path.join(request_dir, "input.mp4")
        with open(video_path, "wb") as buf:
            shutil.copyfileobj(file.file, buf)
    else:
        raise HTTPException(status_code=400, detail="Provide 'image' or 'file'")

    # --- Frame dimensions (authoritative for the returned coordinates) ---
    try:
        probe = subprocess.check_output([
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height", "-of", "json", video_path,
        ]).decode()
        st = json.loads(probe)["streams"][0]
        frame_w, frame_h = int(st["width"]), int(st["height"])
    except Exception:
        frame_w, frame_h = 0, 0

    worker_cmd = [
        WORKER_BIN,
        "--model3", "/home/damar/sams2/sam3cpp/models/sam3-q4_0.ggml",
        "--model2", "/home/damar/sams2/sam3cpp/models/sam2.1_hiera_large_f16.ggml",
        "--video", video_path,
        "--targets", json.dumps(target_list),
        "--start-frame", str(start_frame),
        "--n-frames", "1",
        "--threads", "4",
    ]

    async with WORKER_LOCK:
        proc = await asyncio.create_subprocess_exec(
            *worker_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise HTTPException(status_code=500,
            detail=f"worker failed: {stderr.decode()[-400:]}")

    out = stdout.decode()
    s, e = out.find("{"), out.rfind("}") + 1
    if s == -1:
        raise HTTPException(status_code=500, detail="worker produced no JSON")
    try:
        data = json.loads(out[s:e])
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="worker JSON parse failed")

    objects = {}
    for label, dets in data.get("trajectories", {}).items():
        det = dets[0] if dets else None
        objects[label] = None if det is None else {
            "cx": det.get("cx"),
            "cy": det.get("cy"),
            "bbox": det.get("bbox"),   # [x0, y0, x1, y1]
            "obox": det.get("obox"),   # oriented box, 4 corners
        }

    return {
        "status": "success",
        "frame_w": frame_w,
        "frame_h": frame_h,
        "objects": objects,
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/reset")
async def reset():
    """Recycle the server to clear accumulated GPU/model state (coverage degrades
    over the process lifetime). Exits the process; the supervisor (run_sam3.sh)
    relaunches a fresh one. Callers should wait for /health to return, then retry."""
    import threading

    def _bye():
        time.sleep(0.4)
        os._exit(0)

    threading.Thread(target=_bye, daemon=True).start()
    return {"status": "restarting"}


if __name__ == "__main__":
    uvicorn.run(app, host="10.0.0.1", port=8086)
