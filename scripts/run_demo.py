#!/usr/bin/env python3
"""RPCMS demo runner (dev stack): drives the demo use case against the real Gen2 registry APIs and the
clearly-labelled MOCKS of external systems. Prints PASS / FAIL / NOT IMPLEMENTED per step.

Assumes a FRESH stack (./reset.sh && ./deploy.sh): demo ProGres IDs are reused across runs, so a second
run would legitimately be flagged as duplicate assistance and the runner stops early with a message.
Options:  --records N   number of offline-handover records for screen 6 (default 214)
"""
import argparse, json, os, sys, time, urllib.request, urllib.error
from datetime import date, timedelta

rp = os.path.expanduser(os.environ.get("RP_CHECKOUT", "~/registry-platform"))
sys.path.insert(0, os.path.join(rp, "functional-testing"))
os.environ.setdefault("FUNC_STAFF_API_BASE", "http://127.0.0.1:18082")
os.environ.setdefault("FUNC_KEYCLOAK_BASE", "http://127.0.0.1:18080")
os.environ.setdefault("FUNC_OIDC_CLIENT_SECRET", "func-gate-client-secret")  # dev-only
os.environ.setdefault("FUNC_OIDC_USERNAME", "func-ft-e2e")
os.environ.setdefault("FUNC_OIDC_PASSWORD", "func-ft-e2e-pass")
MOCKS = os.environ.get("RPCMS_MOCKS", "http://127.0.0.1:18100")

from helpers.config import Config, REGISTER_INDIVIDUAL  # noqa: E402
from helpers.http import StaffClient, StaffApiError  # noqa: E402
from helpers.flows.intake import provision_household, provision_record  # noqa: E402
from helpers.flows.change_request import verify_and_approve_cr  # noqa: E402
from helpers.flows.register import search_register_by_text  # noqa: E402
from helpers.profiles import INDIVIDUAL  # noqa: E402

AE = "b0000000-0000-4000-8000-0000000000a0"
TAB, SECTION = "individual_assistance_tab", "in_table_assistance_events"
CYCLE, ATYPE, AMOUNT = "2026-03", "CASH_FOR_FOOD", 150000
MARY, NEIGHBOUR = "UGA-00423318", "UGA-00419907"
RESULTS = []


def step(screen, name, status, detail=""):
    RESULTS.append((screen, name, status))
    print(f"  [{status:15}] {screen} {name}" + (f" -- {detail}" if detail else ""), flush=True)


