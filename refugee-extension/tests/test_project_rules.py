from datetime import date

from openg2p_registry_refugee_extension.integrations import Outcome, Response
from openg2p_registry_refugee_extension.rules.mou_verification import evaluate_mou
from openg2p_registry_refugee_extension.rules.project_funding import evaluate_funding
from openg2p_registry_refugee_extension.rules.service_point_overlap import distance_m, evaluate_overlap, valid_coordinates

TODAY = date(2026, 11, 16)
AMP_OK = Response(Outcome.OK, {"donor": "West Nile Resilience Fund", "currency": "UGX", "commitment": 1200000000, "disbursed_to_partner": 300000000})


# ---- funding
def test_funding_confirmed_when_value_matches():
    r = evaluate_funding("1,200,000,000", "UGX", AMP_OK, TODAY)
    assert r["amp_status"] == "CONFIRMED" and r["amp_notes"] is None and r["amp_donor"] == "West Nile Resilience Fund"
    assert r["amp_disbursed"] == 300000000


def test_funding_mismatch_on_value_and_on_currency():
    assert evaluate_funding(1_000_000, "UGX", AMP_OK, TODAY)["amp_status"] == "MISMATCH"
    r = evaluate_funding(1_200_000_000, "USD", AMP_OK, TODAY)
    assert r["amp_status"] == "MISMATCH" and "Currency" in r["amp_notes"]


def test_funding_not_found_and_not_checked():
    assert evaluate_funding(1, "UGX", Response(Outcome.NOT_FOUND), TODAY)["amp_status"] == "NOT_FOUND"
    for o in (Outcome.UNAVAILABLE, Outcome.NOT_CONFIGURED):
        assert evaluate_funding(1, "UGX", Response(o), TODAY)["amp_status"] == "NOT_CHECKED"


def test_funding_unusable_value_is_a_mismatch_not_a_crash():
    assert evaluate_funding("lots", "UGX", AMP_OK, TODAY)["amp_status"] == "MISMATCH"
    assert evaluate_funding(1, "UGX", Response(Outcome.OK, {"donor": "x"}), TODAY)["amp_status"] == "MISMATCH"


# ---- MoU
def doc(**kw):
    return Response(Outcome.OK, {"valid": True, "problems": [], "current_sha256": "abc", "signatures": 3, "eseals": 2, **kw})


def test_mou_valid_when_everything_present():
    r = evaluate_mou(doc(), 3, 2, TODAY)
    assert r["verification_status"] == "VALID" and r["signatures_count"] == 3 and r["document_sha256"] == "abc"


def test_mou_incomplete_until_all_signed():
    r = evaluate_mou(doc(signatures=1, eseals=0), 3, 2, TODAY)
    assert r["verification_status"] == "INCOMPLETE" and "1 of 3 signatures" in r["verification_notes"]


def test_mou_invalid_when_altered():
    r = evaluate_mou(doc(valid=False, problems=["document content changed after signing"]), 3, 2, TODAY)
    assert r["verification_status"] == "INVALID" and "changed after signing" in r["verification_notes"]


def test_mou_invalid_even_if_flag_missing():
    assert evaluate_mou(Response(Outcome.OK, {"signatures": 3, "eseals": 2}), 3, 2, TODAY)["verification_status"] == "INVALID"


def test_mou_not_found_and_not_checked():
    assert evaluate_mou(Response(Outcome.NOT_FOUND), 3, 2, TODAY)["verification_status"] == "NOT_FOUND"
    assert evaluate_mou(Response(Outcome.UNAVAILABLE), 3, 2, TODAY)["verification_status"] == "NOT_CHECKED"


# ---- overlap
A = dict(latitude=3.4000, longitude=31.3000, service_type="CASH")


def test_distance_known_value():
    # 0.001 degrees of latitude is about 111 m
    assert 110 < distance_m(3.0, 31.0, 3.001, 31.0) < 112
    assert distance_m(3.0, 31.0, 3.0, 31.0) == 0


def test_overlap_found_within_radius_nearest_first():
    others = [dict(latitude=3.4020, longitude=31.3000, service_type="CASH", label="WNRP Point B"),
              dict(latitude=3.4010, longitude=31.3000, service_type="CASH", label="Other C")]
    r = evaluate_overlap(A, others, 500, TODAY)
    assert r["overlap_status"] == "OVERLAP" and r["overlap_with"].startswith("Other C (111 m)")


def test_no_overlap_outside_radius_or_other_service_type():
    far = dict(latitude=3.4100, longitude=31.3000, service_type="CASH", label="far")
    other_type = dict(latitude=3.4001, longitude=31.3000, service_type="FOOD", label="food")
    r = evaluate_overlap(A, [far, other_type], 500, TODAY)
    assert r["overlap_status"] == "NONE" and r["overlap_with"] is None


def test_overlap_not_checked_without_coordinates():
    assert evaluate_overlap({"service_type": "CASH"}, [A], 500, TODAY)["overlap_status"] == "NOT_CHECKED"
    assert evaluate_overlap({"latitude": 99, "longitude": 0}, [A], 500, TODAY)["overlap_status"] == "NOT_CHECKED"


def test_coordinate_validation():
    assert valid_coordinates("3.4", "31.3") and not valid_coordinates(91, 0) and not valid_coordinates(0, 181)
    assert not valid_coordinates(None, 5) and not valid_coordinates("x", "y")


from openg2p_registry_refugee_extension.rules.service_point_overlap import coordinate_error  # noqa: E402


def test_new_point_needs_both_coordinates_or_none():
    assert coordinate_error({"edit_action": "ADD", "latitude": 3.4}) == "latitude and longitude must be entered together"
    assert coordinate_error({"edit_action": "ADD", "longitude": 31.3}) == "latitude and longitude must be entered together"
    assert coordinate_error({"edit_action": "ADD"}) is None
    assert coordinate_error({"edit_action": "ADD", "latitude": 3.4, "longitude": 31.3}) is None


def test_edit_may_change_one_coordinate_but_it_must_be_in_range():
    assert coordinate_error({"edit_action": "UPDATE", "latitude": 3.41}) is None
    assert "latitude" in coordinate_error({"edit_action": "UPDATE", "latitude": 91})
    assert "longitude" in coordinate_error({"edit_action": "UPDATE", "longitude": "abc"})
    assert coordinate_error({"edit_action": "ADD", "latitude": 3, "longitude": 200}).startswith("longitude")
