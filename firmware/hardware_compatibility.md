# WiMotion Hardware & Firmware Compatibility Matrix

This document defines the verified hardware, toolchains, and firmware configuration for reproducible Wi-Fi CSI sensing.

## Hardware Matrix

| Parameter | Validated Specification | Unsupported / Incompatible |
| :--- | :--- | :--- |
| **Microcontroller** | ESP32-WROOM-32 / ESP32-DevKitC v4 (Xtensa LX6) | ESP32-S2 / ESP32-C3 / ESP32-C6 (different CSI format/subcarrier layout) |
| **Antenna Configuration** | Single external or PCB onboard antenna (SISO 1x1) | Dual-antenna diversity (untested phase ambiguity) |
| **Toolchain / SDK** | ESP-IDF v4.3.2 / v4.4 (Stable) | ESP-IDF v5.0+ (breaking changes in `wifi_csi_info_t` struct layout) |
| **Firmware Upstream** | [ESP32-CSI-Tool (StevenMHernandez)](https://github.com/StevenMHernandez/ESP32-CSI-Tool) / [oh-my-physec/esp32-csi-tool](https://github.com/oh-my-physec/esp32-csi-tool) | Custom non-standard CSI serial protocols |
| **Pinned Commit** | `5beecbf` (ESP32-CSI-Tool stable branch) | Untested main/HEAD branches |
| **Serial Baud Rate** | `921600` baud | `115200` baud (causes severe UART buffer dropping at >15 Hz) |
| **Wi-Fi Bandwidth** | 20 MHz (HT20: 64 subcarriers, 52 active carriers) | 40 MHz (HT40: 128 subcarriers - requires separate subcarrier mask) |
| **Wi-Fi Channel** | Channel 6 (2437 MHz) default (or 1, 11) | Dynamic channel switching / DFS channels |
| **Frame Rate** | 20–50 Hz continuous ping/injection | < 10 Hz (violates Nyquist rate for human walking motion) |

## Link Topologies

1. **Active STA -> Active AP (Standard Deployment)**:
   - **Node 1 (TX - Active Station)**: Connects to Node 2 AP and sends periodic UDP packets.
   - **Node 2 (RX - Active Access Point)**: Enables CSI promiscuous/AP callback, logs frame header and raw subcarrier array over USB-UART.

2. **Geometric Setup**:
   - Sensing Baseline: 1.0 m to 2.0 m node spacing.
   - Height: 0.8 m to 1.2 m above floor level (torso height).
   - Clear Line-of-Sight (LOS) for clean baseline calibration.
