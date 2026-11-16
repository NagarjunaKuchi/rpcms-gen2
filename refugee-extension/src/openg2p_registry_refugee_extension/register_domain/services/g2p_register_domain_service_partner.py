import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from openg2p_registry_core.services import G2PRegisterDomainService

from ...integrations import get_integrations
from ...rules.partner_compliance import evaluate_partner
from .utils.validations import validation_error

_logger = logging.getLogger("g2p-register-partner-service")

REQUIRED = ("organisation_name", "ursb_registration_no", "ngo_permit_no")


class G2PRegisterDomainServicePartner(G2PRegisterDomainService):
    async def validate_domain_attributes(self, records: list[dict]):
        for record in records:
            for key in REQUIRED:
                if key in record and not str(record.get(key) or "").strip():
                    validation_error(f"{key} must not be empty")

    async def post_ingest(self, register_id: str, register_row, session: AsyncSession):
        """Runs in the Celery worker right after an approved registration creates the partner row: verify the
        organisation with URSB and the NGO Bureau and record the result (rules/partner_compliance.py).

        A system that is not configured or not reachable leaves compliance NOT_CHECKED; it never fails the
        registration and never guesses.
        """
        from ...config import Settings

        integrations = get_integrations()
        ursb = await integrations.lookup_organisation((register_row.ursb_registration_no or "").strip())
        permit = await integrations.lookup_permit((register_row.ngo_permit_no or "").strip())
        result = evaluate_partner(
            register_row.organisation_name,
            ursb,
            permit,
            datetime.now(timezone.utc).date(),
            Settings.get_config().permit_renewal_alert_days,
        )
        for field, value in result.items():
            setattr(register_row, field, value)
        await session.flush()

    def construct_search_text(self, payload: dict, extra: list[str] = None) -> str:
        keys = ["organisation_name", "partner_code", "ursb_registration_no", "ngo_permit_no", "proposed_area", "sector", "country_director"]
        parts = [str(v).strip() for v in (extra or []) if str(v).strip()]
        parts += [str(payload.get(k) or "").strip() for k in keys if str(payload.get(k) or "").strip()]
        return " ".join(parts).strip()

    def construct_record_name(self, payload: dict, extra: list[str] = None) -> str:
        parts = [str(v).strip() for v in (extra or []) if str(v).strip()]
        parts += [str(payload.get(k) or "").strip() for k in ("organisation_name", "partner_code") if str(payload.get(k) or "").strip()]
        return " ".join(parts).strip() or str(payload.get("functional_record_id") or "").strip()
