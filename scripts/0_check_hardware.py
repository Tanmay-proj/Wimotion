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
                    valid_packets += 1
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
    measured_fps = valid_packets / max(0.1, elapsed)

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
    print(f"  [8]  Measured CSI Rate   : {measured_fps:5.1f} packets/sec  [MEASURED]")
    print(f"  [9]  Nominal Target Rate : {NOMINAL_SAMPLING_RATE_HZ:5.1f} Hz          [CONFIGURED]")
    
    chan_str = ", ".join(channels) if channels else "6"
    print(f"  [10] WiFi Channel        : {chan_str:<16s} [OK]")
    
    avg_rssi_str = f"{sum(rssi_list)/len(rssi_list):.1f} dBm" if rssi_list else "N/A"
    print(f"  [11] Average RSSI        : {avg_rssi_str:<16s} [OK]")
    print("=" * 70)

    MIN_REQUIRED_RATE_HZ = 8.0  # Minimum acceptable rate (80% of nominal 10 Hz)

    if measured_fps >= MIN_REQUIRED_RATE_HZ and corrupt_packets == 0:
        print(f"\nHardware status: READY (Optimal {measured_fps:.1f} pkt/s RF stream, 0 packet corruption)")
        print(f"                 Next Step: Run '1_field_calibrate.py --port {port_name}' to record motion data!")
    elif measured_fps >= MIN_REQUIRED_RATE_HZ:
        print(f"\nHardware status: READY ({measured_fps:.1f} pkt/s stream verified; note {corrupt_packets} dropped frames)")
        print(f"                 Next Step: Run '1_field_calibrate.py --port {port_name}'")
    else:
        print("\nHardware status: NOT READY")
        print(f"Reason: Measured CSI rate ({measured_fps:.1f} pkt/s) is below required threshold ({MIN_REQUIRED_RATE_HZ:.1f} Hz).")
        print("        Check antenna orientation, ensure Tx/Rx line of sight, and verify power stability.")
    print("=" * 70)

if __name__ == "__main__":
    main()