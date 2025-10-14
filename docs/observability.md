# Observabilidad y Operación

Este documento describe las métricas (Prometheus), logging estructurado, límites (rate limiting local o distribuido), exposición opcional de documentación, firma de imágenes y cómo extender la observabilidad del servicio de clasificación.

## Resumen

El servicio expone:
- Endpoint `/metrics` (si `ENABLE_METRICS=1`) en formato Prometheus.
- Logging JSON por request con latencia y código de estado.
- Rate limiting tipo token bucket configurable en memoria o distribuido vía Redis (`REDIS_URL`).
- Validación de longitud máxima de query / payload.
- Métricas de negocio y técnicas (latencia, requests, score de clasificación, abstenciones, 429, 5xx).
- Toggle para exponer/ocultar documentación OpenAPI (`FASTAPI_ENABLE_DOCS`).
- Endpoint de salud enriquecido `/health`.
- Imagen Docker firmada (workflow de release) con SBOM adjunta.

## Variables de Configuración (settings)

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `ENABLE_METRICS` | Activa exportación Prometheus | `1` |
| `REQUEST_RATE_LIMIT` | Tokens por ventana para IP | `100` |
| `RATE_LIMIT_WINDOW_S` | Longitud ventana (s) | `60` |
| `MAX_QUERY_CHARS` | Longitud máxima de texto a clasificar (aprox *4 bytes) | `512` |
| `EMBEDDINGS_BACKEND` | `placeholder` o `st` | `placeholder` |
| `EMBEDDINGS_MODEL` | Nombre modelo ST | `sentence-transformers/all-MiniLM-L6-v2` |
| `FASTAPI_ENABLE_DOCS` | Exponer `/docs` y `/openapi.json` | `1` |
| `REDIS_URL` | Activar rate limiting distribuido | *(vacío)* |

## Logging Estructurado

Formato JSON line por request (middleware) con campos sugeridos:

```json
{
  "ts": "2025-10-14T12:34:56.789Z",
  "method": "POST",
  "path": "/classify",
  "status": 200,
  "duration_ms": 23.4,
  "rate_limited": false,
  "remote_ip": "203.0.113.10"
}
```
Eventos de clasificación pueden incluir `top_class`, `score_max`, `abstained`.

## Métricas (nomenclatura definitiva)

Prefijo unificado `twic_`.

| Nombre | Tipo | Labels | Descripción |
|--------|------|--------|-------------|
| `twic_requests_total` | Counter | `method`, `path`, `status` | Conteo de requests HTTP |
| `twic_request_latency_seconds` | Histogram | `method`, `path` | Latencia por request |
| `twic_classify_score_max` | Histogram | `lang` | Distribución del score máximo devuelto |
| `twic_abstentions_total` | Counter | `lang` | Abstenciones (clasificador se abstiene) |
| `twic_http_429_total` | Counter | *sin labels* | Respuestas 429 (rate limit) |
| `twic_http_5xx_total` | Counter | *sin labels* | Respuestas 5xx |

Buckets `twic_classify_score_max`: `[0.0,0.2,0.4,0.6,0.7,0.8,0.85,0.9,0.95,0.97,1.0]`.

## Cómo habilitar Prometheus

1. Establecer variable de entorno: `ENABLE_METRICS=1`.
2. Desplegar el servicio.
3. Configurar Prometheus scrape job:

```yaml
- job_name: twic
  scrape_interval: 15s
  static_configs:
    - targets: ['twic:8000']
```

1. Asegurar que `/metrics` no está detrás de auth (actualmente abierto). Si se requiere restricción, introducir middleware o reverse proxy.

## Rate Limiting

Dos modos:

1. Local (in-memory): token bucket reseteado cada ventana (`RATE_LIMIT_WINDOW_S`). Adecuado para desarrollo o instancia única.
2. Distribuido (Redis): definir `REDIS_URL` (e.g. `redis://redis:6379/0`). Se hashéa la IP para la clave y se usa una key por ventana (`rl:<sha1>:<ts_bucket>`).

