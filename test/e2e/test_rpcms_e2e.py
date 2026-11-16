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


def change(staff, cfg, parent, tab, section, section_register, row, action, find, register=REGISTER_INDIVIDUAL):
    """Create a change request and approve it (alex.carter then nina.patel). Returns "APPROVED" or the rejection text.

    Approval returns before the worker has applied the change, and the registry allows one pending request per
    record and section, so creation is retried while the previous one is still being applied."""
    payload = {
        "register_id": register, "tab_id": tab, "section_id": section, "section_register_id": section_register,
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


def rows(staff, parent, tab, section_register, register=REGISTER_INDIVIDUAL):
    groups = staff.payload(staff.post_json("/register-data/get_tab_records", {
        "subject_register_id": register, "subject_record_id": parent, "tab_id": tab}))
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


# ---------------------------------------------------------------- Project, MoU, service points -----------------

PROJECT = "a0000000-0000-4000-8000-000000000004"
PROJECT_FORM = "c1000000-0000-4000-8000-000000000004"
MOU = "b0000000-0000-4000-8000-0000000000b0"
SP = "b0000000-0000-4000-8000-0000000000b1"
AMP_RECORD = "AMP-UG-2026-00731"  # in the mock AMP: commitment 1,200,000,000 UGX, 300,000,000 disbursed


def mock_post(path, body):
    req = urllib.request.Request(MOCKS + path, json.dumps(body).encode(), {"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)


def register_project(staff, cfg, **over):
    code = "PRJ-" + uuid.uuid4().hex[:8].upper()
    row = dict(project_code=code, project_name="Cash-for-Food " + code, partner_code="P" + uuid.uuid4().hex[:4].upper(),
               partner_name="Nile Hope Uganda", intervention="CASH_FOR_FOOD", area="Bidibidi Zones 3-4",
               start_date="2026-03-01", end_date="2027-02-28", target_households=1800, household_rate=150000,
               project_value=1200000000, currency="UGX", amp_record_no=AMP_RECORD, edit_action="ADD")
    row.update(over)
    body = save_intake_section(staff, submission_id=None, section_id="pj_project", section_payload=[row],
                               section_register_id=PROJECT, form_id=PROJECT_FORM, register_id=PROJECT)
    sub = staff.payload(body)["submission_id"]
    staff.post_json("/intake-form-data/finalize_intake_form_submission", {"submission_id": sub})
    approve_two_stage_awe(cfg, artifact_type="registry.intake_form", artifact_id=sub, search_text=code)

    def get():
        hits = search_register_by_text(staff, code, register_id=PROJECT)
        if not hits:
            return None
        rec = staff.payload(staff.post_json("/register-data/get_subject_record", {
            "subject_register_id": PROJECT, "subject_record_id": hits[0]["internal_record_id"]}))
        rec = rec.get("record", rec)
        return (hits[0]["internal_record_id"], rec) if rec.get("amp_status") else None
    return wait_for(get, what=f"project {code} AMP check")


def test_project_funding_confirmed_against_amp(staff, cfg):
    _, rec = register_project(staff, cfg)
    assert rec["amp_status"] == "CONFIRMED", rec.get("amp_notes")
    assert rec["amp_donor"] == "West Nile Resilience Fund"
    assert float(rec["amp_commitment"]) == 1200000000 and float(rec["amp_disbursed"]) == 300000000


def test_project_funding_mismatch_and_unknown_record(staff, cfg):
    _, rec = register_project(staff, cfg, project_value=1000000)
    assert rec["amp_status"] == "MISMATCH" and "differs" in rec["amp_notes"]
    _, rec = register_project(staff, cfg, amp_record_no="AMP-UG-0000-00000")
    assert rec["amp_status"] == "NOT_FOUND"
    _, rec = register_project(staff, cfg, amp_record_no="")
    assert rec["amp_status"] == "NOT_CHECKED"


def signed_mou(signatures, eseals):
    """What the signatories' UGPass apps do: create the document, each signer confirms, organisations seal."""
    doc = mock_post("/ugpass/v1/documents", {"text": "MoU OPM/DoR/NHU/2026/" + uuid.uuid4().hex[:6]})["doc_id"]
    for i in range(signatures):
        req = mock_post("/ugpass/v1/signing-requests", {"doc_id": doc, "signer": f"Signatory {i + 1}", "org": "OPM"})["request_id"]
        mock_post(f"/ugpass/v1/signing-requests/{req}/confirm", {"biometric": "FACE"})
    for i in range(eseals):
        mock_post("/ugpass/v1/eseal", {"doc_id": doc, "org": f"Org {i + 1}"})
    return doc


def test_mou_is_verified_then_flagged_when_altered(staff, cfg):
    project, _ = register_project(staff, cfg)
    tab, sec = "project_mou_tab", "pj_table_mou"
    doc = signed_mou(3, 2)
    ref = "OPM/DoR/NHU/" + uuid.uuid4().hex[:6]
    assert change(staff, cfg, project, tab, sec, MOU, dict(mou_number=ref, ugpass_document_id=doc), "ADD", ref, register=PROJECT) == "APPROVED"
    row = wait_for(lambda: next((r for r in rows(staff, project, tab, MOU, PROJECT) if r.get("verification_status")), None), what="MoU verification")
    assert row["verification_status"] == "VALID" and row["signatures_count"] == 3 and row["eseals_count"] == 2
    assert row["document_sha256"] and row["verified_on"]
    # someone edits the signed document: re-checking (an edit of the row) must now report it
    mock_post(f"/ugpass/v1/documents/{doc}/tamper", {"text": "changed amount"})
    assert change(staff, cfg, project, tab, sec, MOU, dict(internal_record_id=row["internal_record_id"], remarks="re-check"), "UPDATE", ref, register=PROJECT) == "APPROVED"
    bad = wait_for(lambda: next((r for r in rows(staff, project, tab, MOU, PROJECT) if r.get("verification_status") == "INVALID"), None), what="INVALID after tamper")
    assert "changed after signing" in bad["verification_notes"]


def test_mou_with_missing_signatures_is_incomplete_and_unknown_document_not_found(staff, cfg):
    project, _ = register_project(staff, cfg)
    tab, sec = "project_mou_tab", "pj_table_mou"
    a, b = "MOU-A-" + uuid.uuid4().hex[:6], "MOU-B-" + uuid.uuid4().hex[:6]
    assert change(staff, cfg, project, tab, sec, MOU, dict(mou_number=a, ugpass_document_id=signed_mou(1, 0)), "ADD", a, register=PROJECT) == "APPROVED"
    assert change(staff, cfg, project, tab, sec, MOU, dict(mou_number=b, ugpass_document_id="DOC-DOES-NOT-EXIST"), "ADD", b, register=PROJECT) == "APPROVED"
    got = wait_for(lambda: (r := {x["mou_number"]: x for x in rows(staff, project, tab, MOU, PROJECT)}) and len(r) == 2
                   and all(x.get("verification_status") for x in r.values()) and r, what="both MoUs checked")
    assert got[a]["verification_status"] == "INCOMPLETE" and "1 of 3 signatures" in got[a]["verification_notes"]
    assert got[b]["verification_status"] == "NOT_FOUND"


def test_service_point_overlap_between_partners_is_flagged_and_clears_when_moved(staff, cfg):
    import random
    lat, lon = round(random.uniform(-60, 60), 4), round(random.uniform(-150, 150), 4)  # a unique spot per run
    tab, sec = "project_service_points_tab", "pj_table_service_points"
    first, _ = register_project(staff, cfg, partner_code="NHU" + uuid.uuid4().hex[:3].upper())
    second, _ = register_project(staff, cfg, partner_code="WNRP" + uuid.uuid4().hex[:3].upper())
    name_a, name_b = "Point A " + uuid.uuid4().hex[:5], "Point B " + uuid.uuid4().hex[:5]
    assert change(staff, cfg, first, tab, sec, SP, dict(point_name=name_a, zone="Zone 4", service_type="CASH_TRANSFER", status="ACTIVE",
                                                       latitude=lat, longitude=lon), "ADD", name_a, register=PROJECT) == "APPROVED"
    a = wait_for(lambda: next((r for r in rows(staff, first, tab, SP, PROJECT) if r.get("overlap_status")), None), what="first point checked")
    assert a["overlap_status"] == "NONE"
    # 0.0013 degrees of latitude is about 145 m: inside the 500 m default radius
    assert change(staff, cfg, second, tab, sec, SP, dict(point_name=name_b, zone="Zone 4", service_type="CASH_TRANSFER", status="ACTIVE",
                                                        latitude=round(lat + 0.0013, 4), longitude=lon), "ADD", name_b, register=PROJECT) == "APPROVED"
    b = wait_for(lambda: next((r for r in rows(staff, second, tab, SP, PROJECT) if r.get("overlap_status")), None), what="second point checked")
    assert b["overlap_status"] == "OVERLAP" and name_a in b["overlap_with"]
    # moved ~1.1 km away: no longer overlapping
    assert change(staff, cfg, second, tab, sec, SP, dict(internal_record_id=b["internal_record_id"], latitude=round(lat + 0.01, 4)), "UPDATE", name_b, register=PROJECT) == "APPROVED"
    moved = wait_for(lambda: next((r for r in rows(staff, second, tab, SP, PROJECT) if r.get("overlap_status") == "NONE"), None), what="overlap cleared")
    assert moved["overlap_with"] in (None, "")


def test_service_point_with_half_a_coordinate_is_refused(staff, cfg):
    project, _ = register_project(staff, cfg)
    r = change(staff, cfg, project, "project_service_points_tab", "pj_table_service_points", SP,
               dict(point_name="Bad", service_type="CASH_TRANSFER", latitude=3.4), "ADD", "Bad", register=PROJECT)
    assert "latitude and longitude must be entered together" in r
