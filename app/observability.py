"""Singleton-like holders for metrics to avoid circular imports."""

from app.core.settings import settings

try:  # optional dependency
    from prometheus_client import Counter, Histogram  # type: ignore
except ImportError:  # pragma: no cover
    Counter = Histogram = None  # type: ignore

REQUEST_LATENCY = None
REQUEST_COUNT = None
CLASSIFY_SCORE_MAX = None
CLASSIFY_ABSTAIN = None
HTTP_429_COUNT = None
HTTP_5XX_COUNT = None

if settings.enable_metrics and Counter and Histogram:  # pragma: no cover - simple wiring
    REQUEST_LATENCY = Histogram(
        "twic_request_latency_seconds", "Request latency", ["method", "path"]
    )
    REQUEST_COUNT = Counter(
        "twic_requests_total", "Total requests", ["method", "path", "status"]
    )
    CLASSIFY_SCORE_MAX = Histogram(
        "twic_classify_score_max",
        "Distribution of top prediction score",
        ["lang"],
        buckets=[0.0,0.2,0.4,0.6,0.7,0.8,0.85,0.9,0.95,0.97,1.0]
    )
    CLASSIFY_ABSTAIN = Counter(
        "twic_abstentions_total",
        "Abstentions by language",
        ["lang"]
    )
    HTTP_429_COUNT = Counter(
        "twic_http_429_total",
        "Total 429 (rate limit exceeded) responses",
        []
    )
    HTTP_5XX_COUNT = Counter(
        "twic_http_5xx_total",
        "Total 5xx responses",
        []
    )
