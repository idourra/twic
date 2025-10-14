from __future__ import annotations

# ruff: noqa: E741,N815

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from app.core.settings import settings
from app.services.embeddings import embed_text
from . import preprocessing
try:  # optional fuzzy dependency
    from rapidfuzz import fuzz  # type: ignore
except ImportError:  # pragma: no cover
    fuzz = None  # type: ignore

DEFAULT_LANGS = ("es","en")

def _as_lang_dict(value: Any, langs=DEFAULT_LANGS) -> dict[str, Any]:
    """Normaliza valores multilingües a dict[lang, value]."""
    if value is None:
        return {}
    if isinstance(value, dict):
        if not value:
            return {}
        first_val = next(iter(value.values()))
        return {l: value.get(l, first_val) for l in langs}
    if isinstance(value, list):
        return {l: list(value) for l in langs}
    return {l: str(value) for l in langs}

@dataclass
class Concept:
    id: str
    uri: str
    inScheme: list[str]
    prefLabel: dict[str,str]
    altLabel: dict[str, list[str]]
    hiddenLabel: dict[str, list[str]]
    definition: dict[str, str | None]
    scopeNote: dict[str, str | None]
    note: dict[str, str | None]
    example: dict[str, list[str]]
    path: dict[str, list[str]]
    broader: list[str]
    narrower: list[str]
    exactMatch: list[str]
    closeMatch: list[str]
    related: list[str]

