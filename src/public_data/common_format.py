# ==============================================================================
# WiMotion Public Data: Common Ingestion Schema & Provenance Tracking
# ==============================================================================
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, List, Dict, Any
import numpy as np

ADAPTER_VERSION = "v1.0"

@dataclass
class CSIRecord:
    dataset: str
    sample_id: str
    activity_label: str
    presence_label: int  # 0 = NO_HUMAN, 1 = HUMAN_PRESENT, -1 = UNKNOWN
    num_subcarriers: int
    original_shape: List[int]
    source_file: str
    adapter_version: str = ADAPTER_VERSION
    participant_id: Optional[str] = None
    environment_id: Optional[str] = None
    sampling_rate: Optional[float] = None
    csi_amplitudes: Optional[np.ndarray] = None  # Shape [N_frames, num_subcarriers]
    timestamps: Optional[np.ndarray] = None      # Shape [N_frames]

    def to_provenance_dict(self) -> Dict[str, Any]:
        return {
            "dataset": self.dataset,
            "sample_id": self.sample_id,
            "participant_id": self.participant_id,
            "environment_id": self.environment_id,
            "activity_label": self.activity_label,
            "presence_label": self.presence_label,
            "source_file": self.source_file,
            "original_shape": self.original_shape,
            "original_sampling_rate": self.sampling_rate,
            "num_subcarriers": self.num_subcarriers,
            "adapter_version": self.adapter_version
        }

    def save(self, output_dir: Path) -> Path:
        """
        Saves record into output_dir as:
          - <sample_id>.npz (numerical CSI + timestamps)
          - <sample_id>_meta.json (provenance metadata)
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        npz_file = output_dir / f"{self.sample_id}.npz"
        json_file = output_dir / f"{self.sample_id}_meta.json"

        # Write provenance
        json_file.write_text(json.dumps(self.to_provenance_dict(), indent=2), encoding="utf-8")

        # Write binary arrays
        arrays_to_save = {}
        if self.csi_amplitudes is not None:
            arrays_to_save["csi"] = np.asarray(self.csi_amplitudes, dtype=np.float32)
        if self.timestamps is not None:
            arrays_to_save["ts"] = np.asarray(self.timestamps, dtype=np.float64)

        np.savez_compressed(npz_file, **arrays_to_save)
        return npz_file

    @classmethod
    def load(cls, npz_path: Path) -> "CSIRecord":
        npz_path = Path(npz_path)
        json_path = npz_path.parent / f"{npz_path.stem}_meta.json"
        meta = json.loads(json_path.read_text(encoding="utf-8")) if json_path.exists() else {}

        data = np.load(npz_path)
        csi = data["csi"] if "csi" in data else None
        ts = data["ts"] if "ts" in data else None

        return cls(
            dataset=meta.get("dataset", "unknown"),
            sample_id=meta.get("sample_id", npz_path.stem),
            activity_label=meta.get("activity_label", "unknown"),
            presence_label=meta.get("presence_label", -1),
            num_subcarriers=meta.get("num_subcarriers", csi.shape[1] if csi is not None else 0),
            original_shape=meta.get("original_shape", list(csi.shape) if csi is not None else []),
            source_file=meta.get("source_file", ""),
            adapter_version=meta.get("adapter_version", ADAPTER_VERSION),
            participant_id=meta.get("participant_id"),
            environment_id=meta.get("environment_id"),
            sampling_rate=meta.get("original_sampling_rate"),
            csi_amplitudes=csi,
            timestamps=ts
        )
