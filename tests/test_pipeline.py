# ==============================================================================
# WiMotion: Comprehensive Unit Test Suite (14 Verification Tests - v2.4)
# ==============================================================================
import unittest
import unittest.mock
import collections
import sys
import json
import pickle
import subprocess
import threading
import urllib.request
import urllib.error
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import (
    NUM_SUBCARRIERS, FEATURE_COUNT, PEAK_FREQ_FEATURE_INDEX,
    NOMINAL_SAMPLING_RATE_HZ, TARGET_RESAMPLE_FS, WINDOW_DURATION_SEC,
    MIN_WINDOW_FRAMES, FEATURE_ENGINE_VERSION, MODEL_VERSION, ACTIVE_SUBCARRIERS
)
from src.csi_parser import parse_csi_line, compute_subcarrier_amplitudes
from src.feature_engine import (
    extract_features, estimate_sampling_rate, resample_to_uniform_grid,
    compute_cross_subcarrier_coherence, augment_csi_window
)
from src.temporal_filter import TemporalDecisionFilter
from src.presence_engine import PresenceEngine

class TestWiMotionPipeline(unittest.TestCase):

    # 1. CSI Parsing Tests
    def test_valid_csi_line_128(self):
        fake_csi = " ".join([str(i % 50 - 25) for i in range(128)])
        sample_line = f"CSI_DATA,STA,BC:DD:C2:CC:49:F5,-67,11,0,0,0,0,0,0,0,0,0,-94,0,6,1,99460646,0,110,0,0,99.8496,128,[{fake_csi}]"
        meta, raw = parse_csi_line(sample_line)
        self.assertIsNotNone(meta)
        self.assertEqual(meta["rssi"], "-67")
        self.assertEqual(meta["channel"], "6")
        self.assertEqual(meta["csi_len"], "128")
        self.assertEqual(len(raw), 128)

    def test_valid_csi_line_384(self):
        fake_csi = " ".join([str(i % 50 - 25) for i in range(128)])
        sample_line = f"CSI_DATA,STA,BC:DD:C2:CC:49:F5,-74,11,1,2,1,1,1,0,0,0,0,-94,0,6,1,96218863,0,110,0,0,96.6078,384,[{fake_csi}]"
        meta, raw = parse_csi_line(sample_line)
        self.assertIsNotNone(meta)
        self.assertEqual(meta["rssi"], "-74")
        self.assertEqual(meta["channel"], "6")
        self.assertEqual(meta["csi_len"], "384")
        self.assertEqual(len(raw), 128)

    def test_invalid_csi_line(self):
        self.assertIsNone(parse_csi_line("")[0])
        self.assertIsNone(parse_csi_line("NOT_CSI_DATA")[0])
        short_line = "CSI_DATA,STA,BC:DD:C2:CC:49:F5,-51,11,0,0,0,0,0,0,0,0,0,-98,0,6,1,40617,0,34,0,0,0.444807,10,[1 2 3 4 5]"
        self.assertIsNone(parse_csi_line(short_line)[0])

    def test_metadata_extraction(self):
        fake_csi = " ".join([str(i % 50 - 25) for i in range(128)])
        sample_line = f"CSI_DATA,STA,BC:DD:C2:CC:49:F5,-48,11,0,0,0,0,0,0,0,0,0,-98,0,6,1,40617,0,34,0,0,0.444807,128,[{fake_csi}]"
        meta, raw = parse_csi_line(sample_line)
        self.assertIsNotNone(meta)
        self.assertEqual(meta["rssi"], "-48")
        self.assertEqual(meta["role"], "STA")

    def test_subcarrier_amplitude_extraction(self):
        raw = [3, 4] * 64
        amps = compute_subcarrier_amplitudes(raw, num_subcarriers=64)
        self.assertIsNotNone(amps)
        self.assertEqual(len(amps), 64)
        self.assertTrue(np.allclose(amps, 5.0))

    # 2. Feature Engine & Shape Tests (217 Features)
    def test_feature_count_and_shape(self):
        window = np.random.uniform(5.0, 25.0, (20, 64))
        feats = extract_features(window, fs=NOMINAL_SAMPLING_RATE_HZ)
        self.assertEqual(feats.shape, (FEATURE_COUNT,))
        self.assertEqual(len(feats), 217)
        self.assertFalse(np.isnan(feats).any())
        self.assertFalse(np.isinf(feats).any())

    def test_cross_subcarrier_coherence(self):
        t = np.arange(20)
        base_motion = np.sin(2 * np.pi * 0.1 * t).reshape(-1, 1)
        correlated_amps = np.tile(base_motion, (1, 64)) + np.random.normal(0, 0.05, (20, 64))
        coherence = compute_cross_subcarrier_coherence(correlated_amps)
        self.assertEqual(len(coherence), 3)
        self.assertTrue(coherence[0] > 0.60)

    def test_active_subcarrier_masking(self):
        self.assertEqual(len(ACTIVE_SUBCARRIERS), 52)
        self.assertNotIn(0, ACTIVE_SUBCARRIERS)
        self.assertNotIn(1, ACTIVE_SUBCARRIERS)
        self.assertNotIn(32, ACTIVE_SUBCARRIERS)
        self.assertNotIn(62, ACTIVE_SUBCARRIERS)
        self.assertNotIn(63, ACTIVE_SUBCARRIERS)

    def test_physics_data_augmentation(self):
        window = np.random.uniform(10.0, 30.0, (20, 64))
        aug = augment_csi_window(window)
        self.assertEqual(aug.shape, window.shape)
        self.assertTrue((aug >= 0.0).all())

    # 3. Temporal Decision Filter & Hysteresis
    def test_rolling_median_noise_rejection(self):
        filter_obj = TemporalDecisionFilter()
        for p in [0.05, 0.04, 0.06, 0.85, 0.05]:
            state, score, conf = filter_obj.update("empty_room", 0.85, raw_presence_score=p)
        self.assertEqual(state, "empty_room")
        self.assertTrue(score < 0.25)

    def test_fast_entry_trigger(self):
        filter_obj = TemporalDecisionFilter()
        for p in [0.85, 0.90, 0.88]:
            state, score, conf = filter_obj.update("human_present", 0.88, raw_presence_score=p)
        self.assertEqual(state, "human_present")
        self.assertTrue(score > 0.60)

    def test_hysteresis_exit_smoothing(self):
        filter_obj = TemporalDecisionFilter()
        for _ in range(4):
            filter_obj.update("human_present", 0.90, raw_presence_score=0.90)
        state, score, _ = filter_obj.update("empty_room", 0.70, raw_presence_score=0.10)
        self.assertEqual(state, "human_present")

    # 4. Problem #1 & #2 Tests: Quality Gate Blocking & Live TARE Calibration
    def test_signal_quality_gate_blocks_inference(self):
        engine = PresenceEngine()
        # Feed frames with low RSSI (< -82 dBm)
        frames = np.random.uniform(10.0, 20.0, (15, 64))
        ts = np.arange(15) * 0.05
        res = None
        for i in range(15):
            res = engine.process_frame(frames[i], timestamp=ts[i], rssi=-88.0)
        self.assertIsNotNone(res)
        self.assertEqual(res["signal_quality"], "UNSTABLE")
        self.assertEqual(res["state"], "SIGNAL UNSTABLE")
        self.assertEqual(res["presence"], False)
        self.assertEqual(res["presence_score"], 0.0)

    def test_live_tare_calibration(self):
        engine = PresenceEngine()
        cal_frames = np.full((20, 64), 12.0) + np.random.normal(0, 0.2, (20, 64))
        report = engine.calibrate_live_baseline(cal_frames, rssi_list=[-58.0]*20)
        self.assertEqual(report["status"], "READY FOR DETECTION")
        self.assertEqual(report["active_subcarriers"], 52)
        self.assertEqual(report["stability"], "EXCELLENT")
        self.assertTrue(engine.is_custom_calibrated)
        self.assertIsNotNone(engine.live_baseline)

    # 5. Integrity, Manifest, and Failure Safety Tests (v2.4 Overhaul)
    def test_model_manifest_exists_and_valid(self):
        manifest_path = PROJECT_ROOT / "models" / "model_manifest.json"
        self.assertTrue(manifest_path.exists())
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data.get("feature_count"), 217)
        self.assertEqual(data.get("tare_status"), "DISABLED_BY_DEFAULT")
        self.assertEqual(data.get("scikit_learn_version"), "1.7.2")
        self.assertIn("honest_baseline_accuracy_pct", data)

    def test_model_file_loads_successfully(self):
        from src.config import MODEL_FILE
        self.assertTrue(MODEL_FILE.exists())
        with open(MODEL_FILE, "rb") as f:
            payload = pickle.load(f)
        self.assertIn("model", payload)
        self.assertIn("classes", payload)
        self.assertIn("empty_room_baseline", payload)
        self.assertEqual(len(payload["empty_room_baseline"]), 64)
        self.assertTrue(hasattr(payload["model"], "predict"))

    def test_pipeline_fails_when_holdout_missing(self):
        holdout = PROJECT_ROOT / "data" / "unseen_entry_exit_test.csv"
        if not holdout.exists():
            cmd = [sys.executable, str(PROJECT_ROOT / "scripts" / "run_complete_pipeline.py"), "--skip-train"]
            res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("PIPELINE VERIFICATION INCOMPLETE", res.stdout)

    def test_server_http_endpoint_responds(self):
        from http.server import ThreadingHTTPServer
        from server.wimotion_server import ObservatoryHTTPHandler, _create_engine
        import server.wimotion_server as srv

        if srv.engine is None:
            _create_engine()
        httpd = ThreadingHTTPServer(('127.0.0.1', 0), ObservatoryHTTPHandler)
        port = httpd.server_port
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        try:
            url = f"http://127.0.0.1:{port}/api/config"
            with urllib.request.urlopen(url, timeout=3.0) as resp:
                self.assertEqual(resp.status, 200)
                body = json.loads(resp.read().decode("utf-8"))
                self.assertIn("http_port", body)
                self.assertIn("mode", body)
        finally:
            httpd.shutdown()

    def test_tare_auto_load_defaults_to_disabled(self):
        engine = PresenceEngine()
        self.assertIsNone(engine.live_baseline)
        self.assertFalse(engine.is_custom_calibrated)

    def test_heuristic_mode_requires_explicit_flag(self):
        import io, contextlib
        with unittest.mock.patch("src.presence_engine.pickle.load", side_effect=ValueError("Simulated model corruption")):
            with self.assertRaises(RuntimeError):
                with contextlib.redirect_stdout(io.StringIO()):
                    PresenceEngine(allow_heuristic=False)
            with contextlib.redirect_stdout(io.StringIO()):
                eng = PresenceEngine(allow_heuristic=True)
            self.assertIsNone(eng.model)

    def test_partitions_manifest_and_directories(self):
        manifest_file = PROJECT_ROOT / "data" / "partitions_manifest.json"
        self.assertTrue(manifest_file.exists())
        with open(manifest_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("partitions", data)
        parts = data["partitions"]
        self.assertIn("train", parts)
        self.assertIn("validation", parts)
        self.assertIn("calibration", parts)
        self.assertIn("test", parts)

        # Verify train partition files
        train_files = list((PROJECT_ROOT / "data" / "train").glob("*.csv"))
        self.assertEqual(len(train_files), 10)
        self.assertEqual(len(parts["train"]["sessions"]), 10)

        # Verify validation partition files
        val_files = list((PROJECT_ROOT / "data" / "validation").glob("*.csv"))
        self.assertEqual(len(val_files), 5)
        self.assertEqual(len(parts["validation"]["sessions"]), 5)

        # Verify calibration partition files
        cal_files = list((PROJECT_ROOT / "data" / "calibration").glob("*.csv"))
        self.assertEqual(len(cal_files), 1)

        # Verify test partition is empty (strict physical holdout policy)
        test_files = list((PROJECT_ROOT / "data" / "test").glob("*.csv"))
        self.assertEqual(len(test_files), 0)
        self.assertEqual(len(parts["test"]["sessions"]), 0)

    def test_runtime_manifest_tamper_detection(self):
        with unittest.mock.patch("hashlib.sha256") as mock_sha:
            mock_obj = unittest.mock.MagicMock()
            mock_obj.hexdigest.return_value = "mismatched_sha256_hash_12345"
            mock_sha.return_value = mock_obj
            with self.assertRaises(RuntimeError) as ctx:
                PresenceEngine(allow_heuristic=False)
            self.assertIn("checksum mismatch", str(ctx.exception).lower())

    def test_tare_endpoint_forbidden_when_disabled(self):
        from http.server import ThreadingHTTPServer
        from server.wimotion_server import ObservatoryHTTPHandler, _create_engine
        import server.wimotion_server as srv

        if srv.engine is None:
            _create_engine()
        original_tare = srv._enable_tare
        srv._enable_tare = False
        httpd = ThreadingHTTPServer(('127.0.0.1', 0), ObservatoryHTTPHandler)
        port = httpd.server_port
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        try:
            url = f"http://127.0.0.1:{port}/api/calibrate/tare"
            req = urllib.request.Request(url, data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(req, timeout=3.0)
            self.assertEqual(ctx.exception.code, 403)
            err_body = json.loads(ctx.exception.read().decode("utf-8"))
            self.assertFalse(err_body.get("success"))
            self.assertIn("disabled by default", err_body.get("reason", "").lower())
        finally:
            srv._enable_tare = original_tare
            httpd.shutdown()

    def test_activity_head_disabled_by_default(self):
        import server.wimotion_server as srv
        self.assertFalse(srv._enable_activity)
        self.assertIsNone(srv.activity_model_bundle)

        from http.server import ThreadingHTTPServer
        from server.wimotion_server import ObservatoryHTTPHandler, _create_engine

        if srv.engine is None:
            _create_engine()
        httpd = ThreadingHTTPServer(('127.0.0.1', 0), ObservatoryHTTPHandler)
        port = httpd.server_port
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        try:
            url = f"http://127.0.0.1:{port}/api/config"
            with urllib.request.urlopen(url, timeout=3.0) as resp:
                self.assertEqual(resp.status, 200)
                body = json.loads(resp.read().decode("utf-8"))
                self.assertIn("enable_activity_experimental", body)
                self.assertFalse(body["enable_activity_experimental"])
                self.assertIn("enable_tare", body)
                self.assertFalse(body["enable_tare"])
        finally:
            httpd.shutdown()

    def test_held_out_script_halts_when_test_empty(self):
        script = PROJECT_ROOT / "scripts" / "14_evaluate_held_out_test.py"
        self.assertTrue(script.exists())
        cmd = [sys.executable, str(script)]
        res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
        self.assertEqual(res.returncode, 1)
        self.assertIn("HELD-OUT TEST EVALUATION INCOMPLETE", res.stdout)
        self.assertIn("ZERO TOUCH RULE", res.stdout)

if __name__ == "__main__":
    unittest.main(verbosity=2)

