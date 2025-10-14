# Observabilidad y Operación

Este documento describe las métricas, logging estructurado, límites (rate limiting / payload), y cómo extender la observabilidad del servicio de clasificación.

## Resumen

El servicio expone:
- Endpoint `/metrics` (si `ENABLE_METRICS=1`) en formato Prometheus.
- Logging JSON por request con latencia y código de estado.
- Rate limiting tipo token bucket configurable.
- Validación de longitud máxima de query / payload.
- Métricas base: latencia (histogram) y conteo de requests.

Este documento también cubre métricas que vamos a añadir (score máximo, abstenciones por idioma) y endpoints enriquecidos (`/health`).

## Variables de Configuración (settings)

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `ENABLE_METRICS` | Activa exportación Prometheus | `1` |
| `REQUEST_RATE_LIMIT` | Tokens por ventana para IP | `60` |
| `RATE_LIMIT_WINDOW_S` | Longitud ventana (s) | `60` |
| `MAX_QUERY_CHARS` | Longitud máxima de texto a clasificar | `512` |
| `EMBEDDINGS_BACKEND` | `placeholder` o `st` | `placeholder` |
| `EMBEDDINGS_MODEL` | Nombre modelo ST | `sentence-transformers/all-MiniLM-L6-v2` |

## Logging Estructurado

Formato JSON line por request (middleware) con campos sugeridos:
```
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

## Métricas Existentes

| Nombre | Tipo | Labels | Descripción |
|--------|------|--------|-------------|
| `app_requests_total` | Counter | `method`, `path`, `status` | Conteo de requests |
| `app_request_latency_seconds` | Histogram | `method`, `path` | Latencia request |
| `app_abstentions_total` | Counter | (pendiente enriq.) `lang` | Número de respuestas donde el sistema se abstuvo |

## Métricas Planeadas (Quick Win)

| Nombre | Tipo | Labels | Descripción |
|--------|------|--------|-------------|
| `app_classify_score_max` | Histogram | `lang` | Distribución del score máximo devuelto |
| `app_abstentions_total` | Counter | `lang` | Abstenciones segmentadas por idioma |

Buckets recomendados para `score_max`: `[0.0,0.2,0.4,0.6,0.7,0.8,0.85,0.9,0.95,1.0]`.

## Cómo habilitar Prometheus

1. Establecer variable de entorno: `ENABLE_METRICS=1`.
2. Desplegar el servicio.
3. Configurar Prometheus scrape job:
```
- job_name: twic
  scrape_interval: 15s
  static_configs:
    - targets: ['twic:8000']
```
4. Asegurar que `/metrics` no está detrás de auth (actualmente abierto). Si se requiere restricción, introducir middleware o reverse proxy.

## Rate Limiting

Implementación token bucket en memoria por IP:
- Clave: dirección IP (X-Forwarded-For si existe, luego peer).
- Cada ventana de `RATE_LIMIT_WINDOW_S` se reinicia el conteo.
- Responde 429 cuando excedido.
Limitaciones: No distribuido (para múltiples réplicas usar Redis o un gateway).

## Validaciones de Payload / Query

- Límite `MAX_QUERY_CHARS` para evitar queries patológicamente grandes.
- Posible extensión: rechazo de entradas vacías o sólo stopwords (pendiente si se considera necesario).

## Endpoint /health (estado futuro enriquecido)

Se añadirá información JSON:
```
{
  "status": "ok",
  "model_version": "0.1.0",
  "classes": 123,
  "embeddings_dim": 384,
  "last_retraining_ts": "2025-10-10T09:00:00Z",
  "artifacts_present": ["models/tfidf.joblib", "models/lr.joblib"],
  "uptime_s": 123456
}
```
Uso: readiness/liveness en orquestador.

## Feedback Loop

Los archivos JSONL diarios en `data/feedback/YYYY-MM-DD.jsonl` se consolidarán con un script (`scripts/feedback_consolidate.py`) para generar un dataset acumulado y estadísticas:
- Total ejemplos.
- % por idioma.
- % abstenciones corregidas (si se registra). 

## Active Learning

Script (`scripts/select_uncertain.py`) calculará entropía o margen (diferencia entre top1 y top2) para priorizar qué ejemplos mandar a etiquetado humano.

## Extensiones Futuras

- Tracing (OpenTelemetry) para spans de subcomponentes: embeddings, bm25, classifier.
- KL / JS divergence de distribución de clases vs baseline para drift.
- Canary/shadow model para comparar distribución de scores.
- Export a Grafana dashboard JSON versionado.

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
Última actualización: 2025-10-14.
