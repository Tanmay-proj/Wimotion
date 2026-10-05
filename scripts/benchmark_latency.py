# ==============================================================================
# WiMotion v2.4: Real-Time Sub-Second Latency Benchmark (Strict Non-Fallback)
# ==============================================================================
import sys
import json
import time
import numpy as np
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import DATA_DIR, NUM_SUBCARRIERS
from src.presence_engine import PresenceEngine

def run_latency_benchmark(verbose: bool = True):
    test_csv = DATA_DIR / "unseen_entry_exit_test.csv"
    if not test_csv.exists():
        if verbose: print(f"Holdout file {test_csv} not found.")
        return {"passed": False}

    df = pd.read_csv(test_csv)
    amp_cols = [f"amp_{i}" for i in range(NUM_SUBCARRIERS)]
    timestamps = df["host_timestamp"].values
    amps = df[amp_cols].values
    gt_labels = df["ground_truth_label"].values
    # Strict clean baseline evaluation without persisted TARE interference
    engine = PresenceEngine(auto_load_persisted_tare=False)

    if verbose:
        print("=" * 70)
        print("  WIMOTION v2.4: LATENCY & HYSTERESIS REAL-TIME BENCHMARK")
        print("=" * 70)
        print(f"Test Stream: {test_csv.name} ({len(df)} frames, {len(df)/20.0:.1f}s duration)")

    # Ground truth event timestamps from metadata:
    # 0.0s - 15.0s: empty room
    # 15.0s: human enters sensing zone (crossing LOS)
    # 15.0s - 56.0s: human present (standing, slow motion, walking, exiting)
    # 56.0s: human completes exit, room is clear
    entry_gt_t = 15.0
    exit_gt_t = 56.0

    detected_entry_t = None
    detected_exit_t = None
    state_flips = 0
    prev_state = None

    start_sim_t = timestamps[0]
    for i in range(len(df)):
        frame = amps[i]
        t = timestamps[i]
        rssi = float(df["rssi"].iloc[i]) if "rssi" in df.columns else -60.0
        rel_t = t - start_sim_t

        res = engine.process_frame(frame, timestamp=t, rssi=rssi)
        if res is not None:
            state = res["state"]
            if prev_state is not None and state != prev_state:
                state_flips += 1

            # In the 3-state system, entry is triggered when state transitions into detection
            # (ANALYZING / HUMAN PRESENT, presence_score >= 0.25)
            if rel_t >= 15.0 and rel_t <= 25.0 and res["presence_score"] >= 0.25 and detected_entry_t is None:
                detected_entry_t = rel_t

            # Exit is triggered when state returns to SENSING ZONE CLEAR after physical exit
            if rel_t >= 56.0 and (state == "SENSING ZONE CLEAR" or not res["presence"]) and detected_exit_t is None:
                detected_exit_t = rel_t

            prev_state = state

    if detected_entry_t is not None:
        entry_latency = detected_entry_t - entry_gt_t
        entry_pass = (entry_latency < 1.5)
        entry_msg = f"t = {detected_entry_t:.2f} s (Latency: {entry_latency:.2f} s) -> [{'PASS' if entry_pass else 'FAIL'}]"
    else:
        entry_latency = None
        entry_pass = False
        entry_msg = "NOT DETECTED in window -> [FAIL]"

    if detected_exit_t is not None:
        exit_latency = detected_exit_t - exit_gt_t
        exit_pass = (exit_latency < 1.8)
        exit_msg = f"t = {detected_exit_t:.2f} s (Latency: {exit_latency:.2f} s) -> [{'PASS' if exit_pass else 'FAIL'}]"
    else:
        exit_latency = None
        exit_pass = False
        exit_msg = "NOT DETECTED in window -> [FAIL]"

    passed = bool(entry_pass and exit_pass)

    if verbose:
        print(f"\n--- Benchmark Results ---")
        print(f"Physical Entry Event:     t = {entry_gt_t:.2f} s")
        print(f"System Entry Detection:   {entry_msg}")
        print(f"Physical Exit Event:      t = {exit_gt_t:.2f} s")
        print(f"System Clear Detection:   {exit_msg}")
        print(f"Total State Transitions:  {state_flips}")
        print(f"Overall Benchmark Status: [{'PASS' if passed else 'FAIL'}]")
        print("=" * 70)

    return {
        "entry_latency_sec": entry_latency,
        "exit_latency_sec": exit_latency,
        "entry_pass": entry_pass,
        "exit_pass": exit_pass,
        "state_flips": state_flips,
        "passed": passed
    }

if __name__ == "__main__":
    run_latency_benchmark()
