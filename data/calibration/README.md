# Calibration Data Partition

This directory holds **ambient empty-room reference samples** captured separately in the target environment before a live deployment or benchmark run.

## Purpose & Protocols

- **Static Reference**: Provides baseline multipath profiles under known zero-occupancy conditions.
- **Ambient Tare**: Used to verify receiver noise floor, active subcarrier amplitude distribution, and nominal RSSI in a specific room.
- **Isolation Rules**: Calibration samples captured during a deployment session must never be leaked into general training or testing partitions.
- **Integrity**: Any dynamic TARE or background subtraction mechanism must be explicitly tested against these files to ensure false positive rates remain within controlled limits (<5%).
