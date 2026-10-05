# ==============================================================================
# WiMotion: Unified 1-Click Pipeline (v2.4 — Integrity-First)
# (CALIBRATE -> VALIDATE -> TRAIN -> LATENCY TEST -> SCORECARD -> DEPLOY)
# ==============================================================================
import sys
import argparse
import importlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def main():
    parser = argparse.ArgumentParser(description="WiMotion v2.4 1-Click Pipeline Runner")
    parser.add_argument("--skip-train", action="store_true", help="Skip training step")
    args = parser.parse_args()

    print("=" * 75)
    print("        WIMOTION v2.4: 1-CLICK PRODUCTION & RESEARCH PIPELINE")
    print("=" * 75)

    stages_passed = 0
    stages_total = 4
    stage_failures = []

    # Step 1: Calibration Validation (Real empirical measurement check)
    print("\n[STAGE 1/4] Pre-Flight Calibration Validation...")
    from src.config import DATA_DIR, NUM_SUBCARRIERS, ACTIVE_SUBCARRIERS
    import pandas as pd
    import numpy as np
    empty_csvs = list(DATA_DIR.glob("empty_room*.csv"))
    if empty_csvs:
        df_base = pd.read_csv(empty_csvs[0])
        amp_cols = [f"amp_{i}" for i in range(NUM_SUBCARRIERS)]
        mean_amps = df_base[amp_cols].values.mean(axis=0)
        mean_active = float(np.mean(mean_amps[ACTIVE_SUBCARRIERS]))
        mean_rssi = float(df_base["rssi"].mean()) if "rssi" in df_base.columns else -60.0
        print(f"  -> Empirical Baseline Verified ({len(ACTIVE_SUBCARRIERS)} Active Carriers | Mean RSSI: {mean_rssi:.1f} dBm | Active Mean Amp: {mean_active:.1f})")
        stages_passed += 1
    else:
        msg = "No baseline CSV found for pre-flight validation."
        print(f"  -> [FAIL] {msg}")
        stage_failures.append(("Stage 1: Calibration", msg))

    # Step 2: Model Training & Adaptation
    if not args.skip_train:
        print("\n[STAGE 2/4] Training Master Model with Session Balancing & Provenance Metadata...")
        try:
            train_mod = importlib.import_module("scripts.2_train_hardware_model")
            train_mod.main()
            stages_passed += 1
        except Exception as e:
            msg = f"Training failed: {e}"
            print(f"  -> [FAIL] {msg}")
            stage_failures.append(("Stage 2: Training", msg))
    else:
        print("\n[STAGE 2/4] Using pre-trained master model v2.4.")
        from src.config import MODEL_FILE
        if MODEL_FILE.exists():
            stages_passed += 1
        else:
            msg = f"Pre-trained model not found at {MODEL_FILE}"
            print(f"  -> [FAIL] {msg}")
            stage_failures.append(("Stage 2: Model Check", msg))

    # Step 3: Latency & Hysteresis Automated Benchmarking
    print("\n[STAGE 3/4] Running Sub-Second Latency Benchmarking on Unseen Holdout...")
    holdout_file = DATA_DIR / "unseen_entry_exit_test.csv"
    if not holdout_file.exists():
        print(f"  -> [FAIL] Holdout file '{holdout_file.name}' not found.")
        stage_failures.append(("Stage 3: Latency Benchmark", f"Missing {holdout_file.name}"))
    else:
        try:
            lat_mod = importlib.import_module("scripts.benchmark_latency")
            lat_res = lat_mod.run_latency_benchmark(verbose=True)
            if lat_res.get("passed", False):
                stages_passed += 1
            else:
                msg = "Latency benchmark did not pass"
                print(f"  -> [FAIL] {msg}")
                stage_failures.append(("Stage 3: Latency Benchmark", msg))
        except Exception as e:
            msg = f"Latency benchmark error: {e}"
            print(f"  -> [FAIL] {msg}")
            stage_failures.append(("Stage 3: Latency Benchmark", msg))

    # Step 4: Research Metrics Scorecard
    print("\n[STAGE 4/4] Generating Research Scorecard & False Positive Stress Test...")
    if not holdout_file.exists():
        print(f"  -> [FAIL] Holdout file '{holdout_file.name}' not found.")
        stage_failures.append(("Stage 4: Research Metrics", f"Missing {holdout_file.name}"))
    else:
        try:
            eval_mod = importlib.import_module("scripts.3_evaluate_research_metrics")
            scorecard = eval_mod.evaluate_research_metrics(verbose=True)
            if scorecard and scorecard.get("all_tests_passed", False):
                stages_passed += 1
            else:
                msg = "Research metrics did not pass all tests"
                print(f"  -> [WARN] {msg}")
                stage_failures.append(("Stage 4: Research Metrics", msg))
        except Exception as e:
            msg = f"Research metrics error: {e}"
            print(f"  -> [FAIL] {msg}")
            stage_failures.append(("Stage 4: Research Metrics", msg))

    # Final verdict — NEVER claim COMPLETE unless ALL stages pass
    print("\n" + "=" * 75)
    if stages_passed == stages_total:
        print("                 PIPELINE VERIFICATION COMPLETE")
        print("  All stages passed. Ready for Live Demo and Research Presentation.")
        print("=" * 75)
    else:
        print("            [!] PIPELINE VERIFICATION INCOMPLETE")
        print(f"  {stages_passed}/{stages_total} stages passed.")
        print()
        for stage_name, reason in stage_failures:
            print(f"  [X] {stage_name}: {reason}")
        print()
        print("  DO NOT present this as a verified pipeline.")
        print("  Fix the above failures before claiming verification.")
        print("=" * 75)
        sys.exit(1)

if __name__ == "__main__":
    main()
