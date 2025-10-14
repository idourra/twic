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

## Contribuir

Lee `CONTRIBUTING.md` y abre un PR.

