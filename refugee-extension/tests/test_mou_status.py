from datetime import date

from openg2p_registry_refugee_extension.integrations import Outcome, Response
from openg2p_registry_refugee_extension.rules.mou_verification import evaluate_mou, mou_status

TODAY = date(2026, 11, 18)


def doc(**kw):
    return Response(Outcome.OK, {"valid": True, "problems": [], "current_sha256": "abc", "signatures": 3, "eseals": 2, **kw})


def test_fully_signed_and_unaltered_is_signed():
    assert evaluate_mou(doc(), 3, 2, TODAY)["mou_status"] == "SIGNED"


def test_some_signatures_means_awaiting():
    assert evaluate_mou(doc(signatures=1, eseals=0), 3, 2, TODAY)["mou_status"] == "AWAITING_SIGNATURES"
    assert evaluate_mou(doc(signatures=3, eseals=1), 3, 2, TODAY)["mou_status"] == "AWAITING_SIGNATURES"


def test_nothing_signed_yet_is_draft():
    assert evaluate_mou(doc(signatures=0, eseals=0), 3, 2, TODAY)["mou_status"] == "DRAFT"


def test_altered_document_is_not_signed():
    r = evaluate_mou(doc(valid=False, problems=["document content changed after signing"]), 3, 2, TODAY, "SIGNED")
    assert r["mou_status"] == "AWAITING_SIGNATURES"


def test_an_unconcluded_check_keeps_the_previous_status():
    for outcome in (Outcome.NOT_FOUND, Outcome.UNAVAILABLE, Outcome.NOT_CONFIGURED):
        assert evaluate_mou(Response(outcome), 3, 2, TODAY, "SIGNED")["mou_status"] == "SIGNED"
        assert evaluate_mou(Response(outcome), 3, 2, TODAY, "AWAITING_SIGNATURES")["mou_status"] == "AWAITING_SIGNATURES"


def test_a_new_mou_that_cannot_be_checked_starts_as_draft():
    assert evaluate_mou(Response(Outcome.UNAVAILABLE), 3, 2, TODAY)["mou_status"] == "DRAFT"


def test_status_function_directly():
    assert mou_status("VALID", 3, 2) == "SIGNED"
    assert mou_status("INCOMPLETE", 0, 0, "AWAITING_SIGNATURES") == "DRAFT"
