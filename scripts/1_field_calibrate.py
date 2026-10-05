# ==============================================================================
# Step 1: Site Multi-Pose Presence Data Collection (v2.1 Guided Calibration)
# ==============================================================================
import serial
import serial.tools.list_ports
import csv
import json
import os
import sys
import time
import argparse
import re
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import (
    DATA_DIR, DEFAULT_BAUDRATE, DEFAULT_SERIAL_TIMEOUT, NUM_SUBCARRIERS,
    NOMINAL_SAMPLING_RATE_HZ, SUBCARRIER_MAPPING_MODE, WINDOW_SIZE,
    SERIAL_RECONNECT_ATTEMPTS, SERIAL_RECONNECT_DELAY_SEC
)
from src.csi_parser import parse_csi_line, compute_subcarrier_amplitudes

DEFAULT_EMPTY_DURATION = 40   # 40 seconds for empty room baseline
DEFAULT_HUMAN_DURATION = 45   # 45 seconds (15s Stand + 15s Slow + 15s Walk)

ACTIVITIES = {
    "empty_room": "EMPTY ROOM BASELINE (Leave the 1.5m zone completely clear of human presence)",
    "walking": "MULTI-POSE HUMAN PRESENCE (15s Standing Still + 15s Slow Movement + 15s Walking)"
}

def select_port_interactive():
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("[!] No COM ports detected! Connect your ESP32 RX board via USB.")
        sys.exit(1)
    if len(ports) == 1:
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
            print(f"[!] Serial connection attempt {attempt}/{SERIAL_RECONNECT_ATTEMPTS} failed on {port}: {e}")
            if attempt < SERIAL_RECONNECT_ATTEMPTS:
                time.sleep(SERIAL_RECONNECT_DELAY_SEC)
    print(f"[ERROR] Could not establish connection to {port} after {SERIAL_RECONNECT_ATTEMPTS} attempts.")
    sys.exit(1)

def get_next_session_paths(label: str):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    existing_files = list(DATA_DIR.glob(f"{label}*.csv"))
    
    max_idx = 0
    for f in existing_files:
        match = re.search(rf"{label}_session_(\d+)\.csv", f.name)
        if match:
            max_idx = max(max_idx, int(match.group(1)))
        elif f.name == f"{label}.csv":
            max_idx = max(max_idx, 1)

    next_idx = max_idx + 1 if existing_files else 1
    session_str = f"{label}_session_{next_idx:02d}"
    out_csv = DATA_DIR / f"{session_str}.csv"
    out_meta = DATA_DIR / f"{session_str}_metadata.json"
    return out_csv, out_meta, next_idx

