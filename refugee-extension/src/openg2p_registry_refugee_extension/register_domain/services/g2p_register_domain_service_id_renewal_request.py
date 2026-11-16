import logging

from openg2p_registry_core.services import G2PRegisterDomainService

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
