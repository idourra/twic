from fastapi import FastAPI, Request
# ruff: noqa: I001
from fastapi.responses import ORJSONResponse, PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware
import time
import json
import os
import joblib
from app.core.settings import settings
from app.routers import taxonomy, feedback, classify, admin
from app import observability

# Metrics (Prometheus) optional
try:  # lightweight optional import
    from prometheus_client import Counter, Histogram, generate_latest  # type: ignore
except ImportError:  # pragma: no cover
    Counter = Histogram = None  # type: ignore
    generate_latest = None  # type: ignore

REQUEST_LATENCY = observability.REQUEST_LATENCY
REQUEST_COUNT = observability.REQUEST_COUNT


class RateLimiter:
    def __init__(self, capacity: int, window_s: int):
        self.capacity = capacity
        self.window_s = window_s
        self.tokens = capacity
        self.refill_ts = time.time()

    def allow(self) -> bool:
        now = time.time()
        if now - self.refill_ts >= self.window_s:
            self.tokens = self.capacity
            self.refill_ts = now
        if self.tokens > 0:
            self.tokens -= 1
            return True
        return False


_rate_limiter = RateLimiter(settings.request_rate_limit, settings.rate_limit_window_s)


class ObservabilityMiddleware(BaseHTTPMiddleware):  # pragma: no cover (integration)
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        if settings.max_query_chars > 0 and request.method == "POST":
            # naive size check for body length (already in memory)
            body_bytes = await request.body()
            if len(body_bytes) > settings.max_query_chars * 4:  # approximate safety margin
                return PlainTextResponse("payload too large", status_code=413)
        if not _rate_limiter.allow():
            return PlainTextResponse("rate limit exceeded", status_code=429)
        response = None
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            dur = time.time() - start
            if REQUEST_LATENCY:
                REQUEST_LATENCY.labels(request.method, request.url.path).observe(dur)
            if REQUEST_COUNT:
                REQUEST_COUNT.labels(request.method, request.url.path, str(status_code)).inc()
            # Structured log line
            log_line = json.dumps({
                "event": "http_access",
                "method": request.method,
                "path": request.url.path,
                "status": status_code,
                "latency_ms": int(dur * 1000),
            })
            print(log_line)

app = FastAPI(
    title=settings.api_name,
    version=settings.api_version,
    default_response_class=ORJSONResponse,
)

app.add_middleware(ObservabilityMiddleware)

@app.get("/metrics")
def metrics():  # pragma: no cover
    if not (settings.enable_metrics and generate_latest and REQUEST_LATENCY):
        return PlainTextResponse("metrics disabled", status_code=404)
    output = generate_latest()  # type: ignore
    return PlainTextResponse(output.decode("utf-8"), media_type="text/plain; version=0.0.4")

@app.get("/health")
def enriched_health():  # lightweight aggregation
    # Gather basic model / artifact info (best-effort)
    artifacts = []
    for f in ["tfidf.joblib", "lr_calibrated.joblib", "lr.joblib", "classes.joblib"]:
        path = os.path.join(settings.models_dir, f)
        if os.path.exists(path):
            artifacts.append(f)
    # embeddings dim (try loading small header via numpy memmap if needed)
    embeddings_dim = None
    for lang in ("es", "en"):
        emb_path = os.path.join(settings.data_dir, f"class_embeddings_{lang}.npy")
        if os.path.exists(emb_path):
            try:
                import numpy as _np  # local import
                arr = _np.load(emb_path, mmap_mode="r")
                embeddings_dim = int(arr.shape[1])
                break
            except Exception:  # pragma: no cover
                pass
    classes_count = None
    cls_file = os.path.join(settings.models_dir, "classes.joblib")
    if os.path.exists(cls_file):
        try:
            cls_ids = joblib.load(cls_file)
            classes_count = len(cls_ids)
        except Exception:  # pragma: no cover
            pass
    return {
        "status": "ok",
        "version": settings.api_version,
        "artifacts": artifacts,
        "classes": classes_count,
        "embeddings_dim": embeddings_dim,
    }

app.include_router(taxonomy.router)
app.include_router(feedback.router)
app.include_router(classify.router)
app.include_router(admin.router)
