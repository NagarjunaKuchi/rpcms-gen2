import json
import urllib.parse
import urllib.request
import uuid

import pytest

from conftest import MOCKS, wait_for

from helpers.config import REGISTER_INDIVIDUAL
from helpers.flows import intake as _intake
from helpers.flows.awe import approve_two_stage_awe
from helpers.flows.intake import provision_household, provision_record, save_intake_section
from helpers.flows.register import search_register_by_text
from helpers.http import StaffApiError
from helpers.profiles import INDIVIDUAL

PARTNER = "a0000000-0000-4000-8000-000000000003"
PARTNER_FORM = "c1000000-0000-4000-8000-000000000003"
AE = "b0000000-0000-4000-8000-0000000000a0"
IR = "b0000000-0000-4000-8000-0000000000a1"
KNOWN_PROGRES_ID = "UGA-00423318"  # active in the mock ProGres


def sms_to(number):
    with urllib.request.urlopen(f"{MOCKS}/sms/v1/messages?to={urllib.parse.quote(number)}", timeout=10) as r:
        return json.load(r)["messages"]


def register_partner(staff, cfg, name, ursb, permit):
    row = {"organisation_name": name, "partner_code": "T" + uuid.uuid4().hex[:5].upper(), "ursb_registration_no": ursb,
           "ngo_permit_no": permit, "sector": "Food security", "edit_action": "ADD"}
    body = save_intake_section(staff, submission_id=None, section_id="pt_organisation", section_payload=[row],
                               section_register_id=PARTNER, form_id=PARTNER_FORM, register_id=PARTNER)
    sub = staff.payload(body)["submission_id"]
    staff.post_json("/intake-form-data/finalize_intake_form_submission", {"submission_id": sub})
    approve_two_stage_awe(cfg, artifact_type="registry.intake_form", artifact_id=sub, search_text=name)
    return row["partner_code"]


def partner_record(staff, code):
    def get():
        hits = search_register_by_text(staff, code, register_id=PARTNER)
        if not hits:
            return None
        rec = staff.payload(staff.post_json("/register-data/get_subject_record", {
            "subject_register_id": PARTNER, "subject_record_id": hits[0]["internal_record_id"]}))
        rec = rec.get("record", rec)
        return rec if rec.get("compliance_status") else None  # the worker fills the check after registration
    return wait_for(get, what=f"partner {code} compliance check")


def person(staff, cfg, phone):
    """An approved Individual created through the normal intake flow, with the given phone (or none)."""
    household = provision_household(staff, cfg).internal_record_id
    orig = _intake.build_individual_section_payload

    def build(section_id, hh, name):
        payload = orig(section_id, hh, name)
        if section_id == "in_contact_details":
            payload["phone_numbers"] = [{"number": phone}] if phone else []
        return payload

    _intake.build_individual_section_payload = build
    try:
        return provision_record(staff, cfg, INDIVIDUAL, household_id=household).internal_record_id
    finally:
        _intake.build_individual_section_payload = orig


def change(staff, cfg, parent, tab, section, section_register, row, action, find):
    """Create a change request and approve it (alex.carter then nina.patel). Returns "APPROVED" or the rejection text.

    Approval returns before the worker has applied the change, and the registry allows one pending request per
    record and section, so creation is retried while the previous one is still being applied."""
    payload = {
        "register_id": REGISTER_INDIVIDUAL, "tab_id": tab, "section_id": section, "section_register_id": section_register,
        "internal_record_id": parent, "change_payload": [dict(row, edit_action=action, link_internal_record_id=parent)]}

    def create():
        try:
            return staff.post_json("/change-requests/create_change_request", payload)
        except StaffApiError as err:
            if "pending change request already exists" in str(err):
                return None
            return err  # refused at creation (e.g. a duplicate): reported to the caller as the reason

    body = wait_for(create, timeout=90, every=2, what="previous change to be applied")
    if isinstance(body, StaffApiError):
        return str(body)
    cr = staff.payload(body)["change_request_id"]
    try:
        approve_two_stage_awe(cfg, artifact_type="registry.change_request", artifact_id=cr, search_text=find)
        return "APPROVED"
    except StaffApiError as err:
        staff.post_json("/change-requests/reject_change_request", {"change_request_id": cr, "rejection_reason": str(err)[:480]})
        return str(err)


