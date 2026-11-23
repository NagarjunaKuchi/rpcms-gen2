"""Approval of a quarterly report's figures before it is sent. Pure function (no I/O, no platform imports).

An approver reviews the preview and approves it; the approval records a fingerprint of those exact figures. Sending
needs an unused approval that matches the figures as they are now, so figures that change after approval need
approving again. Optionally the sender must be a different person from the approver."""


def check(approval: dict | None, digest: str, sender: str, approver_must_differ: bool) -> str | None:
    """None when the report may be sent; otherwise the reason it may not. `approval` is the latest unused approval for
    this system and quarter (keys: payload_sha256, approved_by), or None."""
    if approval is None:
        return "These figures have not been approved. Review the preview, then have an approver approve it."
    if approval["payload_sha256"] != digest:
        return "The figures changed after they were approved. Review the preview and approve them again."
    if approver_must_differ and approval["approved_by"] == sender:
        return "The person who approved the figures cannot also send them. Ask someone else to send."
    return None
