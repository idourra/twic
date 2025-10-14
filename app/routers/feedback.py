from fastapi import APIRouter
from app.models.schemas import FeedbackRequest
from pathlib import Path
import json
from datetime import datetime
from app.core.settings import settings

router = APIRouter()

@router.post("/feedback", status_code=202)
def feedback(body: FeedbackRequest) -> dict[str, bool]:
    p = Path(settings.data_dir) / "feedback"
    p.mkdir(parents=True, exist_ok=True)
    rec = {"ts": datetime.utcnow().isoformat(), **body.model_dump()}
    out = p / f"{datetime.utcnow().date()}.jsonl"
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return {"accepted": True}
