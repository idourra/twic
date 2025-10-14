from __future__ import annotations

# ruff: noqa: E741,N815

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

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

    def search(self, q: str, lang: str) -> list[Concept]:
        if not self._inv:
            self.load()
        lang = lang if lang in self._inv else next(iter(self._inv.keys()))
        ql = q.lower()
        ids = set()
        for k, v in self._inv[lang].items():
            if ql in k:
                ids.update(v)
        return [self.concepts[i] for i in ids]
