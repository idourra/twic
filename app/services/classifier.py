from __future__ import annotations
import joblib, numpy as np
from pathlib import Path
_tfidf=None; _lr=None; _classes: list[str] = []
def load(models_dir: str) -> None:
    global _tfidf,_lr,_classes
    p=Path(models_dir)
    _tfidf=joblib.load(p/"tfidf.joblib")
    _lr=joblib.load(p/"lr.joblib")
    _classes=list(joblib.load(p/"classes.joblib"))
def scores(text: str) -> np.ndarray:
    assert _tfidf is not None and _lr is not None
    X=_tfidf.transform([text])
    if hasattr(_lr,"decision_function"): s=_lr.decision_function(X)
    else: s=_lr.predict_proba(X)[0]
    if s.ndim==2: s=s[0]
    return s.astype("float32")
def class_ids()->list[str]: return _classes
