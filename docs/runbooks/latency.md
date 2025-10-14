# Runbook: High Request Latency

Alert: twic_high_latency_p95

## Symptoms
- Alert fires when p95 latency > SLO threshold (e.g. 800ms) for sustained period.
- Users report slow classify responses.
- Grafana panel 'p95 latency' elevated.

## Quick Triage
1. Confirm spike on dashboard (latency & request volume).
2. Check 5xx and 429 metrics to distinguish saturation vs internal errors.
3. Inspect recent deploy (git_sha in /health) for regression.
4. Sample logs for slow paths (look at latency_ms field).

## Common Root Causes
- Cold start loading embeddings / models on first classify burst.
- Resource saturation (CPU bound vector similarity or sklearn inference).
- Redis latency (if using distributed rate limiter) causing request queueing.
- Large payloads causing preprocessing overhead.
- External system (filesystem / container disk throttling).

## Remediation Steps
- If first spike after deploy: warm caches by calling /classify with representative queries.
- Scale out: increase replica count or CPU allocation.
- Optimize weights: lower TOP_K via env var if excessive retrieval cost.
- Verify embeddings backend (placeholder vs sentence-transformers) – transformer model slower; consider distillation or caching.
- For Redis issues: check INFO latency, consider local fallback by unsetting REDIS_URL.

## Deeper Diagnostics
- Enable profiler temporarily (add cProfile around classify) in a canary.
- Compare current git_sha vs previous stable for performance diff.

## Prevention
- Add load warmup job post-deploy.
- Track cold start latency separately.
- Benchmark before merging heavy changes.
