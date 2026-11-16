from datetime import date

from openg2p_registry_refugee_extension.integrations import Outcome, Response
from openg2p_registry_refugee_extension.rules.partner_compliance import evaluate_partner

TODAY = date(2026, 11, 16)
GOOD_URSB = Response(Outcome.OK, {"name": "Nile Hope Uganda", "status": "ACTIVE"})
GOOD_PERMIT = Response(Outcome.OK, {"status": "VALID", "valid_to": "2027-12-31"})
NOT_FOUND = Response(Outcome.NOT_FOUND)
DOWN = Response(Outcome.UNAVAILABLE, detail="timeout")
OFF = Response(Outcome.NOT_CONFIGURED)


def ev(ursb=GOOD_URSB, permit=GOOD_PERMIT, name="Nile Hope Uganda", days=60):
    return evaluate_partner(name, ursb, permit, TODAY, days)


def test_compliant_and_alert_date():
    r = ev()
    assert r["compliance_status"] == "COMPLIANT" and r["compliance_notes"] is None
    assert r["permit_valid_to"] == date(2027, 12, 31)
    assert r["permit_renewal_alert_date"] == date(2027, 11, 1)  # 60 days before
    assert r["compliance_checked_on"] == TODAY


def test_alert_days_is_configurable():
    assert ev(days=30)["permit_renewal_alert_date"] == date(2027, 12, 1)


def test_name_comparison_ignores_case_and_spacing():
    assert ev(name="  nile   HOPE uganda ")["compliance_status"] == "COMPLIANT"


def test_name_mismatch_is_non_compliant():
    r = ev(name="Other Org")
    assert r["compliance_status"] == "NON_COMPLIANT" and "Name differs" in r["compliance_notes"]


def test_ursb_inactive_is_non_compliant():
    r = ev(ursb=Response(Outcome.OK, {"name": "Nile Hope Uganda", "status": "DEREGISTERED"}))
    assert r["compliance_status"] == "NON_COMPLIANT" and r["ursb_status"] == "DEREGISTERED"


def test_expired_permit_is_non_compliant():
    r = ev(permit=Response(Outcome.OK, {"status": "VALID", "valid_to": "2026-11-15"}))
    assert r["ngo_permit_status"] == "EXPIRED" and r["compliance_status"] == "NON_COMPLIANT"


def test_permit_expiring_today_is_still_valid():
    r = ev(permit=Response(Outcome.OK, {"status": "VALID", "valid_to": "2026-11-16"}))
    assert r["compliance_status"] == "COMPLIANT"


def test_both_not_found_is_non_compliant():
    r = ev(ursb=NOT_FOUND, permit=NOT_FOUND)
    assert r["compliance_status"] == "NON_COMPLIANT"
    assert r["ursb_status"] == r["ngo_permit_status"] == "NOT_FOUND"
    assert "URSB registration number not found" in r["compliance_notes"]


def test_unavailable_system_means_not_checked_never_a_verdict():
    for bad in (DOWN, OFF):
        r = ev(ursb=bad)
        assert r["compliance_status"] == "NOT_CHECKED" and r["ursb_status"] == "NOT_CHECKED"
        r = ev(permit=bad)
        assert r["compliance_status"] == "NOT_CHECKED" and r["ngo_permit_status"] == "NOT_CHECKED"


def test_one_definite_failure_does_not_override_an_unchecked_system():
    # URSB says "not found" but the NGO Bureau could not answer: the overall result stays NOT_CHECKED
    # (re-run the check) rather than recording a verdict from half the evidence.
    assert ev(ursb=NOT_FOUND, permit=DOWN)["compliance_status"] == "NOT_CHECKED"


def test_permit_without_usable_date_is_not_checked():
    for bad in ({"status": "VALID"}, {"status": "VALID", "valid_to": "soon"}):
        r = ev(permit=Response(Outcome.OK, bad))
        assert r["compliance_status"] == "NOT_CHECKED" and "permit_valid_to" not in r
