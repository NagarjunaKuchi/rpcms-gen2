from openg2p_registry_refugee_extension.rules.partner_gate import BLOCKING, REFUSAL_PREFIX, refusal


def test_non_compliant_partner_is_refused_with_the_reason():
    msg = refusal("NHU-1", "NON_COMPLIANT", "NGO permit expired on 2026-01-01", "a project")
    assert msg.startswith(REFUSAL_PREFIX)
    assert "a project" in msg and "NHU-1" in msg and "NGO permit expired on 2026-01-01" in msg


def test_refusal_without_notes_has_no_dangling_colon():
    assert refusal("NHU-1", "NON_COMPLIANT", None, "assistance").endswith("for partner NHU-1")


def test_compliant_partner_may_go_ahead():
    assert refusal("NHU-1", "COMPLIANT", None, "a project") is None


def test_not_checked_does_not_block():
    # An outage at URSB or the NGO Bureau concludes nothing, so it must not stop field work.
    assert refusal("NHU-1", "NOT_CHECKED", "URSB not checked (unavailable)", "a project") is None
    assert "NOT_CHECKED" not in BLOCKING


def test_unset_status_does_not_block():
    assert refusal("NHU-1", None, None, "a project") is None
