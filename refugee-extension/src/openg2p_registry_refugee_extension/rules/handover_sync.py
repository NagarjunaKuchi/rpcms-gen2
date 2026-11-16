"""Field handover sync rules: shape-check one record from a phone and turn it into an assistance-event row.
Pure functions (no I/O, no platform imports) so they are unit-tested without the platform.

Only the whitelisted fields below are taken from the phone. In particular `progres_authenticated` is never accepted: the
registry sets it from ProGres itself, so a phone cannot claim an authentication it did not get."""
from datetime import date, datetime, timezone

from .service_point_overlap import valid_coordinates

MAX_BATCH = 200
CHANNEL = "OFFLINE_HANDOVER"

REQUIRED = ("client_record_id", "registrant_progres_id", "partner_code", "assistance_type", "distribution_cycle", "delivery_date")
TEXT = ("registrant_progres_id", "partner_code", "partner_name", "project_ref", "assistance_type", "distribution_cycle",
        "unit", "currency", "delivery_location", "officer", "client_record_id")
NUMBER = ("quantity", "amount")


def _text(value) -> str:
    return str(value).strip() if value is not None else ""


def parse_instant(value) -> datetime | None:
    """ISO-8601 with an offset ('2026-03-05T11:42:00+03:00' or '...Z'). A time without an offset is refused: a phone's
    local time cannot be placed without knowing its zone."""
    try:
        parsed = datetime.fromisoformat(_text(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def to_row(raw: dict, batch_id: str | None, now: datetime | None = None) -> tuple[dict | None, str | None]:
    """(row, None) when the record is usable, else (None, reason). Reasons are written for the person fixing the phone."""
    if not isinstance(raw, dict):
        return None, "record must be an object"
    now = now or datetime.now(timezone.utc)
    for key in REQUIRED:
        if not _text(raw.get(key)):
            return None, f"{key} is required"
    row = {key: _text(raw[key]) for key in TEXT if _text(raw.get(key))}
    try:
        delivery = date.fromisoformat(_text(raw["delivery_date"])[:10])
    except ValueError:
        return None, "delivery_date must be a date like 2026-03-05"
    if delivery > now.date():
        return None, "delivery_date cannot be in the future"
    row["delivery_date"] = delivery.isoformat()
    for key in NUMBER:
        if _text(raw.get(key)):
            try:
                value = float(raw[key])
            except (TypeError, ValueError):
                return None, f"{key} must be a number"
            if value < 0:
                return None, f"{key} must not be negative"
            row[key] = value
    if _text(raw.get("captured_at")):
        instant = parse_instant(raw["captured_at"])
        if instant is None:
            return None, "captured_at must be a date-time with a zone, like 2026-03-05T11:42:00+03:00"
        if instant > now:
            return None, "captured_at cannot be in the future"
        row["captured_at"] = instant.isoformat()
    lat, lon = raw.get("gps_latitude"), raw.get("gps_longitude")
    if _text(lat) or _text(lon):
        if not valid_coordinates(lat, lon):
            return None, "gps_latitude and gps_longitude must both be given and be real coordinates"
        row["gps_latitude"], row["gps_longitude"] = float(lat), float(lon)
        if _text(raw.get("gps_accuracy_m")):
            try:
                accuracy = float(raw["gps_accuracy_m"])
            except (TypeError, ValueError):
                return None, "gps_accuracy_m must be a number"
            if accuracy < 0:
                return None, "gps_accuracy_m must not be negative"
            row["gps_accuracy_m"] = accuracy
    elif _text(raw.get("gps_accuracy_m")):
        return None, "gps_accuracy_m needs a GPS position"
    row["capture_channel"] = CHANNEL
    if batch_id:
        row["offline_batch_id"] = _text(batch_id)
    return row, None


def batch_error(batch_id, records) -> str | None:
    if not _text(batch_id):
        return "batch_id is required"
    if not isinstance(records, list) or not records:
        return "records must be a non-empty list"
    if len(records) > MAX_BATCH:
        return f"at most {MAX_BATCH} records per request; send the rest in a further request"
    return None
