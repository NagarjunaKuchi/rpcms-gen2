"""Quarterly figures and their submission to AMP and NIMES.

Reads straight from the register tables (read-only SQL, same source as the dashboard views) and writes only the
submission log. Nothing is sent without a person calling submit; every attempt is logged, including failures."""
import logging
from datetime import datetime

from sqlalchemy import text

from ..integrations import Outcome, get_integrations
from ..rules import reporting as rules

_logger = logging.getLogger("rpcms-reporting")


class ReportingError(Exception):
    """A request the caller can fix (bad quarter, already sent...). Carries an HTTP-style status."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


class ReportingService:
    def __init__(self, session_maker):
        self._session_maker = session_maker

    # ---- figures ------------------------------------------------------------------------------------------
    async def summary(self, quarter: str) -> dict:
        start, end = rules.parse_quarter(quarter)
        async with self._session_maker() as s:
            one = lambda sql, **p: s.execute(text(sql), p)  # noqa: E731
            partners = (await one("SELECT count(*) FILTER (WHERE compliance_status = 'COMPLIANT') AS ok, count(*) AS n "
                                  "FROM g2p_register_partners WHERE record_status = 'ACTIVE'")).one()
            events = (await one(
                "SELECT count(*) FILTER (WHERE progres_authenticated IS TRUE) AS authenticated, "
                "count(DISTINCT registrant_progres_id) AS persons, count(*) AS n "
                "FROM g2p_register_assistance_event WHERE record_status = 'ACTIVE' "
                "AND delivery_date >= :a AND delivery_date < :b", a=start, b=end)).one()
            undated = (await one("SELECT count(*) FROM g2p_register_assistance_event "
                                 "WHERE record_status = 'ACTIVE' AND delivery_date IS NULL")).scalar()
            dups = (await one("SELECT count(*) FROM rpcms_duplicate_attempt "
                              "WHERE detected_at >= :a AND detected_at < :b", a=start, b=end)).scalar()
        return {
            "quarter": quarter,
            "partners_active": partners.n,
            # Partner compliance is the position now, not at the end of that quarter: partners are not versioned by date.
            "partners_compliant": partners.ok,
            "events_in_quarter": events.n,
            "events_authenticated": events.authenticated,
            "persons_reached": events.persons,
            "duplicates_flagged": dups,
            "events_without_delivery_date": undated,
        }

    async def expenditure(self, quarter: str) -> tuple[dict, list[dict]]:
        start, end = rules.parse_quarter(quarter)
        async with self._session_maker() as s:
            rows = (await s.execute(text(
                "SELECT e.project_ref AS project_code, pr.amp_record_no, e.currency, "
                "sum(e.amount) AS amount, count(*) AS events "
                "FROM g2p_register_assistance_event e "
                "LEFT JOIN g2p_register_projects pr ON pr.project_code = e.project_ref AND pr.record_status = 'ACTIVE' "
                "WHERE e.record_status = 'ACTIVE' AND e.amount IS NOT NULL "
                "AND e.delivery_date >= :a AND e.delivery_date < :b "
                "GROUP BY e.project_ref, pr.amp_record_no, e.currency ORDER BY e.project_ref"), {"a": start, "b": end})).mappings().all()
        return rules.build_expenditure(quarter, [dict(r) for r in rows])

    async def preview(self, system: str, quarter: str) -> dict:
        system = self._system(system)
        if system == "AMP":
            payload, unmatched = await self.expenditure(quarter)
            return {"system": system, "payload": payload, "not_sent": unmatched}
        summary = await self.summary(quarter)
        return {"system": system, "payload": rules.build_indicators(quarter, summary), "basis": summary}

    # ---- submission ---------------------------------------------------------------------------------------
    async def submit(self, system: str, quarter: str, actor: str, force: bool = False) -> dict:
        system = self._system(system)
        built = await self.preview(system, quarter)
        payload = built["payload"]
        records = len(payload.get("items", payload.get("indicators", [])))
        if records == 0:
            raise ReportingError(f"Nothing to send to {system} for {quarter}", 409)
        digest = rules.payload_digest(payload)
        async with self._session_maker() as s:
            sent = (await s.execute(text(
                "SELECT submitted_at, external_reference FROM rpcms_report_submission "
                "WHERE system = :sys AND quarter = :q AND status = 'SENT' ORDER BY submitted_at DESC LIMIT 1"),
                {"sys": system, "q": quarter})).first()
        if sent and not force:
            raise ReportingError(
                f"{system} already accepted {quarter} on {sent.submitted_at:%Y-%m-%d} (reference "
                f"{sent.external_reference}). Resubmitting may double count there; send with force=true only if "
                f"{system} has confirmed it needs a resubmission.", 409)

        client = get_integrations()
        result = await (client.submit_expenditure(payload) if system == "AMP" else client.submit_indicators(payload))
        if result.outcome is Outcome.OK and result.data.get("accepted", True):
            status, reference, detail = "SENT", str(result.data.get("reference") or ""), None
        elif result.outcome is Outcome.NOT_CONFIGURED:
            status, reference, detail = "NOT_CONFIGURED", None, f"{system} is not configured"
        else:
            status, reference, detail = "FAILED", None, str(result.detail or result.outcome.value)[:500]
        async with self._session_maker() as s:
            await s.execute(text(
                "INSERT INTO rpcms_report_submission (submission_id, system, quarter, submitted_at, submitted_by, status, "
                "external_reference, records_sent, payload_sha256, detail) VALUES "
                "(gen_random_uuid()::text, :system, :quarter, :at, :by, :status, :ref, :n, :sha, :detail)"),
                {"system": system, "quarter": quarter, "at": datetime.utcnow(), "by": actor, "status": status,
                 "ref": reference, "n": records if status == "SENT" else 0, "sha": digest, "detail": detail})
            await s.commit()
        _logger.info("Report %s %s submitted by %s: %s", system, quarter, actor, status)
        return {"system": system, "quarter": quarter, "status": status, "reference": reference, "records": records,
                "detail": detail, "not_sent": built.get("not_sent", [])}

    async def history(self, limit: int = 100) -> list[dict]:
        async with self._session_maker() as s:
            rows = (await s.execute(text(
                "SELECT submission_id, system, quarter, submitted_at, submitted_by, status, external_reference, "
                "records_sent, detail FROM rpcms_report_submission ORDER BY submitted_at DESC LIMIT :n"),
                {"n": min(max(limit, 1), 500)})).mappings().all()
        return [{**dict(r), "submitted_at": r["submitted_at"].isoformat()} for r in rows]

    @staticmethod
    def _system(system: str) -> str:
        system = str(system or "").strip().upper()
        if system not in rules.SYSTEMS:
            raise ReportingError(f"system must be one of {list(rules.SYSTEMS)}")
        return system


_instance = None


def get_reporting_service() -> ReportingService:
    global _instance
    if _instance is None:
        from openg2p_fastapi_common.context import get_async_session_maker

        _instance = ReportingService(get_async_session_maker())
    return _instance
