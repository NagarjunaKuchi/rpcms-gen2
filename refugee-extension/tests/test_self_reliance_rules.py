from datetime import date

import pytest

from openg2p_registry_refugee_extension.rules import reporting as rep
from openg2p_registry_refugee_extension.rules import self_reliance as sr

FULL = {"food_source": "OWN_PRODUCTION_AND_ASSISTANCE", "has_income": "YES", "children_in_school": "THREE_OR_MORE",
        "savings_group_member": "YES"}
TODAY = date(2026, 11, 16)


def test_weights_add_up_to_100():
    assert sr.MAX_INDEX == 100


def test_index_extremes_and_a_mixed_case():
    assert sr.compute_index({"food_source": "ASSISTANCE_ONLY", "has_income": "NO", "children_in_school": "NONE",
                             "savings_group_member": "NO"}) == 0
    assert sr.compute_index({"food_source": "MARKET_INCOME", "has_income": "YES", "children_in_school": "THREE_OR_MORE",
                             "savings_group_member": "YES"}) == 100
    assert sr.compute_index(FULL) == 20 + 30 + 15 + 15


@pytest.mark.parametrize("missing", list(sr.SCALES))
def test_unfinished_survey_is_not_scored_as_zero(missing):
    record = {**FULL, missing: None}
    assert sr.compute_index(record) is None
    assert sr.compute_index({k: v for k, v in FULL.items() if k != missing}) is None


def test_unknown_answer_is_not_scored():
    assert sr.compute_index({**FULL, "food_source": "SOMETHING"}) is None


def test_answer_errors():
    assert sr.answer_error(FULL, TODAY) is None
    assert "food_source" in sr.answer_error({"food_source": "BARTER"}, TODAY)
    assert "round_label" in sr.answer_error({"round_label": "Round 2"}, TODAY)
    assert sr.answer_error({"round_label": "2026-R2"}, TODAY) is None
    assert "must not be empty" in sr.answer_error({"round_label": " "}, TODAY)
    assert "no income" in sr.answer_error({"has_income": "NO", "income_source": "vegetable sales"}, TODAY)
    assert sr.answer_error({"has_income": "YES", "income_source": "vegetable sales"}, TODAY) is None
    assert "future" in sr.answer_error({"survey_date": date(2026, 12, 1)}, TODAY)
    assert sr.answer_error({"survey_date": TODAY}, TODAY) is None


def test_partial_update_checks_only_what_it_carries():
    assert sr.answer_error({"zone": "Zone 3"}, TODAY) is None


def test_survey_counts_become_indicators_only_when_surveys_exist():
    out = rep.build_indicators("2026-Q3", {"households_surveyed": 40, "households_with_income": 19})
    assert [(i["code"], i["value"]) for i in out["indicators"]] == [
        ("RPCMS-HOUSEHOLDS-SURVEYED", 40), ("RPCMS-HOUSEHOLDS-WITH-INCOME", 19)]
    assert rep.build_indicators("2026-Q3", {"households_surveyed": None, "households_with_income": None})["indicators"] == []
