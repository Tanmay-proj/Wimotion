# ==============================================================================
# WiMotion Script 14: Dedicated Held-Out Test Evaluator (v1.0)
# (STRICT ZERO TOUCH RULE: Reads ONLY from data/test/ post-training)
# ==============================================================================
import sys
import json
import pickle
import hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import (
    DATA_DIR, MODELS_DIR, MODEL_FILE, NUM_SUBCARRIERS,
    WINDOW_DURATION_SEC, WINDOW_STEP_SEC, MIN_WINDOW_FRAMES, TARGET_RESAMPLE_FS
)
from src.feature_engine import extract_features, resample_to_uniform_grid

TEST_DIR = DATA_DIR / "test"
SCORECARD_FILE = MODELS_DIR / "final_test_scorecard.json"
MANIFEST_FILE = MODELS_DIR / "model_manifest.json"


def evaluate_held_out_partition(verbose: bool = True):
    print("=" * 75)
    print("   WIMOTION: DEDICATED HELD-OUT TEST EVALUATOR (ZERO TOUCH RULE)")
    print("=" * 75)

    if not TEST_DIR.exists():
        print(f"\n[!] Target directory '{TEST_DIR}' does not exist.")
        sys.exit(1)

    test_files = sorted(list(TEST_DIR.glob("*.csv")))
    if not test_files:
        print(f"\n[!] HELD-OUT TEST EVALUATION INCOMPLETE: No physical session files found in '{TEST_DIR.name}/'.")
        print("    In accordance with research governance (ZERO TOUCH RULE):")
        print("    - No synthetic or augmented data is ever substituted for final testing.")
        print("    - Final test evaluation cannot be claimed until a physical session is recorded.")
        print("    To complete verification, place an empirical physical recording (e.g. unseen_entry_exit_test.csv)")
        print(f"    into '{TEST_DIR.resolve()}'.")
        print("=" * 75)
        sys.exit(1)

    if not MODEL_FILE.exists():
        print(f"\n[!] Model file '{MODEL_FILE}' not found. Run scripts/2_train_hardware_model.py first.")
        sys.exit(1)

    print(f"[*] Found {len(test_files)} session(s) in dedicated test partition:")
    for tf in test_files:
        print(f"    - {tf.name}")

    # Load and verify model
    with open(MODEL_FILE, "rb") as f:
        payload = pickle.load(f)

    model = payload.get("model")
    empty_baseline = np.asarray(payload.get("empty_room_baseline", []), dtype=float)
    if model is None or empty_baseline.size != NUM_SUBCARRIERS:
        print("[!] Model payload is invalid or missing baseline reference.")
        sys.exit(1)

    all_features = []
    all_gts = []
    all_sessions = []

    for f in test_files:
        df = pd.read_csv(f)
        amp_cols = [f"amp_{i}" for i in range(NUM_SUBCARRIERS)]
        amps = df[amp_cols].astype(float).values
        ts = df["host_timestamp"].values

        # Determine ground truth label
        meta_file = f.parent / f"{f.stem}_metadata.json"
        presence_label = None
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                presence_label = meta.get("presence_label")
            except Exception:
                pass

        if presence_label is None:
            if "empty" in f.name.lower():
                presence_label = 0
            elif "walking" in f.name.lower() or "human" in f.name.lower():
                presence_label = 1
            else:
                presence_label = 1

        label_str = "empty_room" if presence_label == 0 else "human_present"

        start_time, end_time = ts[0], ts[-1]
        curr_time = start_time
        win_count = 0

        while (curr_time + WINDOW_DURATION_SEC) <= end_time:
            win_end_time = curr_time + WINDOW_DURATION_SEC
            mask = (ts >= curr_time) & (ts <= win_end_time)
            win_amps = amps[mask]
            win_ts = ts[mask]

            if len(win_amps) >= MIN_WINDOW_FRAMES:
                resampled = resample_to_uniform_grid(win_amps, win_ts, target_fs=TARGET_RESAMPLE_FS)
                feats = extract_features(
                    resampled, timestamps=None, fs=TARGET_RESAMPLE_FS,
                    baseline_reference=empty_baseline
                )
                all_features.append(feats)
                all_gts.append(label_str)
                all_sessions.append(f.name)
                win_count += 1

            curr_time += WINDOW_STEP_SEC

        print(f"    -> Extracted {win_count} test windows from {f.name} (GT: {label_str})")

    X_test = np.array(all_features)
    y_test = np.array(all_gts)

    preds = model.predict(X_test)
    acc = accuracy_score(y_test, preds)
    prec = precision_score(y_test, preds, pos_label="human_present", zero_division=0)
    rec = recall_score(y_test, preds, pos_label="human_present", zero_division=0)
    f1 = f1_score(y_test, preds, pos_label="human_present", zero_division=0)

    scorecard = {
        "status": "FINAL_TOUCH_FREE_EVALUATION",
        "n_sessions": len(test_files),
        "total_windows": len(X_test),
        "accuracy_pct": round(acc * 100, 2),
        "precision_pct": round(prec * 100, 2),
        "recall_pct": round(rec * 100, 2),
        "f1_pct": round(f1 * 100, 2),
        "sessions_evaluated": [f.name for f in test_files]
    }

    with open(SCORECARD_FILE, "w", encoding="utf-8") as sc_f:
        json.dump(scorecard, sc_f, indent=2)

    print("\n" + "=" * 75)
    print("                 HELD-OUT EVALUATION COMPLETE")
    print(f"  Accuracy:  {scorecard['accuracy_pct']}%")
    print(f"  Precision: {scorecard['precision_pct']}%")
    print(f"  Recall:    {scorecard['recall_pct']}%")
    print(f"  F1 Score:  {scorecard['f1_pct']}%")
    print(f"  Saved:     {SCORECARD_FILE.name}")
    print("=" * 75)


if __name__ == "__main__":
    evaluate_held_out_partition()
