# ==============================================================================
# WiMotion Script 13: Model Selection & Validation Benchmark (v3.1)
# (Evaluates train/ and validation/ partitions. Final testing is in Script 14)
# ==============================================================================
import sys
import json
import time
import argparse
from pathlib import Path
from collections import Counter

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, ExtraTreesClassifier
from sklearn.model_selection import GroupKFold, GroupShuffleSplit
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import (
    DATA_DIR, MODELS_DIR, WINDOW_DURATION_SEC, WINDOW_STEP_SEC, NUM_SUBCARRIERS,
    TARGET_RESAMPLE_FS, MIN_WINDOW_FRAMES, FEATURE_COUNT
)
from src.feature_engine import extract_features, estimate_sampling_rate

TRAIN_DIR = DATA_DIR / "train"
VAL_DIR = DATA_DIR / "validation"
GENUINE_DIR = DATA_DIR / "genuine"
SCORECARD_FILE = MODELS_DIR / "session_wise_evaluation_scorecard.json"

def load_session_dataset():
    """
    Discovers all physical sessions in data/train and data/validation (or genuine).
    Excludes data/test (reserved strictly for final untouched evaluation in Script 14).
    """
    search_dirs = [TRAIN_DIR, VAL_DIR, GENUINE_DIR]
    seen_names = set()
    session_files = []

    for s_dir in search_dirs:
        if not s_dir.exists():
            continue
        for f in sorted(s_dir.glob("*.csv")):
            if f.name in seen_names or "unseen" in f.name.lower() or "OLD_DATA" in f.parts or "test" in f.parts:
                continue
            seen_names.add(f.name)
            session_files.append(f)

    if not session_files:
        raise FileNotFoundError(f"No CSV sessions found in {TRAIN_DIR} or {VAL_DIR}")

    print(f"[*] Scanning {len(session_files)} potential session files...")

    all_windows = []
    all_labels = []
    all_groups = []
    session_catalog = []

    for f in session_files:
        meta_file = f.parent / f"{f.stem}_metadata.json"
        presence_label = None
        act_name = "unknown"
        pos_name = "NONE"
        is_physical = True

        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                presence_label = meta.get("presence_label")
                act_name = meta.get("activity", meta.get("activity_label", "unknown"))
                pos_name = meta.get("position", "NONE")
                is_physical = meta.get("physical_recording", True)
            except Exception:
                pass

        if presence_label is None:
            # Fallback heuristic based on filename
            fname_lower = f.name.lower()
            if "empty" in fname_lower or "hard_neg" in fname_lower:
                presence_label = 0
                act_name = "empty_room"
            elif any(k in fname_lower for k in ["walking", "standing", "slow", "entry", "human", "dist"]):
                presence_label = 1
                act_name = "human_present"
            else:
                continue

        # Load CSV data
        try:
            df = pd.read_csv(f)
            amp_cols = [c for c in df.columns if c.startswith("amp_")]
            if len(amp_cols) != NUM_SUBCARRIERS:
                continue

            amplitudes = df[amp_cols].astype(float).values
            timestamps = df["host_timestamp"].values if "host_timestamp" in df.columns else np.arange(len(df)) * 0.05
            fs = estimate_sampling_rate(timestamps)

            w_frames = max(MIN_WINDOW_FRAMES, int(round(WINDOW_DURATION_SEC * fs)))
            s_frames = max(1, int(round(WINDOW_STEP_SEC * fs)))

            session_feats = []
            for s in range(0, len(amplitudes) - w_frames + 1, s_frames):
                win_amps = amplitudes[s:s + w_frames]
                win_ts = timestamps[s:s + w_frames]
                feat = extract_features(win_amps, timestamps=win_ts, target_fs=TARGET_RESAMPLE_FS)
                if feat.shape[0] == FEATURE_COUNT and np.all(np.isfinite(feat)):
                    session_feats.append(feat)

            if len(session_feats) >= 5:
                session_id = f.stem
                all_windows.extend(session_feats)
                all_labels.extend([presence_label] * len(session_feats))
                all_groups.extend([session_id] * len(session_feats))

                session_catalog.append({
                    "session_id": session_id,
                    "filename": f.name,
                    "label": presence_label,
                    "activity": act_name,
                    "position": pos_name,
                    "window_count": len(session_feats),
                    "physical": is_physical
                })
        except Exception as e:
            print(f"[!] Warning: Could not process {f.name}: {e}")

    return (
        np.array(all_windows),
        np.array(all_labels, dtype=int),
        np.array(all_groups),
        session_catalog
    )

