import subprocess
import json
import os

video = "IMG_2731.MOV"
# The point you selected: [963, 711]
target = [{"label": "pedal", "points": [[963, 711]], "neg_points": []}]
total_frames = 3676
start_offset = 600
chunk_size = 500

n_total = total_frames - start_offset
num_chunks = (n_total + chunk_size - 1) // chunk_size

chunks_files = []

for i in range(num_chunks):
    s_f = start_offset + i * chunk_size
    n_f = min(chunk_size, total_frames - s_f)
    if s_f >= total_frames: break
    
    out_file = f"chunk_manual_{i}.json"
    chunks_files.append(out_file)
    
    # For chunks after the first one, we use the LAST point of the previous chunk 
    # to re-initialize tracking if needed, or we just trust the hybrid worker 
    # (The hybrid worker re-runs the detection/point-prompt on the first frame of each chunk)
    
    cmd = [
        "./build/examples/sam3_api_worker_hybrid",
        "--model3", "./models/sam3-q4_0.ggml",
        "--model2", "./models/sam2.1_hiera_large_f16.ggml",
        "--video", video,
        "--targets", json.dumps(target),
        "--start-frame", str(s_f),
        "--n-frames", str(n_f),
        "--threads", "16"
    ]
    
    print(f"Processing Chunk {i+1}/{num_chunks}: Frames {s_f} to {s_f+n_f}...")
    with open(out_file, "w") as f:
        subprocess.run(cmd, stdout=f)
    
    # Update target points for next chunk based on last frame of current chunk to maintain continuity
    try:
        with open(out_file, "r") as f:
            data = json.load(f)
            traj = data["trajectories"]["pedal"]
            if traj:
                last_pt = traj[-1]
                target = [{"label": "pedal", "points": [[last_pt["cx"], last_pt["cy"]]], "neg_points": []}]
    except:
        print(f"Warning: Chunk {i} failed to provide continuity point. Using initial point.")

# Merge
print("Merging results...")
merged = {"status": "success", "trajectories": {"pedal": []}}
for out_file in chunks_files:
    if not os.path.exists(out_file): continue
    with open(out_file, "r") as f:
        try:
            data = json.load(f)
            merged["trajectories"]["pedal"].extend(data["trajectories"]["pedal"])
        except:
            continue

with open("pedal_manual_final.json", "w") as f:
    json.dump(merged, f)

# Visualize
print("Rendering visualization...")
subprocess.run([
    "python3", "visualize_results.py",
    video, "pedal_manual_final.json", "pedal_manual_final.mp4"
])

print("Done! Result saved to pedal_manual_final.mp4")
