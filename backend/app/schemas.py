import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CandidateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    phone: str
    email: Optional[str] = None
    current_company: Optional[str] = None
    created_at: datetime.datetime


class ImportSummaryOut(BaseModel):
    total_rows: int
    imported: int
    updated: int
    skipped: int
    error_count: int
    errors: list[dict]


class CampaignCreate(BaseModel):
    name: str
    position: str
    department: Optional[str] = None
    location: Optional[str] = None
    experience_min: int = 0
    experience_max: int = 10
    job_description: Optional[str] = None
    candidate_ids: Optional[list[int]] = None  # if omitted, all candidates are added


class CampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    position: str
    department: Optional[str] = None
    location: Optional[str] = None
    experience_min: int
    experience_max: int
    job_description: Optional[str] = None
    status: str
    total_candidates: int
    created_at: datetime.datetime
    started_at: Optional[datetime.datetime] = None
    completed_at: Optional[datetime.datetime] = None


class CampaignStats(BaseModel):
    total: int
    pending: int
    in_progress: int
    shortlisted: int
    manual_review: int
    rejected: int
    failed: int


class CampaignDetailOut(CampaignOut):
    stats: CampaignStats


class ScreeningListItemOut(BaseModel):
    id: int
    candidate_id: int
    candidate_name: str
    candidate_phone: str
    candidate_company: Optional[str] = None
    call_status: str
    outcome_detail: Optional[str] = None
    recommendation: Optional[str] = None
    ai_score: Optional[int] = None
    attempt_count: int
    last_attempt_at: Optional[datetime.datetime] = None


class ScreeningDetailOut(BaseModel):
    id: int
    campaign_id: int
    campaign_name: str
    candidate: CandidateOut
    call_status: str
    outcome_detail: Optional[str] = None
    recommendation: Optional[str] = None
    ai_score: Optional[int] = None
    summary: Optional[str] = None
    extracted_data: Optional[dict] = None
    error_message: Optional[str] = None
    call_duration_seconds: Optional[int] = None
    attempt_count: int
    max_attempts: int
    last_attempt_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime


class PageOut(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
