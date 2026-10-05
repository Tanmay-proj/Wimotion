# ==============================================================================
# WiMotion: CSI Motion & Temporal-Frequency Feature Engine (v2.4)
# (Uniform Resampling + Active Carrier SVD Coherence + Data Augmentation)
# ==============================================================================
import numpy as np
import pandas as pd
from scipy.interpolate import interp1d
from src.config import (
    NUM_SUBCARRIERS, NOMINAL_SAMPLING_RATE_HZ, TARGET_RESAMPLE_FS,
    SMOOTHING_WINDOW, MOTION_FREQ_BINS, FEATURE_COUNT, PEAK_FREQ_FEATURE_INDEX,
    ACTIVE_SUBCARRIERS
)

def estimate_sampling_rate(timestamps: np.ndarray) -> float:
    """Estimates physical CSI packet sampling rate (Hz) from host timestamps."""
    ts = np.asarray(timestamps, dtype=float)
    if len(ts) < 3:
        return NOMINAL_SAMPLING_RATE_HZ

    total_span = float(ts[-1] - ts[0])
    if total_span >= 0.3:
        rate = float(len(ts) - 1) / total_span
    else:
        dt = np.diff(ts)
        valid_dt = dt[np.isfinite(dt) & (dt > 0.001)]
        if len(valid_dt) < 2:
            return NOMINAL_SAMPLING_RATE_HZ
        median_dt = float(np.median(valid_dt))
        if median_dt <= 0.0:
            return NOMINAL_SAMPLING_RATE_HZ
        rate = 1.0 / median_dt

    return float(np.clip(rate, 4.0, 30.0))

def resample_to_uniform_grid(window_arr: np.ndarray, timestamps: np.ndarray = None, target_fs: float = TARGET_RESAMPLE_FS) -> np.ndarray:
    """Interpolates irregular arrival time series onto an exact uniform temporal grid (20.0 Hz)."""
    n_frames = window_arr.shape[0]
    if timestamps is None or len(timestamps) != n_frames or len(timestamps) < 3:
        return window_arr

    ts = np.asarray(timestamps, dtype=float)
    t_start, t_end = ts[0], ts[-1]
    duration = t_end - t_start

    if duration < 0.2:
        return window_arr

    n_target = max(10, int(round(duration * target_fs)))
    t_uniform = np.linspace(t_start, t_end, n_target)

    try:
        f_interp = interp1d(ts, window_arr, axis=0, kind="linear", fill_value="extrapolate")
        return f_interp(t_uniform)
    except Exception:
        return window_arr

def smooth_window(arr: np.ndarray) -> np.ndarray:
    """Causal temporal moving-average smoothing across CSI frames."""
    return pd.DataFrame(arr).rolling(window=SMOOTHING_WINDOW, min_periods=1).mean().values

def augment_csi_window(window_arr: np.ndarray, gain_range: float = 0.04, noise_std: float = 0.06) -> np.ndarray:
    """
    Physics-informed CSI data augmentation:
      - Subtle physical RF gain fluctuation (+-4%)
      - Active subcarrier multipath perturbation (Gaussian noise)
      - Inactive subcarriers masked to 0
    """
    inactive = [i for i in range(NUM_SUBCARRIERS) if i not in ACTIVE_SUBCARRIERS]
    gain = 1.0 + np.random.uniform(-gain_range, gain_range)
    aug_arr = window_arr * gain
    noise = np.random.normal(0.0, noise_std, size=window_arr.shape)
    aug_arr[:, ACTIVE_SUBCARRIERS] += noise[:, ACTIVE_SUBCARRIERS]
    aug_arr[:, inactive] = 0.0
    return np.maximum(aug_arr, 0.0)

