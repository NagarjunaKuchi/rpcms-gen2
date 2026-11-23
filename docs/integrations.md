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
- **MoU status** (set from the same check, never typed): `SIGNED` when the check is `VALID`; `AWAITING_SIGNATURES` when some signatures or e-Seals are in but not all, or when the document is `INVALID` (a signed MoU that was altered is no longer signed); `DRAFT` when nothing is signed yet. A check that cannot conclude (`NOT_FOUND`, `NOT_CHECKED`) leaves the previous status, `DRAFT` for a new MoU. Mapping `INVALID` to `AWAITING_SIGNATURES` is our choice: the document names only three statuses. Nothing uses the status yet: locking the project budget on `SIGNED` is a later change.
- **Service points** (after each approved add or edit): compared by distance with other partners' non-closed points of the same service type; within `SERVICE_POINT_OVERLAP_RADIUS_M` (default 500) it is marked `OVERLAP` with the other point's name and distance.

## Quarterly reports (AMP expenditure, NIMES indicators)
Sent only when a person calls `POST /rpcms-reports/submit`; nothing is scheduled.
- **Approval first.** `POST /rpcms-reports/approve` `{"system", "quarter", optional "note"}` (permission `rpcmsReport:approve`) records who approved the figures as the preview shows them now, with a fingerprint of them (`rpcms_report_approval`). `submit` refuses with 409 unless there is an unused approval whose fingerprint matches the current figures, so figures that change after approval need approving again. A successful send uses the approval up; a failed attempt does not, and a forced resubmission needs a new approval. `GET /preview` shows the latest approval and whether it still matches. With `REPORT_APPROVER_MUST_DIFFER` (default true) the person who approved cannot also send; the dev compose file turns it off so the e2e tests can use one login. Who should approve is not decided in the build document, so the permission is separate and can be given to any role.
- AMP `POST /amp/v1/expenditure`: `{"quarter": "2026-Q4", "items": [{"amp_record", "project_code", "currency", "amount", "events"}]}` -> `{"accepted": true, "reference"}`. Spend is the sum of assistance event amounts by project and quarter (by delivery date). Projects with no AMP record number are not sent.
- NIMES `POST /nimes/v1/indicators`: `{"quarter", "indicators": [{"code", "name", "value", "unit"}]}` -> `{"accepted": true, "reference"}`. Configure with `REGISTRY_EXTENSIONS_NIMES_BASE_URL` / `_API_KEY`.
The NIMES indicators also carry `RPCMS-HOUSEHOLDS-SURVEYED` and `RPCMS-HOUSEHOLDS-WITH-INCOME`: each household counts once, by its latest self-reliance survey dated in the quarter; left out when nothing was surveyed. They are RPCMS working codes, not NDP IV codes.
Every attempt (SENT, FAILED, NOT_CONFIGURED) is logged in `rpcms_report_submission`.

## Field handover sync (staff API)
`POST /rpcms-handovers/sync` `{"batch_id", "records": [{"client_record_id", "registrant_progres_id", "partner_code", "assistance_type", "distribution_cycle", "delivery_date", optional "amount", "currency", "quantity", "unit", "project_ref", "delivery_location", "officer", "captured_at" (ISO-8601 with zone), "gps_latitude", "gps_longitude", "gps_accuracy_m"}]}` -> `{"batch_id", "received", "counts", "results": [{"client_record_id", "status", "reason", "record_id"}]}`. `status` is one of `SYNCED`, `ALREADY_SYNCED`, `DUPLICATE`, `NOT_AUTHENTICATED` (ProGres answered No for the ID; nothing recorded), `REJECTED`, `RETRY_LATER`, `FAILED`. This contract is ours, not a UNHCR/OPM specification. Authentication is the staff API's usual sign-in; there is no link between a login and a partner yet, so any user with `rpcmsHandover:sync` can send for any active partner.

