# ==============================================================================
# WiMotion Script 8: Public Dataset Inspection & Preparation Engine
# (Audit-First / Non-Destructive / Zero-Guesswork Provenance Tracker)
# ==============================================================================
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import argparse
import json
import numpy as np
from typing import Dict, Any, List, Optional

try:
    import scipy.io as sio
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

from src.public_data.common_format import CSIRecord
from src.public_data.label_mapping import (
    map_presence, ESP_FI_ACTIVITY_MAP, TU_WIEN_ACTIVITY_MAP,
    CSI_HAR_ACTIVITY_MAP, UNKNOWN_LABEL
)

DATASETS_DIR = ROOT / "datasets"
PUBLIC_DIR = DATASETS_DIR / "public"
PROCESSED_DIR = DATASETS_DIR / "processed"

def audit_esp_fi(public_path: Path) -> Dict[str, Any]:
    folder = public_path / "esp_fi"
    files = list(folder.glob("**/*.mat")) if folder.exists() else []
    report = {
        "dataset": "ESP-Fi HAR",
        "folder": str(folder.relative_to(ROOT)),
        "file_count": len(files),
        "status": "WAITING FOR DOWNLOAD" if len(files) == 0 else "FILES DETECTED",
        "sample_shape": "N/A",
        "csi_type": "N/A",
        "subcarriers": "N/A",
        "sampling_rate": "Unspecified in raw header (typically normalized)",
        "activities_found": set(),
        "participants_found": set(),
        "notes": "Published 1x950x52 amplitude matrix; requires IEEE 802.11n 52->64 carrier mapping."
    }

    if files and SCIPY_AVAILABLE:
        try:
            sample_file = files[0]
            mat = sio.loadmat(sample_file)
            keys = [k for k in mat.keys() if not k.startswith("__")]
            if keys:
                csi_key = keys[0]
                arr = mat[csi_key]
                report["csi_type"] = f"Key '{csi_key}', dtype={arr.dtype}"
                report["sample_shape"] = list(arr.shape)
                if arr.ndim >= 2:
                    report["subcarriers"] = arr.shape[-1]

            # Parse metadata from filenames: X-Y-Z-M.mat
            for f in files[:200]:
                parts = f.stem.split("-")
                if len(parts) >= 4:
                    try:
                        p_id = parts[1]
                        act_id = int(parts[2])
                        report["participants_found"].add(p_id)
                        if act_id in ESP_FI_ACTIVITY_MAP:
                            report["activities_found"].add(ESP_FI_ACTIVITY_MAP[act_id])
                    except ValueError:
                        pass
            report["activities_found"] = sorted(list(report["activities_found"]))
            report["participants_found"] = len(report["participants_found"])
            report["status"] = "AUDITED & READY FOR ADAPTER"
        except Exception as e:
            report["status"] = f"PARSE ERROR: {e}"

    return report

def audit_tu_wien(public_path: Path) -> Dict[str, Any]:
    folder = public_path / "tu_wien"
    files = list(folder.glob("**/*.*")) if folder.exists() else []
    report = {
        "dataset": "TU Wien ESP32",
        "folder": str(folder.relative_to(ROOT)),
        "file_count": len(files),
        "status": "WAITING FOR DOWNLOAD" if len(files) == 0 else "FILES DETECTED",
        "sample_shape": "N/A",
        "csi_type": "N/A",
        "subcarriers": "N/A",
        "sampling_rate": "100.0 Hz (Published specification)",
        "activities_found": list(TU_WIEN_ACTIVITY_MAP.values()),
        "notes": "Contains DP_LOS/DP_NLOS (Presence) and DA_LOS/DA_NLOS (Activity). Strict rule: no_activity -> UNKNOWN presence."
    }
    return report

def audit_csi_har(public_path: Path) -> Dict[str, Any]:
    folder = public_path / "csi_har"
    files = list(folder.glob("**/*.*")) if folder.exists() else []
    report = {
        "dataset": "CSI-HAR",
        "folder": str(folder.relative_to(ROOT)),
        "file_count": len(files),
        "status": "WAITING FOR DOWNLOAD" if len(files) == 0 else "FILES DETECTED",
        "sample_shape": "N/A",
        "csi_type": "N/A",
        "subcarriers": "N/A",
        "sampling_rate": "Check sample headers",
        "activities_found": list(CSI_HAR_ACTIVITY_MAP.values()),
        "notes": "7 Human activities (sitdown, standup, liedown, run, walk, fall, bend). Zero empty room samples."
    }
    return report

