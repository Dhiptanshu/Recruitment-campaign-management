"""Drives a campaign's outbound screening calls through the simulated
calling service using a bounded worker pool, so a campaign of any size
(100s to 100,000+ candidates) behaves the same way -- work is streamed
through a fixed-size pool rather than all launched at once."""
import datetime
import logging
import threading
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select

from ..calling_service import CallingServiceError, place_call
from ..database import SessionLocal
from ..models import Campaign, Screening
from .scoring import score_and_recommend
from .jd_matching import match_job_description

logger = logging.getLogger("globalvox.campaign_runner")

CONCURRENCY = 10
RETRY_BACKOFF_SECONDS = 0.05

# tracks campaign_id -> "cancel requested" flag for cooperative stop
_cancel_flags: dict[int, threading.Event] = {}
_lock = threading.Lock()


def request_cancel(campaign_id: int):
    with _lock:
        flag = _cancel_flags.get(campaign_id)
        if flag:
            flag.set()


def _get_cancel_flag(campaign_id: int) -> threading.Event:
    with _lock:
        flag = _cancel_flags.setdefault(campaign_id, threading.Event())
        flag.clear()
        return flag


def process_one_screening(screening_id: int):
    """Runs the full retry loop for a single candidate's screening call.
    Opens its own short-lived DB session so it can run safely from any
    worker thread."""
    db = SessionLocal()
    try:
        screening = db.get(Screening, screening_id)
        if screening is None:
            return
        campaign = db.get(Campaign, screening.campaign_id)
        candidate = screening.candidate

        screening.call_status = "in_progress"
        db.commit()

        campaign_dict = {
            "experience_min": campaign.experience_min,
            "experience_max": campaign.experience_max,
            "position": campaign.position,
        }
        candidate_dict = {"name": candidate.name, "phone": candidate.phone}

        last_error = None
        while screening.attempt_count < screening.max_attempts:
            screening.attempt_count += 1
            screening.last_attempt_at = datetime.datetime.utcnow()
            try:
                result = place_call(candidate_dict, campaign_dict)
            except CallingServiceError as exc:
                last_error = str(exc)
                screening.outcome_detail = "technical_error"
                screening.error_message = last_error
                continue

            if result.outcome == "success":
                score, recommendation, summary = score_and_recommend(result.data, campaign)
                jd_pct, jd_matched, jd_missing = match_job_description(
                    campaign.job_description, result.data.get("skills")
                )
                data = dict(result.data)
                if jd_pct is not None:
                    data["jd_match"] = {"pct": jd_pct, "matched": jd_matched, "missing": jd_missing}

                screening.call_status = "completed"
                screening.outcome_detail = "success"
                screening.recommendation = recommendation
                screening.ai_score = score
                screening.summary = summary
                screening.extracted_data = data
                screening.jd_match_pct = jd_pct
                screening.call_duration_seconds = result.duration_seconds
                screening.error_message = None
                db.commit()
                return

            # no_answer / voicemail: worth one retry, otherwise terminal-failed
            screening.outcome_detail = result.outcome
            screening.call_duration_seconds = result.duration_seconds

        # exhausted attempts without a completed conversation
        screening.call_status = "failed"
        if not screening.error_message and screening.outcome_detail == "technical_error":
            screening.error_message = last_error
        db.commit()
    except Exception:
        logger.exception("Unhandled error processing screening %s", screening_id)
        db.rollback()
        try:
            screening = db.get(Screening, screening_id)
            if screening:
                screening.call_status = "failed"
                screening.outcome_detail = "technical_error"
                screening.error_message = "Internal processing error"
                db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()


def run_campaign(campaign_id: int):
    db = SessionLocal()
    try:
        campaign = db.get(Campaign, campaign_id)
        if campaign is None:
            return
        campaign.status = "running"
        campaign.started_at = campaign.started_at or datetime.datetime.utcnow()
        db.commit()

        screening_ids = [
            row[0] for row in db.execute(
                select(Screening.id)
                .where(Screening.campaign_id == campaign_id)
                .where(Screening.call_status.in_(["not_contacted", "in_progress"]))
            ).all()
        ]
    finally:
        db.close()

    cancel_flag = _get_cancel_flag(campaign_id)

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = []
        for sid in screening_ids:
            if cancel_flag.is_set():
                break
            futures.append(pool.submit(process_one_screening, sid))
        for f in futures:
            f.result()

    db = SessionLocal()
    try:
        campaign = db.get(Campaign, campaign_id)
        if campaign is None:
            return
        remaining = db.execute(
            select(Screening.id)
            .where(Screening.campaign_id == campaign_id)
            .where(Screening.call_status.in_(["not_contacted", "in_progress"]))
            .limit(1)
        ).first()
        if cancel_flag.is_set():
            campaign.status = "paused"
        elif remaining is None:
            campaign.status = "completed"
            campaign.completed_at = datetime.datetime.utcnow()
        db.commit()
    finally:
        db.close()


def start_campaign_async(campaign_id: int):
    thread = threading.Thread(target=run_campaign, args=(campaign_id,), daemon=True)
    thread.start()
    return thread
