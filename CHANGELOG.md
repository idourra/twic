# Changelog

All notable changes to this project will be documented in this file.

The format roughly follows Keep a Changelog, with semantic version intent (pre-1.0 may introduce breaking changes).

## [0.3.1] - 2025-10-14

### Added

- Archivo `.env.example` con variables clave y comentarios.
- Script `scripts/smoke.sh` para smoke test automatizado (health, ready, classify, taxonomy search/autocomplete, metrics).
- Sección README "MVP Deploy" con pasos rápidos (env, build/run, smoke, observabilidad, checklist).

### Changed

- Versión bump a 0.3.1 (MVP formal) en `pyproject.toml` y `settings`.

### Fixed

- Gauge `twic_taxo_embeddings_cache_size` ahora se expone también cuando `TAXO_W_VEC=0` (valor 0) evitando flakiness en tests y facilitando monitoreo consistente.

### Notes

- Marca el corte de MVP operativo: clasificación híbrida, búsqueda taxonomía (heurística + fuzzy + vector opcional), autocomplete, métricas, readiness, smoke test y supply chain (firma + SBOM) listos.

## [0.3.0] - 2025-10-14


### Added

- Taxonomy fuzzy search con RapidFuzz (partial ratio + peso configurable + umbral mínimo) y fallback cuando no hay coincidencias léxicas.
- Integración de similitud vectorial en búsqueda de taxonomía con matriz precomputada (prefLabel + altLabel) y peso configurable (`TAXO_W_VEC`).
- Endpoint de autocompletado `/taxonomy/autocomplete` con índice de prefijos, búsqueda binaria, caché LRU y métricas.
- Métricas Prometheus específicas de taxonomía: `twic_taxo_search_latency_seconds`, `twic_taxo_search_results_total` (bucketed), `twic_taxo_search_empty_total`, `twic_taxo_embedding_cache_size`.
- Script offline `scripts/eval_taxonomy_search.py` para (N)DCG con relevancia graduada.
- Modelos Pydantic para respuestas de autocompletado.

### Changed

- Heurística de ranking revisada: pesos diferenciados para exact, prefix, substring, altLabel, hidden, path depth, context, similitud vectorial y fuzzy ratio.
- Normalización y preprocesamiento extendidos para queries de taxonomía.

### Fixed

- Conflicto de rutas que provocaba 404 en `/taxonomy/autocomplete` reordenando definición antes de ruta dinámica.
- Fallback fuzzy asegurando candidatos para typos sin coincidencias léxicas.

### Documentation

- README actualizado (fuzzy, autocomplete, métricas de taxonomía, workflow de evaluación, variables de entorno nuevas).

### Internal

- Bump de versión a 0.3.0 (settings y pyproject).

## Unreleased

- Redis rate limiting distribuido (fallback automático a local).
- Toggle de documentación pública (`FASTAPI_ENABLE_DOCS`).
- Métricas HTTP adicionales: `twic_http_429_total`, `twic_http_5xx_total`.
- Workflows CI/CD: `release.yml` (firma cosign + SBOM) y `deploy.yml` (verificación + smoke test + métricas).
- Dashboard Grafana versionado (`docs/grafana/dashboard_twic.json`).
- Firma de imagen Docker (cosign keyless) y generación de SBOM SPDX.
- Actualización de documentación de observabilidad y README con nuevas capacidades.
- Integrar distribución completa de probabilidades del clasificador para mejorar estrategias de incertidumbre. (plan)
- Alerting (p95 latencia, tasa abstención) y dashboards preconfigurados adicionales. (plan)
- Canary/shadow deployment del próximo modelo calibrado. (plan)

## [0.1.0] - 2025-10-14

### Added

- Initial MVP scaffolding (FastAPI app structure `app/`, `scripts/`, `data/`, `models/`).
- SKOS JSON-LD import script (`import_skos_jsonld.py`) producing enriched `taxonomy.json`.
- Taxonomy store with multilingual search and inverted index.
- Embeddings build script (`build_embeddings.py`) for deterministic placeholder embeddings (ES/EN).
- Hybrid retrieval: dense (FAISS placeholder) + BM25 + fusion (triple strategy).
- Classification endpoint with abstention threshold (`TAU_LOW`).
- Feedback endpoint to collect user labeled intents.
- Admin reload endpoint resetting indices and taxonomy cache.
- Retraining script (`retrain_classifier.py`) for TF-IDF + LogisticRegression classifier.
- Dockerfile multi-stage + docker-compose setup.
- CI workflow (pytest, ruff, mypy) and GitHub Flow docs (`CONTRIBUTING.md`).
- SOW documentation (`docs/CONTRATO_SOW.md`) and retraining guide (`docs/retraining.md`).

### Changed

- Classify endpoint hardened: filters stale class IDs, logs discarded concepts, structured logging additions.
- README expanded with Docker usage and retraining instructions.

### Fixed

- KeyError on `/classify` when classifier classes not present in taxonomy (defensive filtering).
- Markdown lint issues in documentation files.

### Security

- Ensured taxonomy / embeddings paths configurable via environment variables.

---

## [0.2.0] - 2025-10-14

### Added (0.2.0)

- Real-time observability docs (`docs/observability.md`) y sección Operación en README.
- Métricas Prometheus adicionales: `twic_classify_score_max{lang}`, `twic_abstentions_total{lang}`.
- Endpoint `/health` enriquecido con artefactos presentes, número de clases y dimensión de embeddings.
- Scripts de ciclo de vida de datos:
  - `feedback_consolidate.py` (consolidación y estadísticas de feedback diario).
  - `select_uncertain.py` (active learning: margin / entropy).
- Módulo `app/observability.py` para centralizar métricas (evita imports circulares).

### Changed (0.2.0)

- `classify` ahora registra abstenciones y distribuye score máximo a histogram (cuando métricas activas).
- TESTS: relajado test de metadata para compatibilidad con artefactos legacy.

### Fixed (0.2.0)

- Eliminado circular import entre `classify` y `main` moviendo métricas a módulo dedicado.
- Lint issues menores en nuevos scripts (imports y longitud líneas).

### Notes

- Esta versión formaliza el pipeline de feedback y sienta bases de active learning.
- Preparado para futura integración de `predict_proba` real y detección de drift.

---
