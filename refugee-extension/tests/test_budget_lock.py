from openg2p_registry_refugee_extension.rules.budget_lock import REFUSAL_PREFIX, changed_budget_fields, refusal

STORED = dict(project_value=1200000000, currency="UGX", target_households=1800, household_rate=150000)


def test_changing_a_budget_figure_is_caught():
    assert changed_budget_fields(STORED, {"project_value": 1300000000}) == ["project_value"]
    assert changed_budget_fields(STORED, {"currency": "USD", "household_rate": 40}) == ["currency", "household_rate"]


def test_resending_the_same_values_is_not_a_change():
    assert changed_budget_fields(STORED, {"project_value": "1,200,000,000.00", "currency": " UGX ",
                                          "target_households": "1800", "household_rate": 150000.0}) == []


def test_fields_outside_the_budget_are_free():
    assert changed_budget_fields(STORED, {"project_name": "New name", "end_date": "2027-12-31", "area": "Zone 5"}) == []


def test_clearing_a_budget_field_is_a_change():
    assert changed_budget_fields(STORED, {"project_value": ""}) == ["project_value"]
    assert changed_budget_fields(STORED, {"target_households": None}) == ["target_households"]


def test_setting_a_value_that_was_empty_is_a_change():
    assert changed_budget_fields({}, {"project_value": 5}) == ["project_value"]


def test_refusal_message():
    msg = refusal("NHU-CFF-2026", ["project_value"])
    assert msg.startswith(REFUSAL_PREFIX) and "NHU-CFF-2026" in msg and "project_value" in msg
    assert refusal("NHU-CFF-2026", []) is None
