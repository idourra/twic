from __future__ import annotations
import math
from typing import List, Tuple, Dict
import numpy as np

def _is_finite(x: float) -> bool:
    return math.isfinite(float(x))

def combine(
    sem_scores: List[Tuple[str, float]],
    cls_scores: np.ndarray,
    classes: list[str],
    alpha: float,
) -> List[Tuple[str, float]]:
    """
    Fusión simple: semántico + clasificador.
    alpha ∈ [0,1] controla el peso del semántico (1.0 = solo sem).
    Robusta a ids faltantes o longitudes distintas.
    """
    alpha = float(alpha)
    if not (0.0 <= alpha <= 1.0):
        alpha = 0.5

    pos: Dict[str, int] = {cid: i for i, cid in enumerate(classes)}
    out: List[Tuple[str, float]] = []

    for cid, s_sem in sem_scores:
        s_sem = float(s_sem)
        if not _is_finite(s_sem):
            continue
        s_cls = 0.0
        j = pos.get(cid)
        if j is not None and 0 <= j < cls_scores.shape[0]:
            v = float(cls_scores[j])
            if _is_finite(v):
                s_cls = v
        s = alpha * s_sem + (1.0 - alpha) * s_cls
        if _is_finite(s):
            out.append((cid, s))

    if not out:
        out = [(cid, float(s)) for cid, s in sem_scores if _is_finite(s)]
    out.sort(key=lambda x: x[1], reverse=True)
    return out

def combine_triple(
    sem_scores: List[Tuple[str, float]],
    bm25_scores: List[Tuple[str, float]],
    cls_scores: np.ndarray,
    classes: list[str],
    w_sem: float, w_bm25: float, w_clf: float
) -> List[Tuple[str, float]]:
    """
    Fusión híbrida: semántico + BM25 + clasificador.
    - Normaliza pesos.
    - Tolera ids que falten en alguna señal.
    - Devuelve lista ordenada (id, score).
    """
    # Normaliza pesos
    ws = max(1e-8, float(w_sem))
    wb = max(1e-8, float(w_bm25))
    wc = max(1e-8, float(w_clf))
    s = ws + wb + wc
    ws, wb, wc = ws / s, wb / s, wc / s

    pos: Dict[str, int] = {cid: i for i, cid in enumerate(classes)}
    sem = {cid: float(sc) for cid, sc in sem_scores if _is_finite(sc)}
    bm  = {cid: float(sc) for cid, sc in bm25_scores if _is_finite(sc)}

    out: List[Tuple[str, float]] = []
    ids = set(sem.keys()) | set(bm.keys()) | set(classes)

    for cid in ids:
        s_sem = sem.get(cid, 0.0)
        s_bm  = bm.get(cid, 0.0)
        s_clf = 0.0
        j = pos.get(cid)
        if j is not None and 0 <= j < cls_scores.shape[0]:
            v = float(cls_scores[j])
            if _is_finite(v):
                s_clf = v
        score = ws * s_sem + wb * s_bm + wc * s_clf
        if _is_finite(score):
            out.append((cid, score))

    out.sort(key=lambda x: x[1], reverse=True)
    return out
