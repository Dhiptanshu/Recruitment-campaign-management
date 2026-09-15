import csv
import io

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Campaign, Candidate, Screening
from ..schemas import (
    CampaignCreate, CampaignOut, CampaignDetailOut, CampaignStats,
    ScreeningListItemOut, PageOut, ImportSummaryOut,
)
from ..services.csv_import import import_candidates_csv
from ..services.campaign_runner import start_campaign_async, request_cancel

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


def _compute_stats(db: Session, campaign_id: int) -> CampaignStats:
    rows = db.execute(
        select(Screening.call_status, Screening.recommendation, func.count())
        .where(Screening.campaign_id == campaign_id)
        .group_by(Screening.call_status, Screening.recommendation)
    ).all()
    stats = dict(total=0, pending=0, in_progress=0, shortlisted=0, manual_review=0, rejected=0, failed=0)
    for call_status, recommendation, count in rows:
        stats["total"] += count
        if call_status == "not_contacted":
            stats["pending"] += count
        elif call_status == "in_progress":
            stats["in_progress"] += count
        elif call_status == "failed":
            stats["failed"] += count
        elif call_status == "completed":
            if recommendation == "shortlisted":
                stats["shortlisted"] += count
            elif recommendation == "rejected":
                stats["rejected"] += count
            else:
                stats["manual_review"] += count
    return CampaignStats(**stats)


@router.post("", response_model=CampaignOut)
def create_campaign(payload: CampaignCreate, db: Session = Depends(get_db)):
    if payload.experience_min > payload.experience_max:
        raise HTTPException(400, "experience_min cannot exceed experience_max")
    campaign = Campaign(
        name=payload.name,
        position=payload.position,
        department=payload.department,
        location=payload.location,
        experience_min=payload.experience_min,
        experience_max=payload.experience_max,
        job_description=payload.job_description,
    )
    db.add(campaign)
    db.flush()

    if payload.candidate_ids:
        _attach_candidates(db, campaign, payload.candidate_ids)

    db.commit()
    db.refresh(campaign)
    return campaign


def _attach_candidates(db: Session, campaign: Campaign, candidate_ids: list[int]) -> int:
    existing = set(
        db.execute(
            select(Screening.candidate_id).where(Screening.campaign_id == campaign.id)
        ).scalars().all()
    )
    added = 0
    for cid in candidate_ids:
        if cid in existing:
            continue
        db.add(Screening(campaign_id=campaign.id, candidate_id=cid))
        existing.add(cid)
        added += 1
    campaign.total_candidates = (campaign.total_candidates or 0) + added
    return added


@router.post("/{campaign_id}/candidates/attach")
def attach_candidates(campaign_id: int, candidate_ids: list[int], db: Session = Depends(get_db)):
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    added = _attach_candidates(db, campaign, candidate_ids)
    db.commit()
    return {"added": added}


@router.post("/{campaign_id}/candidates/attach_all")
def attach_all_candidates(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    all_ids = db.execute(select(Candidate.id)).scalars().all()
    added = _attach_candidates(db, campaign, list(all_ids))
    db.commit()
    return {"added": added}


@router.post("/{campaign_id}/candidates/import", response_model=ImportSummaryOut)
async def import_candidates_into_campaign(
    campaign_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)
):
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Please upload a .csv file")
    content = await file.read()
    if not content:
        raise HTTPException(400, "File is empty")

    summary = import_candidates_csv(db, content)
    _attach_candidates(db, campaign, summary.touched_candidate_ids)
    db.commit()
    return summary.to_dict()


@router.get("", response_model=list[CampaignDetailOut])
def list_campaigns(db: Session = Depends(get_db)):
    campaigns = db.execute(select(Campaign).order_by(Campaign.created_at.desc())).scalars().all()
    out = []
    for c in campaigns:
        item = CampaignOut.model_validate(c).model_dump(mode="json")
        item["stats"] = _compute_stats(db, c.id).model_dump()
        out.append(item)
    return out


@router.get("/{campaign_id}", response_model=CampaignDetailOut)
def get_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    item = CampaignOut.model_validate(campaign).model_dump(mode="json")
    item["stats"] = _compute_stats(db, campaign_id).model_dump()
    return item


@router.post("/{campaign_id}/start")
def start_campaign(campaign_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    if campaign.status == "running":
        raise HTTPException(409, "Campaign is already running")
    total = db.scalar(
        select(func.count()).select_from(Screening).where(Screening.campaign_id == campaign_id)
    )
    if not total:
        raise HTTPException(400, "Add candidates to this campaign before starting it")
    start_campaign_async(campaign_id)
    return {"status": "started"}


@router.post("/{campaign_id}/cancel")
def cancel_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    request_cancel(campaign_id)
    return {"status": "cancel_requested"}


@router.get("/{campaign_id}/screenings", response_model=PageOut)
def list_screenings(
    campaign_id: int,
    status_filter: str | None = None,
    recommendation: str | None = None,
    search: str | None = None,
    sort: str = "score_desc",
    page: int = 1,
    page_size: int = 25,
    db: Session = Depends(get_db),
):
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    page_size = min(max(page_size, 1), 500)
    page = max(page, 1)

    query = select(Screening).join(Candidate).where(Screening.campaign_id == campaign_id)
    if status_filter:
        query = query.where(Screening.call_status == status_filter)
    if recommendation:
        query = query.where(Screening.recommendation == recommendation)
    if search:
        like = f"%{search}%"
        query = query.where(or_(Candidate.name.ilike(like), Candidate.phone.ilike(like)))

    if sort == "score_desc":
        query = query.order_by(Screening.ai_score.desc().nullslast())
    elif sort == "score_asc":
        query = query.order_by(Screening.ai_score.asc().nullsfirst())
    elif sort == "recent":
        query = query.order_by(Screening.last_attempt_at.desc().nullslast())
    else:
        query = query.order_by(Candidate.name.asc())

    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(query.offset((page - 1) * page_size).limit(page_size)).scalars().all()

    items = [
        ScreeningListItemOut(
            id=s.id,
            candidate_id=s.candidate_id,
            candidate_name=s.candidate.name,
            candidate_phone=s.candidate.phone,
            candidate_company=s.candidate.current_company,
            call_status=s.call_status,
            outcome_detail=s.outcome_detail,
            recommendation=s.recommendation,
            ai_score=s.ai_score,
            attempt_count=s.attempt_count,
            last_attempt_at=s.last_attempt_at,
        ).model_dump(mode="json")
        for s in rows
    ]
    return {"items": items, "total": total or 0, "page": page, "page_size": page_size}


@router.get("/{campaign_id}/export")
def export_campaign_csv(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    rows = db.execute(
        select(Screening).join(Candidate).where(Screening.campaign_id == campaign_id).order_by(
            Screening.ai_score.desc().nullslast()
        )
    ).scalars().all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "name", "phone", "email", "current_company", "call_status", "outcome_detail",
        "recommendation", "ai_score", "attempt_count", "summary",
    ])
    for s in rows:
        writer.writerow([
            s.candidate.name, s.candidate.phone, s.candidate.email, s.candidate.current_company,
            s.call_status, s.outcome_detail or "", s.recommendation or "", s.ai_score or "",
            s.attempt_count, (s.summary or "").replace("\n", " "),
        ])
    buf.seek(0)
    filename = f"campaign_{campaign_id}_results.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
