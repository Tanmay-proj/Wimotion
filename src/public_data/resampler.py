# ==============================================================================
# WiMotion Public Data: Temporal Resampling & Alignment Engine
# ==============================================================================
# pyrefly: ignore [missing-import]
import numpy as np
from typing import Tuple, Optional

NOMINAL_WIMOTION_FS = 20.0

def resample_csi_sequence(
    csi_matrix: np.ndarray,
    timestamps: Optional[np.ndarray] = None,
    source_fs: Optional[float] = None,
    target_fs: float = NOMINAL_WIMOTION_FS
) -> Tuple[np.ndarray, np.ndarray, bool]:
    """
    Resamples a multi-subcarrier CSI sequence [N_frames, N_subcarriers]
    onto a uniform temporal grid at target_fs (default 20.0 Hz).

    Returns:
       (resampled_csi, resampled_timestamps, is_resampled)
    """
    arr = np.asarray(csi_matrix, dtype=float)
    n_frames, n_sub = arr.shape

    if n_frames < 2:
        return arr, np.array([0.0]), False

    # Establish time vector
    if timestamps is not None and len(timestamps) == n_frames:
        t = np.asarray(timestamps, dtype=float)
        t = t - t[0]
    elif source_fs is not None and source_fs > 0:
        t = np.arange(n_frames) / float(source_fs)
    else:
        # Unknown temporal grid — cannot interpolate without fabrication
        return arr, np.arange(n_frames) * (1.0 / target_fs), False

    duration = t[-1]
    if duration <= 0:
        return arr, t, False

    n_target = max(2, int(np.round(duration * target_fs)))
    t_uniform = np.linspace(0, duration, n_target)

    # Linear interpolation per subcarrier
    resampled = np.zeros((n_target, n_sub), dtype=np.float32)
    for c in range(n_sub):
        resampled[:, c] = np.interp(t_uniform, t, arr[:, c])

    return resampled, t_uniform, True
