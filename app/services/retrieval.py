from __future__ import annotations
# ruff: noqa: I001

import numpy as np

from app.services.embeddings import embed_text

class _RetrievalState:
    embeddings: np.ndarray | None = None
    ids: list[str] = []


_state = _RetrievalState()

def load_index(embeddings_path: str, ids_path: str) -> None:
    _state.embeddings = np.load(embeddings_path)
    _state.ids = list(np.load(ids_path, allow_pickle=True))
    print(
        f"[retrieval] loaded: {embeddings_path} shape={_state.embeddings.shape} "
        f"ids={len(_state.ids)}"
    )

def reset_index() -> None:
    _state.embeddings = None
    _state.ids = []
    print("[retrieval] reset_index()")

def embed_query(text: str) -> np.ndarray:
    return embed_text(text)

def topk(q_emb: np.ndarray, k: int = 20):
    assert _state.embeddings is not None, "Index not loaded"
    den_q = float(np.linalg.norm(q_emb) + 1e-8)
    den_m = np.linalg.norm(_state.embeddings, axis=1) + 1e-8
    sims = (_state.embeddings @ q_emb) / (den_m * den_q)
    idx = np.argsort(-sims)[:k]
    return [(_state.ids[i], float(sims[i])) for i in idx]