def compute_temporal_motion_power_spectrum(normalized_arr: np.ndarray) -> np.ndarray:
    """Computes normalized Doppler / multipath motion power spectrum across active subcarriers."""
    n_frames = normalized_arr.shape[0]
    active_arr = normalized_arr[:, ACTIVE_SUBCARRIERS]
    arr_detrended = active_arr - active_arr.mean(axis=0, keepdims=True)
    hanning = np.hanning(n_frames).reshape(-1, 1)
    windowed = arr_detrended * hanning

    fft_result = np.fft.rfft(windowed, axis=0)
    power_spectrum = np.abs(fft_result) ** 2
    motion_power_full = power_spectrum.sum(axis=1)

    n_keep = min(MOTION_FREQ_BINS, max(1, (n_frames // 2)))
    motion_power_spectrum = motion_power_full[1:1 + n_keep]

    if len(motion_power_spectrum) < MOTION_FREQ_BINS:
        motion_power_spectrum = np.pad(motion_power_spectrum, (0, MOTION_FREQ_BINS - len(motion_power_spectrum)))

    return motion_power_spectrum

def compute_cross_subcarrier_coherence(normalized_arr: np.ndarray) -> np.ndarray:
    """
    SVD Spatial Subcarrier Coherence Analysis on active OFDM carriers.
    Extracts:
      - pc1_ratio: Dominant spatial eigenmode energy ratio (>60% in human movement)
      - pc2_ratio: Secondary spatial mode ratio
      - spatial_entropy: Information entropy of spatial singular values
    """
    active_norm = normalized_arr[:, ACTIVE_SUBCARRIERS]
    try:
        _, s, _ = np.linalg.svd(active_norm - active_norm.mean(axis=0, keepdims=True), full_matrices=False)
        s_var = s ** 2
        total_s_var = float(np.sum(s_var))
        if total_s_var > 1e-6:
            pc1_ratio = float(s_var[0] / total_s_var)
            pc2_ratio = float(s_var[1] / total_s_var) if len(s) > 1 else 0.0
            p = (s_var / total_s_var) + 1e-12
            spatial_entropy = float(-np.sum(p * np.log(p)))
        else:
            pc1_ratio, pc2_ratio, spatial_entropy = 0.0, 0.0, 0.0
    except Exception:
        pc1_ratio, pc2_ratio, spatial_entropy = 0.0, 0.0, 0.0

    return np.array([pc1_ratio, pc2_ratio, spatial_entropy])

def extract_features(window_arr: np.ndarray, timestamps: np.ndarray = None,
                     fs: float = NOMINAL_SAMPLING_RATE_HZ, target_fs: float = TARGET_RESAMPLE_FS,
                     baseline_reference: np.ndarray = None) -> np.ndarray:
    """
    Extracts 217 baseline-invariant motion-frequency, spatial-coherence and statistical features:
      - 192 Per-subcarrier normalized statistics (Relative STD, Dynamic Range, Step-diff)
      - 6 Global normalized motion statistics (mean/max STD, STD-of-STD, mean/max range, energy)
      - 12 Temporal motion power spectrum bins (|FFT|^2 on uniform 20 Hz grid, DC excluded)
      - 4 Temporal-frequency summary features (Peak Freq, Total Power, Centroid, Bandwidth)
      - 3 Cross-subcarrier spatial coherence features (PC1 Energy Ratio, PC2 Ratio, Spatial Entropy)
    """
    inactive = [i for i in range(NUM_SUBCARRIERS) if i not in ACTIVE_SUBCARRIERS]

    if timestamps is not None:
        arr_grid = resample_to_uniform_grid(window_arr, timestamps, target_fs=target_fs)
        effective_fs = target_fs
    else:
        arr_grid = window_arr
        effective_fs = fs

    arr_grid = np.maximum(arr_grid, 0.0)
    arr_grid[:, inactive] = 0.0
    arr = smooth_window(arr_grid)
    n_frames = arr.shape[0]

    if baseline_reference is not None:
        ref = np.asarray(baseline_reference, dtype=float).reshape(1, -1).copy()
        ref[:, inactive] = 0.0
        baseline = ref
        scale = np.maximum(np.abs(ref), 1.0)
    else:
        baseline = np.median(arr, axis=0, keepdims=True)
        baseline[:, inactive] = 0.0
        scale = np.maximum(np.median(np.abs(arr), axis=0, keepdims=True), 1.0)

    normalized = (arr - baseline) / scale
    normalized[:, inactive] = 0.0

    temporal_std = normalized.std(axis=0)
    temporal_range = np.ptp(normalized, axis=0)
    temporal_diff = np.abs(np.diff(normalized, axis=0)).mean(axis=0) if n_frames > 1 else np.zeros(NUM_SUBCARRIERS)

    # Active carriers for global stats
    active_norm = normalized[:, ACTIVE_SUBCARRIERS]
    global_mean_std = float(active_norm.std(axis=0).mean())
    global_max_std = float(active_norm.std(axis=0).max())
    global_std_of_std = float(active_norm.std(axis=0).std())
    global_mean_range = float(np.ptp(active_norm, axis=0).mean())
    global_max_range = float(np.ptp(active_norm, axis=0).max())
    global_total_energy = float((active_norm ** 2).mean())

    global_features = np.array([
        global_mean_std, global_max_std, global_std_of_std,
        global_mean_range, global_max_range, global_total_energy
    ])

    motion_power_spectrum = compute_temporal_motion_power_spectrum(normalized)
    peak_bin_idx = int(np.argmax(motion_power_spectrum)) + 1
    
    freqs_hz = np.arange(1, len(motion_power_spectrum) + 1) * effective_fs / max(1, n_frames)
    peak_frequency_hz = (peak_bin_idx * effective_fs) / max(1, n_frames)
    total_motion_power = float(motion_power_spectrum.sum())

    if total_motion_power > 1e-6:
        motion_centroid_hz = float((freqs_hz * motion_power_spectrum).sum() / total_motion_power)
        diff_sq = (freqs_hz - motion_centroid_hz) ** 2
        motion_spread_hz = float(np.sqrt((diff_sq * motion_power_spectrum).sum() / total_motion_power))
    else:
        motion_centroid_hz = 0.0
        motion_spread_hz = 0.0

    motion_summary = np.array([
        peak_frequency_hz, total_motion_power, motion_centroid_hz, motion_spread_hz
    ])

    coherence_features = compute_cross_subcarrier_coherence(normalized)

    feature_vector = np.concatenate([
        temporal_std, temporal_range, temporal_diff,
        global_features,
        motion_power_spectrum, motion_summary,
        coherence_features
    ])

    return np.nan_to_num(feature_vector, nan=0.0, posinf=0.0, neginf=0.0)
