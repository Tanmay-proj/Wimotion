# ==============================================================================
# WiMotion v3.0: 100-Session Rigorous Empirical Hardware Data Recorder
# (100% Genuine Physical Capture - Scientific Standard & Provenance Logging)
# ==============================================================================
import csv
import json
import os
import shutil
import sys
import time
import argparse
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import serial
import serial.tools.list_ports

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import (
    DATA_DIR, DEFAULT_BAUDRATE, DEFAULT_SERIAL_TIMEOUT, NUM_SUBCARRIERS,
    SERIAL_RECONNECT_ATTEMPTS, SERIAL_RECONNECT_DELAY_SEC
)
from src.csi_parser import parse_csi_line, compute_subcarrier_amplitudes

GENUINE_DATA_DIR = DATA_DIR / "genuine"
GENUINE_DATA_DIR.mkdir(parents=True, exist_ok=True)
ARCHIVE_DATA_DIR = DATA_DIR / "questionable_archive"
ARCHIVE_DATA_DIR.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------------------
# 100-Session Scientific Protocol Specification
# ------------------------------------------------------------------------------
PROTOCOL_SESSIONS = []

# Category 1: Empty Room Baseline (20 sessions, 90s each, presence_label=0)
for i in range(1, 21):
    PROTOCOL_SESSIONS.append({
        "id": f"empty_{i:02d}",
        "category": "EMPTY_ROOM",
        "category_name": "Empty Room Baseline (Noise Floor & Ambient Reflections)",
        "name": f"empty_room_real_{i:02d}",
        "activity": "empty_room",
        "presence_label": 0,
        "position": "NONE",
        "distance_m": 0.0,
        "duration": 90,
        "desc": "Room completely empty of any human. Normal ambient room condition. Do NOT create artificial disturbance."
    })

# Category 2: Stationary Standing (15 sessions, 80s each, presence_label=1)
positions_standing = ["CENTER", "NEAR_TX", "NEAR_RX", "CROSS_LOS", "CENTER"]
for i in range(1, 16):
    pos = positions_standing[(i - 1) % len(positions_standing)]
    dist = 0.5 if "NEAR" in pos else (0.8 if pos == "CROSS_LOS" else 1.2)
    PROTOCOL_SESSIONS.append({
        "id": f"stand_{i:02d}",
        "category": "STANDING",
        "category_name": "Stationary Standing Presence (Micro-Doppler / Respiration)",
        "name": f"standing_real_{i:02d}",
        "activity": "standing",
        "presence_label": 1,
        "position": pos,
        "distance_m": dist,
        "duration": 80,
        "desc": f"Stand stationary at {pos} (~{dist}m). Relaxed posture, normal breathing. Test micro-Doppler & respiration baseline."
    })

# Category 3: Slow Micro-Movement (15 sessions, 80s each, presence_label=1)
positions_slow = ["CENTER", "NEAR_TX", "NEAR_RX", "CROSS_LOS"]
for i in range(1, 16):
    pos = positions_slow[(i - 1) % len(positions_slow)]
    dist = 0.6 if "NEAR" in pos else 1.2
    PROTOCOL_SESSIONS.append({
        "id": f"slow_{i:02d}",
        "category": "SLOW_MOVEMENT",
        "category_name": "Slow Subtle Micro-Movement (Weight shift, head turn)",
        "name": f"slow_real_{i:02d}",
        "activity": "slow_movement",
        "presence_label": 1,
        "position": pos,
        "distance_m": dist,
        "duration": 80,
        "desc": f"Subtle slow motion at {pos}: slow weight shifting, subtle posture adjustment, turning head. No rapid arm swings."
    })

# Category 4: Natural Walking (15 sessions, 85s each, presence_label=1)
for i in range(1, 16):
    PROTOCOL_SESSIONS.append({
        "id": f"walk_{i:02d}",
        "category": "WALKING",
        "category_name": "Continuous & Intermittent Walking",
        "name": f"walking_real_{i:02d}",
        "activity": "walking",
        "presence_label": 1,
        "position": "CROSS_LOS",
        "distance_m": 1.2,
        "duration": 85,
        "desc": "Walk naturally through sensing zone across TX-RX path. Normal walking cadence (~1.5 - 2.0 Hz Doppler shift)."
    })

