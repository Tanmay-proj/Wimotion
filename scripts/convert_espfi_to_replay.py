#!/usr/bin/env python3
"""
Convert ESP-FI processed .npz files into WiMotion replay CSV format.

The ESP-FI dataset contains WiFi CSI amplitude data from 7 activities × 6 rooms × 10 trials.
Each .npz has a 2D array of shape (frames, 64) with subcarrier amplitudes.
This script converts them to the WiMotion format: host_timestamp,rssi,amp_0..amp_63

Output CSVs are placed in data/ so the dashboard can replay them.
"""
import sys
import json
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

ESPFI_DIR = PROJECT_ROOT / "datasets" / "processed" / "esp_fi"
OUTPUT_DIR = PROJECT_ROOT / "data"

# How many sessions per activity to convert (keep it manageable)
MAX_PER_ACTIVITY = 2

def convert_npz_to_csv(npz_path: Path, output_path: Path):
    """Convert a single ESP-FI .npz to WiMotion replay CSV."""
    data = np.load(npz_path)
    # ESP-FI npz files have 'amplitudes' or the first array key
    if 'amplitudes' in data:
        amps = data['amplitudes']
    elif 'arr_0' in data:
        amps = data['arr_0']
    else:
        keys = list(data.keys())
        if len(keys) == 0:
            print(f"  [!] Empty npz: {npz_path.name}")
            return False
        amps = data[keys[0]]

    n_frames = amps.shape[0]
    n_subs = amps.shape[1] if amps.ndim > 1 else 64

    # Pad or trim to 64 subcarriers
    if amps.ndim == 1:
        amps = amps.reshape(-1, 64)
    if n_subs < 64:
        pad = np.zeros((n_frames, 64 - n_subs))
        amps = np.hstack([amps, pad])
    elif n_subs > 64:
        amps = amps[:, :64]

    # Generate synthetic timestamps at ~20 Hz (typical ESP32 CSI rate)
    timestamps = np.arange(n_frames) / 20.0 + 1700000000.0  # Reasonable epoch

    # Generate synthetic RSSI (typical indoor range)
    rssi = np.full(n_frames, -62.0) + np.random.normal(0, 2, n_frames)
    rssi = np.clip(rssi, -80, -40)

    # Write CSV
    header = "host_timestamp,rssi," + ",".join(f"amp_{i}" for i in range(64))
    with open(output_path, 'w') as f:
        f.write(header + "\n")
        for i in range(n_frames):
            row = f"{timestamps[i]:.6f},{rssi[i]:.1f}"
            row += "," + ",".join(f"{amps[i, j]:.4f}" for j in range(64))
            f.write(row + "\n")

    return True


def main():
    if not ESPFI_DIR.exists():
        print(f"[!] ESP-FI processed directory not found: {ESPFI_DIR}")
        return

    npz_files = sorted(ESPFI_DIR.glob("*.npz"))
    if not npz_files:
        print("[!] No .npz files found in ESP-FI processed directory.")
        return

    print(f"[*] Found {len(npz_files)} ESP-FI .npz files")

    # Group by activity
    activities = {}
    for f in npz_files:
        # Filename: espfi_3-1-1-1_running.npz -> activity = "running"
        name = f.stem  # e.g. "espfi_3-1-1-1_running"
        parts = name.split("_", 1)
        if len(parts) == 2:
            activity = parts[1]
        else:
            activity = "unknown"
        activities.setdefault(activity, []).append(f)

    converted = 0
    for activity, files in sorted(activities.items()):
        for i, npz_path in enumerate(files[:MAX_PER_ACTIVITY]):
            # Output name: running_session_01.csv
            out_name = f"{activity}_session_{i+1:02d}.csv"
            out_path = OUTPUT_DIR / out_name

            print(f"  Converting {npz_path.name} -> {out_name}...", end=" ")
            if convert_npz_to_csv(npz_path, out_path):
                print(f"OK ({out_path.stat().st_size // 1024} KB)")
                converted += 1
            else:
                print("FAILED")

    print(f"\n[+] Converted {converted} ESP-FI sessions to WiMotion replay format in data/")
    print("[+] These sessions will now appear in the Observatory dashboard session picker.")


if __name__ == "__main__":
    main()
