# ==============================================================================
# WiMotion: Shared Project Configuration (Single Source of Truth - v2.4)
# ==============================================================================
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_SYN_DIR = BASE_DIR / "data_syn"
MODELS_DIR = BASE_DIR / "models"
CALIBRATION_DIR = DATA_DIR / "calibration"
CALIBRATION_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Hardware / Serial Parameters
DEFAULT_BAUDRATE = 921600          # High-speed UART rate for zero packet loss
DEFAULT_SERIAL_TIMEOUT = 1.0       # Serial read timeout in seconds (prevents blocking)
SERIAL_RECONNECT_ATTEMPTS = 5      # Max retries on USB disconnect
SERIAL_RECONNECT_DELAY_SEC = 2.0   # Delay between reconnect attempts

# CSI Subcarrier Configuration (ESP32 802.11n HT20)
NUM_SUBCARRIERS = 64               # Primary 64 complex CSI samples extracted per frame
REQUIRED_RAW_CSI_BYTES = 128       # 64 I/Q pairs = 128 interleaved integer values
SUBCARRIER_MAPPING_MODE = "first_64_complex"  # Extracts first 64 complex CSI samples from ESP32 serial packet format

# Active Sensing Subcarrier Selection (Masking Null/Guard 0, 1, 62, 63 and DC 32)
GUARD_SUBCARRIERS = [0, 1, 2, 3, 4, 5, 59, 60, 61, 62, 63]
DC_SUBCARRIER = [32]
ACTIVE_SUBCARRIERS = [i for i in range(NUM_SUBCARRIERS) if i not in (GUARD_SUBCARRIERS + DC_SUBCARRIER)]

# Sampling & Time-Based Resampling Parameters (v2.4 Fast-Response)
NOMINAL_SAMPLING_RATE_HZ = 10.0    # Baseline nominal sampling rate (Hz)
TARGET_RESAMPLE_FS = 20.0          # Uniform resampling temporal grid rate (20.0 Hz)
MIN_ACCEPTABLE_DATASET_FPS = 1.0   # Minimum acceptable packet rate for training

# Fast Sub-Second Time Windowing
WINDOW_DURATION_SEC = 1.0          # Fast 1.0s physical time window (sub-second reaction)
WINDOW_STEP_SEC = 0.20             # Step duration between sliding windows (0.20 seconds)
PREDICTION_INTERVAL_SEC = 0.10     # 10 Hz live evaluation rate (super responsive)

# Safety bounds for frame count in a 1.0s time window
MIN_WINDOW_FRAMES = 5              # Minimum frames allowed in a 1.0s window (~5 Hz)
MAX_WINDOW_FRAMES = 40             # Maximum frames allowed in a 1.0s window (~30 Hz)
MAX_WINDOWS_PER_SESSION = 600      # Session balancing cap

# Signal Quality Gate Thresholds
MIN_RSSI_DBM = -82.0               # Fringe signal threshold
MIN_STREAM_FPS = 4.0               # Drop below this triggers UNSTABLE
MAX_STREAM_FPS = 60.0              # Abnormal surge

# Legacy aliases for compatibility
WINDOW_SIZE = 20                   # Legacy alias
WINDOW_STEP = 4                    # Legacy alias
PREDICTION_STEP = 2                # Legacy alias

# Temporal Decision Smoothing & 3-State Hysteresis (v2.4)
STATE_HISTORY_LENGTH = 5           # Rolling median buffer length
MIN_ENTRY_SUSTAINED_VOTES = 2      # Entry requires score > 0.70 sustained for 2 windows (~0.8s)
MIN_EXIT_SUSTAINED_VOTES = 4       # Exit requires score < 0.25 sustained for 4 windows (~1.4s)
CONFIDENCE_THRESHOLD = 0.55        # Minimum confidence threshold
CLEAR_THRESHOLD = 0.25             # Zone clear upper bound (0% - 25%)
PRESENCE_THRESHOLD = 0.70          # Human present lower bound (70% - 100%)
MIN_WINDOWS_PER_CLASS = 10         # Minimum windows required per class for training

ENTRY_HYSTERESIS_THRESH = 0.70
EXIT_HYSTERESIS_THRESH = 0.25

# Sample Weighting Factors
HISTORICAL_SAMPLE_WEIGHT = 1.0     # Baseline historical weight
CALIBRATION_SAMPLE_WEIGHT = 3.0    # Current room calibration boost weight

SMOOTHING_WINDOW = 3               # Temporal moving average smoothing for subcarriers
MOTION_FREQ_BINS = 12              # Positive motion frequency bins
COHERENCE_FEATURE_COUNT = 3        # Spatial SVD coherence features (PC1, PC2, Spatial Entropy)

# Feature Indices & Versioning (217 Features)
FEATURE_COUNT = (NUM_SUBCARRIERS * 3) + 6 + MOTION_FREQ_BINS + 4 + COHERENCE_FEATURE_COUNT
PEAK_FREQ_FEATURE_INDEX = -7       # Index of Peak Spectral Frequency in 217-feature vector
FEATURE_ENGINE_VERSION = "v2.4"
MODEL_VERSION = "v2.4"

# Model Deployment File
MODEL_FILE = MODELS_DIR / "wimotion_model.pkl"

# Labeled Classes & Multi-Pose Mapping
CLASSES = ["empty_room", "human_present"]
MULTI_POSE_MAPPING = {
    "empty_room": "empty_room",
    "site_empty": "empty_room",
    "current_empty": "empty_room",
    "walking": "human_present",
    "human_present": "human_present",
    "human_standing": "human_present",
    "human_slow": "human_present",
    "human_walking": "human_present",
    "site_human": "human_present",
    "current_human": "human_present"
}

# Spatial Positions
SPATIAL_POSITIONS = ["NEAR_TX", "CENTER", "NEAR_RX", "CROSS_LOS"]

# WiMotion v2.4 Observatory / sensing-zone configuration
DISPLAY_LABELS = {
    "empty_room": "SENSING ZONE CLEAR",
    "uncertain": "ANALYZING...",
    "human_present": "HUMAN PRESENT",
    "unstable": "SIGNAL UNSTABLE"
}
WEBSOCKET_HOST = "127.0.0.1"
WEBSOCKET_PORT = 8765
HTTP_HOST = "127.0.0.1"
HTTP_PORT = 8000
SENSING_ZONE_RADIUS_M = 1.5
OBSERVATORY_GRID_SIZE = 20
