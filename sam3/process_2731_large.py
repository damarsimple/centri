import subprocess
import json
import os
import time

video = "IMG_2731.MOV"
targets = '["red phone"]'
total_frames = 3676
start_offset = 600
n_total = total_frames - start_offset
num_chunks = 3
chunk_size = (n_total + num_chunks - 1) // num_chunks

procs = []
for i in range(num_chunks):
    s_f = start_offset + i * chunk_size
    n_f = min(chunk_size, total_frames - s_f)
    if s_f >= total_frames: break
    
    out_file = f"chunk_2731_large_{i}.json"
    cmd = [
        "./build/examples/sam3_api_worker_hybrid",
        "--model3", "./models/sam3-q4_0.ggml",
        "--model2", "./models/sam2.1_hiera_large_f16.ggml", # Using Large model
        "--video", video,
        "--targets", targets,
        "--start-frame", str(s_f),
        "--n-frames", str(n_f),
        "--threads", "4"
    ]
    print(f"Starting Large chunk {i}: {s_f} to {s_f+n_f}")
    f = open(out_file, "w")
    p = subprocess.Popen(cmd, stdout=f, stderr=subprocess.DEVNULL)
    procs.append((p, f, out_file))

for p, f, _ in procs:
    p.wait()
    f.close()

# Merge
merged = {"status": "success", "trajectories": {}}
for _, _, out_file in procs:
    with open(out_file, "r") as f:
        text = f.read()
        start = text.find('{')
        end = text.rfind('}') + 1
        if start == -1: continue
        data = json.loads(text[start:end])
        for label, traj in data.get("trajectories", {}).items():
            if label not in merged["trajectories"]:
                merged["trajectories"][label] = []
            merged["trajectories"][label].extend(traj)

for label in merged["trajectories"]:
    merged["trajectories"][label].sort(key=lambda x: x["frame"])

with open("results_2731_large.json", "w") as f:
    json.dump(merged, f)

# Visualize
subprocess.run([
    "python3", "visualize_results.py",
    "--video", video,
    "--json", "results_2731_large.json",
    "--output", "output_2731_large_trail.mp4"
])
print("Done! output_2731_large_trail.mp4")
