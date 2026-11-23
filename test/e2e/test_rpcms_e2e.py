import json
import os
import urllib.parse
import urllib.request
import uuid
from datetime import date, timedelta

import pytest

from conftest import MOCKS, wait_for

from helpers.config import REGISTER_HOUSEHOLD, REGISTER_INDIVIDUAL
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
SRV = "b0000000-0000-4000-8000-0000000000b2"
KNOWN_PROGRES_ID = "UGA-00423318"  # active in the mock ProGres


def sms_to(number):
    with urllib.request.urlopen(f"{MOCKS}/sms/v1/messages?to={urllib.parse.quote(number)}", timeout=10) as r:
        return json.load(r)["messages"]


def register_partner(staff, cfg, name, ursb, permit, district="Yumbe"):
    row = {"organisation_name": name, "partner_code": "T" + uuid.uuid4().hex[:5].upper(), "ursb_registration_no": ursb,
           "ngo_permit_no": permit, "sector": "Food security", "operating_district": district, "edit_action": "ADD"}
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
    assert rec["permit_area_status"] == "COVERED"  # the mock permit covers Yumbe
    assert rec["permit_valid_to"] and rec["permit_renewal_alert_date"]
    assert rec["permit_renewal_alert_date"] < rec["permit_valid_to"]


def test_partner_whose_permit_does_not_cover_the_district_is_non_compliant(staff, cfg):
    rec = partner_record(staff, register_partner(staff, cfg, "Nile Hope Uganda", "80020003318742", "NGO/PMT/2025/4418",
                                                 district="Kampala"))
    assert rec["compliance_status"] == "NON_COMPLIANT" and rec["permit_area_status"] == "NOT_COVERED"
    assert rec["ngo_permit_status"] == "VALID" and "does not cover Kampala" in rec["compliance_notes"]


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
    refused = change(staff, cfg, parent, "individual_assistance_tab", "in_table_assistance_events", AE,
                     dict(base, registrant_progres_id=unknown), "ADD", unknown)
    assert "ProGres did not confirm" in refused  # a ProGres "No" refuses the handover: nothing is recorded
    found = wait_for(lambda: rows(staff, parent, "individual_assistance_tab", AE), what="the confirmed assistance row")
    assert len(found) == 1, found
    by_id = {r["registrant_progres_id"]: r for r in found}
    assert by_id[KNOWN_PROGRES_ID]["progres_authenticated"] is True
    assert by_id[KNOWN_PROGRES_ID]["progres_auth_reference"].startswith("PGV4-AUTH-")  # from ProGres (mock), not typed
    assert by_id[KNOWN_PROGRES_ID]["progres_authenticated_at"]
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
    project, project_row = register_project(staff, cfg)
    tab, sec = "project_mou_tab", "pj_table_mou"
    doc = signed_mou(3, 2)
    ref = "OPM/DoR/NHU/" + uuid.uuid4().hex[:6]
    assert change(staff, cfg, project, tab, sec, MOU, dict(mou_number=ref, ugpass_document_id=doc), "ADD", ref, register=PROJECT) == "APPROVED"
    row = wait_for(lambda: next((r for r in rows(staff, project, tab, MOU, PROJECT) if r.get("verification_status")), None), what="MoU verification")
    assert row["verification_status"] == "VALID" and row["signatures_count"] == 3 and row["eseals_count"] == 2
    assert row["document_sha256"] and row["verified_on"] and row["mou_status"] == "SIGNED"
    # the signed MoU locks the budget; other project details stay editable
    locked = change(staff, cfg, project, "project_info_tab", "pj_project", PROJECT,
                    dict(internal_record_id=project, project_value=1300000000), "UPDATE", project_row["project_code"], register=PROJECT)
    assert "Project budget is locked" in locked, locked
    assert change(staff, cfg, project, "project_info_tab", "pj_project", PROJECT,
                  dict(internal_record_id=project, project_name="Renamed after signing"), "UPDATE", project_row["project_code"],
                  register=PROJECT) == "APPROVED"
    # someone edits the signed document: re-checking (an edit of the row) must now report it
    mock_post(f"/ugpass/v1/documents/{doc}/tamper", {"text": "changed amount"})
    assert change(staff, cfg, project, tab, sec, MOU, dict(internal_record_id=row["internal_record_id"], remarks="re-check"), "UPDATE", ref, register=PROJECT) == "APPROVED"
    bad = wait_for(lambda: next((r for r in rows(staff, project, tab, MOU, PROJECT) if r.get("verification_status") == "INVALID"), None), what="INVALID after tamper")
    assert "changed after signing" in bad["verification_notes"] and bad["mou_status"] == "AWAITING_SIGNATURES"  # no longer signed


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
    assert got[a]["mou_status"] == "AWAITING_SIGNATURES" and got[b]["mou_status"] == "DRAFT"


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


