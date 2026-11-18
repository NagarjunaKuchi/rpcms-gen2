"""Budget lock: once a project's MoU is signed, its budget cannot be changed.
Pure functions (no I/O, no platform imports).

The budget is the project value, its currency, and the two figures it is built from (target households and the rate per
household). A change request that only repeats the stored values is not a change, so a screen that resends the whole
form is not refused."""
from decimal import Decimal, InvalidOperation

LOCKED_FIELDS = ("project_value", "currency", "target_households", "household_rate")
REFUSAL_PREFIX = "Project budget is locked"
SIGNED = "SIGNED"


def _norm(value):
    if value is None or str(value).strip() == "":
        return None
    try:
        return Decimal(str(value).replace(",", "").strip()).normalize()
    except InvalidOperation:
        return str(value).strip()


def changed_budget_fields(stored: dict, incoming: dict) -> list[str]:
    """Budget fields the change names with a value different from the stored one."""
    return [f for f in LOCKED_FIELDS if f in incoming and _norm(incoming.get(f)) != _norm(stored.get(f))]


def refusal(project_code, fields: list[str]) -> str | None:
    if not fields:
        return None
    return (f"{REFUSAL_PREFIX}: the MoU for project {project_code or ''} is signed, so {', '.join(fields)} "
            "cannot be changed").replace("project  is", "this project is")
