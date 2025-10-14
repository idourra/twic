from __future__ import annotations
import re, unicodedata
_ws = re.compile(r"\s+")
_non_alnum = re.compile(r"[^0-9a-záéíóúüñ ]", flags=re.IGNORECASE)

def _strip_accents(s: str) -> str:
    # NFKD + remove combining marks
    nk = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in nk if not unicodedata.combining(ch))

def _simple_singular(token: str) -> str:
    # naive: plural -> singular if token ends with 's' and length>4
    if len(token) > 4 and token.endswith("s"):
        return token[:-1]
    return token

def normalize(text: str, *, accents: bool = True, singular: bool = True) -> str:
    """Normalización expandida para búsqueda / embeddings.
    - Unicode NFKC
    - Lowercase
    - Strip espacios
    - Remove chars no alfanum (mantiene acentos primarios, luego opcionalmente se quitan)
    - Singularización muy simple (quitar 's' final) para heurística plural->singular
    """
    text = unicodedata.normalize("NFKC", text).lower()
    text = _non_alnum.sub(" ", text)
    text = _ws.sub(" ", text).strip()
    if accents:
        text = _strip_accents(text)
    if singular:
        text = " ".join(_simple_singular(tok) for tok in text.split())
    return text
