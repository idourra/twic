from fastapi import APIRouter, HTTPException, Query

from app.core.settings import settings
from app.models.schemas import TaxoConceptDetail, TaxoResult, TaxoSearchResponse
from app.services.taxonomy_store import TaxonomyStore

router = APIRouter()


class _StoreHolder:
    inst: TaxonomyStore | None = None


def _get_store() -> TaxonomyStore:
    if _StoreHolder.inst is None:
        _StoreHolder.inst = TaxonomyStore(f"{settings.data_dir}/taxonomy.json")
        _StoreHolder.inst.load()
    return _StoreHolder.inst

@router.get("/taxonomy/search", response_model=TaxoSearchResponse)
def search(q: str, lang: str = Query(default=settings.default_lang)) -> TaxoSearchResponse:
    store = _get_store()
    results = store.search(q, lang)
    payload = []
    for c in results:
        label = (
            c.prefLabel.get(lang)
            or c.prefLabel.get(settings.default_lang)
            or next(iter(c.prefLabel.values()))
        )
        path = (
            c.path.get(lang)
            or c.path.get(settings.default_lang)
            or next(iter(c.path.values()))
        )
        payload.append(TaxoResult(id=c.id, label=label, path=path))
    return TaxoSearchResponse(results=payload)

@router.get("/taxonomy/{concept_id}", response_model=TaxoConceptDetail)
def get_concept(concept_id: str) -> TaxoConceptDetail:
    store = _get_store()
    c = store.concepts.get(concept_id)
    if not c:
        raise HTTPException(status_code=404, detail="concept not found")
    # Convert dataclass Concept to dict matching schema (aliases applied automatically)
    data = {
        "id": c.id,
        "uri": c.uri,
        "prefLabel": c.prefLabel,
        "altLabel": c.altLabel,
        "hiddenLabel": c.hiddenLabel,
        "definition": c.definition,
        "scopeNote": c.scopeNote,
        "note": c.note,
        "example": c.example,
        "path": c.path,
        "broader": c.broader,
        "narrower": c.narrower,
        "exactMatch": c.exactMatch,
        "closeMatch": c.closeMatch,
        "related": c.related,
    }
    return TaxoConceptDetail(**data)
