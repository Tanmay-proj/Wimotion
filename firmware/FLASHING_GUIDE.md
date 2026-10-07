# ESP32 Firmware Guide (ESP32-CSI-Tool)

WiMotion uses the proven **ESP32-CSI-Tool** frame exchange architecture.

---

## Hardware Compatibility & Pinned Toolchain

| Item | Requirement / Recommendation |
| :--- | :--- |
| **Target Boards** | 2x ESP32-WROOM-32 / ESP32-DevKitC v4 |
| **ESP-IDF Version** | **v4.3** (Recommended) or v4.4. *(Do NOT use v5.x due to breaking CSI struct changes)* |
| **Upstream Repository** | [ESP32-CSI-Tool](https://github.com/StevenMHernandez/ESP32-CSI-Tool) / [oh-my-physec/esp32-csi-tool](https://github.com/oh-my-physec/esp32-csi-tool) |
| **Pinned Commit** | `5beecbf` (verified stable on ESP-IDF v4.3) |
| **Baud Rate** | **921600** baud (required for real-time 20-50 Hz CSI packet output without UART buffer drops) |
| **Wi-Fi Channel** | Channel 6 (HT20: 64 subcarriers, 52 active) |

See [hardware_compatibility.md](hardware_compatibility.md) for full matrix.

---

## Architecture: Active STA (TX) & Active AP (CSI-RX)

* **Node 1 (Active STA / Transmitter):** Station node continuously sending frame requests to the AP.
* **Node 2 (Active AP / CSI Receiver):** Access Point capturing CSI on received WiFi frames, streaming CSI packets over USB Serial to the PC.

---

## Option 1: Use Existing Flashed Boards (Recommended)

If your ESP32 boards were already flashed with `active_sta` (TX) and `active_ap` (RX), **do NOT re-flash**. They work 100% out of the box with WiMotion.

---

## Option 2: Fresh Flash via Included Source Snapshot (ESP-IDF v4.3 / v4.4)

The complete ESP-IDF projects are included directly in the repository at `firmware/src/` (pinned to stable ESP32-CSI-Tool architecture):

### 1. Requirements
* ESP-IDF v4.3 or v4.4 installed (open ESP-IDF Command Prompt).

### 2. Flash Node 1 (Active STA / Transmitter)
```bash
cd firmware/src/active_sta
idf.py -p COM3 flash
```

### 3. Flash Node 2 (Active AP / CSI Receiver)
```bash
cd firmware/src/active_ap
idf.py -p COM5 flash
```

### 4. Verify Stream
Open `run_wimotion.bat` and press `0` to run the 8-second diagnostic audit.

---

## Raw CSI_DATA Fixture Example (Parser Reference)

When running properly, Node 2 emits lines formatted as:
```text
CSI_DATA,STA,BC:DD:C2:CC:49:F5,-67,11,0,0,0,0,0,0,0,0,0,-94,0,6,1,99460646,0,110,0,0,99.8496,128,[3 -4 5 0 ... -2 3]
```

### Field Breakdown:
1. `type`: `CSI_DATA`
2. `role`: `STA` or `AP`
3. `mac`: Sender MAC address (`BC:DD:C2:CC:49:F5`)
4. `rssi`: Received Signal Strength Indicator in dBm (e.g. `-67`)
5. `rate`: Physical layer transmission rate
6. `sig_mode` to `noise_floor`: PHY header parameters (`noise_floor`: e.g. `-94`)
7. `channel`: Wi-Fi channel index (e.g. `6`)
8. `timestamp`: Microsecond internal hardware timer
9. `csi_len`: Number of bytes in raw array (e.g. `128` bytes for 64 complex subcarrier pairs $[I, Q]$)
10. `[data]`: Space-delimited signed integers representing alternating in-phase ($I$) and quadrature ($Q$) components:
    $$\text{Amplitude}_k = \sqrt{I_k^2 + Q_k^2}$$

---

## Hardware Stream Rate & Stability Diagnostics

### Root Cause Analysis: 0.7 Hz vs 9.6 Hz Fluctuation
| Symptom / Rate | Cause | Solution |
| :--- | :--- | :--- |
| **0.7 – 1.5 pkt/s (CRITICAL)** | 1. Baud set to 115200 (at 400 bytes/packet, 40 Hz saturates UART buffer and causes severe drops).<br>2. Transmitter unlinked or restarting.<br>3. USB port power starvation (unpowered hub). | 1. Always use **921600 baud**.<br>2. Plug ESP32 directly into PC/laptop motherboard USB ports.<br>3. Keep nodes 1–2 meters apart on Channel 6. |
| **4.0 – 7.9 pkt/s (WARNING)** | Wi-Fi multipath degradation, distance > 3m, or intermittent transmitter pacing. | Signal Quality Gate allows inference, but temporal response may experience minor latency. Re-align node antennas parallel to each other. |
| **8.0 – 15.0 pkt/s (READY / OPTIMAL)** | Clean HT20 link, zero UART packet loss, optimal transmission rate. | Ideal state for live evaluation. Both CLI and 3D Observatory will operate smoothly. |

---

## Live Demo Pre-Flight Checklist (Viva Protocol)

### Phase 1 — Hardware Pre-Flight Audit
1. Connect Node 2 (CSI Receiver / AP) to COM8 (or detected COM port) using a high-quality USB data cable.
2. Power Node 1 (Transmitter / STA). Ensure both boards are ~1.5 meters apart.
3. Open `run_wimotion.bat` and select `[0] Hardware Diagnostics & CSI Rate Measurement`.
4. Verify:
   - Serial Port: `[OK]`
   - Baud Rate: `921600 [OK]`
   - Packet Corruption: `0 dropped [OK]`
   - Effective Rate: **$\ge 8.0$ pkt/s [READY]**
   > **CRITICAL RULE:** If the hardware diagnostic reports `< 4.0 Hz`, **DO NOT launch live demo mode**. The Signal Quality Gate will actively block ML inference. Either replug USB / power-cycle the transmitter, or use **Demo Option B (Replay Backup)**.

### Phase 2 — 3D Observatory Demonstration
1. Open `run_wimotion.bat` and select `[5] Launch WiMotion 3D Observatory Dashboard`.
2. First verify with Replay Mode:
   - Dashboard automatically loads `golden_demo_presence.csv` (gold standard 10 Hz physical session).
   - Show the panel: Room Clear (t < 8s) $\to$ Human Walking Entry (t = 8–18s, `HUMAN PRESENT`) $\to$ Exit (t > 18s, `SENSING ZONE CLEAR`).
3. Switch Dashboard to **LIVE** mode (COM8, 921600 baud):
   - **Step 1 (Empty Baseline):** Stand outside sensing zone for 10–15 seconds. Observe `SENSING ZONE CLEAR` (presence score < 0.20).
   - **Step 2 (Human Entry):** Walk into the sensing zone (1.0–1.5m from Tx/Rx line). Observe the real-time hysteresis transition to `HUMAN PRESENT` (presence score > 0.80).
   - **Step 3 (Exit):** Step out of the zone. Observe smooth return to `SENSING ZONE CLEAR`.

### Phase 3 — Fallback Policy
If live RF environment undergoes severe interference during presentation:
> *"We have implemented a dual-path observatory. While live physical RF streams depend on immediate 2.4 GHz channel conditions, we also maintain a verified golden empirical dataset (`golden_demo_presence.csv`) recorded under identical hardware parameters to demonstrate exact pipeline reproducibility."*