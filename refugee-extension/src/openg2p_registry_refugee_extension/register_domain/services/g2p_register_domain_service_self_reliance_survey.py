import logging
from datetime import datetime, timezone

from sqlalchemy import select

from openg2p_registry_core.services import G2PRegisterDomainService

from ...rules import self_reliance as rules
from .utils.validations import parse_date, validation_error

_logger = logging.getLogger("g2p-register-selfreliancesurvey-service")

REQUIRED = ("round_label", "survey_date")
SEARCH_KEYS = ["round_label", "zone", "food_source"]
NAME_KEYS = ["round_label", "zone"]


class G2PRegisterDomainServiceSelfRelianceSurvey(G2PRegisterDomainService):
    async def validate_domain_attributes(self, records: list[dict]):
        today = datetime.now(timezone.utc).date()
        for record in records:
            if record.get("edit_action") not in (None, "ADD", "UPDATE"):
                continue
            checked = dict(record)
            if "survey_date" in checked:
                if checked["survey_date"] not in (None, "") and parse_date(checked["survey_date"]) is None:
                    validation_error("survey_date is not a valid date")
                checked["survey_date"] = parse_date(checked["survey_date"])
            for key in REQUIRED:
                if key in record and not str(record.get(key) or "").strip():
                    validation_error(f"{key} must not be empty")
            problem = rules.answer_error(checked, today)
            if problem:
                validation_error(problem)
        from openg2p_fastapi_common.context import get_async_session_maker

        async with get_async_session_maker()() as session:
            await self._check_one_per_round(records, session)

    async def _check_one_per_round(self, rows: list[dict], session) -> None:
        """A household has one survey per round. The registry's own duplicate check does not cover child registers,
        so the rule lives here; a partial UPDATE is completed from the stored row first."""
        from ..models import G2PRegisterSelfRelianceSurvey as Survey

        seen = set()
        for row in rows:
            if row.get("edit_action") not in (None, "ADD", "UPDATE"):
                continue
            household, label, own_id = row.get("link_internal_record_id"), row.get("round_label"), None
            if row.get("edit_action") == "UPDATE" and row.get("internal_record_id"):
                own_id = row["internal_record_id"]
                stored = (await session.execute(select(Survey).where(Survey.internal_record_id == own_id))).scalar()
                if stored is not None:
                    household = household or stored.link_internal_record_id
                    label = label or stored.round_label
            if not (household and label):
                continue
            key = (str(household), str(label).strip())
            if key in seen:
                validation_error(f"Round {key[1]} appears twice in this request for the same household")
            seen.add(key)
            query = select(Survey.internal_record_id).where(
                Survey.link_internal_record_id == household, Survey.round_label == key[1])
            if own_id:
                query = query.where(Survey.internal_record_id != own_id)
            if (await session.execute(query.limit(1))).first():
                validation_error(f"This household already has a survey for round {key[1]}")

    async def pre_approve(self, change_request, session):
        from openg2p_registry_core.models import G2PRegisterChangeRequestPayload

        payload = (
            await session.execute(
                select(G2PRegisterChangeRequestPayload).where(
                    G2PRegisterChangeRequestPayload.change_request_id == change_request.change_request_id
                )
            )
        ).scalar()
        # Re-checked at approval: another request may have been approved since this one was made.
        await self._check_one_per_round(list((payload.change_payload if payload else None) or []), session)

    async def post_approve(self, change_request, session):
        """After an approved add or edit: score the survey from its four answers and store the index with the version
        of the formula. An unfinished survey gets no index (never 0)."""
        from openg2p_registry_core.models import G2PRegisterChangeRequestPayload

        from ..models import G2PRegisterSelfRelianceSurvey as Survey

        payload = (
            await session.execute(
                select(G2PRegisterChangeRequestPayload).where(
                    G2PRegisterChangeRequestPayload.change_request_id == change_request.change_request_id
                )
            )
        ).scalar()
        for row in (payload.change_payload if payload else None) or []:
            if row.get("edit_action") not in (None, "ADD", "UPDATE"):
                continue
            if row.get("internal_record_id"):
                query = select(Survey).where(Survey.internal_record_id == row["internal_record_id"])
            else:
                parent = row.get("link_internal_record_id")
                if not (parent and row.get("round_label")):
                    continue
                query = select(Survey).where(Survey.link_internal_record_id == parent, Survey.round_label == row["round_label"])
            stored = (await session.execute(query.limit(1))).scalar()
            if stored is None:
                _logger.warning("survey %s not found after approval; not scored", row.get("round_label"))
                continue
            stored.self_reliance_index = rules.compute_index(
                {k: getattr(stored, k) for k in rules.SCALES})
            stored.index_version = rules.INDEX_VERSION
            stored.index_computed_on = datetime.now(timezone.utc).date()
            await session.flush()

    def construct_search_text(self, payload: dict, extra: list[str] = None) -> str:
        parts = [str(v).strip() for v in (extra or []) if str(v).strip()]
        parts += [str(payload.get(k) or "").strip() for k in SEARCH_KEYS if str(payload.get(k) or "").strip()]
        return " ".join(parts).strip()

    def construct_record_name(self, payload: dict, extra: list[str] = None) -> str:
        parts = [str(v).strip() for v in (extra or []) if str(v).strip()]
        parts += [str(payload.get(k) or "").strip() for k in NAME_KEYS if str(payload.get(k) or "").strip()]
        return " ".join(parts).strip() or str(payload.get("functional_record_id") or "").strip()
