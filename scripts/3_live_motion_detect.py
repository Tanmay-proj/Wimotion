# ==============================================================================
# WiMotion v2.0: Real-Time Contactless Human Presence CLI
# ==============================================================================
import serial
import serial.tools.list_ports
import pickle
import time
import sys
import argparse
import collections
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import (
    MODEL_FILE, DEFAULT_BAUDRATE, DEFAULT_SERIAL_TIMEOUT, NUM_SUBCARRIERS,
    WINDOW_DURATION_SEC, PREDICTION_INTERVAL_SEC, MIN_WINDOW_FRAMES,
    FEATURE_COUNT, FEATURE_ENGINE_VERSION,
    SERIAL_RECONNECT_ATTEMPTS, SERIAL_RECONNECT_DELAY_SEC,
)
from src.csi_parser import parse_csi_line, compute_subcarrier_amplitudes
from src.presence_engine import PresenceEngine

def select_port_interactive():
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("[!] No COM ports detected! Connect the ESP32 CSI receiver.")
        sys.exit(1)
    if len(ports) == 1:
        return ports[0].device
    print("\nAvailable COM Ports:")
    for idx, p in enumerate(ports):
        print(f"  [{idx + 1}] {p.device} - {p.description}")
    while True:
        choice = input(f"Select Port [1-{len(ports)}] (default: 1): ").strip()
        if choice == "": return ports[0].device
        if choice.isdigit() and 1 <= int(choice) <= len(ports): return ports[int(choice)-1].device

def open_serial_with_reconnect(port, baud):
    for attempt in range(1, SERIAL_RECONNECT_ATTEMPTS + 1):
        try:
            ser = serial.Serial(port, baud, timeout=DEFAULT_SERIAL_TIMEOUT)
            ser.reset_input_buffer()
            return ser
        except serial.SerialException as e:
            print(f"[!] Serial attempt {attempt}/{SERIAL_RECONNECT_ATTEMPTS}: {e}")
            if attempt < SERIAL_RECONNECT_ATTEMPTS: time.sleep(SERIAL_RECONNECT_DELAY_SEC)
    raise RuntimeError(f"Could not connect to {port}")

def main():
    ap = argparse.ArgumentParser(description="WiMotion v2.0 human presence CLI")
    ap.add_argument("--port", default=None)
    ap.add_argument("--baud", type=int, default=DEFAULT_BAUDRATE)
    args = ap.parse_args()

    if not MODEL_FILE.exists():
        print("[ERROR] No deployment model. Run scripts\\2_train_hardware_model.py first.")
        return 1
    with open(MODEL_FILE, "rb") as f: payload = pickle.load(f)
    if payload.get("feature_engine_version") != FEATURE_ENGINE_VERSION:
        print(f"[ERROR] Model expects {payload.get('feature_engine_version')} but code is {FEATURE_ENGINE_VERSION}.")
        return 1
    if payload.get("feature_count") != FEATURE_COUNT:
        print("[ERROR] Model feature-count mismatch. Retrain the model.")
        return 1

    port = args.port or select_port_interactive()
    ser = open_serial_with_reconnect(port, args.baud)
    engine = PresenceEngine(payload)
    buffer = collections.deque(maxlen=200)
    valid = corrupt = 0
    started = time.time(); last_eval = 0.0; last = engine.last; last_rssi = "N/A"

    print("=" * 92)
    print(" WiMotion v2.0 — CONTACTLESS HUMAN PRESENCE OBSERVATORY (CLI)")
    print(" Controlled sensing zone: ~1.5 m | 20 Hz uniform feature grid | Ctrl+C to stop")
    print("=" * 92)
    try:
        while True:
            raw = ser.readline()
            if not raw: continue
            line = raw.decode("utf-8", errors="ignore").strip()
            meta, csi_raw = parse_csi_line(line)
            if meta is None:
                if line.startswith("CSI_DATA"): corrupt += 1
                continue
            amps = compute_subcarrier_amplitudes(csi_raw, num_subcarriers=NUM_SUBCARRIERS)
            if amps is None:
                corrupt += 1; continue
            now = time.time(); buffer.append((now, amps)); valid += 1
            if meta.get("rssi") != "N/A": last_rssi = meta["rssi"]
            if now - last_eval < PREDICTION_INTERVAL_SEC: continue
            last_eval = now
            tuples = [x for x in buffer if x[0] >= now - WINDOW_DURATION_SEC]
            if len(tuples) < MIN_WINDOW_FRAMES: continue
            ts = np.array([x[0] for x in tuples]); amps_arr = np.array([x[1] for x in tuples])
            try: last = engine.predict(amps_arr, ts)
            except Exception as e: print(f"\n[!] Prediction error: {e}"); continue
            fps = valid / max(0.1, now-started)
            status_str = last.get('status') or last.get('state', 'SENSING ZONE CLEAR')
            print(f"\r[{status_str:20s}] Presence {last['presence_score']*100:5.1f}% | "
                  f"Confidence {last['confidence']*100:5.1f}% | Coherence {last['coherence']:.3f} | "
                  f"CSI {fps:5.1f} Hz | RSSI {last_rssi:>4s} dBm | Peak {last['peak_frequency_hz']:.2f} Hz", end="", flush=True)
    except KeyboardInterrupt:
        print("\n\n[+] Presence detection stopped.")
    finally:
        ser.close()
    return 0

if __name__ == "__main__": raise SystemExit(main())
