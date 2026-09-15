from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Candidate
from ..schemas import CandidateOut, ImportSummaryOut, PageOut
from ..services.csv_import import import_candidates_file, SUPPORTED_EXTENSIONS

router = APIRouter(prefix="/api/candidates", tags=["candidates"])

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


@router.post("/import", response_model=ImportSummaryOut)
async def import_candidates(file: UploadFile = File(...), db: Session = Depends(get_db)):
    ext = file.filename.lower().rsplit(".", 1)[-1] if "." in file.filename else ""
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(400, "Please upload a .csv or .xlsx file")
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(400, "File too large (max 50 MB)")
    if len(content) == 0:
        raise HTTPException(400, "File is empty")
    try:
        summary = import_candidates_file(db, file.filename, content)
    except Exception as exc:
        db.rollback()
        raise HTTPException(400, f"Could not read this file -- is it a valid, non-corrupted .{ext}? ({exc})")
    return summary.to_dict()


@router.get("", response_model=PageOut)
def list_candidates(
    search: str | None = None,
    page: int = 1,
    page_size: int = 25,
    db: Session = Depends(get_db),
):
    page_size = min(max(page_size, 1), 200)
    page = max(page, 1)
    query = select(Candidate)
    if search:
        like = f"%{search}%"
        query = query.where(
            or_(Candidate.name.ilike(like), Candidate.phone.ilike(like), Candidate.email.ilike(like))
        )
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(
        query.order_by(Candidate.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    return {
        "items": [CandidateOut.model_validate(r).model_dump(mode="json") for r in rows],
        "total": total or 0,
        "page": page,
        "page_size": page_size,
    }


@router.get("/count")
def count_candidates(db: Session = Depends(get_db)):
    total = db.scalar(select(func.count()).select_from(Candidate))
    return {"total": total or 0}
