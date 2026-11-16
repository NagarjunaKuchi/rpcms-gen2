import logging

from openg2p_registry_core.services import G2PRegisterDomainService

from sqlalchemy import select

from .utils.mocks_client import call_mock
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
        """Inform the refugee by SMS (MOCK gateway in dev) when a request is flagged, booked or closed."""
        from openg2p_registry_core.models import G2PRegisterChangeRequestPayload

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
            stored = None
            if row.get("internal_record_id"):
                stored = (
                    await session.execute(
                        select(Request).where(Request.internal_record_id == row["internal_record_id"])
                    )
                ).scalar()
            merged = {c: getattr(stored, c, None) for c in ("request_ref", "registrant_progres_id", "card_expiry", "appointment_date", "appointment_time", "appointment_location")} if stored else {}
            merged.update({k: v for k, v in row.items() if v not in (None, "")})
            to, ref, status = merged.get("registrant_progres_id"), merged.get("request_ref"), row["status"]
            if not to:
                continue
            text = {
                "EXPIRY_FLAGGED": f"OPM Refugees: Your refugee ID expires on {merged.get('card_expiry')}. Please book a renewal appointment at the Bidibidi service centre.",
                "APPOINTMENT_BOOKED": f"Renewal appointment booked: {merged.get('appointment_date')}, {merged.get('appointment_time') or ''} {merged.get('appointment_location') or ''}. Bring your current ID. Ref {ref}.".replace("  ", " "),
                "CLOSED_RENEWED": "Your refugee ID renewal is complete. Thank you for visiting OPM Bidibidi.",
                "CLOSED_NOT_RENEWED": "Your refugee ID renewal request was closed without renewal. Please contact OPM Bidibidi.",
            }.get(status)
            if text:
                await call_mock("POST", "/sms/v1/messages", {"to": to, "text": text, "ref": ref})
