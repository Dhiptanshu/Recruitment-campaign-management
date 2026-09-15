import csv
import io

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Campaign, Candidate, Screening
from ..schemas import (
    CampaignCreate, CampaignUpdate, CampaignOut, CampaignDetailOut, CampaignStats,
    ScreeningListItemOut, PageOut, ImportSummaryOut,
)
from ..services.csv_import import import_candidates_file, SUPPORTED_EXTENSIONS
from ..services.campaign_runner import start_campaign_async, request_cancel

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])

# the recruiter's override always wins over the AI recommendation wherever
# a bucket (dashboard stats, filters, exports) is computed
EFFECTIVE_RECOMMENDATION = func.coalesce(Screening.recruiter_override, Screening.recommendation)


def _compute_stats(db: Session, campaign_id: int) -> CampaignStats:
    rows = db.execute(
        select(Screening.call_status, EFFECTIVE_RECOMMENDATION, func.count())
        .where(Screening.campaign_id == campaign_id)
        .group_by(Screening.call_status, EFFECTIVE_RECOMMENDATION)
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
    ext = file.filename.lower().rsplit(".", 1)[-1] if "." in file.filename else ""
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(400, "Please upload a .csv or .xlsx file")
    content = await file.read()
    if not content:
        raise HTTPException(400, "File is empty")

    summary = import_candidates_file(db, file.filename, content)
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


@router.patch("/{campaign_id}", response_model=CampaignDetailOut)
def update_campaign(campaign_id: int, payload: CampaignUpdate, db: Session = Depends(get_db)):
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    data = payload.model_dump(exclude_unset=True)
    new_min = data.get("experience_min", campaign.experience_min)
    new_max = data.get("experience_max", campaign.experience_max)
    if new_min > new_max:
        raise HTTPException(400, "experience_min cannot exceed experience_max")

    for field, value in data.items():
        setattr(campaign, field, value)
    db.commit()
    db.refresh(campaign)

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
        query = query.where(EFFECTIVE_RECOMMENDATION == recommendation)
    if search:
        like = f"%{search}%"
        query = query.where(or_(Candidate.name.ilike(like), Candidate.phone.ilike(like)))

    if sort == "score_desc":
        query = query.order_by(Screening.ai_score.desc().nullslast())
    elif sort == "score_asc":
        query = query.order_by(Screening.ai_score.asc().nullsfirst())
    elif sort == "jd_match_desc":
        query = query.order_by(Screening.jd_match_pct.desc().nullslast())
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
            recruiter_override=s.recruiter_override,
            effective_recommendation=s.recruiter_override or s.recommendation,
            ai_score=s.ai_score,
            jd_match_pct=s.jd_match_pct,
            attempt_count=s.attempt_count,
            last_attempt_at=s.last_attempt_at,
        ).model_dump(mode="json")
        for s in rows
    ]
    return {"items": items, "total": total or 0, "page": page, "page_size": page_size}


EXPORT_HEADERS = [
    "name", "phone", "email", "current_company", "call_status", "outcome_detail",
    "ai_recommendation", "recruiter_override", "effective_recommendation", "ai_score",
    "jd_match_pct", "attempt_count", "summary", "recruiter_note",
]


def _export_row(s: Screening) -> list:
    return [
        s.candidate.name, s.candidate.phone, s.candidate.email, s.candidate.current_company,
        s.call_status, s.outcome_detail or "", s.recommendation or "", s.recruiter_override or "",
        s.recruiter_override or s.recommendation or "", s.ai_score or "", s.jd_match_pct or "",
        s.attempt_count, (s.summary or "").replace("\n", " "), (s.recruiter_note or "").replace("\n", " "),
    ]


@router.get("/{campaign_id}/export")
def export_campaign(campaign_id: int, format: str = "csv", db: Session = Depends(get_db)):
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    if format not in ("csv", "xlsx"):
        raise HTTPException(400, "format must be 'csv' or 'xlsx'")

    rows = db.execute(
        select(Screening).join(Candidate).where(Screening.campaign_id == campaign_id).order_by(
            Screening.ai_score.desc().nullslast()
        )
    ).scalars().all()

    if format == "xlsx":
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = "Results"
        ws.append(EXPORT_HEADERS)
        for s in rows:
            ws.append(_export_row(s))
        for col in ws.columns:
            width = min(60, max(10, max(len(str(c.value)) for c in col if c.value is not None) + 2))
            ws.column_dimensions[col[0].column_letter].width = width

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        filename = f"campaign_{campaign_id}_results.xlsx"
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(EXPORT_HEADERS)
    for s in rows:
        writer.writerow(_export_row(s))
    buf.seek(0)
    filename = f"campaign_{campaign_id}_results.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
