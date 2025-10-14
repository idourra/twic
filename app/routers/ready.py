import os

from fastapi import APIRouter, Response

from app.core.settings import settings

router = APIRouter()

_READY_FLAGS = {
    "taxonomy_loaded": False,
    "classifier_loaded": False,
    "bm25_loaded": False,
}

def mark_ready(
    taxonomy: bool | None = None,
    classifier: bool | None = None,
    bm25: bool | None = None,
):
    if taxonomy is not None:
        _READY_FLAGS["taxonomy_loaded"] = taxonomy
    if classifier is not None:
        _READY_FLAGS["classifier_loaded"] = classifier
    if bm25 is not None:
        _READY_FLAGS["bm25_loaded"] = bm25

@router.get("/ready")
def ready() -> Response:
    # Quick checks: taxonomy file & model artifacts existence + flags
    taxo_file = os.path.join(settings.data_dir, "taxonomy.json")
    taxonomy_ok = os.path.exists(taxo_file) and _READY_FLAGS["taxonomy_loaded"]
    model_file = os.path.join(settings.models_dir, "lr.joblib")
    classifier_ok = os.path.exists(model_file) and _READY_FLAGS["classifier_loaded"]
    bm25_ok = _READY_FLAGS["bm25_loaded"]  # built in memory
    all_ok = taxonomy_ok and classifier_ok
    status = 200 if all_ok else 503
    payload = {
        "status": "ready" if all_ok else "initializing",
        "taxonomy": taxonomy_ok,
        "classifier": classifier_ok,
        "bm25": bm25_ok,
    }
    return Response(content=str(payload), media_type="application/json", status_code=status)
