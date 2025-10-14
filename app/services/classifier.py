from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np


class _ClassifierState:
    def __init__(self) -> None:
        self.tfidf = None
        self.model = None
        self.classes: list[str] = []
        self.calibrated: bool = False

    def load(self, models_dir: str) -> None:
        p = Path(models_dir)
        self.tfidf = joblib.load(p / "tfidf.joblib")
        calib_path = p / "lr_calibrated.joblib"
        if calib_path.exists():
            self.model = joblib.load(calib_path)
            self.calibrated = True
        else:
            self.model = joblib.load(p / "lr.joblib")
            self.calibrated = False
        self.classes = list(joblib.load(p / "classes.joblib"))

    def scores(self, text: str) -> np.ndarray:
        assert self.tfidf is not None and self.model is not None
        x_vec = self.tfidf.transform([text])
        if hasattr(self.model, "predict_proba"):
            proba = self.model.predict_proba(x_vec)[0]
            s = proba.astype("float32")
        elif hasattr(self.model, "decision_function"):
            df = self.model.decision_function(x_vec)
            if df.ndim == 1:
                p1 = float(1.0 / (1.0 + np.exp(-df[0])))
                s = np.array([1.0 - p1, p1], dtype="float32")
            else:
                s = df[0].astype("float32")
        else:
            raise RuntimeError("Classifier lacks predict_proba/decision_function")
        if s.shape[0] != len(self.classes):
            if len(self.classes) == 2 and s.shape[0] == 1:
                p1 = float(s[0])
                s = np.array([1.0 - p1, p1], dtype="float32")
            else:
                raise RuntimeError(
                    f"score length {s.shape[0]} != classes {len(self.classes)}"
                )
        return s

    def class_ids(self) -> list[str]:
        return self.classes

    def is_calibrated(self) -> bool:
        return self.calibrated


_state = _ClassifierState()


def load(models_dir: str) -> None:  # public API
    _state.load(models_dir)


def scores(text: str) -> np.ndarray:
    return _state.scores(text)


def class_ids() -> list[str]:
    return _state.class_ids()


def is_calibrated() -> bool:
    return _state.is_calibrated()
