# Genuine Physical Wi-Fi CSI Dataset Repository

This directory strictly contains **100% verified physical CSI recordings** collected using the WiMotion ESP32 hardware testbed.

## Provenance Rules
1. **Physical Recording Only**: Every session must be an empirical physical capture with `"physical_recording": true` in its companion metadata JSON.
2. **Companion Metadata**: Every `.csv` file must have an accompanying `_metadata.json` documenting:
   - `session_id`
   - `activity` (raw activity label)
   - `presence_label` (0 = NO_HUMAN, 1 = HUMAN_PRESENT, -1 = UNKNOWN)
   - `position` (NEAR_TX, CENTER, NEAR_RX, CROSS_LOS, NONE)
   - `distance_m`
   - `duration_sec` (60-90s)
   - `channel`, `baud`, `measured_fps`, `environment`
3. **No Overlapping Window Leakage**: During training and evaluation, splits must be done strictly at the **session level** (`session_id`), never across overlapping sliding windows.

## Session Breakdown Target (100 Sessions Total)
- **Empty Room Baseline**: 20 sessions (60–90s)
- **Stationary Standing**: 15 sessions (Near TX, Center, Near RX)
- **Slow Micro-Movement**: 15 sessions
- **Natural Walking**: 15 sessions
- **Dynamic Entry / Presence / Exit**: 15 sessions
- **Hard Negatives & Disturbances**: 10 sessions (fans, outside doors, vibrations)
- **Multi-Distance & Angle Variation**: 10 sessions (0.5m, 1.0m, 1.5m, 2.0m)
