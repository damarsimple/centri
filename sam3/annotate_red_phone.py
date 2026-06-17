import requests
import json
import subprocess
import os

def main():
    video_path = "/home/damar/sams2/sam3cpp/IMG_3075.MOV"
    api_url = "http://localhost:8086/track"
    targets = json.dumps(["red phone"])
    
    print(f"Calling API to track 'red phone' in {video_path}...")
    
    with open(video_path, 'rb') as f:
        files = {'file': (os.path.basename(video_path), f, 'video/quicktime')}
        data = {'targets': targets}
        response = requests.post(api_url, files=files, data=data)
    
    if response.status_code != 200:
        print(f"Error calling API: {response.status_code}")
        print(response.text)
        return
    
    result = response.json()
    json_path = "/home/damar/sams2/sam3cpp/red_phone_track.json"
    with open(json_path, 'w') as f:
        json.dump(result, f)
    
    print(f"Tracking completed. Results saved to {json_path}")
    
    output_video = "/home/damar/sams2/sam3cpp/IMG_3075_annotated.mp4"
    print(f"Running visualization to generate {output_video}...")
    
    cmd = [
        "python3", "visualize_results.py",
        video_path,
        json_path,
        output_video
    ]
    
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print("Visualization failed:")
        print(proc.stderr)
    else:
        print(f"Success! Annotated video saved to {output_video}")

if __name__ == "__main__":
    main()
