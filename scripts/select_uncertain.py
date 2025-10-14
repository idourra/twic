#!/usr/bin/env python
"""Selecciona ejemplos (queries) con mayor incertidumbre para etiquetado (Active Learning).

Requiere que el clasificador y vocabulario estén cargables desde `models/`.

Estrategias implementadas:
- margin: diferencia entre probabilidad top1 y top2 (ascendente => más incierto)
- entropy: entropía de la distribución de probabilidades (descendente => más incierto)

Uso:
    python scripts/select_uncertain.py \
        --input data/feedback/feedback_consolidated.jsonl \
        --strategy margin --top 50

Si el archivo de entrada no tiene probabilidades completas, se recalculan con el
clasificador en runtime sobre el texto (`query`).
"""
from __future__ import annotations

import argparse
import json
import math
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services import classifier, preprocessing

@dataclass
class Sample:
    query: str
    lang: str | None
    probs: list[float]
    meta: dict[str, Any]

    def margin(self) -> float:
        if len(self.probs) < 2:
            return 0.0
        p_sorted = sorted(self.probs, reverse=True)
        return p_sorted[0] - p_sorted[1]

    def entropy(self) -> float:
        return -sum(p * math.log(p) for p in self.probs if p > 0)


def iter_rows(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                yield obj


def ensure_probs(q: str) -> list[float]:
    # Usa vectorizador TF-IDF y LR para obtener probs.
    # Implementación: classifier.scores actualmente devuelve mapping id->score (logits agregados).
    # Para active learning se necesita distribución; si no hay `predict_proba` la
    # aproximamos normalizando scores (0..1) obtenidos y asumiendo que el resto de
    # clases tienen prob ~0 (densidad parcial).
    mapping = classifier.scores(preprocessing.normalize(q))
    # mapping: dict[class_id, score]
    scores = list(mapping.values())
    if not scores:
        return []
    total = sum(scores)
    if total <= 0:
        return []
    return [s / total for s in scores]


def select(samples: list[Sample], strategy: str, top: int) -> list[Sample]:
    if strategy == "margin":
        # menor margen primero
        return sorted(samples, key=lambda s: s.margin())[:top]
    if strategy == "entropy":
        return sorted(samples, key=lambda s: s.entropy(), reverse=True)[:top]
    raise ValueError("unknown strategy")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Archivo consolidado (jsonl)")
    ap.add_argument("--strategy", choices=["margin", "entropy"], default="margin")
    ap.add_argument("--top", type=int, default=50, help="Número de ejemplos a devolver")
    ap.add_argument("--output", default="active_selection.jsonl", help="Archivo salida")
    args = ap.parse_args()

    # Carga modelo
    classifier.load("models")

    path = Path(args.input)
    selected: list[Sample] = []
    for row in iter_rows(path):
        q = row.get("query")
        if not q or not isinstance(q, str):
            continue
        probs = ensure_probs(q)
        if len(probs) < 2:
            continue
        selected.append(Sample(query=q, lang=row.get("lang"), probs=probs, meta=row))

    chosen = select(selected, args.strategy, args.top)
    out_path = path.parent / args.output
    with out_path.open("w", encoding="utf-8") as fh:
        for s in chosen:
            record = {
                "query": s.query,
                "lang": s.lang,
                "strategy": args.strategy,
                "margin": s.margin(),
                "entropy": s.entropy(),
                "meta": s.meta,
            }
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(json.dumps({"wrote": out_path.name, "count": len(chosen)}, ensure_ascii=False))

if __name__ == "__main__":  # pragma: no cover
    main()
