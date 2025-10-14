from fastapi import APIRouter
from pathlib import Path
import hashlib
from app.core.settings import settings
from app.services import retrieval, retrieval_bm25

router = APIRouter()

def _checksum(p: str) -> str:
    fp = Path(p)
    if not fp.exists():
        return "missing"
    try:
        return hashlib.sha256(fp.read_bytes()).hexdigest()[:12]
    except Exception:
        return "error"

@router.post("/admin/reload")
def admin_reload(lang: str | None = None):
    # 1) reset índices densos y BM25
    retrieval.reset_index()
    if lang:
        retrieval_bm25.reset(lang)
    else:
        retrieval_bm25.reset(None)

    # 2) intenta resetear el TaxonomyStore del router taxonomy (si existe)
    taxo_reset = False
    try:
        from app.routers import taxonomy  # type: ignore
        taxonomy._store = None  # type: ignore
        taxo_reset = True
    except Exception:
        taxo_reset = False

    rep = {
        "taxonomy.json": _checksum(f"{settings.data_dir}/taxonomy.json"),
        "emb_es": _checksum(f"{settings.data_dir}/class_embeddings_es.npy"),
        "emb_en": _checksum(f"{settings.data_dir}/class_embeddings_en.npy"),
        "ids": _checksum(f"{settings.data_dir}/class_ids.npy"),
        "taxonomy_store_reset": taxo_reset,
        "langs": [lang] if lang else ["es","en"],
    }
    return {"reloaded": True, "files": rep}
