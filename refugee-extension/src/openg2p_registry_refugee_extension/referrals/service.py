"""Referral cases: every refused duplicate-assistance entry is a case to review (see rules/referral_review.py)."""
from datetime import datetime

from sqlalchemy import select

from ..rules.referral_review import decide


class ReferralError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _view(c) -> dict:
    return {"case_id": c.attempt_id, "case_ref": c.attempt_id[:8], "detected_at": c.detected_at.isoformat() if c.detected_at else None,
            "registrant_progres_id": c.registrant_progres_id, "assistance_type": c.assistance_type,
            "distribution_cycle": c.distribution_cycle, "partner_code": c.partner_code,
            "already_received_by": c.holder_progres_id, "reason": c.reason, "status": c.review_status,
            "reviewed_by": c.reviewed_by, "reviewed_at": c.reviewed_at.isoformat() if c.reviewed_at else None,
            "review_note": c.review_note, "release_used": bool(c.released_used_at)}


class ReferralService:
    def __init__(self, session_maker):
        self._session_maker = session_maker

    async def list_cases(self, status: str | None = "OPEN", limit: int = 100) -> list[dict]:
        from ..register_domain.models import RpcmsDuplicateAttempt as Case

        query = select(Case).order_by(Case.detected_at.desc()).limit(max(1, min(limit, 500)))
        if status:
            query = query.where(Case.review_status == status.upper())
        async with self._session_maker() as session:
            return [_view(c) for c in (await session.execute(query)).scalars()]

    async def review(self, case_id: str, decision: str, note: str | None, actor: str) -> dict:
        from ..register_domain.models import RpcmsDuplicateAttempt as Case

        async with self._session_maker() as session:
            case = (await session.execute(select(Case).where(Case.attempt_id == case_id).with_for_update())).scalar()
            if case is None:
                raise ReferralError("no such case", 404)
            status, why = decide(case.review_status, decision, note)
            if status is None:
                raise ReferralError(why, 409 if "already decided" in why else 400)
            case.review_status, case.reviewed_by, case.reviewed_at = status, actor, datetime.utcnow()
            case.review_note = (note or "").strip() or None
            await session.commit()
            return _view(case)


def get_referral_service() -> ReferralService:
    from openg2p_fastapi_common.context import get_async_session_maker

    return ReferralService(get_async_session_maker())
