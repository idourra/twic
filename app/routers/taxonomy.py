import time

from fastapi import APIRouter, HTTPException, Query

from app import observability as obs
from app.core.settings import settings
from app.models.schemas import (
    TaxoConceptDetail,
    TaxoResult,
    TaxoSearchResponse,
    AutocompleteResponse,
    AutocompleteResult,
)
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
def search(
    q: str,
    lang: str = Query(default=settings.default_lang),
    limit: int | None = Query(default=None, ge=1, le=200),
) -> TaxoSearchResponse:
    store = _get_store()
    t0 = time.perf_counter()
    results = store.search(q, lang, limit=limit or settings.taxo_top_k)
    dt = time.perf_counter() - t0
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
    # Metrics
    if obs.TAXO_SEARCH_LATENCY:
        obs.TAXO_SEARCH_LATENCY.labels(lang=lang, source="search").observe(dt)
    if obs.TAXO_SEARCH_RESULTS:
        n = len(results)
        if n == 0:
            bucket = "0"
        elif n <= 5:
            bucket = "1_5"
        elif n <= 10:
            bucket = "6_10"
        else:
            bucket = "gt_10"
        obs.TAXO_SEARCH_RESULTS.labels(lang=lang, source="search", bucket=bucket).inc()
    if obs.TAXO_SEARCH_EMPTY and not results:
        obs.TAXO_SEARCH_EMPTY.labels(lang=lang, source="search").inc()
    # Embedding gauge (set once per request cheap) — reflects matrix size
    if obs.TAXO_EMB_CACHE_SIZE and store._emb_lang_mats:
        mat = store._emb_lang_mats.get(lang)
        if mat is not None:
            obs.TAXO_EMB_CACHE_SIZE.labels(lang=lang).set(mat.shape[0])
    return TaxoSearchResponse(results=payload)

@router.get("/taxonomy/autocomplete", response_model=AutocompleteResponse)
def autocomplete(
    q: str,
    lang: str = Query(default=settings.default_lang),
    limit: int = Query(default=15, ge=1, le=50),
) -> AutocompleteResponse:
    store = _get_store()
    t0 = time.perf_counter()
    triples = store.autocomplete(q, lang, limit=limit)
    dt = time.perf_counter() - t0
    results: list[AutocompleteResult] = []
    for _norm, cid, kind_label in triples:
        kind, label = kind_label.split("|", 1)
        results.append(AutocompleteResult(id=cid, label=label, kind=kind))
    if obs.TAXO_SEARCH_LATENCY:
        obs.TAXO_SEARCH_LATENCY.labels(lang=lang, source="autocomplete").observe(dt)
    if obs.TAXO_SEARCH_RESULTS:
        n = len(results)
        if n == 0:
            bucket = "0"
        elif n <= 5:
            bucket = "1_5"
        elif n <= 10:
            bucket = "6_10"
        else:
            bucket = "gt_10"
        obs.TAXO_SEARCH_RESULTS.labels(lang=lang, source="autocomplete", bucket=bucket).inc()
    if obs.TAXO_SEARCH_EMPTY and not results:
        obs.TAXO_SEARCH_EMPTY.labels(lang=lang, source="autocomplete").inc()
    return AutocompleteResponse(results=results)

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
