# ==============================================================================
# WiMotion v2.4 — Research-Grade HTTP + WebSocket Observatory Server
# (Dynamic Port Resolution + Live Serial Worker + REST Control + Real TARE)
# ==============================================================================
import warnings
warnings.filterwarnings('ignore')
import argparse
import asyncio
import json
import pickle
import threading
import time
import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
import pandas as pd

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

try:
    from websockets.asyncio.server import serve
except ImportError:
    from websockets import serve

ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = ROOT / "dashboard"
DATA_DIR = ROOT / "data"
LOGS_DIR = ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)
MODEL_FILE = ROOT / "models" / "wimotion_model.pkl"

import sys
sys.path.insert(0, str(ROOT))
from src.config import (
    DEFAULT_BAUDRATE, DEFAULT_SERIAL_TIMEOUT, NUM_SUBCARRIERS,
    WINDOW_DURATION_SEC, PREDICTION_INTERVAL_SEC, MIN_WINDOW_FRAMES,
    TARGET_RESAMPLE_FS, FEATURE_COUNT, FEATURE_ENGINE_VERSION,
    SENSING_ZONE_RADIUS_M, WEBSOCKET_HOST, WEBSOCKET_PORT,
    HTTP_HOST, HTTP_PORT, DISPLAY_LABELS, ACTIVE_SUBCARRIERS,
    CALIBRATION_DIR, CLASSES
)
from src.csi_parser import parse_csi_line, compute_subcarrier_amplitudes
from src.presence_engine import PresenceEngine
from src.feature_engine import extract_features

ACTIVITY_MODEL_FILE = ROOT / "models" / "activity_model.pkl"
activity_model_bundle = None
_enable_activity = False

def init_activity_model():
    global activity_model_bundle
    if _enable_activity and ACTIVITY_MODEL_FILE.exists():
        try:
            with open(ACTIVITY_MODEL_FILE, "rb") as f:
                activity_model_bundle = pickle.load(f)
            print(f"[*] Stage 2 Activity Recognizer loaded: {len(activity_model_bundle['classes'])} classes")
        except Exception as e:
            print(f"[!] Warning: Could not load activity model: {e}")
            activity_model_bundle = None
    else:
        activity_model_bundle = None
        if not _enable_activity:
            print("[*] Stage 2 Activity Recognition: DISABLED (pass --enable-activity-experimental to activate).")

