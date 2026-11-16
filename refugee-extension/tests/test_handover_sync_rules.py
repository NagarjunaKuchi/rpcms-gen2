from datetime import datetime, timezone

import pytest

from openg2p_registry_refugee_extension.rules import handover_sync as h

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
RAW = {"client_record_id": "DST-1", "registrant_progres_id": "UGA-00423318", "partner_code": "NHU",
       "assistance_type": "CASH_FOR_FOOD", "distribution_cycle": "2026-03", "delivery_date": "2026-03-05",
       "amount": "150000", "currency": "UGX", "captured_at": "2026-03-05T11:42:00+03:00",
       "gps_latitude": 3.4719, "gps_longitude": 31.3547, "gps_accuracy_m": 8, "officer": "Emmanuel Taban"}


def row(**over):
    return h.to_row({**RAW, **over}, "B-1", NOW)


def test_good_record_becomes_a_row_marked_as_offline_handover():
    r, problem = row()
    assert problem is None
    assert r["capture_channel"] == "OFFLINE_HANDOVER" and r["offline_batch_id"] == "B-1"
    assert r["amount"] == 150000.0 and r["delivery_date"] == "2026-03-05" and r["gps_latitude"] == 3.4719
    assert r["captured_at"].startswith("2026-03-05T11:42:00")


def test_phone_cannot_claim_a_progres_authentication():
    r, _ = row(progres_authenticated=True, internal_record_id="x", record_status="ACTIVE")
    assert "progres_authenticated" not in r and "internal_record_id" not in r and "record_status" not in r


@pytest.mark.parametrize("key", h.REQUIRED)
def test_required_fields(key):
    r, problem = row(**{key: " "})
    assert r is None and key in problem


@pytest.mark.parametrize("over,words", [
    ({"delivery_date": "05/03/2026"}, "delivery_date"),
    ({"delivery_date": "2026-12-01"}, "future"),
    ({"amount": "lots"}, "amount"),
    ({"amount": -5}, "negative"),
    ({"captured_at": "2026-03-05T11:42:00"}, "zone"),
    ({"captured_at": "2027-01-01T00:00:00Z"}, "future"),
    ({"gps_longitude": None}, "both"),
    ({"gps_latitude": 95}, "real coordinates"),
    ({"gps_accuracy_m": -1}, "negative"),
])
def test_bad_values_are_refused_with_a_reason(over, words):
    r, problem = row(**over)
    assert r is None and words in problem


def test_gps_is_optional_but_accuracy_needs_a_position():
    no_gps = {k: v for k, v in RAW.items() if not k.startswith("gps_")}
    assert h.to_row(no_gps, None, NOW)[1] is None
    assert "GPS position" in h.to_row({**no_gps, "gps_accuracy_m": 5}, None, NOW)[1]


def test_zulu_time_is_accepted_and_non_objects_refused():
    assert row(captured_at="2026-03-05T08:42:00Z")[1] is None
    assert h.to_row("nope", "B", NOW)[1] == "record must be an object"


def test_batch_limits():
    assert h.batch_error("", [RAW]) == "batch_id is required"
    assert h.batch_error("B", []) and h.batch_error("B", "x")
    assert h.batch_error("B", [RAW] * (h.MAX_BATCH + 1)) and h.batch_error("B", [RAW]) is None
