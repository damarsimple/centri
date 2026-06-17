import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os

def plot_velocity(json_path, output_plot):
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    if data['status'] != 'success':
        print("Error: JSON status is not success")
        return

    fps = data['video_info']['fps']
    trajectories = data['trajectories']
    
    if 'red phone' not in trajectories:
        print("Error: 'red phone' not found in trajectories")
        return
    
    traj = trajectories['red phone']
    df = pd.DataFrame(traj)
    df['t_sec'] = df['frame'] / fps
    
    # Circle fit to find rotation center
    X = df['cx'].values
    Y = df['cy'].values
    
    # Formulate the least squares problem: (x-a)^2 + (y-b)^2 = R^2
    # x^2 - 2ax + a^2 + y^2 - 2by + b^2 = R^2
    # 2ax + 2by + (R^2 - a^2 - b^2) = x^2 + y^2
    A = np.c_[X, Y, np.ones(len(X))]
    B = X**2 + Y**2
    C, resid, rank, s = np.linalg.lstsq(A, B, rcond=None)
    
    xc, yc = C[0]/2, C[1]/2
    print(f"Estimated rotation center: ({xc:.2f}, {yc:.2f})")
    
    # Calculate angles
    df['angle'] = np.arctan2(df['cy'] - yc, df['cx'] - xc)
    df['angle_unwrapped'] = np.unwrap(df['angle'])
    
    # Calculate angular velocity (omega = d_theta / d_t)
    # Using a central difference (gradient)
    df['omega_rad_s'] = np.gradient(df['angle_unwrapped'], df['t_sec'])
    
    # Smoothing for better visualization
    df['omega_smooth'] = df['omega_rad_s'].rolling(window=5, center=True).mean()
    
    # Plotting
    plt.figure(figsize=(12, 8))
    
    # Top plot: Trajectory
    plt.subplot(2, 1, 1)
    plt.scatter(X, Y, c=df['frame'], cmap='viridis', s=10, alpha=0.5)
    plt.plot(xc, yc, 'rx', markersize=15, label='Rotation Center')
    plt.axis('equal')
    plt.title("Red Phone Trajectory (X-Y Plane)")
    plt.xlabel("X (pixels)")
    plt.ylabel("Y (pixels)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # Bottom plot: Angular Velocity
    plt.subplot(2, 1, 2)
    plt.plot(df['t_sec'], df['omega_rad_s'], alpha=0.3, label='Raw Omega', color='gray')
    plt.plot(df['t_sec'], df['omega_smooth'], label='Smoothed Omega (Window=5)', color='red', linewidth=2)
    plt.title("Angular Velocity over Time")
    plt.xlabel("Time (seconds)")
    plt.ylabel("Angular Velocity (rad/s)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_plot, dpi=150)
    print(f"Plot saved to {output_plot}")

if __name__ == "__main__":
    json_path = "/home/damar/sams2/sam3cpp/red_phone_track.json"
    output_plot = "/home/damar/sams2/sam3cpp/red_phone_velocity.png"
    plot_velocity(json_path, output_plot)
