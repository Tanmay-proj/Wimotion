# ==============================================================================
# WiMotion: Fast Canonical Leave-One-Session-Out (LOSO) Validation (v2.4)
# (Precomputed In-Memory Windows for High-Speed Cross-Session Evaluation)
# ==============================================================================
import sys
import json
import time
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.metrics import accuracy_score, f1_score, recall_score, precision_score

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import (
    DATA_DIR, MODELS_DIR, WINDOW_DURATION_SEC, WINDOW_STEP_SEC, NUM_SUBCARRIERS,
    TARGET_RESAMPLE_FS, MIN_WINDOW_FRAMES, MAX_WINDOWS_PER_SESSION
)
from src.feature_engine import extract_features, estimate_sampling_rate, augment_csi_window

def load_session_windows(csv_path: Path):
    """Loads CSV and extracts regular and augmented feature matrices once into memory."""
    df = pd.read_csv(csv_path)
    amp_cols = [f"amp_{i}" for i in range(NUM_SUBCARRIERS)]
    timestamps = df["host_timestamp"].values
    amplitudes = df[amp_cols].astype(float).values
    fs = estimate_sampling_rate(timestamps)

    w_frames = max(MIN_WINDOW_FRAMES, int(round(WINDOW_DURATION_SEC * fs)))
    s_frames = max(1, int(round(WINDOW_STEP_SEC * fs)))

    reg_feats = []
    aug_feats = []

    for s in range(0, len(amplitudes) - w_frames + 1, s_frames):
        win_amps = amplitudes[s:s + w_frames]
        win_ts = timestamps[s:s + w_frames]

        f = extract_features(win_amps, timestamps=win_ts, target_fs=TARGET_RESAMPLE_FS)
        reg_feats.append(f)

        # In-fold augmentation pool
        aug_win = augment_csi_window(win_amps, gain_range=0.04, noise_std=0.06)
        aug_f = extract_features(aug_win, timestamps=win_ts, target_fs=TARGET_RESAMPLE_FS)
        aug_feats.append(aug_f)

        if len(reg_feats) >= MAX_WINDOWS_PER_SESSION:
            break

    return np.array(reg_feats), np.array(aug_feats)

def calculate_weights(session_names):
    weights = []
    for s in session_names:
        if s.startswith("site_") or "current_" in s:
            weights.append(3.5)
        elif "standing" in s or "slow" in s:
            weights.append(2.0)
        else:
            weights.append(1.0)
    return np.array(weights, dtype=float)

def run_canonical_loso():
    t_start = time.time()
    print("=" * 75)
    print("  WIMOTION v2.4: FAST CANONICAL LEAVE-ONE-SESSION-OUT (LOSO) VALIDATION")
    print("  (Pre-Sliced Features | In-Fold Augmentation | Rigorous Cross-Session)")
    print("=" * 75)

    empty_files = sorted([f for f in DATA_DIR.glob("empty_room*.csv") if "unseen" not in f.name])
    human_files = sorted([
        f for f in (
            list(DATA_DIR.glob("walking*.csv")) +
            list(DATA_DIR.glob("standing*.csv")) +
            list(DATA_DIR.glob("slow_movement*.csv"))
        ) if "unseen" not in f.name
    ])

    all_files = [(f, 0, "empty") for f in empty_files] + [
        (f, 1, "standing" if "standing" in f.name else ("slow" if "slow" in f.name else "walking"))
        for f in human_files
    ]

    print(f"[*] Pre-extracting feature windows for {len(all_files)} recorded sessions...")
    sessions = []
    for f, label, cls_type in all_files:
        reg, aug = load_session_windows(f)
        if len(reg) > 0:
            sessions.append({
                "name": f.name,
                "stem": f.stem,
                "label": label,
                "type": cls_type,
                "reg_feats": reg,
                "aug_feats": aug
            })

    n_sessions = len(sessions)
    print(f"[OK] Extracted {n_sessions} sessions in {time.time() - t_start:.1f}s. Beginning LOSO Folds...")

    print(f"\n{'Held-out Session':<30}{'Class':<15}{'Windows':<10}{'Accuracy':<10}{'F1-Score':<10}")
    print("-" * 75)

    results = []

    for i in range(n_sessions):
        test_sess = sessions[i]
        train_sessions = [s for j, s in enumerate(sessions) if j != i]

        # Assemble training pool: regular features + in-fold augmentation features
        X_train_parts, y_train_parts, group_train_parts = [], [], []
        for s in train_sessions:
            # Add regular features
            X_train_parts.append(s["reg_feats"])
            y_train_parts.extend([s["label"]] * len(s["reg_feats"]))
            group_train_parts.extend([s["stem"]] * len(s["reg_feats"]))

            # Add augmented features (in-fold only)
            X_train_parts.append(s["aug_feats"])
            y_train_parts.extend([s["label"]] * len(s["aug_feats"]))
            group_train_parts.extend([s["stem"]] * len(s["aug_feats"]))

        X_train = np.vstack(X_train_parts)
        y_train = np.array(y_train_parts)
        train_weights = calculate_weights(group_train_parts)

        # Test set strictly contains unaugmented regular features
        X_test = test_sess["reg_feats"]
        y_test = np.array([test_sess["label"]] * len(X_test))

        clf = ExtraTreesClassifier(n_estimators=100, max_depth=14, random_state=42, class_weight='balanced', n_jobs=-1)
        clf.fit(X_train, y_train, sample_weight=train_weights)

        y_pred = clf.predict(X_test)
        acc = accuracy_score(y_test, y_pred)
        f1 = f1_score(y_test, y_pred, pos_label=test_sess["label"], zero_division=0)

        results.append({
            "session": test_sess["name"],
            "type": test_sess["type"],
            "label": test_sess["label"],
            "windows": len(X_test),
            "accuracy": float(acc),
            "f1": float(f1)
        })

        cls_str = "empty" if test_sess["label"] == 0 else test_sess["type"]
        print(f"{test_sess['name']:<30}{cls_str:<15}{len(X_test):<10}{acc * 100.0:>6.2f}%    {f1 * 100.0:>6.2f}%")

    accs = [r["accuracy"] for r in results]
    mean_acc = float(np.mean(accs))
    std_acc = float(np.std(accs))

    print("-" * 75)
    print(f"Canonical LOSO Mean Accuracy:   {mean_acc * 100.0:6.2f}% (+- {std_acc * 100.0:6.2f}%)")
    print("=" * 75)
    print("\n[SCIENTIFIC CONCLUSION / RESEARCH FINDING]:")
    print(f"  Uncalibrated cross-session accuracy is approximately {mean_acc*100.0:.1f}%.")
    print("  Cross-session generalization remains the primary scientific challenge in Wi-Fi CSI sensing")
    print("  due to environmental multipath variations across sessions.")
    print("=" * 75)

    loso_summary = {
        "mean_loso_accuracy": mean_acc,
        "std_loso_accuracy": std_acc,
        "total_sessions_evaluated": len(results),
        "individual_results": results,
        "status": "COMPLETED"
    }

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    (MODELS_DIR / "loso_scorecard.json").write_text(json.dumps(loso_summary, indent=2), encoding="utf-8")
    print(f"[OK] Canonical LOSO Scorecard saved to: models/loso_scorecard.json ({time.time() - t_start:.1f}s total)")
    return loso_summary

if __name__ == "__main__":
    run_canonical_loso()
