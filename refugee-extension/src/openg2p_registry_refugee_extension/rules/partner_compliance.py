"""Partner compliance rule: combine the URSB and NGO Bureau answers into the fields stored on the partner row.

Pure function (no I/O, no platform imports) so it can be unit-tested on its own.
"""
from datetime import date, timedelta

from ..integrations import Outcome, Response

CHECKED = (Outcome.OK, Outcome.NOT_FOUND)


def _norm(name) -> str:
    return " ".join(str(name or "").lower().split())


def _district(name) -> str:
    """'Yumbe', 'yumbe district' and ' YUMBE  District ' are the same district."""
    words = _norm(name).split()
    if len(words) > 1 and words[-1] == "district":
        words = words[:-1]
    return " ".join(words)


def evaluate_area(operating_district, permit_data: dict) -> tuple[str, str | None]:
    """(permit_area_status, note): does the permit cover the district the partner will work in?

    COVERED      the district is in the permit's list of operating districts.
    NOT_COVERED  the permit lists districts and this one is not among them.
    NOT_CHECKED  no district entered for the partner, or the NGO Bureau answer lists none: nothing is concluded."""
    wanted = _district(operating_district)
    if not wanted:
        return "NOT_CHECKED", "Operating district not entered"
    listed = permit_data.get("operating_districts")
    districts = {_district(d) for d in listed if isinstance(d, str)} - {""} if isinstance(listed, list) else set()
    if not districts:
        return "NOT_CHECKED", "NGO Bureau answer did not list the permit's operating districts"
    if wanted in districts:
        return "COVERED", None
    return "NOT_COVERED", f"NGO permit does not cover {' '.join(str(operating_district).split())}"


def _parse_date(value) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _not_checked(system: str, response: Response) -> str:
    return f"{system} not checked ({response.outcome.value.lower().replace('_', ' ')})"


def evaluate_partner(organisation_name: str, ursb: Response, permit: Response, today: date, alert_days: int,
                     operating_district: str | None = None) -> dict:
    """Return the compliance fields for a partner.

    COMPLIANT      URSB registration ACTIVE with the same name AND NGO permit VALID, not expired and covering the
                   partner's operating district.
    NON_COMPLIANT  both systems answered and at least one check failed (not found, inactive, expired, name differs,
                   district not covered).
    NOT_CHECKED    a system could not answer (not configured / unavailable), or the permit is otherwise in order but
                   its area could not be compared (no district entered, or none listed): nothing is concluded.
    """
    out: dict = {}
    notes: list[str] = []

    ursb_ok = False
    ursb_checked = ursb.outcome in CHECKED
    if ursb.outcome is Outcome.OK:
        status = str(ursb.data.get("status") or "UNKNOWN")
        out["ursb_status"] = status
        out["ursb_registered_name"] = ursb.data.get("name")
        if status != "ACTIVE":
            notes.append(f"URSB status is {status}")
        elif _norm(organisation_name) != _norm(ursb.data.get("name")):
            notes.append(f"Name differs from URSB record ({ursb.data.get('name')})")
        else:
            ursb_ok = True
    elif ursb.outcome is Outcome.NOT_FOUND:
        out["ursb_status"] = "NOT_FOUND"
        notes.append("URSB registration number not found")
    else:
        out["ursb_status"] = "NOT_CHECKED"
        notes.append(_not_checked("URSB", ursb))

    permit_ok = False
    permit_checked = permit.outcome in CHECKED
    if permit.outcome is Outcome.OK:
        valid_to = _parse_date(permit.data.get("valid_to"))
        if valid_to is None:
            permit_checked = False
            out["ngo_permit_status"] = "NOT_CHECKED"
            out["permit_area_status"] = "NOT_CHECKED"
            notes.append("NGO Bureau answer had no usable permit expiry date")
        else:
            out["permit_valid_to"] = valid_to
            out["permit_renewal_alert_date"] = valid_to - timedelta(days=alert_days)
            if valid_to < today:
                out["ngo_permit_status"] = "EXPIRED"
                notes.append(f"NGO permit expired on {valid_to}")
            else:
                status = str(permit.data.get("status") or "UNKNOWN")
                out["ngo_permit_status"] = status
                permit_ok = status == "VALID"
                if not permit_ok:
                    notes.append(f"NGO permit status is {status}")
            # The area is always shown; it only decides compliance when the permit is otherwise in order.
            area_status, area_note = evaluate_area(operating_district, permit.data)
            out["permit_area_status"] = area_status
            if area_note:
                notes.append(area_note)
            if permit_ok and area_status == "NOT_COVERED":
                permit_ok = False
            elif permit_ok and area_status == "NOT_CHECKED":
                permit_checked = False
    elif permit.outcome is Outcome.NOT_FOUND:
        out["ngo_permit_status"] = "NOT_FOUND"
        out["permit_area_status"] = "NOT_CHECKED"
        notes.append("NGO permit number not found")
    else:
        out["ngo_permit_status"] = "NOT_CHECKED"
        out["permit_area_status"] = "NOT_CHECKED"
        notes.append(_not_checked("NGO Bureau", permit))

    if not (ursb_checked and permit_checked):
        out["compliance_status"] = "NOT_CHECKED"
    else:
        out["compliance_status"] = "COMPLIANT" if (ursb_ok and permit_ok) else "NON_COMPLIANT"
    out["compliance_checked_on"] = today
    out["compliance_notes"] = "; ".join(notes) or None
    return out
