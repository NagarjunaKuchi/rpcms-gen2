from openg2p_registry_refugee_extension.rules.assistance_duplicates import first_duplicate_within, key_of, message

A = dict(registrant_progres_id="UGA-1", assistance_type="FOOD", distribution_cycle="2026-03")


def test_key_needs_all_three_parts():
    assert key_of(A) == ("UGA-1", "FOOD", "2026-03")
    assert key_of({**A, "distribution_cycle": " "}) is None
    assert key_of({"assistance_type": "FOOD"}) is None


def test_key_ignores_surrounding_whitespace():
    assert key_of({**A, "registrant_progres_id": "  UGA-1 "}) == key_of(A)


def test_duplicate_inside_one_request():
    assert first_duplicate_within([A, {**A, "partner_code": "X"}]) == key_of(A)


def test_different_type_or_cycle_or_person_is_not_a_duplicate():
    rows = [A, {**A, "assistance_type": "CASH_FOR_FOOD"}, {**A, "distribution_cycle": "2026-04"}, {**A, "registrant_progres_id": "UGA-2"}]
    assert first_duplicate_within(rows) is None


def test_incomplete_rows_are_ignored():
    assert first_duplicate_within([{"amount": 5}, {"amount": 5}]) is None


def test_message_names_the_conflict():
    assert message(key_of(A)) == "Duplicate assistance: registrant UGA-1 already received FOOD in cycle 2026-03"
