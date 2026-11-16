"""ReportingService logic that does not need the platform: submission outcomes and the resubmission guard.

The database is replaced by a tiny fake session, the integration client by a stub."""
import asyncio
from datetime import datetime

import pytest

from openg2p_registry_refugee_extension import integrations
from openg2p_registry_refugee_extension.integrations import Outcome, Response
from openg2p_registry_refugee_extension.reporting.service import ReportingError, ReportingService


class FakeResult:
    def __init__(self, rows=None, scalar=None):
        self._rows, self._scalar = rows or [], scalar

    def first(self):
        return self._rows[0] if self._rows else None

    def one(self):
        return self._rows[0]

    def scalar(self):
        return self._scalar

    def mappings(self):
        return self

    def all(self):
        return self._rows


class Row(dict):
    __getattr__ = dict.get


class FakeSession:
    def __init__(self, db):
        self.db = db

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def commit(self):
        pass

    async def execute(self, statement, params=None):
        sql = str(statement)
        if "INSERT INTO rpcms_report_submission" in sql:
            self.db["inserted"].append(params)
            return FakeResult()
        if "FROM rpcms_report_submission" in sql and "status = 'SENT'" in sql:
            return FakeResult([self.db["sent"]] if self.db.get("sent") else [])
        if "FROM g2p_register_assistance_event e" in sql:
            return FakeResult(self.db["spend"])
        raise AssertionError("unexpected SQL: " + sql[:80])


class Stub:
    def __init__(self, response):
        self.response, self.calls = response, []

    async def submit_expenditure(self, payload):
        self.calls.append(("AMP", payload))
        return self.response

    async def submit_indicators(self, payload):
        self.calls.append(("NIMES", payload))
        return self.response


def service(db, stub):
    integrations.reset_integrations(stub)
    return ReportingService(lambda: FakeSession(db))


def run(coro):
    return asyncio.run(coro)


SPEND = [{"project_code": "P1", "amp_record_no": "AMP-1", "currency": "UGX", "amount": 100, "events": 2}]


@pytest.fixture(autouse=True)
def _reset():
    yield
    integrations.reset_integrations()


def test_sent_is_logged_with_reference():
    db = {"spend": SPEND, "inserted": []}
    stub = Stub(Response(Outcome.OK, {"accepted": True, "reference": "AMP-EXP-1"}))
    out = run(service(db, stub).submit("amp", "2026-Q3", "alex"))
    assert out["status"] == "SENT" and out["reference"] == "AMP-EXP-1" and out["records"] == 1
    assert db["inserted"][0]["status"] == "SENT" and db["inserted"][0]["by"] == "alex" and db["inserted"][0]["n"] == 1
    assert stub.calls[0][1]["items"][0]["amp_record"] == "AMP-1"


def test_already_accepted_quarter_is_refused_unless_forced():
    db = {"spend": SPEND, "inserted": [], "sent": Row(submitted_at=datetime(2026, 10, 5), external_reference="AMP-EXP-9")}
    stub = Stub(Response(Outcome.OK, {"accepted": True, "reference": "AMP-EXP-10"}))
    with pytest.raises(ReportingError) as e:
        run(service(db, stub).submit("AMP", "2026-Q3", "alex"))
    assert e.value.status == 409 and "AMP-EXP-9" in str(e.value) and not stub.calls
    assert run(service(db, stub).submit("AMP", "2026-Q3", "alex", force=True))["status"] == "SENT"


def test_unavailable_system_is_logged_as_failed_and_nothing_is_claimed_sent():
    db = {"spend": SPEND, "inserted": []}
    out = run(service(db, Stub(Response(Outcome.UNAVAILABLE, detail="timeout"))).submit("AMP", "2026-Q3", "alex"))
    assert out["status"] == "FAILED" and "timeout" in out["detail"]
    assert db["inserted"][0]["status"] == "FAILED" and db["inserted"][0]["n"] == 0


def test_not_configured_is_its_own_status():
    db = {"spend": SPEND, "inserted": []}
    out = run(service(db, Stub(Response(Outcome.NOT_CONFIGURED))).submit("AMP", "2026-Q3", "alex"))
    assert out["status"] == "NOT_CONFIGURED"


def test_rejected_by_the_system_is_not_recorded_as_sent():
    db = {"spend": SPEND, "inserted": []}
    out = run(service(db, Stub(Response(Outcome.OK, {"accepted": False}))).submit("AMP", "2026-Q3", "alex"))
    assert out["status"] == "FAILED"


def test_nothing_to_send_is_refused_and_not_logged():
    db = {"spend": [], "inserted": []}
    with pytest.raises(ReportingError) as e:
        run(service(db, Stub(Response(Outcome.OK))).submit("AMP", "2026-Q3", "alex"))
    assert e.value.status == 409 and not db["inserted"]


def test_bad_system_and_quarter():
    svc = service({"spend": [], "inserted": []}, Stub(Response(Outcome.OK)))
    with pytest.raises(ReportingError):
        run(svc.submit("SAP", "2026-Q3", "a"))
    with pytest.raises(ValueError):
        run(svc.submit("AMP", "nope", "a"))
