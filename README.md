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

### Health y OpenAPI

Una vez levantado: <http://localhost:8000/docs> (deshabilitar en prod si se requiere).


## Contribuir

Lee `CONTRIBUTING.md` y abre un PR.

