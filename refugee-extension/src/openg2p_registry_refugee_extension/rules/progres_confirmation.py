"""ProGres confirmation rule: turn the ProGres v4 answer into the fields stored on an assistance row.
Pure function (no I/O, no platform imports).

RPCMS keeps exactly three things from ProGres: Yes/No, the transaction reference and the time of the check.
Nothing else in the answer is read, so no refugee profile data can be copied by accident."""
from ..integrations import Outcome, Response

REGISTRY_ONLY = ("progres_auth_reference", "progres_authenticated_at")
MAX_LEN = 128


def _clean(value) -> str | None:
    """A short single-line string, or None. Objects and lists are refused rather than stored as text."""
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return None
    text = " ".join(str(value).split())
    return text[:MAX_LEN] or None


def confirmation_fields(response: Response) -> dict:
    """Fields to write on the row, or {} when ProGres could not answer (nothing is concluded).

    OK         Yes/No as answered, with the reference and time ProGres gave (None when it gave none).
    NOT_FOUND  ProGres does not know the ID: No, with no reference or time.
    otherwise  {} : the row keeps "not checked", never "No"."""
    if response.outcome is Outcome.OK:
        return {
            "progres_authenticated": bool(response.data.get("authenticated")),
            "progres_auth_reference": _clean(response.data.get("reference")),
            "progres_authenticated_at": _clean(response.data.get("timestamp")),
        }
    if response.outcome is Outcome.NOT_FOUND:
        return {"progres_authenticated": False, "progres_auth_reference": None, "progres_authenticated_at": None}
    return {}


REFUSAL_PREFIX = "ProGres did not confirm"


def must_be_confirmed(edit_action, id_changed: bool = False) -> bool:
    """Whether a ProGres "No" refuses this row.

    A new assistance row (the handover itself) always. An edit only when it changes the ProGres ID: correcting the
    amount or location of a handover already recorded must stay possible after the person's ID has lapsed, but an
    edit must not be a way to move a row onto an ID ProGres does not confirm."""
    if edit_action in (None, "ADD"):
        return True
    return edit_action == "UPDATE" and bool(id_changed)


def refusal(progres_id: str, fields: dict) -> str | None:
    """The refusal text when ProGres answered No, else None. An empty `fields` (ProGres could not answer) never
    refuses: "not checked" is not "No"."""
    if fields.get("progres_authenticated") is False:
        return f"{REFUSAL_PREFIX} ID {progres_id}: the assistance cannot be recorded"
    return None


def strip_registry_only(row: dict) -> bool:
    """Remove a reference or time supplied by the person or system entering the row. True when something was removed."""
    removed = False
    for key in REGISTRY_ONLY:
        if key in row:
            del row[key]
            removed = True
    return removed
