#!/usr/bin/env python3
"""Read-only smoke probe of the RPCMS staff-api (dev stack).

Reuses the registry-platform functional-testing helpers (StaffClient/Config) from a
registry-platform checkout (default ~/registry-platform; override RP_CHECKOUT).
Checks: login works, registers are listed, and the Individual intake form exposes our
Assistance Events section. Writes nothing.
"""
import json, os, sys

rp = os.path.expanduser(os.environ.get("RP_CHECKOUT", "~/registry-platform"))
sys.path.insert(0, os.path.join(rp, "functional-testing"))
os.environ.setdefault("FUNC_STAFF_API_BASE", "http://127.0.0.1:18082")
os.environ.setdefault("FUNC_KEYCLOAK_BASE", "http://127.0.0.1:18080")
os.environ.setdefault("FUNC_OIDC_CLIENT_SECRET", "func-gate-client-secret")  # dev-only value from deploy/docker-compose.yaml realm
os.environ.setdefault("FUNC_OIDC_USERNAME", "func-ft-e2e")
os.environ.setdefault("FUNC_OIDC_PASSWORD", "func-ft-e2e-pass")

from helpers.config import Config, INDIVIDUAL_INTAKE_FORM_ID  # noqa: E402
from helpers.http import StaffClient  # noqa: E402

cfg = Config.from_env()
with StaffClient.login(cfg) as staff:
    print("login OK")
    regs = staff.post_json("/register-metadata/get_all_registers", {})
    payload = staff.payload(regs)
    print("get_all_registers payload keys:", list(payload)[:8] if isinstance(payload, dict) else type(payload))
    text = json.dumps(payload)
    print("AssistanceEvent in registers:", "AssistanceEvent" in text)
    render = staff.post_json("/intake-form-metadata/render_intake_form", {"form_id": INDIVIDUAL_INTAKE_FORM_ID})
    rtext = json.dumps(render)
    print("intake form exposes in_table_assistance_events:", "in_table_assistance_events" in rtext)
    print("intake form exposes individual_assistance_tab/form tab:", "assistance" in rtext.lower())
