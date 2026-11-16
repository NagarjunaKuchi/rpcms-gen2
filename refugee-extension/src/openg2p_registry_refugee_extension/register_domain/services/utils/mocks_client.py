"""Tiny client for the external-system MOCKS (URSB, NGO Bureau, ProGres v4, SMS).

Dev only. The base URL comes from RPCMS_MOCKS_URL; if it is not set, every call returns None and the
caller records "not checked" instead of failing. Uses the standard library (urllib) in a worker thread so
it works the same inside the staff API and the Celery worker.
"""
import asyncio
import json
import logging
import os
import urllib.error
import urllib.request

_logger = logging.getLogger("rpcms-mocks")


def _call(method: str, path: str, body: dict | None) -> tuple[int, dict] | None:
    base = os.environ.get("RPCMS_MOCKS_URL", "").rstrip("/")
    if not base:
        return None
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        base + path, data, {"Content-Type": "application/json"}, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.load(resp)
    except urllib.error.HTTPError as err:
        try:
            return err.code, json.loads(err.read() or b"{}")
        except ValueError:
            return err.code, {}
    except Exception as err:  # network down, DNS, timeout...
        _logger.warning("mock call %s %s failed: %s", method, path, err)
        return None


async def call_mock(method: str, path: str, body: dict | None = None):
    return await asyncio.get_running_loop().run_in_executor(None, _call, method, path, body)
