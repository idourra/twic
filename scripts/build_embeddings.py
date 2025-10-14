from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np

EMBED_DIM = 768

def text_embed(s: str) -> np.ndarray:
    """Deterministic pseudo embedding (placeholder)."""
    rng = np.random.default_rng(abs(hash(s)) % 2**32)
    return rng.normal(size=(EMBED_DIM,), loc=0.0, scale=1.0).astype(np.float32)

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
    dim = int(os.getenv("EMBED_DIM", str(EMBED_DIM)))
    if dim != EMBED_DIM:
        # Simple resize by trunc/pad
        embs_base = [text_embed(t) for t in texts]
        embs_adj = []
        for e in embs_base:
            if dim < EMBED_DIM:
                embs_adj.append(e[:dim])
            else:
                pad = np.zeros((dim-EMBED_DIM,), dtype=np.float32)
                embs_adj.append(np.concatenate([e, pad]))
        embs = np.vstack(embs_adj) if embs_adj else np.zeros((0,dim), dtype=np.float32)
    else:
        embs = (
            np.vstack([text_embed(t) for t in texts])
            if texts
            else np.zeros((0, EMBED_DIM), dtype=np.float32)
        )
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
