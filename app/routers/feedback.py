from fastapi import APIRouter
from app.models.schemas import FeedbackRequest
from pathlib import Path
import json
from datetime import datetime
from app.core.settings import settings
from app.observability import FEEDBACK_TOTAL

router = APIRouter()

@router.post("/feedback", status_code=202)
def feedback(body: FeedbackRequest) -> dict[str, bool]:
    p = Path(settings.data_dir) / "feedback"
    p.mkdir(parents=True, exist_ok=True)
    rec = {"ts": datetime.utcnow().isoformat(), **body.model_dump()}
    out = p / f"{datetime.utcnow().date()}.jsonl"
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    # Determine feedback type for metric labeling
    fb_type = "generic"
    if body.correct_id and not body.predicted_id:
        fb_type = "correction"  # user supplies correct label when system abstained
    elif body.correct_id and body.predicted_id:
        fb_type = "override"  # user overrides predicted with a different one
    elif body.predicted_id and not body.correct_id:
        fb_type = "confirm"  # user confirms prediction (implicit if design so)
    if FEEDBACK_TOTAL:
        FEEDBACK_TOTAL.labels(fb_type).inc()
    return {"accepted": True}