# Category 5: Dynamic Entry -> Presence -> Exit (15 sessions, 90s each, presence_label=1)
for i in range(1, 16):
    PROTOCOL_SESSIONS.append({
        "id": f"entry_exit_{i:02d}",
        "category": "ENTRY_EXIT",
        "category_name": "Dynamic Entry -> Presence -> Exit Cycles",
        "name": f"entry_exit_real_{i:02d}",
        "activity": "entry_exit",
        "presence_label": 1,
        "position": "TRANSIT",
        "distance_m": 1.5,
        "duration": 90,
        "desc": "Strict timed protocol: 0-15s EMPTY -> 15-35s STEP IN & STAY -> 35-65s DYNAMIC PRESENCE -> 65-75s STEP OUT -> 75-90s EMPTY."
    })

# Category 6: Hard Negatives & Environmental Disturbances (10 sessions, 80s each, presence_label=0)
disturbances = [
    "Ceiling fan on high speed with room empty",
    "Pedestal / table fan oscillating across link with room empty",
    "Door opening and closing outside sensing perimeter",
    "Curtain motion / window draft with room empty",
    "Robot vacuum / small object mechanical movement across floor",
    "Human walking OUTSIDE the closed door (out-of-zone interference)",
    "Fluorescent light cycling / electronic equipment power fluctuation",
    "Chair shifted slightly then empty room",
    "AC compressor turning on / violent air draft",
    "Nearby laptop / smartphone heavy Wi-Fi transmission"
]
for i in range(1, 11):
    PROTOCOL_SESSIONS.append({
        "id": f"hard_neg_{i:02d}",
        "category": "HARD_NEGATIVE",
        "category_name": "Hard Negative Disturbance (Room Empty with RF Noise)",
        "name": f"hard_negative_real_{i:02d}",
        "activity": "hard_negative",
        "presence_label": 0,
        "position": "NONE",
        "distance_m": 0.0,
        "duration": 80,
        "desc": f"HARD NEGATIVE: {disturbances[i - 1]}. NO human in sensing zone. Must test false-positive rejection."
    })

# Category 7: Multi-Distance & Edge-of-Zone Variation (10 sessions, 80s each, presence_label=1)
distances_tests = [0.4, 0.8, 1.2, 1.5, 1.8, 2.0, 2.2, 2.5, 1.0, 1.5]
for i in range(1, 11):
    dist = distances_tests[i - 1]
    PROTOCOL_SESSIONS.append({
        "id": f"dist_{i:02d}",
        "category": "DISTANCE_VARIATION",
        "category_name": "Distance & Sensing Boundary Calibration",
        "name": f"distance_real_{i:02d}",
        "activity": "distance_variation",
        "presence_label": 1,
        "position": f"DIST_{dist:.1f}M",
        "distance_m": dist,
        "duration": 80,
        "desc": f"Human standing/present at calibrated radial distance of {dist:.1f}m from baseline link center."
    })

assert len(PROTOCOL_SESSIONS) == 100, f"Expected 100 sessions, got {len(PROTOCOL_SESSIONS)}"

# ------------------------------------------------------------------------------
# Serial Port Helper
# ------------------------------------------------------------------------------
def select_port_interactive():
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("\n[!] No COM ports detected!")
        print("    Please connect your ESP32 CSI receiver via USB and try again.")
        sys.exit(1)
    if len(ports) == 1:
        print(f"[+] Auto-detected Serial Port: {ports[0].device} ({ports[0].description})")
        return ports[0].device

    print("\nAvailable COM Ports:")
    for idx, p in enumerate(ports):
        print(f"  [{idx + 1}] {p.device} - {p.description}")

    while True:
        choice = input(f"Select Port [1-{len(ports)}] (default: 1): ").strip()
        if choice == "":
            return ports[0].device
        if choice.isdigit() and 1 <= int(choice) <= len(ports):
            return ports[int(choice) - 1].device
        print("Invalid selection. Try again.")

