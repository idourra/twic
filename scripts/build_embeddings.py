from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np

class _EmbedRuntime:
    def __init__(self) -> None:
        self.backend = os.getenv("EMBEDDINGS_BACKEND", "placeholder")
        self.model_name = os.getenv(
            "EMBEDDINGS_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        )
        self.model = None
        self.dim: int | None = None

    def ensure(self) -> None:  # pragma: no cover - heavy import
        if self.backend != "st" or self.model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except ImportError as e:
            print(
                f"[build_embeddings] sentence-transformers import failed ({e}); "
                "fallback placeholder"
            )
            self.backend = "placeholder"
            return
        try:
            self.model = SentenceTransformer(self.model_name)
            test_vec = self.model.encode(["_probe_"], normalize_embeddings=True)
            self.dim = int(test_vec.shape[1])
            print(
                f"[build_embeddings] loaded '{self.model_name}' dim={self.dim}"
            )
        except (OSError, RuntimeError, ValueError) as e:
            print(f"[build_embeddings] failed to load model ({e}); fallback placeholder")
            self.backend = "placeholder"
            self.model = None
            self.dim = None


_RUNTIME = _EmbedRuntime()


def _placeholder_embed(s: str, dim: int = 768) -> np.ndarray:
    rng = np.random.default_rng(abs(hash(s)) % 2**32)
    vec = rng.normal(size=(dim,), loc=0.0, scale=1.0).astype(np.float32)
    return vec


def embed_texts(texts: list[str]) -> np.ndarray:
    if _RUNTIME.backend == "st":
        _RUNTIME.ensure()
        if _RUNTIME.model is not None:
            arr = _RUNTIME.model.encode(texts, normalize_embeddings=True)
            return arr.astype(np.float32)
    dim = _RUNTIME.dim or 768
    return (
        np.vstack([_placeholder_embed(t, dim) for t in texts])
        if texts
        else np.zeros((0, dim), dtype=np.float32)
    )

def _as_text(value: Any, lang: str) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        # Prefer lang, luego 'es', luego primer valor
        for k in (lang, "es"):
            v = value.get(k)
            if v:
                if isinstance(v, list):
                    return " ".join(str(x) for x in v if x)
                return str(v)
        # fallback primer valor
        first = next(iter(value.values()), "")
        if isinstance(first, list):
            return " ".join(str(x) for x in first if x)
        return str(first)
    if isinstance(value, list):
        return " ".join(str(x) for x in value if x)
    return str(value)

def build_for_lang(lang: str) -> None:
    taxo_path = Path("data/taxonomy.json")
    if not taxo_path.exists():
        raise SystemExit("taxonomy.json no encontrado; genera primero con import_skos_jsonld.py")
    taxo = json.loads(taxo_path.read_text(encoding="utf-8"))
    ids: list[str] = []
    texts: list[str] = []
    for row in taxo:
    # Campos formato nuevo: prefLabel(dict), altLabel(dict/list), hiddenLabel, definition, example
    # Compatibilidad formato antiguo: desc, examples
        pref = _as_text(row.get("prefLabel"), lang)
        alt  = _as_text(row.get("altLabel"), lang)
        hid  = _as_text(row.get("hiddenLabel"), lang)
        definition = _as_text(row.get("definition"), lang) or _as_text(row.get("desc"), lang)
        scope = _as_text(row.get("scopeNote"), lang)
        note  = _as_text(row.get("note"), lang)
        example = _as_text(row.get("example"), lang) or _as_text(row.get("examples"), lang)
        path_field = row.get("path")
        path_txt = _as_text(path_field, lang)
        pieces = [pref, alt, hid, definition, scope, note, example, path_txt]
        txt = " | ".join([p for p in pieces if p]).strip()
        ids.append(str(row.get("id")))
        texts.append(txt)
    # Embedding dimension determined by backend; optional override via EMBED_DIM for placeholder
    if _RUNTIME.backend == "placeholder":
        dim = int(os.getenv("EMBED_DIM", "768"))
        embs = embed_texts(texts)
        # If user changed EMBED_DIM but placeholder default is 768, resize accordingly
        if dim != embs.shape[1]:
            adjusted = []
            for e in embs:
                if dim < embs.shape[1]:
                    adjusted.append(e[:dim])
                else:
                    pad = np.zeros((dim - embs.shape[1],), dtype=np.float32)
                    adjusted.append(np.concatenate([e, pad]))
            embs = np.vstack(adjusted) if adjusted else np.zeros((0, dim), dtype=np.float32)
    else:
        embs = embed_texts(texts)
    Path("data").mkdir(exist_ok=True)
    np.save(f"data/class_embeddings_{lang}.npy", embs)
    np.save("data/class_ids.npy", np.array(ids, dtype=object))
    print(f"[{lang}] saved data/class_embeddings_{lang}.npy {embs.shape}, ids={len(ids)}")

def main() -> None:
    langs = ("es", "en")
    for lang in langs:
        build_for_lang(lang)

if __name__ == "__main__":
    main()
