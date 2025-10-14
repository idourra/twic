# Runbook: Elevated 5xx Errors

Alert: twic_high_5xx_rate

## Symptoms

- Increase in twic_http_5xx_total.
- Users receive HTTP 500 or 503 responses.
- Latency may spike (retries) or drop (fast failures).

## Quick Triage

1. Check logs around error timestamps for stack traces or 'taxonomy concept missing'.
2. Hit /health to confirm service alive and artifacts list still present.
3. Verify model / embeddings files not corrupted or missing (artifacts, embeddings_dim not None).
4. Compare recent deploy (git_sha) with prior stable.

## Common Root Causes

- Missing taxonomy concept (stale ID in model outputs vs current taxonomy).
- Corrupted model artifacts after partial deploy.
- Out-of-memory during large retrieval / embedding load causing restarts.
- Unexpected input triggering unhandled exception.

## Remediation Steps

- Roll back to previous image digest / git_sha.
- Re-sync taxonomy.json with training artifacts; rebuild embeddings.
- Add guard clauses for discovered edge-case inputs.
- Increase memory or reduce concurrency.

## Prevention

- Add canary instance performing continuous smoke classification.
- Include integrity hash check of artifacts at startup.
- Expand test coverage for classify edge cases.
