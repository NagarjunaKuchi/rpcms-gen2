"""HTTP endpoints for the quarterly reports. Registered on the staff API only (reporting_api_enabled)."""
import logging

from fastapi import HTTPException, Request
from iam_core.user_auth.decorators import require_permissions
from openg2p_fastapi_common.controller import BaseController
from pydantic import BaseModel

from .service import ReportingError, get_reporting_service

_logger = logging.getLogger("rpcms-reporting")

VIEW = {"rpcmsReport:view"}
SUBMIT = {"rpcmsReport:submit"}


class SubmitRequest(BaseModel):
    system: str  # AMP | NIMES
    quarter: str  # 2026-Q3
    force: bool = False


def _actor(request: Request) -> str:
    auth = getattr(request.state, "auth", None)
    return getattr(auth, "preferred_username", None) or getattr(auth, "name", None) or getattr(auth, "sub", None) or "unknown"


class RpcmsReportController(BaseController):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.router.tags += ["/rpcms-reports"]
        self.router.prefix = "/rpcms-reports"
        self.router.add_api_route("/summary", self.summary, methods=["GET"], operation_id="rpcms_report_summary")
        self.router.add_api_route("/preview", self.preview, methods=["GET"], operation_id="rpcms_report_preview")
        self.router.add_api_route("/submit", self.submit, methods=["POST"], operation_id="rpcms_report_submit")
        self.router.add_api_route("/submissions", self.submissions, methods=["GET"], operation_id="rpcms_report_submissions")

    @staticmethod
    def _guard(call):
        async def run():
            try:
                return await call()
            except ReportingError as e:
                raise HTTPException(status_code=e.status, detail=str(e))
            except ValueError as e:  # bad quarter
                raise HTTPException(status_code=400, detail=str(e))

        return run()

    @require_permissions(VIEW)
    async def summary(self, quarter: str):
        return await self._guard(lambda: get_reporting_service().summary(quarter))

    @require_permissions(VIEW)
    async def preview(self, system: str, quarter: str):
        """What would be sent to AMP or NIMES for a quarter, and what cannot be sent and why. Sends nothing."""
        return await self._guard(lambda: get_reporting_service().preview(system, quarter))

    @require_permissions(SUBMIT)
    async def submit(self, body: SubmitRequest, request: Request):
        return await self._guard(lambda: get_reporting_service().submit(body.system, body.quarter, _actor(request), body.force))

    @require_permissions(VIEW)
    async def submissions(self, limit: int = 100):
        return await self._guard(lambda: get_reporting_service().history(limit))
