"""Project funding rule: compare a registered project with its AMP (Aid Management Platform) record.
Pure function (no I/O, no platform imports)."""
from datetime import date
from decimal import Decimal, InvalidOperation

from ..integrations import Outcome, Response


def _number(value) -> Decimal | None:
    try:
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, AttributeError):
        return None


def evaluate_funding(project_value, currency: str | None, amp: Response, today: date) -> dict:
    """Fields for the project's funding section.

    CONFIRMED    AMP has the record and its commitment equals the project value (same currency).
    MISMATCH     AMP has the record but the value or currency differs.
    NOT_FOUND    AMP has no such record.
    NOT_CHECKED  AMP could not answer (not configured / unavailable): nothing is concluded.
    """
    out: dict = {"amp_checked_on": today}
    if amp.outcome is Outcome.NOT_FOUND:
        out.update(amp_status="NOT_FOUND", amp_notes="AMP record number not found")
    elif amp.outcome is not Outcome.OK:
        out.update(amp_status="NOT_CHECKED", amp_notes=f"AMP not checked ({amp.outcome.value.lower().replace('_', ' ')})")
    else:
        d = amp.data
        commitment = _number(d.get("commitment"))
        out.update(amp_donor=d.get("donor"), amp_commitment=commitment, amp_disbursed=_number(d.get("disbursed_to_partner")))
        notes = []
        if commitment is None:
            notes.append("AMP record has no usable commitment amount")
        elif _number(project_value) != commitment:
            notes.append(f"Project value {project_value} differs from AMP commitment {commitment}")
        if d.get("currency") and currency and d["currency"] != currency:
            notes.append(f"Currency {currency} differs from AMP currency {d['currency']}")
        out.update(amp_status="MISMATCH" if notes else "CONFIRMED", amp_notes="; ".join(notes) or None)
    return out
