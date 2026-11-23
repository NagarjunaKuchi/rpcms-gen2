"""Review of a refused duplicate-assistance entry (a referral). Pure functions (no I/O, no platform imports).

A refused duplicate becomes a case with status OPEN. A reviewer either CONFIRMS it was a real duplicate (it stays
refused) or RELEASES it (the same entry may then be recorded once). A case is decided once."""
OPEN, CONFIRMED, RELEASED = "OPEN", "CONFIRMED_DUPLICATE", "RELEASED"
DECISIONS = {"CONFIRM": CONFIRMED, "RELEASE": RELEASED}


def decide(current_status: str | None, decision: str | None, note: str | None) -> tuple[str | None, str | None]:
    """(new status, None) when the decision may be made, or (None, why not)."""
    if current_status != OPEN:
        return None, f"this case was already decided ({current_status})"
    status = DECISIONS.get(str(decision or "").upper())
    if status is None:
        return None, f"decision must be one of {sorted(DECISIONS)}"
    if status == RELEASED and not str(note or "").strip():
        return None, "a note is required to release a case: say why the second entry is allowed"
    return status, None
