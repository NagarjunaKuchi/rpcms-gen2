from datetime import date

import pytest

from openg2p_registry_refugee_extension.rules import reporting as r


def test_parse_quarter_bounds():
    assert r.parse_quarter("2026-Q3") == (date(2026, 7, 1), date(2026, 10, 1))
    assert r.parse_quarter("2026-q4") == (date(2026, 10, 1), date(2027, 1, 1))
    assert r.parse_quarter(" 2026-Q1 ") == (date(2026, 1, 1), date(2026, 4, 1))


@pytest.mark.parametrize("bad", ["", None, "2026-Q5", "2026Q3", "26-Q3", "2026-Q0", "Q3"])
def test_parse_quarter_rejects(bad):
    with pytest.raises(ValueError):
        r.parse_quarter(bad)


def test_quarter_of():
    assert r.quarter_of(date(2026, 7, 1)) == "2026-Q3"
    assert r.quarter_of(date(2026, 12, 31)) == "2026-Q4"
    assert r.quarter_of(date(2026, 3, 31)) == "2026-Q1"


def test_expenditure_splits_unmatched():
    payload, unmatched = r.build_expenditure("2026-Q3", [
        {"project_code": "P1", "amp_record_no": "AMP-1", "currency": "UGX", "amount": 1000.456, "events": 3},
        {"project_code": "P2", "amp_record_no": "", "currency": "UGX", "amount": 50, "events": 1},
        {"project_code": "P3", "amp_record_no": "AMP-3", "currency": None, "amount": 5, "events": 1},
    ])
    assert payload == {"quarter": "2026-Q3", "items": [
        {"amp_record": "AMP-1", "project_code": "P1", "currency": "UGX", "amount": 1000.46, "events": 3}]}
    assert [u["project_code"] for u in unmatched] == ["P2", "P3"]
    assert unmatched[0]["reason"] == "no AMP record number" and unmatched[1]["reason"] == "no currency"


def test_expenditure_empty():
    assert r.build_expenditure("2026-Q3", []) == ({"quarter": "2026-Q3", "items": []}, [])


def test_indicators_leave_out_what_is_unknown():
    out = r.build_indicators("2026-Q3", {"partners_compliant": 2, "events_authenticated": 0, "persons_reached": None})
    assert [i["code"] for i in out["indicators"]] == ["RPCMS-PARTNERS-COMPLIANT", "RPCMS-EVENTS-AUTHENTICATED"]
    assert out["indicators"][1]["value"] == 0  # a real zero is kept


def test_digest_is_stable_and_order_independent():
    a = {"x": 1, "y": [1, 2]}
    assert r.payload_digest(a) == r.payload_digest({"y": [1, 2], "x": 1})
    assert r.payload_digest(a) != r.payload_digest({"x": 2, "y": [1, 2]})
