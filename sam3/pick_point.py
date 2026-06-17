import cv2
import json
import os

video_path = 'IMG_2731.MOV'
frame_idx = 600
output_image = f'frame_{frame_idx}.jpg'
output_json = 'pedal_points_v2.json'

if not os.path.exists(output_image):
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ret, frame = cap.read()
    if ret:
        cv2.imwrite(output_image, frame)
    cap.release()

img = cv2.imread(output_image)
overlay = img.copy()

points = {"pos": [], "neg": []}

def on_click(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        points["pos"].append([x, y])
        cv2.circle(overlay, (x, y), 8, (0, 255, 0), -1)
    elif event == cv2.EVENT_RBUTTONDOWN:
        points["neg"].append([x, y])
        cv2.circle(overlay, (x, y), 8, (0, 0, 255), -1)
    
    cv2.imshow('Left=Pedal, Right=Seat (ESC to save)', overlay)

cv2.namedWindow('Left=Pedal, Right=Seat (ESC to save)')
cv2.setMouseCallback('Left=Pedal, Right=Seat (ESC to save)', on_click)
cv2.imshow('Left=Pedal, Right=Seat (ESC to save)', overlay)

print("Instructions:")
print("- LEFT CLICK: Center of the Pedal (Green)")
print("- RIGHT CLICK: The Seat or Frame (Red)")
print("- Press ESC when done.")

cv2.waitKey(0)
cv2.destroyAllWindows()

if points["pos"]:
    with open(output_json, 'w') as f:
        json.dump(points, f, indent=2)
    print(f"Saved to {output_json}")
else:
    print("No points selected.")
