"""HTTP endpoint that runs the daily checks now. Registered on the staff API only (reporting_api_enabled).

A daily trigger calls it; staff can also call it by hand. Running it twice in a day is safe."""
import logging

from fastapi import Request
from iam_core.user_auth.decorators import require_permissions
from openg2p_fastapi_common.controller import BaseController

from .service import get_jobs_service

_logger = logging.getLogger("rpcms-jobs")


class RpcmsJobsController(BaseController):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.router.tags += ["/rpcms-jobs"]
        self.router.prefix = "/rpcms-jobs"
        self.router.add_api_route("/run", self.run, methods=["POST"], operation_id="rpcms_jobs_run")

    @require_permissions({"rpcmsJobs:run"})
    async def run(self, request: Request):
        """Run the daily checks: SMS to partners whose NGO permit is about to expire, and ID-expiry flags (with the
        renewal SMS) for refugees whose card expires soon. Answers with counts per outcome."""
        return await get_jobs_service().run()
