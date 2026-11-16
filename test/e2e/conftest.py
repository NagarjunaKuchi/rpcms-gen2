"""End-to-end tests against a RUNNING local stack (./deploy.sh), through the same staff API the UI uses.

Needs: RP_CHECKOUT = a registry-platform checkout (its functional-testing/helpers are reused for login,
intake and AWE approval; deploy.sh leaves one in .cache/registry-platform). Skipped when it is not set.
Run on a fresh stack: the mock external systems hold fixed sample data and the tests register records.
    RP_CHECKOUT=$PWD/.cache/registry-platform .cache/venv/bin/python -m pytest test/e2e -q
"""
import os
import sys
import time

import pytest

RP = os.environ.get("RP_CHECKOUT")
if not RP:
    pytest.skip("set RP_CHECKOUT to run the end-to-end tests", allow_module_level=True)
sys.path.insert(0, os.path.join(RP, "functional-testing"))
for k, v in {
    "FUNC_STAFF_API_BASE": "http://127.0.0.1:18082", "FUNC_KEYCLOAK_BASE": "http://127.0.0.1:18080",
    "FUNC_OIDC_CLIENT_SECRET": "func-gate-client-secret", "FUNC_OIDC_USERNAME": "func-ft-e2e",
    "FUNC_OIDC_PASSWORD": "func-ft-e2e-pass",
}.items():
    os.environ.setdefault(k, v)

from helpers.config import Config  # noqa: E402
from helpers.http import StaffClient  # noqa: E402

MOCKS = os.environ.get("RPCMS_MOCKS_BASE", "http://127.0.0.1:18100")


@pytest.fixture(scope="session")
def cfg():
    return Config.from_env()


@pytest.fixture
def staff(cfg):
    """A fresh login per test. Approvals can take a minute, long enough for the API to drop an idle keep-alive
    connection, so calls that fail that way are retried once on a new connection."""
    import httpx

    with StaffClient.login(cfg) as s:
        original = s.post_json

        def post_json(path, body, *a, **kw):
            try:
                return original(path, body, *a, **kw)
            except (httpx.RemoteProtocolError, httpx.ReadError):
                return original(path, body, *a, **kw)

        s.post_json = post_json
        yield s


def wait_for(fn, timeout=90, every=2.0, what="condition"):
    """Poll fn() until it returns something truthy (approved changes are applied asynchronously by a worker)."""
    end = time.time() + timeout
    while time.time() < end:
        value = fn()
        if value:
            return value
        time.sleep(every)
    raise AssertionError(f"timed out waiting for {what}")
