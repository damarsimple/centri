import time
import subprocess
import os

def run_test(num_workers, video_path, targets):
    # Get total frames
    probe_cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=nb_frames", "-of", "csv=p=0", video_path]
    probe_out = subprocess.check_output(probe_cmd).decode().strip()
    nb_frames = int(probe_out.replace(',', ''))
    
    chunk_size = (nb_frames + num_workers - 1) // num_workers
    
    start_time = time.time()
    processes = []
    
    print(f"Starting test with {num_workers} workers...")
    for i in range(num_workers):
        start_f = i * chunk_size
        n_f = min(chunk_size, nb_frames - start_f)
        if start_f >= nb_frames: break
        
        cmd = [
            "./build/examples/sam3_api_worker_hybrid",
            "--model3", "./models/sam3-q4_0.ggml",
            "--model2", "./models/sam2.1_hiera_tiny_f16.ggml",
            "--video", video_path,
            "--targets", targets,
            "--start-frame", str(start_f),
            "--n-frames", str(n_f),
            "--threads", "4"
        ]
        p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        processes.append(p)
    
    for p in processes:
        p.wait()
    
    end_time = time.time()
    total_time = end_time - start_time
    fps = nb_frames / total_time
    return total_time, fps

if __name__ == "__main__":
    video = "IMG_2539.MOV"
    targets = '["phone"]'
    
    t3, fps3 = run_test(3, video, targets)
    print(f"3 Workers: {t3:.2f}s ({fps3:.2f} FPS)")
    
    time.sleep(2) # Cooldown
    
    t5, fps5 = run_test(5, video, targets)
    print(f"5 Workers: {t5:.2f}s ({fps5:.2f} FPS)")
    
    print("\nSummary:")
    if t5 < t3:
        speedup = (t3 / t5 - 1) * 100
        print(f"5 workers is {speedup:.1f}% faster than 3 workers.")
    else:
        slowdown = (t5 / t3 - 1) * 100
        print(f"5 workers is {slowdown:.1f}% slower than 3 workers (likely due to overhead).")