Notas:
- Fallback automático a modo local si no se puede conectar a Redis en arranque.
- Métrica de saturación indirecta: observar ratio de respuestas 429 sobre total.
- Para proteger detrás de un proxy, garantizar forward de cabeceras IP y (idealmente) introducir un WAF / API Gateway externo para reglas más complejas.

## Validaciones de Payload / Query

- Límite `MAX_QUERY_CHARS` para evitar queries patológicamente grandes.
- Posible extensión: rechazo de entradas vacías o sólo stopwords (pendiente si se considera necesario).

## Endpoint /health

Devuelve información ligera sobre artefactos presentes, número de clases y dimensión de embeddings detectada. Se puede extender para incluir versión de modelo o timestamp de retraining (añadir a `models/metadata.json`). Útil para readiness/liveness.

## Feedback Loop

Los archivos JSONL diarios en `data/feedback/YYYY-MM-DD.jsonl` se consolidarán con un script (`scripts/feedback_consolidate.py`) para generar un dataset acumulado y estadísticas:
- Total ejemplos.
- % por idioma.
- % abstenciones corregidas (si se registra).

## Active Learning

Script (`scripts/select_uncertain.py`) calculará entropía o margen (diferencia entre top1 y top2) para priorizar qué ejemplos mandar a etiquetado humano.

## Firma de Imágenes & Supply Chain

El workflow de release firma la imagen Docker con **cosign (keyless)** y genera un SBOM SPDX (syft). Recomendaciones:
- Verificar firma en pipeline de deploy (`cosign verify`).
- Configurar política de admisión (Kubernetes) que sólo permita imágenes firmadas.
- Archivar SBOMs para escaneo de vulnerabilidades (Grype, Trivy).

## Extensiones Futuras

- Tracing (OpenTelemetry) para spans de embeddings / BM25 / classifier.
- Detección de drift: KL/JS divergence sobre distribución de clases y buckets de score.
- Canary/shadow model para comparar score distributions antes de promover.
- Integración de alertas (Prometheus Alertmanager) para p95, abstention rate y ratio 5xx.

## Buenas Prácticas Operativas

- Registrar hash (md5/sha256) de cada artefacto en metadata del retraining.
- Alertar si `abstention_rate` > umbral definido (ej. 10%) durante 5 minutos.
- Revisar semanalmente bucket de `score_max` para detectar shift (p.ej. aumento de bajas confianzas).
- Programar retraining cuando: (N feedback nuevos >= threshold) OR (drift > delta) OR (edad modelo > X días).

## Seguridad / Privacidad

- Posible anonimización: hash salteado de queries antes de log.
- Política de retención: rotación logs en 30 días, feedback crudo 180 días.

## Checklist de Operación Rápida

1. `/health` responde `status=ok`.
2. `/metrics` expone histogram y counters esperados.
3. Latencia p95 < objetivo (definir SLO, ej. 150 ms).
4. `app_abstentions_total` ratio < 0.1.
5. Sin crecimiento anómalo de tamaño de logs.

---
Última actualización: 2025-10-14 (redis + firma + métricas HTTP).

## Alerting (Prometheus)

Archivo de reglas sugeridas: `deploy/alerts/prometheus-rules.yml`.

Alertas incluidas:

- Latencia p95 > 150ms 5m (`TwicHighLatencyP95`).
- Abstention rate > 10% 10m (`TwicHighAbstentionRate`).
- Tasa absoluta 5xx > 0.05/s 5m (`TwicHighError5xx`).
- Ratio 429 > 2% 10m (`TwicHighRateLimit429`).
- Mean score < 0.55 15m (`TwicLowMeanScore`).

Recomendaciones:

1. Ajustar umbrales tras observar línea base en producción.
2. Añadir rutas de silencio / mantenimiento programado en Alertmanager.
3. Correlacionar `TwicLowMeanScore` con drift de distribución de clases y métricas offline.
4. Añadir anotaciones con enlaces a runbooks (futuros `docs/runbooks/*.md`).