def open_serial_with_reconnect(port: str, baud: int):
    for attempt in range(1, SERIAL_RECONNECT_ATTEMPTS + 1):
        try:
            ser = serial.Serial(port, baud, timeout=DEFAULT_SERIAL_TIMEOUT)
            ser.reset_input_buffer()
            return ser
        except serial.SerialException as e:
            print(f"[!] Serial attempt {attempt}/{SERIAL_RECONNECT_ATTEMPTS} failed on {port}: {e}")
            if attempt < SERIAL_RECONNECT_ATTEMPTS:
                time.sleep(SERIAL_RECONNECT_DELAY_SEC)
    raise RuntimeError(f"Could not establish serial connection to {port} at {baud} baud.")

# ------------------------------------------------------------------------------
# Progress Audit
# ------------------------------------------------------------------------------
def check_dataset_progress():
    counts = {}
    total_recorded = 0
    for s in PROTOCOL_SESSIONS:
        cat = s["category"]
        if cat not in counts:
            counts[cat] = {"total": 0, "done": 0, "name": s["category_name"]}
        counts[cat]["total"] += 1

        csv_path = GENUINE_DATA_DIR / f"{s['name']}.csv"
        if csv_path.exists() and csv_path.stat().st_size > 1000:
            counts[cat]["done"] += 1
            total_recorded += 1

    return counts, total_recorded

def print_progress_table():
    counts, total = check_dataset_progress()
    print("\n" + "=" * 78)
    print("      GENUINE PHYSICAL DATASET PROGRESS (TARGET: 100 SESSIONS)")
    print("=" * 78)
    for cat, info in counts.items():
        pct = (info["done"] / info["total"]) * 100.0
        bar = "#" * int(info["done"]) + "-" * (info["total"] - info["done"])
        print(f"  [{bar}] {info['done']:2d}/{info['total']:2d} ({pct:5.1f}%) | {info['name'][:42]}")
    print("-" * 78)
    print(f"  TOTAL RECORDED: {total} / 100 Genuine Physical Sessions ({(total / 100.0) * 100:.1f}%)")
    print(f"  DESTINATION:    {GENUINE_DATA_DIR}")
    print("=" * 78)