# ---------------------------------------------------------------- Reporting and dashboard -------------------

SUPERSET = os.environ.get("RPCMS_SUPERSET_BASE", "http://127.0.0.1:18088")


def today_quarter():
    d = date.today()
    return f"{d.year}-Q{(d.month - 1) // 3 + 1}"


def report_call(staff, method, path, **kw):
    """The /rpcms-reports endpoints use plain JSON, not the register envelope. Returns (status, json)."""
    staff._refresh_auth_header()
    r = staff._client.request(method, "/rpcms-reports" + path, **kw)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, {"raw": r.text}


def reason(body):
    """The platform wraps errors as {"errors": [{"code", "message"}]}."""
    return " ".join(e.get("message", "") for e in body.get("errors", [])) or str(body)


def add_event(staff, cfg, parent, **over):
    row = dict(registrant_progres_id=KNOWN_PROGRES_ID, partner_code="NHU", partner_name="Nile Hope Uganda",
               assistance_type="CASH_FOR_FOOD", distribution_cycle="C-" + uuid.uuid4().hex[:6],
               delivery_date=date.today().isoformat(), delivery_location="Zone 3", currency="UGX")
    row.update(over)
    result = change(staff, cfg, parent, "individual_assistance_tab", "in_table_assistance_events", AE, row, "ADD",
                    row["registrant_progres_id"])
    assert result == "APPROVED", result
    return row


def test_refused_duplicates_are_counted(staff, cfg):
    q = today_quarter()
    before = report_call(staff, "GET", "/summary", params={"quarter": q})[1]["duplicates_flagged"]
    parent = person(staff, cfg, "+256700000222")
    first = add_event(staff, cfg, parent)
    again = change(staff, cfg, parent, "individual_assistance_tab", "in_table_assistance_events", AE, first, "ADD",
                   first["registrant_progres_id"])
    assert "Duplicate assistance" in again
    after = report_call(staff, "GET", "/summary", params={"quarter": q})[1]["duplicates_flagged"]
    assert after >= before + 1


def test_quarterly_reports_preview_submit_and_do_not_double_count(staff, cfg):
    q = today_quarter()
    _, project = register_project(staff, cfg)
    parent = person(staff, cfg, "+256700000333")
    add_event(staff, cfg, parent, project_ref=project["project_code"], amount=150000)
    add_event(staff, cfg, parent, project_ref="NO-SUCH-PROJECT-" + uuid.uuid4().hex[:4], amount=5000)

    # Approval returns before the worker has applied the change, so wait until both events show in the preview.
    def ready():
        st, pv = report_call(staff, "GET", "/preview", params={"system": "AMP", "quarter": q})
        assert st == 200, pv
        has_project = any(i["project_code"] == project["project_code"] for i in pv["payload"]["items"])
        return pv if has_project and pv["not_sent"] else None

    preview = wait_for(ready, what="both events in the AMP preview")
    status = 200
    mine = [i for i in preview["payload"]["items"] if i["project_code"] == project["project_code"]]
    assert mine and mine[0]["amp_record"] == AMP_RECORD and mine[0]["amount"] >= 150000 and mine[0]["currency"] == "UGX"
    # An event for a project RPCMS does not know cannot be matched to an AMP record, so it is listed, not sent.
    assert any(u["reason"] == "no AMP record number" for u in preview["not_sent"])
    assert all(i["amp_record"] for i in preview["payload"]["items"])

    # forced, so the test also passes on a stack where an earlier run already sent this quarter
    status, sent = report_call(staff, "POST", "/submit", json={"system": "AMP", "quarter": q, "force": True})
    assert status == 200 and sent["status"] == "SENT" and sent["reference"].startswith("AMP-EXP-"), sent
    status, again = report_call(staff, "POST", "/submit", json={"system": "AMP", "quarter": q})
    assert status == 409 and "already accepted" in reason(again)
    status, forced = report_call(staff, "POST", "/submit", json={"system": "AMP", "quarter": q, "force": True})
    assert status == 200 and forced["status"] == "SENT"

    status, preview = report_call(staff, "GET", "/preview", params={"system": "NIMES", "quarter": q})
    codes = {i["code"]: i["value"] for i in preview["payload"]["indicators"]}
    assert codes["RPCMS-PERSONS-REACHED"] >= 1 and codes["RPCMS-EVENTS-AUTHENTICATED"] >= 1
    status, nimes = report_call(staff, "POST", "/submit", json={"system": "NIMES", "quarter": q, "force": True})
    assert status == 200 and nimes["status"] == "SENT" and nimes["reference"].startswith("NIMES-"), nimes

    status, history = report_call(staff, "GET", "/submissions")
    assert {(h["system"], h["status"]) for h in history} >= {("AMP", "SENT"), ("NIMES", "SENT")}


