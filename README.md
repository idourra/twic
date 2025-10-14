# twic

Servicio de clasificación de intenciones de búsqueda (FastAPI + recuperación híbrida + clasificación) con observabilidad, rate limiting distribuido opcional y cadena de suministro firmada.

> Guía rápida: ver `docs/quickstart.md` para instalar, ejecutar, clasificar, métricas y release.
> Runbooks operativos: `docs/runbooks/` (latency, abstention, errors, rate_limit, low_score)
> Herramienta batch CLI: `scripts/cli_classify.py` para clasificar archivos masivos.

## Flujo de Trabajo (GitHub Flow)

Usamos GitHub Flow:

1. Crear rama desde `main` (`feat/…`, `fix/…`).
2. Commits pequeños y claros.
3. Pull Request (draft temprano) → revisión.
4. CI verde (tests + lint) → squash & merge a `main`.
5. Eliminar rama.

Ver detalles en `CONTRIBUTING.md`.

## Estructura (resumen)

```text
app/            # FastAPI endpoints, servicios
data/           # Artefactos de taxonomía y embeddings
models/         # Modelos ML serializados
scripts/        # Utilidades (importar SKOS, entrenar, embeddings)
```

## Roadmap (extracto histórico)

- MVP inicial (fusión híbrida y endpoints básicos)
- Métricas y logging estructurado
- Calibración opcional y métricas offline
- Feedback loop + active learning (scripts)
- Release 0.2.0 (tag y CHANGELOG)
- Hardening Docker + compose prod + smoke test
- Rate limiting distribuido (Redis) + toggle docs (`FASTAPI_ENABLE_DOCS`)
- Workflows: release (build + firma cosign + SBOM) y deploy con smoke test

Próximos candidatos:

- Tracing (OpenTelemetry)
- Detección de drift y alertas Prometheus

## Operación & Observabilidad

Incluye:

- Middleware de logging JSON (latencia, código, ruta).
- Rate limiting local en memoria o distribuido via Redis (`REDIS_URL`).
- Toggle de documentación: `FASTAPI_ENABLE_DOCS=0` para ocultar `/docs` y `/openapi.json` en producción.
- Endpoint `/metrics` (Prometheus) activable vía `ENABLE_METRICS=1`.
- Métricas: `twic_requests_total`, `twic_request_latency_seconds`, `twic_classify_score_max`, `twic_abstentions_total`, `twic_http_429_total`, `twic_http_5xx_total`, `twic_feedback_total{type}`, `twic_unknown_queries_total{lang}`, `twic_model_version_info{version,git_sha}`.
  - `twic_feedback_total{type}`: tipos: `correction` (sistema abstiene y usuario aporta), `override` (usuario reemplaza predicción), `confirm` (usuario confirma), `generic` (otros casos).
  - `twic_unknown_queries_total{lang}`: consultas con abstención (proxy de intents desconocidos / gap de cobertura).
  - `twic_model_version_info{version,git_sha}`: gauge estático (=1) etiquetado para correlacionar métricas con despliegues.
  - Cobertura aproximada = 1 - rate(twic_abstentions_total{lang}) / rate(twic_requests_total{path="/classify",status=~"200.*"}).
- Dashboard Grafana JSON en `docs/grafana/dashboard_twic.json`.
- Imagen Docker firmada (cosign keyless) + SBOM (workflow release).

Referencias detalladas y buenas prácticas en `docs/observability.md`.

Ejemplo de arranque con métricas:

```bash
ENABLE_METRICS=1 uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Scrape config Prometheus mínima:

```yaml
- job_name: twic
  static_configs:
    - targets: ['localhost:8000']
