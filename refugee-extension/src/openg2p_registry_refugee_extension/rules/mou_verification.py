"""MoU rule: turn a UGPass verification answer into the status stored on the MoU row.
Signing itself happens in UGPass (each signatory confirms in their own app); RPCMS only checks the result.
Pure function (no I/O, no platform imports)."""
from datetime import date

from ..integrations import Outcome, Response


def evaluate_mou(verification: Response, expected_signatures: int, expected_eseals: int, today: date) -> dict:
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
    return out
