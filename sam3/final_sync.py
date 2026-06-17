import pandas as pd
import numpy as np
import json
import matplotlib.pyplot as plt
from scipy.signal import correlate, savgol_filter

def analyze():
    # 1. Load Sensor Data
    df = pd.read_csv("rotation_data_2026-04-26T11-54-02-612Z.csv")
    # The timestamps seem to have a large jump at the beginning (row 5-6)
    # Let's check for jumps
    df['dt'] = df['timestamp'].diff()
    # print(df['dt'].head(10)) # Row 5 to 6 has a jump of 60000ms (1 minute!)
    
    # Let's only use the data after the jump
    df = df[df['timestamp'] > df['timestamp'].iloc[0] + 1000].copy()
    df['t_sec'] = (df['timestamp'] - df['timestamp'].iloc[0]) / 1000.0
    
    # 2. Load Video Data (LARGE)
    with open("results_2731_large.json", "r") as f:
        video_data = json.load(f)
    traj = video_data['trajectories']['red phone']
    v_df = pd.DataFrame(traj)
    fps = 60000/1001.0
    v_df['t_sec'] = v_df['frame'] / fps
    
    # Load Video Data (TINY)
    with open("results_2731.json", "r") as f:
        tiny_data = json.load(f)
    t_traj = tiny_data['trajectories']['red phone']
    t_df = pd.DataFrame(t_traj)
    t_df['t_sec'] = t_df['frame'] / fps

    # Use REFINED center
    a, b = 654.83, 705.29
    print(f"Using Refined Axle Center: ({a:.2f}, {b:.2f})")
    
    # Process Large
    v_df['angle'] = np.unwrap(np.arctan2(v_df['cy'] - b, v_df['cx'] - a))
    v_df['omega'] = np.abs(np.gradient(v_df['angle'], v_df['t_sec']))
    v_df['omega_s'] = savgol_filter(v_df['omega'], 15, 2)
    
    # Process Tiny
    t_df['angle'] = np.unwrap(np.arctan2(t_df['cy'] - b, t_df['cx'] - a))
    t_df['omega'] = np.abs(np.gradient(t_df['angle'], t_df['t_sec']))
    t_df['omega_s'] = savgol_filter(t_df['omega'], 15, 2)
    
    # 3. Sensor omega
    df['omega_sensor'] = np.abs(df['gyro_gamma']) * (np.pi / 180.0)
    df['omega_sensor_s'] = savgol_filter(df['omega_sensor'], 21, 2)
    
    # 4. Sync (using Large as reference)
    t_common = np.arange(0, 60, 0.01)
    v_interp = np.interp(t_common, v_df['t_sec'], v_df['omega_s'])
    s_interp = np.interp(t_common, df['t_sec'], df['omega_sensor_s'])
    
    correlation = correlate(v_interp, s_interp, mode='full')
    lags = np.arange(-len(v_interp) + 1, len(v_interp))
    best_lag = lags[np.argmax(correlation)]
    time_offset = best_lag * 0.01
    df['t_synced'] = df['t_sec'] + time_offset
    
    # 5. Cropping
    threshold = 0.5
    moving = v_df[v_df['omega_s'] > threshold]
    t_start, t_end = moving['t_sec'].iloc[0], moving['t_sec'].iloc[-1]
    
    # Plot
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 12))
    
    # TOP PANEL: Full Duration
    ax1.plot(v_df['t_sec'], v_df['omega_s'], 'b-', linewidth=1.5, label='Video Omega (SAM2 Large)')
    ax1.plot(t_df['t_sec'], t_df['omega_s'], 'g--', linewidth=1, alpha=0.6, label='Video Omega (SAM2 Tiny)')
    ax1.plot(df['t_synced'], df['omega_sensor_s'], 'r-', linewidth=1.2, alpha=0.5, label='Phone Gyro (Synced)')
    ax1.set_title(f"Full Sequence Context (Offset: {time_offset:.2f}s)")
    ax1.set_ylabel("Angular Velocity (rad/s)")
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # BOTTOM PANEL: Zoomed Movement
    ax2.plot(v_df['t_sec'], v_df['omega_s'], 'b-', linewidth=2.5, label='Video Omega (SAM2 Large)')
    ax2.plot(t_df['t_sec'], t_df['omega_s'], 'g--', linewidth=1.5, alpha=0.8, label='Video Omega (SAM2 Tiny)')
    ax2.plot(df['t_synced'], df['omega_sensor_s'], 'r-', linewidth=2, alpha=0.7, label='Phone Gyro (Synced)')
    
    ax2.set_title("Zoomed View: Active Rotation Phase")
    ax2.set_xlabel("Video Time (s)")
    ax2.set_ylabel("Angular Velocity (rad/s)")
    ax2.set_xlim(t_start - 1, t_end + 1)
    ax2.set_ylim(0, max(v_df['omega_s'].max(), df['omega_sensor_s'].max()) * 1.1)
    ax2.legend()
    ax2.grid(True, which='both', linestyle='--', alpha=0.5)
    
    # Final check: are the values actually the same?
    v_avg = v_df[(v_df['t_sec'] > t_start+1) & (v_df['t_sec'] < t_end-1)]['omega_s'].mean()
    s_avg = df[(df['t_synced'] > t_start+1) & (df['t_synced'] < t_end-1)]['omega_sensor_s'].mean()
    
    ax2.annotate(f"Video Avg: {v_avg:.2f} rad/s\nSensor Avg: {s_avg:.2f} rad/s", 
                 xy=(0.02, 0.95), xycoords='axes fraction', verticalalignment='top',
                 bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    plt.tight_layout()
    plt.savefig("final_sync_plot.png")
    print(f"Long plot saved. Video Avg: {v_avg:.2f}, Sensor Avg: {s_avg:.2f}")

if __name__ == "__main__":
    analyze()
