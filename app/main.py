from fastapi import FastAPI, Request
# ruff: noqa: I001
from fastapi.responses import ORJSONResponse, PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware
import time
import json
import os
import joblib
import hashlib
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


class LocalRateLimiter:
    def __init__(self, capacity: int, window_s: int):
        self.capacity = capacity
        self.window_s = window_s
        self.tokens = capacity
        self.refill_ts = time.time()

    def allow(self, key: str) -> bool:  # key ignored locally
        now = time.time()
        if now - self.refill_ts >= self.window_s:
            self.tokens = self.capacity
            self.refill_ts = now
        if self.tokens > 0:
            self.tokens -= 1
            return True
        return False


class RedisRateLimiter:
    def __init__(self, url: str, capacity: int, window_s: int):
        import redis  # type: ignore  # optional dependency

        self.r = redis.Redis.from_url(url, decode_responses=True)
        self.capacity = capacity
        self.window_s = window_s

    def allow(self, key: str) -> bool:
        key_hash = hashlib.sha1(key.encode()).hexdigest()
        bucket = f"rl:{key_hash}:{int(time.time() // self.window_s)}"
        with self.r.pipeline() as pipe:  # type: ignore
            while True:  # optimistic lock
                try:
                    pipe.watch(bucket)
                    current = pipe.get(bucket)
                    current_i = int(current) if current else 0
                    if current_i >= self.capacity:
                        pipe.unwatch()
                        return False
                    pipe.multi()
                    pipe.incr(bucket, 1)
                    pipe.expire(bucket, self.window_s + 1)
                    pipe.execute()
                    return True
                except Exception:  # pragma: no cover
                    time.sleep(0.005)
                    continue


if settings.redis_url:
    try:  # pragma: no cover (network)
        _rate_limiter: object | None = RedisRateLimiter(
            settings.redis_url, settings.request_rate_limit, settings.rate_limit_window_s
        )
    except Exception:  # fallback to local
        _rate_limiter = LocalRateLimiter(settings.request_rate_limit, settings.rate_limit_window_s)
else:
    _rate_limiter = LocalRateLimiter(settings.request_rate_limit, settings.rate_limit_window_s)


class ObservabilityMiddleware(BaseHTTPMiddleware):  # pragma: no cover (integration)
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        if settings.max_query_chars > 0 and request.method == "POST":
            # naive size check for body length (already in memory)
            body_bytes = await request.body()
            if len(body_bytes) > settings.max_query_chars * 4:  # approximate safety margin
                return PlainTextResponse("payload too large", status_code=413)
        # Identify client (basic): IP or fallback to 'global'
        client_ip = request.client.host if request.client else "global"
        if not _rate_limiter.allow(client_ip):  # type: ignore[arg-type]
            if observability.HTTP_429_COUNT:
                observability.HTTP_429_COUNT.inc()
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
            if 500 <= status_code <= 599 and observability.HTTP_5XX_COUNT:
                observability.HTTP_5XX_COUNT.inc()
            # Structured log line
            log_line = json.dumps({
                "event": "http_access",
                "method": request.method,
                "path": request.url.path,
                "status": status_code,
                "latency_ms": int(dur * 1000),
            })
            print(log_line)

docs_url = "/docs" if settings.enable_docs else None
redoc_url = "/redoc" if settings.enable_docs else None
openapi_url = "/openapi.json" if settings.enable_docs else None
app = FastAPI(
    title=settings.api_name,
    version=settings.api_version,
    default_response_class=ORJSONResponse,
    docs_url=docs_url,
    redoc_url=redoc_url,
    openapi_url=openapi_url,
)

# Set static model/app version gauge once at import time
if observability.MODEL_VERSION_INFO:  # pragma: no cover - simple wiring
    try:
        observability.MODEL_VERSION_INFO.labels(
            settings.api_version, settings.git_sha or "unknown"
        ).set(1)
    except Exception:  # safety
        pass

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
        "git_sha": settings.git_sha,
        "build_date": settings.build_date,
        "python_version": __import__("platform").python_version(),
        "artifacts": artifacts,
        "classes": classes_count,
        "embeddings_dim": embeddings_dim,
    }

app.include_router(taxonomy.router)
app.include_router(feedback.router)
app.include_router(classify.router)
app.include_router(admin.router)
