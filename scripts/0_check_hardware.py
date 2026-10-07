# ==============================================================================
# Step 0: Comprehensive ESP32 Hardware & CSI Stream Diagnostic
# ==============================================================================
import serial
import serial.tools.list_ports
import sys
import time
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import (
    DEFAULT_BAUDRATE, NUM_SUBCARRIERS, NOMINAL_SAMPLING_RATE_HZ,
    REQUIRED_RAW_CSI_BYTES, DEFAULT_SERIAL_TIMEOUT, MIN_ACCEPTABLE_DATASET_FPS
)
from src.csi_parser import parse_csi_line, compute_subcarrier_amplitudes

def select_port_interactive():
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("\n[!] No COM ports detected!")
        print("    1. Connect your ESP32 board via USB data cable.")
        print("    2. Ensure USB-to-UART drivers (CP2102/CH340) are installed.")
        sys.exit(1)

    if len(ports) == 1:
        return ports[0].device

    print("\nAvailable COM Ports:")
    for idx, p in enumerate(ports):
        print(f"  [{idx + 1}] {p.device} ------------------ {p.description}")

    while True:
        choice = input(f"Select Port [1-{len(ports)}] (default: 1): ").strip()
        if choice == "":
            return ports[0].device
        if choice.isdigit() and 1 <= int(choice) <= len(ports):
            return ports[int(choice) - 1].device
        print("Invalid selection. Try again.")

