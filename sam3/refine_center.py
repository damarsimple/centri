import pandas as pd
import numpy as np
import json
import cv2

def re_estimate():
    with open("results_2731_large.json", "r") as f:
        video_data = json.load(f)
    
    traj = video_data['trajectories']['red phone']
    v_df = pd.DataFrame(traj)
    
    # Filter out outliers (the noisy cluster on the right)
    main_cluster = v_df[v_df['cx'] < 900].copy()
    
    X, Y = main_cluster['cx'].values, main_cluster['cy'].values
    A = np.c_[X, Y, np.ones(len(X))]
    B = X**2 + Y**2
    C, _, _, _ = np.linalg.lstsq(A, B, rcond=None)
    a, b = C[0]/2, C[1]/2
    
    print(f"Refined turntable center: ({a:.2f}, {b:.2f})")
    
    # Draw on image
    img = cv2.imread('sample_2731_f600.jpg')
    cv2.circle(img, (int(a), int(b)), 10, (0, 0, 255), -1)
    cv2.drawMarker(img, (int(a), int(b)), (0, 255, 0), cv2.MARKER_CROSS, 40, 3)
    cv2.putText(img, f'Refined Center: ({int(a)}, {int(b)})', (int(a)+20, int(b)), 
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    cv2.imwrite('turntable_center_refined.jpg', img)

if __name__ == "__main__":
    re_estimate()
