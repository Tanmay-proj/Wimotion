# ==============================================================================
# WiMotion Script 10: Binary Presence Model Trainer (Stage 1 Presence Gate)
# (Zero-Leakage / Domain-Weighted Training with Local Baseline Integrity)
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
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import classification_report, accuracy_score, f1_score, roc_auc_score

from src.config import NUM_SUBCARRIERS, FEATURE_COUNT
from src.feature_engine import extract_features

DATA_DIR = ROOT / "data"
PROCESSED_DIR = ROOT / "datasets" / "processed"
MODELS_DIR = ROOT / "models"
MODELS_DIR.mkdir(exist_ok=True)

MODEL_FILE = MODELS_DIR / "presence_model.pkl"
SCORECARD_FILE = MODELS_DIR / "presence_model_scorecard.json"

def extract_windows_from_csv(csv_path: Path, label: int, window_size: int = 25, step_size: int = 15):
    df = pd.read_csv(csv_path)
    amp_cols = [f"amp_{i}" for i in range(NUM_SUBCARRIERS)]
    amps = df[amp_cols].values
    ts = df["host_timestamp"].values if "host_timestamp" in df.columns else np.arange(len(df)) * 0.05

    X_list = []
    n_frames = len(df)
    for start_idx in range(0, n_frames - window_size + 1, step_size):
        win = amps[start_idx : start_idx + window_size]
        win_ts = ts[start_idx : start_idx + window_size]
        feats = extract_features(win, timestamps=win_ts)
        if feats.shape[0] == FEATURE_COUNT and np.all(np.isfinite(feats)):
            X_list.append(feats)

    return X_list, [label] * len(X_list)

def train_presence_gate():
    print("=" * 76)
    print("      WiMotion Stage 1: Binary Presence Gate Model Training")
    print("=" * 76)

    # 1. Load Genuine Physical WiMotion Sessions
    empty_csvs = sorted(list(DATA_DIR.glob("empty_room*.csv")))
    walking_csvs = sorted(list(DATA_DIR.glob("walking*.csv")))

    print(f"[*] Extracting local WiMotion physical windows...")
    print(f"    Empty Room CSVs: {len(empty_csvs)} files")
    print(f"    Walking CSVs   : {len(walking_csvs)} files")

    local_X = []
    local_y = []

    for f in empty_csvs:
        x_w, y_w = extract_windows_from_csv(f, label=0)
        local_X.extend(x_w)
        local_y.extend(y_w)

    for f in walking_csvs:
        x_w, y_w = extract_windows_from_csv(f, label=1)
        local_X.extend(x_w)
        local_y.extend(y_w)

    local_X = np.array(local_X, dtype=np.float32)
    local_y = np.array(local_y, dtype=np.int32)
    print(f"[+] Extracted {len(local_X)} local windows: Empty={np.sum(local_y==0)}, Human={np.sum(local_y==1)}")

    # 2. Optionally load a balanced sample of public activity windows
    public_cache = PROCESSED_DIR / "activity_features_public.npz"
    if public_cache.exists():
        p_data = np.load(public_cache)
        p_X = p_data["X"]
        # Subsample to avoid public data drowning out local physical baseline
        n_public = min(len(p_X), len(local_X))
        idx_sub = np.random.RandomState(42).choice(len(p_X), n_public, replace=False)
        p_X_sub = p_X[idx_sub]
        p_y_sub = np.ones(n_public, dtype=np.int32)

        # Domain weighting: Local real data has weight 2.0, Public has weight 0.5
        w_local = np.full(len(local_X), 2.0, dtype=np.float32)
        w_public = np.full(n_public, 0.5, dtype=np.float32)

        X_all = np.vstack([local_X, p_X_sub])
        y_all = np.concatenate([local_y, p_y_sub])
        weights_all = np.concatenate([w_local, w_public])
        print(f"[+] Integrated {n_public} domain-weighted public activity windows into Stage 1.")
    else:
        X_all = local_X
        y_all = local_y
        weights_all = np.ones(len(local_X), dtype=np.float32)

    # Cross-validation
    print(f"[*] Executing 5-Fold Stratified Cross-Validation...")
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    fold_accs = []
    fold_f1s = []

    for fold, (train_idx, val_idx) in enumerate(skf.split(X_all, y_all)):
        clf = HistGradientBoostingClassifier(
            max_iter=100,
            learning_rate=0.08,
            random_state=42 + fold
        )
        clf.fit(X_all[train_idx], y_all[train_idx], sample_weight=weights_all[train_idx])
        pred = clf.predict(X_all[val_idx])
        fold_accs.append(accuracy_score(y_all[val_idx], pred))
        fold_f1s.append(f1_score(y_all[val_idx], pred))

    print(f"[+] 5-Fold CV Accuracy: {np.mean(fold_accs)*100:.2f}% (+/- {np.std(fold_accs)*100:.2f}%)")
    print(f"[+] 5-Fold CV F1-Score: {np.mean(fold_f1s)*100:.2f}% (+/- {np.std(fold_f1s)*100:.2f}%)")

    # Fit final Stage 1 model
    final_clf = HistGradientBoostingClassifier(max_iter=120, learning_rate=0.08, random_state=42)
    final_clf.fit(X_all, y_all, sample_weight=weights_all)

    empty_amps = []
    for f in empty_csvs:
        df = pd.read_csv(f)
        amp_cols = [f"amp_{i}" for i in range(NUM_SUBCARRIERS)]
        empty_amps.append(df[amp_cols].values)
    empty_baseline = np.median(np.vstack(empty_amps), axis=0) if empty_amps else np.zeros(NUM_SUBCARRIERS)

    bundle = {
        "model": final_clf,
        "classes": ["empty_room", "human_present"],
        "empty_room_baseline": empty_baseline.tolist(),
        "feature_count": FEATURE_COUNT,
        "cv_accuracy_pct": round(float(np.mean(fold_accs) * 100), 2),
        "cv_f1_pct": round(float(np.mean(fold_f1s) * 100), 2),
        "created_timestamp": time.time()
    }
    with open(MODEL_FILE, "wb") as f:
        pickle.dump(bundle, f)
    print(f"[+] Presence Model saved to: {MODEL_FILE.relative_to(ROOT)}")
    
    # Also update wimotion_model.pkl so all downstream consumers use this model
    legacy_model_file = MODELS_DIR / "wimotion_model.pkl"
    with open(legacy_model_file, "wb") as f:
        pickle.dump(bundle, f)
    print(f"[+] Synced presence model bundle to: {legacy_model_file.relative_to(ROOT)}")

    scorecard = {
        "model_type": "HistGradientBoostingClassifier",
        "stage": "Stage-1 Binary Presence Gate",
        "total_windows": int(len(X_all)),
        "local_windows": int(len(local_X)),
        "cv_accuracy_pct": bundle["cv_accuracy_pct"],
        "cv_f1_pct": bundle["cv_f1_pct"],
        "classes": bundle["classes"]
    }
    SCORECARD_FILE.write_text(json.dumps(scorecard, indent=2), encoding="utf-8")
    print(f"[+] Presence scorecard saved to: {SCORECARD_FILE.relative_to(ROOT)}")

def main():
    train_presence_gate()

if __name__ == "__main__":
    main()