def mock(method, path, body=None):
    req = urllib.request.Request(MOCKS + path, json.dumps(body).encode() if body is not None else None,
                                 {"Content-Type": "application/json"}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def add_and_approve(staff, parent_id, ev):
    """Record one assistance event (change request ADD) and approve it. Returns 'APPROVED' or the rejection text."""
    body = staff.post_json("/change-requests/create_change_request", {
        "register_id": REGISTER_INDIVIDUAL, "tab_id": TAB, "section_id": SECTION, "section_register_id": AE,
        "internal_record_id": parent_id,
        "change_payload": [{"edit_action": "ADD", "link_internal_record_id": parent_id, **ev}]})
    cr = staff.payload(body)["change_request_id"]
    try:
        verify_and_approve_cr(staff, cr)
        return "APPROVED"
    except StaffApiError as e:
        # A change request that fails approval stays PENDING and the registry allows only one pending request per
        # record+section, so reject it explicitly (with the reason); otherwise it blocks every later event.
        try:
            staff.post_json("/change-requests/reject_change_request", {"change_request_id": cr, "rejection_reason": str(e)[:480]})
        except StaffApiError as e2:
            print(f"     could not reject change request {cr}: {e2}")
        return str(e)


def find_events(staff, progres_id):
    """Pre-handover duplicate check: search the shared assistance register by ProGres ID (record name starts with it)."""
    hits = search_register_by_text(staff, progres_id, register_id=AE, page_size=50)
    return [h for h in hits if str(h.get("record_name") or "").split(" ")[:1] == [progres_id]]


def event(pid, partner_code, partner_name, when, ref, cycle=CYCLE, atype=ATYPE):
    return dict(registrant_progres_id=pid, partner_code=partner_code, partner_name=partner_name, assistance_type=atype,
                distribution_cycle=cycle, amount=AMOUNT, currency="UGX", delivery_date=when, project_ref=ref,
                delivery_location="Bidibidi Zone 3", capture_channel="ONLINE")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--records", type=int, default=214); a = ap.parse_args()
    print("RPCMS demo run (dev). External systems are MOCKS; registry calls are real.\n")
    if mock("GET", "/health")[0] != 200:
        sys.exit(f"mocks not reachable at {MOCKS}. Is the 'mocks' service up?  (cd deploy && docker compose up -d mocks)")

    # ---- Screen 1: partner registration & compliance ------------------------------------------------
    s, org = mock("GET", "/ursb/v1/organisations?registration_no=80020003318742")
    s2, permit = mock("GET", "/ngobureau/v1/permits?permit_no=NGO/PMT/2025/4418")
    ok = s == 200 and s2 == 200 and org["name"] == permit["holder"] == "Nile Hope Uganda" and permit["status"] == "VALID"
    alert = date.fromisoformat(permit["valid_to"]) - timedelta(days=60) if s2 == 200 else None
    step("1", "URSB + NGO Bureau compliance checks (mock)", "PASS" if ok else "FAIL", f"permit valid to {permit.get('valid_to')}, renewal alert {alert}")
    step("1", "Partner profile in partner-management + expiry alert", "NOT IMPLEMENTED", "Gen2 partner-management registration flow not wired yet")

    # ---- Screen 2: e-MoU with UGPass (mock) ----------------------------------------------------------
    text = "MoU OPM/DoR/NHU/2026/014 | Nile Hope Uganda | total project value UGX 1,200,000,000 | AMP-UG-2026-00731 | 01 Mar 2026 - 28 Feb 2027"
    _, d = mock("POST", "/ugpass/v1/documents", {"text": text}); did = d["doc_id"]
    for signer, org_ in (("OPM Commissioner", "OPM-DoR"), ("NHU Country Director", "Nile Hope Uganda"), ("OPM Legal Officer", "OPM-DoR")):
        _, r = mock("POST", "/ugpass/v1/signing-requests", {"doc_id": did, "signer": signer, "org": org_})
        mock("POST", f"/ugpass/v1/signing-requests/{r['request_id']}/confirm", {"biometric": "FINGERPRINT"})
    for org_ in ("OPM-DoR", "Nile Hope Uganda"):
        mock("POST", "/ugpass/v1/eseal", {"doc_id": did, "org": org_})
    _, v = mock("GET", f"/ugpass/v1/documents/{did}/verify")
    step("2", "3 signatures + 2 e-Seals verify (mock UGPass, HMAC not PKI)", "PASS" if v["valid"] and v["signatures"] == 3 and v["eseals"] == 2 else "FAIL")
    mock("POST", f"/ugpass/v1/documents/{did}/tamper", {"text": text.replace("1,200,000,000", "9,200,000,000")})
    _, v2 = mock("GET", f"/ugpass/v1/documents/{did}/verify")
    step("2", "Tampering with the amount breaks verification", "PASS" if not v2["valid"] else "FAIL", "; ".join(v2["problems"]))

    # ---- Screen 3: project, funding (AMP mock) ------------------------------------------------------
    s, amp = mock("GET", "/amp/v1/records/AMP-UG-2026-00731")
    step("3", "AMP funding record matches MoU (mock)", "PASS" if s == 200 and amp["commitment"] == 1200000000 else "FAIL", f"commitment {amp.get('commitment')} {amp.get('currency')}")
    step("3", "Overlap detection between partners' service points (map)", "NOT IMPLEMENTED", "needs service-point geodata")

    # ---- Registry set-up: a household + a person as parent for assistance rows -------------------------
    cfg = Config.from_env()
    with StaffClient.login(cfg) as staff:
        if find_events(staff, MARY):
            sys.exit("Demo ProGres IDs already have events: this stack is not fresh. Run ./reset.sh && ./deploy.sh, then retry.")
        hh = provision_household(staff, cfg)
        parent = provision_record(staff, cfg, INDIVIDUAL, household_id=hh.internal_record_id).internal_record_id
        print(f"  (set-up) stand-in household/person created in the registry; person record {parent}")
        print("  NOTE: the stand-in person has a generated name and no ProGres ID field yet, so all assistance rows below attach to it.")

        # ---- Screen 4: authenticate with ProGres v4 (mock) -------------------------------------------
        _, auth = mock("POST", "/progres/v4/authenticate", {"progres_id": MARY, "biometric": {"modality": "FACE", "capture": "demo-capture"}})
        allowed = {"authenticated", "record_active", "reference", "timestamp", "mock"}
        step("4", "ProGres auth answers YES for Mary, returns no personal data (mock)", "PASS" if auth["authenticated"] and set(auth) <= allowed else "FAIL", f"ref {auth['reference']}")
        _, bad = mock("POST", "/progres/v4/authenticate", {"progres_id": "UGA-00500001", "biometric": {"modality": "FACE", "capture": "x"}})
        step("4", "Inactive/unknown ID is NOT authenticated (mock)", "PASS" if not bad["authenticated"] else "FAIL")

        # ---- Screen 5: duplicate assistance check ----------------------------------------------------
        r = add_and_approve(staff, parent, event(NEIGHBOUR, "WNRP", "West Nile Relief Partners", "2026-03-02", "DST-WNRP-0302-0188"))
        step("5", "Other partner's earlier handover recorded in shared register", "PASS" if r == "APPROVED" else "FAIL", "" if r == "APPROVED" else r[:200])
        time.sleep(3)  # let the worker apply the approved change and index the row for search
        mine, theirs = find_events(staff, MARY), find_events(staff, NEIGHBOUR)
        step("5", "Mary: no duplicate found before handover (search by ProGres ID)", "PASS" if not mine else "FAIL")
        step("5", "UGA-00419907: duplicate flagged before handover", "PASS" if theirs and "WNRP" in str(theirs[0].get("record_name")) else "FAIL", str(theirs[0].get("record_name")) if theirs else "search found nothing")
        r = add_and_approve(staff, parent, event(NEIGHBOUR, "NHU", "Nile Hope Uganda", "2026-03-05", "DST-NHU-0305-00001"))
        step("5", "Registry itself rejects the duplicate if recorded anyway", "PASS" if "Duplicate assistance" in r else "FAIL", r[:160])

        # ---- Screen 6: handover + offline batch sync -----------------------------------------------------
        r = add_and_approve(staff, parent, event(MARY, "NHU", "Nile Hope Uganda", "2026-03-05", "DST-NHU-0305-00214"))
        step("6", "Mary's handover recorded", "PASS" if r == "APPROVED" else "FAIL", "" if r == "APPROVED" else r[:200])
        n, dups = a.records, 3
        ids = [f"UGA-{1000000 + i}" for i in range(n - dups)]
        batch = ids + ids[:dups]  # last 3 repeat earlier IDs -> duplicates inside the batch
        approved = flagged = errors = 0; t0 = time.time()
        for i, pid in enumerate(batch):
            r = add_and_approve(staff, parent, dict(event(pid, "NHU", "Nile Hope Uganda", "2026-03-05", f"DST-NHU-0305-{i:05d}"), capture_channel="OFFLINE_HANDOVER", offline_batch_id="BATCH-Z3-A"))
            if r == "APPROVED": approved += 1
            elif "Duplicate assistance" in r: flagged += 1
            else:
                errors += 1; print("     error:", r[:160])
        secs = time.time() - t0
        ok = errors == 0 and approved == n - dups and flagged == dups
        step("6", f"Offline batch of {n}: {approved} recorded, {flagged} flagged duplicate, {errors} errors", "PASS" if ok else "FAIL", f"{secs:.0f}s via change-request API (not the demo's 14 s broker sync)")
        value = (approved + 1) * AMOUNT
        print(f"     recorded value UGX {value:,} (demo shows UGX 32,100,000 = all 214 records incl. the 3 flagged)")
        step("6", "Offline-first phone sync, GPS capture", "NOT IMPLEMENTED", "no field app; GPS not captured in the register")

    # ---- Screens 7, 8, 9, 10 ---------------------------------------------------------------------------------
    step("7", "ID expiry flag, appointment, SMS", "NOT IMPLEMENTED", "needs ProGres-ID expiry field + Novu/notifications")
    step("8", "Self-reliance survey (offline)", "NOT IMPLEMENTED", "ODK Central not added")
    _, e = mock("POST", "/amp/v1/expenditure", {"period": "2026-Q1", "items": [{"project": "PRJ-BDB-2026-022", "amount": value, "currency": "UGX"}]})
    _, nm = mock("POST", "/nimes/v1/indicators", {"period": "2026-Q1", "indicators": [{"code": "assistance_events", "value": approved + 1}]})
    step("10", "Expenditure sent to AMP, indicators to NIMES (mocks, figures from this run)", "PASS" if e.get("accepted") and nm.get("accepted") else "FAIL", f"{e.get('reference')}, {nm.get('reference')}")
    step("10", "National dashboard (146 partners, maps, partner table)", "NOT IMPLEMENTED", "Superset not added")

    print("\nSummary:")
    for st in ("PASS", "FAIL", "NOT IMPLEMENTED"):
        print(f"  {st:16} {sum(1 for x in RESULTS if x[2] == st)}")
    sys.exit(1 if any(x[2] == "FAIL" for x in RESULTS) else 0)


if __name__ == "__main__":
    main()
