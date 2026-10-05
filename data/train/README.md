# Training Data Partition

This directory holds sessions used **exclusively for fitting model parameters**.

## Rules

- Data in this directory is used ONLY by the training script (`scripts/2_train_hardware_model.py`).
- It must NEVER be used for model selection, threshold tuning, or final evaluation.
- Augmented copies must remain grouped with their source session during cross-validation.
- The empty-room baseline should be computed from ONLY the training sessions in each fold.