```

SLO sugerido inicial: p95 latencia < 150 ms, tasa de abstención < 10%, 429 rate bajo (<2% de requests), 5xx < 0.5%.

### Búsqueda de taxonomía (ranking actual)

El endpoint `/taxonomy/search` ahora aplica:

1. Normalización extendida (Unicode NFKC, lowercase, remover acentos, colapsar no alfanum, singularización naïve de plurales simples).
2. Scoring heurístico por concepto usando pesos configurables vía variables de entorno:
  - `TAXO_W_EXACT` (default 100): match exacto de `prefLabel`.
  - `TAXO_W_PREFIX` (60): `prefLabel` inicia con la query.
  - `TAXO_W_SUBSTRING` (40): substring en `prefLabel`.
  - `TAXO_W_ALT` (30): coincidence en `altLabel`.
  - `TAXO_W_HIDDEN` (20): `hiddenLabel`.
  - `TAXO_W_PATH` (10): cualquier segmento de la ruta jerárquica.
  - `TAXO_W_CONTEXT` (5): definición / scope / note / example.
  - `TAXO_W_VEC` (0): peso de similitud vectorial (si >0 calcula embeddings de `prefLabel`).
3. Fuzzy matching opcional (RapidFuzz `partial_ratio`) ponderado por `TAXO_W_FUZZY` si >0 y mínimo ratio `TAXO_FUZZY_MIN_RATIO` (default 70). Aumenta el score proporcionalmente al ratio (ratio/100 * peso).
4. Combinación opcional con similitud vectorial coseno (normalizada a [0,1]) si `TAXO_W_VEC>0` (usa embeddings precomputados de `prefLabel` y `altLabel`).
5. Orden final por score descendente y, en caso de empate, por longitud (más corta primero).
6. Límite de resultados controlado por `limit` (query param) o `TAXO_TOP_K` (default 25).

Ejemplo:

```bash
curl -s 'http://localhost:8000/taxonomy/search?q=chocolates&lang=es&limit=5' | jq .
```

Para habilitar señal vectorial (si embeddings reales están activos):

```bash
export TAXO_W_VEC=15
uvicorn app.main:app
```

Nuevos pesos y variables relevantes:

| Variable | Descripción | Default |
|----------|-------------|---------|
| `TAXO_W_FUZZY` | Peso adicional fuzzy ratio | 0 |
| `TAXO_FUZZY_MIN_RATIO` | Ratio mínimo (0-100) para sumar fuzzy | 70 |
| `TAXO_TOP_K` | Máximo de resultados por defecto | 25 |

Recomendación: ajustar pesos tras observar métricas de CTR, feedback y NDCG offline.

#### Autocomplete

Endpoint: `/taxonomy/autocomplete?q=<prefijo>&lang=es&limit=15`

Características:

- Índice precomputado de `prefLabel` y `altLabel` normalizados.
- Búsqueda por prefix (binary search) + orden: `prefLabel` primero, luego `altLabel`, priorizando longitudes más cortas.
- Cache LRU en memoria (tamaño 256) por `(lang, query_norm, limit)`.
- Métricas etiquetadas `source="autocomplete"`.

Ejemplo:

```bash
curl -s 'http://localhost:8000/taxonomy/autocomplete?q=choc&lang=es&limit=5' | jq .
```

Respuesta:

```json
{
  "results": [
    {"id": "111007", "label": "Chocolates y bombones", "kind": "pref"},
    {"id": "111007", "label": "Bombones", "kind": "alt"}
  ]
}
```

#### Métricas específicas de búsqueda/Autocomplete

Se añaden (todas con cardinalidad controlada):

| Métrica | Tipo | Labels | Descripción |
|---------|------|--------|-------------|
| `twic_taxo_search_latency_seconds` | Histogram | `lang`, `source` | Latencia de búsqueda/autocomplete |
| `twic_taxo_search_results_total` | Counter | `lang`, `source`, `bucket` | Distribución de tamaños (buckets: 0,1_5,6_10,gt_10) |
| `twic_taxo_search_empty_total` | Counter | `lang`, `source` | Búsquedas sin resultados |
| `twic_taxo_embeddings_cache_size` | Gauge | `lang` | Nº de embeddings precomputados (pref+alt) |

Ejemplos PromQL:

```promql
# p95 latencia búsqueda (últimos 5m)
histogram_quantile(0.95, sum by (le) (rate(twic_taxo_search_latency_seconds_bucket{source="search"}[5m])))