## Behaviour when a system is not available
Nothing is invented and nothing blocks the record:
- Partner: status fields become `NOT_CHECKED` and overall compliance `NOT_CHECKED` (a definite "not found" is `NON_COMPLIANT`). The permit must also cover the partner's `operating_district` (`permit_area_status`: `COVERED`, `NOT_COVERED`, `NOT_CHECKED`). A district the permit does not list makes the partner `NON_COMPLIANT`. With no district entered, or an NGO Bureau answer that lists none, a partner whose permit is otherwise in order is `NOT_CHECKED`: coverage is never assumed. District names are compared ignoring case, spacing and a trailing "District".
- Partner standing gates work: a `NON_COMPLIANT` partner cannot have a project (refused when the form or change request is saved), an assistance entry (refused at approval, new rows only) or a field handover (`REJECTED`, nothing created). `NOT_CHECKED` does not block, so an outage at URSB or the NGO Bureau never stops field work; whether it should is an open question for OPM/UNHCR. An unknown partner code is not refused by this rule. The policy is one constant, `BLOCKING` in `rules/partner_gate.py`. Existing projects and assistance are not touched when a partner later becomes non-compliant.
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

## Daily checks (`POST /rpcms-jobs/run`)
Two checks run together, on staff-API permission `rpcmsJobs:run`; running them twice in a day is safe.
- **Partner permit alert:** from the partner's `permit_renewal_alert_date` (60 days before expiry by default) until the permit expires, an SMS goes to the partner's `contact_phone`, once per permit. The result is stored on the partner as `permit_alert_status` (`SENT`, `FAILED`, `NO_PHONE`, `NOT_CONFIGURED`); `permit_alert_sent_on` is set only on `SENT`, so anything else is tried again on the next run.
- **ID expiry:** a refugee whose `progres_card_expiry` falls within `REGISTRY_EXTENSIONS_ID_EXPIRY_ALERT_DAYS` days (default 60, our choice: the document gives no number) gets an ID renewal request with status `EXPIRY_FLAGGED`, created and approved by the system step (`rpcms-scheduler`), so the existing renewal SMS and its `SENT / FAILED / NO_PHONE` record apply. The request reference is `AUTO-<ProGres ID>-<expiry date>`, so a person is flagged once per card expiry. Cards that expired earlier are not picked up.
- **Nothing calls the endpoint by itself yet.** A daily trigger (a scheduled caller with a service login) is still to be set up; until then staff or a script call it.

## Budget lock
Once a project has an active MoU whose status is `SIGNED`, a change request that gives the project value, currency, target households or household rate a different value is refused when it is created ("Project budget is locked ..."). Repeating the stored value is not a change; every other project field stays editable. If the MoU later stops being `SIGNED` (for example the document is altered), the lock lifts. New projects have no MoU, so a project can still be recorded before signing: whether it should not be is an open question in the build document.

## Duplicate assistance and referral
- **Rule:** a registrant, or any other member of the registrant's household, cannot receive the same assistance type twice in the same cycle, whichever partner records it. A household is the individuals linked to the same household record; a registrant with no household, or no ProGres ID on their individual record, is checked alone. The cycle is still free text, so partners must use the same cycle label (an open question in the build document).
- **Referral:** a refused duplicate is also a case, `OPEN` until a reviewer decides it. The refusal tells the person entering it the case reference. `GET /rpcms-referrals?status=OPEN` lists cases (permission `rpcmsReferral:view`); `POST /rpcms-referrals/{case_id}/review` with `{"decision": "CONFIRM" | "RELEASE", "note": "..."}` decides one (permission `rpcmsReferral:review`). `CONFIRM` keeps it refused. `RELEASE` needs a note and lets that exact entry (registrant, type, cycle) be recorded once. A case is decided once.
- **Not decided:** who reviews and how fast. Today any user with the review permission can decide a case, including one who made the entry. Reviewing from the staff screen is not built; it is API only.

