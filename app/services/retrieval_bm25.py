from __future__ import annotations
from typing import List, Tuple, Dict
from rank_bm25 import BM25Okapi
import re, json
from pathlib import Path
from app.services import preprocessing

# Pesos por campo (alineables con embeddings)
FIELD_WEIGHTS = {
    "prefLabel": 2.0,
    "altLabel":  1.5,
    "hiddenLabel": 1.2,
    "definition": 1.0,
    "scopeNote":  0.8,
    "note":       0.6,
    "example":    0.8,
    "path":       1.2,
}

_bm25_idx: Dict[str, BM25Okapi] = {}   # lang -> index
_bm25_ids: Dict[str, List[str]] = {}   # lang -> ids

_token = re.compile(r"\w+", flags=re.UNICODE)

def _to_list(field, lang: str) -> List[str]:
    if field is None: return []
    if isinstance(field, dict):
        v = field.get(lang) or field.get("es") or next(iter(field.values()), "")
        if isinstance(v, list): return [str(x) for x in v]
        return [str(v)]
    if isinstance(field, list): return [str(x) for x in field]
    return [str(field)]

def _tokenize(s: str) -> List[str]:
    s = preprocessing.normalize(s)
    return _token.findall(s)

def _doc_pieces(row: dict, lang: str) -> List[str]:
    pieces: List[str] = []
    for fname, w in FIELD_WEIGHTS.items():
        for piece in _to_list(row.get(fname), lang):
            if not piece: continue
            repeat = max(1, int(round(w * 2)))  # ponderación simple por repetición
            pieces.extend([piece] * repeat)
    return pieces or [row.get("id", "")]

def build_or_get(lang: str, taxonomy_path: str = "data/taxonomy.json") -> None:
    if lang in _bm25_idx:
        return
    data = json.loads(Path(taxonomy_path).read_text(encoding="utf-8"))
    docs_tokens: List[List[str]] = []
    ids: List[str] = []
    for row in data:
        ids.append(str(row["id"]))
        tokens: List[str] = []
        for chunk in _doc_pieces(row, lang):
            tokens.extend(_tokenize(chunk))
        docs_tokens.append(tokens if tokens else [""])
    _bm25_ids[lang] = ids
    _bm25_idx[lang] = BM25Okapi(docs_tokens)
    print(f"[bm25] built for lang={lang} docs={len(ids)}")

def reset(lang: str | None = None) -> None:
    if lang is None:
        _bm25_idx.clear(); _bm25_ids.clear()
        print("[bm25] reset all")
    else:
        _bm25_idx.pop(lang, None); _bm25_ids.pop(lang, None)
        print(f"[bm25] reset lang={lang}")

def topk(query: str, lang: str, k: int = 20) -> List[Tuple[str, float]]:
    assert lang in _bm25_idx, "BM25 index not built"
    tok = _tokenize(query)
    scores = _bm25_idx[lang].get_scores(tok)  # numpy array
    if len(scores) == 0:
        return []
    import numpy as np
    idx = np.argsort(-scores)[:k]
    mx = float(scores[idx[0]]) if scores[idx[0]] > 0 else 1.0
    ids = _bm25_ids[lang]
    out: List[Tuple[str, float]] = []
    for i in idx:
        sc = float(scores[i]) / (mx if mx != 0 else 1.0)
        out.append((ids[int(i)], sc))
    return out
