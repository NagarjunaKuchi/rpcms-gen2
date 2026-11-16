"""Service-point overlap rule: flag a partner's service point that lies within a radius of another partner's
point of the same service type. Pure functions (no I/O, no platform imports)."""
import math
from datetime import date

EARTH_RADIUS_M = 6_371_000.0


def valid_coordinates(lat, lon) -> bool:
    try:
        return -90 <= float(lat) <= 90 and -180 <= float(lon) <= 180
    except (TypeError, ValueError):
        return False


def distance_m(lat1, lon1, lat2, lon2) -> float:
    """Great-circle (haversine) distance in metres."""
    p1, p2 = math.radians(float(lat1)), math.radians(float(lat2))
    dp, dl = p2 - p1, math.radians(float(lon2) - float(lon1))
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def evaluate_overlap(point: dict, others: list[dict], radius_m: float, today: date) -> dict:
    """point: {latitude, longitude, service_type}. others: [{latitude, longitude, service_type, label}] belonging to
    OTHER partners. NOT_CHECKED when the point has no usable coordinates; otherwise NONE or OVERLAP (nearest first)."""
    out: dict = {"overlap_checked_on": today}
    if not valid_coordinates(point.get("latitude"), point.get("longitude")):
        out.update(overlap_status="NOT_CHECKED", overlap_with=None)
        return out
    hits = []
    for other in others:
        if other.get("service_type") != point.get("service_type") or not valid_coordinates(other.get("latitude"), other.get("longitude")):
            continue
        d = distance_m(point["latitude"], point["longitude"], other["latitude"], other["longitude"])
        if d <= radius_m:
            hits.append((d, other.get("label") or "another partner"))
    hits.sort()
    out.update(overlap_status="OVERLAP" if hits else "NONE",
               overlap_with="; ".join(f"{label} ({d:.0f} m)" for d, label in hits) or None)
    return out


def coordinate_error(record: dict) -> str | None:
    """Why the coordinates in a service-point entry are unacceptable, or None.

    A new point (ADD) must give both or neither. An edit (UPDATE) may change just one of them, because the other
    one is already stored; each value given must still be a number in range."""
    lat, lon = record.get("latitude"), record.get("longitude")
    has_lat, has_lon = lat not in (None, ""), lon not in (None, "")
    if record.get("edit_action") in (None, "ADD") and has_lat != has_lon:
        return "latitude and longitude must be entered together"
    for name, value, limit in (("latitude", lat, 90), ("longitude", lon, 180)):
        if value in (None, ""):
            continue
        try:
            ok = -limit <= float(value) <= limit
        except (TypeError, ValueError):
            ok = False
        if not ok:
            return f"{name} must be a number between -{limit} and {limit}"
    return None