def rows(staff, parent, tab, section_register):
    groups = staff.payload(staff.post_json("/register-data/get_tab_records", {
        "subject_register_id": REGISTER_INDIVIDUAL, "subject_record_id": parent, "tab_id": tab}))
    return [r for g in groups if g.get("section_register_id") == section_register for r in g.get("records", [])]


# ---------------------------------------------------------------- Partner ------------------------------------

def test_partner_in_good_standing_is_compliant(staff, cfg):
    rec = partner_record(staff, register_partner(staff, cfg, "Nile Hope Uganda", "80020003318742", "NGO/PMT/2025/4418"))
    assert rec["compliance_status"] == "COMPLIANT", rec.get("compliance_notes")
    assert rec["ursb_status"] == "ACTIVE" and rec["ngo_permit_status"] == "VALID"
    assert rec["permit_valid_to"] and rec["permit_renewal_alert_date"]
    assert rec["permit_renewal_alert_date"] < rec["permit_valid_to"]


def test_partner_with_unknown_numbers_is_non_compliant(staff, cfg):
    rec = partner_record(staff, register_partner(staff, cfg, "Unregistered Relief Org", "11111111111111", "NGO/PMT/0000/0000"))
    assert rec["compliance_status"] == "NON_COMPLIANT"
    assert rec["ursb_status"] == "NOT_FOUND" and rec["ngo_permit_status"] == "NOT_FOUND"
    assert "not found" in rec["compliance_notes"]


def test_partner_without_required_numbers_is_rejected(staff, cfg):
    with pytest.raises(StaffApiError):
        register_partner(staff, cfg, "No Numbers Org", "", "")


# ---------------------------------------------------------------- Assistance ---------------------------------

def test_assistance_records_progres_confirmation_and_blocks_duplicates(staff, cfg):
    parent = person(staff, cfg, "+256700000111")
    cycle = "2026-" + uuid.uuid4().hex[:4]
    base = dict(partner_code="NHU", partner_name="Nile Hope Uganda", assistance_type="CASH_FOR_FOOD", distribution_cycle=cycle)
    assert change(staff, cfg, parent, "individual_assistance_tab", "in_table_assistance_events", AE,
                  dict(base, registrant_progres_id=KNOWN_PROGRES_ID), "ADD", KNOWN_PROGRES_ID) == "APPROVED"
    unknown = "UGA-9" + uuid.uuid4().hex[:6]
    assert change(staff, cfg, parent, "individual_assistance_tab", "in_table_assistance_events", AE,
                  dict(base, registrant_progres_id=unknown), "ADD", unknown) == "APPROVED"
    found = wait_for(lambda: len(rows(staff, parent, "individual_assistance_tab", AE)) == 2
                     and rows(staff, parent, "individual_assistance_tab", AE), what="two assistance rows")
    by_id = {r["registrant_progres_id"]: r for r in found}
    assert by_id[KNOWN_PROGRES_ID]["progres_authenticated"] is True
    assert by_id[unknown]["progres_authenticated"] is False
    dup = change(staff, cfg, parent, "individual_assistance_tab", "in_table_assistance_events", AE,
                 dict(base, registrant_progres_id=KNOWN_PROGRES_ID), "ADD", KNOWN_PROGRES_ID)
    assert "Duplicate assistance" in dup


# ---------------------------------------------------------------- ID renewal ---------------------------------

def renewal_row(**kw):
    return dict(request_ref="REQ-" + uuid.uuid4().hex[:8].upper(), registrant_progres_id=KNOWN_PROGRES_ID,
                service_type="ID_RENEWAL", card_expiry="2026-10-31", **kw)