def convert_esp_fi(public_path: Path, processed_path: Path, limit: Optional[int] = None) -> int:
    folder = public_path / "esp_fi"
    files = list(folder.glob("**/*.mat")) if folder.exists() else []
    if not files:
        print("[-] No ESP-Fi .mat files found to convert.")
        return 0

    out_dir = processed_path / "esp_fi"
    out_dir.mkdir(parents=True, exist_ok=True)

    if limit and limit > 0:
        files_to_process = files[:limit]
    else:
        files_to_process = files

    print(f"\n[*] Converting {len(files_to_process)} ESP-Fi trials into {out_dir.relative_to(ROOT)}...")
    converted_count = 0
    for idx, f in enumerate(files_to_process):
        try:
            mat = sio.loadmat(f)
            keys = [k for k in mat.keys() if not k.startswith("__")]
            if not keys:
                continue
            csi = mat[keys[0]]
            if csi.ndim == 3 and csi.shape[0] == 1:
                csi = csi.squeeze(0)  # Convert [1, 950, 52] -> [950, 52]
            elif csi.ndim != 2:
                continue

            act_folder = f.parent.name
            parts = f.stem.split("-")
            scenario_id = parts[0] if len(parts) >= 1 else "unknown"
            participant_id = parts[1] if len(parts) >= 2 else "unknown"

            # Clean activity label
            activity_clean = act_folder.lower()
            if activity_clean in ("run", "running"): activity_clean = "running"
            elif activity_clean in ("walk", "walking"): activity_clean = "walking"

            sample_id = f"espfi_{f.stem}_{activity_clean}"
            rec = CSIRecord(
                dataset="esp_fi",
                sample_id=sample_id,
                activity_label=activity_clean,
                presence_label=1,  # Human present
                num_subcarriers=csi.shape[1],
                original_shape=list(csi.shape),
                source_file=str(f.relative_to(ROOT)),
                participant_id=participant_id,
                environment_id=scenario_id,
                sampling_rate=None,  # Not specified in header, don't fabricate
                csi_amplitudes=csi
            )
            rec.save(out_dir)
            converted_count += 1
            if (idx + 1) % 50 == 0 or (idx + 1) == len(files_to_process):
                print(f"    Processed {idx + 1}/{len(files_to_process)} records...")
        except Exception as e:
            print(f"    [WARN] Failed to process {f.name}: {e}")

    print(f"[+] Successfully standardized and saved {converted_count} ESP-Fi records with full provenance.")
    return converted_count

def run_audit():
    print("=" * 76)
    print("      WiMotion Research Pipeline: Public CSI Dataset Audit Report")
    print("=" * 76)

    reports = [
        audit_esp_fi(PUBLIC_DIR),
        audit_tu_wien(PUBLIC_DIR),
        audit_csi_har(PUBLIC_DIR)
    ]

    for rep in reports:
        print(f"\n[+] Dataset: {rep['dataset']}")
        print(f"    Folder           : {rep['folder']}")
        print(f"    Total Files      : {rep['file_count']}")
        print(f"    Status           : {rep['status']}")
        print(f"    Sample Shape     : {rep['sample_shape']}")
        print(f"    Subcarriers      : {rep['subcarriers']}")
        print(f"    Sampling Rate    : {rep['sampling_rate']}")
        print(f"    Activities       : {rep['activities_found']}")
        print(f"    Technical Notes  : {rep['notes']}")

    print("\n" + "=" * 76)
    any_files = sum(r["file_count"] for r in reports) > 0
    if not any_files:
        print("\n[ACTION REQUIRED]: Public dataset directories are ready but currently empty.")
    else:
        print("\n[READY]: Found files for conversion. Run with --convert to generate standardized records.")
    print("=" * 76)

def main():
    parser = argparse.ArgumentParser(description="WiMotion Script 8: Public Dataset Inspector & Preparer")
    parser.add_argument("--audit", action="store_true", help="Run audit and inspect shapes")
    parser.add_argument("--convert", action="store_true", help="Execute conversion of audited public files into datasets/processed/")
    parser.add_argument("--limit", type=int, default=None, help="Max samples per dataset to convert (default all)")
    args = parser.parse_args()

    run_audit()

    if args.convert:
        convert_esp_fi(PUBLIC_DIR, PROCESSED_DIR, limit=args.limit)

if __name__ == "__main__":
    from typing import Optional
    main()
