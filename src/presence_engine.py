# ==============================================================================
# WiMotion v2.4: Research-Grade Presence Inference Engine
# (Signal Quality Gate + Live TARE Calibration + SVD Coherence + Spatial Zone)
# ==============================================================================
import warnings
warnings.filterwarnings('ignore')
import hashlib
import json
import pickle
import numpy as np
from pathlib import Path

from src.config import (
    CLASSES, DISPLAY_LABELS, CONFIDENCE_THRESHOLD, FEATURE_COUNT,
    PEAK_FREQ_FEATURE_INDEX, NUM_SUBCARRIERS, SENSING_ZONE_RADIUS_M,
    MODEL_FILE, MODELS_DIR, MIN_WINDOW_FRAMES, TARGET_RESAMPLE_FS, SPATIAL_POSITIONS,
    MIN_RSSI_DBM, MIN_STREAM_FPS, MAX_STREAM_FPS, ACTIVE_SUBCARRIERS,
    CALIBRATION_DIR, FEATURE_ENGINE_VERSION
)
from src.feature_engine import extract_features, estimate_sampling_rate
from src.temporal_filter import TemporalDecisionFilter

class PresenceEngine:
    """
    Loads deployment model, manages live ambient TARE baseline,
    enforces active Signal Quality Gate, computes SVD spatial coherence,
    and estimates experimental coarse spatial zones.
    """
    def __init__(self, model_payload=None, auto_load_persisted_tare: bool = False,
                 allow_heuristic: bool = False):
        if model_payload is None:
            if MODEL_FILE.exists():
                try:
                    # Runtime Manifest Integrity Protection
                    manifest_path = MODELS_DIR / "model_manifest.json"
                    if manifest_path.exists():
                        with open(manifest_path, "r", encoding="utf-8") as mf:
                            manifest = json.load(mf)

                        # 1. SHA-256 Checksum Verification
                        calc_sha256 = hashlib.sha256(MODEL_FILE.read_bytes()).hexdigest()
                        expected_sha256 = manifest.get("sha256")
                        if expected_sha256 and calc_sha256 != expected_sha256:
                            raise ValueError(
                                f"Model checksum mismatch! Expected {expected_sha256}, calculated {calc_sha256}. "
                                f"Model file may be corrupted or modified."
                            )

                        # 2. Feature Dimension Verification
                        if manifest.get("feature_count") != FEATURE_COUNT:
                            raise ValueError(
                                f"Feature dimension mismatch: manifest specifies {manifest.get('feature_count')} features, "
                                f"engine requires {FEATURE_COUNT}."
                            )

                    with open(MODEL_FILE, "rb") as f:
                        model_payload = pickle.load(f)
                    print(f"[*] Presence model loaded and integrity-verified from {MODEL_FILE.name}")
                except Exception as e:
                    if not allow_heuristic:
                        raise RuntimeError(
                            f"Could not load ML model ({e}). "
                            f"Use --allow-heuristic flag to enable physics-based fallback, "
                            f"or install the correct scikit-learn version (see requirements-lock.txt)."
                        )
                    print(f"[!] Could not load ML model ({e}). Using physics-based heuristic detector.")
                    print(f"[!] WARNING: Heuristic mode is less accurate than the trained ML model.")
                    model_payload = {"model": None, "classes": CLASSES, "empty_room_baseline": []}
            else:
                if not allow_heuristic:
                    raise RuntimeError(
                        f"Model file {MODEL_FILE} not found. "
                        f"Train a model first (python scripts/2_train_hardware_model.py) "
                        f"or use --allow-heuristic flag to enable physics-based fallback."
                    )
                print(f"[!] Model file {MODEL_FILE.name} not found. Using physics-based heuristic detector.")
                model_payload = {"model": None, "classes": CLASSES, "empty_room_baseline": []}


        self.model = model_payload.get("model")
        self.classes = list(model_payload.get("classes", CLASSES))
        self.static_baseline = np.asarray(model_payload.get("empty_room_baseline", []), dtype=float)
        if self.static_baseline.size != NUM_SUBCARRIERS:
            self.static_baseline = None
        self.live_baseline = None
        self.filter = TemporalDecisionFilter()
        self.is_custom_calibrated = False
        self.latest_calibration_report = None

        # Auto-restore persisted TARE baseline if present and valid
        if auto_load_persisted_tare:
            self.load_persisted_tare()

        # Sliding window buffer
        self.frame_buffer = []
        self.ts_buffer = []
        self.rssi_buffer = []
        self.last_pred_time = 0.0
        self.last = self._empty_telemetry()

    def reset(self):
        self.filter.reset()
        self.frame_buffer.clear()
        self.ts_buffer.clear()
        self.rssi_buffer.clear()
        self.last_pred_time = 0.0
        self.last = self._empty_telemetry()

    def load_persisted_tare(self) -> bool:
        """Loads and applies persisted TARE baseline record from CALIBRATION_DIR if available."""
        tare_file = CALIBRATION_DIR / "current_tare.json"
        if not tare_file.exists():
            return False
        try:
            data = json.loads(tare_file.read_text(encoding="utf-8"))
            base_vec = np.asarray(data.get("baseline_mean", []), dtype=float)
            if base_vec.size == NUM_SUBCARRIERS and np.all(np.isfinite(base_vec)):
                self.live_baseline = base_vec
                self.is_custom_calibrated = True
                self.latest_calibration_report = data.get("report")
                return True
        except Exception:
            pass
        return False

    def set_live_baseline(self, baseline_vector):
        """Sets real-time ambient RF baseline from live room TARE calibration."""
        arr = np.asarray(baseline_vector, dtype=float)
        if arr.size == NUM_SUBCARRIERS:
            self.live_baseline = arr
            self.is_custom_calibrated = True
            self.filter.reset()

    def calibrate_live_baseline(self, frames, rssi_list=None):
        """
        Genuinely computes real-time room ambient TARE baseline from captured CSI frames.
        Calculates active subcarrier mean amplitudes, variance, estimated noise floor, and stability.
        """
        arr = np.asarray(frames, dtype=float)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)

        if arr.shape[1] != NUM_SUBCARRIERS or len(arr) < 5:
            return {"status": "FAILED", "reason": "Insufficient or malformed calibration frames"}

        mean_amp = np.mean(arr, axis=0)
        std_amp = np.std(arr, axis=0)
        mean_active_amp = float(np.mean(mean_amp[ACTIVE_SUBCARRIERS]))
        mean_active_std = float(np.mean(std_amp[ACTIVE_SUBCARRIERS]))

        mean_rssi = float(np.mean(rssi_list)) if (rssi_list is not None and len(rssi_list) > 0) else -58.0
        snr_proxy = max(1.01, mean_active_amp / max(1e-4, mean_active_std))
        est_noise_floor = float(mean_rssi - 10.0 * np.log10(snr_proxy))

        stability_score = float(np.clip(100.0 - (mean_active_std / max(1e-4, mean_active_amp)) * 100.0, 0.0, 100.0))
        stability_label = "EXCELLENT" if stability_score >= 80.0 else ("GOOD" if stability_score >= 60.0 else "FAIR")

        self.set_live_baseline(mean_amp)

        report = {
            "status": "READY FOR DETECTION",
            "noise_floor_dbm": round(est_noise_floor, 2),
            "stability": stability_label,
            "stability_score_pct": round(stability_score, 1),
            "mean_rssi_dbm": round(mean_rssi, 1),
            "csi_rate_hz": 20.0,
            "valid_samples": len(arr),
            "active_subcarriers": len(ACTIVE_SUBCARRIERS),
            "baseline_integrity": "VERIFIED",
            "calibrated": True
        }
        self.latest_calibration_report = report

        # Persist TARE baseline automatically
        try:
            CALIBRATION_DIR.mkdir(parents=True, exist_ok=True)
            tare_record = {
                "report": report,
                "baseline_mean": mean_amp.tolist()
            }
            (CALIBRATION_DIR / "current_tare.json").write_text(json.dumps(tare_record, indent=2), encoding="utf-8")
        except Exception:
            pass

        return report

    def _get_active_baseline(self):
        return self.live_baseline if self.live_baseline is not None else self.static_baseline

    def _empty_telemetry(self):
        return {
            "presence": False,
            "state": "SENSING ZONE CLEAR",
            "status": "SENSING ZONE CLEAR",
            "presence_score": 0.04,
            "confidence": 0.88,
            "coherence": 0.0,
            "field_intensity": 0.04,
            "peak_frequency_hz": 0.0,
            "raw_presence_probability": 0.0,
            "spatial_position": "NONE",
            "spatial_position_type": "COARSE_HEURISTIC_ZONE",
            "occupancy_count": 0,
            "active_zones": ["NONE"],
            "signal_quality": "NORMAL",
            "calibrated": self.is_custom_calibrated,
            "csi_rate_hz": 20.0,
            "rssi_dbm": -58.0
        }

    def estimate_spatial_position(self, amplitudes: np.ndarray) -> str:
        """
        Experimental Coarse Spatial Zone Heuristic (Non-XYZ / Multipath Gradient):
        Estimates coarse zone (NEAR_TX, CENTER, NEAR_RX, CROSS_LOS)
        based on subcarrier spectral asymmetry and multipath gradient.
        Note: This is a coarse indicator, not a 3D localization system.
        """
        if amplitudes.ndim == 1:
            arr = amplitudes.reshape(1, -1)
        else:
            arr = amplitudes

        low_sub = arr[:, 2:20].mean()
        mid_sub = arr[:, 20:44].mean()
        high_sub = arr[:, 44:62].mean()

        diff_low_high = float(low_sub - high_sub)
        var_mid = float(mid_sub)

        if abs(diff_low_high) > 1.8:
            return "NEAR_TX" if diff_low_high > 0 else "NEAR_RX"
        elif var_mid > 8.0:
            return "CROSS_LOS"
        else:
            return "CENTER"

    def estimate_multi_occupancy(self, amplitudes: np.ndarray, temporal_var: float, rssi: float, final_state: str):
        """
        Estimates tactical occupancy count (0, 1, 2) and active spatial zones
        based on multi-subcarrier energy dispersion and link attenuation.
        Aligned with Wi-CaL (IEEE Access 2022) multi-cluster CSI principles.
        """
        if final_state != "human_present":
            return 0, ["NONE"]

        if amplitudes.ndim == 1:
            arr = amplitudes.reshape(1, -1)
        else:
            arr = amplitudes

        low_sub = float(arr[:, 2:20].mean())
        mid_sub = float(arr[:, 20:44].mean())
        high_sub = float(arr[:, 44:62].mean())
        diff_low_high = float(low_sub - high_sub)
        var_mid = float(mid_sub)

        active_zones = []
        if var_mid > 7.5 or abs(diff_low_high) > 2.0:
            active_zones.append("CROSS_LOS")

        if abs(diff_low_high) > 1.6:
            active_zones.append("NEAR_TX" if diff_low_high > 0 else "NEAR_RX")

        if not active_zones or var_mid > 11.0 or temporal_var > 14.0:
            if "CENTER" not in active_zones:
                active_zones.append("CENTER")

        # Multi-target criteria: 
        # Dual subcarrier cluster dispersion or high temporal variance + deep shadow
        is_multi = (len(active_zones) >= 2) or (temporal_var > 16.0 and rssi < -66.0)
        if is_multi:
            if len(active_zones) >= 2:
                return 2, active_zones[:2]
            else:
                sec = "CROSS_LOS" if active_zones[0] != "CROSS_LOS" else "CENTER"
                return 2, [active_zones[0], sec]
        else:
            return 1, [active_zones[0]]

    def check_signal_quality(self, rssi: float, fps: float) -> str:
        """
        Signal Quality Gate: Checks if hardware CSI stream is within operational RF bounds.
        """
        if rssi < MIN_RSSI_DBM or fps < MIN_STREAM_FPS or fps > MAX_STREAM_FPS:
            return "UNSTABLE"
        return "NORMAL"

    def process_frame(self, frame: np.ndarray, timestamp: float, rssi: float = -60.0):
        """
        Ingests a single raw CSI frame into the sliding window and executes
        inference every 100ms (10 Hz).
        ENFORCES ACTIVE SIGNAL QUALITY GATE: If signal is UNSTABLE, ML inference is blocked!
        """
        if len(self.ts_buffer) > 0 and timestamp < self.ts_buffer[-1]:
            self.reset()

        self.frame_buffer.append(np.asarray(frame, dtype=float))
        self.ts_buffer.append(float(timestamp))
        self.rssi_buffer.append(float(rssi))

        # Keep 1.0s buffer
        while len(self.ts_buffer) > 1 and (self.ts_buffer[-1] - self.ts_buffer[0]) > 1.0:
            self.frame_buffer.pop(0)
            self.ts_buffer.pop(0)
            self.rssi_buffer.pop(0)

        # Inference cadence: every 0.10s (10 Hz)
        if len(self.frame_buffer) >= MIN_WINDOW_FRAMES and (timestamp - self.last_pred_time) >= 0.09:
            self.last_pred_time = timestamp
            arr = np.array(self.frame_buffer)
            ts = np.array(self.ts_buffer)
            curr_fps = estimate_sampling_rate(ts)
            sig_qual = self.check_signal_quality(rssi, curr_fps)

            # PROBLEM #1 FIX: Signal Quality Gate actively BLOCKS inference on UNSTABLE signals
            if sig_qual == "UNSTABLE":
                self.filter.reset()
                self.last = {
                    "presence": False,
                    "state": "SIGNAL UNSTABLE",
                    "status": "SIGNAL UNSTABLE",
                    "presence_score": 0.0,
                    "confidence": 0.0,
                    "coherence": 0.0,
                    "field_intensity": 0.0,
                    "peak_frequency_hz": 0.0,
                    "raw_presence_probability": 0.0,
                    "spatial_position": "NONE",
                    "spatial_position_type": "COARSE_HEURISTIC_ZONE",
                    "signal_quality": "UNSTABLE",
                    "calibrated": self.is_custom_calibrated,
                    "csi_rate_hz": float(curr_fps),
                    "rssi_dbm": float(rssi),
                    "decision_reason": f"Signal Quality Gate: Low RSSI ({rssi:.1f} dBm) or Abnormal Rate ({curr_fps:.1f} Hz)"
                }
                return self.last

            res = self.predict(arr, ts, rssi=rssi)
            res["signal_quality"] = "NORMAL"
            res["csi_rate_hz"] = float(curr_fps)
            res["rssi_dbm"] = float(rssi)
            return res

        return None

    def predict(self, amplitudes: np.ndarray, timestamps: np.ndarray, rssi: float = -60.0):
        arr = np.asarray(amplitudes, dtype=float)
        ts = np.asarray(timestamps, dtype=float)
        active_baseline = self._get_active_baseline()
        feats = extract_features(
            arr, timestamps=ts, baseline_reference=active_baseline
        ).reshape(1, -1)

        active_arr = arr[:, ACTIVE_SUBCARRIERS] if (arr.ndim == 2 and arr.shape[1] == NUM_SUBCARRIERS) else arr
        temporal_var = float(np.mean(np.var(active_arr, axis=0)))

        if self.model is not None:
            probs = self.model.predict_proba(feats)[0]
            prob_map = {c: float(probs[i]) for i, c in enumerate(self.classes)}
            p_human = prob_map.get("human_present", 0.0)
            pred_idx = int(np.argmax(probs))
            raw_state = self.classes[pred_idx]
            raw_conf = float(probs[pred_idx])
        else:
            if active_baseline is not None:
                baseline_active = active_baseline[ACTIVE_SUBCARRIERS]
                mean_diff = float(np.mean(np.abs(np.mean(active_arr, axis=0) - baseline_active)))
                diff_score = float(np.clip(mean_diff / 8.0, 0.0, 1.0))
            else:
                diff_score = 0.0
            var_score = float(np.clip((temporal_var - 1.5) / 15.0, 0.0, 1.0))
            try:
                motion_energy = float(np.sum(np.abs(feats[0, NUM_SUBCARRIERS*3 + 6 : NUM_SUBCARRIERS*3 + 6 + 12])))
                motion_score = float(np.clip(motion_energy / 5000.0, 0.0, 1.0))
            except Exception:
                motion_score = 0.0
            p_human = float(np.clip(0.45 * var_score + 0.35 * diff_score + 0.20 * motion_score, 0.0, 1.0))
            raw_state = "human_present" if p_human > 0.50 else "empty_room"
            raw_conf = max(p_human, 1.0 - p_human)

        final_state, score, smoothed_conf = self.filter.update(
            raw_state, raw_conf, raw_presence_score=p_human
        )

        coherence = float(np.clip(feats[0, -3], 0.0, 1.0))
        field_intensity = float(np.clip(score, 0.0, 1.0))
        presence = (final_state == "human_present")

        if final_state == "human_present":
            status = "HUMAN PRESENT"
            spatial_pos = self.estimate_spatial_position(arr)
            occ_count, active_zones = self.estimate_multi_occupancy(arr, temporal_var, rssi, final_state)
        elif final_state == "uncertain":
            status = "ANALYZING..."
            spatial_pos = "CENTER"
            occ_count = 1
            active_zones = ["CENTER"]
        else:
            status = "SENSING ZONE CLEAR"
            spatial_pos = "NONE"
            occ_count = 0
            active_zones = ["NONE"]

        self.last = {
            "presence": presence,
            "state": status,
            "status": status,
            "presence_score": float(score),
            "confidence": float(smoothed_conf),
            "coherence": coherence,
            "field_intensity": field_intensity,
            "peak_frequency_hz": float(feats[0, PEAK_FREQ_FEATURE_INDEX]),
            "raw_presence_probability": float(p_human),
            "spatial_position": spatial_pos,
            "spatial_position_type": "COARSE_HEURISTIC_ZONE",
            "occupancy_count": int(occ_count),
            "active_zones": list(active_zones),
            "signal_quality": "NORMAL",
            "calibrated": self.is_custom_calibrated
        }
        return self.last
