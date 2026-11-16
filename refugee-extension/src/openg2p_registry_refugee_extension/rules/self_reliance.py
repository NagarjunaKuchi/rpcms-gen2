"""Self-reliance survey rules: answer checks and the self-reliance index. Pure functions (no I/O, no platform imports)
so they are unit-tested without the platform.

THE INDEX FORMULA IS RPCMS'S OWN WORKING FORMULA (version INDEX_VERSION). It is not taken from the demo, from UNHCR, OPM
or any NDP IV / NIMES document: the demo shows index values (31, 54) but not how they are derived. The weights below must
be replaced by the agreed national methodology before the index is used for decisions. `index_version` is stored with
every score so scores made under a different formula can be told apart."""
import re
from datetime import date

INDEX_VERSION = "rpcms-v1"

FOOD_SOURCE = {"ASSISTANCE_ONLY": 0, "OWN_PRODUCTION_AND_ASSISTANCE": 20, "MARKET_INCOME": 40}
INCOME = {"NO": 0, "YES": 30}
SCHOOL = {"NONE": 0, "ONE_TO_TWO": 8, "THREE_OR_MORE": 15}
SAVINGS = {"NO": 0, "YES": 15}

# answer field -> its allowed values and the points each earns. The maxima add up to 100.
SCALES = {"food_source": FOOD_SOURCE, "has_income": INCOME, "children_in_school": SCHOOL, "savings_group_member": SAVINGS}
MAX_INDEX = sum(max(scale.values()) for scale in SCALES.values())

_ROUND = re.compile(r"^(\d{4})-R(\d{1,2})$")


def answer_error(record: dict, today: date | None = None) -> str | None:
    """The first problem in the fields the record carries (a partial update carries only what it changes)."""
    for field, scale in SCALES.items():
        value = record.get(field)
        if value not in (None, "") and str(value) not in scale:
            return f"{field} must be one of {sorted(scale)}"
    label = record.get("round_label")
    if "round_label" in record and not str(label or "").strip():
        return "round_label must not be empty"
    if label not in (None, "") and not _ROUND.match(str(label).strip()):
        return "round_label must look like 2026-R2 (year, then round number)"
    if str(record.get("has_income") or "") == "NO" and str(record.get("income_source") or "").strip():
        return "income_source must be empty when the household has no income"
    survey_date = record.get("survey_date")
    if isinstance(survey_date, date) and today is not None and survey_date > today:
        return "survey_date cannot be in the future"
    return None


def compute_index(record: dict) -> int | None:
    """0-100, or None when any of the four answers is missing: an unfinished survey is not scored, never scored as 0."""
    total = 0
    for field, scale in SCALES.items():
        value = record.get(field)
        if value in (None, "") or str(value) not in scale:
            return None
        total += scale[str(value)]
    return total
