from __future__ import annotations

import os

import numpy as np

from app.core.settings import settings

# Embeddings backend abstraction.
# Backends: placeholder (deterministic RNG) | st (sentence-transformers)
# Fallback: if sentence-transformers import/model load fails we revert to placeholder.


class _State:
    model = None  # type: ignore
    dim: int | None = None


_state = _State()

def _init_sentence_transformers(model_name: str):  # pragma: no cover - heavy import
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except ImportError as e:
        print(
            f"[embeddings] sentence-transformers import failed ({e}); using placeholder backend"
        )
        settings.embeddings_backend = "placeholder"  # type: ignore[attr-defined]
        return
    device = os.getenv("EMBEDDINGS_DEVICE")  # let library decide if None
    try:
        _state.model = SentenceTransformer(model_name, device=device)
        # Run a tiny inference to discover dimensionality
        test_vec = _state.model.encode(["_probe_"], normalize_embeddings=True)
        _state.dim = int(test_vec.shape[1])
        print(
            f"[embeddings] Loaded sentence-transformers model '{model_name}' dim={_state.dim}"
        )
    except (OSError, RuntimeError, ValueError) as e:
        print(f"[embeddings] failed to init model '{model_name}' ({e}); fallback placeholder")
        settings.embeddings_backend = "placeholder"  # type: ignore[attr-defined]
        _state.model = None
        _state.dim = None


def _placeholder_embed(text: str) -> np.ndarray:
    rng = np.random.default_rng(abs(hash(text)) % 2**32)
    return rng.normal(size=(768,), loc=0.0, scale=1.0).astype(np.float32)


def embed_text(text: str) -> np.ndarray:
    """Return embedding for a single text using configured backend.

    Deterministic for placeholder backend.
    """
    if getattr(settings, "embeddings_backend", "placeholder") == "st":  # dynamic fallback
        if _state.model is None:
            _init_sentence_transformers(settings.embeddings_model)  # type: ignore[attr-defined]
        if _state.model is not None:
            vec = _state.model.encode([text], normalize_embeddings=True)  # shape (1, D)
            return vec[0].astype(np.float32)
    # Fallback
    return _placeholder_embed(text)


def backend_name() -> str:
    return getattr(settings, "embeddings_backend", "placeholder")


def embedding_dimension() -> int:
    if backend_name() == "st" and _state.dim is not None:
        return _state.dim
    return 768
