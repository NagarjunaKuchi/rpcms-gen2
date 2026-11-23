from openg2p_registry_refugee_extension.rules.assistance_duplicates import household_message, key_of, with_referral
from openg2p_registry_refugee_extension.rules.referral_review import CONFIRMED, OPEN, RELEASED, decide

KEY = key_of(dict(registrant_progres_id="UGA-1", assistance_type="FOOD", distribution_cycle="2026-03"))


def test_household_message_names_the_member_and_keeps_the_duplicate_prefix():
    msg = household_message(KEY, "UGA-2")
    assert msg.startswith("Duplicate assistance") and "UGA-2" in msg and "UGA-1" in msg and "FOOD" in msg


def test_referral_case_is_named_in_the_refusal():
    assert with_referral("Duplicate assistance: x", "ab12").endswith("referred for review as case ab12")
    assert with_referral("Duplicate assistance: x", None) == "Duplicate assistance: x"


def test_open_case_can_be_confirmed_with_or_without_a_note():
    assert decide(OPEN, "confirm", None) == (CONFIRMED, None)
    assert decide(OPEN, "CONFIRM", "same household, same day") == (CONFIRMED, None)


def test_releasing_needs_a_reason():
    assert decide(OPEN, "RELEASE", "second partner delivered a different item") == (RELEASED, None)
    status, why = decide(OPEN, "RELEASE", "  ")
    assert status is None and "note is required" in why


def test_a_case_is_decided_once():
    for done in (CONFIRMED, RELEASED):
        status, why = decide(done, "RELEASE", "changed my mind")
        assert status is None and "already decided" in why


def test_unknown_decision_is_refused():
    status, why = decide(OPEN, "maybe", "x")
    assert status is None and "decision must be one of" in why