def test_report_requests_are_validated(staff, cfg):
    assert report_call(staff, "GET", "/summary", params={"quarter": "2026-Q9"})[0] == 400
    assert report_call(staff, "GET", "/preview", params={"system": "SAP", "quarter": today_quarter()})[0] == 400
    assert report_call(staff, "POST", "/submit", json={"system": "AMP", "quarter": "next-quarter"})[0] == 400
    # A quarter with no events has nothing to send, and says so rather than sending an empty report.
    status, body = report_call(staff, "POST", "/submit", json={"system": "AMP", "quarter": "2001-Q1"})
    assert status == 409 and "Nothing to send" in reason(body)


# ---------------------------------------------------------------- Self-reliance survey -------------------

def survey(staff, cfg, household, label, action="ADD", **row):
    return change(staff, cfg, household, "household_self_reliance_tab", "hh_table_self_reliance", SRV,
                  dict(round_label=label, **row), action, label, register=REGISTER_HOUSEHOLD)


def survey_rows(staff, household):
    return rows(staff, household, "household_self_reliance_tab", SRV, REGISTER_HOUSEHOLD)


def test_self_reliance_survey_is_scored_and_feeds_the_reports(staff, cfg):
    hh = provision_household(staff, cfg).internal_record_id
    today = date.today()
    first = dict(survey_date=(today - timedelta(days=1)).isoformat(), zone="Zone 3", food_source="ASSISTANCE_ONLY",
                 has_income="NO", children_in_school="ONE_TO_TWO", savings_group_member="NO")
    second = dict(survey_date=today.isoformat(), zone="Zone 3", food_source="OWN_PRODUCTION_AND_ASSISTANCE", has_income="YES",
                  income_source="vegetable sales", children_in_school="THREE_OR_MORE", savings_group_member="YES")
    assert survey(staff, cfg, hh, "2026-R1", **first) == "APPROVED"
    assert survey(staff, cfg, hh, "2026-R2", **second) == "APPROVED"

    def scored():
        found = {r["round_label"]: r for r in survey_rows(staff, hh)}
        return found if len(found) == 2 and all(r.get("self_reliance_index") is not None for r in found.values()) else None

    found = wait_for(scored, what="both rounds scored")
    assert found["2026-R1"]["self_reliance_index"] == 8 and found["2026-R2"]["self_reliance_index"] == 80
    assert found["2026-R2"]["index_version"] == "rpcms-v1" and found["2026-R2"]["index_computed_on"]

    # An unfinished survey is kept, but has no index: it is not scored as 0.
    unfinished = {k: v for k, v in second.items() if k != "savings_group_member"}
    assert survey(staff, cfg, hh, "2026-R3", **unfinished) == "APPROVED"
    r3 = wait_for(lambda: next((r for r in survey_rows(staff, hh) if r["round_label"] == "2026-R3"), None), what="third round stored")
    assert r3.get("self_reliance_index") in (None, "")

    # One survey per household and round, wrong answers and future dates are refused when entered.
    assert "already has a survey for round 2026-R2" in survey(staff, cfg, hh, "2026-R2", **second)
    assert "food_source must be one of" in survey(staff, cfg, hh, "2026-R4", **dict(second, food_source="BARTER"))
    assert "round_label must look like" in survey(staff, cfg, hh, "Round 4", **second)
    assert "future" in survey(staff, cfg, hh, "2026-R4", **dict(second, survey_date=(today + timedelta(days=3)).isoformat()))
    assert "no income" in survey(staff, cfg, hh, "2026-R4", **dict(second, has_income="NO"))

    # Changing an answer re-scores the survey.
    stored = next(r for r in survey_rows(staff, hh) if r["round_label"] == "2026-R1")
    assert survey(staff, cfg, hh, "2026-R1", action="UPDATE", internal_record_id=stored["internal_record_id"], savings_group_member="YES") == "APPROVED"
    wait_for(lambda: next((r for r in survey_rows(staff, hh) if r["round_label"] == "2026-R1" and r.get("self_reliance_index") == 23), None),
             what="first round re-scored")

    # The household is counted once in the quarter's indicators, by its latest survey (income: yes).
    status, preview = report_call(staff, "GET", "/preview", params={"system": "NIMES", "quarter": today_quarter()})
    codes = {i["code"]: i["value"] for i in preview["payload"]["indicators"]}
    assert status == 200 and codes["RPCMS-HOUSEHOLDS-SURVEYED"] >= 1 and codes["RPCMS-HOUSEHOLDS-WITH-INCOME"] >= 1


