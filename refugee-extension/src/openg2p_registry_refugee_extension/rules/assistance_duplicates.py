"""Duplicate-assistance rule: the same registrant must not receive the same assistance type twice in a
distribution cycle. Pure helpers (no I/O, no platform imports)."""

DEDUP_KEYS = ("registrant_progres_id", "assistance_type", "distribution_cycle")


def key_of(row: dict) -> tuple | None:
    """The (registrant, type, cycle) identity of an assistance row, or None when any part is missing."""
    key = tuple(str(row.get(k) or "").strip() for k in DEDUP_KEYS)
    return key if all(key) else None


def first_duplicate_within(rows: list[dict]) -> tuple | None:
    """The first identity that appears more than once among the rows of one request."""
    seen = set()
    for row in rows:
        key = key_of(row)
        if key is None:
            continue
        if key in seen:
            return key
        seen.add(key)
    return None


def message(key: tuple) -> str:
    return f"Duplicate assistance: registrant {key[0]} already received {key[1]} in cycle {key[2]}"
