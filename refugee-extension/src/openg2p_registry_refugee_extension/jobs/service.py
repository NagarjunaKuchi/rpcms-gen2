"""The daily scheduled checks: partner permit renewal alerts, and refugee ID expiry flags.

Both are safe to run as often as you like: an alert is sent once per permit, and an ID is flagged once per card expiry
(the request reference is built from the ProGres ID and the expiry date, and an existing one is never created again).
One partner or person per transaction: a failure on one never blocks the others.

The ID flag is a normal ID renewal request (status EXPIRY_FLAGGED) created and approved through the registry's own change
request path by the system step, so history and audit are kept and the existing renewal SMS and its SENT / FAILED /
NO_PHONE record are used unchanged."""
import logging
from datetime import date, datetime, timezone

from sqlalchemy import select

from ..config import Settings
from ..integrations import Outcome, get_integrations
from ..rules import scheduled_checks as rules
from ..rules.renewal_notifications import first_phone

_logger = logging.getLogger("rpcms-jobs")

SYSTEM_ACTOR = "rpcms-scheduler"
REGISTER_INDIVIDUAL = "a0000000-0000-4000-8000-000000000001"
TAB = "individual_id_renewal_tab"
SECTION = "in_table_id_renewals"
SECTION_REGISTER = "b0000000-0000-4000-8000-0000000000a1"
SOURCE = "SCHEDULER"

SMS_STATUS = {Outcome.OK: "SENT", Outcome.NOT_CONFIGURED: "NOT_CONFIGURED"}


class JobsService:
    def __init__(self, session_maker):
        self._session_maker = session_maker

    async def run(self, today: date | None = None) -> dict:
        today = today or datetime.now(timezone.utc).date()
        result = {"run_on": today.isoformat(), "permit_alerts": await self.permit_alerts(today),
                  "id_expiry": await self.id_expiry(today)}
        _logger.info("scheduled checks: %s", result)
        return result

    # ---- partner permit renewal alerts ------------------------------------------------------------------------
    async def permit_alerts(self, today: date) -> dict:
        from ..register_domain.models import G2PRegisterPartner as Partner

        counts: dict = {}
        async with self._session_maker() as session:
            ids = list((await session.execute(select(Partner.internal_record_id).where(
                Partner.record_status == "ACTIVE", Partner.permit_renewal_alert_date.is_not(None)))).scalars())
        for record_id in ids:
            try:
                async with self._session_maker() as session:
                    partner = (await session.execute(select(Partner).where(
                        Partner.internal_record_id == record_id))).scalar()
                    if partner is None or not rules.permit_alert_due(
                            today, partner.permit_renewal_alert_date, partner.permit_valid_to, partner.permit_alert_sent_on):
                        continue
                    phone = (partner.contact_phone or "").strip()
                    if not phone:
                        status = "NO_PHONE"
                    else:
                        sent = await get_integrations().send_sms(
                            phone, rules.permit_sms_text(partner.organisation_name, partner.permit_valid_to),
                            f"PERMIT-{partner.partner_code}")
                        status = SMS_STATUS.get(sent.outcome, "FAILED")
                    partner.permit_alert_status = status
                    if status == "SENT":
                        partner.permit_alert_sent_on = today  # anything else is tried again on the next run
                    await session.commit()
                    counts[status] = counts.get(status, 0) + 1
            except Exception:
                _logger.exception("permit alert for partner record %s failed", record_id)
                counts["ERROR"] = counts.get("ERROR", 0) + 1
        return counts

    # ---- refugee ID expiry ------------------------------------------------------------------------------------
    async def id_expiry(self, today: date) -> dict:
        from datetime import timedelta

        from ..register_domain.models import G2PRegisterIndividual as Individual

        days = Settings.get_config().id_expiry_alert_days
        counts: dict = {}
        async with self._session_maker() as session:
            people = (await session.execute(select(Individual.internal_record_id, Individual.progres_id,
                                                   Individual.progres_card_expiry).where(
                Individual.record_status == "ACTIVE", Individual.progres_id.is_not(None),
                Individual.progres_card_expiry >= today,
                Individual.progres_card_expiry <= today + timedelta(days=days)))).all()
        for record_id, progres_id, expiry in people:
            if not rules.id_expiry_due(today, expiry, days) or not (progres_id or "").strip():
                continue
            outcome = await self._flag(record_id, progres_id.strip(), expiry, today)
            counts[outcome] = counts.get(outcome, 0) + 1
        return counts

    async def _flag(self, person_id: str, progres_id: str, expiry: date, today: date) -> str:
        from ..register_domain.models import G2PRegisterIdRenewalRequest as Request

        ref = rules.renewal_ref(progres_id, expiry)
        try:
            async with self._session_maker() as session:
                exists = (await session.execute(select(Request.internal_record_id).where(
                    Request.request_ref == ref).limit(1))).scalar()
                if exists:
                    return "ALREADY_FLAGGED"
                try:
                    await self._create_and_approve(session, person_id, {
                        "request_ref": ref, "registrant_progres_id": progres_id, "service_type": "ID_RENEWAL",
                        "status": "EXPIRY_FLAGGED", "card_expiry": expiry.isoformat(), "flagged_on": today.isoformat()})
                    await session.commit()
                    return "FLAGGED"
                except Exception as err:
                    await session.rollback()
                    if "pending change request already exists" in str(getattr(err, "message", None) or err):
                        return "RETRY_LATER"  # another change to this person's renewals is waiting; the next run picks it up
                    _logger.exception("could not flag ID expiry for record %s", person_id)
                    return "ERROR"
        except Exception:
            _logger.exception("ID expiry check for record %s failed", person_id)
            return "ERROR"

    @staticmethod
    async def _create_and_approve(session, person_id: str, row: dict) -> None:
        from openg2p_registry_core.schemas import ChangePayload, ChangeRequestRequestPayload
        from openg2p_registry_core.services import G2PChangeRequestWorkerService, G2PRegisterChangeRequestService

        payload = ChangeRequestRequestPayload(
            register_id=REGISTER_INDIVIDUAL, tab_id=TAB, section_id=SECTION, section_register_id=SECTION_REGISTER,
            internal_record_id=person_id,
            change_payload=[ChangePayload.model_validate({**row, "edit_action": "ADD", "link_internal_record_id": person_id})])
        cr = await G2PChangeRequestWorkerService.get_component().create_change_request(
            payload, session, created_by=SYSTEM_ACTOR, change_request_source=SOURCE)
        await G2PRegisterChangeRequestService.get_component()._approve_change_request_core(
            change_request_id=cr.change_request_id, session=session, skip_verification=True, approved_by=SYSTEM_ACTOR)


def get_jobs_service() -> JobsService:
    from openg2p_fastapi_common.context import get_async_session_maker

    return JobsService(get_async_session_maker())