# ---------------------------------------------------------------- Field handover sync ---------------------

def sync_call(staff, batch_id, records):
    staff._refresh_auth_header()
    r = staff._client.post("/rpcms-handovers/sync", json={"batch_id": batch_id, "records": records})
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, {"raw": r.text}


def test_field_handovers_sync_once_with_gps_and_the_same_rules(staff, cfg):
    code = register_partner(staff, cfg, "Nile Hope Uganda", "80020003318742", "NGO/PMT/2025/4418")
    partner_record(staff, code)
    parent = person(staff, cfg, None)
    pid = "UGA-" + str(uuid.uuid4().int)[:8]
    assert change(staff, cfg, parent, "individual_info_tab", "in_identifier", REGISTER_INDIVIDUAL, dict(progres_id=pid),
                  "UPDATE", pid) == "APPROVED"
    cycle = "C-" + uuid.uuid4().hex[:6]
    base = dict(registrant_progres_id=pid, partner_code=code, assistance_type="CASH_FOR_FOOD", distribution_cycle=cycle,
                delivery_date=date.today().isoformat(), amount=150000, currency="UGX", delivery_location="Zone 3, Point A",
                officer="Emmanuel Taban", captured_at=date.today().isoformat() + "T08:42:00+00:00",
                gps_latitude=3.4719, gps_longitude=31.3547, gps_accuracy_m=8)
    good = dict(base, client_record_id="PH-" + uuid.uuid4().hex[:8])
    batch = "B-" + uuid.uuid4().hex[:6]

    # The person's ProGres ID is applied by the worker after approval, so wait until the registry knows it.
    def registered():
        status, body = sync_call(staff, batch, [good])
        assert status == 200, body
        only = body["results"][0]
        return body if "not registered" not in only.get("reason", "") else None

    first = wait_for(registered, what="registrant known by ProGres ID")
    # RPCMS knows the person, but ProGres (the mock) does not know this ID yet: the handover is refused, not recorded.
    assert first["results"][0]["status"] == "NOT_AUTHENTICATED", first
    assert rows(staff, parent, "individual_assistance_tab", AE) == []
    mock_post("/progres/v4/_mock/records", {"progres_id": pid, "active": True})
    status, body = sync_call(staff, batch, [good])  # the same record sent again once ProGres confirms the ID
    assert status == 200 and body["results"][0]["status"] == "SYNCED", body

    bad = [
        dict(base, client_record_id="PH-" + uuid.uuid4().hex[:8], registrant_progres_id="UGA-NOBODY-" + uuid.uuid4().hex[:5]),
        dict(base, client_record_id="PH-" + uuid.uuid4().hex[:8], distribution_cycle="C-X", gps_longitude=None),
        dict(base, client_record_id="PH-" + uuid.uuid4().hex[:8], distribution_cycle="C-Y", partner_code="NO-SUCH-PARTNER"),
        dict(base, client_record_id="PH-" + uuid.uuid4().hex[:8]),  # same person, type and cycle as `good`
    ]
    status, body = sync_call(staff, batch, [good] + bad)
    assert status == 200, body
    by = {r["client_record_id"]: r for r in body["results"]}
    assert by[good["client_record_id"]]["status"] == "ALREADY_SYNCED"  # sending again is safe
    assert "not registered" in by[bad[0]["client_record_id"]]["reason"] and by[bad[0]["client_record_id"]]["status"] == "REJECTED"
    assert "coordinates" in by[bad[1]["client_record_id"]]["reason"]
    assert "not an active partner" in by[bad[2]["client_record_id"]]["reason"]
    assert by[bad[3]["client_record_id"]]["status"] == "DUPLICATE" and "Duplicate assistance" in by[bad[3]["client_record_id"]]["reason"]

    # Exactly one event exists, carrying the GPS position, the channel and the batch, with no human approval needed.
    events = rows(staff, parent, "individual_assistance_tab", AE)
    assert len(events) == 1, events
    e = events[0]
    assert e["capture_channel"] == "OFFLINE_HANDOVER" and e["offline_batch_id"] == batch and e["client_record_id"] == good["client_record_id"]
    assert float(e["gps_latitude"]) == 3.4719 and float(e["gps_longitude"]) == 31.3547 and e["officer"] == "Emmanuel Taban"
    assert e["progres_authenticated"] is True  # set by the registry from ProGres, never taken from the phone
    assert e["progres_auth_reference"].startswith("PGV4-AUTH-")

    # The envelope itself is checked.
    assert sync_call(staff, "", [good])[0] == 400
    assert sync_call(staff, batch, [])[0] == 400


