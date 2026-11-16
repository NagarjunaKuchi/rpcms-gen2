"""Adapters against a real local HTTP stub: auth header, retries, 404, rejection, timeout, not configured."""
import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from openg2p_registry_refugee_extension.integrations import IntegrationConfig, Integrations, Outcome


class Stub:
    """Serves queued (status, body) answers for each path and records requests."""

    def __init__(self):
        self.answers: dict[str, list] = {}
        self.seen: list[dict] = []
        stub = self

        class H(BaseHTTPRequestHandler):
            def _do(self):
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"null") if n else None
                stub.seen.append({"method": self.command, "path": self.path, "auth": self.headers.get("Authorization"), "body": body})
                path = self.path.split("?")[0]
                queue = stub.answers.get(path) or [(404, {})]
                status, payload = queue.pop(0) if len(queue) > 1 else queue[0]
                raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            do_GET = do_POST = _do

            def log_message(self, *a):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def close(self):
        self.server.shutdown()


@pytest.fixture
def stub():
    s = Stub()
    yield s
    s.close()


def make(stub, **kw):
    cfg = IntegrationConfig(timeout=2, retries=2, ursb_base_url=stub.url, ursb_api_key="k-ursb",
                            ngo_bureau_base_url=stub.url, progres_base_url=stub.url,
                            sms_base_url=stub.url, sms_sender_id="OPM", **kw)
    return Integrations(cfg, sleep=lambda s: None)


def run(coro):
    return asyncio.run(coro)


def test_ok_sends_query_and_bearer_key(stub):
    stub.answers["/ursb/v1/organisations"] = [(200, {"name": "Nile Hope Uganda", "status": "ACTIVE"})]
    r = run(make(stub).lookup_organisation("80020000123456"))
    assert r.outcome is Outcome.OK and r.data["name"] == "Nile Hope Uganda"
    assert stub.seen[0]["path"] == "/ursb/v1/organisations?registration_no=80020000123456"
    assert stub.seen[0]["auth"] == "Bearer k-ursb"


def test_query_value_is_url_encoded(stub):
    run(make(stub).lookup_permit("NGO/PMT/2024 0001&x=1"))
    assert "permit_no=NGO%2FPMT%2F2024+0001%26x%3D1" in stub.seen[0]["path"]


def test_404_is_not_found_and_not_retried(stub):
    r = run(make(stub).lookup_permit("nope"))
    assert r.outcome is Outcome.NOT_FOUND and len(stub.seen) == 1


def test_5xx_is_retried_then_succeeds(stub):
    stub.answers["/ngobureau/v1/permits"] = [(503, {}), (500, {}), (200, {"status": "VALID", "valid_to": "2027-12-31"})]
    r = run(make(stub).lookup_permit("P1"))
    assert r.outcome is Outcome.OK and len(stub.seen) == 3


def test_5xx_exhausts_retries_to_unavailable(stub):
    stub.answers["/ngobureau/v1/permits"] = [(503, {})]
    r = run(make(stub).lookup_permit("P1"))
    assert r.outcome is Outcome.UNAVAILABLE and len(stub.seen) == 3  # 1 + 2 retries


def test_401_is_unavailable_and_not_retried(stub):
    stub.answers["/ursb/v1/organisations"] = [(401, {})]
    r = run(make(stub).lookup_organisation("x"))
    assert r.outcome is Outcome.UNAVAILABLE and r.detail == "HTTP 401" and len(stub.seen) == 1


def test_non_json_body_is_unavailable(stub):
    stub.answers["/ursb/v1/organisations"] = [(200, b"<html>gateway</html>")]
    assert run(make(stub).lookup_organisation("x")).outcome is Outcome.UNAVAILABLE


def test_not_configured_makes_no_call():
    r = run(Integrations(IntegrationConfig()).lookup_organisation("x"))
    assert r.outcome is Outcome.NOT_CONFIGURED


def test_connection_refused_is_unavailable():
    cfg = IntegrationConfig(timeout=1, retries=1, sms_base_url="http://127.0.0.1:9")
    r = run(Integrations(cfg, sleep=lambda s: None).send_sms("+256700000001", "hi", "R1"))
    assert r.outcome is Outcome.UNAVAILABLE


def test_progres_sends_id_only_no_biometric(stub):
    stub.answers["/progres/v4/authenticate"] = [(200, {"authenticated": True})]
    r = run(make(stub).confirm_progres_id("UGA-00423318"))
    assert r.ok and r.data["authenticated"] is True
    assert stub.seen[0]["body"] == {"progres_id": "UGA-00423318"}


def test_sms_payload_includes_sender(stub):
    stub.answers["/sms/v1/messages"] = [(202, {"id": "S1"})]
    r = run(make(stub).send_sms("+256700000001", "hello", "REQ-1"))
    assert r.ok
    assert stub.seen[0]["body"] == {"to": "+256700000001", "text": "hello", "ref": "REQ-1", "sender_id": "OPM"}


def test_funding_lookup_path_is_encoded(stub):
    stub.answers["/amp/v1/records/AMP-UG-2026-00731"] = [(200, {"commitment": 1})]
    cfg = IntegrationConfig(timeout=2, retries=0, amp_base_url=stub.url)
    assert run(Integrations(cfg).lookup_funding("AMP-UG-2026-00731")).ok
    run(Integrations(cfg).lookup_funding("a/b c"))
    assert stub.seen[-1]["path"] == "/amp/v1/records/a%2Fb%20c"


def test_document_verification_path(stub):
    stub.answers["/ugpass/v1/documents/DOC-1/verify"] = [(200, {"valid": True, "signatures": 3, "eseals": 2})]
    cfg = IntegrationConfig(timeout=2, retries=0, ugpass_base_url=stub.url, ugpass_api_key="k")
    r = run(Integrations(cfg).verify_document("DOC-1"))
    assert r.ok and r.data["signatures"] == 3 and stub.seen[0]["auth"] == "Bearer k"
