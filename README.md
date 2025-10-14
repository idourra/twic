# twic

MVP de clasificación de intenciones de búsqueda (FastAPI + recuperación híbrida + clasificación).

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

## Próximos pasos

- Añadir workflow CI (pytest + ruff + mypy).
- Integrar importación real de SKOS en pipeline.
- Añadir CHANGELOG y versionado semántico automatizado.
- (Hecho) Fusión híbrida.
- Integrar embeddings reales sentence-transformers.

## Operación & Observabilidad

El servicio incluye:

- Middleware de logging JSON (latencia, código, ruta).
- Rate limiting configurable (token bucket) y validación de longitud de query.
- Endpoint `/metrics` (Prometheus) activable vía `ENABLE_METRICS=1`.
- Métricas base: histogram de latencia y contador de requests.
- Métricas planificadas inmediatas: distribución de `score_max` y abstenciones por idioma.

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

SLO sugerido inicial: p95 latencia < 150 ms, tasa de abstención < 10%.

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

### Health y OpenAPI

Una vez levantado: <http://localhost:8000/docs> (deshabilitar en prod si se requiere).

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


## Contribuir

Lee `CONTRIBUTING.md` y abre un PR.

## Documentación adicional

- **Contrato / SOW del MVP:** ver `docs/CONTRATO_SOW.md` para objetivo, alcance, KPIs y criterios de aceptación.
- **Changelog:** ver `CHANGELOG.md` para historial de versiones (actual 0.1.0 / SOW v1.0).

