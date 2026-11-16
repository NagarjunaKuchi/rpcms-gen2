"""Sync of handovers recorded on a phone (possibly offline) into the register.

Each record is checked, then created and approved through the platform's own change-request path (the same one its
ingestion worker uses), so the existing rules run unchanged: duplicate refusal (and its count on the dashboard), the
ProGres confirmation, history and audit. Approval is by the system step, not by the two human approvers: field records
arrive in hundreds and have already been authenticated at the point of delivery. The signed-in user is kept as the
creator and approver of every record.

One record per transaction: a bad record never blocks the others, and a failure leaves no half-created request."""
import logging

from sqlalchemy import func, select

from ..rules import handover_sync as rules

_logger = logging.getLogger("rpcms-handover-sync")

REGISTER_INDIVIDUAL = "a0000000-0000-4000-8000-000000000001"
TAB = "individual_assistance_tab"
SECTION = "in_table_assistance_events"
SECTION_REGISTER = "b0000000-0000-4000-8000-0000000000a0"
SOURCE = "AGENT_PORTAL"

# per-record outcomes
SYNCED, ALREADY, DUPLICATE, REJECTED, RETRY, FAILED = "SYNCED", "ALREADY_SYNCED", "DUPLICATE", "REJECTED", "RETRY_LATER", "FAILED"


class HandoverError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


class HandoverSyncService:
    def __init__(self, session_maker):
        self._session_maker = session_maker

    async def sync(self, actor: str, batch_id: str, records: list) -> dict:
        problem = rules.batch_error(batch_id, records)
        if problem:
            raise HandoverError(problem)
        results, seen = [], set()
        for raw in records:
            ref = str(raw.get("client_record_id") or "").strip() if isinstance(raw, dict) else ""
            if ref and ref in seen:
                results.append({"client_record_id": ref, "status": REJECTED, "reason": "client_record_id repeated in this request"})
                continue
            seen.add(ref)
            results.append(await self._one(actor, batch_id, raw, ref))
        counts: dict = {}
        for r in results:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        _logger.info("handover sync by %s, batch %s: %s", actor, batch_id, counts)
        return {"batch_id": batch_id, "received": len(results), "counts": counts, "results": results}

    async def _one(self, actor: str, batch_id: str, raw, ref: str) -> dict:
        row, problem = rules.to_row(raw, batch_id)
        if problem:
            return {"client_record_id": ref or None, "status": REJECTED, "reason": problem}
        out = {"client_record_id": ref}
        try:
            async with self._session_maker() as session:
                existing = await self._existing(session, ref)
                if existing:
                    return {**out, "status": ALREADY, "record_id": existing}
                if not await self._partner_active(session, row["partner_code"]):
                    return {**out, "status": REJECTED, "reason": f"partner {row['partner_code']} is not an active partner in RPCMS"}
                individuals = await self._individuals(session, row["registrant_progres_id"])
                if len(individuals) != 1:
                    why = "is not registered in RPCMS" if not individuals else "matches more than one registrant in RPCMS"
                    return {**out, "status": REJECTED, "reason": f"ProGres ID {row['registrant_progres_id']} {why}"}
                parent = individuals[0]
                try:
                    record_id = await self._create_and_approve(session, actor, parent, row)
                    await session.commit()
                    return {**out, "status": SYNCED, "record_id": record_id}
                except Exception as err:
                    await session.rollback()
                    return {**out, **self._classify(err)}
        except Exception as err:  # database unavailable and the like: this record can simply be sent again
            _logger.exception("handover %s could not be processed", ref)
            return {**out, "status": FAILED, "reason": f"could not be processed ({type(err).__name__}); send it again"}

    async def _create_and_approve(self, session, actor: str, parent: str, row: dict) -> str:
        from openg2p_registry_core.schemas import ChangePayload, ChangeRequestRequestPayload
        from openg2p_registry_core.services import G2PChangeRequestWorkerService, G2PRegisterChangeRequestService

        payload = ChangeRequestRequestPayload(
            register_id=REGISTER_INDIVIDUAL, tab_id=TAB, section_id=SECTION, section_register_id=SECTION_REGISTER,
            internal_record_id=parent,
            change_payload=[ChangePayload.model_validate({**row, "edit_action": "ADD", "link_internal_record_id": parent})])
        cr = await G2PChangeRequestWorkerService.get_component().create_change_request(
            payload, session, created_by=actor, change_request_source=SOURCE)
        await G2PRegisterChangeRequestService.get_component()._approve_change_request_core(
            change_request_id=cr.change_request_id, session=session, skip_verification=True, approved_by=actor)
        return await self._event_id(session, row["client_record_id"])

    @staticmethod
    def _classify(err: Exception) -> dict:
        message = str(getattr(err, "message", None) or err)
        if "pending change request already exists" in message:
            return {"status": RETRY, "reason": "another change to this person's assistance is waiting for approval; send again later"}
        if message.startswith("Duplicate assistance"):
            return {"status": DUPLICATE, "reason": message}
        if getattr(err, "code", None) is not None:  # a rule of the registry refused it
            return {"status": REJECTED, "reason": message}
        _logger.exception("handover approval failed")
        return {"status": FAILED, "reason": f"could not be recorded ({type(err).__name__}); send it again"}

    # ---- lookups ------------------------------------------------------------------------------------------
    @staticmethod
    async def _existing(session, ref: str) -> str | None:
        from ..register_domain.models import G2PRegisterAssistanceEvent as Event

        return (await session.execute(select(Event.internal_record_id).where(Event.client_record_id == ref).limit(1))).scalar()

    @staticmethod
    async def _event_id(session, ref: str) -> str | None:
        return await HandoverSyncService._existing(session, ref)

    @staticmethod
    async def _partner_active(session, code: str) -> bool:
        from ..register_domain.models import G2PRegisterPartner as Partner

        n = (await session.execute(select(func.count()).select_from(Partner).where(
            Partner.partner_code == code, Partner.record_status == "ACTIVE"))).scalar()
        return bool(n)

    @staticmethod
    async def _individuals(session, progres_id: str) -> list[str]:
        from ..register_domain.models import G2PRegisterIndividual as Individual

        return list((await session.execute(select(Individual.internal_record_id).where(
            Individual.progres_id == progres_id, Individual.record_status == "ACTIVE").limit(2))).scalars())


def get_handover_service() -> HandoverSyncService:
    from openg2p_fastapi_common.context import get_async_session_maker

    return HandoverSyncService(get_async_session_maker())
