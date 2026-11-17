# External system integrations

RPCMS calls four external systems through adapters in
`refugee-extension/src/openg2p_registry_refugee_extension/integrations/clients.py`.
Each is configured by environment variables (prefix `REGISTRY_EXTENSIONS_`); an empty base URL means
**not configured**. Secrets (API keys) must come from the deployment's secret store, never from the repo.

| System | Used for | Base URL / key variables | Request | Expected response |
|---|---|---|---|---|
| URSB | Partner registration check | `URSB_BASE_URL`, `URSB_API_KEY` | `GET /ursb/v1/organisations?registration_no=` | `200 {"name": str, "status": "ACTIVE"...}`, `404` unknown |
| NGO Bureau | Partner permit check | `NGO_BUREAU_BASE_URL`, `NGO_BUREAU_API_KEY` | `GET /ngobureau/v1/permits?permit_no=` | `200 {"status": "VALID"..., "valid_to": "YYYY-MM-DD", "operating_districts": [str]}`, `404` unknown |
| UNHCR ProGres v4 | Confirm the ProGres ID on an assistance entry | `PROGRES_BASE_URL`, `PROGRES_API_KEY` | `POST /progres/v4/authenticate {"progres_id"}` | `200 {"authenticated": bool, "reference": str, "timestamp": str}`, `404` unknown |
| AMP (MoFPED Aid Management Platform) | Check a project's funding record | `AMP_BASE_URL`, `AMP_API_KEY` | `GET /amp/v1/records/{amp_record_no}` | `200 {"donor", "currency", "commitment", "disbursed_to_partner", ...}`, `404` unknown |
| UGPass (NITA-U) | Check a signed MoU | `UGPASS_BASE_URL`, `UGPASS_API_KEY` | `GET /ugpass/v1/documents/{document_id}/verify` | `200 {"valid": bool, "problems": [str], "current_sha256", "signatures": int, "eseals": int}`, `404` unknown |
| SMS gateway | Renewal notifications | `SMS_BASE_URL`, `SMS_API_KEY`, `SMS_SENDER_ID` | `POST /sms/v1/messages {"to","text","ref"[,"sender_id"]}` | `2xx {"id": str}` |

Common: `Authorization: Bearer <key>` when a key is set; timeout `INTEGRATION_TIMEOUT_SECONDS` (10);
`INTEGRATION_RETRIES` (2) extra attempts with backoff on network errors, HTTP 429 and 5xx.

## What the registry does with them
- **Project** (after final approval of its registration): asks AMP for the record and compares the commitment and currency with the project: `CONFIRMED`, `MISMATCH`, `NOT_FOUND` or `NOT_CHECKED`.
- **MoU** (after each approved add or edit of an MoU row): asks UGPass about the document: `VALID` (unaltered, expected signatures and e-Seals present), `INCOMPLETE`, `INVALID` (e.g. content changed after signing), `NOT_FOUND` or `NOT_CHECKED`. Expected counts default to 3 signatures and 2 e-Seals (`MOU_EXPECTED_SIGNATURES`, `MOU_EXPECTED_ESEALS`), or can be set per MoU. **Signing itself happens in the signatories' UGPass apps, not in RPCMS.** To re-check a MoU, edit the row (for example its remarks) and approve.
- **Service points** (after each approved add or edit): compared by distance with other partners' non-closed points of the same service type; within `SERVICE_POINT_OVERLAP_RADIUS_M` (default 500) it is marked `OVERLAP` with the other point's name and distance.