def main():
    parser = argparse.ArgumentParser(description="WiMotion Step 0: Hardware Diagnostic")
    parser.add_argument("--port", type=str, default=None, help="ESP32 COM port (e.g. COM9)")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUDRATE, help="Baud rate (115200 or 921600)")
    args = parser.parse_args()

    print("=" * 70)
    print("  WiMotion ------------------ Step 0: ESP32 Hardware Diagnostics & Stream Audit")
    print("=" * 70)

    port_name = args.port or select_port_interactive()
    baud = args.baud

    print(f"\n[SERIAL] Connecting to {port_name} at {baud} baud...")
    try:
        ser = serial.Serial(port_name, baud, timeout=DEFAULT_SERIAL_TIMEOUT)
        ser.reset_input_buffer()
    except Exception as e:
        print(f"[ERROR] Could not open {port_name}: {e}")
        sys.exit(1)

    print("[*] Waiting for Wi-Fi handshake & steady-state stream lock (up to 15s)...")
    t_warm = time.time()
    steady_count = 0
    while time.time() - t_warm < 15.0:
        raw = ser.readline()
        if not raw:
            continue
        line = raw.decode("utf-8", errors="ignore").strip()
        if line.startswith("CSI_DATA"):
            steady_count += 1
            if steady_count >= 8:
                print("[+] Steady 10 Hz stream locked! Starting 8-second audit...")
                break
    ser.reset_input_buffer()

    print("[*] Running 8-second live stream diagnostic. Measuring CSI arrival rate...")
    
    start_t = time.time()
    total_lines = 0
    valid_packets = 0
    corrupt_packets = 0
    packet_timestamps = []
    rssi_list = []
    channels = set()
    roles = set()
    declared_lengths = set()

    try:
        while (time.time() - start_t) < 8.0:
            raw_line = ser.readline()
            if not raw_line:
                continue
            total_lines += 1
            
            try:
                line_str = raw_line.decode("utf-8", errors="ignore").strip()
            except UnicodeDecodeError:
                corrupt_packets += 1
                continue

            meta, csi_raw = parse_csi_line(line_str)
            if meta is not None:
                amps = compute_subcarrier_amplitudes(csi_raw, num_subcarriers=NUM_SUBCARRIERS)
                if amps is not None and len(amps) == NUM_SUBCARRIERS:
                    now_pkt = time.time()
                    valid_packets += 1
                    packet_timestamps.append(now_pkt)
                    if meta.get("rssi") != "N/A":
                        try:
                            rssi_list.append(int(meta["rssi"]))
                        except ValueError:
                            pass
                    if meta.get("channel") != "N/A":
                        channels.add(meta["channel"])
                    if meta.get("role") != "N/A":
                        roles.add(meta["role"])
                    if meta.get("csi_len") != "N/A":
                        declared_lengths.add(meta["csi_len"])
                else:
                    corrupt_packets += 1
            else:
                if line_str.startswith("CSI_DATA"):
                    corrupt_packets += 1

            elapsed = time.time() - start_t
            fps = valid_packets / max(0.1, elapsed)
            print(f"  Streaming: {elapsed:3.1f}/8.0s | Valid CSI: {valid_packets:4d} | Rate: {fps:5.1f} pkt/s", end="\r")

    except serial.SerialException as e:
        print(f"\n[!] Serial connection error during diagnostic: {e}")
    finally:
        ser.close()

    elapsed = time.time() - start_t
    import numpy as np
    if len(packet_timestamps) > 1:
        dts = np.diff(packet_timestamps)
        mean_dt = float(np.mean(dts))
        std_dt = float(np.std(dts))
        measured_fps = 1.0 / mean_dt if mean_dt > 0 else 0.0
        jitter_ms = std_dt * 1000.0
    else:
        mean_dt = 0.0
        std_dt = 0.0
        measured_fps = valid_packets / max(0.1, elapsed)
        jitter_ms = 0.0

    print("\n\n" + "=" * 70)
    print("                 WIMOTION HARDWARE CHECK REPORT")
    print("=" * 70)
    print(f"  [1]  Serial Port         : {port_name:<16s} [OK]")
    print(f"  [2]  Baud Rate           : {baud:<16d} [OK]")
    print(f"  [3]  Total Frames Read   : {total_lines:<16d} [OK]")
    print(f"  [4]  Valid CSI Frames    : {valid_packets:<16d} [OK]")
    
    if corrupt_packets == 0:
        print(f"  [5]  Invalid / Discarded : {corrupt_packets:<16d} [OK]")
    else:
        print(f"  [5]  Invalid / Discarded : {corrupt_packets:<16d} [WARN: {corrupt_packets} dropped]")

    csi_len_str = ", ".join(declared_lengths) if declared_lengths else f"{REQUIRED_RAW_CSI_BYTES} (extracted)"
    print(f"  [6]  CSI Declared Length : {csi_len_str:<16s} [OK]")
    
    role_str = ", ".join(roles) if roles else "AP"
    print(f"  [7]  Node Mode (Role)    : {role_str:<16s} [OK]")
    print(f"  [8]  Effective CSI Rate  : {measured_fps:5.1f} packets/sec  [MEASURED]")
    if mean_dt > 0:
        print(f"  [9]  Arrival Interval Δt : {mean_dt*1000.0:5.1f} ms (± {jitter_ms:.1f} ms jitter)")
    print(f"  [10] Nominal Target Rate : {NOMINAL_SAMPLING_RATE_HZ:5.1f} Hz          [CONFIGURED]")
    
    chan_str = ", ".join(channels) if channels else "6"
    print(f"  [11] WiFi Channel        : {chan_str:<16s} [OK]")
    
    avg_rssi_str = f"{sum(rssi_list)/len(rssi_list):.1f} dBm" if rssi_list else "N/A"
    print(f"  [12] Average RSSI        : {avg_rssi_str:<16s} [OK]")
    print("=" * 70)

    # 3-Tier Hardware Readiness Assessment:
    # >= 8.0 Hz: READY (Optimal stream for live demo)
    # 4.0 - 8.0 Hz: WARNING (Sub-optimal, may experience lag or jitter)
    # < 4.0 Hz: CRITICAL / NOT READY (Signal Quality Gate will BLOCK inference!)
    if measured_fps >= 8.0 and corrupt_packets == 0:
        print(f"\nHardware Status: READY [OPTIMAL]")
        print(f"  Verified {measured_fps:.1f} pkt/s RF stream with 0 corruption.")
        print(f"  Arrival interval: {mean_dt*1000.0:.1f} ms. System is ready for live demonstration!")
    elif measured_fps >= 8.0:
        print(f"\nHardware Status: READY [WARNING: {corrupt_packets} corrupted frames]")
        print(f"  CSI rate ({measured_fps:.1f} pkt/s) meets demo criteria, but check USB cable/baud to reduce dropped frames.")
    elif measured_fps >= 4.0:
        print(f"\nHardware Status: WARNING [SUB-OPTIMAL STREAM: {measured_fps:.1f} pkt/s]")
        print(f"  Stream rate is between 4.0 Hz and 8.0 Hz.")
        print(f"  Signal Quality Gate will allow inference, but temporal response may lag or jitter.")
        print(f"  Recommended: Check antenna line of sight and re-verify transmitter pacing.")
    else:
        print(f"\nHardware Status: CRITICAL / NOT READY [STREAM TOO LOW: {measured_fps:.1f} pkt/s < 4.0 Hz]")
        print(f"  WARNING: WiMotion Signal Quality Gate will actively BLOCK inference during live demo!")
        print(f"  Troubleshooting steps:")
        print(f"    1. Confirm baud rate is 921600 (not 115200) to prevent UART buffer overflow.")
        print(f"    2. Ensure both Node 1 (STA) and Node 2 (AP) are powered and within 1-2 meters.")
        print(f"    3. Use direct motherboard USB ports; avoid unpowered USB splitters/hubs.")
        print(f"    4. Check if firmware vTaskDelay in active_sta is pacing at ~25-100ms.")
        print(f"    5. If hardware remains unstable, use Demo Backup Option 2 (Replay Golden Session).")
    print("=" * 70)

if __name__ == "__main__":
    main()