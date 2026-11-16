#!/usr/bin/env python3
"""RPCMS external-systems MOCKS (dev only). Pure stdlib. Every response carries "mock": true.

Stand-ins for systems outside OpenG2P: URSB, NGO Bureau, UNHCR ProGres v4 (authentication only),
UGPass (signing + e-Seal), AMP, NIMES. Data is representative demo data from the RPCMS demo.
UGPass signatures here are HMAC-SHA256 with a throw-away key: NOT real PKI, NOT NITA-U's API.
All state is in memory and is lost on restart.
"""
import hashlib, hmac, json, os, secrets, threading, time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

KEY = secrets.token_bytes(32)
LOCK = threading.Lock()
DOCS, SIGREQS, EXPENDITURE, INDICATORS, SMS = {}, {}, [], [], []

URSB = {"80020003318742": {"registration_no": "80020003318742", "name": "Nile Hope Uganda", "type": "NGO (company limited by guarantee)", "status": "ACTIVE"}}
NGO_BUREAU = {"NGO/PMT/2025/4418": {"permit_no": "NGO/PMT/2025/4418", "holder": "Nile Hope Uganda", "status": "VALID", "valid_to": "2027-12-31", "sectors": ["Food security", "Livelihoods"]}}
PROGRES = {"UGA-00423318": {"active": True}, "UGA-00419907": {"active": True}, "UGA-00500001": {"active": False}}
AMP = {"AMP-UG-2026-00731": {"amp_record": "AMP-UG-2026-00731", "donor": "West Nile Resilience Fund", "currency": "UGX",
                             "commitment": 1200000000, "disbursed_to_partner": 300000000, "target_households": 1800, "household_rate": 150000}}


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def sign(doc_hash, who):
    return hmac.new(KEY, f"{doc_hash}|{who}".encode(), hashlib.sha256).hexdigest()


class H(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        obj = dict(obj, mock=True)
        raw = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return {}

    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urlparse(self.path); q = {k: v[0] for k, v in parse_qs(u.query).items()}; p = u.path.rstrip("/")
        if p == "/health":
            return self._send(200, {"status": "ok"})
        if p == "/ursb/v1/organisations":
            r = URSB.get(q.get("registration_no", ""))
            return self._send(200, r) if r else self._send(404, {"error": "not found"})
        if p == "/ngobureau/v1/permits":
            r = NGO_BUREAU.get(q.get("permit_no", ""))
            return self._send(200, r) if r else self._send(404, {"error": "not found"})
        if p == "/sms/v1/messages":
            to = q.get("to", "")
            return self._send(200, {"messages": [m for m in SMS if not to or m["to"] == to]})
        if p.startswith("/amp/v1/records/"):
            r = AMP.get(p.rsplit("/", 1)[1])
            return self._send(200, r) if r else self._send(404, {"error": "not found"})
        if p.startswith("/ugpass/v1/documents/") and p.endswith("/verify"):
            d = DOCS.get(p.split("/")[4])
            if not d:
                return self._send(404, {"error": "not found"})
            cur = sha(d["text"]); problems = []
            if cur != d["sha256"]:
                problems.append("document content changed after signing")
            for s in d["signatures"]:
                if s["signature"] != sign(d["sha256"], s["signer"]):
                    problems.append(f"bad signature {s['signer']}")
            return self._send(200, {"valid": not problems, "problems": problems, "current_sha256": cur, "signed_sha256": d["sha256"],
                                    "signatures": len(d["signatures"]), "eseals": len(d["eseals"])})
        return self._send(404, {"error": "unknown path"})

    def do_POST(self):
        p = urlparse(self.path).path.rstrip("/"); b = self._body()
        with LOCK:
            if p == "/progres/v4/authenticate":
                # Authentication ONLY: answer is yes/no + reference. No personal data is ever returned.
                rec = PROGRES.get(str(b.get("progres_id", "")))
                bio = b.get("biometric") or {}
                ok = bool(rec and rec["active"])  # ID-only confirmation (RPCMS does not capture biometrics)
                return self._send(200, {"authenticated": ok, "record_active": bool(rec and rec["active"]),
                                        "reference": f"PGV4-AUTH-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}", "timestamp": now()})
            if p == "/ugpass/v1/documents":
                text = str(b.get("text", ""))
                did = "DOC-" + secrets.token_hex(4).upper()
                DOCS[did] = {"text": text, "sha256": sha(text), "signatures": [], "eseals": []}
                return self._send(201, {"doc_id": did, "sha256": DOCS[did]["sha256"]})
            if p == "/ugpass/v1/signing-requests":
                if b.get("doc_id") not in DOCS:
                    return self._send(404, {"error": "unknown doc"})
                rid = "SR-" + secrets.token_hex(4).upper()
                SIGREQS[rid] = {"doc_id": b["doc_id"], "signer": b.get("signer"), "org": b.get("org"), "status": "PENDING"}
                return self._send(201, {"request_id": rid, "status": "PENDING"})
            if p.startswith("/ugpass/v1/signing-requests/") and p.endswith("/confirm"):
                r = SIGREQS.get(p.split("/")[4])
                if not r or r["status"] != "PENDING":
                    return self._send(404, {"error": "unknown or already confirmed"})
                if (b.get("biometric") or "") not in ("FINGERPRINT", "FACE"):
                    return self._send(400, {"error": "biometric confirmation required"})
                d = DOCS[r["doc_id"]]; r["status"] = "SIGNED"
                d["signatures"].append({"signer": r["signer"], "org": r["org"], "signature": sign(d["sha256"], r["signer"]), "at": now()})
                return self._send(200, {"status": "SIGNED", "signer": r["signer"]})
            if p == "/ugpass/v1/eseal":
                d = DOCS.get(b.get("doc_id"))
                if not d:
                    return self._send(404, {"error": "unknown doc"})
                d["eseals"].append({"org": b.get("org"), "signature": sign(d["sha256"], "ESEAL:" + str(b.get("org"))), "at": now()})
                return self._send(200, {"sealed_by": b.get("org")})
            if p.startswith("/ugpass/v1/documents/") and p.endswith("/tamper"):  # demo helper: simulate editing the MoU
                d = DOCS.get(p.split("/")[4])
                if not d:
                    return self._send(404, {"error": "unknown doc"})
                d["text"] = str(b.get("text", ""))
                return self._send(200, {"changed": True})
            if p == "/sms/v1/messages":  # MOCK: nothing is sent to any phone; messages are only stored for the demo
                if not b.get("to") or not b.get("text"):
                    return self._send(400, {"error": "to and text are required"})
                SMS.append({"id": f"SMS-{len(SMS) + 1:05d}", "to": b["to"], "text": b["text"], "scheduled_for": b.get("scheduled_for"),
                            "ref": b.get("ref"), "queued_at": now(), "mock": True})
                return self._send(202, {"queued": True, "id": SMS[-1]["id"]})
            if p == "/amp/v1/expenditure":
                EXPENDITURE.append(b)
                return self._send(202, {"accepted": True, "reference": f"AMP-EXP-{len(EXPENDITURE):05d}", "records": len(b.get("items", []) or [])})
            if p == "/nimes/v1/indicators":
                INDICATORS.append(b)
                return self._send(202, {"accepted": True, "reference": f"NIMES-{len(INDICATORS):05d}", "indicators": len(b.get("indicators", []) or [])})
        return self._send(404, {"error": "unknown path"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    print(f"RPCMS mocks listening on :{port}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
