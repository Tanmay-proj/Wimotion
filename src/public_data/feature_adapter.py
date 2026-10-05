# ==============================================================================
# WiMotion Public Data: Feature Adapter & Active Carrier Mapper
# ==============================================================================
import numpy as np
from typing import Optional, Tuple
from src.config import ACTIVE_SUBCARRIERS, NUM_SUBCARRIERS, FEATURE_COUNT
from src.feature_engine import extract_features

# IEEE 802.11n 20MHz standard active subcarrier distribution in 64-point FFT
# 52 Active carriers: 26 negative frequencies + 26 positive frequencies
# WiMotion ACTIVE_SUBCARRIERS contains exactly indices 6..31 and 33..58 (length 52)
ORDERED_ACTIVE_52 = sorted(list(ACTIVE_SUBCARRIERS))

def map_52_to_64_grid(csi_52: np.ndarray) -> np.ndarray:
    """
    Maps a 52-carrier physical amplitude matrix [N, 52] to WiMotion's
    64-subcarrier slot grid [N, 64] using exact IEEE 802.11n carrier positions.
    Null/Guard carriers [0..5, 32, 59..63] remain 0.0.
    """
    arr = np.asarray(csi_52, dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    n_frames, n_sub = arr.shape

    if n_sub != 52:
        raise ValueError(f"Expected 52 active carriers, got {n_sub}")

    grid_64 = np.zeros((n_frames, NUM_SUBCARRIERS), dtype=np.float32)
    for i, slot_idx in enumerate(ORDERED_ACTIVE_52):
        grid_64[:, slot_idx] = arr[:, i]

    return grid_64

def adapt_and_extract_features(
    csi_matrix: np.ndarray,
    timestamps: Optional[np.ndarray] = None,
    sampling_rate: Optional[float] = None
) -> Tuple[Optional[np.ndarray], str]:
    """
    Attempts to extract exact 217-dimensional WiMotion features from an adapted matrix.
    If representation or carrier count is incompatible, returns (None, reason).
    """
    arr = np.asarray(csi_matrix, dtype=float)
    if arr.ndim != 2:
        return None, f"Expected 2D matrix [N_frames, N_sub], got shape {arr.shape}"

    n_frames, n_sub = arr.shape
    if n_frames < 10:
        return None, f"Insufficient frames for 1.0s window: {n_frames} < 10"

    try:
        if n_sub == 52:
            grid_64 = map_52_to_64_grid(arr)
        elif n_sub == 64:
            grid_64 = arr
        else:
            return None, f"Carrier count {n_sub} not directly mappable to 52/64 grid"

        feats = extract_features(grid_64, timestamps=timestamps)
        if feats.shape[0] != FEATURE_COUNT:
            return None, f"Extracted {feats.shape[0]} features, expected {FEATURE_COUNT}"
        if not np.all(np.isfinite(feats)):
            return None, "Extracted features contain NaN or Inf values"

        return feats, "SUCCESS"
    except Exception as e:
        return None, f"Feature extraction failed: {str(e)}"
