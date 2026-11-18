"""Partner gate: work is recorded only for a partner whose compliance check has not failed.

Pure function (no I/O, no platform imports) so it can be unit-tested on its own.

NON_COMPLIANT blocks: both outside systems answered and a check failed (inactive registration, expired permit, name
differs, district not covered). NOT_CHECKED does not block: a system could not answer, so nothing is concluded, and an
outage at URSB or the NGO Bureau must not stop field work. (Whether it should is an open question for OPM/UNHCR.)
Change BLOCKING to include "NOT_CHECKED" to make the gate strict.
"""
BLOCKING = frozenset({"NON_COMPLIANT"})
REFUSAL_PREFIX = "Partner is not compliant"


def refusal(partner_code, compliance_status, notes=None, what: str = "work") -> str | None:
    """The message that refuses `what` (e.g. 'a project') for this partner, or None when it may go ahead."""
    if str(compliance_status or "") not in BLOCKING:
        return None
    why = f": {notes}" if notes else ""
    return f"{REFUSAL_PREFIX}: {what} cannot be recorded for partner {partner_code}{why}"
