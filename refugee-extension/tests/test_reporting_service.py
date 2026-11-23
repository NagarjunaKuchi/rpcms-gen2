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
        if "FROM rpcms_report_approval" in sql:
            return FakeResult([self.db["approval"]] if self.db.get("approval") else [])
        if "INSERT INTO rpcms_report_approval" in sql:
            self.db.setdefault("approvals_inserted", []).append(params)
            return FakeResult()
        if "UPDATE rpcms_report_approval" in sql:
            self.db["approval_used"] = params["id"]
            return FakeResult()
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


def service(db, stub, approved_by="nina", must_differ=True):
    """A service whose quarter has already been approved (by `approved_by`) at the figures it currently shows,
    unless the test puts an approval in `db` itself or sets db["no_approval"]."""
    integrations.reset_integrations(stub)
    svc = ReportingService(lambda: FakeSession(db), approver_must_differ=must_differ)
    if "approval" not in db and not db.get("no_approval"):
        digest = run(svc.preview("AMP", "2026-Q3"))["payload_sha256"]
        db["approval"] = {"approval_id": "ap-1", "payload_sha256": digest, "approved_by": approved_by,
                          "approved_at": datetime(2026, 10, 1)}
    return svc


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


def test_unapproved_figures_are_not_sent():
    db = {"spend": SPEND, "inserted": [], "no_approval": True}
    stub = Stub(Response(Outcome.OK, {"accepted": True, "reference": "R"}))
    with pytest.raises(ReportingError, match="not been approved") as e:
        run(service(db, stub).submit("AMP", "2026-Q3", "alex"))
    assert e.value.status == 409 and stub.calls == [] and db["inserted"] == []


def test_figures_that_changed_after_approval_are_not_sent():
    db = {"spend": SPEND, "inserted": []}
    svc = service(db, Stub(Response(Outcome.OK, {"accepted": True})))
    db["spend"] = [dict(SPEND[0], amount=999)]
    with pytest.raises(ReportingError, match="changed after"):
        run(svc.submit("AMP", "2026-Q3", "alex"))


def test_the_approver_cannot_send_when_a_different_person_is_required():
    db = {"spend": SPEND, "inserted": []}
    with pytest.raises(ReportingError, match="cannot also send"):
        run(service(db, Stub(Response(Outcome.OK)), approved_by="alex").submit("AMP", "2026-Q3", "alex"))
    out = run(service({"spend": SPEND, "inserted": []}, Stub(Response(Outcome.OK, {"accepted": True})),
                      approved_by="alex", must_differ=False).submit("AMP", "2026-Q3", "alex"))
    assert out["status"] == "SENT"


def test_a_successful_send_uses_the_approval_up_and_a_failed_one_does_not():
    db = {"spend": SPEND, "inserted": []}
    run(service(db, Stub(Response(Outcome.UNAVAILABLE, detail="timeout"))).submit("AMP", "2026-Q3", "alex"))
    assert "approval_used" not in db
    run(service(db, Stub(Response(Outcome.OK, {"accepted": True, "reference": "R"}))).submit("AMP", "2026-Q3", "alex"))
    assert db["approval_used"] == "ap-1"


def test_approve_records_the_figures_and_the_approver():
    db = {"spend": SPEND, "inserted": [], "no_approval": True}
    out = run(service(db, Stub(Response(Outcome.OK))).approve("amp", "2026-Q3", "nina", " looks right "))
    row = db["approvals_inserted"][0]
    assert out["records"] == 1 and row["by"] == "nina" and row["note"] == "looks right"
    assert row["sha"] == out["payload_sha256"] and row["system"] == "AMP"


def test_nothing_to_approve_is_refused():
    db = {"spend": [], "inserted": [], "no_approval": True}
    with pytest.raises(ReportingError, match="Nothing to approve"):
        run(service(db, Stub(Response(Outcome.OK))).approve("AMP", "2026-Q3", "nina"))
