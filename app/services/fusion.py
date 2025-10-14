from __future__ import annotations
import numpy as np
from typing import List, Tuple

def combine(
    sem_scores: List[Tuple[str, float]],
    cls_scores: np.ndarray,
    classes: list[str],
    alpha: float,
) -> List[Tuple[str, float]]:
    """
    Fusiona score semántico (retrieval) y score del clasificador.
    sem_scores: lista de (class_id, score_sem)
    cls_scores: vector de scores por clase en el mismo orden que 'classes'
    classes: lista de class_ids que indexa cls_scores
    alpha: peso de score semántico (0..1)
    """
    pos = {cid: i for i, cid in enumerate(classes)}
    out: List[Tuple[str, float]] = []
    for cid, s_sem in sem_scores:
        s_cls = float(cls_scores[pos[cid]]) if cid in pos else 0.0
        s = alpha * s_sem + (1.0 - alpha) * s_cls
        out.append((cid, s))
    out.sort(key=lambda x: x[1], reverse=True)
    return out
