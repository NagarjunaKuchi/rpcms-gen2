"""Quarterly reporting rules: pure helpers (no I/O, no platform imports) so they are unit-tested without the platform.

The indicator codes below are RPCMS's own working codes. They are NOT the NDP IV / NIMES indicator catalogue: that
catalogue has to come from OPM/NIMES, and these must be mapped to it before submissions are real."""
import hashlib
import json
import re
from datetime import date

SYSTEMS = ("AMP", "NIMES")
_QUARTER = re.compile(r"^(\d{4})-Q([1-4])$")


def parse_quarter(value: str) -> tuple[date, date]:
    """'2026-Q3' -> (2026-07-01, 2026-10-01): the first day of the quarter and of the next one."""
    m = _QUARTER.match(str(value or "").strip().upper())
    if not m:
        raise ValueError("quarter must look like 2026-Q3")
    year, q = int(m.group(1)), int(m.group(2))
    start = date(year, 3 * (q - 1) + 1, 1)
    end = date(year + 1, 1, 1) if q == 4 else date(year, 3 * q + 1, 1)
    return start, end


def quarter_of(day: date) -> str:
    return f"{day.year}-Q{(day.month - 1) // 3 + 1}"


def build_expenditure(quarter: str, rows: list[dict]) -> tuple[dict, list[dict]]:
    """Split per-project spend into what can be sent and what cannot.

    rows: {project_code, amp_record_no, currency, amount, events}. A project with no AMP record number cannot be
    matched to a funding record, so it is returned in `unmatched` instead of being sent under a guess."""
    items, unmatched = [], []
    for r in rows:
        amount = float(r.get("amount") or 0)
        entry = {"project_code": r.get("project_code"), "currency": r.get("currency"), "amount": round(amount, 2),
                 "events": int(r.get("events") or 0)}
        amp = str(r.get("amp_record_no") or "").strip()
        if amp and r.get("currency"):
            items.append({"amp_record": amp, **entry})
        else:
            unmatched.append({**entry, "reason": "no AMP record number" if not amp else "no currency"})
    return {"quarter": quarter, "items": items}, unmatched


def build_indicators(quarter: str, summary: dict) -> dict:
    """Indicators computed from what RPCMS records. Values that cannot be computed are left out, never zeroed."""
    spec = [
        ("RPCMS-PARTNERS-COMPLIANT", "Partners verified compliant (URSB and NGO Bureau)", "partners_compliant", "count"),
        ("RPCMS-EVENTS-AUTHENTICATED", "Assistance events with a confirmed ProGres ID", "events_authenticated", "count"),
        ("RPCMS-PERSONS-REACHED", "Distinct registrants reached with assistance", "persons_reached", "count"),
        ("RPCMS-DUPLICATES-FLAGGED", "Duplicate assistance attempts refused", "duplicates_flagged", "count"),
        ("RPCMS-HOUSEHOLDS-SURVEYED", "Households with a self-reliance survey in the quarter", "households_surveyed", "count"),
        ("RPCMS-HOUSEHOLDS-WITH-INCOME", "Surveyed households that earn income (latest survey in the quarter)", "households_with_income", "count"),
    ]
    indicators = []
    for code, name, key, unit in spec:
        if summary.get(key) is None:
            continue
        indicators.append({"code": code, "name": name, "value": int(summary[key]), "unit": unit})
    return {"quarter": quarter, "indicators": indicators}


def payload_digest(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
