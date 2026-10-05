# Validation Data Partition

This directory holds sessions used **strictly for model selection, hyperparameter tuning, and threshold calibration**.

## Rules

- Data in this directory must NEVER be used to fit model weights or feature normalizers.
- It is evaluated periodically during training or grid search to select optimal decision thresholds, temporal filter windows, and model architectures.
- It must remain completely separate from both the training partition and the dedicated held-out test partition.
- Cross-validation splits must respect session boundaries to prevent window leakage.
