import logging
from datetime import datetime, timezone

from sqlalchemy import select

from openg2p_registry_core.services import G2PRegisterDomainService

from ...integrations import get_integrations
from ...rules.mou_verification import evaluate_mou
from .utils.validations import as_int, validation_error

_logger = logging.getLogger("g2p-register-projectmou-service")

REQUIRED = ("mou_number", "ugpass_document_id")
SEARCH_KEYS = ["mou_number", "ugpass_document_id", "verification_status"]
NAME_KEYS = ["mou_number", "ugpass_document_id"]


class G2PRegisterDomainServiceProjectMou(G2PRegisterDomainService):
    async def validate_domain_attributes(self, records: list[dict]):
        for record in records:
            for key in REQUIRED:
                if key in record and not str(record.get(key) or "").strip():
                    validation_error(f"{key} must not be empty")
            for key in ("expected_signatures", "expected_eseals"):
                if record.get(key) not in (None, ""):
                    value = as_int(record.get(key))
                    if value is None or value < 0:
                        validation_error(f"{key} must be a non-negative whole number")

    async def post_approve(self, change_request, session):
        """After an approved add or edit: ask UGPass about the document and store the result on the MoU row.
        Editing the row again (e.g. a remark) re-checks it."""
        from openg2p_registry_core.models import G2PRegisterChangeRequestPayload

        from ...config import Settings
        from ..models import G2PRegisterProjectMou as Mou

        settings = Settings.get_config()
        payload = (
            await session.execute(
                select(G2PRegisterChangeRequestPayload).where(
                    G2PRegisterChangeRequestPayload.change_request_id == change_request.change_request_id
                )
            )
        ).scalar()
        for row in (payload.change_payload if payload else None) or []:
            if row.get("edit_action") not in (None, "ADD", "UPDATE"):
                continue
            if row.get("internal_record_id"):
                query = select(Mou).where(Mou.internal_record_id == row["internal_record_id"])
            elif row.get("mou_number"):
                query = select(Mou).where(Mou.mou_number == row["mou_number"])
            else:
                continue
            stored = (await session.execute(query.limit(1))).scalar()
            if stored is None:
                _logger.warning("MoU %s not found after approval; not verified", row.get("mou_number"))
                continue
            response = await get_integrations().verify_document((stored.ugpass_document_id or "").strip())
            result = evaluate_mou(
                response,
                stored.expected_signatures if stored.expected_signatures is not None else settings.mou_expected_signatures,
                stored.expected_eseals if stored.expected_eseals is not None else settings.mou_expected_eseals,
                datetime.now(timezone.utc).date(),
            )
            for field, value in result.items():
                setattr(stored, field, value)
            await session.flush()

    def construct_search_text(self, payload: dict, extra: list[str] = None) -> str:
        parts = [str(v).strip() for v in (extra or []) if str(v).strip()]
        parts += [str(payload.get(k) or "").strip() for k in SEARCH_KEYS if str(payload.get(k) or "").strip()]
        return " ".join(parts).strip()

    def construct_record_name(self, payload: dict, extra: list[str] = None) -> str:
        parts = [str(v).strip() for v in (extra or []) if str(v).strip()]
        parts += [str(payload.get(k) or "").strip() for k in NAME_KEYS if str(payload.get(k) or "").strip()]
        return " ".join(parts).strip() or str(payload.get("functional_record_id") or "").strip()
