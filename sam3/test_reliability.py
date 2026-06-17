import subprocess
import json
import time
import numpy as np
import os

def run_reliability_test(model_path, model_name, n_runs=10):
    video = "IMG_2731.MOV"
    targets = '["red phone"]'
    start_f = 1000
    n_f = 300 # 5 seconds to keep it reasonably fast
    
    results = []
    times = []
    
    print(f"--- Testing Reliability for {model_name} ({n_runs} runs) ---")
    
    for i in range(n_runs):
        start_t = time.time()
        cmd = [
            "./build/examples/sam3_api_worker_hybrid",
            "--model3", "./models/sam3-q4_0.ggml",
            "--model2", model_path,
            "--video", video,
            "--targets", targets,
            "--start-frame", str(start_f),
            "--n-frames", str(n_f),
            "--threads", "4"
        ]
        
        try:
            out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode()
            end_t = time.time()
            
            # Parse JSON
            start_idx = out.find('{')
            end_idx = out.rfind('}') + 1
            data = json.loads(out[start_idx:end_idx])
            
            traj = data['trajectories']['red phone']
            coords = np.array([[p['cx'], p['cy']] for p in traj])
            
            results.append(coords)
            times.append(end_t - start_t)
            print(f"Run {i+1}: {end_t - start_t:.2f}s")
        except Exception as e:
            print(f"Run {i+1} failed: {e}")
            
    # Analyze Determinism
    if len(results) > 1:
        # Check if all arrays are identical to the first one
        ref = results[0]
        max_diffs = []
        for i in range(1, len(results)):
            diff = np.abs(results[i] - ref).max()
            max_diffs.append(diff)
            
        avg_time = np.mean(times)
        std_time = np.std(times)
        max_coord_diff = max(max_diffs)
        
        print(f"\nResults for {model_name}:")
        print(f"  Avg Time: {avg_time:.2f}s (±{std_time:.2f}s)")
        print(f"  Max Coordinate Difference between runs: {max_coord_diff:.6f} pixels")
        if max_coord_diff == 0:
            print("  STATUS: PERFECTLY DETERMINISTIC")
        else:
            print(f"  STATUS: NON-DETERMINISTIC (Max variance: {max_coord_diff:.6f} px)")
    
    return {
        "model": model_name,
        "avg_time": np.mean(times),
        "max_diff": max(max_diffs) if len(max_diffs) > 0 else 0
    }

if __name__ == "__main__":
    tiny_res = run_reliability_test("./models/sam2.1_hiera_tiny_f16.ggml", "SAM 2.1 Tiny")
    print("\n" + "="*40 + "\n")
    large_res = run_reliability_test("./models/sam2.1_hiera_large_f16.ggml", "SAM 2.1 Large")
