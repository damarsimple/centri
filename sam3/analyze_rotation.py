import pandas as pd
import numpy as np
import json
import matplotlib.pyplot as plt

def analyze():
    # 1. Load CSV
    df = pd.read_csv("rotation_data_2026-04-26T11-54-02-612Z.csv")
    df['t_sec'] = (df['timestamp'] - df['timestamp'].iloc[0]) / 1000.0
    
    # Check gyro values
    print("Gyro stats:")
    print(df[['gyro_alpha', 'gyro_beta', 'gyro_gamma']].describe())
    
    # 2. Load Video Data
    with open("results_2731_large.json", "r") as f:
        video_data = json.load(f)
    
    traj = video_data['trajectories']['red phone']
    v_df = pd.DataFrame(traj)
    
    # Video stats: 60 fps
    fps = 60000/1001.0
    v_df['t_sec'] = v_df['frame'] / fps
    
    # Find center of rotation (Turntable center)
    # The phone moves in a circle. We can fit a circle to (cx, cy).
    X = v_df['cx'].values
    Y = v_df['cy'].values
    
    # Simple circle fit (least squares)
    # (x-a)^2 + (y-b)^2 = R^2  => x^2 - 2ax + a^2 + y^2 - 2by + b^2 = R^2
    # x^2 + y^2 = 2ax + 2by + C where C = R^2 - a^2 - b^2
    A = np.c_[X, Y, np.ones(len(X))]
    B = X**2 + Y**2
    C, resid, rank, s = np.linalg.lstsq(A, B, rcond=None)
    a, b = C[0]/2, C[1]/2
    print(f"Turntable center estimated at: ({a:.2f}, {b:.2f})")
    
    # Calculate angle
    v_df['angle'] = np.arctan2(v_df['cy'] - b, v_df['cx'] - a)
    # Unwrapping to avoid jump from pi to -pi
    v_df['angle_unwrapped'] = np.unwrap(v_df['angle'])
    
    # Calculate angular velocity (rad/s)
    v_df['omega_rad_s'] = np.gradient(v_df['angle_unwrapped'], v_df['t_sec'])
    
    # Plot both
    plt.figure(figsize=(12, 6))
    plt.subplot(2, 1, 1)
    plt.plot(df['t_sec'], df['gyro_alpha'], label='Alpha')
    plt.plot(df['t_sec'], df['gyro_beta'], label='Beta')
    plt.plot(df['t_sec'], df['gyro_gamma'], label='Gamma')
    plt.title("Sensor Gyro Data")
    plt.legend()
    
    plt.subplot(2, 1, 2)
    plt.plot(v_df['t_sec'], v_df['omega_rad_s'], label='Video Omega')
    plt.title("Video Angular Velocity")
    plt.legend()
    plt.tight_layout()
    plt.savefig("angular_velocity_raw.png")
    print("Saved angular_velocity_raw.png")

if __name__ == "__main__":
    analyze()
