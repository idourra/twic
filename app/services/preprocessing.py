from __future__ import annotations
import re, unicodedata
_ws = re.compile(r"\s+")
def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower().strip()
    return _ws.sub(" ", text)
