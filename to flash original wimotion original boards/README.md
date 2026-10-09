# Original WiMotion (v1) Golden Hardware Backup

Yeh folder purane original WiMotion (v1) ke dono operational boards (TX aur RX) ka **bit-by-bit verified flash backup** hai.

---

## 1. Hardware Details & Binary Hashes

| Device Role | Hardware MAC | Port Tested | Binary File | Size | SHA256 Hash |
|---|---|---|---|---|---|
| **Original RX** | `4C:11:AE:64:9A:04` | `COM8` | `original_rx_com8.bin` | 434,176 B | `B0DD1ADD5DEC8993030BE4AA3CFE6F20C0C8E6C41339AA68CE238501C2557C2A` |
| **Original TX** | `BC:DD:C2:CC:49:F4` | `COM9` | `original_tx_com9.bin` | 434,176 B | `EDD3A4CFCB651A0E30925E472AA1B16811AE9AA2618B67687608F6CCE3EE3912` |

> **Coverage:** Yeh binaries offset `0x00000000` se `0x0006A000` tak ka complete bootable image contain karte hain:
> - `0x1000` : Second-stage Bootloader
> - `0x8000` : Partition Table (NVS, PHY Init, Factory App)
> - `0x9000` : NVS Storage
> - `0xF000` : PHY Calibration Data
> - `0x10000`: Full Compiled WiMotion Firmware

---

## 2. 1-Click Restore Instructions

Jab bhi kabhi original WiMotion v1 chalana ho:
1. Dono boards ko laptop se connect karo:
   - **Original RX** $\to$ `COM8`
   - **Original TX** $\to$ `COM9`
2. Iss folder mein jaakar **`restore_wimotion_v1.bat`** par double click karo (ya command line se run karo).
3. 10–15 seconds ke andar dono boards 100% unki original state mein flash ho jayenge!
