# Runbook: Excessive 429 Responses

Alert: twic_high_429_rate

## Symptoms

- Spike in twic_http_429_total.
- Clients report frequent HTTP 429 'rate limit exceeded'.
- Request volume panel shows surge or bursty traffic.

## Quick Triage

1. Confirm if traffic pattern legitimate (marketing campaign, crawler?).
2. Check if REDIS_URL configured (distributed) or local limiter in use.
3. Review REQUEST_RATE_LIMIT and RATE_LIMIT_WINDOW_S env vars.
4. Inspect IP distribution (extend logging if needed) to detect abusive source.

## Common Root Causes

- Legitimate traffic growth beyond configured capacity.
- Bot / scraper causing burst loads.
- Misconfigured client retry logic hammering endpoint.

## Remediation Steps

- Raise REQUEST_RATE_LIMIT temporarily (with monitoring).
- Introduce client-specific API keys & per-key limits.
- Block abusive IPs at ingress / WAF.
- Add exponential backoff guidance to client docs.

## Prevention

- Implement token bucket w/ leaky burst allowance and separate global vs per-IP.
- Add dashboard panel for top IPs (ingress logs integration).