def test_renewal_sms_goes_to_the_persons_phone_and_is_recorded(staff, cfg):
    phone = "+25670" + str(uuid.uuid4().int)[:7]
    parent = person(staff, cfg, phone)
    row = renewal_row(status="EXPIRY_FLAGGED")
    ref = row["request_ref"]
    t = ("individual_id_renewal_tab", "in_table_id_renewals", IR)
    assert change(staff, cfg, parent, *t, row, "ADD", ref) == "APPROVED"
    rid = wait_for(lambda: (r := rows(staff, parent, t[0], IR)) and r[0]["internal_record_id"], what="renewal row")
    assert change(staff, cfg, parent, *t, dict(internal_record_id=rid, status="APPOINTMENT_BOOKED", appointment_date="2026-11-20",
                                              appointment_time="10:00", appointment_location="OPM office Bidibidi"), "UPDATE", ref) == "APPROVED"
    assert change(staff, cfg, parent, *t, dict(internal_record_id=rid, status="CLOSED_RENEWED", closed_on="2026-11-20",
                                              closed_by="OPM registration officer"), "UPDATE", ref) == "APPROVED"
    sent = wait_for(lambda: len(sms_to(phone)) >= 3 and sms_to(phone), what="3 SMS at the mock gateway")
    texts = [m["text"] for m in sent]
    assert any("expires on 2026-10-31" in x for x in texts)
    assert any("2026-11-20 10:00" in x and "OPM office Bidibidi" in x for x in texts)
    assert any("complete" in x for x in texts)
    final = wait_for(lambda: (r := rows(staff, parent, t[0], IR)) and r[0]["status"] == "CLOSED_RENEWED" and r[0], what="closed row")
    assert final["notification_status"] == "SENT" and final["notified_on"]
    assert sms_to(KNOWN_PROGRES_ID) == []  # nothing is sent to a ProGres ID any more


def test_renewal_without_phone_records_no_phone_and_sends_nothing(staff, cfg):
    parent = person(staff, cfg, None)
    row = renewal_row(status="EXPIRY_FLAGGED")
    assert change(staff, cfg, parent, "individual_id_renewal_tab", "in_table_id_renewals", IR, row, "ADD", row["request_ref"]) == "APPROVED"
    stored = wait_for(lambda: (r := rows(staff, parent, "individual_id_renewal_tab", IR)) and r[0].get("notification_status") and r[0],
                      what="notification status")
    assert stored["notification_status"] == "NO_PHONE"


def test_assistance_update_is_not_its_own_duplicate_but_cannot_move_into_one(staff, cfg):
    parent = person(staff, cfg, "+256700000222")
    tab, sec = "individual_assistance_tab", "in_table_assistance_events"
    c1, c2 = "2026-" + uuid.uuid4().hex[:4], "2026-" + uuid.uuid4().hex[:4]
    base = dict(partner_code="NHU", partner_name="Nile Hope Uganda", assistance_type="FOOD", registrant_progres_id=KNOWN_PROGRES_ID)
    for cycle in (c1, c2):
        assert change(staff, cfg, parent, tab, sec, AE, dict(base, distribution_cycle=cycle), "ADD", cycle) == "APPROVED"
    by_cycle = {r["distribution_cycle"]: r for r in wait_for(
        lambda: len(rows(staff, parent, tab, AE)) == 2 and rows(staff, parent, tab, AE), what="two rows")}
    # editing an unrelated field of the row is fine: it is not a duplicate of itself
    ok = change(staff, cfg, parent, tab, sec, AE, dict(internal_record_id=by_cycle[c1]["internal_record_id"], amount=5000), "UPDATE", c1)
    assert ok == "APPROVED"
    # a partial update that only changes the cycle to one already recorded must be refused
    bad = change(staff, cfg, parent, tab, sec, AE, dict(internal_record_id=by_cycle[c1]["internal_record_id"], distribution_cycle=c2), "UPDATE", c1)
    assert "Duplicate assistance" in bad
