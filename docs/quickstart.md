# Quickstart

Guía rápida para levantar y usar el servicio de clasificación "twic".

## 1. Requisitos

- Python 3.11+
- (Opcional) Docker / Docker Compose
- (Opcional) Redis si quieres rate limiting distribuido
- `pip install --upgrade pip`

## 2. Instalación local (modo desarrollo)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

(Opcional embeddings reales):

```bash
pip install .[embeddings]
```

## 3. Generar embeddings (placeholder o ST)

Por defecto se usan vectores placeholder ya provistos en `data/`. Para embeddings reales:
```bash
export EMBEDDINGS_BACKEND=st
export EMBEDDINGS_MODEL=sentence-transformers/all-MiniLM-L6-v2
python scripts/build_embeddings.py
```

## 4. Arrancar API

```bash
uvicorn app.main:app --reload --port 8000
```

Visita `/docs` (si `FASTAPI_ENABLE_DOCS=1`), `/health` y `/metrics` (si `ENABLE_METRICS=1`).

Variables clave:

- `FASTAPI_ENABLE_DOCS=0` oculta la documentación
- `ENABLE_METRICS=1` expone Prometheus
- `REDIS_URL=redis://localhost:6379/0` activa rate limit distribuido

## 5. Ejemplo de clasificación

```bash
curl -s -X POST localhost:8000/classify -H 'Content-Type: application/json' \
  -d '{"query":"iphone 13 128gb","lang":"es","top_k":3}' | jq .
```

Respuesta (ejemplo):
```json
{
  "results": [
    {"class_id":"electronics.smartphone","score":0.83},
    {"class_id":"electronics.accessory","score":0.41}
  ],
  "abstained": false,
  "lang": "es"
}
```

## 6. Feedback

Enviar feedback:
```bash
curl -X POST localhost:8000/feedback -H 'Content-Type: application/json' -d '{"query":"iphone 13 128gb","lang":"es","label":"electronics.smartphone"}'
```
Los registros diarios quedan en `data/feedback/YYYY-MM-DD.jsonl`.

## 7. Retraining clasificador

Dry-run:
```bash
python scripts/retrain_classifier.py --lang es --dry-run --max-examples 10
```
Entrenar:
```bash
python scripts/retrain_classifier.py --lang es --max-examples 100
```
Artefactos: `models/tfidf.joblib`, `models/lr.joblib`, `models/classes.joblib`, `models/metadata.json`.

## 8. Docker (rápido)

Build:
```bash
docker build -t twic:dev .
```
Run:
```bash
docker run --rm -p 8000:8000 -e ENABLE_METRICS=1 twic:dev
```
Redis + ocultar docs:
```bash
docker run --rm -p 8000:8000 \
  -e REDIS_URL=redis://host.docker.internal:6379/0 \
  -e FASTAPI_ENABLE_DOCS=0 \
  twic:dev
```

## 9. Docker Compose (prod baseline)

```bash
docker compose -f docker-compose.prod.yaml up --build
```
Incluye healthcheck y usuario no-root.

## 10. Métricas Principales

- `twic_requests_total{method,path,status}`
- `twic_request_latency_seconds_bucket`
- `twic_classify_score_max_bucket{lang}` / `_sum`, `_count`
- `twic_abstentions_total{lang}`
- `twic_http_429_total`, `twic_http_5xx_total`

Dashboard JSON: `docs/grafana/dashboard_twic.json`.

## 11. Alertas

Reglas sugeridas: `deploy/alerts/prometheus-rules.yml` (latencia p95, abstención, 5xx, 429, mean score).

## 12. Salud y Build Metadata

Endpoint `/health` retorna: `version`, `git_sha`, `build_date`, `python_version`, `artifacts`, `classes`, `embeddings_dim`.
Inyectar metadata en build docker:
```bash
docker build --build-arg GIT_SHA=$(git rev-parse HEAD) \
             --build-arg BUILD_DATE=$(date -u +%Y-%m-%dT%H:%M:%SZ) \
             -t twic:dev .
```

## 13. Tests & Lint

```bash
pytest
ruff check .
mypy .
```

## 14. Release (manual)

Crear tag:
```bash
git tag v0.2.1 && git push origin v0.2.1
```
Workflow `release.yml` hará: tests -> build -> push -> firma cosign -> SBOM.

## 15. Deploy (manual vía workflow)

En GitHub Actions > Deploy workflow: indicar `image-tag` y (opcional) `enable-docs=0`, `redis-url`.

## 16. Siguientes Pasos Sugeridos

- Añadir tracing (OpenTelemetry)
- Añadir runbooks para alertas
- Lock reproducible (pip-compile)
- Canary/shadow model

---
¡Listo! Si algo falla revisa logs estructurados en stdout y `/metrics`.
