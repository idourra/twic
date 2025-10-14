#!/usr/bin/env python
"""Retrain TF-IDF + LogisticRegression classifier from taxonomy.json.

Usage (basic):
  python scripts/retrain_classifier.py --lang es

Features:
  - Builds per-class text corpus from taxonomy fields.
  - Optional cap per class (--max-examples) for balance.
  - Word ngram TF-IDF plus optional char ngrams (--char-ngrams).
  - Saves artifacts atomically (tmp -> move) to avoid race.
  - Writes metadata JSON with metrics & parameters.
  - Dry-run mode to inspect stats without writing.
"""
from __future__ import annotations
# ruff: noqa: I001

import argparse
import json
import random
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass, asdict
from pathlib import Path

import joblib
import numpy as np

from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import FeatureUnion

TAU_DEFAULT = 0.4

RANDOM_SEED = 42
random.seed(RANDOM_SEED)

FIELDS_MULTI = ["altLabel", "hiddenLabel"]
FIELDS_SINGLE = ["prefLabel", "definition", "scopeNote", "note", "example"]

@dataclass
class RetrainConfig:
    lang: str
    data_dir: str
    models_dir: str
    max_examples: int | None
    char_ngrams: bool
    test_size: float
    dry_run: bool
    min_len: int
    max_iter: int
    calibration: str  # none|platt|isotonic
    cv_folds: int
    tau_low: float

@dataclass
class RetrainStats:
    n_classes: int
    classes_with_text: int
    total_texts: int
    avg_texts_per_class: float
    max_texts_per_class: int
    min_texts_per_class: int
    accuracy_val: float | None
    macro_f1_val: float | None
    coverage_at_tau: float | None
    train_time_s: float
    vocab_size: int
    calibrated: bool
    calibration_method: str | None
    cv_folds: int | None
    convergence_warn: bool


