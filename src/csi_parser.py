# ==============================================================================
# WiMotion: Robust ESP32 CSI Packet Parser & Strict Header Validator
# ==============================================================================
import numpy as np
from src.config import NUM_SUBCARRIERS, REQUIRED_RAW_CSI_BYTES

def parse_csi_line(line: str):
    """
    Strictly parses and validates raw CSI_DATA lines from ESP32-CSI-Tool stream.
    Verified exact hardware header format (0-indexed, 25 fields before bracket):
      0: type (CSI_DATA), 1: role (STA/AP), 2: mac, 3: rssi, 4: rate, 5: sig_mode,
      6: mcs, 7: bandwidth, 8: smoothing, 9: not_sounding, 10: aggregation, 11: stbc,
      12: fec_coding, 13: sgi, 14: noise_floor, 15: ampdu_cnt, 16: channel,
      17: secondary_channel, 18: local_timestamp, 19: ant, 20: sig_len, 21: rx_state,
      22: real_time_set, 23: real_timestamp, 24: len, 25: data [...]
    Returns: (metadata_dict, csi_raw_list) or (None, None) on validation failure.
    """
    if not line:
        return None, None
    
    line = line.strip()
    if not line.startswith("CSI_DATA"):
        return None, None

    try:
        bracket_start = line.index("[")
        bracket_end = line.index("]")
    except ValueError:
        return None, None

    metadata_part = line[:bracket_start].rstrip(",")
    csi_part = line[bracket_start + 1:bracket_end].strip()

    meta_fields = [f.strip() for f in metadata_part.split(",")]
    
    # Strict Header Format Validation:
    # Must have at least 25 fields (0 to 24) and field 0 must strictly equal "CSI_DATA"
    if len(meta_fields) < 25 or meta_fields[0] != "CSI_DATA":
        return None, None

    # Exact field extraction verified against real ESP32 stream:
    # index 3 = rssi, index 16 = channel, index 24 = len (128 or 384 bytes)
    rssi_val = meta_fields[3] if len(meta_fields) > 3 and meta_fields[3] else "N/A"
    channel_val = meta_fields[16] if len(meta_fields) > 16 and meta_fields[16] else "N/A"
    len_field_str = meta_fields[24] if len(meta_fields) > 24 else "128"

    metadata = {
        "role": meta_fields[1] if len(meta_fields) > 1 else "STA",
        "mac": meta_fields[2] if len(meta_fields) > 2 else "N/A",
        "rssi": rssi_val,
        "channel": channel_val,
        "csi_len": len_field_str,
        "real_timestamp": meta_fields[23] if len(meta_fields) > 23 else "0",
        "first_word": "0"
    }

    try:
        csi_raw = [int(x) for x in csi_part.split() if x.strip()]
    except ValueError:
        return None, None

    # Length Validation:
    # Must have at least 128 interleaved I/Q integers (64 complex subcarriers)
    if len(csi_raw) < REQUIRED_RAW_CSI_BYTES:
        return None, None

    return metadata, csi_raw

def compute_subcarrier_amplitudes(csi_raw, num_subcarriers=NUM_SUBCARRIERS, first_word: int = 0):
    """
    Extracts the first num_subcarriers complex samples from raw interleaved I/Q integers:
      amplitude = sqrt(I^2 + Q^2)
    Returns exactly num_subcarriers amplitudes, or None if raw list is truncated.
    """
    if len(csi_raw) < (num_subcarriers * 2):
        return None

    amplitudes = []
    for i in range(0, num_subcarriers * 2, 2):
        I = csi_raw[i]
        Q = csi_raw[i + 1]
        amp = np.sqrt(I**2 + Q**2)
        amplitudes.append(round(float(amp), 4))
    
    return amplitudes