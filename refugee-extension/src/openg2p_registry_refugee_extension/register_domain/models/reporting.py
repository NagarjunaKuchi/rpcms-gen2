import uuid
from datetime import date, datetime

from openg2p_fastapi_common.models import BaseORMModel
from sqlalchemy import Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column


class RpcmsDuplicateAttempt(BaseORMModel):
    """One refused duplicate-assistance entry. Duplicates are refused when entered, so nothing else records them;
    this is what the dashboard's 'duplicate cases flagged' counts."""

    __tablename__ = "rpcms_duplicate_attempt"

    attempt_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    detected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    detected_by: Mapped[str] = mapped_column(String, nullable=True)
    registrant_progres_id: Mapped[str] = mapped_column(String, nullable=True, index=True)
    assistance_type: Mapped[str] = mapped_column(String, nullable=True)
    distribution_cycle: Mapped[str] = mapped_column(String, nullable=True)
    partner_code: Mapped[str] = mapped_column(String, nullable=True, index=True)
    reason: Mapped[str] = mapped_column(String, nullable=True)
    holder_progres_id: Mapped[str] = mapped_column(String, nullable=True)  # who already received it (a household member)
    # Referral: every refused duplicate is a case to review. OPEN -> CONFIRMED_DUPLICATE or RELEASED (decided once).
    review_status: Mapped[str] = mapped_column(String, nullable=False, default="OPEN", server_default="OPEN", index=True)
    reviewed_by: Mapped[str] = mapped_column(String, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    review_note: Mapped[str] = mapped_column(String, nullable=True)
    released_used_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)  # a release lets the entry through once


class RpcmsReportSubmission(BaseORMModel):
    """One attempt to send a quarterly report to an external system (AMP or NIMES), and what happened."""

    __tablename__ = "rpcms_report_submission"

    submission_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    system: Mapped[str] = mapped_column(String, nullable=False, index=True)  # AMP | NIMES
    quarter: Mapped[str] = mapped_column(String, nullable=False, index=True)  # 2026-Q3
    submitted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    submitted_by: Mapped[str] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)  # SENT | FAILED | NOT_CONFIGURED
    external_reference: Mapped[str] = mapped_column(String, nullable=True)
    records_sent: Mapped[int] = mapped_column(Integer, nullable=True)
    payload_sha256: Mapped[str] = mapped_column(String, nullable=True)
    detail: Mapped[str] = mapped_column(Text, nullable=True)
