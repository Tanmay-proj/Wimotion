# ==============================================================================
# WiMotion Script 9: Public Dataset Feature Matrix Builder
# (Sliding Window Feature Extraction & Matrix Cache)
# ==============================================================================
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import argparse
import glob
import json
import time
import numpy as np

from src.config import FEATURE_COUNT
from src.public_data.common_format import CSIRecord
from src.public_data.feature_adapter import map_52_to_64_grid, adapt_and_extract_features

DATASETS_DIR = ROOT / "datasets"
PROCESSED_DIR = DATASETS_DIR / "processed"
OUTPUT_CACHE = PROCESSED_DIR / "activity_features_public.npz"

def build_features(window_size: int = 25, step_size: int = 15, max_samples: int = None):
    npz_files = sorted(glob.glob(str(PROCESSED_DIR / "esp_fi" / "*.npz")))
    if not npz_files:
        print("[-] No standardized records found in datasets/processed/esp_fi/. Run Script 8 first!")
        return

    if max_samples and max_samples > 0:
        npz_files = npz_files[:max_samples]

    print(f"[*] Extracting 217-dim features from {len(npz_files)} standardized public trials...")
    print(f"    Window size: {window_size} frames | Step: {step_size} frames")

    X_list = []
    y_act_list = []
    y_pres_list = []
    meta_list = []

    t0 = time.time()
    for idx, npz_path in enumerate(npz_files):
        rec = CSIRecord.load(Path(npz_path))
        if rec.csi_amplitudes is None:
            continue

        csi = rec.csi_amplitudes
        n_frames = csi.shape[0]

        # Extract features across sliding windows
        for start_idx in range(0, n_frames - window_size + 1, step_size):
            win = csi[start_idx : start_idx + window_size]
            feats, status = adapt_and_extract_features(win)
            if status == "SUCCESS" and feats is not None:
                X_list.append(feats)
                y_act_list.append(rec.activity_label)
                y_pres_list.append(rec.presence_label)
                meta_list.append({
                    "dataset": rec.dataset,
                    "sample_id": rec.sample_id,
                    "participant": rec.participant_id,
                    "environment": rec.environment_id,
                    "window_start": start_idx
                })

        if (idx + 1) % 50 == 0 or (idx + 1) == len(npz_files):
            elapsed = time.time() - t0
            print(f"    Processed {idx + 1}/{len(npz_files)} trials | Windows generated: {len(X_list)} ({elapsed:.1f}s)")

    if not X_list:
        print("[-] No valid features extracted.")
        return

    X = np.array(X_list, dtype=np.float32)
    y_act = np.array(y_act_list)
    y_pres = np.array(y_pres_list, dtype=np.int32)

    print(f"\n[+] Feature Matrix Complete:")
    print(f"    Matrix Shape     : {X.shape} (Windows x Features)")
    print(f"    Features per Row : {X.shape[1]} (Expected: {FEATURE_COUNT})")
    print(f"    Unique Activities: {sorted(list(set(y_act)))}")

    # Class balance breakdown
    from collections import Counter
    counts = Counter(y_act)
    for act, c in counts.most_common():
        print(f"      - {act:12s}: {c} windows ({c/len(y_act)*100:.1f}%)")

    np.savez_compressed(
        OUTPUT_CACHE,
        X=X,
        y_act=y_act,
        y_pres=y_pres,
        meta=json.dumps(meta_list)
    )
    print(f"[+] Cached feature matrix saved to: {OUTPUT_CACHE.relative_to(ROOT)} ({OUTPUT_CACHE.stat().st_size / 1e6:.2f} MB)")

def main():
    parser = argparse.ArgumentParser(description="WiMotion Script 9: Public Feature Matrix Builder")
    parser.add_argument("--window", type=int, default=25, help="Window frame length (default 25)")
    parser.add_argument("--step", type=int, default=15, help="Window stride step (default 15)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of trials to process")
    args = parser.parse_args()

    build_features(window_size=args.window, step_size=args.step, max_samples=args.limit)

if __name__ == "__main__":
    main()
