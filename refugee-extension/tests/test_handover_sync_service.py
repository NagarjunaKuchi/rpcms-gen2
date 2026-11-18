import asyncio

import pytest

from openg2p_registry_refugee_extension.handover.service import HandoverError, HandoverSyncService


class Refused(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.code, self.message = "REQ-VAL-001", message


def classify(err):
    return HandoverSyncService._classify(err)


def test_outcomes_are_told_apart():
    assert classify(Refused("Duplicate assistance: registrant X already received FOOD"))["status"] == "DUPLICATE"
    assert classify(Refused("A pending change request already exists for this record and section"))["status"] == "RETRY_LATER"
    assert classify(Refused("gps_latitude must be real"))["status"] == "REJECTED"
    no = classify(Refused("ProGres did not confirm ID UGA-1: the assistance cannot be recorded"))
    assert no["status"] == "NOT_AUTHENTICATED" and "UGA-1" in no["reason"]
    assert classify(RuntimeError("boom"))["status"] == "FAILED"
    assert "boom" not in classify(RuntimeError("boom"))["reason"]  # internals are not leaked to the phone


def test_batch_is_validated_and_repeats_inside_a_request_are_not_applied_twice():
    svc = HandoverSyncService(lambda: None)
    with pytest.raises(HandoverError):
        asyncio.run(svc.sync("alex", "", [{}]))
    calls = []

    async def fake_one(actor, batch, raw, ref):
        calls.append(ref)
        return {"client_record_id": ref, "status": "SYNCED"}

    svc._one = fake_one
    out = asyncio.run(svc.sync("alex", "B1", [{"client_record_id": "a"}, {"client_record_id": "b"}, {"client_record_id": "a"}]))
    assert calls == ["a", "b"] and out["counts"] == {"SYNCED": 2, "REJECTED": 1}
    assert out["results"][2]["status"] == "REJECTED" and "repeated" in out["results"][2]["reason"]