# ------------------------------------------------------------------------------
# Single Session Recorder with Phase Timers & Rich Metadata
# ------------------------------------------------------------------------------
def record_single_session(port: str, baud: int, session_spec: dict):
    name = session_spec["name"]
    duration_sec = session_spec["duration"]
    desc = session_spec["desc"]
    position = session_spec["position"]
    dist_m = session_spec["distance_m"]
    act_label = session_spec["activity"]
    presence_label = session_spec["presence_label"]

    out_csv = GENUINE_DATA_DIR / f"{name}.csv"
    out_meta = GENUINE_DATA_DIR / f"{name}_metadata.json"

    print("\n" + "=" * 75)
    print(f"  SESSION ID:   {session_spec['id'].upper()} -> {name}")
    print(f"  CATEGORY:     {session_spec['category_name']}")
    print(f"  ACTIVITY:     {act_label.upper()} (Presence Ground Truth: {presence_label})")
    print(f"  POSITION:     {position} (Distance: {dist_m:.1f}m)")
    print(f"  DURATION:     {duration_sec}s")
    print(f"  PROTOCOL:     {desc}")
    print(f"  OUTPUT FILE:  data/genuine/{out_csv.name}")
    print("=" * 75)

    if out_csv.exists() and out_csv.stat().st_size > 1000:
        ans = input(f"\n[!] WARNING: {out_csv.name} already exists. Re-record/overwrite? [y/N]: ").strip().lower()
        if ans != "y":
            print("Skipping session.")
            return False

    input("\n>> Press ENTER to begin 5-second Pre-Roll Countdown...")

    for i in range(5, 0, -1):
        print(f"  [PRE-ROLL] Starting in {i}s... Take your designated position!", end="\r", flush=True)
        time.sleep(1.0)
    print("\n[+] STREAM ACTIVE -> RECORDING PHYSICAL HARDWARE FRAMES NOW!\n")

    ser = open_serial_with_reconnect(port, baud)
    ser.reset_input_buffer()

    collected_rows = []
    rssi_list = []
    channels = set()
    start_time = time.time()
    is_aborted = False

    try:
        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["host_timestamp", "rssi"] + [f"amp_{i}" for i in range(NUM_SUBCARRIERS)])

            while (time.time() - start_time) < duration_sec:
                try:
                    raw_line = ser.readline()
                except serial.SerialException as e:
                    print(f"\n[!] Serial read error: {e}. Reconnecting...")
                    ser.close()
                    ser = open_serial_with_reconnect(port, baud)
                    continue

                if not raw_line:
                    continue
                try:
                    line_str = raw_line.decode("utf-8", errors="ignore").strip()
                except UnicodeDecodeError:
                    continue

                meta, csi_raw = parse_csi_line(line_str)
                if meta is not None:
                    first_word_val = int(meta.get("first_word", "0"))
                    amps = compute_subcarrier_amplitudes(csi_raw, num_subcarriers=NUM_SUBCARRIERS, first_word=first_word_val)
                    if amps is not None and len(amps) == NUM_SUBCARRIERS:
                        now_ts = time.time()
                        rssi_val = meta.get("rssi", "-65")
                        writer.writerow([now_ts, rssi_val] + amps)
                        collected_rows.append(amps)

                        if meta.get("channel") != "N/A":
                            channels.add(meta["channel"])
                        try:
                            rssi_list.append(float(rssi_val))
                        except ValueError:
                            pass

                        elapsed = now_ts - start_time
                        remaining = max(0, duration_sec - elapsed)
                        fps = len(collected_rows) / max(0.1, elapsed)
                        prog_bar_len = 25
                        filled = int(prog_bar_len * (elapsed / duration_sec))
                        bar = "#" * filled + "-" * (prog_bar_len - filled)

                        # Phase indicator for entry/exit
                        phase_guide = ""
                        if session_spec["category"] == "ENTRY_EXIT":
                            if elapsed < 15:
                                phase_guide = "[PHASE 1: OUTSIDE / EMPTY]"
                            elif elapsed < 35:
                                phase_guide = "[PHASE 2: STEP IN & STAY]"
                            elif elapsed < 65:
                                phase_guide = "[PHASE 3: DYNAMIC MOTION]"
                            elif elapsed < 75:
                                phase_guide = "[PHASE 4: STEP OUT]"
                            else:
                                phase_guide = "[PHASE 5: OUTSIDE / EMPTY]"

                        print(f"  [{bar}] {elapsed:4.1f}s/{duration_sec}s | Rem: {remaining:3.0f}s | Pkts: {len(collected_rows):4d} ({fps:4.1f} Hz) | {phase_guide}", end="\r", flush=True)

    except KeyboardInterrupt:
        print("\n\n[!] Recording interrupted by user (Ctrl+C).")
        is_aborted = True
    finally:
        ser.close()

    print()
    if is_aborted or len(collected_rows) < 50:
        print("[!] Incomplete session (<50 packets). Discarding output.")
        if out_csv.exists():
            out_csv.unlink()
        return False

    # Compute Metadata (Scientific Schema)
    duration_actual = time.time() - start_time
    avg_fps = len(collected_rows) / max(0.1, duration_actual)
    avg_rssi = float(np.mean(rssi_list)) if rssi_list else -62.0

    metadata = {
        "session_id": session_spec["id"],
        "session_name": name,
        "activity": act_label,
        "presence_label": presence_label,
        "position": position,
        "distance_m": dist_m,
        "duration_sec": round(duration_actual, 2),
        "channel": int(list(channels)[0]) if channels else 6,
        "tx": "ESP32_WROOM_TX",
        "rx": "ESP32_WROOM_RX",
        "baud": baud,
        "measured_fps": round(avg_fps, 2),
        "environment": "indoor_rf_testbed",
        "physical_recording": True,
        "valid_frames": len(collected_rows),
        "average_rssi_dbm": round(avg_rssi, 1),
        "protocol_description": desc,
        "timestamp_utc": datetime.now(timezone.utc).isoformat()
    }

    with open(out_meta, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"\n[OK] Successfully saved genuine physical recording:")
    print(f"     CSV:      data/genuine/{out_csv.name} ({len(collected_rows)} frames | {avg_fps:.1f} Hz)")
    print(f"     METADATA: data/genuine/{out_meta.name}")
    return True

