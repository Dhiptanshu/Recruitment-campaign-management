import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_EXPERIENCE_YEARS = 60
MAX_RETRY_ATTEMPTS = 5


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
    name: str = Field(min_length=1, max_length=300)
    position: str = Field(min_length=1, max_length=200)
    department: Optional[str] = Field(None, max_length=200)
    location: Optional[str] = Field(None, max_length=200)
    experience_min: int = Field(0, ge=0, le=MAX_EXPERIENCE_YEARS)
    experience_max: int = Field(10, ge=0, le=MAX_EXPERIENCE_YEARS)
    job_description: Optional[str] = Field(None, max_length=10_000)
    max_attempts: int = Field(2, ge=1, le=MAX_RETRY_ATTEMPTS)
    candidate_ids: Optional[list[int]] = None  # if omitted, all candidates are added

    @field_validator("name", "position")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("cannot be blank")
        return v

    @model_validator(mode="after")
    def _experience_range(self):
        if self.experience_min > self.experience_max:
            raise ValueError("experience_min cannot exceed experience_max")
        return self


class CampaignUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=300)
    position: Optional[str] = Field(None, min_length=1, max_length=200)
    department: Optional[str] = Field(None, max_length=200)
    location: Optional[str] = Field(None, max_length=200)
    experience_min: Optional[int] = Field(None, ge=0, le=MAX_EXPERIENCE_YEARS)
    experience_max: Optional[int] = Field(None, ge=0, le=MAX_EXPERIENCE_YEARS)
    job_description: Optional[str] = Field(None, max_length=10_000)
    max_attempts: Optional[int] = Field(None, ge=1, le=MAX_RETRY_ATTEMPTS)

    @field_validator("name", "position")
    @classmethod
    def _not_blank(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("cannot be blank")
        return v
    # cross-field experience_min <= experience_max is enforced in the router,
    # since this is a partial update and either field may be absent here --
    # the router has the campaign's current values to fill the gap.


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
    max_attempts: int
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
    recruiter_override: Optional[str] = None
    effective_recommendation: Optional[str] = None
    ai_score: Optional[int] = None
    jd_match_pct: Optional[int] = None
    attempt_count: int
    last_attempt_at: Optional[datetime.datetime] = None


class TranscriptTurn(BaseModel):
    speaker: str
    text: str


class ScreeningDetailOut(BaseModel):
    id: int
    campaign_id: int
    campaign_name: str
    candidate: CandidateOut
    call_status: str
    outcome_detail: Optional[str] = None
    recommendation: Optional[str] = None
    ai_score: Optional[int] = None
    ai_source: Optional[str] = None  # "llm" | "heuristic"
    summary: Optional[str] = None
    extracted_data: Optional[dict] = None
    transcript: Optional[list[TranscriptTurn]] = None
    error_message: Optional[str] = None
    call_duration_seconds: Optional[int] = None
    attempt_count: int
    max_attempts: int
    last_attempt_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime

    jd_match_pct: Optional[int] = None
    recruiter_note: Optional[str] = None
    recruiter_override: Optional[str] = None
    effective_recommendation: Optional[str] = None
    reviewed_at: Optional[datetime.datetime] = None
    interview_suggestion: Optional[dict] = None


class RecruiterFeedbackIn(BaseModel):
    note: Optional[str] = Field(None, max_length=4000)
    override: Optional[str] = None  # shortlisted | manual_review | rejected
    clear_override: bool = False


class LeaderboardItemOut(BaseModel):
    rank: int
    screening_id: int
    candidate_name: str
    candidate_company: Optional[str] = None
    campaign_id: int
    campaign_name: str
    ai_score: Optional[int] = None
    jd_match_pct: Optional[int] = None
    recommendation: Optional[str] = None


class PageOut(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
