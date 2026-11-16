#!/usr/bin/env python3
"""First write-path test of the AssistanceEvent register (dev stack). EXPLORATORY: it prints
what the API does instead of asserting, because duplicate handling on child (TABLE) registers
has not been verified yet.

NOTE: the built-in dedup did not stop the 2nd identical event (verified 2026-11-16); the rule is now enforced in
the domain service pre_approve hook, so event #2 is expected to fail at the approve step.

Steps: provision a Household + an Individual (via platform helpers) -> add an AssistanceEvent
by change request (edit_action ADD) -> approve -> repeat the identical event -> report.
"""
import json, os, sys, uuid

rp = os.path.expanduser(os.environ.get("RP_CHECKOUT", "~/registry-platform"))
sys.path.insert(0, os.path.join(rp, "functional-testing"))
os.environ.setdefault("FUNC_STAFF_API_BASE", "http://127.0.0.1:18082")
os.environ.setdefault("FUNC_KEYCLOAK_BASE", "http://127.0.0.1:18080")
os.environ.setdefault("FUNC_OIDC_CLIENT_SECRET", "func-gate-client-secret")  # dev-only
os.environ.setdefault("FUNC_OIDC_USERNAME", "func-ft-e2e")
os.environ.setdefault("FUNC_OIDC_PASSWORD", "func-ft-e2e-pass")

from helpers.config import Config, REGISTER_INDIVIDUAL  # noqa: E402
from helpers.http import StaffClient, StaffApiError  # noqa: E402
from helpers.flows.intake import provision_household, provision_record  # noqa: E402
from helpers.flows.change_request import verify_and_approve_cr  # noqa: E402
from helpers.profiles import INDIVIDUAL  # noqa: E402

AE_REGISTER = "b0000000-0000-4000-8000-0000000000a0"
TAB, SECTION = "individual_assistance_tab", "in_table_assistance_events"

def say(m): print(f"[test] {m}", flush=True)

def add_event(staff, subject_id, event):
    payload = {
        "register_id": REGISTER_INDIVIDUAL, "tab_id": TAB, "section_id": SECTION,
        "section_register_id": AE_REGISTER, "internal_record_id": subject_id,
        "change_payload": [{"edit_action": "ADD", "link_internal_record_id": subject_id, **event}],
    }
    body = staff.post_json("/change-requests/create_change_request", payload)
    pl = staff.payload(body)
    return body, (pl.get("change_request_id") if isinstance(pl, dict) else None)

cfg = Config.from_env()
event = dict(registrant_progres_id="PRG-T-" + uuid.uuid4().hex[:8], partner_code="WFP", partner_name="World Food Programme",
             assistance_type="FOOD", distribution_cycle="2026-11", quantity=25, unit="kg",
             delivery_date="2026-11-10", capture_channel="ONLINE")
with StaffClient.login(cfg) as staff:
    say("provision household"); hh = provision_household(staff, cfg, step=say)
    say(f"household record {hh.internal_record_id}")
    say("provision individual"); ind = provision_record(staff, cfg, INDIVIDUAL, household_id=hh.internal_record_id, step=say)
    say(f"individual record {ind.internal_record_id}")
    for n in (1, 2):
        say(f"--- submit assistance event #{n} (identical) ---")
        try:
            body, cr = add_event(staff, ind.internal_record_id, event)
            say(f"create_change_request OK, change_request_id={cr}")
            say("response: " + json.dumps(body)[:900])
            if cr:
                try:
                    verify_and_approve_cr(staff, cr, step=say); say("approved")
                except StaffApiError as e:
                    say(f"approve step error: {e}")
        except StaffApiError as e:
            say(f"create_change_request error: {e}")
print("\nNow run:  docker compose exec postgres psql -U postgres -d registry -c "
      "\"select registrant_progres_id, assistance_type, distribution_cycle, partner_code from g2p_register_assistance_event;\"")
