from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Campaign, Candidate, Screening
from ..schemas import LeaderboardItemOut, PageOut

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])


@router.get("", response_model=PageOut)
def get_leaderboard(
    campaign_id: int | None = None,
    page: int = 1,
    page_size: int = 25,
    db: Session = Depends(get_db),
):
    page_size = min(max(page_size, 1), 200)
    page = max(page, 1)

    query = (
        select(Screening)
        .join(Candidate)
        .join(Campaign)
        .where(Screening.call_status == "completed")
        .where(Screening.ai_score.isnot(None))
    )
    if campaign_id:
        query = query.where(Screening.campaign_id == campaign_id)
    query = query.order_by(Screening.ai_score.desc())

    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(query.offset((page - 1) * page_size).limit(page_size)).scalars().all()

    start_rank = (page - 1) * page_size + 1
    items = [
        LeaderboardItemOut(
            rank=start_rank + i,
            screening_id=s.id,
            candidate_name=s.candidate.name,
            candidate_company=s.candidate.current_company,
            campaign_id=s.campaign_id,
            campaign_name=s.campaign.name,
            ai_score=s.ai_score,
            jd_match_pct=s.jd_match_pct,
            recommendation=s.recruiter_override or s.recommendation,
        ).model_dump(mode="json")
        for i, s in enumerate(rows)
    ]
    return {"items": items, "total": total or 0, "page": page, "page_size": page_size}
