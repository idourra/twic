"""Singleton-like holders for metrics to avoid circular imports."""

from app.core.settings import settings

try:  # optional dependency
    from prometheus_client import Counter, Histogram, Gauge  # type: ignore
except ImportError:  # pragma: no cover
    Counter = Histogram = None  # type: ignore

REQUEST_LATENCY = None
REQUEST_COUNT = None
CLASSIFY_SCORE_MAX = None
CLASSIFY_ABSTAIN = None
HTTP_429_COUNT = None
HTTP_5XX_COUNT = None

FEEDBACK_TOTAL = None
UNKNOWN_QUERIES_TOTAL = None
MODEL_VERSION_INFO = None

# Taxonomy search/autocomplete metrics
TAXO_SEARCH_LATENCY = None
TAXO_SEARCH_RESULTS = None
TAXO_SEARCH_EMPTY = None
TAXO_EMB_CACHE_SIZE = None

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
    FEEDBACK_TOTAL = Counter(
        "twic_feedback_total",
        "Feedback events by type (accepted, correction, rejection)",
        ["type"]
    )
    UNKNOWN_QUERIES_TOTAL = Counter(
        "twic_unknown_queries_total",
        "Queries where system abstained (proxy for unknown intents)",
        ["lang"]
    )
    MODEL_VERSION_INFO = Gauge(
        "twic_model_version_info",
        "Static gauge=1 labeled with current api_version and git_sha",
        ["version", "git_sha"]
    )
    TAXO_SEARCH_LATENCY = Histogram(
        "twic_taxo_search_latency_seconds",
        "Latency of taxonomy search/autocomplete",
        ["lang", "source"],  # source=search|autocomplete
        buckets=[0.005,0.01,0.02,0.05,0.1,0.2,0.5,1.0]
    )
    TAXO_SEARCH_RESULTS = Counter(
        "twic_taxo_search_results_total",
        "Distribution of result counts bucketed",
        ["lang", "source", "bucket"]  # bucket=0|1_5|6_10|gt_10
    )
    TAXO_SEARCH_EMPTY = Counter(
        "twic_taxo_search_empty_total",
        "Empty result sets",
        ["lang", "source"]
    )
    TAXO_EMB_CACHE_SIZE = Gauge(
        "twic_taxo_embeddings_cache_size",
        "Number of precomputed taxonomy label embeddings",
        ["lang"]
    )