def record_activity(port_name: str, baud: int, label: str, desc: str, duration_sec: int):
    out_csv, out_meta, session_idx = get_next_session_paths(label)

    print("\n" + "=" * 65)
    print(f"[*] RECORDING TARGET: {label.upper()} (Session #{session_idx})")
    print(f"[*] PROTOCOL:         {desc}")
    print(f"[*] Target Duration:  {duration_sec} seconds")
    print(f"[*] Output File:      {out_csv.name}")
    print("=" * 65)

    if label == "walking":
        print("\n--- GUIDED MULTI-POSE PROTOCOL ---")
        print("  [00s - 15s]: STAND STILL inside the 1.5m zone")
        print("  [15s - 30s]: SLOW MICRO-MOVEMENT inside the 1.5m zone")
        print("  [30s - 45s]: NORMAL WALKING / PACING inside the 1.5m zone")
        print("-----------------------------------")

    input(f"\n>> Press ENTER when ready to start recording '{label}' (Session #{session_idx})...")

    ser = open_serial_with_reconnect(port_name, baud)

    print("[WARM-UP] Waiting for active CSI stream lock (up to 12s)...")
    warm_start = time.time()
    lock_count = 0
    while (time.time() - warm_start) < 12.0:
        raw = ser.readline()
        if not raw:
            continue
        try:
            line_str = raw.decode("utf-8", errors="ignore").strip()
            if line_str.startswith("CSI_DATA"):
                lock_count += 1
                if lock_count >= 5:
                    print("[+] CSI stream locked! Starting recording session...")
                    break
        except Exception:
            pass
    ser.reset_input_buffer()

    print("\n>>> RECORDING LIVE CSI STREAM <<< [Press Ctrl+C to abort & discard]")

    start_time = time.time()
    collected_rows = []
    corrupt_count = 0
    channels = set()
    rssi_list = []
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
                    ser = open_serial_with_reconnect(port_name, baud)
                    continue

                if not raw_line:
                    continue
                try:
                    line_str = raw_line.decode("utf-8", errors="ignore").strip()
                except UnicodeDecodeError:
                    corrupt_count += 1
                    continue

                meta, csi_raw = parse_csi_line(line_str)
                if meta is not None:
                    first_word_val = int(meta.get("first_word", "0"))
                    amps = compute_subcarrier_amplitudes(csi_raw, num_subcarriers=NUM_SUBCARRIERS, first_word=first_word_val)
                    if amps is not None and len(amps) == NUM_SUBCARRIERS:
                        host_timestamp = time.time()
                        rssi = meta.get("rssi", "N/A")
                        writer.writerow([host_timestamp, rssi] + amps)
                        collected_rows.append(amps)

                        if meta.get("channel") != "N/A":
                            channels.add(meta["channel"])
                        if rssi != "N/A":
                            try:
                                rssi_list.append(int(rssi))
                            except ValueError:
                                pass

                        elapsed = time.time() - start_time
                        fps = len(collected_rows) / max(0.1, elapsed)

                        pose_hint = ""
                        if label == "walking":
                            if elapsed < 15:
                                pose_hint = "[POSE: STANDING STILL]"
                            elif elapsed < 30:
                                pose_hint = "[POSE: SLOW MOVEMENT]"
                            else:
                                pose_hint = "[POSE: NORMAL WALKING]"

                        print(f"  Progress: {elapsed:4.1f}/{duration_sec}s | Frames: {len(collected_rows):4d} ({fps:4.1f} pkt/s) {pose_hint}    ", end="\r")
                    else:
                        corrupt_count += 1

    except KeyboardInterrupt:
        is_aborted = True
        print("\n\n[!] Recording aborted by user (Ctrl+C).")
    finally:
        ser.close()

    if is_aborted:
        if out_csv.exists():
            out_csv.unlink()
        if out_meta.exists():
            out_meta.unlink()
        print(f"[CLEANUP] Partial session '{out_csv.name}' was discarded cleanly.")
        return 0

    elapsed = time.time() - start_time
    avg_fps = len(collected_rows) / max(0.1, elapsed)

    status_str = "VALID_COMPLETE"
    print(f"\n[+] Recorded {len(collected_rows)} valid CSI frames (Status: {status_str} | Avg Rate: {avg_fps:.1f} pkt/s)")

    metadata_payload = {
        "activity_label": label,
        "session_index": session_idx,
        "dataset_status": status_str,
        "recorded_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(elapsed, 2),
        "target_sampling_rate_hz": NOMINAL_SAMPLING_RATE_HZ,
        "measured_sampling_rate_hz": round(avg_fps, 2),
        "baudrate": baud,
        "serial_port_host": port_name,
        "num_csi_samples": NUM_SUBCARRIERS,
        "subcarrier_mapping": SUBCARRIER_MAPPING_MODE,
        "window_size": WINDOW_SIZE,
        "window_duration_sec": 1.0,
        "engine_version": "v2.1",
        "feature_count": 217,
        "uniform_resample_fs": 20.0,
        "valid_frame_count": len(collected_rows),
        "corrupt_frame_count": corrupt_count,
        "active_channels": list(channels),
        "average_rssi_dbm": round(sum(rssi_list)/len(rssi_list), 1) if rssi_list else "N/A"
    }

    with open(out_meta, "w", encoding="utf-8") as f:
        json.dump(metadata_payload, f, indent=2)
    print(f"[+] Saved recording metadata to {out_meta.name}")
    return len(collected_rows)

def main():
    parser = argparse.ArgumentParser(description="WiMotion Guided Multi-Pose Calibration Data Logger")
    parser.add_argument("--port", type=str, default=None, help="Serial COM port")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUDRATE, help="Baud rate")
    args = parser.parse_args()

    print("=" * 65)
    print("  WiMotion: Guided Multi-Pose Site Data Collection (v2.1)")
    print("=" * 65)

    port = args.port if args.port else select_port_interactive()
    print(f"[+] Using Serial Port: {port} @ {args.baud} baud")

    while True:
        print("\nSelect Activity to Record:")
        print("  [1] Empty Room Baseline (40 sec)")
        print("  [2] Multi-Pose Human Presence (45 sec: Stand + Slow + Walk)")
        print("  [3] Exit to Main Console")

        choice = input("\nChoice [1-3]: ").strip()
        if choice == "1":
            record_activity(port, args.baud, "empty_room", ACTIVITIES["empty_room"], DEFAULT_EMPTY_DURATION)
        elif choice == "2":
            record_activity(port, args.baud, "walking", ACTIVITIES["walking"], DEFAULT_HUMAN_DURATION)
        elif choice == "3":
            print("Exiting data collector.")
            break
        else:
            print("Invalid option. Please enter 1, 2, or 3.")

if __name__ == "__main__":
    main()
