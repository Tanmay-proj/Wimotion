# ==============================================================================
# WiMotion Script 12: Two-Stage Hierarchical Sensing & Transfer Evaluator
# (Stage 1 Presence Gate + Stage 2 Activity Head Unseen Evaluation)
# ==============================================================================
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import argparse
import json
import pickle
import time
import numpy as np
import pandas as pd
from collections import Counter
from sklearn.metrics import accuracy_score, f1_score, confusion_matrix, classification_report

from src.config import NUM_SUBCARRIERS, FEATURE_COUNT
from src.feature_engine import extract_features

DATA_DIR = ROOT / "data"
MODELS_DIR = ROOT / "models"
PRESENCE_MODEL_FILE = MODELS_DIR / "presence_model.pkl"
ACTIVITY_MODEL_FILE = MODELS_DIR / "activity_model.pkl"
REPORT_FILE = MODELS_DIR / "hierarchical_transfer_evaluation.json"

def evaluate_pipeline(unseen_empty_count: int = 2, unseen_walking_count: int = 2):
    print("=" * 76)
    print("  WiMotion Research Pipeline: Two-Stage Hierarchical Transfer Evaluation")
    print("=" * 76)

    # 1. Load Models
    if not PRESENCE_MODEL_FILE.exists():
        print(f"[-] Stage 1 Presence Model not found at {PRESENCE_MODEL_FILE}. Run Script 10 first!")
        return
    if not ACTIVITY_MODEL_FILE.exists():
        print(f"[-] Stage 2 Activity Model not found at {ACTIVITY_MODEL_FILE}. Run Script 11 first!")
        return

    with open(PRESENCE_MODEL_FILE, "rb") as f:
        p_bundle = pickle.load(f)
    p_model = p_bundle["model"]
    p_classes = p_bundle["classes"]

    with open(ACTIVITY_MODEL_FILE, "rb") as f:
        a_bundle = pickle.load(f)
    a_model = a_bundle["model"]
    a_classes = a_bundle["classes"]

    print(f"[+] Loaded Stage 1 Presence Gate: {p_model.__class__.__name__} ({p_classes})")
    print(f"[+] Loaded Stage 2 Activity Head : {a_model.__class__.__name__} ({len(a_classes)} classes: {a_classes})")

    # 2. Select unseen physical holdout sessions
    empty_csvs = sorted(list(DATA_DIR.glob("empty_room*.csv")))
    walking_csvs = sorted(list(DATA_DIR.glob("walking*.csv")))

    # Pick last sessions as unseen test holdout
    test_empty = empty_csvs[-unseen_empty_count:]
    test_walking = walking_csvs[-unseen_walking_count:]

    print(f"\n[*] Unseen Physical Test Sessions:")
    print(f"    Empty Room Test Holdouts: {[f.name for f in test_empty]}")
    print(f"    Walking Test Holdouts   : {[f.name for f in test_walking]}")

    def get_session_windows(csv_path: Path, window_size: int = 25, step_size: int = 15):
        df = pd.read_csv(csv_path)
        amp_cols = [f"amp_{i}" for i in range(NUM_SUBCARRIERS)]
        amps = df[amp_cols].values
        ts = df["host_timestamp"].values if "host_timestamp" in df.columns else np.arange(len(df)) * 0.05

        windows = []
        n_frames = len(df)
        for start_idx in range(0, n_frames - window_size + 1, step_size):
            win = amps[start_idx : start_idx + window_size]
            win_ts = ts[start_idx : start_idx + window_size]
            feats = extract_features(win, timestamps=win_ts)
            if feats.shape[0] == FEATURE_COUNT and np.all(np.isfinite(feats)):
                windows.append(feats)
        return np.array(windows, dtype=np.float32)

    # 3. Test Empty Room Sessions (Ground Truth: NO HUMAN)
    empty_windows = []
    for f in test_empty:
        w = get_session_windows(f)
        if len(w) > 0:
            empty_windows.append(w)
    X_empty = np.vstack(empty_windows)

    # Stage 1 evaluation on Empty Room
    p_empty_pred = p_model.predict(X_empty)
    # 0 = empty_room, 1 = human_present
    empty_correct = np.sum(p_empty_pred == 0)
    empty_acc = empty_correct / len(p_empty_pred)
    false_alarm_rate = np.sum(p_empty_pred == 1) / len(p_empty_pred)

    print(f"\n--- [1] EMPTY ROOM HOLDOUT EVALUATION ({len(X_empty)} windows) ---")
    print(f"    True Negative Rate (Clear Zone Accuracy): {empty_acc*100:.2f}%")
    print(f"    False Alarm Rate (False Presence)       : {false_alarm_rate*100:.2f}%")

    # 4. Test Walking Sessions (Ground Truth: HUMAN PRESENT + WALKING)
    walk_windows = []
    for f in test_walking:
        w = get_session_windows(f)
        if len(w) > 0:
            walk_windows.append(w)
    X_walk = np.vstack(walk_windows)

    # Stage 1 evaluation on Walking
    p_walk_pred = p_model.predict(X_walk)
    p_walk_probs = p_model.predict_proba(X_walk)
    walk_detected = np.sum(p_walk_pred == 1)
    walk_detection_rate = walk_detected / len(p_walk_pred)

    print(f"\n--- [2] HUMAN WALKING HOLDOUT EVALUATION ({len(X_walk)} windows) ---")
    print(f"    Stage 1 True Positive Rate (Human Detection): {walk_detection_rate*100:.2f}%")

    # Stage 2 Hierarchical Gate:
    # Activity Head is ONLY triggered when Stage 1 confirms Presence!
    activity_preds_triggered = []
    activity_probs_triggered = []
    active_mask = (p_walk_pred == 1)

    if np.any(active_mask):
        X_active = X_walk[active_mask]
        a_pred_indices = a_model.predict(X_active)
        a_probs = a_model.predict_proba(X_active)

        for idx in a_pred_indices:
            activity_preds_triggered.append(a_classes[idx])

        counts = Counter(activity_preds_triggered)
        print(f"\n--- [3] STAGE 2 HIERARCHICAL ACTIVITY RECOGNITION (On Confirmed Presence) ---")
        print(f"    Gated Windows Evaluated: {len(activity_preds_triggered)} / {len(X_walk)}")
        print(f"    Predicted Activity Distribution:")
        for act, cnt in counts.most_common():
            pct = cnt / len(activity_preds_triggered) * 100
            flag = " [CORRECT ACTIVITY]" if act == "walking" else ""
            print(f"      - {act:12s}: {cnt:3d} windows ({pct:5.1f}%){flag}")

        walking_recall = counts.get("walking", 0) / len(activity_preds_triggered)
        print(f"\n    Physical Walking Recognition Precision: {walking_recall*100:.2f}%")
    else:
        print("[-] Stage 1 did not trigger presence for walking frames.")
        walking_recall = 0.0

    # Overall Metrics
    y_true_binary = np.concatenate([np.zeros(len(X_empty)), np.ones(len(X_walk))])
    y_pred_binary = np.concatenate([p_empty_pred, p_walk_pred])
    overall_binary_acc = accuracy_score(y_true_binary, y_pred_binary)
    overall_binary_f1 = f1_score(y_true_binary, y_pred_binary)

    print("\n" + "=" * 76)
    print(f" OVERALL HIERARCHICAL PERFORMANCE SUMMARY (UNSEEN PHYSICAL HOLDOUTS)")
    print("=" * 76)
    print(f"  Stage 1 Overall Binary Accuracy  : {overall_binary_acc*100:.2f}%")
    print(f"  Stage 1 Binary Presence F1-Score : {overall_binary_f1*100:.2f}%")
    print(f"  Stage 1 False Alarm Rate         : {false_alarm_rate*100:.2f}%")
    print(f"  Stage 2 Walking Recognition Rate : {walking_recall*100:.2f}%")
    print("=" * 76)

    # Save comprehensive JSON report
    report = {
        "evaluation_timestamp": time.time(),
        "unseen_empty_sessions": [f.name for f in test_empty],
        "unseen_walking_sessions": [f.name for f in test_walking],
        "total_test_windows": int(len(y_true_binary)),
        "empty_test_windows": int(len(X_empty)),
        "walking_test_windows": int(len(X_walk)),
        "stage1_metrics": {
            "binary_accuracy_pct": round(float(overall_binary_acc * 100), 2),
            "binary_f1_pct": round(float(overall_binary_f1 * 100), 2),
            "true_positive_rate_pct": round(float(walk_detection_rate * 100), 2),
            "false_alarm_rate_pct": round(float(false_alarm_rate * 100), 2)
        },
        "stage2_metrics": {
            "gated_windows": int(len(activity_preds_triggered)),
            "walking_recognition_pct": round(float(walking_recall * 100), 2),
            "activity_distribution": dict(counts) if np.any(active_mask) else {}
        }
    }
    REPORT_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n[+] Comprehensive scorecard saved to: {REPORT_FILE.relative_to(ROOT)}")

def main():
    parser = argparse.ArgumentParser(description="WiMotion Script 12: Hierarchical Transfer Evaluator")
    parser.add_argument("--unseen-empty", type=int, default=2, help="Number of unseen empty sessions to hold out")
    parser.add_argument("--unseen-walking", type=int, default=2, help="Number of unseen walking sessions to hold out")
    args = parser.parse_args()

    evaluate_pipeline(unseen_empty_count=args.unseen_empty, unseen_walking_count=args.unseen_walking)

if __name__ == "__main__":
    main()
