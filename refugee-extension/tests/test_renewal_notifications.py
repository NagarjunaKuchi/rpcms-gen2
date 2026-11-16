from openg2p_registry_refugee_extension.rules.renewal_notifications import first_phone, sms_text


def test_first_phone_skips_blank_entries():
    assert first_phone([{"number": " "}, {"number": "+256700000001"}, {"number": "+256700000002"}]) == "+256700000001"


def test_first_phone_handles_missing_and_odd_shapes():
    assert first_phone(None) == "" and first_phone([]) == "" and first_phone([{}]) == ""
    assert first_phone(["+256700000009"]) == "+256700000009"


def test_texts_per_status():
    a = ("REQ-1", "2026-10-31", "2026-11-20", "10:00", "OPM office Bidibidi")
    assert "expires on 2026-10-31" in sms_text("EXPIRY_FLAGGED", *a)
    booked = sms_text("APPOINTMENT_BOOKED", *a)
    assert "2026-11-20 10:00" in booked and "OPM office Bidibidi" in booked and "REQ-1" in booked
    assert "complete" in sms_text("CLOSED_RENEWED", *a)
    assert "without renewal" in sms_text("CLOSED_NOT_RENEWED", *a)


def test_unknown_status_sends_nothing():
    assert sms_text("SOMETHING_ELSE", "R", None, None, None, None) is None
