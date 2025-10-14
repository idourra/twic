#!/usr/bin/env python
"""Evaluate taxonomy search relevance using NDCG.

Input: JSONL lines with fields:
{
  "query": "...",
  "lang": "es",            # optional (defaults to settings.default_lang)
  "relevant": ["111007",...] # list of relevant concept IDs (gain=1 each) OR
  "graded": {"111007":3,...} # optional graded relevance overrides (if present)
}

Usage:
  python scripts/eval_taxonomy_search.py --input data/eval_queries.jsonl --k 5 10 --limit 25

Outputs aggregate mean/median NDCG@K, coverage and per-query lines.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean, median

from app.core.settings import settings
from app.services.taxonomy_store import TaxonomyStore


def dcg(relevances: list[float]) -> float:
    import math
    return sum((rel / math.log2(i + 2)) for i, rel in enumerate(relevances))


def ndcg(pred_ids: list[str], rel_map: dict[str, float], k: int) -> float:
    gains = [rel_map.get(pid, 0.0) for pid in pred_ids[:k]]
    ideal = sorted(rel_map.values(), reverse=True)[:k]
    return 0.0 if not any(gains) else dcg(gains) / (dcg(ideal) or 1.0)


def load_queries(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def evaluate(input_path: Path, ks: list[int], limit: int) -> None:
    store = TaxonomyStore(f"{settings.data_dir}/taxonomy.json")
    store.load()
    queries = load_queries(input_path)
    summary = {k: [] for k in ks}
    coverage_counts = {k: 0 for k in ks}

    for row in queries:
        q = row["query"]
        lang = row.get("lang", settings.default_lang)
        graded = row.get("graded")
        relevant = row.get("relevant") or []
        rel_map: dict[str, float] = {}
        if graded:
            rel_map.update({cid: float(score) for cid, score in graded.items()})
        else:
            rel_map.update({cid: 1.0 for cid in relevant})
        results = store.search(q, lang, limit=limit)
        pred_ids = [c.id for c in results]
        for k in ks:
            score = ndcg(pred_ids, rel_map, k)
            summary[k].append(score)
            if any(cid in rel_map for cid in pred_ids[:k]):
                coverage_counts[k] += 1
        print(json.dumps({
            "query": q,
            "lang": lang,
            "pred": pred_ids[:max(ks)],
            **{f"ndcg@{k}": summary[k][-1] for k in ks},
        }, ensure_ascii=False))

    print("--- Aggregate ---")
    out = {}
    for k in ks:
        scores = summary[k]
        out[f"mean@{k}"] = round(mean(scores), 4)
        out[f"median@{k}"] = round(median(scores), 4)
        out[f"coverage@{k}"] = round(coverage_counts[k] / max(len(queries),1), 4)
    print(json.dumps(out, ensure_ascii=False, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Path JSONL queries")
    ap.add_argument("--k", nargs="*", type=int, default=[5,10], help="List of K values")
    ap.add_argument("--limit", type=int, default=25, help="Search limit (>= max K)")
    args = ap.parse_args()
    ks = sorted(set(args.k))
    evaluate(Path(args.input), ks, args.limit)

if __name__ == "__main__":  # pragma: no cover
    main()
