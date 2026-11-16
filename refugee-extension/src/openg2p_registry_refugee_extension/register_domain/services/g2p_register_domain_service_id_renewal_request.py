import logging
from datetime import datetime, timezone

from openg2p_registry_core.services import G2PRegisterDomainService

from sqlalchemy import select

from ...integrations import Outcome, get_integrations
from ...rules.renewal_notifications import first_phone, sms_text
from .utils.validations import parse_date, validation_error

_logger = logging.getLogger("g2p-register-idrenewal-service")

STATUSES = {"EXPIRY_FLAGGED", "APPOINTMENT_BOOKED", "CLOSED_RENEWED", "CLOSED_NOT_RENEWED"}
SERVICE_TYPES = {"ID_RENEWAL"}
REQUIRED = ("request_ref", "registrant_progres_id", "status")
DATE_FIELDS = ("card_expiry", "flagged_on", "appointment_date", "closed_on")


class G2PRegisterDomainServiceIdRenewalRequest(G2PRegisterDomainService):
    async def validate_domain_attributes(self, records: list[dict]):
        for record in records:
            for key in REQUIRED:
                if key in record and not str(record.get(key) or "").strip():
                    validation_error(f"{key} must not be empty")
            status = record.get("status")
            if status not in (None, "") and str(status) not in STATUSES:
                validation_error(f"status must be one of {sorted(STATUSES)}")
            service_type = record.get("service_type")
            if service_type not in (None, "") and str(service_type) not in SERVICE_TYPES:
                validation_error(f"service_type must be one of {sorted(SERVICE_TYPES)}")
            for key in DATE_FIELDS:
                if record.get(key) not in (None, "") and parse_date(record.get(key)) is None:
                    validation_error(f"{key} is not a valid date")
            if str(status or "") == "APPOINTMENT_BOOKED" and any(
                k in record and not str(record.get(k) or "").strip()
                for k in ("appointment_date", "appointment_location")
            ):
                validation_error("appointment_date and appointment_location are required to book an appointment")

    def construct_search_text(self, payload: dict, extra: list[str] = None) -> str:
        keys = ["request_ref", "registrant_progres_id", "service_type", "status"]
        parts = [str(v).strip() for v in (extra or []) if str(v).strip()]
        parts += [str(payload.get(k) or "").strip() for k in keys if str(payload.get(k) or "").strip()]
        return " ".join(parts).strip()

    def construct_record_name(self, payload: dict, extra: list[str] = None) -> str:
        # ProGres ID first (same convention as assistance events), then the request reference.
        keys = ["registrant_progres_id", "request_ref", "service_type"]
        parts = [str(v).strip() for v in (extra or []) if str(v).strip()]
        parts += [str(payload.get(k) or "").strip() for k in keys if str(payload.get(k) or "").strip()]
        return " ".join(parts).strip() or str(payload.get("functional_record_id") or "").strip()

    async def post_approve(self, change_request, session):
        """Tell the refugee by SMS when a request is flagged, booked or closed, and record on the request what
        happened (SENT / FAILED / NO_PHONE / NOT_CONFIGURED) so staff can follow up where it did not go out."""
        from openg2p_registry_core.models import G2PRegisterChangeRequestPayload

        from ..models import G2PRegisterIndividual as Individual
        from ..models import G2PRegisterIdRenewalRequest as Request

        payload = (
            await session.execute(
                select(G2PRegisterChangeRequestPayload).where(
                    G2PRegisterChangeRequestPayload.change_request_id == change_request.change_request_id
                )
            )
        ).scalar()
        for row in (payload.change_payload if payload else None) or []:
            if row.get("edit_action") not in (None, "ADD", "UPDATE") or not row.get("status"):
                continue
            stored = await self._find_stored(session, Request, row)
            if stored is None:
                _logger.warning("renewal row %s not found after approval; no SMS sent", row.get("request_ref"))
                continue
            text = sms_text(row["status"], stored.request_ref, stored.card_expiry, stored.appointment_date, stored.appointment_time, stored.appointment_location)
            if not text:
                continue
            parent_id = row.get("link_internal_record_id") or stored.link_internal_record_id
            person = (
                await session.execute(select(Individual).where(Individual.internal_record_id == parent_id))
            ).scalar() if parent_id else None
            phone = first_phone(getattr(person, "phone_numbers", None))
            if not phone:
                stored.notification_status = "NO_PHONE"
            else:
                result = await get_integrations().send_sms(phone, text, stored.request_ref or "")
                stored.notification_status = {
                    Outcome.OK: "SENT",
                    Outcome.NOT_CONFIGURED: "NOT_CONFIGURED",
                }.get(result.outcome, "FAILED")
            stored.notified_on = datetime.now(timezone.utc).date()
            await session.flush()

    @staticmethod
    async def _find_stored(session, Request, row):
        if row.get("internal_record_id"):
            query = select(Request).where(Request.internal_record_id == row["internal_record_id"])
        elif row.get("request_ref"):
            query = select(Request).where(Request.request_ref == row["request_ref"])
        else:
            return None
        return (await session.execute(query.limit(1))).scalar()