def evaluate_session_wise(n_splits: int = 5, model_type: str = "HistGradientBoosting"):
    t_start = time.time()
    print("=" * 78)
    print("      WIMOTION v3.0: LEAKAGE-FREE SESSION-WISE EVALUATION (GROUP-CV)")
    print("    (Guaranteed 0% Window Leakage | Strict GroupKFold by Session ID)")
    print("=" * 78)

    X, y, groups, catalog = load_session_dataset()
    unique_sessions = np.unique(groups)
    print(f"\n[+] Loaded Dataset Summary:")
    print(f"    Total Sessions   : {len(unique_sessions)}")
    print(f"    Total Windows    : {len(X)} (Feature Dim: {X.shape[1]})")
    empty_cnt = sum(1 for s in catalog if s["label"] == 0)
    human_cnt = sum(1 for s in catalog if s["label"] == 1)
    print(f"    Session Distribution: {empty_cnt} Empty Room | {human_cnt} Human Present")

    if len(unique_sessions) < 4:
        print("[!] Too few sessions for cross-validation (<4). Record more sessions.")
        return

    # GroupKFold ensures no session appears in both train and test!
    effective_splits = min(n_splits, len(unique_sessions))
    gkf = GroupKFold(n_splits=effective_splits)

    y_true_all = []
    y_pred_all = []
    session_results = {}

    print(f"\n[*] Running {effective_splits}-Fold Zero-Leakage Group Cross-Validation...")

    for fold, (train_idx, test_idx) in enumerate(gkf.split(X, y, groups), 1):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]
        groups_test = groups[test_idx]

        train_sessions = set(groups[train_idx])
        test_sessions = set(groups_test)

        # STRICT ASSERTION: Zero intersection between train sessions and test sessions
        overlap = train_sessions.intersection(test_sessions)
        assert len(overlap) == 0, f"DATA LEAKAGE DETECTED! Overlapping sessions: {overlap}"

        if model_type == "ExtraTrees":
            clf = ExtraTreesClassifier(n_estimators=100, max_depth=12, random_state=42)
        else:
            clf = HistGradientBoostingClassifier(max_iter=100, max_depth=6, random_state=42)

        clf.fit(X_train, y_train)
        preds = clf.predict(X_test)

        y_true_all.extend(y_test)
        y_pred_all.extend(preds)

        fold_acc = accuracy_score(y_test, preds)
        fold_f1 = f1_score(y_test, preds, average="binary", zero_division=0)
        print(f"  Fold {fold:2d}/{effective_splits:2d}: {len(test_sessions):2d} Test Sessions | Acc: {fold_acc*100:5.2f}% | F1: {fold_f1*100:5.2f}%")

        # Record session-level majority vote
        for sess in test_sessions:
            mask = (groups_test == sess)
            sess_preds = preds[mask]
            sess_true = y_test[mask][0]
            majority_pred = 1 if (np.sum(sess_preds == 1) >= (len(sess_preds) / 2.0)) else 0
            session_results[sess] = {
                "ground_truth": int(sess_true),
                "predicted": int(majority_pred),
                "correct": bool(majority_pred == sess_true),
                "window_accuracy": float(accuracy_score(y_test[mask], sess_preds)),
                "window_count": int(np.sum(mask))
            }

    y_true_arr = np.array(y_true_all)
    y_pred_arr = np.array(y_pred_all)

    # Window-level metrics
    acc = float(accuracy_score(y_true_arr, y_pred_arr))
    prec = float(precision_score(y_true_arr, y_pred_arr, zero_division=0))
    rec = float(recall_score(y_true_arr, y_pred_arr, zero_division=0))
    f1 = float(f1_score(y_true_arr, y_pred_arr, zero_division=0))

    cm = confusion_matrix(y_true_arr, y_pred_arr)
    tn, fp, fn, tp = cm.ravel()
    fpr = float(fp / max(1, (fp + tn)))
    fnr = float(fn / max(1, (fn + tp)))
    specificity = float(tn / max(1, (tn + fp)))

    # Session-level metrics (Majority Voting per held-out physical session)
    sess_correct = sum(1 for v in session_results.values() if v["correct"])
    sess_acc = sess_correct / max(1, len(session_results))

    print("\n" + "=" * 78)
    print("      RESEARCH SCORECARD: ZERO-LEAKAGE SESSION-WISE EVALUATION")
    print("=" * 78)
    print(f"  Window Accuracy     : {acc * 100:6.2f}%")
    print(f"  Precision           : {prec * 100:6.2f}%")
    print(f"  Recall (Sensitivity): {rec * 100:6.2f}%")
    print(f"  F1-Score            : {f1 * 100:6.2f}%")
    print(f"  Specificity (TNR)   : {specificity * 100:6.2f}%")
    print(f"  False Positive Rate : {fpr * 100:6.2f}% (Target: < 5.0%)")
    print(f"  False Negative Rate : {fnr * 100:6.2f}%")
    print("-" * 78)
    print(f"  CONFUSION MATRIX (Windows):")
    print(f"               Pred Empty   Pred Human")
    print(f"    Act Empty  : {tn:6d}     {fp:6d}")
    print(f"    Act Human  : {fn:6d}     {tp:6d}")
    print("-" * 78)
    print(f"  SESSION-LEVEL RECOGNITION (Majority Vote across Unseen Sessions):")
    print(f"  -> {sess_correct} / {len(session_results)} Sessions Correctly Classified ({sess_acc * 100:.2f}%)")
    print("=" * 78)

    scorecard = {
        "evaluation_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "methodology": "Leakage-Free GroupKFold Cross-Validation (Partitioned by Session ID)",
        "zero_window_leakage_verified": True,
        "n_sessions": len(unique_sessions),
        "total_windows": len(X),
        "metrics": {
            "window_accuracy_pct": round(acc * 100, 2),
            "precision_pct": round(prec * 100, 2),
            "recall_pct": round(rec * 100, 2),
            "f1_pct": round(f1 * 100, 2),
            "specificity_pct": round(specificity * 100, 2),
            "fpr_pct": round(fpr * 100, 2),
            "fnr_pct": round(fnr * 100, 2),
            "session_level_accuracy_pct": round(sess_acc * 100, 2)
        },
        "confusion_matrix": {
            "true_negatives": int(tn),
            "false_positives": int(fp),
            "false_negatives": int(fn),
            "true_positives": int(tp)
        },
        "session_details": session_results
    }

    SCORECARD_FILE.parent.mkdir(exist_ok=True)
    with open(SCORECARD_FILE, "w", encoding="utf-8") as f:
        json.dump(scorecard, f, indent=2)

    print(f"[+] Detailed scorecard saved to: {SCORECARD_FILE.name}")
    print(f"    Elapsed Time: {time.time() - t_start:.2f}s")
    return scorecard

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WiMotion Zero-Leakage Session-Wise Evaluation")
    parser.add_argument("--folds", type=int, default=5, help="Number of GroupKFold splits")
    parser.add_argument("--model", type=str, default="HistGradientBoosting", choices=["HistGradientBoosting", "ExtraTrees"])
    args = parser.parse_args()

    evaluate_session_wise(n_splits=args.folds, model_type=args.model)
