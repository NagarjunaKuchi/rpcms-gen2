"""HTTP endpoints for duplicate-assistance referral cases. Registered on the staff API only (reporting_api_enabled).

Who reviews a case, and how fast, is not decided: any user with the review permission can decide a case."""
import logging

from fastapi import HTTPException, Request
from iam_core.user_auth.decorators import require_permissions
from openg2p_fastapi_common.controller import BaseController
from pydantic import BaseModel

from .service import ReferralError, get_referral_service

_logger = logging.getLogger("rpcms-referrals")


class ReviewRequest(BaseModel):
    decision: str  # CONFIRM (a real duplicate, stays refused) or RELEASE (the entry may be recorded once)
    note: str | None = None


def _actor(request: Request) -> str:
    auth = getattr(request.state, "auth", None)
    return getattr(auth, "preferred_username", None) or getattr(auth, "name", None) or getattr(auth, "sub", None) or "unknown"


class RpcmsReferralController(BaseController):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.router.tags += ["/rpcms-referrals"]
        self.router.prefix = "/rpcms-referrals"
        self.router.add_api_route("", self.list_cases, methods=["GET"], operation_id="rpcms_referrals_list")
        self.router.add_api_route("/{case_id}/review", self.review, methods=["POST"], operation_id="rpcms_referrals_review")

    @require_permissions({"rpcmsReferral:view"})
    async def list_cases(self, status: str = "OPEN", limit: int = 100):
        """Referral cases, newest first. status: OPEN (default), CONFIRMED_DUPLICATE, RELEASED, or empty for all."""
        return await get_referral_service().list_cases(status or None, limit)

    @require_permissions({"rpcmsReferral:review"})
    async def review(self, case_id: str, body: ReviewRequest, request: Request):
        try:
            return await get_referral_service().review(case_id, body.decision, body.note, _actor(request))
        except ReferralError as e:
            raise HTTPException(status_code=e.status, detail=str(e))