# Tasa de vacíos autocomplete vs búsqueda (1h)
sum(rate(twic_taxo_search_empty_total{source="autocomplete"}[1h])) / sum(rate(twic_taxo_search_results_total{source="autocomplete",bucket!="0"}[1h]))
```

#### Evaluación offline (NDCG)

Script: `scripts/eval_taxonomy_search.py`

Formato JSONL entrada (una línea por query):

```json
{"query": "chocolates", "lang": "es", "relevant": ["111007"]}
{"query": "gaseosa cola", "relevant": ["110501"]}
{"query": "bombons", "graded": {"111007": 3, "111099": 1}}
```

Ejecución:

```bash
python scripts/eval_taxonomy_search.py --input data/eval_queries.jsonl --k 5 10 --limit 25 > ndcg_out.jsonl
```

Salida mezcla líneas por query + bloque agregado final (`mean@K`, `median@K`, `coverage@K`). Usar para comparar ajustes de pesos (`TAXO_W_*`) y thresholds fuzzy.

## Docker

### Build

```bash
docker build -t twic:latest .
```

### Run simple

```bash
docker run --rm -p 8000:8000 twic:latest
```

### docker-compose

```bash
docker compose up --build
```

Esto monta `./data` como volumen para poder regenerar embeddings sin reconstruir la imagen.

Para desarrollo interactivo con hot reload y Redis opcional, existe `docker-compose.override.yaml` que expone el código como volumen y ejecuta `uvicorn --reload`.

### Desarrollo (hot reload)

Para desarrollo puedes usar uvicorn directamente:

```bash
uvicorn app.main:app --reload --port 8000
```

### Variables de entorno relevantes

| Variable | Descripción | Default |
|----------|-------------|---------|
| MODELS_DIR | Carpeta de modelos | models |
| DATA_DIR | Carpeta de datos (taxonomy, embeddings) | data |
| DEFAULT_LANG | Idioma por defecto | es |
| EMBEDDINGS_BACKEND | placeholder o st (sentence-transformers) | placeholder |
| EMBEDDINGS_MODEL | Nombre del modelo ST | sentence-transformers/all-MiniLM-L6-v2 |
| FASTAPI_ENABLE_DOCS | Exponer docs/openapi | 1 |
| REDIS_URL | Activar rate limiting distribuido | (vacío) |
| ENABLE_METRICS | Exponer /metrics | 1 |
| REQUEST_RATE_LIMIT | Tokens por ventana para rate limiting local/distribuido | 100 |
| RATE_LIMIT_WINDOW_S | Ventana (s) para rate limiting | 60 |
| TAXO_W_FUZZY | Peso fuzzy ratio | 0 |
| TAXO_FUZZY_MIN_RATIO | Mínimo ratio fuzzy | 70 |
| TAXO_TOP_K | Top-K por defecto taxonomía | 25 |

### Health y OpenAPI

Una vez levantado: <http://localhost:8000/docs> (controlado por `FASTAPI_ENABLE_DOCS`).

### Health enriquecido

`/health` devuelve ahora:

```jsonc
{
  "status": "ok",
  "version": "0.2.1",
  "git_sha": "<commit>",
  "build_date": "2025-10-14T12:34:56Z", // si se inyecta BUILD_DATE
  "python_version": "3.11.9",
  "artifacts": ["tfidf.joblib","lr.joblib"],
  "classes": 123,
  "embeddings_dim": 384
}
```

Inyectar variables en build/run:

```bash
export GIT_SHA=$(git rev-parse HEAD)
export BUILD_DATE=$(date -u +%Y-%m-%dT%H:%M:%SZ)
ENABLE_METRICS=1 GIT_SHA=$GIT_SHA BUILD_DATE=$BUILD_DATE uvicorn app.main:app
```

## Retraining del Clasificador

El clasificador (TF-IDF + LogisticRegression) se puede regenerar a partir de la taxonomía actual:

1. Asegura que `data/taxonomy.json` está actualizado (usar script SKOS si cambia la fuente).
1. Ejecuta en modo inspección (sin escribir artefactos):

```bash
python scripts/retrain_classifier.py --lang es --dry-run --max-examples 10
```

1. Ejecuta retraining real:

```bash
python scripts/retrain_classifier.py --lang es --max-examples 10
```

1. Revisa `models/metadata.json` para métricas y parámetros.
2. (Opcional) Ajusta hiperparámetros: añade `--char-ngrams` para mezclar ngramas de caracteres o cambia `--max-examples` para balance.
3. Smoke test endpoint:

```bash
uvicorn app.main:app --reload &
curl -s -X POST localhost:8000/classify -H 'Content-Type: application/json' \\
  -d '{"query":"iphone 13 128gb","lang":"es","top_k":3}' | jq .
