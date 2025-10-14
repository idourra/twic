# Plan de Retraining del Clasificador

Objetivo: Alinear el modelo TF-IDF + LogisticRegression con la taxonomía SKOS actual (`data/taxonomy.json`) asegurando que `classifier.class_ids()` sea un subconjunto exacto de los IDs presentes en la taxonomía y que cubra las clases relevantes.

## Resumen

1. Extraer corpus de entrenamiento por clase a partir de labels (prefLabel, altLabel, hiddenLabel) y campos textuales (definition, scopeNote, note, example).
2. Generar ejemplos sintéticos balanceados por clase (data augmentation ligera opcional) para evitar sesgo hacia clases con más sinónimos.
3. Vectorizar con TF-IDF (caracteres + palabras) y entrenar modelo multiclase (one-vs-rest LogisticRegression o LinearSVC probabilístico).
4. Serializar artefactos: `tfidf.joblib`, `lr.joblib`, `classes.joblib` (orden estable).
5. Validar calidad (exact@1, top-k recall) sobre un conjunto de queries sintéticas/feedback si existe.
6. Integrar script reproducible `scripts/retrain_classifier.py`.

## Fuente de Datos

- Archivo: `data/taxonomy.json`.
- Por cada concepto (id):
  - Texto base por idioma: concatenación de `prefLabel[lang]`, todas las `altLabel[lang]`, `hiddenLabel[lang]`, y frases de `definition[lang]`, `scopeNote[lang]`, `note[lang]`, `example[lang]`.
  - Si un campo en `lang` está vacío, fallback a `settings.default_lang`.

## Generación de Corpus

Pseudo procedimiento:

```text
for concept in taxonomy:
  texts = []
  add(prefLabel)
  extend(altLabel, hiddenLabel)
  add(definition, scopeNote, note, example)
  deduplicate, normalize (lower, strip, unicode normalize, opcional stemming ligero)
  if texts vacío -> descartar clase (pero loggear)
```

Opcional: crear variantes combinando label + sinónimo (p.e., "comprar altLabel"). Limitar a N máximos por clase para balance (p.e. 50).

## Balance y Split

- Estrategia mínima viable: usar todo para entrenamiento (no hay ground truth real todavía).
- Generar un pequeño set de validación sintética (10%) mediante muestreo estratificado para comparar modelos si se re-entrena en el futuro.

## Vectorización

- TF-IDF parámetros recomendados iniciales:
  - ngram_range palabras: (1, 2)
  - analyzer="word"
  - min_df=1 (dado corpus pequeño), max_features opcional (20k)
  - norm=l2
  - sublinear_tf=True
- (Opcional) Un segundo TF-IDF char-level ngram_range=(3, 5) y combinar vía FeatureUnion.

## Modelo

- LogisticRegression(solver="liblinear" o "saga" si muchas clases, multi_class="ovr", class_weight="balanced").
- Guardar `classes_` ordenado (list) y usarlo como `classes.joblib` para asegurar mapping fijo en runtime.

## Métricas Iniciales

- Exact@1 sobre validación sintética.
- Cobertura: porcentaje de clases con al menos un ejemplo.
- Distribución de ejemplos por clase (Gini o ratio max/min) para monitor.

## Validación Runtime

Después de serializar:

```python
X = tfidf.transform(["query test"])
proba = lr.predict_proba(X)
assert proba.shape[1] == len(classes)
```

## Integración en Endpoint

- Reemplazar artefactos en `models/` de forma atómica (escribir a `models/tmp` y luego mover) para evitar race conditions en producción.
- Añadir checksum en `/admin/reload` (ya existe) — posible extensión: loggear hashes de modelos.

## Script de Retraining (implementado)

Ver `scripts/retrain_classifier.py` (creado en esta PR) para pipeline ejecutable:

```bash
python scripts/retrain_classifier.py --lang es --max-examples 50
```

## Extensiones Futuras

- Incluir queries reales + feedback etiquetado como datos adicionales.
- Hard negatives: para cada clase, muestrear textos de otras clases similares para robustez.
- Calibración de probabilidades (Platt / isotonic) si se usa umbral de abstención.
- Persistir métricas en JSON (`models/metadata.json`).

## Checklist de Operación

- [ ] Ejecutar retraining script
- [ ] Revisar métricas impresas
- [ ] Sustituir artefactos en `models/`
- [ ] Ejecutar `pytest` y smoke test `/classify`
- [ ] Commit + PR

