import datetime
from sqlalchemy import (
    String, Integer, Text, DateTime, ForeignKey, UniqueConstraint, Index, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime.datetime:
    return datetime.datetime.utcnow()


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(200), nullable=True)
    current_company: Mapped[str] = mapped_column(String(200), nullable=True)
    external_ref: Mapped[str] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    screenings: Mapped[list["Screening"]] = relationship(back_populates="candidate")


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(300))
    position: Mapped[str] = mapped_column(String(200))
    department: Mapped[str] = mapped_column(String(200), nullable=True)
    location: Mapped[str] = mapped_column(String(200), nullable=True)
    experience_min: Mapped[float] = mapped_column(Integer, default=0)
    experience_max: Mapped[float] = mapped_column(Integer, default=99)
    job_description: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft, running, paused, completed
    total_candidates: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow)
    started_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)

    screenings: Mapped[list["Screening"]] = relationship(back_populates="campaign", cascade="all, delete-orphan")


class Screening(Base):
    """One candidate's screening record within one campaign (the simulated call + outcome)."""

    __tablename__ = "screenings"
    __table_args__ = (
        UniqueConstraint("campaign_id", "candidate_id", name="uq_campaign_candidate"),
        Index("ix_screening_campaign_status", "campaign_id", "call_status"),
        Index("ix_screening_campaign_recommendation", "campaign_id", "recommendation"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"))
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"))

    # not_contacted -> in_progress -> completed | failed
    call_status: Mapped[str] = mapped_column(String(20), default="not_contacted", index=True)
    outcome_detail: Mapped[str] = mapped_column(String(30), nullable=True)  # success/no_answer/voicemail/technical_error
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=2)

    recommendation: Mapped[str] = mapped_column(String(20), nullable=True, index=True)  # shortlisted/manual_review/rejected
    ai_score: Mapped[int] = mapped_column(Integer, nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=True)
    extracted_data: Mapped[dict] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    call_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=True)

    # % overlap between the campaign's job_description and the candidate's
    # captured skills; null when the campaign has no JD text with recognizable
    # skill keywords (matching wasn't applicable, not "0% match")
    jd_match_pct: Mapped[int] = mapped_column(Integer, nullable=True)

    # a recruiter can leave a note and/or override the AI's recommendation;
    # the override always wins over `recommendation` wherever a bucket is shown
    recruiter_note: Mapped[str] = mapped_column(Text, nullable=True)
    recruiter_override: Mapped[str] = mapped_column(String(20), nullable=True, index=True)
    reviewed_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow)
    last_attempt_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)

    campaign: Mapped["Campaign"] = relationship(back_populates="screenings")
    candidate: Mapped["Candidate"] = relationship(back_populates="screenings")
