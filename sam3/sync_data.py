import pandas as pd
import numpy as np
import json
import matplotlib.pyplot as plt
from scipy.signal import correlate

def analyze():
    # 1. Load Sensor Data
    df = pd.read_csv("rotation_data_2026-04-26T11-54-02-612Z.csv")
    df['t_sec'] = (df['timestamp'] - df['timestamp'].iloc[0]) / 1000.0
    
    # Assume gyro_gamma is the primary rotation axis for the turntable
    # or calculate magnitude
    df['gyro_mag'] = np.sqrt(df['gyro_alpha']**2 + df['gyro_beta']**2 + df['gyro_gamma']**2)
    
    # 2. Load Video Data
    with open("results_2731_large.json", "r") as f:
        video_data = json.load(f)
    
    traj = video_data['trajectories']['red phone']
    v_df = pd.DataFrame(traj)
    fps = 60000/1001.0
    v_df['t_sec'] = v_df['frame'] / fps
    
    # Estimate center of rotation
    X, Y = v_df['cx'].values, v_df['cy'].values
    A = np.c_[X, Y, np.ones(len(X))]
    B = X**2 + Y**2
    C, _, _, _ = np.linalg.lstsq(A, B, rcond=None)
    a, b = C[0]/2, C[1]/2
    
    v_df['angle'] = np.unwrap(np.arctan2(v_df['cy'] - b, v_df['cx'] - a))
    v_df['omega'] = np.abs(np.gradient(v_df['angle'], v_df['t_sec'])) # rad/s
    
    # Convert sensor to rad/s if it was deg/s (720 max suggests deg/s)
    # 720 deg/s = 12.56 rad/s.
    # Video omega: let's check its max.
    v_max = v_df['omega'].max()
    s_max = df['gyro_mag'].max()
    print(f"Video max omega (rad/s): {v_max:.2f}")
    print(f"Sensor max gyro (raw): {s_max:.2f}")
    
    # If s_max is around 12.5 and v_max is around 12.5, it's rad/s.
    # If s_max is around 720 and v_max is around 12.5, sensor is deg/s.
    sensor_is_deg = False
    if s_max > 50:
        sensor_is_deg = True
        df['gyro_rad_s'] = df['gyro_mag'] * (np.pi / 180.0)
    else:
        df['gyro_rad_s'] = df['gyro_mag']
        
    # 3. Synchronization via Cross-Correlation
    # Resample video to sensor rate (roughly)
    # Sensor rate: 2929 samples / 60s = ~50Hz.
    # Video rate: 60Hz.
    # Let's interpolate both to a common 100Hz grid.
    t_common = np.arange(0, 60, 0.01)
    s_interp = np.interp(t_common, df['t_sec'], df['gyro_rad_s'])
    v_interp = np.interp(t_common, v_df['t_sec'], v_df['omega'])
    
    # Cross-correlate
    correlation = correlate(v_interp, s_interp, mode='full')
    lags = np.arange(-len(v_interp) + 1, len(v_interp))
    best_lag = lags[np.argmax(correlation)]
    time_offset = best_lag * 0.01 # 10ms steps
    print(f"Best time offset: {time_offset:.2f} seconds")
    
    # Apply offset
    df['t_synced'] = df['t_sec'] + time_offset
    
    # 4. Movement Detection (Start/Stop)
    # Find when omega > 0.1 rad/s
    threshold = 0.2
    moving_v = v_df[v_df['omega'] > threshold]
    if not moving_v.empty:
        v_start = moving_v['t_sec'].iloc[0]
        v_end = moving_v['t_sec'].iloc[-1]
    else:
        v_start, v_end = 0, 60
        
    print(f"Movement detected in video: {v_start:.2f}s to {v_end:.2f}s")
    
    # 5. Final Plot
    plt.figure(figsize=(12, 6))
    plt.plot(v_df['t_sec'], v_df['omega'], 'b-', alpha=0.5, label='Video Angular Velocity (rad/s)')
    plt.plot(df['t_synced'], df['gyro_rad_s'], 'r-', alpha=0.5, label='Sensor Gyro (rad/s, synced)')
    
    plt.axvspan(v_start, v_end, color='gray', alpha=0.2, label='Movement Period')
    plt.xlim(v_start - 2, v_end + 2)
    plt.title("Comparison: Video vs Sensor Angular Velocity")
    plt.xlabel("Time (s)")
    plt.ylabel("Angular Velocity (rad/s)")
    plt.legend()
    plt.grid(True)
    plt.savefig("sync_comparison.png")
    print("Saved sync_comparison.png")

if __name__ == "__main__":
    analyze()
