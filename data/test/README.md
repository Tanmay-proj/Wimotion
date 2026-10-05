# Dedicated Held-Out Unseen Test Partition

This directory holds isolated physical sessions used strictly for final, untouched evaluation.

## Strict Scientific Policy

- **ZERO TOUCH RULE**: Models, feature scaling parameters, and decision thresholds must **NEVER** see, fit against, or tune upon any window from files in this partition.
- Not for training, not for validation, not for hyperparameter tuning, not for threshold selection.
- Used exclusively for final post-training reporting (e.g. `scripts/13_session_wise_evaluation.py`) to report true, uncorrupted generalization metrics.
- Missing holdout files must be flagged explicitly as missing data—never substituted with training or synthetic data while claiming holdout verification.
