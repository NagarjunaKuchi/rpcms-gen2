import logging

from sqlalchemy import select

from openg2p_registry_core.services import G2PRegisterDomainService

from .utils.validations import as_float, parse_date, validation_error

_logger = logging.getLogger("g2p-register-assistanceevent-service")

CAPTURE_CHANNELS = {"ONLINE", "OFFLINE_HANDOVER"}
REQUIRED = ("registrant_progres_id", "partner_code", "assistance_type", "distribution_cycle")


class G2PRegisterDomainServiceAssistanceEvent(G2PRegisterDomainService):
    async def validate_domain_attributes(self, records: list[dict]):
        for record in records:
            # Only validate when the record carries assistance fields (partial change requests).
            if not any(k in record for k in REQUIRED):
                continue
            for key in REQUIRED:
                if key in record and not str(record.get(key) or "").strip():
                    validation_error(f"{key} must not be empty")
            for key in ("quantity", "amount"):
                if record.get(key) not in (None, ""):
                    value = as_float(record.get(key))
                    if value is None or value < 0:
                        validation_error(f"{key} must be a non-negative number")
            if record.get("delivery_date") not in (None, "") and parse_date(record.get("delivery_date")) is None:
                validation_error("delivery_date is not a valid date")
            channel = record.get("capture_channel")
            if channel not in (None, "") and str(channel).upper() not in CAPTURE_CHANNELS:
                validation_error(f"capture_channel must be one of {sorted(CAPTURE_CHANNELS)}")

    DEDUP_KEYS = ("registrant_progres_id", "assistance_type", "distribution_cycle")

    async def pre_approve(self, change_request, session):
        """Business rule: the same registrant must not receive the same assistance type in the same
        distribution cycle twice. Registry-core's built-in dedup does NOT cover child (TABLE) registers
        (verified on the dev stack: two identical events were both approved), so enforce it here, at approval.
        """
        # Imported lazily: models import this service module.
        from openg2p_registry_core.models import G2PRegisterChangeRequestPayload

        from ..models import G2PRegisterAssistanceEvent as Event

        payload = (
            await session.execute(
                select(G2PRegisterChangeRequestPayload).where(
                    G2PRegisterChangeRequestPayload.change_request_id == change_request.change_request_id
                )
            )
        ).scalar()
        seen = set()
        for row in (payload.change_payload if payload else None) or []:
            if row.get("edit_action") not in (None, "ADD", "UPDATE"):
                continue
            key = tuple(str(row.get(k) or "").strip() for k in self.DEDUP_KEYS)
            if not all(key):
                continue  # partial UPDATE: the stored row decides; required fields are checked in validation
            if key in seen:
                validation_error("Duplicate assistance in this request: same registrant, assistance type and cycle")
            seen.add(key)
            query = select(Event.internal_record_id).where(
                Event.registrant_progres_id == key[0],
                Event.assistance_type == key[1],
                Event.distribution_cycle == key[2],
            )
            if row.get("edit_action") == "UPDATE" and row.get("internal_record_id"):
                query = query.where(Event.internal_record_id != row["internal_record_id"])
            if (await session.execute(query.limit(1))).first():
                validation_error(
                    f"Duplicate assistance: registrant {key[0]} already received {key[1]} in cycle {key[2]}"
                )

    def construct_search_text(self, payload: dict, extra: list[str] = None) -> str:
        keys = ["registrant_progres_id", "partner_code", "partner_name", "assistance_type", "distribution_cycle", "project_ref"]
        parts = [str(v).strip() for v in (extra or []) if str(v).strip()]
        parts += [str(payload.get(k) or "").strip() for k in keys if str(payload.get(k) or "").strip()]
        return " ".join(parts).strip()

    def construct_record_name(self, payload: dict, extra: list[str] = None) -> str:
        keys = ["partner_code", "assistance_type", "distribution_cycle"]
        parts = [str(v).strip() for v in (extra or []) if str(v).strip()]
        parts += [str(payload.get(k) or "").strip() for k in keys if str(payload.get(k) or "").strip()]
        return " ".join(parts).strip() or str(payload.get("functional_record_id") or "").strip()
