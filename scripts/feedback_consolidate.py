#!/usr/bin/env python
"""Consolida archivos diarios JSONL de feedback en un único dataset agregado y genera estadísticas.

Input: data/feedback/YYYY-MM-DD.jsonl (cada línea: {query, lang, prediction, correct_id?, timestamp?})
Output:
  - data/feedback/feedback_consolidated.jsonl (todas las líneas, ordenadas por timestamp si existe)
  - data/feedback/stats.json (resumen agregado)

Campos esperados por línea (flexible):
  query: str
  lang: str (opcional)
  prediction: str (clase predicha)
  correct_id: str | null (etiqueta correcta si difiere / correción humana)
  score: float (score max del modelo)
  timestamp: ISO8601 | epoch (opcional)

Uso:
  python scripts/feedback_consolidate.py --data-dir data/feedback

Se ignoran archivos que no cumplan patrón YYYY-MM-DD.jsonl.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.jsonl$")

@dataclass
class FeedbackRow:
    raw: dict[str, Any]

    @property
    def timestamp(self) -> float:
        ts = self.raw.get("timestamp")
        if ts is None:
            return 0.0
        if isinstance(ts, (int, float)):
            return float(ts)
        if isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
            except ValueError:  # formato inválido
                return 0.0
        return 0.0

    def to_json(self) -> str:
        return json.dumps(self.raw, ensure_ascii=False)


def iter_feedback_files(dir_path: Path) -> Iterable[Path]:
    for p in dir_path.glob("*.jsonl"):
        if DATE_RE.match(p.name):
            yield p


def parse_lines(path: Path) -> Iterable[FeedbackRow]:
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    yield FeedbackRow(obj)
            except json.JSONDecodeError:
                continue


def consolidate(feedback_dir: Path) -> tuple[list[FeedbackRow], dict[str, Any]]:
    rows: list[FeedbackRow] = []
    for file in iter_feedback_files(feedback_dir):
        rows.extend(parse_lines(file))
    rows.sort(key=lambda r: r.timestamp)

    total = len(rows)
    langs = Counter(r.raw.get("lang", "?") for r in rows)
    has_correction = [r for r in rows if r.raw.get("correct_id")]
    corrected = sum(1 for r in has_correction if r.raw.get("correct_id") != r.raw.get("prediction"))
    abstentions = sum(1 for r in rows if r.raw.get("prediction") is None)

    scores = [r.raw.get("score") for r in rows if isinstance(r.raw.get("score"), (int, float))]
    avg_score = sum(scores) / len(scores) if scores else None

    stats = {
        "total_rows": total,
        "languages": dict(langs),
        "with_correction_field": len(has_correction),
        "corrections_changed": corrected,
        "abstentions": abstentions,
        "abstention_rate": abstentions / total if total else None,
        "avg_score": avg_score,
    }
    return rows, stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data/feedback", help="Directorio de feedback diario")
    ap.add_argument(
        "--output",
        default="feedback_consolidated.jsonl",
        help="Nombre archivo consolidado",
    )
    args = ap.parse_args()

    feedback_dir = Path(args.data_dir)
    feedback_dir.mkdir(parents=True, exist_ok=True)

    rows, stats = consolidate(feedback_dir)

    consolidated_path = feedback_dir / args.output
    with consolidated_path.open("w", encoding="utf-8") as out:
        for r in rows:
            out.write(r.to_json() + "\n")

    with (feedback_dir / "stats.json").open("w", encoding="utf-8") as fh:
        json.dump(stats, fh, indent=2, ensure_ascii=False)

    print(json.dumps({"wrote": consolidated_path.name, "rows": len(rows)}, ensure_ascii=False))

if __name__ == "__main__":  # pragma: no cover
    main()