## Quarterly reports (AMP expenditure, NIMES indicators)
Sent only when a person calls `POST /rpcms-reports/submit`; nothing is scheduled.
- AMP `POST /amp/v1/expenditure`: `{"quarter": "2026-Q4", "items": [{"amp_record", "project_code", "currency", "amount", "events"}]}` -> `{"accepted": true, "reference"}`. Spend is the sum of assistance event amounts by project and quarter (by delivery date). Projects with no AMP record number are not sent.
- NIMES `POST /nimes/v1/indicators`: `{"quarter", "indicators": [{"code", "name", "value", "unit"}]}` -> `{"accepted": true, "reference"}`. Configure with `REGISTRY_EXTENSIONS_NIMES_BASE_URL` / `_API_KEY`.
The NIMES indicators also carry `RPCMS-HOUSEHOLDS-SURVEYED` and `RPCMS-HOUSEHOLDS-WITH-INCOME`: each household counts once, by its latest self-reliance survey dated in the quarter; left out when nothing was surveyed. They are RPCMS working codes, not NDP IV codes.
Every attempt (SENT, FAILED, NOT_CONFIGURED) is logged in `rpcms_report_submission`.

## Field handover sync (staff API)
`POST /rpcms-handovers/sync` `{"batch_id", "records": [{"client_record_id", "registrant_progres_id", "partner_code", "assistance_type", "distribution_cycle", "delivery_date", optional "amount", "currency", "quantity", "unit", "project_ref", "delivery_location", "officer", "captured_at" (ISO-8601 with zone), "gps_latitude", "gps_longitude", "gps_accuracy_m"}]}` -> `{"batch_id", "received", "counts", "results": [{"client_record_id", "status", "reason", "record_id"}]}`. `status` is one of `SYNCED`, `ALREADY_SYNCED`, `DUPLICATE`, `NOT_AUTHENTICATED` (ProGres answered No for the ID; nothing recorded), `REJECTED`, `RETRY_LATER`, `FAILED`. This contract is ours, not a UNHCR/OPM specification. Authentication is the staff API's usual sign-in; there is no link between a login and a partner yet, so any user with `rpcmsHandover:sync` can send for any active partner.

## Behaviour when a system is not available
Nothing is invented and nothing blocks the record:
- Partner: status fields become `NOT_CHECKED` and overall compliance `NOT_CHECKED` (a definite "not found" is `NON_COMPLIANT`). The permit must also cover the partner's `operating_district` (`permit_area_status`: `COVERED`, `NOT_COVERED`, `NOT_CHECKED`). A district the permit does not list makes the partner `NON_COMPLIANT`. With no district entered, or an NGO Bureau answer that lists none, a partner whose permit is otherwise in order is `NOT_CHECKED`: coverage is never assumed. District names are compared ignoring case, spacing and a trailing "District".
- Assistance: when ProGres cannot answer, the row is still recorded and the ProGres confirmation column stays empty. **A definite "No" (not authenticated, or unknown ID) refuses the row**: a new assistance entry, or an edit that changes the ProGres ID, is not recorded. Other edits of a row already recorded are not refused. Whether an outage should also block is not decided. When ProGres answers, its transaction `reference` and `timestamp` are stored with the Yes/No (`progres_auth_reference`, `progres_authenticated_at`); nothing else in the answer is read. Both are set only by the registry: a value typed in the UI or sent to the sync API is dropped.
- Project / MoU: the status becomes `NOT_CHECKED`. Service-point overlap needs no external system.
- ID renewal: the request records `SMS Status` = `SENT`, `FAILED`, `NO_PHONE` (the person has no phone number) or `NOT_CONFIGURED`.

## IMPORTANT: these contracts are ours
The request/response shapes above were written for the local mocks (`mocks/server.py`). They are **not** the
published APIs of URSB, the NGO Bureau, ProGres v4 or any SMS provider. Before go-live each adapter method in
`clients.py` must be checked against that system's real specification (authentication scheme, paths, field names,
status vocabulary) and changed there. ProGres in particular: the ID-only confirmation does **not** capture or send
a biometric; if the real service requires one, that needs a capture step in the UI that does not exist yet.

## Local development
`deploy/docker-compose.yaml` points all four at the `mocks` service (`mocks/server.py`). Every mock response says
`"mock": true`; no message is sent to any phone. Mock data is in `mocks/server.py`.
