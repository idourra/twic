# Contribuir al proyecto

Usamos GitHub Flow simplificado:

1. Crea una rama desde `main`.
   - Formato sugerido: `feat/<slug>`, `fix/<slug>`, `chore/<slug>`, `docs/<slug>`.
   - Ejemplo: `feat/taxonomy-import-skos`.
2. Commits pequeños y claros (presente imperativo). Prefijo opcional convencional: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`.
3. Abre un Pull Request (PR) temprano (draft) para feedback.
4. Asegura que pase CI (lint, tests) y que añades/actualizas tests cuando cambias comportamiento.
5. Revisión: al menos 1 aprobación (o CODEOWNERS si aplica) antes de merge.
6. Merge siempre vía botón de **Squash & Merge** (historia lineal). Elimina la rama tras merge.

## Branch Protection (main)

La rama `main` debe estar protegida:

- Requerir PR (no pushes directos).
- Requerir status checks: `pytest` (y `ruff` si se añade workflow).
- Requerir al menos 1 review.
- Dismiss stale reviews cuando se hacen nuevos pushes.
- Impedir merge si no pasa `Require branches to be up to date`.

### Estilo de Código

- Python 3.11.
- Linter: `ruff` (añadir workflow futuro).
- Tipado estricto (mypy) para módulos core.

### Tests

- Framework: `pytest`.
- Añade test mínimo para cada bug fix (regresión) o feature crítica.

### Lanzamientos / Versionado

- `pyproject.toml` contiene `version`.
- Etiquetar releases con tags semánticos: `v0.1.0`, `v0.1.1`.
- Actualizar CHANGELOG (pendiente de crear) en cada bump.

## Commits Ejemplos

```text
feat: añadir importador SKOS a taxonomy.json
fix: corregir path de embeddings en settings
docs: describir flujo de clasificación
```

## PR Checklist (resumen)

Incluida también en la plantilla:

- [ ] Código compila / pasa tests
- [ ] Linter limpio / formateo aceptado
- [ ] Tests nuevos o actualizados
- [ ] Documentación actualizada (README / ejemplos)
- [ ] No secrets ni datos sensibles

## Preguntas

Abre un issue con etiqueta `question` o inicia un draft PR si ya hay código.
