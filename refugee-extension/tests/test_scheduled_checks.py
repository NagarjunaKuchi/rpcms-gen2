from datetime import date

from openg2p_registry_refugee_extension.rules.scheduled_checks import (
    id_expiry_due, permit_alert_due, permit_sms_text, renewal_ref)

TODAY = date(2026, 11, 18)
ALERT, VALID_TO = date(2026, 11, 1), date(2026, 12, 31)


def test_permit_alert_is_due_from_the_alert_date_until_expiry():
    assert permit_alert_due(TODAY, ALERT, VALID_TO, None)
    assert permit_alert_due(ALERT, ALERT, VALID_TO, None)
    assert permit_alert_due(VALID_TO, ALERT, VALID_TO, None)
    assert not permit_alert_due(date(2026, 10, 31), ALERT, VALID_TO, None)
    assert not permit_alert_due(date(2027, 1, 1), ALERT, VALID_TO, None)  # expired: a different problem


def test_permit_alert_is_sent_once_per_permit():
    assert not permit_alert_due(TODAY, ALERT, VALID_TO, date(2026, 11, 2))
    assert not permit_alert_due(TODAY, ALERT, VALID_TO, ALERT)
    assert permit_alert_due(TODAY, ALERT, VALID_TO, date(2026, 10, 1))  # sent for an earlier permit


def test_permit_alert_needs_dates():
    assert not permit_alert_due(TODAY, None, VALID_TO, None)
    assert not permit_alert_due(TODAY, ALERT, None, None)


def test_permit_sms_names_the_organisation_and_date():
    text = permit_sms_text("Nile Hope Uganda", VALID_TO)
    assert "Nile Hope Uganda" in text and "2026-12-31" in text
    assert "your organisation" in permit_sms_text(None, VALID_TO)


def test_id_expiry_window():
    assert id_expiry_due(TODAY, date(2026, 11, 18), 60)
    assert id_expiry_due(TODAY, date(2027, 1, 17), 60)  # exactly 60 days ahead
    assert not id_expiry_due(TODAY, date(2027, 1, 18), 60)
    assert not id_expiry_due(TODAY, date(2026, 11, 17), 60)  # already expired: not picked up
    assert not id_expiry_due(TODAY, None, 60)


def test_renewal_ref_is_stable_per_person_and_expiry():
    assert renewal_ref("UGA-1", date(2026, 12, 31)) == "AUTO-UGA-1-20261231"
    assert renewal_ref("UGA-1", date(2026, 12, 31)) == renewal_ref("UGA-1", date(2026, 12, 31))
    assert renewal_ref("UGA-1", date(2027, 12, 31)) != renewal_ref("UGA-1", date(2026, 12, 31))
