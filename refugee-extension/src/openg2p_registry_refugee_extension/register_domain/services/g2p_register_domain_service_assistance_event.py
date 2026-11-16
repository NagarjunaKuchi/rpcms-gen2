import logging

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from openg2p_registry_core.services import G2PRegisterDomainService

from ...integrations import Outcome, get_integrations
from ...rules.assistance_duplicates import DEDUP_KEYS, first_duplicate_within, key_of
from ...rules.assistance_duplicates import message as duplicate_message
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
        # Duplicates are refused when the entry is made, so the person entering it sees the reason at once and no
        # request is left waiting for an approver to discover it. Needs the database, so it opens its own session.
        from openg2p_fastapi_common.context import get_async_session_maker

        async with get_async_session_maker()() as session:
            await self._check_duplicates(records, session)

    async def _check_duplicates(self, rows: list[dict], session) -> None:
        """Reject a row whose (ProGres ID, assistance type, cycle) is already recorded, or repeated in the request.

        registry-core's built-in dedup does not cover child (TABLE) registers, so the rule lives here. A partial
        UPDATE is completed from the stored row first, so changing only the cycle cannot slip past it."""
        from ..models import G2PRegisterAssistanceEvent as Event

        candidates = []
        for row in rows:
            if row.get("edit_action") not in (None, "ADD", "UPDATE"):
                continue
            merged, own_id = dict(row), None
            if row.get("edit_action") == "UPDATE" and row.get("internal_record_id"):
                own_id = row["internal_record_id"]
                stored = (await session.execute(select(Event).where(Event.internal_record_id == own_id))).scalar()
                if stored is not None:
                    for k in DEDUP_KEYS:
                        if not row.get(k):
                            merged[k] = getattr(stored, k)
            key = key_of(merged)
            if key is not None:
                candidates.append((merged, key, own_id))

        within = first_duplicate_within([m for m, _, _ in candidates])
        if within:
            validation_error("Duplicate assistance in this request: same registrant, assistance type and cycle")
        for _, key, own_id in candidates:
            query = select(Event.internal_record_id).where(
                Event.registrant_progres_id == key[0],
                Event.assistance_type == key[1],
                Event.distribution_cycle == key[2],
            )
            if own_id:
                query = query.where(Event.internal_record_id != own_id)
            if (await session.execute(query.limit(1))).first():
                validation_error(duplicate_message(key))

    async def pre_approve(self, change_request, session):
        # Imported lazily: models import this service module.
        from openg2p_registry_core.models import G2PRegisterChangeRequestPayload

        payload = (
            await session.execute(
                select(G2PRegisterChangeRequestPayload).where(
                    G2PRegisterChangeRequestPayload.change_request_id == change_request.change_request_id
                )
            )
        ).scalar()
        # Re-checked at approval as a safety net: another request may have been approved since this one was made.
        await self._check_duplicates(list((payload.change_payload if payload else None) or []), session)

        # Confirm the ProGres ID with UNHCR ProGres v4 and record Yes/No on the row. No personal data comes back.
        # A "No", or ProGres being unavailable, does not block recording (staff may enter late/offline data):
        # the column stays empty when ProGres could not answer, so "not checked" is never shown as "No".
        rows = list((payload.change_payload if payload else None) or [])
        changed = False
        for row in rows:
            pid = str(row.get("registrant_progres_id") or "").strip()
            if row.get("edit_action") not in (None, "ADD", "UPDATE") or not pid:
                continue
            result = await get_integrations().confirm_progres_id(pid)
            if result.outcome is Outcome.OK:
                row["progres_authenticated"] = bool(result.data.get("authenticated"))
                changed = True
            elif result.outcome is Outcome.NOT_FOUND:
                row["progres_authenticated"] = False
                changed = True
        if changed:
            payload.change_payload = rows
            flag_modified(payload, "change_payload")

    def construct_search_text(self, payload: dict, extra: list[str] = None) -> str:
        keys = ["registrant_progres_id", "partner_code", "partner_name", "assistance_type", "distribution_cycle", "project_ref"]
        parts = [str(v).strip() for v in (extra or []) if str(v).strip()]
        parts += [str(payload.get(k) or "").strip() for k in keys if str(payload.get(k) or "").strip()]
        return " ".join(parts).strip()

    def construct_record_name(self, payload: dict, extra: list[str] = None) -> str:
        # ProGres ID first: the record name is what search results show, and the pre-handover duplicate check reads it.
        keys = ["registrant_progres_id", "partner_code", "assistance_type", "distribution_cycle"]
        parts = [str(v).strip() for v in (extra or []) if str(v).strip()]
        parts += [str(payload.get(k) or "").strip() for k in keys if str(payload.get(k) or "").strip()]
        return " ".join(parts).strip() or str(payload.get("functional_record_id") or "").strip()
