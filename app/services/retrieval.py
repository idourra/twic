from __future__ import annotations
from typing import List, Tuple
import numpy as np
_index_embeddings: np.ndarray | None = None
_index_ids: List[str] = []
def load_index(embeddings_path: str, ids_path: str) -> None:
    global _index_embeddings, _index_ids
    _index_embeddings = np.load(embeddings_path)
    _index_ids = list(np.load(ids_path, allow_pickle=True))
def embed_query(text: str) -> np.ndarray:
    # Placeholder determinista por hash; reemplaza por embeddings reales cuando quieras
    rng = np.random.default_rng(abs(hash(text)) % 2**32)
    return rng.normal(size=(768,)).astype(np.float32)
def topk(q_emb: np.ndarray, k: int = 20) -> List[Tuple[str, float]]:
    assert _index_embeddings is not None, "Index not loaded"
    sims = (_index_embeddings @ q_emb) / (np.linalg.norm(_index_embeddings, axis=1) * (np.linalg.norm(q_emb)+1e-8))
    idx = np.argsort(-sims)[:k]
    return [(_index_ids[i], float(sims[i])) for i in idx]
