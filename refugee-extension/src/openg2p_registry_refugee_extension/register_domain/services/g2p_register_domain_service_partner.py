import logging
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from openg2p_registry_core.services import G2PRegisterDomainService

from .utils.mocks_client import call_mock
from .utils.validations import validation_error

_logger = logging.getLogger("g2p-register-partner-service")

REQUIRED = ("organisation_name", "ursb_registration_no", "ngo_permit_no")
RENEWAL_ALERT_DAYS = 60  # ASSUMPTION: the demo says "alerted 60 days before renewal"; not a platform setting


class G2PRegisterDomainServicePartner(G2PRegisterDomainService):
    async def validate_domain_attributes(self, records: list[dict]):
        for record in records:
            for key in REQUIRED:
                if key in record and not str(record.get(key) or "").strip():
                    validation_error(f"{key} must not be empty")

    async def post_ingest(self, register_id: str, register_row, session: AsyncSession):
        """Runs in the Celery worker right after an approved registration creates the partner row:
        verify the organisation with URSB and the NGO Bureau (mock services in dev) and record the result."""
        today = date.today()
        notes = []
        ursb_ok = permit_ok = False

        ursb = await call_mock(
            "GET", f"/ursb/v1/organisations?registration_no={register_row.ursb_registration_no or ''}", None
        )
        if ursb is None:
            register_row.ursb_status = "NOT_CHECKED"
            notes.append("URSB service not reachable")
        elif ursb[0] == 200:
            register_row.ursb_status = str(ursb[1].get("status") or "UNKNOWN")
            register_row.ursb_registered_name = ursb[1].get("name")
            ursb_ok = register_row.ursb_status == "ACTIVE"
            if ursb_ok and (register_row.organisation_name or "").strip().lower() != str(ursb[1].get("name") or "").strip().lower():
                ursb_ok = False
                notes.append(f"Name differs from URSB record ({ursb[1].get('name')})")
        else:
            register_row.ursb_status = "NOT_FOUND"
            notes.append("URSB registration number not found")

        permit = await call_mock(
            "GET", f"/ngobureau/v1/permits?permit_no={register_row.ngo_permit_no or ''}", None
        )
        if permit is None:
            register_row.ngo_permit_status = "NOT_CHECKED"
            notes.append("NGO Bureau service not reachable")
        elif permit[0] == 200:
            valid_to = date.fromisoformat(str(permit[1]["valid_to"])[:10])
            register_row.permit_valid_to = valid_to
            register_row.permit_renewal_alert_date = valid_to - timedelta(days=RENEWAL_ALERT_DAYS)
            expired = valid_to < today
            register_row.ngo_permit_status = "EXPIRED" if expired else str(permit[1].get("status") or "UNKNOWN")
            permit_ok = register_row.ngo_permit_status == "VALID"
            if expired:
                notes.append(f"NGO permit expired on {valid_to}")
        else:
            register_row.ngo_permit_status = "NOT_FOUND"
            notes.append("NGO permit number not found")

        if ursb is None or permit is None:
            register_row.compliance_status = "NOT_CHECKED"
        else:
            register_row.compliance_status = "COMPLIANT" if (ursb_ok and permit_ok) else "NON_COMPLIANT"
        register_row.compliance_checked_on = today
        register_row.compliance_notes = "; ".join(notes) or None
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
