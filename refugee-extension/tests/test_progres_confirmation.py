from openg2p_registry_refugee_extension.integrations import Outcome, Response
from openg2p_registry_refugee_extension.rules.progres_confirmation import confirmation_fields, strip_registry_only


def test_yes_keeps_the_reference_and_time_and_nothing_else():
    answer = Response(Outcome.OK, {"authenticated": True, "reference": "PGV4-AUTH-20260305-A1B2C3",
                                   "timestamp": "2026-03-05T11:42:00+03:00", "full_name": "must never be stored"})
    assert confirmation_fields(answer) == {"progres_authenticated": True,
                                           "progres_auth_reference": "PGV4-AUTH-20260305-A1B2C3",
                                           "progres_authenticated_at": "2026-03-05T11:42:00+03:00"}


def test_no_is_recorded_with_its_reference():
    fields = confirmation_fields(Response(Outcome.OK, {"authenticated": False, "reference": "R-9", "timestamp": "T"}))
    assert fields["progres_authenticated"] is False and fields["progres_auth_reference"] == "R-9"


def test_answer_without_reference_or_time_leaves_them_empty():
    assert confirmation_fields(Response(Outcome.OK, {"authenticated": True})) == {
        "progres_authenticated": True, "progres_auth_reference": None, "progres_authenticated_at": None}


def test_unknown_id_is_no_and_clears_an_older_reference():
    assert confirmation_fields(Response(Outcome.NOT_FOUND)) == {
        "progres_authenticated": False, "progres_auth_reference": None, "progres_authenticated_at": None}


def test_progres_not_answering_concludes_nothing():
    assert confirmation_fields(Response(Outcome.UNAVAILABLE, detail="timeout")) == {}
    assert confirmation_fields(Response(Outcome.NOT_CONFIGURED)) == {}


def test_odd_values_are_not_stored_as_text():
    fields = confirmation_fields(Response(Outcome.OK, {"authenticated": True, "reference": {"a": 1}, "timestamp": ["x"]}))
    assert fields["progres_auth_reference"] is None and fields["progres_authenticated_at"] is None
    long = confirmation_fields(Response(Outcome.OK, {"authenticated": True, "reference": "R" * 500, "timestamp": " a\n b "}))
    assert len(long["progres_auth_reference"]) == 128 and long["progres_authenticated_at"] == "a b"


def test_a_typed_reference_or_time_is_dropped():
    row = {"registrant_progres_id": "UGA-1", "progres_auth_reference": "typed", "progres_authenticated_at": "typed"}
    assert strip_registry_only(row) is True
    assert row == {"registrant_progres_id": "UGA-1"}
    assert strip_registry_only(row) is False
