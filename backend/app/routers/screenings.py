from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import threading

from ..database import get_db
from ..models import Screening
from ..schemas import ScreeningDetailOut, CandidateOut
from ..services.campaign_runner import process_one_screening

router = APIRouter(prefix="/api/screenings", tags=["screenings"])


@router.get("/{screening_id}", response_model=ScreeningDetailOut)
def get_screening(screening_id: int, db: Session = Depends(get_db)):
    s = db.get(Screening, screening_id)
    if not s:
        raise HTTPException(404, "Screening not found")
    return ScreeningDetailOut(
        id=s.id,
        campaign_id=s.campaign_id,
        campaign_name=s.campaign.name,
        candidate=CandidateOut.model_validate(s.candidate),
        call_status=s.call_status,
        outcome_detail=s.outcome_detail,
        recommendation=s.recommendation,
        ai_score=s.ai_score,
        summary=s.summary,
        extracted_data=s.extracted_data,
        error_message=s.error_message,
        call_duration_seconds=s.call_duration_seconds,
        attempt_count=s.attempt_count,
        max_attempts=s.max_attempts,
        last_attempt_at=s.last_attempt_at,
        created_at=s.created_at,
    )


@router.post("/{screening_id}/retry")
def retry_screening(screening_id: int, db: Session = Depends(get_db)):
    s = db.get(Screening, screening_id)
    if not s:
        raise HTTPException(404, "Screening not found")
    if s.call_status == "in_progress":
        raise HTTPException(409, "Call already in progress")
    s.call_status = "not_contacted"
    s.attempt_count = 0
    s.error_message = None
    db.commit()

    thread = threading.Thread(target=process_one_screening, args=(screening_id,), daemon=True)
    thread.start()
    return {"status": "retry_started"}