def load_taxonomy(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def collect_texts(
    taxonomy: list[dict],
    lang: str,
    default_lang: str,
    cfg: RetrainConfig,
) -> tuple[list[str], list[str]]:
    x_texts: list[str] = []
    y: list[str] = []
    rng = random.Random(RANDOM_SEED)
    for row in taxonomy:
        cid = str(row.get("id"))
        texts: list[str] = []
        # Single fields
        for f in FIELDS_SINGLE:
            block = row.get(f) or {}
            if isinstance(block, dict):
                val = block.get(lang) or block.get(default_lang)
                if isinstance(val, str) and val.strip():
                    texts.append(val.strip())
            elif isinstance(block, str) and block.strip():  # legacy possibility
                texts.append(block.strip())
        # Multi fields
        for f in FIELDS_MULTI:
            block = row.get(f) or {}
            if isinstance(block, dict):
                arr = block.get(lang) or block.get(default_lang)
                if isinstance(arr, list):
                    for v in arr:
                        if isinstance(v, str) and v.strip():
                            texts.append(v.strip())
        # Deduplicate & basic normalize
        normed = []
        seen = set()
        for t in texts:
            t2 = t.lower().strip()
            if len(t2) < cfg.min_len:
                continue
            if t2 not in seen:
                seen.add(t2)
                normed.append(t2)
        if not normed:
            continue
        # Balance cap
        if cfg.max_examples and len(normed) > cfg.max_examples:
            normed = rng.sample(normed, cfg.max_examples)
        x_texts.extend(normed)
        y.extend([cid] * len(normed))
    return x_texts, y


def build_vectorizer(cfg: RetrainConfig):
    word = TfidfVectorizer(
        ngram_range=(1, 2), analyzer="word", min_df=1, sublinear_tf=True, norm="l2"
    )
    if not cfg.char_ngrams:
        return word
    char = TfidfVectorizer(
        ngram_range=(3, 5), analyzer="char", min_df=1, sublinear_tf=True, norm="l2"
    )
    return FeatureUnion([
        ("w", word),
        ("c", char),
    ])


def train_model(
    x_texts: list[str], y: list[str], cfg: RetrainConfig
) -> tuple[object, object, RetrainStats]:
    classes = sorted({c for c in y})
    n_classes = len(classes)
    vectorizer = build_vectorizer(cfg)
    x_vec = vectorizer.fit_transform(x_texts)
    vocab_size = x_vec.shape[1]

    # Train/val split (stratified if viable)
    if cfg.test_size > 0 and n_classes > 1:
        try:
            x_tr, x_va, y_tr, y_va = train_test_split(
                x_vec, y, test_size=cfg.test_size, random_state=RANDOM_SEED, stratify=y
            )
        except ValueError:
            x_tr, x_va, y_tr, y_va = x_vec, None, y, None
    else:
        x_tr, x_va, y_tr, y_va = x_vec, None, y, None

    clf = LogisticRegression(
        solver="liblinear" if n_classes < 50 else "saga",
        multi_class="ovr",
        class_weight="balanced",
        max_iter=cfg.max_iter,
        n_jobs=1,
        random_state=RANDOM_SEED,
    )

    t0 = time.time()
    convergence_warn = False
    try:
        clf.fit(x_tr, y_tr)
    except (ValueError, RuntimeError) as e:
        print(f"[WARN] LogisticRegression fit raised {e}")
        convergence_warn = True
    train_time = time.time() - t0

    acc = None
    macro_f1 = None
    coverage = None
    if x_va is not None and y_va is not None:
        preds = clf.predict(x_va)
        acc = float(accuracy_score(y_va, preds))
        try:
            macro_f1 = float(f1_score(y_va, preds, average="macro"))
        except ValueError:
            macro_f1 = None
        if hasattr(clf, "predict_proba"):
            proba = clf.predict_proba(x_va)
            top = proba.max(axis=1)
            coverage = float((top >= cfg.tau_low).mean())

    counts: dict[str, int] = {}
    for cid in y:
        counts[cid] = counts.get(cid, 0) + 1
    per_class_vals = list(counts.values())

    calibrated = False
    calibration_method: str | None = None
    cv_used: int | None = None
    # Calibration (after base training & validation split) to avoid leakage
    if cfg.calibration in {"platt", "isotonic"}:
        method = "sigmoid" if cfg.calibration == "platt" else "isotonic"
        if x_va is not None and y_va is not None:
            base_est = clf
            calib = CalibratedClassifierCV(base_est, method=method, cv=cfg.cv_folds)
            t1 = time.time()
            calib.fit(x_tr, y_tr)  # uses internal CV
            train_time += time.time() - t1
            clf = calib  # type: ignore
            calibrated = True
            calibration_method = cfg.calibration
            cv_used = cfg.cv_folds
            # recompute metrics with calibrated probs if possible
            if x_va is not None and y_va is not None and hasattr(clf, "predict"):
                preds = clf.predict(x_va)
                try:
                    acc = float(accuracy_score(y_va, preds))
                    macro_f1 = float(f1_score(y_va, preds, average="macro"))
                except ValueError:
                    pass
                if hasattr(clf, "predict_proba"):
                    proba = clf.predict_proba(x_va)
                    top = proba.max(axis=1)
                    coverage = float((top >= cfg.tau_low).mean())

    stats = RetrainStats(
        n_classes=n_classes,
        classes_with_text=n_classes,
        total_texts=len(y),
        avg_texts_per_class=float(np.mean(per_class_vals)) if per_class_vals else 0.0,
        max_texts_per_class=max(per_class_vals) if per_class_vals else 0,
        min_texts_per_class=min(per_class_vals) if per_class_vals else 0,
        accuracy_val=acc,
        macro_f1_val=macro_f1,
        coverage_at_tau=coverage,
        train_time_s=float(train_time),
        vocab_size=vocab_size,
        calibrated=calibrated,
        calibration_method=calibration_method,
        cv_folds=cv_used,
        convergence_warn=convergence_warn,
    )

    return vectorizer, clf, stats


def atomic_save(
    models_dir: Path,
    vectorizer,
    clf,
    classes: list[str],
    stats: RetrainStats,
    cfg: RetrainConfig,
):
    tmp = Path(tempfile.mkdtemp(prefix="retrain_tmp_"))
    try:
        joblib.dump(vectorizer, tmp / "tfidf.joblib")
        # Choose filename based on calibration
        if (
            hasattr(clf, "classes_")
            and hasattr(clf, "predict_proba")
            and not isinstance(clf, LogisticRegression)
        ):
            joblib.dump(clf, tmp / "lr_calibrated.joblib")
        else:
            joblib.dump(clf, tmp / "lr.joblib")
        joblib.dump(classes, tmp / "classes.joblib")
        meta = {
            "stats": asdict(stats),
            "config": asdict(cfg),
            "classes_checksum": hash(tuple(classes)),
        }
        (tmp / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        # Move
        models_dir.mkdir(parents=True, exist_ok=True)
        for fname in ["tfidf.joblib", "lr.joblib", "classes.joblib", "metadata.json"]:
            shutil.move(str(tmp / fname), str(models_dir / fname))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def parse_args() -> RetrainConfig:
    p = argparse.ArgumentParser()
    p.add_argument("--lang", default="es", help="Idioma principal (prefLabel, etc.)")
    p.add_argument("--data-dir", default="data", help="Directorio con taxonomy.json")
    p.add_argument("--models-dir", default="models", help="Salida de artefactos")
    p.add_argument(
        "--max-examples",
        type=int,
        default=50,
        help="Máximo ejemplos por clase (0 = ilimitado)",
    )
    p.add_argument("--char-ngrams", action="store_true", help="Añade TF-IDF de caracteres")
    p.add_argument("--test-size", type=float, default=0.1, help="Fracción validación (0 desactiva)")
    p.add_argument("--dry-run", action="store_true", help="No escribe modelos, solo muestra stats")
    p.add_argument(
        "--min-len",
        type=int,
        default=3,
        help="Longitud mínima de texto tras normalizar",
    )
    p.add_argument("--max-iter", type=int, default=300, help="Max iter LogisticRegression")
    p.add_argument(
        "--calibration",
        choices=["none", "platt", "isotonic"],
        default="none",
        help="Método de calibración de probabilidades",
    )
    p.add_argument("--cv-folds", type=int, default=3, help="Folds para calibración (si aplica)")
    p.add_argument(
        "--tau-low",
        type=float,
        default=TAU_DEFAULT,
        help="Umbral para coverage@tau (solo métrica offline)",
    )
    a = p.parse_args()
    return RetrainConfig(
        lang=a.lang.lower(),
        data_dir=a.data_dir,
        models_dir=a.models_dir,
        max_examples=None if a.max_examples == 0 else a.max_examples,
        char_ngrams=a.char_ngrams,
        test_size=max(0.0, min(0.5, a.test_size)),
        dry_run=a.dry_run,
        min_len=a.min_len,
        max_iter=a.max_iter,
        calibration=a.calibration,
        cv_folds=a.cv_folds,
        tau_low=a.tau_low,
    )


def main() -> int:
    cfg = parse_args()
    tax_path = Path(cfg.data_dir) / "taxonomy.json"
    if not tax_path.exists():
        print(f"ERROR: taxonomy file not found: {tax_path}", file=sys.stderr)
        return 1
    taxonomy = load_taxonomy(tax_path)
    default_lang = cfg.lang  # fallback simple (se podría parameterizar)
    x_texts, y = collect_texts(taxonomy, cfg.lang, default_lang, cfg)
    if not x_texts:
        print("ERROR: No se generaron textos para entrenamiento", file=sys.stderr)
        return 2

    vec, clf, stats = train_model(x_texts, y, cfg)
    classes = sorted(list({c for c in y}))

    print("=== Retraining Stats ===")
    for k, v in asdict(stats).items():
        print(f"{k}: {v}")
    print(f"classes (n={len(classes)}): sample={classes[:5]}")

    if cfg.dry_run:
        print("Dry-run: artefactos no guardados.")
        return 0

    atomic_save(Path(cfg.models_dir), vec, clf, classes, stats, cfg)
    print(f"Model artifacts saved to {cfg.models_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
