"""HTTP endpoint for syncing field handovers. Registered on the staff API only (reporting_api_enabled)."""
import logging
from typing import Any, List

from fastapi import HTTPException, Request
from iam_core.user_auth.decorators import require_permissions
from openg2p_fastapi_common.controller import BaseController
from pydantic import BaseModel

from .service import HandoverError, get_handover_service

_logger = logging.getLogger("rpcms-handover-sync")


class SyncRequest(BaseModel):
    batch_id: str  # the phone's id for this upload; stored on every record of it
    records: List[Any]


def _actor(request: Request) -> str:
    auth = getattr(request.state, "auth", None)
    return getattr(auth, "preferred_username", None) or getattr(auth, "name", None) or getattr(auth, "sub", None) or "unknown"


class RpcmsHandoverController(BaseController):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.router.tags += ["/rpcms-handovers"]
        self.router.prefix = "/rpcms-handovers"
        self.router.add_api_route("/sync", self.sync, methods=["POST"], operation_id="rpcms_handover_sync")

    @require_permissions({"rpcmsHandover:sync"})
    async def sync(self, body: SyncRequest, request: Request):
        """Record a batch of handovers captured on a phone. Always answers per record; resend only the ones that
        did not end SYNCED or ALREADY_SYNCED (sending a record again is safe: the phone's record id is remembered)."""
        try:
            return await get_handover_service().sync(_actor(request), body.batch_id, body.records)
        except HandoverError as e:
            raise HTTPException(status_code=e.status, detail=str(e))
