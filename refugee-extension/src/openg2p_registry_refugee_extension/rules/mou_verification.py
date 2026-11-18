"""MoU rule: turn a UGPass verification answer into the status stored on the MoU row.
Signing itself happens in UGPass (each signatory confirms in their own app); RPCMS only checks the result.
Pure function (no I/O, no platform imports)."""
from datetime import date

from ..integrations import Outcome, Response


DRAFT, AWAITING, SIGNED = "DRAFT", "AWAITING_SIGNATURES", "SIGNED"


def mou_status(verification_status: str, signatures: int, eseals: int, previous: str | None = None) -> str:
    """The MoU's place in its life, from the UGPass check.
    SIGNED               every expected signature and e-Seal is there and nothing was altered (VALID).
    AWAITING_SIGNATURES  signing has started but is not complete (INCOMPLETE with something signed), or the signed
                         document no longer checks out (INVALID): it is not signed until it is signed again.
    DRAFT                prepared, nothing signed yet.
    A check that could not conclude (NOT_FOUND, NOT_CHECKED) changes nothing: the previous status stays, DRAFT for a
    new MoU."""
    if verification_status == "VALID":
        return SIGNED
    if verification_status == "INVALID":
        return AWAITING
    if verification_status == "INCOMPLETE":
        return AWAITING if (signatures or eseals) else DRAFT
    return previous or DRAFT


def evaluate_mou(verification: Response, expected_signatures: int, expected_eseals: int, today: date,
                 previous_status: str | None = None) -> dict:
    """VALID        nothing was altered and every expected signature and e-Seal is present.
    INCOMPLETE   nothing wrong, but fewer signatures or e-Seals than expected so far.
    INVALID      UGPass reports a problem (content changed after signing, bad signature).
    NOT_FOUND    UGPass has no such document.
    NOT_CHECKED  UGPass could not answer: nothing is concluded."""
    out: dict = {"verified_on": today}
    if verification.outcome is Outcome.NOT_FOUND:
        out.update(verification_status="NOT_FOUND", verification_notes="UGPass document not found")
    elif verification.outcome is not Outcome.OK:
        out.update(verification_status="NOT_CHECKED",
                   verification_notes=f"UGPass not checked ({verification.outcome.value.lower().replace('_', ' ')})")
    else:
        d = verification.data
        signatures, eseals = int(d.get("signatures") or 0), int(d.get("eseals") or 0)
        out.update(signatures_count=signatures, eseals_count=eseals, document_sha256=d.get("current_sha256"))
        problems = [str(p) for p in (d.get("problems") or [])]
        if not d.get("valid", False) or problems:
            out.update(verification_status="INVALID", verification_notes="; ".join(problems) or "UGPass reports the document is not valid")
        elif signatures < expected_signatures or eseals < expected_eseals:
            out.update(verification_status="INCOMPLETE",
                       verification_notes=f"{signatures} of {expected_signatures} signatures and {eseals} of {expected_eseals} e-Seals so far")
        else:
            out.update(verification_status="VALID", verification_notes=None)
    out["mou_status"] = mou_status(out["verification_status"], out.get("signatures_count") or 0,
                                   out.get("eseals_count") or 0, previous_status)
    return out
