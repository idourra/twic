# CONTRATO / STATEMENT OF WORK (SOW) – v1.0

**Proyecto:** Green Project – Clasificación automática de intenciones de búsqueda en marketplaces ("TWIC")  
**Cliente:** [Nombre de la empresa]  
**Equipo:** Product Owner (Cliente) + Ingeniero (tú) + Agente Copilot (asistido)  
**Fecha:** 14/oct/2025 (Europe/Madrid)  
**Alcance temporal del SOW:** MVP inicial y primeras iteraciones (8–10 semanas)

_Este documento forma parte del repositorio `twic`. Para guía técnica de instalación ver `README.md`._

---

## 1) Objetivo

Diseñar, implementar y desplegar un **MVP funcional** de un servicio de **clasificación automática de intenciones de búsqueda** de usuarios en un marketplace B2C/B2B, con **alta pertinencia**, baja latencia y **apoyo en una taxonomía canónica SKOS (W3C)** bilingüe (ES/EN). El MVP prioriza **puesta en producción temprana** y **aprendizaje validado** sobre calidad.

### 1.1 KPIs de éxito del MVP

* **Exact@1** (offline, conjunto de validación): >= **0,78** (objetivo), >= 0,72 (mínimo aceptable).
* **p95 de latencia** en endpoint `/classify`: <= **250 ms** en entorno *staging* (payload simple).
* **Tasa de abstención** (predicción nula cuando score < τ): **5–25%** (controlada por `TAU_LOW`).
* **Cobertura multilengua:** ES y EN con **path jerárquico** correcto (construido desde `notation`).
* **Trazabilidad** de decisiones: endpoint de **detalle** `/taxonomy/{id}` y logging básico.

---

## 2) Alcance (Scope)

Incluido en el MVP:

1. **Servicio de API** con **FastAPI (Python)**: endpoints `/health`, `/taxonomy/search`, `/taxonomy/{id}`, `/classify`, `/feedback`, `/admin/reload`.
2. **Ingesta** de **JSON-LD SKOS** (W3C) bilingüe (ES/EN), con soporte a:
   * `prefLabel`, `altLabel`, `hiddenLabel`, `definition`, `scopeNote`, `note`, `example`, `related`, `exactMatch`, `closeMatch`, `broader`, `narrower`, `inScheme`.
   * **Jerarquía dinámica** por `notation` (cada 1–2 caracteres por nivel, profundidad variable).
3. **Búsqueda híbrida**:
   * Denso (embeddings) con **pesos por campo** y por idioma.
   * Léxico **BM25** (rank-bm25) por idioma.
   * **Fusión triple** (sem + bm25 + clf) con pesos `ALPHA_SEM`, `BETA_BM25`, `GAMMA_CLF` y umbral `TAU_LOW`.
4. **Clasificador ligero** (scores) y **abstención** configurable.
5. **Operativa de recarga** sin reiniciar: `/admin/reload` limpia índices (denso/BM25) y el cache de taxonomía.
6. **Tooling**: repositorio GitHub, PRs, flujos de rama, integración con **VSCode** y **GitHub Copilot**.
7. **Comparativa de modelos** (más adelante): compatibilidad para probar **GPT‑5 embeddings** vs. baseline (placeholder determinista), sin vendor lock-in.

Excluido (fuera del MVP, sujeto a alcance futuro):

* UI final para Backoffice/Analítica (se entrega **OpenAPI** + cURL/postman).
* Entrenamiento con datos privados sensibles sin anonimización.
* MLOps completos (CI/CD cloud, autoscaling, feature store) – se deja **base**.

---

## 3) Entregables (Deliverables)

1. **Repositorio** `twic` con:
   * Código Python (FastAPI), estructura modular `app/`, `scripts/`, `data/`, `models/`.
   * **Importador SKOS** (`scripts/import_skos_jsonld.py`).
   * **Construcción de embeddings** enriquecidos (`scripts/build_embeddings.py`).
   * **Servicios**: `taxonomy_store`, `retrieval` (denso), `retrieval_bm25`, `fusion`, `classifier`, `preprocessing`.
   * **Routers**: `health`, `taxonomy`, `taxonomy_detail`, `classify`, `feedback`, `admin`.
   * **Esquemas Pydantic** y `settings` configurables por variables de entorno.
2. **Taxonomía** transformada a `data/taxonomy.json` (bilingüe, expandida) + artefactos `class_embeddings_{es,en}.npy` y `class_ids.npy`.
3. **Documentación**:
   * README con **setup desde cero en Ubuntu**, troubleshooting y *smoke tests*.
   * Especificación OpenAPI (`/docs`), ejemplos cURL, y **guía de operación** (`/admin/reload`).
4. **Paquete de pruebas**: script para **evaluación offline** (Exact@1, p95_ms) y guía de ajuste de hiperparámetros.
5. **Plan de hardening** para pasar de MVP a *staging/prod*.

