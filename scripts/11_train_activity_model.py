# ==============================================================================
# WiMotion Script 11: Multi-Class Activity Recognition Model Trainer
# (Stage 2: Micro-Movement Classification across 7 Physical Activities)
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
from collections import Counter
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.metrics import classification_report, accuracy_score, f1_score, confusion_matrix
from sklearn.preprocessing import LabelEncoder

DATASETS_DIR = ROOT / "datasets"
PROCESSED_DIR = DATASETS_DIR / "processed"
MODELS_DIR = ROOT / "models"
MODELS_DIR.mkdir(exist_ok=True)

INPUT_CACHE = PROCESSED_DIR / "activity_features_public.npz"
MODEL_FILE = MODELS_DIR / "activity_model.pkl"
SCORECARD_FILE = MODELS_DIR / "activity_model_scorecard.json"

def train_activity_model(n_iter: int = 150):
    if not INPUT_CACHE.exists():
        print(f"[-] Feature matrix not found at {INPUT_CACHE}. Run Script 9 first!")
        return

    print("=" * 76)
    print("      WiMotion Stage 2: Public Multi-Class Activity Model Training")
    print("=" * 76)

    print(f"[*] Loading feature cache: {INPUT_CACHE.name}...")
    data = np.load(INPUT_CACHE)
    X = data["X"]
    y_act = data["y_act"]

    print(f"    Total Samples: {X.shape[0]} windows | Features: {X.shape[1]}")
    counts = Counter(y_act)
    print("    Class Distribution:")
    for act, c in counts.most_common():
        print(f"      - {act:12s}: {c} samples ({c/len(y_act)*100:.1f}%)")

    # Encode activity labels
    le = LabelEncoder()
    y = le.fit_transform(y_act)
    classes = list(le.classes_)

    # Stratified Train/Test Split (80% train, 20% test)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    print(f"\n[*] Dataset split: {len(X_train)} train windows | {len(X_test)} test windows")

    # Train HistGradientBoostingClassifier
    print(f"[*] Training HistGradientBoostingClassifier (max_iter={n_iter})...")
    t0 = time.time()
    clf = HistGradientBoostingClassifier(
        max_iter=n_iter,
        learning_rate=0.08,
        max_leaf_nodes=31,
        min_samples_leaf=20,
        l2_regularization=0.1,
        random_state=42
    )
    clf.fit(X_train, y_train)
    train_time = time.time() - t0
    print(f"[+] Training completed in {train_time:.2f} seconds.")

    # Evaluate on holdout test split
    y_pred = clf.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    macro_f1 = f1_score(y_test, y_pred, average="macro")

    print("\n" + "=" * 76)
    print(f" Holdout Test Accuracy: {acc*100:.2f}% | Macro F1-Score: {macro_f1*100:.2f}%")
    print("=" * 76)

    rep_dict = classification_report(y_test, y_pred, target_names=classes, output_dict=True)
    rep_text = classification_report(y_test, y_pred, target_names=classes, digits=3)
    print("\nClassification Report:")
    print(rep_text)

    cm = confusion_matrix(y_test, y_pred).tolist()

    # Save model artifact bundle
    bundle = {
        "model": clf,
        "classes": classes,
        "label_encoder": le,
        "feature_count": X.shape[1],
        "created_timestamp": time.time()
    }
    with open(MODEL_FILE, "wb") as f:
        pickle.dump(bundle, f)
    print(f"\n[+] Activity Model saved to: {MODEL_FILE.relative_to(ROOT)}")

    # Save scorecard
    scorecard = {
        "model_type": "HistGradientBoostingClassifier",
        "stage": "Stage-2 Multi-Class Activity Recognizer",
        "total_windows": int(X.shape[0]),
        "train_windows": int(len(X_train)),
        "test_windows": int(len(X_test)),
        "test_accuracy_pct": round(float(acc * 100), 2),
        "macro_f1_pct": round(float(macro_f1 * 100), 2),
        "classes": classes,
        "classification_report": rep_dict,
        "confusion_matrix": cm,
        "training_duration_sec": round(train_time, 2)
    }
    SCORECARD_FILE.write_text(json.dumps(scorecard, indent=2), encoding="utf-8")
    print(f"[+] Scorecard written to: {SCORECARD_FILE.relative_to(ROOT)}")

def main():
    parser = argparse.ArgumentParser(description="WiMotion Script 11: Activity Model Trainer")
    parser.add_argument("--iter", type=int, default=150, help="Max boosting iterations (default 150)")
    args = parser.parse_args()

    train_activity_model(n_iter=args.iter)

if __name__ == "__main__":
    main()
