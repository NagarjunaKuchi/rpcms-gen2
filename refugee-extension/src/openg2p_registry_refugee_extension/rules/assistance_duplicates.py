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


def household_message(key: tuple, holder: str) -> str:
    """The refusal when another member of the registrant's household already received this assistance."""
    return (f"Duplicate assistance: household member {holder} already received {key[1]} in cycle {key[2]} "
            f"(household of registrant {key[0]})")


def with_referral(text: str, case_ref: str | None) -> str:
    """The refusal, plus the referral case it created, so the person entering it knows it went to review."""
    return f"{text}; referred for review as case {case_ref}" if case_ref else text
