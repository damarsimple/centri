import subprocess
import json
import os

video = "IMG_2731.MOV"
# Initial points from user
pos_pts = [[959, 708]]
neg_pts = [[975, 945]]

total_frames = 3676
start_offset = 600
chunk_size = 500
overlap = 100

n_total = total_frames - start_offset
# We use overlapping chunks
chunks_files = []

current_start = start_offset
chunk_idx = 0

while current_start < total_frames:
    n_f = min(chunk_size, total_frames - current_start)
    out_file = f"chunk_guided_{chunk_idx}.json"
    chunks_files.append((out_file, current_start, n_f))
    
    target = [{"label": "pedal", "points": pos_pts, "neg_points": neg_pts}]
    
    cmd = [
        "./build/examples/sam3_api_worker_hybrid",
        "--model3", "./models/sam3-q4_0.ggml",
        "--model2", "./models/sam2.1_hiera_large_f16.ggml",
        "--video", video,
        "--targets", json.dumps(target),
        "--start-frame", str(current_start),
        "--n-frames", str(n_f),
        "--threads", "16"
    ]
    
    print(f"Processing Chunk {chunk_idx}: Frames {current_start} to {current_start+n_f}...")
    with open(out_file, "w") as f:
        subprocess.run(cmd, stdout=f)
    
    # Update pos_pts for the next chunk from the overlap region
    # We look for a point near the end of the current chunk, but before the overlap ends
    try:
        with open(out_file, "r") as f:
            data = json.load(f)
            traj = data["trajectories"]["pedal"]
            if len(traj) > overlap:
                # Pick a point at the end of the chunk to start the next one
                # Actually, next start is current_start + chunk_size - overlap
                # So we need the point at that frame.
                target_frame = current_start + chunk_size - overlap
                # Find the frame in trajectory
                found = False
                for p in reversed(traj):
                    if p["frame"] <= target_frame:
                        pos_pts = [[p["cx"], p["cy"]]]
                        found = True
                        break
                if not found and traj:
                    pos_pts = [[traj[-1]["cx"], traj[-1]["cy"]]]
    except Exception as e:
        print(f"Warning: Failed to extract overlap point from chunk {chunk_idx}: {e}")

    current_start += (chunk_size - overlap)
    chunk_idx += 1
    if n_f < chunk_size: break # Reached end

# Merge with overlap handling (keep the first occurrence of a frame)
print("Merging results...")
merged_traj = []
seen_frames = set()

for out_file, _, _ in chunks_files:
    if not os.path.exists(out_file): continue
    with open(out_file, "r") as f:
        try:
            data = json.load(f)
            for p in data["trajectories"]["pedal"]:
                if p["frame"] not in seen_frames:
                    merged_traj.append(p)
                    seen_frames.add(p["frame"])
        except:
            continue

merged_traj.sort(key=lambda x: x["frame"])
result = {"status": "success", "trajectories": {"pedal": merged_traj}}

with open("pedal_guided_final.json", "w") as f:
    json.dump(result, f)

# Visualize
print("Rendering visualization...")
subprocess.run([
    "python3", "visualize_results.py",
    video, "pedal_guided_final.json", "pedal_guided_final.mp4"
])

print("Done! Result saved to pedal_guided_final.mp4")
