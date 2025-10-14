import time
import logging
# ruff: noqa: I001

from fastapi import APIRouter, HTTPException

from app.core.settings import settings
from app.models.schemas import Alternative, ClassifyRequest, ClassifyResponse, Prediction
from app.services import classifier, preprocessing, retrieval, retrieval_bm25
from app.services.fusion import combine_triple
from app.services.taxonomy_store import TaxonomyStore
from app.observability import (
    REQUEST_COUNT,
    CLASSIFY_SCORE_MAX,
    CLASSIFY_ABSTAIN,
    UNKNOWN_QUERIES_TOTAL,
)

router = APIRouter()
logger = logging.getLogger("classify")


class _ClassifyState:
    def __init__(self) -> None:
        self.loaded_dense: dict[str, bool] = {"es": False, "en": False}
        self.loaded_bm25: dict[str, bool] = {"es": False, "en": False}
        self.store: TaxonomyStore | None = None

    def ensure(self, lang: str) -> TaxonomyStore:
        if self.store is None:
            self.store = TaxonomyStore(f"{settings.data_dir}/taxonomy.json")
            self.store.load()
        if not self.loaded_dense.get(lang, False):
            retrieval.load_index(
                f"{settings.data_dir}/class_embeddings_{lang}.npy",
                f"{settings.data_dir}/class_ids.npy",
            )
            classifier.load(settings.models_dir)
            self.loaded_dense[lang] = True
        if not self.loaded_bm25.get(lang, False):
            retrieval_bm25.build_or_get(
                lang, taxonomy_path=f"{settings.data_dir}/taxonomy.json"
            )
            self.loaded_bm25[lang] = True
        return self.store


_state = _ClassifyState()

@router.post("/classify", response_model=ClassifyResponse)
def classify(body: ClassifyRequest) -> ClassifyResponse:
    t0 = time.time()
    if not body.query or not body.query.strip():
        raise HTTPException(status_code=400, detail="query is required")
    lang = (body.lang or settings.default_lang).lower()
    if lang not in settings.supported_langs:
        lang = settings.default_lang

    store = _state.ensure(lang)

    q = preprocessing.normalize(body.query)
    # 1) Denso (semántico)
    q_emb = retrieval.embed_query(q)
    sem = retrieval.topk(q_emb, k=settings.top_k)
    # 2) Léxico (BM25)
    bm25 = retrieval_bm25.topk(q, lang=lang, k=settings.top_k)
    # 3) Clasificador
    cls_vec = classifier.scores(q)

    combined = combine_triple(
        sem_scores=sem,
        bm25_scores=bm25,
        cls_scores=cls_vec,
        classes=classifier.class_ids(),
        w_sem=settings.alpha_sem,
        w_bm25=settings.beta_bm25,
        w_clf=settings.gamma_clf,
    )

    if not combined:
        combined = sem or bm25 or []
    if not combined:
        raise HTTPException(status_code=503, detail="no candidates")

    # Filtra ids que no existan en la taxonomía (puede haber clases históricas)
    assert store is not None
    before = len(combined)
    combined = [(cid, sc) for cid, sc in combined if cid in store.concepts]
    discarded = before - len(combined)
    if discarded:
        logger.info("classify.discarded_missing_concepts", extra={
            "discarded": discarded,
            "kept": len(combined),
            "lang": lang,
        })
    if not combined:
        raise HTTPException(status_code=503, detail="no candidates in taxonomy")

    best_id, best_score = combined[0]
    concept = store.concepts.get(best_id)
    if concept is None:
        raise HTTPException(status_code=500, detail="taxonomy concept missing")

    label = concept.prefLabel.get(lang) or next(iter(concept.prefLabel.values()))
    path  = concept.path.get(lang) or next(iter(concept.path.values()))
    abstained = best_score < settings.tau_low

    prediction = None if abstained else Prediction(
        id=best_id, label=label, path=path, score=float(best_score), method="sem+bm25+clf"
    )

    k_alt = body.top_k or 5
    alts = []
    for cid, sc in combined[1 : k_alt + 1]:
        c = store.concepts.get(cid)
        if c is None:
            continue
        al_label = c.prefLabel.get(lang) or next(iter(c.prefLabel.values()))
        alts.append(Alternative(id=cid, label=al_label, score=float(sc)))

    latency_ms = int((time.time() - t0) * 1000)
    logger.info(
        "classify.success",
        extra={
            "latency_ms": latency_ms,
            "prediction": prediction.id if prediction else None,
            "abstained": abstained,
            "alternatives": len(alts),
            "lang": lang,
        },
    )
    if REQUEST_COUNT:
        REQUEST_COUNT.labels("POST", "/classify", "200_abstain" if abstained else "200").inc()
    if CLASSIFY_SCORE_MAX and not abstained:
        CLASSIFY_SCORE_MAX.labels(lang).observe(float(best_score))
    if CLASSIFY_ABSTAIN and abstained:
        CLASSIFY_ABSTAIN.labels(lang).inc()
    if UNKNOWN_QUERIES_TOTAL and abstained:
        UNKNOWN_QUERIES_TOTAL.labels(lang).inc()
    return ClassifyResponse(
        prediction=prediction,
        alternatives=alts,
        abstained=abstained,
        latency_ms=latency_ms,
    )
