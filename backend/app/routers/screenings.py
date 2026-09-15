import datetime
import threading

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Screening
from ..schemas import ScreeningDetailOut, CandidateOut, RecruiterFeedbackIn
from ..services.campaign_runner import process_one_screening
from ..services.scheduling import suggest_interview_window

router = APIRouter(prefix="/api/screenings", tags=["screenings"])

VALID_OVERRIDES = {"shortlisted", "manual_review", "rejected"}


def effective_recommendation(s: Screening) -> str | None:
    return s.recruiter_override or s.recommendation


def _to_detail_out(s: Screening) -> ScreeningDetailOut:
    effective = effective_recommendation(s)
    return ScreeningDetailOut(
        id=s.id,
        campaign_id=s.campaign_id,
        campaign_name=s.campaign.name,
        candidate=CandidateOut.model_validate(s.candidate),
        call_status=s.call_status,
        outcome_detail=s.outcome_detail,
        recommendation=s.recommendation,
        ai_score=s.ai_score,
        ai_source=s.ai_source,
        summary=s.summary,
        extracted_data=s.extracted_data,
        transcript=s.transcript,
        error_message=s.error_message,
        call_duration_seconds=s.call_duration_seconds,
        attempt_count=s.attempt_count,
        max_attempts=s.max_attempts,
        last_attempt_at=s.last_attempt_at,
        created_at=s.created_at,
        jd_match_pct=s.jd_match_pct,
        recruiter_note=s.recruiter_note,
        recruiter_override=s.recruiter_override,
        effective_recommendation=effective,
        reviewed_at=s.reviewed_at,
        interview_suggestion=suggest_interview_window(s.extracted_data, s.ai_score, effective),
    )


@router.get("/{screening_id}", response_model=ScreeningDetailOut)
def get_screening(screening_id: int, db: Session = Depends(get_db)):
    s = db.get(Screening, screening_id)
    if not s:
        raise HTTPException(404, "Screening not found")
    return _to_detail_out(s)


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


@router.post("/{screening_id}/feedback", response_model=ScreeningDetailOut)
def submit_feedback(screening_id: int, payload: RecruiterFeedbackIn, db: Session = Depends(get_db)):
    s = db.get(Screening, screening_id)
    if not s:
        raise HTTPException(404, "Screening not found")

    if payload.clear_override:
        s.recruiter_override = None
    elif payload.override is not None:
        if payload.override not in VALID_OVERRIDES:
            raise HTTPException(400, f"override must be one of {', '.join(sorted(VALID_OVERRIDES))}")
        s.recruiter_override = payload.override

    if payload.note is not None:
        s.recruiter_note = payload.note

    s.reviewed_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(s)
    return _to_detail_out(s)
