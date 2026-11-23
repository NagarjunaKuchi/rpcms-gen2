from openg2p_registry_refugee_extension.rules.report_approval import check

APPROVAL = {"payload_sha256": "abc", "approved_by": "nina"}


def test_matching_approval_by_someone_else_may_send():
    assert check(APPROVAL, "abc", "alex", True) is None


def test_no_approval_blocks():
    assert "have not been approved" in check(None, "abc", "alex", True)


def test_changed_figures_need_approving_again():
    assert "changed after they were approved" in check(APPROVAL, "def", "alex", True)


def test_approver_cannot_send_when_the_setting_asks_for_a_different_person():
    assert "cannot also send" in check(APPROVAL, "abc", "nina", True)


def test_approver_may_send_when_the_setting_allows_it():
    assert check(APPROVAL, "abc", "nina", False) is None
