# ==============================================================================
# WiMotion v2.4: Master Observatory Execution Console
# ==============================================================================
import argparse
import subprocess
import socket
import webbrowser
import sys
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = BASE_DIR / "scripts"

def run_script(script_name: str, args=None):
    script_path = SCRIPTS_DIR / script_name
    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)
    try:
        subprocess.run(cmd, cwd=str(BASE_DIR))
    except KeyboardInterrupt:
        pass

def _kill_port(port: int):
    """Silently terminate any process listening on the given TCP port."""
    terminate_script = BASE_DIR / "scripts" / "terminate_server.py"
    try:
        subprocess.run(
            [sys.executable, str(terminate_script), str(port)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            cwd=str(BASE_DIR)
        )
    except Exception:
        pass

def find_available_port(default_port: int):
    for p in [default_port, default_port + 88, default_port + 100, default_port + 1000]:
        s = socket.socket()
        try:
            s.bind(('127.0.0.1', p))
            s.close()
            return p
        except Exception:
            s.close()
    return default_port

def main():
    parser = argparse.ArgumentParser(description="WiMotion v2.4 Master Observatory Execution Console")
    parser.add_argument("--clean", action="store_true", help="Force clean shutdown of any existing server instances before launching")
    args = parser.parse_args()

    while True:
        print("\n" + "=" * 70)
        print("  WiMotion v2.4 - Contactless Human Presence & 3D Observatory")
        print("=" * 70)
        print("  [0] Hardware Diagnostics & CSI Rate Measurement (ESP32 Stream Audit)")
        print("  [1] Rigorous 100-Session Hardware Data Recorder (v3.0 - Scientific Protocol)")
        print("  [2] Train Master Human Presence Model (LOSO CV & Augmentation)")
        print("  [3] Launch Real-Time Live Human Presence CLI")
        print("  [4] Run Automated Unit Tests (26 Verification Tests)")
        print("  [5] Launch WiMotion 3D Observatory Dashboard (Live & Replay)")
        print("  [6] Run Complete 1-Click Pipeline (Train -> Latency -> Scorecard)")
        print("  [7] Run Zero-Leakage Session-Wise Evaluation (0% Window Leakage Scorecard)")
        print("  [8] Rapid Site Multi-Pose Quick Calibration (2 Sessions)")
        print("  [9] Exit")
        print("=" * 70)

        try:
            choice = input("Select an option [0-9]: ").strip()
        except KeyboardInterrupt:
            print("\nExiting WiMotion. Goodbye!")
            break

        if choice == "0":
            run_script("0_check_hardware.py")
        elif choice == "1":
            run_script("record_real_sessions.py")
        elif choice == "2":
            run_script("2_train_hardware_model.py")
        elif choice == "3":
            run_script("3_live_motion_detect.py")
        elif choice == "4":
            test_path = BASE_DIR / "tests" / "test_pipeline.py"
            try:
                subprocess.run([sys.executable, str(test_path)], cwd=str(BASE_DIR))
            except KeyboardInterrupt:
                pass
        elif choice == "5":
            server_path = BASE_DIR / "server" / "wimotion_server.py"
            # Fixed ports for a stable dashboard experience
            http_host = "127.0.0.1"
            http_port = 8000
            ws_port = 8765
            # Always clean up any existing server on these ports before launching
            print("[*] Stopping any previous server instances...")
            _kill_port(http_port)
            _kill_port(ws_port)
            import time as _time
            _time.sleep(0.8)  # Brief pause to let OS release the ports
            try:
                subprocess.Popen([
                    sys.executable, str(server_path),
                    "--mode", "REPLAY",
                    "--host", http_host,
                    "--http-port", str(http_port),
                    "--ws-port", str(ws_port),
                    "--enable-activity-experimental"
                ], cwd=str(BASE_DIR))
                # Poll server readiness before opening browser (model loading takes 4-7s)
                print("[*] Initializing WiMotion Observatory server", end="", flush=True)
                import urllib.request
                server_ready = False
                for attempt in range(40):  # Up to 20 seconds (40 x 0.5s)
                    print(".", end="", flush=True)
                    try:
                        req = urllib.request.Request(
                            f"http://{http_host}:{http_port}/",
                            headers={"User-Agent": "WiMotionLauncher/1.0"}
                        )
                        with urllib.request.urlopen(req, timeout=1.0) as resp:
                            if resp.status == 200:
                                server_ready = True
                                break
                    except Exception:
                        _time.sleep(0.5)
                if server_ready:
                    print(" [READY]")
                    _time.sleep(0.5)  # Buffer to allow WebSocket server to bind
                    dashboard_url = f"http://{http_host}:{http_port}"
                    webbrowser.open(dashboard_url)
                    print(f"[+] Observatory launched successfully at {dashboard_url} (WS: {ws_port})")
                else:
                    print("\n[!] Server did not respond in time. Try opening http://{http_host}:{http_port} manually.")
            except Exception as e:
                print(f"[!] Could not launch Observatory: {e}")
        elif choice == "6":
            run_script("run_complete_pipeline.py")
        elif choice == "7":
            run_script("13_session_wise_evaluation.py")
        elif choice == "8":
            run_script("1_field_calibrate.py")
        elif choice == "9":
            print("\nExiting WiMotion. Goodbye!")
            break
        else:
            print("[!] Invalid option. Please choose between 0 and 9.")

if __name__ == "__main__":
    main()