def test_dashboard_charts_show_the_registered_data():
    """The Superset dashboard, signed in as its admin, returns real rows from the reporting views."""
    import httpx

    with httpx.Client(base_url=SUPERSET, timeout=60) as c:
        tok = c.post("/api/v1/security/login", json={"username": "admin", "password": "admin", "provider": "db"}).json()["access_token"]
        h = {"Authorization": "Bearer " + tok}

        def chart_rows(name):
            q = "(filters:!((col:slice_name,opr:eq,value:'%s')))" % name
            cid = c.get("/api/v1/chart/", params={"q": q}, headers=h).json()["result"][0]["id"]
            res = c.get(f"/api/v1/chart/{cid}/data/", headers=h).json()["result"][0]
            assert not res.get("error"), res
            return res["data"]

        partners = chart_rows("Partner performance")
        assert any(r["compliance_status"] == "COMPLIANT" for r in partners)
        assert chart_rows("Partners compliance-verified")[0]["Partners compliance-verified"] >= 1
        assert chart_rows("Persons reached with assistance")[0]["Persons reached"] >= 1
        assert any(r.get("Persons reached") for r in chart_rows("Reach by delivery location"))
        assert any(r.get("currency") == "UGX" for r in chart_rows("Expenditure by project and quarter"))
        by_round = {r["round_label"]: r for r in chart_rows("Households with an income source by survey round")}
        assert by_round["2026-R2"]["Surveyed"] >= 1 and by_round["2026-R2"]["With income"] >= 1
        assert any(r.get("Average index (0-100)") for r in chart_rows("Self-reliance index by survey round"))
        # The dashboard's database role sees the reporting views and nothing else.
        dash = c.get("/api/v1/dashboard/rpcms-national", headers=h)
        assert dash.status_code == 200 and dash.json()["result"]["published"] is True


def test_non_compliant_partner_cannot_have_a_project_or_a_handover(staff, cfg):
    code = register_partner(staff, cfg, "Unregistered Relief Org", "11111111111111", "NGO/PMT/0000/0000")
    assert partner_record(staff, code)["compliance_status"] == "NON_COMPLIANT"
    with pytest.raises(StaffApiError) as refused:  # refused when the project form is saved
        register_project(staff, cfg, partner_code=code)
    assert "Partner is not compliant" in str(refused.value)

    handover = dict(client_record_id="PH-" + uuid.uuid4().hex[:8], registrant_progres_id="UGA-" + str(uuid.uuid4().int)[:8],
                    partner_code=code, assistance_type="CASH_FOR_FOOD", distribution_cycle="C-" + uuid.uuid4().hex[:6],
                    delivery_date=date.today().isoformat(), amount=150000, currency="UGX", delivery_location="Zone 3, Point A",
                    officer="Emmanuel Taban", captured_at=date.today().isoformat() + "T08:42:00+00:00",
                    gps_latitude=3.4719, gps_longitude=31.3547, gps_accuracy_m=8)
    status, body = sync_call(staff, "B-" + uuid.uuid4().hex[:6], [handover])
    assert status == 200 and body["results"][0]["status"] == "REJECTED", body
    assert "Partner is not compliant" in body["results"][0]["reason"]


