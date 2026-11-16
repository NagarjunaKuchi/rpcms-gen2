"""ID-renewal SMS wording and recipient lookup. Pure functions (no I/O, no platform imports)."""


def first_phone(phone_numbers) -> str:
    """The first usable number in a register's phone_numbers list ([{"number": "+256..."}, ...])."""
    for item in phone_numbers or []:
        raw = item.get("number") if isinstance(item, dict) else item
        number = str(raw).strip() if raw is not None else ""
        if number:
            return number
    return ""


def sms_text(status: str, request_ref, card_expiry, appointment_date, appointment_time, appointment_location) -> str | None:
    when = " ".join(str(v) for v in (appointment_date, appointment_time) if v)
    return {
        "EXPIRY_FLAGGED": f"OPM Refugees: your refugee ID expires on {card_expiry}. Please book a renewal appointment at the Bidibidi service centre.",
        "APPOINTMENT_BOOKED": f"OPM Refugees: your renewal appointment is booked for {when} at {appointment_location}. Bring your current ID. Ref {request_ref}.",
        "CLOSED_RENEWED": "OPM Refugees: your refugee ID renewal is complete.",
        "CLOSED_NOT_RENEWED": "OPM Refugees: your renewal request was closed without renewal. Please contact OPM Bidibidi.",
    }.get(status)
