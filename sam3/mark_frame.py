import cv2
import numpy as np

img = cv2.imread('frame_600.jpg')

# Targets and their OBOX coordinates
targets = [
    {
        "label": "red smartphone",
        "obox": [[792.907, 790.8], [687.503, 854.156], [656.4, 802.409], [761.803, 739.054]],
        "color": (0, 0, 255) # Red
    },
    {
        "label": "rear bicycle tire",
        "obox": [[976.743, 631.163], [724.407, 1030.84], [326.456, 779.594], [578.793, 379.917]],
        "color": (0, 255, 0) # Green
    }
]

for t in targets:
    pts = np.array(t['obox'], np.int32)
    cv2.polylines(img, [pts], True, t['color'], 3)
    # Draw center
    cx = int(np.mean(pts[:, 0]))
    cy = int(np.mean(pts[:, 1]))
    cv2.circle(img, (cx, cy), 5, t['color'], -1)
    # Add label
    cv2.putText(img, t['label'], (pts[0][0], pts[0][1]-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, t['color'], 2)

cv2.imwrite('marked_frame_600.jpg', img)