### 3.1 Criterios de aceptación por entregable

* **API**: Endpoints responden 200 OK; `/classify` devuelve `prediction` o `abstained=true`; soporta `lang=es|en`.
* **Taxonomía**: `path` correcto por `notation`, `broader/narrower` consistentes.
* **Embeddings**: shape `(N, 768)` para ES y EN, donde `N = #conceptos` del `taxonomy.json`.
* **Búsqueda híbrida**: resultados coherentes a consultas de ejemplo (`carne de res`, `beef`) con al menos 1 alternativa relevante.
* **Reload**: llamada a `/admin/reload` resetea índices y refleja nuevos artefactos.

---

## 4) Organización, Roles y Responsabilidades

* **Product Owner (Cliente):** Prioriza backlog/KPIs, provee **SKOS** y ejemplos de queries, valida entregables.
* **Ingeniero + Agente Copilot:** Diseño técnico, implementación, pruebas, documentación, *coaching* de uso.
* **Seguridad/Compliance (Cliente):** Revisión de privacidad, DPA, políticas de datos.

### 4.1 Gobernanza & Rituales

* **Daily** asíncrono en GitHub Issues (10 min).
* **Weekly Review** (30–45 min) con demo y métricas.
* **Board** Kanban: `Backlog → Doing → Review → Done`.

---

## 5) Plan de Trabajo & Hitos (tentativo)

**Duración estimada:** 8 semanas (puede compactarse según disponibilidad).

* **M0 (T0):** Kick-off, infraestructura local (Ubuntu, venv, FastAPI), repositorio GitHub.
* **M1 (T0+1s):** Importador SKOS, `taxonomy.json` válido, `/taxonomy/search` & `/taxonomy/{id}`.
* **M2 (T0+2s):** Embeddings enriquecidos ES/EN + índice BM25; `/classify` (fusión).
* **M3 (T0+3s):** Métricas offline + feedback loop `/feedback`; tuning inicial.
* **M4 (T0+4s):** Endpoint `/admin/reload`, hardening, logging básico.
* **M5 (T0+6s):** Validación con datos reales y KPI gate (Exact@1, p95).
* **M6 (T0+8s):** Preparación *staging/prod*: documentación final, checklist seguridad.

---

## 6) Supuestos y Dependencias

* **Taxonomía canónica SKOS** provista por el Cliente, con `notation` como **ID único jerárquico**.
* Datos de ejemplo (queries + etiqueta esperada) para validación offline.
* Infra local: **Ubuntu**, Python 3.11, **VSCode**, **GitHub/Copilot** disponibles.
* Para comparativas con **GPT‑5** u otros modelos, el Cliente proveerá credenciales y límites de coste.

---

## 7) Exclusiones y Limitaciones

* No se compromete **SLA de producción** en esta etapa (MVP); sí **objetivos internos** de latencia.
* Sin soporte a más idiomas fuera de ES/EN en el MVP (extensible a futuro).
* Embeddings iniciales pueden ser **placeholders deterministas**; el *switch* a GPT‑5 u otro proveedor se hará en una iteración posterior.

---

## 8) Seguridad, Privacidad y Cumplimiento

* La taxonomía y ejemplos no deben contener **datos personales**; si los hubiera, deben estar **anonimizados**.
* El repositorio será privado; se aplicará **gestión de secretos** por variables de entorno.
* Se mantiene un **DPA** y se respetan políticas internas de la compañía.

---

## 9) Propiedad Intelectual

* El **código fuente**, taxonomía y artefactos pertenecen al **Cliente**, con licencia interna.
* Dependencias OSS conservan sus licencias.

---

## 10) Gestión de Cambios

* Cualquier modificación relevante del alcance o KPIs se tramita vía **Change Request** (issue con impacto en esfuerzo/cronograma).

---

## 11) Riesgos Principales & Mitigación

1. **SKOS incompleto o inconsistente** → Validación temprana con el importador y reglas de normalización.
2. **Embeddings de baja calidad** → Tuning de pesos de campo, fusión híbrida, opción a modelo superior (GPT‑5) si KPIs no se alcanzan.
3. **Latencia alta** → Cache, reducción dimensional, top‑k, afinado de BM25 y vectorización.
4. **Desalineación con negocio** → Semanales de revisión con queries reales, feedback loop `/feedback`.

---

## 12) Criterios de Aceptación Global del MVP

* KPIs mínimos alcanzados (Exact@1 ≥ 0,72; p95 ≤ 250 ms; abstención dentro del rango).
* Taxonomía ES/EN funcional con endpoints `/taxonomy/search` y detalle accesible.
* Endpoint `/classify` devuelve predicción o abstención coherente según `TAU_LOW`.
* Reload operativo sin reinicio (`/admin/reload`).
* Logging básico de latencias y descartes de IDs.
* Script de retraining ejecutable y artefactos consistentes.

---

*Firmado digitalmente (aceptación tácita vía pull request / issue tracking).*