log_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
flight_log_file = LOGS_DIR / f"decision_log_{log_timestamp}.csv"
flight_log_file.write_text(
    "timestamp,host_time,raw_probability,presence_score,confidence,state,csi_rate_hz,rssi_dbm,coherence,spatial_pos,signal_quality\n",
    encoding="utf-8"
)

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer, int)):
            return int(obj)
        elif isinstance(obj, (np.floating, float)):
            return float(obj)
        elif isinstance(obj, (np.bool_, bool)):
            return bool(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

class SharedState:
    def __init__(self):
        self.lock = threading.Lock()
        self.mode = "REPLAY"
        self.session = "golden_demo_presence.csv"
        self.port = "COM8"
        self.baudrate = DEFAULT_BAUDRATE
        self.speed = 1.0
        self.http_port = HTTP_PORT
        self.ws_port = WEBSOCKET_PORT
        self.speed = 1.0
        self.session_changed = False
        self.host = HTTP_HOST
        self.seq = 0
        self.telemetry = {
            "timestamp": time.time(),
            "presence": False,
            "state": "SENSING ZONE CLEAR",
            "presence_score": 0.0,
            "confidence": 0.90,
            "csi_rate_hz": 20.0,
            "rssi_dbm": -58.0,
            "coherence": 0.0,
            "field_intensity": 0.0,
            "peak_frequency_hz": 0.0,
            "raw_presence_probability": 0.0,
            "amplitudes": [10.0] * NUM_SUBCARRIERS,
            "mode": "REPLAY",
            "session": "golden_demo_presence.csv",
            "spatial_position": "CENTER",
            "spatial_position_type": "COARSE_HEURISTIC_ZONE",
            "signal_quality": "NORMAL",
            "calibrated": True,
            "activity": "ZONE CLEAR",
            "activity_confidence": 0.0
        }

    def reset_telemetry(self):
        self.telemetry.update({
            "presence": False,
            "state": "SENSING ZONE CLEAR",
            "presence_score": 0.0,
            "confidence": 0.90,
            "raw_presence_probability": 0.0,
            "coherence": 0.0,
            "spatial_position": "CENTER",
            "peak_frequency_hz": 0.0,
            "field_intensity": 0.0,
            "signal_quality": "NORMAL",
            "activity": "ZONE CLEAR",
            "activity_confidence": 0.0
        })

state = SharedState()
clients = set()

# These flags are set by main_async() before engine is used.
# Default: heuristic NOT allowed, TARE disabled (60.87% FPR when enabled).
_allow_heuristic = False
_enable_tare = False

def _create_engine():
    """Create the PresenceEngine with the current CLI flags."""
    global engine
    try:
        engine = PresenceEngine(
            auto_load_persisted_tare=_enable_tare,
            allow_heuristic=_allow_heuristic
        )
    except RuntimeError as e:
        print(f"[!] FATAL: {e}")
        print(f"[!] Server cannot start without a valid model.")
        print(f"[!] Options:")
        print(f"    1. Install correct dependencies: pip install -r requirements-lock.txt")
        print(f"    2. Train a model: python scripts/2_train_hardware_model.py")
        print(f"    3. Run with --allow-heuristic flag (lower accuracy)")
        raise SystemExit(1)

engine = None  # Initialized in main_async

def log_flight_decision(t_now, host_t, p_raw, p_score, conf, state_str, rate, rssi, coh, pos, qual):
    try:
        line = f"{t_now:.3f},{host_t:.3f},{p_raw:.4f},{p_score:.4f},{conf:.4f},{state_str},{rate:.1f},{rssi:.1f},{coh:.4f},{pos},{qual}\n"
        with open(flight_log_file, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass

class ObservatoryHTTPHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/config":
            with state.lock:
                cfg = {
                    "http_port": state.http_port,
                    "ws_port": state.ws_port,
                    "host": state.host,
                    "mode": state.mode,
                    "session": state.session,
                    "port": state.port,
                    "speed": state.speed,
                    "enable_tare": _enable_tare,
                    "enable_activity_experimental": _enable_activity
                }
            self._json_response(cfg)
        elif path == "/api/sessions":
            # Search both root DATA_DIR and subdirectories (genuine, questionable_archive)
            session_files = sorted(list(set(
                f.name for f in DATA_DIR.rglob("*.csv") if "OLD_DATA" not in f.parts
            )))
            self._json_response({"sessions": session_files})
        elif path == "/api/calibrate/report":
            if engine.latest_calibration_report is not None:
                self._json_response(engine.latest_calibration_report)
            else:
                self._json_response({
                    "status": "NOT CALIBRATED",
                    "calibrated": False,
                    "noise_floor_dbm": None,
                    "stability": "NONE",
                    "stability_score_pct": 0.0,
                    "valid_samples": 0,
                    "message": "No live TARE calibration performed. Baseline is currently uncalibrated."
                })
        elif path == "/api/state":
            with state.lock:
                self._json_response(state.telemetry)
        else:
            rel = "index.html" if path in ("/", "") else path.lstrip("/")
            file_path = DASHBOARD_DIR / rel
            if file_path.exists() and file_path.is_file():
                ct = "text/html"
                if rel.endswith(".js"): ct = "application/javascript"
                elif rel.endswith(".css"): ct = "text/css"
                elif rel.endswith(".json"): ct = "application/json"
                content = file_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", ct)
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_error(404, "File Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"

        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            payload = {}

        if path == "/api/control":
            with state.lock:
                if "mode" in payload:
                    new_mode = str(payload["mode"]).upper()
                    if new_mode != state.mode:
                        state.mode = new_mode
                        engine.live_baseline = None
                        engine.is_custom_calibrated = False
                        engine.latest_calibration_report = None
                if "session" in payload:
                    new_session = str(payload["session"])
                    if new_session != state.session:
                        state.session = new_session
                        # Isolation: Reset TARE baseline so previous session baseline does not bleed into new session
                        engine.live_baseline = None
                        engine.is_custom_calibrated = False
                        engine.latest_calibration_report = None
                if "port" in payload:
                    state.port = str(payload["port"])
                if "baudrate" in payload:
                    state.baudrate = int(payload["baudrate"])
                if "speed" in payload:
                    state.speed = float(payload["speed"])
                state.session_changed = True
                state.telemetry["mode"] = state.mode
                state.telemetry["session"] = state.session
                state.reset_telemetry()

            engine.reset()
            self._json_response({"success": True, "mode": state.mode, "session": state.session, "speed": state.speed, "port": state.port})

        elif path == "/api/calibrate/tare":
            if not _enable_tare:
                self._json_response({
                    "success": False,
                    "reason": "TARE calibration is disabled by default due to a known 60.87% false positive rate. Pass --enable-tare on the server CLI to unlock."
                }, status=403)
                return

            # Step 15 Bug Fix #2: Quality Gate strictly requires genuine empty room baseline
            with state.lock:
                cur_mode = state.mode
                cur_session = state.session

            if cur_mode == "REPLAY" and "empty" not in cur_session.lower():
                self._json_response({
                    "success": False,
                    "reason": f"TARE calibration rejected: active replay session '{cur_session}' contains human activity. TARE baseline must be calibrated against an explicit empty room baseline."
                }, status=400)
                return

            if cur_mode == "LIVE" and engine.last.get("presence", False):
                self._json_response({
                    "success": False,
                    "reason": "TARE calibration rejected: active human presence detected in live sensing field. Room must be completely clear to tare."
                }, status=400)
                return

            recent_frames = []
            recent_rssi = []

            if len(engine.frame_buffer) >= 10:
                recent_frames = list(engine.frame_buffer)
                recent_rssi = list(engine.rssi_buffer)
            else:
                # Fallback: strictly find genuine empty room baseline
                cand_file = None
                for cand in ["empty_room.csv", "empty_room_real_01.csv", "empty_room_session_02.csv"]:
                    p = DATA_DIR / cand
                    if p.exists():
                        cand_file = p
                        break
                    p_gen = DATA_DIR / "genuine" / cand
                    if p_gen.exists():
                        cand_file = p_gen
                        break
                if cand_file is not None:
                    df = pd.read_csv(cand_file)
                    amp_cols = [f"amp_{i}" for i in range(NUM_SUBCARRIERS)]
                    recent_frames = df[amp_cols].iloc[:100].values
                    recent_rssi = df["rssi"].iloc[:100].values if "rssi" in df.columns else [-58.0]*100

            if len(recent_frames) > 0:
                report = engine.calibrate_live_baseline(recent_frames, rssi_list=recent_rssi)
                # Persist TARE baseline calibration record
                tare_record_file = CALIBRATION_DIR / "current_tare.json"
                tare_record = {
                    "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "report": report,
                    "baseline_mean": engine.live_baseline.tolist() if engine.live_baseline is not None else []
                }
                tare_record_file.write_text(json.dumps(tare_record, indent=2), encoding="utf-8")
                with state.lock:
                    state.telemetry["calibrated"] = True
                self._json_response({"success": True, "report": report})
            else:
                self._json_response({"success": False, "reason": "No frames available for TARE calibration"}, status=400)

        elif path == "/api/reset":
            engine.reset()
            self._json_response({"success": True})
        else:
            self.send_error(404, "Endpoint Not Found")

    def _json_response(self, data, status=200):
        content = json.dumps(data, cls=NumpyEncoder).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

def replay_worker():
    while True:
        if state.mode != "REPLAY":
            time.sleep(0.2)
            continue

        with state.lock:
            current_session = state.session if state.session else "golden_demo_presence.csv"
            state.session_changed = False

        engine.reset()

        csv_file = DATA_DIR / current_session
        if not csv_file.exists():
            csv_file = DATA_DIR / "genuine" / current_session
        if not csv_file.exists():
            csv_file = DATA_DIR / "questionable_archive" / current_session
        if not csv_file.exists():
            # Check recursive search
            found = list(DATA_DIR.rglob(current_session))
            if found:
                csv_file = found[0]

        if not csv_file.exists():
            time.sleep(0.5)
            continue

        try:
            df = pd.read_csv(csv_file)
            amp_cols = [f"amp_{i}" for i in range(NUM_SUBCARRIERS)]
            amps = df[amp_cols].values
            ts = df["host_timestamp"].values if "host_timestamp" in df.columns else np.arange(len(df)) * 0.05
            rssi = df["rssi"].values if "rssi" in df.columns else np.full(len(df), -60.0)

            for i in range(len(df)):
                with state.lock:
                    if state.mode != "REPLAY" or state.session_changed or state.session != current_session:
                        break

                t_frame = ts[i]
                res = engine.process_frame(amps[i], timestamp=t_frame, rssi=rssi[i])
                if res is not None:
                    act_label = "ZONE CLEAR" if _enable_activity else None
                    act_conf = 0.0
                    if _enable_activity and res.get("state") == "HUMAN PRESENT" and activity_model_bundle is not None:
                        try:
                            if len(engine.frame_buffer) >= 15:
                                cur_win = np.array(engine.frame_buffer)
                                cur_ts = np.array(engine.ts_buffer)
                                f_vec = extract_features(cur_win, timestamps=cur_ts).reshape(1, -1)
                                a_clf = activity_model_bundle["model"]
                                a_classes = activity_model_bundle["classes"]
                                a_idx = int(a_clf.predict(f_vec)[0])
                                a_probs = a_clf.predict_proba(f_vec)[0]
                                act_label = str(a_classes[a_idx]).upper()
                                act_conf = float(a_probs[a_idx])
                        except Exception:
                            act_label = "UNKNOWN"
                            act_conf = 0.0

                    with state.lock:
                        state.telemetry.update(res)
                        state.telemetry["amplitudes"] = amps[i].tolist()
                        state.telemetry["mode"] = "REPLAY"
                        state.telemetry["session"] = csv_file.name
                        state.telemetry["activity"] = act_label
                        state.telemetry["activity_confidence"] = act_conf

                    log_flight_decision(
                        time.time(), t_frame,
                        res.get("raw_presence_probability", 0.0),
                        res.get("presence_score", 0.0),
                        res.get("confidence", 0.88),
                        res.get("state", "SENSING ZONE CLEAR"),
                        res.get("csi_rate_hz", 20.0),
                        res.get("rssi_dbm", -60.0),
                        res.get("coherence", 0.0),
                        res.get("spatial_position", "CENTER"),
                        res.get("signal_quality", "NORMAL")
                    )

                time.sleep(max(0.005, 0.05 / max(0.25, state.speed)))
        except Exception as e:
            time.sleep(1.0)

def live_serial_worker():
    """
    Problem #4: Genuine LIVE SERIAL worker for ESP32 CSI streaming over USB UART.
    """
    ser = None
    while True:
        if state.mode != "LIVE":
            if ser is not None:
                try: ser.close()
                except Exception: pass
                ser = None
            time.sleep(0.2)
            continue

        if not SERIAL_AVAILABLE:
            with state.lock:
                state.telemetry["state"] = "PYSERIAL NOT INSTALLED"
            time.sleep(1.0)
            continue

        port_name = state.port
        baud = state.baudrate

        try:
            if ser is None or not ser.is_open:
                with state.lock:
                    state.telemetry["state"] = f"CONNECTING {port_name}..."
                ser = serial.Serial(port_name, baud, timeout=DEFAULT_SERIAL_TIMEOUT)
                ser.reset_input_buffer()
                with state.lock:
                    state.telemetry["state"] = "STREAM LOCKED"

            raw_line = ser.readline()
            if not raw_line:
                continue

            line_str = raw_line.decode("utf-8", errors="ignore").strip()
            if not line_str.startswith("CSI_DATA"):
                continue

            meta, csi_raw = parse_csi_line(line_str)
            if meta is not None:
                first_word_val = int(meta.get("first_word", "0"))
                amps = compute_subcarrier_amplitudes(csi_raw, num_subcarriers=NUM_SUBCARRIERS, first_word=first_word_val)
                if amps is not None and len(amps) == NUM_SUBCARRIERS:
                    t_frame = time.time()
                    try:
                        rssi_val = float(meta.get("rssi", -60.0))
                    except ValueError:
                        rssi_val = -60.0

                    res = engine.process_frame(np.array(amps), timestamp=t_frame, rssi=rssi_val)
                    if res is not None:
                        act_label = "ZONE CLEAR" if _enable_activity else None
                        act_conf = 0.0
                        if _enable_activity and res.get("state") == "HUMAN PRESENT" and activity_model_bundle is not None:
                            try:
                                if len(engine.frame_buffer) >= 15:
                                    cur_win = np.array(engine.frame_buffer)
                                    cur_ts = np.array(engine.ts_buffer)
                                    f_vec = extract_features(cur_win, timestamps=cur_ts).reshape(1, -1)
                                    a_clf = activity_model_bundle["model"]
                                    a_classes = activity_model_bundle["classes"]
                                    a_idx = int(a_clf.predict(f_vec)[0])
                                    a_probs = a_clf.predict_proba(f_vec)[0]
                                    act_label = str(a_classes[a_idx]).upper()
                                    act_conf = float(a_probs[a_idx])
                            except Exception:
                                act_label = "UNKNOWN"
                                act_conf = 0.0

                        with state.lock:
                            state.telemetry.update(res)
                            state.telemetry["amplitudes"] = amps
                            state.telemetry["mode"] = "LIVE"
                            state.telemetry["session"] = f"LIVE ({port_name} @ {baud})"
                            state.telemetry["activity"] = act_label
                            state.telemetry["activity_confidence"] = act_conf

                        log_flight_decision(
                            time.time(), t_frame,
                            res.get("raw_presence_probability", 0.0),
                            res.get("presence_score", 0.0),
                            res.get("confidence", 0.88),
                            res.get("state", "SENSING ZONE CLEAR"),
                            res.get("csi_rate_hz", 20.0),
                            rssi_val,
                            res.get("coherence", 0.0),
                            res.get("spatial_position", "CENTER"),
                            res.get("signal_quality", "NORMAL")
                        )
        except Exception as e:
            if ser is not None:
                try: ser.close()
                except Exception: pass
                ser = None
            with state.lock:
                state.telemetry["state"] = f"SERIAL ERROR: {e}"
            time.sleep(1.0)

clients = set()

async def ws_handler(websocket):
    clients.add(websocket)
    try:
        while True:
            with state.lock:
                data = dict(state.telemetry)
            await websocket.send(json.dumps(data, cls=NumpyEncoder))
            await asyncio.sleep(0.05)
    except Exception as e:
        print(f"[WS] Client disconnected/error: {e}", flush=True)
    finally:
        clients.discard(websocket)

async def main_async(args):
    global _allow_heuristic, _enable_tare, _enable_activity
    _allow_heuristic = args.allow_heuristic
    _enable_tare = args.enable_tare
    _enable_activity = args.enable_activity_experimental

    # Create the engine with the resolved flags
    _create_engine()
    init_activity_model()

    if _enable_tare:
        print("[!] WARNING: TARE auto-load ENABLED. Known issue: 60.87% false positive rate.")
    if _allow_heuristic and (engine is None or engine.model is None):
        print("[!] WARNING: Running in HEURISTIC mode. Accuracy is lower than trained ML model.")

    state.http_port = args.http_port
    state.ws_port = args.ws_port
    state.host = args.host
    state.mode = args.mode.upper()
    state.session = args.session
    state.port = args.port
    state.baudrate = args.baud
    state.speed = args.speed

    # Start Workers
    t_replay = threading.Thread(target=replay_worker, daemon=True)
    t_replay.start()

    t_live = threading.Thread(target=live_serial_worker, daemon=True)
    t_live.start()

    httpd = ThreadingHTTPServer((args.host, args.http_port), ObservatoryHTTPHandler)
    http_t = threading.Thread(target=httpd.serve_forever, daemon=True)
    http_t.start()
    print(f"[*] HTTP Observatory: http://{args.host}:{args.http_port}")
    print(f"[*] WebSocket Stream: ws://{args.host}:{args.ws_port}")
    print(f"[*] Initial Mode:     {state.mode} | Session: {state.session} | Serial Port: {state.port}")

    async with serve(ws_handler, args.host, args.ws_port):
        await asyncio.Future()

def main():
    parser = argparse.ArgumentParser(description="WiMotion v2.4 3D Sensing Observatory Server")
    parser.add_argument("--http-port", type=int, default=HTTP_PORT, help="HTTP Server Port")
    parser.add_argument("--ws-port", type=int, default=WEBSOCKET_PORT, help="WebSocket Stream Port")
    parser.add_argument("--host", type=str, default=HTTP_HOST, help="Host Address")
    parser.add_argument("--mode", type=str, default="REPLAY", choices=["REPLAY", "LIVE", "replay", "live"], help="Execution Mode")
    parser.add_argument("--session", type=str, default="walking.csv", help="Replay CSV Session")
    parser.add_argument("--port", type=str, default="COM8", help="Serial COM Port for Live Stream")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUDRATE, help="Baud rate for Serial Stream")
    parser.add_argument("--speed", type=float, default=1.0, help="Replay playback speed factor (e.g. 1.0, 2.0)")
    parser.add_argument("--allow-heuristic", action="store_true",
                        help="Allow physics-based heuristic fallback if ML model cannot load")
    parser.add_argument("--enable-tare", action="store_true",
                        help="Enable TARE auto-load (WARNING: known 60.87%% FPR issue)")
    parser.add_argument("--enable-activity-experimental", action="store_true",
                        help="Enable experimental Stage-2 activity classification (14.49%% transfer accuracy)")
    args = parser.parse_args()

    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        print("\nServer shutdown cleanly.")

if __name__ == "__main__":
    main()
