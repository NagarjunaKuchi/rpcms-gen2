"""Adapters for the external systems RPCMS talks to: URSB, NGO Bureau, UNHCR ProGres v4 and an SMS gateway.

Design rules
- Never invent a result. A system that is not configured, down, or answering with an error yields an explicit
  Outcome (NOT_CONFIGURED / UNAVAILABLE) that callers record as "not checked"; it never raises into the
  registration or approval flow.
- Standard library only (urllib, run in a worker thread) so it behaves the same in the staff API and the
  Celery worker and adds no dependency to the platform base images.
- Each adapter method is the single place to change when a real system's API differs from the contract in
  docs/integrations.md.
"""
import asyncio
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from enum import Enum

_logger = logging.getLogger("rpcms-integrations")


class Outcome(str, Enum):
    OK = "OK"  # the system answered and the answer is in Response.data
    NOT_FOUND = "NOT_FOUND"  # the system answered: no such record
    UNAVAILABLE = "UNAVAILABLE"  # network error, timeout, 5xx after retries, or the request was rejected
    NOT_CONFIGURED = "NOT_CONFIGURED"  # no base URL set for this system


@dataclass(frozen=True)
class Response:
    outcome: Outcome
    data: dict = field(default_factory=dict)
    detail: str | None = None

    @property
    def ok(self) -> bool:
        return self.outcome is Outcome.OK


@dataclass(frozen=True)
class IntegrationConfig:
    timeout: float = 10.0
    retries: int = 2
    ursb_base_url: str = ""
    ursb_api_key: str = ""
    ngo_bureau_base_url: str = ""
    ngo_bureau_api_key: str = ""
    progres_base_url: str = ""
    progres_api_key: str = ""
    sms_base_url: str = ""
    sms_api_key: str = ""
    sms_sender_id: str = ""
    amp_base_url: str = ""
    amp_api_key: str = ""
    ugpass_base_url: str = ""
    ugpass_api_key: str = ""

    @classmethod
    def from_settings(cls, settings) -> "IntegrationConfig":
        return cls(
            timeout=settings.integration_timeout_seconds,
            retries=settings.integration_retries,
            ursb_base_url=settings.ursb_base_url,
            ursb_api_key=settings.ursb_api_key,
            ngo_bureau_base_url=settings.ngo_bureau_base_url,
            ngo_bureau_api_key=settings.ngo_bureau_api_key,
            progres_base_url=settings.progres_base_url,
            progres_api_key=settings.progres_api_key,
            sms_base_url=settings.sms_base_url,
            sms_api_key=settings.sms_api_key,
            sms_sender_id=settings.sms_sender_id,
            amp_base_url=settings.amp_base_url,
            amp_api_key=settings.amp_api_key,
            ugpass_base_url=settings.ugpass_base_url,
            ugpass_api_key=settings.ugpass_api_key,
        )


def _request(base_url: str, api_key: str, method: str, path: str, *, params: dict | None, body: dict | None,
             timeout: float, retries: int, sleep=time.sleep) -> Response:
    if not base_url:
        return Response(Outcome.NOT_CONFIGURED, detail="base URL not configured")
    url = base_url.rstrip("/") + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    last = "no attempt made"
    for attempt in range(retries + 1):
        if attempt:
            sleep(min(0.5 * 2 ** (attempt - 1), 4.0))
        req = urllib.request.Request(url, data, headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                return Response(Outcome.OK, json.loads(raw) if raw else {})
        except urllib.error.HTTPError as err:
            if err.code == 404:
                return Response(Outcome.NOT_FOUND)
            last = f"HTTP {err.code}"
            if err.code == 429 or err.code >= 500:
                continue  # transient: retry
            _logger.error("%s %s rejected: %s (check credentials/contract)", method, base_url + path, last)
            return Response(Outcome.UNAVAILABLE, detail=last)
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as err:
            last = f"{type(err).__name__}: {err}"
        except ValueError as err:  # body was not JSON
            last = f"invalid response: {err}"
            break
    _logger.warning("%s %s failed after %d attempt(s): %s", method, base_url + path, retries + 1, last)
    return Response(Outcome.UNAVAILABLE, detail=last)


class Integrations:
    def __init__(self, config: IntegrationConfig, sleep=time.sleep):
        self._c = config
        self._sleep = sleep

    async def _call(self, base_url, api_key, method, path, params=None, body=None) -> Response:
        try:
            return await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: _request(base_url, api_key, method, path, params=params, body=body,
                                 timeout=self._c.timeout, retries=self._c.retries, sleep=self._sleep),
            )
        except Exception as err:  # an adapter must never break registration or approval
            _logger.exception("unexpected integration error")
            return Response(Outcome.UNAVAILABLE, detail=f"{type(err).__name__}: {err}")

    async def lookup_organisation(self, registration_no: str) -> Response:
        """URSB. OK data: {"name": str, "status": "ACTIVE"|...}"""
        return await self._call(self._c.ursb_base_url, self._c.ursb_api_key, "GET", "/ursb/v1/organisations",
                                params={"registration_no": registration_no})

    async def lookup_permit(self, permit_no: str) -> Response:
        """NGO Bureau. OK data: {"status": "VALID"|..., "valid_to": "YYYY-MM-DD"}"""
        return await self._call(self._c.ngo_bureau_base_url, self._c.ngo_bureau_api_key, "GET",
                                "/ngobureau/v1/permits", params={"permit_no": permit_no})

    async def confirm_progres_id(self, progres_id: str) -> Response:
        """ProGres v4. OK data: {"authenticated": bool}. Sends the ID only: biometric capture is not implemented."""
        return await self._call(self._c.progres_base_url, self._c.progres_api_key, "POST",
                                "/progres/v4/authenticate", body={"progres_id": progres_id})

    async def lookup_funding(self, amp_record_no: str) -> Response:
        """AMP. OK data: {"donor", "currency", "commitment", "disbursed_to_partner", "target_households", "household_rate"}"""
        path = "/amp/v1/records/" + urllib.parse.quote(amp_record_no, safe="")
        return await self._call(self._c.amp_base_url, self._c.amp_api_key, "GET", path)

    async def verify_document(self, document_id: str) -> Response:
        """UGPass. OK data: {"valid": bool, "problems": [str], "current_sha256", "signed_sha256", "signatures": int, "eseals": int}"""
        path = "/ugpass/v1/documents/" + urllib.parse.quote(document_id, safe="") + "/verify"
        return await self._call(self._c.ugpass_base_url, self._c.ugpass_api_key, "GET", path)

    async def send_sms(self, to: str, text: str, ref: str) -> Response:
        """SMS gateway. OK data: {"id": str}"""
        body = {"to": to, "text": text, "ref": ref}
        if self._c.sms_sender_id:
            body["sender_id"] = self._c.sms_sender_id
        return await self._call(self._c.sms_base_url, self._c.sms_api_key, "POST", "/sms/v1/messages", body=body)


_instance: Integrations | None = None


def get_integrations() -> Integrations:
    """The process-wide adapters, built once from the extension Settings."""
    global _instance
    if _instance is None:
        from ..config import Settings

        _instance = Integrations(IntegrationConfig.from_settings(Settings.get_config()))
    return _instance


def reset_integrations(instance: Integrations | None = None) -> None:
    """Test hook: replace (or clear) the process-wide adapters."""
    global _instance
    _instance = instance
