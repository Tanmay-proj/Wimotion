# WiMotion v2.4 — Contactless Human Presence & Motion Detection

WiMotion is a research prototype for **contactless binary human-presence and motion detection** using ESP32 Wi-Fi Channel State Information (CSI). The system uses one ESP32 transmitter and one ESP32-WROOM CSI receiver inside a controlled ~1.5 m sensing zone in a **single calibrated room**.

## Current Capabilities (Controlled Prototype)

- **Binary presence detection**: `EMPTY ROOM` vs `HUMAN PRESENT` (motion-based in single calibrated room).
- Continuous 0–1 presence probability score with temporal smoothing.
- 20 Hz uniform resampling of 64-subcarrier CSI amplitudes.
- Empty-room reference calibration stored with the trained model.
- Cross-subcarrier SVD coherence telemetry.
- Live serial inference at 921600 baud from ESP32.
- Replay of recorded CSI sessions for hardware-free demonstrations.
- Local HTTP + WebSocket telemetry server.
- Three.js 3D Observatory with visual spatial representation.

## Scientific Boundary

> **The 3D field in the dashboard is a visualization of estimated human-presence probability. It is NOT a rendering of electromagnetic radiation and does NOT claim exact (x, y, z) human localization from a single Wi-Fi link.** Accurate 3D localization would require multiple spatially distributed sensing links or antenna arrays (Angle-of-Arrival).

## Known Limitations

| Area | Status | Detail |
|------|--------|--------|
| Binary presence (motion) | 🟡 Baseline Benchmark | 70.58% session-wise accuracy (31.4% FPR) — honest baseline benchmark, not yet validated operational performance |
| Activity recognition | ⚠️ Disabled by default | 14.49% cross-room transfer — essentially chance for 7 classes. Gated behind `--enable-activity-experimental` |
| 3D localization | ❌ Not feasible | Single Wi-Fi link provides insufficient spatial information |
| Fall detection | ❌ Not validated | No safety-critical claims |
| Cross-room generalization | ❌ Not tested | CSI is highly environment-specific |
| TARE live calibration | ⚠️ Disabled by default | Increases false positives from 15% to 61%. Gated behind `--enable-tare` |

## What This Project Does NOT Claim

- Exact 3D human position tracking
- Reliable fall detection or safety monitoring
- Seven-class activity recognition in arbitrary rooms
- Generalization to unseen rooms, people, or hardware configurations
- Any safety-critical or security monitoring capability

## Honest Metrics

| Metric | Value | Source |
|--------|-------|--------|
| In-Fold Session-Grouped Accuracy | **70.58%** (F1: 71.88%) | `models/presence_model_scorecard.json` |
| Session-wise GroupKFold accuracy | 70.30% (FPR: 31.44%) | `models/session_wise_evaluation_scorecard.json` |
| LOSO mean accuracy | 68.5% (σ=22.1%) | `models/loso_scorecard.json` |
| Research holdout accuracy | 92.8% (⚠️ STALE — holdout file missing from archive) | `models/research_scorecard.json` |
| TARE false positive rate | 60.87% | `models/tare_ab_results.json` |

## Live Demonstration Guide (5-Minute Walkthrough)

For live evaluation, technical presentations, or live jury reviews:

1. **Launch Menu**: Run `run_wimotion.bat` (or execute `py -3.10 wimotion_main.py`).
2. **Step 1 — Rigor & Verification (Option 4)**:
   - Select `4` (Run Full Test Suite).
   - Validates all 25 unit tests (`Ran 25 tests in ~7s ... OK`). Verifies feature extractors, SVD coherence, signal quality gates, and model integrity without warnings.
3. **Step 2 — Interactive 3D Observatory (Option 5)**:
   - Select `5` (Launch 3D Observatory).
   - Server boots with status ticker and automatically opens `http://127.0.0.1:8000` (100% offline-ready via local Three.js vendor bundle).
4. **Step 3 — Interactive Walkthrough**:
   - In the left sidebar, choose a session (`walking.csv` or `room_1_session_1.csv`) and click **"START / APPLY SOURCE"**.
   - Observe real-time 64-subcarrier CSI disturbance, presence probability gauge, and 3D wave disturbance dynamics.
   - Switch between **⚡ DEMO MODE** (high-contrast operator gauges) and **🔬 RESEARCH MODE** (SVD coherence matrix, subcarrier dispersion, raw phase diagnostics).

## Quick Start

```powershell
# Use Python 3.10 (models trained with scikit-learn 1.7.2 on Python 3.10)
pip install -r requirements-lock.txt
python scripts\2_train_hardware_model.py
python server\wimotion_server.py --mode replay --session walking.csv --speed 2
```

Open `http://localhost:8000` in a browser. The dashboard switches between replay sessions and live serial mode.

For live serial:

```powershell
python server\wimotion_server.py --mode live --port COM8
```

## Reproducibility

- **Python version**: 3.10 (required for model compatibility)
- **Dependencies**: Pinned in `requirements-lock.txt`
- **Model manifest**: `models/model_manifest.json` documents training provenance

## Project Structure

- `src/` — CSI parsing, feature engine, temporal filter, presence inference.
- `scripts/` — diagnostics, collection, training, CLI inference.
- `server/` — local HTTP/WebSocket telemetry service.
- `dashboard/` — WiMotion 3D Observatory frontend (visual-only spatial representation).
- `models/` — deployment model, scorecards, and manifest.
- `data/` — partitioned into `train/`, `validation/`, `test/`, `calibration/`.
- `tests/` — automated pipeline and integrity checks.
- `firmware/` — ESP32 flashing guide and hardware compatibility documentation.

## Attribution

The 3D Observatory is inspired by/adapts selected open-source visualization concepts from RuView. See `THIRD_PARTY_LICENSES.md`.