def jobs_call(staff):
    staff._refresh_auth_header()
    r = staff._client.post("/rpcms-jobs/run")
    return r.status_code, r.json()


def test_daily_check_flags_an_expiring_id_once_and_sends_the_renewal_sms(staff, cfg):
    phone = "+25670" + str(uuid.uuid4().int)[:7]
    parent = person(staff, cfg, phone)
    pid = "UGA-" + str(uuid.uuid4().int)[:8]
    expiry = (date.today() + timedelta(days=10)).isoformat()
    assert change(staff, cfg, parent, "individual_info_tab", "in_identifier", REGISTER_INDIVIDUAL,
                  dict(progres_id=pid, progres_card_expiry=expiry), "UPDATE", pid) == "APPROVED"

    def flagged():
        status, body = jobs_call(staff)
        assert status == 200, body
        found = rows(staff, parent, "individual_id_renewal_tab", IR)
        return found or None  # the person's ProGres ID is applied by the worker, so the first runs may not see it

    found = wait_for(flagged, timeout=120, every=5, what="ID expiry flagged")
    assert len(found) == 1 and found[0]["status"] == "EXPIRY_FLAGGED" and found[0]["card_expiry"] == expiry
    assert found[0]["request_ref"].startswith("AUTO-" + pid)
    wait_for(lambda: rows(staff, parent, "individual_id_renewal_tab", IR)[0].get("notification_status") == "SENT",
             what="renewal SMS recorded")
    assert any("expires on " + expiry in m["text"] for m in sms_to(phone))
    status, body = jobs_call(staff)  # running it again flags no one twice
    assert status == 200 and len(rows(staff, parent, "individual_id_renewal_tab", IR)) == 1, body


def referral_call(staff, method, path, body=None):
    staff._refresh_auth_header()
    r = staff._client.request(method, path, json=body)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, {"raw": r.text}


def test_duplicate_becomes_a_referral_and_a_release_lets_one_entry_through(staff, cfg):
    import re

    parent = person(staff, cfg, "+256700000222")
    cycle = "2026-" + uuid.uuid4().hex[:4]
    row = dict(partner_code="NHU", partner_name="Nile Hope Uganda", assistance_type="CASH_FOR_FOOD", distribution_cycle=cycle,
               registrant_progres_id=KNOWN_PROGRES_ID)
    enter = lambda: change(staff, cfg, parent, "individual_assistance_tab", "in_table_assistance_events", AE, row, "ADD", KNOWN_PROGRES_ID)
    assert enter() == "APPROVED"
    refused = enter()
    assert "Duplicate assistance" in refused and "referred for review as case" in refused, refused
    case_ref = re.search(r"case ([0-9a-f]{8})", refused).group(1)

    status, cases = referral_call(staff, "GET", "/rpcms-referrals?status=OPEN")
    mine = [c for c in cases if c["case_ref"] == case_ref]
    assert status == 200 and len(mine) == 1 and mine[0]["distribution_cycle"] == cycle and mine[0]["status"] == "OPEN", cases
    case_id = mine[0]["case_id"]

    status, body = referral_call(staff, "POST", f"/rpcms-referrals/{case_id}/review", {"decision": "RELEASE"})
    assert status == 400 and "note is required" in str(body)  # releasing needs a reason
    status, body = referral_call(staff, "POST", f"/rpcms-referrals/{case_id}/review",
                                 {"decision": "RELEASE", "note": "Second partner delivered a different item"})
    assert status == 200 and body["status"] == "RELEASED" and body["reviewed_by"], body
    status, body = referral_call(staff, "POST", f"/rpcms-referrals/{case_id}/review", {"decision": "CONFIRM"})
    assert status == 409, body  # a case is decided once

    assert enter() == "APPROVED"  # the release lets this one entry through
    assert "Duplicate assistance" in enter()  # and only one