# ------------------------------------------------------------------------------
# Main Menu
# ------------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="WiMotion v3.0 100-Session Rigorous Empirical Hardware Recorder")
    parser.add_argument("--port", type=str, default=None, help="Serial COM Port")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUDRATE, help="Baud rate")
    args = parser.parse_args()

    print("=" * 78)
    print("      WIMOTION v3.0: 100-SESSION RIGOROUS EMPIRICAL HARDWARE RECORDER")
    print("         (100% Genuine Physical Capture - Scientific Standard)")
    print("=" * 78)

    port = args.port if args.port else select_port_interactive()
    print(f"[+] Serial Port: {port} @ {args.baud} baud\n")

    while True:
        print_progress_table()
        print("\nDATASET COLLECTION MENU:")
        print("  [1] Record Next Incomplete Session (Automatic Smart Order)")
        print("  [2] Phase 1: EMPTY ROOM Baseline (20 Sessions x 90s)")
        print("  [3] Phase 2: STATIONARY STANDING (15 Sessions x 80s: Center, TX, RX, LOS)")
        print("  [4] Phase 3: SLOW MICRO-MOVEMENT (15 Sessions x 80s: Subtle weight/head shifts)")
        print("  [5] Phase 4: NATURAL WALKING (15 Sessions x 85s: Cross-LOS cadence)")
        print("  [6] Phase 5: ENTRY -> PRESENCE -> EXIT (15 Sessions x 90s: Timed cycle)")
        print("  [7] Phase 6: HARD NEGATIVES (10 Sessions x 80s: Fans, drafts, out-of-zone)")
        print("  [8] Phase 7: MULTI-DISTANCE VARIATIONS (10 Sessions x 80s: 0.4m to 2.5m range)")
        print("  [9] Record Specific Session by ID (e.g. walk_04, empty_08, entry_exit_02)")
        print("  [0] Exit")

        choice = input("\nSelect Option [0-9]: ").strip()

        if choice == "0":
            print("\nExiting WiMotion recorder. Goodbye!")
            break

        elif choice == "1":
            # Find first incomplete session
            found = False
            for s in PROTOCOL_SESSIONS:
                csv_p = GENUINE_DATA_DIR / f"{s['name']}.csv"
                if not csv_p.exists() or csv_p.stat().st_size < 1000:
                    record_single_session(port, args.baud, s)
                    found = True
                    break
            if not found:
                print("\n[***] CONGRATULATIONS! All 100 genuine physical sessions are complete!")

        elif choice in ["2", "3", "4", "5", "6", "7", "8"]:
            cat_map = {
                "2": "EMPTY_ROOM",
                "3": "STANDING",
                "4": "SLOW_MOVEMENT",
                "5": "WALKING",
                "6": "ENTRY_EXIT",
                "7": "HARD_NEGATIVE",
                "8": "DISTANCE_VARIATION"
            }
            target_cat = cat_map[choice]
            sessions = [s for s in PROTOCOL_SESSIONS if s["category"] == target_cat]
            print(f"\n[*] Starting batch capture for: {sessions[0]['category_name']} ({len(sessions)} sessions)")
            for idx, s in enumerate(sessions, 1):
                csv_p = GENUINE_DATA_DIR / f"{s['name']}.csv"
                if csv_p.exists() and csv_p.stat().st_size > 1000:
                    print(f"  [Skipping already recorded] {s['name']}")
                    continue
                print(f"\n>>> Batch Progress: {idx} of {len(sessions)} <<<")
                record_single_session(port, args.baud, s)
                input("\n>> Press ENTER to proceed to next recording (take a breath!)...")

        elif choice == "9":
            target_id = input("Enter session ID (e.g. empty_01, walk_03, entry_exit_05): ").strip().lower()
            match = [s for s in PROTOCOL_SESSIONS if s["id"] == target_id or s["name"] == target_id]
            if match:
                record_single_session(port, args.baud, match[0])
            else:
                print(f"[!] Session ID '{target_id}' not recognized.")

        else:
            print("[!] Invalid option. Please select 0-9.")

if __name__ == "__main__":
    main()
