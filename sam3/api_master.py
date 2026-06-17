import os
import uuid
import shutil
import time
import json
import subprocess
import asyncio
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
import uvicorn
import cv2

app = FastAPI(title="SAM 2.1 Master API")

# Global lock to prevent GPU oversubscription
WORKER_LOCK = asyncio.Lock()
UPLOAD_DIR = "/home/damar/sams2/api_data"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def extract_frames(video_path, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    
    # Get FPS and count using ffprobe
    probe_cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=avg_frame_rate,nb_frames",
        "-of", "default=noprint_wrappers=1:nokey=1", video_path
    ]
    try:
        probe_out = subprocess.check_output(probe_cmd).decode().split()
        fps_eval = probe_out[0].split('/')
        fps = float(fps_eval[0]) / float(fps_eval[1]) if len(fps_eval) > 1 else float(fps_eval[0])
        count = int(probe_out[1])
    except:
        # Fallback if ffprobe fails
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()

    # Fast extraction with ffmpeg
    extract_cmd = [
        "ffmpeg", "-i", video_path,
        "-q:v", "2", # High quality JPEG
        "-start_number", "0",
        os.path.join(output_dir, "%05d.jpg")
    ]
    subprocess.run(extract_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    return count, fps

@app.post("/track")
async def track_video(
    file: UploadFile = File(...),
    targets: str = Form(...) # JSON string
):
    request_id = str(uuid.uuid4())
    request_dir = os.path.join(UPLOAD_DIR, request_id)
    os.makedirs(request_dir, exist_ok=True)
    
    video_path = os.path.join(request_dir, "input.mp4")
    frames_dir = os.path.join(request_dir, "frames")
    results_json = os.path.join(request_dir, "results.json")
    
    # Save uploaded file
    with open(video_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Pre-process: Extract frames (done in master for simplicity)
    print(f"[{request_id}] Extracting frames...", flush=True)
    frame_count, fps = extract_frames(video_path, frames_dir)
    
    # Wait for GPU slot
    async with WORKER_LOCK:
        print(f"[{request_id}] Starting Worker Process...", flush=True)
        worker_cmd = [
            "conda", "run", "-n", "sam2", "--no-capture-output",
            "python", "-u", "/home/damar/sams2/worker_segmenter.py",
            "--video_dir", frames_dir,
            "--targets", targets,
            "--output", results_json
        ]
        
        try:
            # Run worker in a separate process with real-time log streaming
            process = await asyncio.create_subprocess_exec(
                *worker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Helper to read stream and print
            async def log_stream(stream, prefix):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    print(f"[{request_id}][{prefix}] {line.decode().strip()}", flush=True)

            # Stream stdout and stderr concurrently
            await asyncio.gather(
                log_stream(process.stdout, "WORKER"),
                log_stream(process.stderr, "ERROR")
            )

            returncode = await process.wait()
            
            if returncode != 0:
                raise HTTPException(status_code=500, detail=f"Worker process failed with code {returncode}")
            
            # Read results
            if not os.path.exists(results_json):
                raise HTTPException(status_code=500, detail="Worker finished but no results found.")
            
            with open(results_json, 'r') as f:
                data = json.load(f)
            
            # Add master metadata
            data["request_id"] = request_id
            data["fps"] = fps
            data["frame_count"] = frame_count
            
            return data
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            # Keep for debug or cleanup
            # shutil.rmtree(request_dir)
            pass

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8085)