class TaxonomyStore:
    def __init__(self, path: str):
        self.path = Path(path)
        self.concepts: dict[str, Concept] = {}
        self._inv: dict[str, dict[str, list[str]]] = {}
        # Embedding precompute structures
        self._emb_lang_mats: dict[str, np.ndarray] = {}  # lang -> matrix (N_texts, D)
        # lang -> list of (concept_id, field, original_text)
        self._emb_lang_text_meta: dict[str, list[tuple[str, str, str]]] = {}
        # cid -> {lang: row_index for its prefLabel}
        self._emb_concept_pref_index: dict[str, dict[str, int]] = {}
        self._emb_dim: int | None = None
        # Autocomplete structures
        # lang -> list of (norm, concept_id, kind|label_original)
        self._ac_labels: dict[str, list[tuple[str, str, str]]] = {}
        self._ac_norms: dict[str, list[str]] = {}  # lang -> parallel list of normalized keys
        # (lang, norm_q, limit) -> list of tuples
        self._ac_cache: dict[tuple[str, str, int], list[tuple[str, str, str]]] = {}
        self._ac_cache_order: list[tuple[str,str,int]] = []  # simple LRU ordering
        self._ac_cache_max = 256

    def load(self) -> None:
        data: list[dict[str, Any]] = json.loads(self.path.read_text(encoding="utf-8"))
        self.concepts.clear()

        for row in data:
            # Normalización de claves legacy -> nuevas
            if "definition" not in row and "desc" in row:
                row["definition"] = row.get("desc")
            if "example" not in row and "examples" in row:
                row["example"] = row.get("examples")

            pref = _as_lang_dict(row.get("prefLabel"))
            alt  = _as_lang_dict(row.get("altLabel"))
            hid  = _as_lang_dict(row.get("hiddenLabel"))
            defin= _as_lang_dict(row.get("definition"))
            scop = _as_lang_dict(row.get("scopeNote"))
            note = _as_lang_dict(row.get("note"))
            ex   = _as_lang_dict(row.get("example"))
            path = _as_lang_dict(row.get("path"))

            c = Concept(
                id=str(row["id"]),
                uri=str(row.get("uri", row["id"])),
                inScheme=list(row.get("inScheme", [])),
                prefLabel={k:str(v) for k,v in pref.items()},
                altLabel={k: (v if isinstance(v, list) else [v]) for k,v in alt.items()},
                hiddenLabel={k: (v if isinstance(v, list) else [v]) for k,v in hid.items()},
                definition={k:(None if v in (None,"") else str(v)) for k,v in defin.items()},
                scopeNote={k:(None if v in (None,"") else str(v)) for k,v in scop.items()},
                note={k:(None if v in (None,"") else str(v)) for k,v in note.items()},
                example={k: (v if isinstance(v, list) else [v]) for k,v in ex.items()},
                path={k: (v if isinstance(v, list) else [v]) for k,v in path.items()},
                broader=list(row.get("broader", [])),
                narrower=list(row.get("narrower", [])),
                exactMatch=list(row.get("exactMatch", [])),
                closeMatch=list(row.get("closeMatch", [])),
                related=list(row.get("related", [])),
            )
            self.concepts[c.id] = c

        # idiomas presentes o por defecto
        langs = set()
        for c in self.concepts.values():
            langs.update(c.prefLabel.keys())
        langs = langs or set(DEFAULT_LANGS)

        # índice invertido
        self._inv = {l: {} for l in langs}
        for c in self.concepts.values():
            for l in self._inv.keys():
                terms: list[str] = []
                if c.prefLabel.get(l):
                    terms.append(c.prefLabel[l])
                terms += c.altLabel.get(l, [])
                terms += c.hiddenLabel.get(l, [])
                if c.definition.get(l):
                    terms.append(c.definition[l] or "")
                if c.scopeNote.get(l):
                    terms.append(c.scopeNote[l] or "")
                if c.note.get(l):
                    terms.append(c.note[l] or "")
                terms += c.example.get(l, [])
                terms += c.path.get(l, [])
                for t in terms:
                    key = (t or "").lower().strip()
                    if not key:
                        continue
                    self._inv[l].setdefault(key, []).append(c.id)

        # Precompute embeddings (prefLabel + altLabel) if vector weight enabled
        if settings.taxo_w_vec > 0:
            self._emb_lang_mats.clear()
            self._emb_lang_text_meta.clear()
            self._emb_concept_pref_index.clear()
            from app.services.embeddings import embedding_dimension
            dim = embedding_dimension()
            self._emb_dim = dim
            for l in langs:
                rows: list[np.ndarray] = []
                meta: list[tuple[str,str,str]] = []
                for c in self.concepts.values():
                    # prefLabel first (used for concept-level score)
                    pref_text = c.prefLabel.get(l) or next(iter(c.prefLabel.values()), "")
                    if pref_text:
                        emb = embed_text(pref_text)
                        rows.append(emb)
                        idx = len(meta)
                        meta.append((c.id, "pref", pref_text))
                        self._emb_concept_pref_index.setdefault(c.id, {})[l] = idx
                    # altLabels
                    for alt in c.altLabel.get(l, []):
                        if not alt:
                            continue
                        emb = embed_text(alt)
                        rows.append(emb)
                        meta.append((c.id, "alt", alt))
                if rows:
                    mat = np.vstack(rows).astype(np.float32)
                else:
                    mat = np.zeros((0, dim), dtype=np.float32)
                self._emb_lang_mats[l] = mat
                self._emb_lang_text_meta[l] = meta
        # Build autocomplete indices
        self._ac_labels.clear()
        self._ac_norms.clear()
        for l in langs:
            triplets: list[tuple[str,str,str]] = []  # (norm_label, concept_id, kind|original)
            for c in self.concepts.values():
                pref = c.prefLabel.get(l) or next(iter(c.prefLabel.values()), "")
                if pref:
                    triplets.append((preprocessing.normalize(pref), c.id, f"pref|{pref}"))
                for alt in c.altLabel.get(l, []):
                    if alt:
                        triplets.append((preprocessing.normalize(alt), c.id, f"alt|{alt}"))
            # sort by normalized form then by length then pref before alt
            triplets.sort(key=lambda t: (t[0], len(t[2]), 0 if t[2].startswith("pref|") else 1))
            self._ac_labels[l] = triplets
            self._ac_norms[l] = [t[0] for t in triplets]
        # Invalidate autocomplete cache
        self._ac_cache.clear()
        self._ac_cache_order.clear()

    _emb_cache: dict[str, np.ndarray] = {}

    def _embed_pref(self, c: Concept, lang: str) -> np.ndarray:
        key = f"{c.id}:{lang}"
        emb = self._emb_cache.get(key)
        if emb is not None:
            return emb
        text = c.prefLabel.get(lang) or next(iter(c.prefLabel.values()), "")
        emb = embed_text(text)
        self._emb_cache[key] = emb
        return emb

    def search(self, q: str, lang: str, limit: int | None = None) -> list[Concept]:
        """Búsqueda con ranking heurístico.
        Score por concepto = max de reglas:
          +100 exact prefLabel
          +60 prefix prefLabel
          +40 substring prefLabel
          +30 altLabel match
          +20 hiddenLabel match
          +10 path match
           +5 definition/scope/note/example match
        Se aplica normalización extendida a query y campos.
        """
        if not self._inv:
            self.load()
        lang = lang if lang in self._inv else next(iter(self._inv.keys()))
        raw_q = q
        q_norm = preprocessing.normalize(raw_q)
        if not q_norm:
            return []
        scores: dict[str, float] = {}
        vec_scores: dict[str, float] = {}
        # pre-candidate: filtrar solo claves que contienen substring normalizada
        for key, concept_ids in self._inv[lang].items():
            if q_norm in preprocessing.normalize(key):
                for cid in concept_ids:
                    c = self.concepts[cid]
                    pref = c.prefLabel.get(lang) or ""
                    pref_norm = preprocessing.normalize(pref)
                    base = 0.0
                    if pref_norm == q_norm:
                        base += settings.taxo_w_exact
                    elif pref_norm.startswith(q_norm):
                        base += settings.taxo_w_prefix
                    elif q_norm in pref_norm:
                        base += settings.taxo_w_substring
                    # alt / hidden
                    if any(
                        q_norm in preprocessing.normalize(a)
                        for a in c.altLabel.get(lang, [])
                    ):
                        base += settings.taxo_w_alt
                    if any(
                        q_norm in preprocessing.normalize(h)
                        for h in c.hiddenLabel.get(lang, [])
                    ):
                        base += settings.taxo_w_hidden
                    # path
                    if any(q_norm in preprocessing.normalize(p) for p in c.path.get(lang, [])):
                        base += settings.taxo_w_path
                    # definition / scope / note / example (menor peso)
                    for dfield in (c.definition.get(lang), c.scopeNote.get(lang), c.note.get(lang)):
                        if dfield and q_norm in preprocessing.normalize(dfield or ""):
                            base += settings.taxo_w_context
                            break
                    if any(q_norm in preprocessing.normalize(ex) for ex in c.example.get(lang, [])):
                        base += settings.taxo_w_context
                    if base <= 0:
                        continue
                    prev = scores.get(cid, 0.0)
                    if base > prev:
                        scores[cid] = base
        # Vector similarity (optional)
        # Fuzzy fallback if no base matches but fuzzy enabled
        if not scores and settings.taxo_w_fuzzy > 0 and fuzz:
            # Evaluate fuzzy over all prefLabels (could be optimized)
            for cid, c in self.concepts.items():
                pref = c.prefLabel.get(lang) or next(iter(c.prefLabel.values()), "")
                pref_norm = preprocessing.normalize(pref)
                ratio = fuzz.partial_ratio(q_norm, pref_norm)
                if ratio >= settings.taxo_fuzzy_min_ratio:
                    scores[cid] = (ratio / 100.0) * settings.taxo_w_fuzzy
        if settings.taxo_w_vec > 0 and scores:
            # Use precomputed matrix if available; fallback to per-concept embedding
            q_emb = embed_text(raw_q)
            q_norm_val = float(np.linalg.norm(q_emb) + 1e-8)
            if self._emb_lang_mats.get(lang) is not None and self._emb_lang_mats[lang].shape[0] > 0:
                mat = self._emb_lang_mats[lang]  # (N, D)
                # cosine similarity
                # avoid large memory if huge: simple dot then divide
                dots = mat @ q_emb  # (N,)
                mat_norms = np.linalg.norm(mat, axis=1) + 1e-8
                sims = dots / (mat_norms * q_norm_val)
                # aggregate: prefer prefLabel embedding (recorded index), else max altLabel sim
                for cid in list(scores.keys()):
                    pref_idx = self._emb_concept_pref_index.get(cid, {}).get(lang)
                    best_sim = None
                    if pref_idx is not None:
                        best_sim = float(sims[pref_idx])
                    else:  # compute max over all rows belonging to this cid
                        # Iterate meta list to find rows for this cid (moderate size expected)
                        best_sim = -1.0
                        for i, (mcid, _field, _text) in enumerate(
                            self._emb_lang_text_meta[lang]
                        ):
                            if mcid == cid:
                                if sims[i] > best_sim:
                                    best_sim = float(sims[i])
                    # Normalize to [0,1] from assumed [-1,1]
                    sim01 = (best_sim + 1) / 2
                    vec_scores[cid] = sim01 * settings.taxo_w_vec
            else:
                # Fallback per concept
                for cid in scores.keys():
                    c = self.concepts[cid]
                    emb = self._embed_pref(c, lang)
                    sim = float((emb @ q_emb) / ((np.linalg.norm(emb) + 1e-8) * q_norm_val))
                    sim01 = (sim + 1) / 2
                    vec_scores[cid] = sim01 * settings.taxo_w_vec
        # Fuzzy similarity (optional)
        if settings.taxo_w_fuzzy > 0 and fuzz and scores:
            for cid in list(scores.keys()):
                c = self.concepts[cid]
                pref = c.prefLabel.get(lang) or next(iter(c.prefLabel.values()), "")
                pref_norm = preprocessing.normalize(pref)
                ratio = fuzz.partial_ratio(q_norm, pref_norm)
                if ratio >= settings.taxo_fuzzy_min_ratio:
                    scores[cid] = scores.get(cid, 0.0) + (ratio / 100.0) * settings.taxo_w_fuzzy
        # Combine
        if vec_scores:
            for cid, vsc in vec_scores.items():
                scores[cid] = scores.get(cid, 0.0) + vsc
        if not scores:
            return []
        ordered = sorted(
            scores.items(),
            key=lambda kv: (
                -kv[1],
                len(self.concepts[kv[0]].prefLabel.get(lang, "")),
            ),
        )
        lim = limit or settings.taxo_top_k
        return [self.concepts[cid] for cid, _ in ordered[:lim]]

    # --- Autocomplete ---
    def autocomplete(self, q: str, lang: str, limit: int = 15) -> list[tuple[str,str,str]]:
        if not self._inv:
            self.load()
        lang = lang if lang in self._ac_norms else next(iter(self._ac_norms.keys()))
        norm_q = preprocessing.normalize(q)
        if not norm_q:
            return []
        cache_key = (lang, norm_q, limit)
        cached = self._ac_cache.get(cache_key)
        if cached is not None:
            return cached
        norms = self._ac_norms.get(lang, [])
        from bisect import bisect_left
        idx = bisect_left(norms, norm_q)
        out: list[tuple[str,str,str]] = []
        n = len(norms)
        # forward scan while prefix matches
        while idx < n and norms[idx].startswith(norm_q):
            trip = self._ac_labels[lang][idx]
            out.append(trip)
            if len(out) >= limit:
                break
            idx += 1
        # LRU cache store
        self._ac_cache[cache_key] = out
        self._ac_cache_order.append(cache_key)
        if len(self._ac_cache_order) > self._ac_cache_max:
            old = self._ac_cache_order.pop(0)
            self._ac_cache.pop(old, None)
        return out
