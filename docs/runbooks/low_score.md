# Runbook: Low Mean Prediction Score

Alert: twic_low_mean_score

## Symptoms

- Mean / distribution panel shifts left; few scores in >0.9 buckets.
- Downstream ranking quality complaints.
- Possible concurrent rise in abstentions.

## Quick Triage

1. Validate classifier calibration status (metadata.json: calibrated, method).
2. Inspect recent taxonomy changes causing label mismatch.
3. Check embeddings version / model switch.
4. Run manual queries to compare expected vs current scores.

## Common Root Causes

- Embeddings model quality regression.
- Fusion weights rebalanced reducing classifier contribution.
- Training data drift lowering separability.
- Calibration misconfigured (e.g., isotonic on too little data).

## Remediation Steps

- Recalibrate classifier (set CLF_CALIBRATION=platt or isotonic and retrain).
- Adjust fusion weights to boost stronger modality.
- Augment training set with new feedback examples.
- Rebuild embeddings with improved model.

## Prevention

- Track offline macro_f1_val & coverage trends pre-release.
- Keep changelog of fusion weight adjustments.
