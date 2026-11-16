import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from openg2p_registry_core.services import G2PRegisterDomainService

from ...integrations import get_integrations
from ...rules.project_funding import evaluate_funding
from .utils.validations import as_float, as_int, parse_date, validation_error

_logger = logging.getLogger("g2p-register-project-service")

REQUIRED = ("project_code", "project_name", "partner_code")
SEARCH_KEYS = ["project_code", "project_name", "partner_code", "partner_name", "amp_record_no", "area"]
NAME_KEYS = ["project_code", "project_name"]


class G2PRegisterDomainServiceProject(G2PRegisterDomainService):
    async def validate_domain_attributes(self, records: list[dict]):
        for record in records:
            for key in REQUIRED:
                if key in record and not str(record.get(key) or "").strip():
                    validation_error(f"{key} must not be empty")
            for key in ("project_value", "household_rate"):
                if record.get(key) not in (None, ""):
                    value = as_float(record.get(key))
                    if value is None or value < 0:
                        validation_error(f"{key} must be a non-negative number")
            if record.get("target_households") not in (None, ""):
                value = as_int(record.get("target_households"))
                if value is None or value < 0:
                    validation_error("target_households must be a non-negative whole number")
            for key in ("start_date", "end_date"):
                if record.get(key) not in (None, "") and parse_date(record.get(key)) is None:
                    validation_error(f"{key} is not a valid date")
            start, end = parse_date(record.get("start_date")), parse_date(record.get("end_date"))
            if start and end and end < start:
                validation_error("end_date must not be before start_date")

    async def post_ingest(self, register_id: str, register_row, session: AsyncSession):
        """After an approved registration: ask AMP for the funding record and store the comparison on the project."""
        record_no = (register_row.amp_record_no or "").strip()
        today = datetime.now(timezone.utc).date()
        if not record_no:
            result = {"amp_status": "NOT_CHECKED", "amp_notes": "No AMP record number entered", "amp_checked_on": today}
        else:
            response = await get_integrations().lookup_funding(record_no)
            result = evaluate_funding(register_row.project_value, register_row.currency, response, today)
        for field, value in result.items():
            setattr(register_row, field, value)
        await session.flush()

    def construct_search_text(self, payload: dict, extra: list[str] = None) -> str:
        parts = [str(v).strip() for v in (extra or []) if str(v).strip()]
        parts += [str(payload.get(k) or "").strip() for k in SEARCH_KEYS if str(payload.get(k) or "").strip()]
        return " ".join(parts).strip()

    def construct_record_name(self, payload: dict, extra: list[str] = None) -> str:
        parts = [str(v).strip() for v in (extra or []) if str(v).strip()]
        parts += [str(payload.get(k) or "").strip() for k in NAME_KEYS if str(payload.get(k) or "").strip()]
        return " ".join(parts).strip() or str(payload.get("functional_record_id") or "").strip()
