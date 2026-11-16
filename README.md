# rpcms-gen2

Refugee Partnership Coordination & Monitoring System (RPCMS) on OpenG2P **Gen2** (registry-platform).
**Dev environment only** (fixed passwords, no TLS). Work in progress: see `docs/PLAN.md`.

## Deploy locally (Ubuntu 22.04)
```
git clone <this repo> && cd rpcms-gen2
./deploy.sh        # installs Docker if missing (then log out/in and re-run), builds, starts, seeds, smoke-tests
./stop.sh          # stop, keep data
./reset.sh         # wipe everything
./run-demo.sh      # run the demo use case against a FRESH stack (reset + deploy first)
```
Needs roughly 8 GB RAM free and several GB of disk; first run builds images. Ports used: 3000, 15432, 18080-18083, 18090-18091.
Browser access from another machine needs a hosts entry (`127.0.0.1 keycloak`) plus an SSH tunnel, because Keycloak's hostname is fixed to `keycloak:8080` so that token issuers match across services. Exact steps are printed at the end of `deploy.sh`.

## Layout
- `refugee-extension/`  registry-platform extension (Individual, Household, **AssistanceEvent** register), derived from the platform reference extension (MPL-2.0).
- `docker/`  thin images on the published `openg2p/openg2p-registry-*` base (`RP_VERSION` in `deploy/.env`), with documented workarounds for upstream image defects.
- `deploy/`  compose stack (adapted from registry-platform's functional-testing gate), Keycloak realm, IAM seed.
- `mocks/`  stand-ins for external systems (URSB, NGO Bureau, ProGres v4 auth, UGPass, AMP, NIMES); stdlib Python; every response says `"mock": true`.
- `scripts/`  `bootstrap-ubuntu.sh`, `seed-iam.sh`, `probe_api.py`, `test_assistance.py`, `run_demo.py` (demo runner, PASS/FAIL/NOT IMPLEMENTED per step).

## Using it from the UI
Open http://localhost:3000 and sign in (dev only): `admin`/`admin` to enter data. Changes to existing records and new intake records need two approvals:
sign in as `alex.carter`/`alex.carter-pass` (stage 1), then `nina.patel`/`nina.patel-pass` (stage 2), and approve from the approvals list.
- **Partners:** register a partner via intake (organisation name, URSB number, NGO permit number). After final approval the registry calls the URSB and NGO Bureau mocks and records compliance status and a permit renewal alert date.
- **Individuals:** the ID Renewal tab records expiry flagged / appointment booked / closed; each approved status change sends an SMS through the mock SMS service.
- **Assistance tab:** add an assistance row; at approval the registry calls the mock ProGres authentication and records the result. Duplicate (ProGres ID, type, cycle) is rejected.
Mock URSB numbers/permits accepted: see `mocks/server.py`. Everything external is a mock and says so in its response.

## Status
Verified in an automated run against a fresh stack (`run-demo.sh`, test harness only): Partner intake + compliance check (compliant and non-compliant cases),
assistance entry with ProGres authentication recorded, ID renewal with SMS, two-stage approvals.
**Assumptions:** the permit alert date is 60 days before permit expiry (not from the demo); assistance type values are my own list.
**Not built:** expiry scan/reminder is manual (no scheduled job), map overlap check, offline field app/GPS, real SMS, self-reliance survey (screen 8), national dashboard.
**Not verified in a real browser:** rendering of the new dropdowns and list columns; whether Save enables on a section with no pending change request.