```

Artefactos generados:

- `models/tfidf.joblib`
- `models/lr.joblib`
- `models/classes.joblib`
- `models/metadata.json`

Detalles más extensos en `docs/retraining.md`.

### Clasificación batch (offline)

Para procesar un archivo grande de consultas y obtener predicciones JSONL:

```bash
python scripts/cli_classify.py --input queries.txt --output results.jsonl --url http://localhost:8000 --lang es --top-k 5 --concurrency 16 --max-rps 50
```

`queries.txt` puede ser:

- Texto plano (una consulta por línea)
- JSONL con un campo `query` (otras claves se ignoran)

Salida: un JSONL con cada línea conteniendo campos originales más `prediction`, `alternatives`, `abstained`, `latency_ms`.

### Opciones avanzadas de retraining

Flags clave adicionales:

| Flag | Descripción |
|------|-------------|
| `--max-iter` | Iteraciones máximas de LogisticRegression (por defecto 300) |
| `--calibration {none,platt,isotonic}` | Calibración de probabilidades (Platt=sigmoid) |
| `--cv-folds` | Folds internos para calibración (default 3) |
| `--tau-low` | Umbral para metric coverage@tau offline |
| `--char-ngrams` | Activa mezcla de ngramas de caracteres |

Cuando se usa calibración y se genera un modelo calibrado se guarda `lr_calibrated.joblib` y se prioriza su carga en runtime.

## Embeddings reales (opcional)

Por defecto se usa un backend determinista de placeholder (vectores aleatorios reproducibles) para simplicidad y velocidad.

Para activar embeddings reales con sentence-transformers:

1. Instala dependencia opcional:

```bash
pip install .[embeddings]
```

1. Exporta variables y regenera embeddings:

```bash
export EMBEDDINGS_BACKEND=st
export EMBEDDINGS_MODEL=sentence-transformers/all-MiniLM-L6-v2
python scripts/build_embeddings.py
```

1. Arranca la API (cargará el mismo backend automáticamente):

```bash
uvicorn app.main:app --reload
```

Fallback automático: si falla la importación o carga del modelo, el sistema imprime un aviso y vuelve a `placeholder` sin romper el flujo.

## Release & Deploy

Workflows en `.github/workflows/`:

- `release.yml`: Ejecuta lint + tests, construye imagen, la sube a GHCR, firma con cosign (keyless) y genera SBOM SPDX.
- `deploy.yml`: Verifica firma, arranca contenedor, ejecuta `scripts/smoke.py` y valida `/metrics`.

Para lanzar un release: crear tag `vX.Y.Z` (p.ej. `git tag v0.2.1 && git push origin v0.2.1`).

Verificación local de firma (suponiendo cosign instalado):

```bash
cosign verify ghcr.io/<owner>/<repo>:0.2.0
```

## Reproducibilidad de dependencias

Se incluye `requirements.lock` con un snapshot de versiones. Para instalar exactamente esas versiones:

```bash
pip install -r requirements.lock
```

Para regenerar (tras actualizar `pyproject.toml`):

```bash
pip install .[embeddings,dev]
pip freeze --exclude-editable > requirements.lock
```

Alternativa futura: uso de `pip-tools` (`pip-compile`) para resolución determinista.

### Consultas Prometheus útiles (business KPIs)

```promql
# Cobertura (1 - tasa abstención) por idioma (window 1h)
1 - (sum by (lang) (rate(twic_abstentions_total[1h])) / sum by (lang) (rate(twic_requests_total{path="/classify",status=~"200.*"}[1h])))

# Feedback por tipo (últimas 24h)
sum by (type) (increase(twic_feedback_total[24h]))

# Unknown queries ratio (abstenciones / requests) 24h
sum(rate(twic_unknown_queries_total[24h])) / sum(rate(twic_requests_total{path="/classify",status=~"200.*"}[24h]))

# Despliegues recientes (gauge etiquetado)
twic_model_version_info
```


## Contribuir

Lee `CONTRIBUTING.md` y abre un PR.

## Documentación adicional

- **Contrato / SOW del MVP:** ver `docs/CONTRATO_SOW.md` para objetivo, alcance, KPIs y criterios de aceptación.
- **Changelog:** ver `CHANGELOG.md` para historial de versiones (actual 0.2.1).
- **Runbooks:** `docs/runbooks/*.md` para respuesta a alertas (latencia, 5xx, abstención, score bajo, 429).

