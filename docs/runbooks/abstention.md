# Runbook: High Abstention Rate

Alert: twic_high_abstention_rate

## Symptoms

- Rising count in twic_abstentions_total / low prediction coverage.
- Business users report many 'no prediction' cases.
- Mean top score panel decreases; low_score alert may co-fire.

## Quick Triage

1. Verify recent model or weight changes (git_sha, /health artifacts list).
2. Inspect tau_low env var; was it raised recently?
3. Check score distribution panel for shift (fewer high-score buckets).
4. Run a manual classify on known common queries to reproduce.

## Common Root Causes

- Tau threshold too aggressive relative to calibration.
- Domain drift: new query patterns not represented in training data.
- Embeddings degradation (switched backend accidentally?).
- Retrieval mis-weighted (fusion weights changed lowering classifier influence).

## Remediation Steps

- Temporarily lower TAU_LOW to restore coverage; redeploy.
- Retrain classifier with new feedback examples (scripts/train_classifier.py).
- Rebuild embeddings if taxonomy changed (scripts/build_embeddings.py).
- Adjust fusion weights ALPHA_SEM/BETA_BM25/GAMMA_CLF to emphasize strongest signal.
- Improve calibration (set CLF_CALIBRATION=platt or isotonic and retrain).

## Prevention

- Scheduled offline evaluation (scripts/eval_offline.py) with drift tracking.
- Monitor coverage_at_tau metric in metadata.json during releases.
