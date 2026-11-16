# rpcms-gen2

Refugee Partnership Coordination & Monitoring System (RPCMS) on OpenG2P **Gen2** (registry-platform).
**Dev environment only** (fixed passwords, no TLS). Work in progress: see `docs/PLAN.md`.

## Deploy locally (Ubuntu 22.04)
```
git clone <this repo> && cd rpcms-gen2
./deploy.sh        # installs Docker if missing (then log out/in and re-run), builds, starts, seeds, smoke-tests
./stop.sh          # stop, keep data
./reset.sh         # wipe everything
./run-e2e.sh       # end-to-end tests against a FRESH stack (reset + deploy first)
```
Needs roughly 8 GB RAM free and several GB of disk; first run builds images. Ports used: 3000, 15432, 18080-18083, 18090-18091.
Browser access from another machine needs a hosts entry (`127.0.0.1 keycloak`) plus an SSH tunnel, because Keycloak's hostname is fixed to `keycloak:8080` so that token issuers match across services. Exact steps are printed at the end of `deploy.sh`.

## Layout
- `refugee-extension/`  registry-platform extension (Individual, Household, **AssistanceEvent** register), derived from the platform reference extension (MPL-2.0).
- `docker/`  thin images on the published `openg2p/openg2p-registry-*` base (`RP_VERSION` in `deploy/.env`), with documented workarounds for upstream image defects.
- `deploy/`  compose stack (adapted from registry-platform's functional-testing gate), Keycloak realm, IAM seed.
- `mocks/`  LOCAL-ONLY stand-ins for external systems (URSB, NGO Bureau, ProGres v4, SMS, UGPass, AMP, NIMES); stdlib Python; every response says `"mock": true`. Never used outside local development.
- `scripts/`  `bootstrap-ubuntu.sh`, `seed-iam.sh`, `prepare-tests.sh`, `probe_api.py`.
- `refugee-extension/src/.../integrations/`  adapters for URSB, NGO Bureau, ProGres, SMS (configured by environment, see `docs/integrations.md`).
- `refugee-extension/src/.../rules/`  business rules as pure functions (partner compliance, duplicate assistance, renewal SMS wording).
- `refugee-extension/tests/`  unit tests (`python -m pytest refugee-extension/tests`). `test/`  version-pin check; `test/e2e/` end-to-end tests (`./run-e2e.sh`). CI: `.github/workflows/checks.yml`.

## Using it from the UI
Open http://localhost:3000 and sign in (local development only): `admin`/`admin` to enter data. Changes to existing records and new intake records need two approvals:
sign in as `alex.carter`/`alex.carter-pass` (stage 1), then `nina.patel`/`nina.patel-pass` (stage 2), and approve from the approvals list.
- **Partners:** register a partner via intake (organisation name, URSB number, NGO permit number). After final approval the registry asks URSB and the NGO Bureau and records compliance and a permit renewal alert date (`permit_renewal_alert_days` before expiry, default 60). If a system cannot answer, the result is NOT_CHECKED, never a guess.
- **Individuals:** the ID Renewal tab records expiry flagged / appointment booked / closed. Each approved status change sends an SMS to the person's phone number (Contact Details) and the request shows the SMS status (SENT, FAILED, NO_PHONE, NOT_CONFIGURED).
- **Projects:** register a project (code, partner, AMP record number, value, dates) via intake. After final approval the registry checks the funding with AMP. On the project, the MoU tab records each MoU (number and UGPass document ID) and shows the UGPass check; the Service Points tab records points (type, coordinates) and shows any overlap with another partner's point.
- **Assistance tab:** add an assistance row; the registry asks ProGres to confirm the ProGres ID and records Yes/No (empty when ProGres could not answer). A duplicate (same ProGres ID, assistance type and cycle) is refused as soon as it is entered.

## Configuration and production notes
- External systems are configured with `REGISTRY_EXTENSIONS_*` variables; see `docs/integrations.md`. **The request/response contracts in that file are ours, written for the local mocks. They must be checked against each real system before go-live.**
- Locally, `deploy/docker-compose.yaml` points everything at the mocks and uses fixed development passwords. That compose file is **not** a production deployment. A production deployment follows the farmer-registry pattern (Helm wrapper chart on the shared platform chart); it is not built yet.
- Database columns added to the models are added to existing tables automatically on start. Changes to the register **metadata** SQL (sections, labels, policies) are not applied to an existing install: a reset is needed locally, and `meta_data/zz-upgrades/` SQL (as in farmer-registry) would be needed for a live system.

- **Master Data (dropdowns).** Code lists such as gender, marital status, age method and citizenship category are read from the Master Data Service through its `/catalogue` API. They are empty unless Master Data is seeded, so `deploy/docker-compose.yaml` runs a `master-data-seed` job. It loads the code lists from the `ETH` country pack (the lists are generic) and the geography from the fictitious `XKM` pack. **There is no Uganda pack yet, so locations are not real Bidibidi geography.** A real deployment needs a Uganda pack in `openg2p-data` and the master-data chart's `geoSeed.countryPack` set to it. The Master Data images are pinned by digest in the compose file because `develop` is a moving tag; bump the digests on purpose. The older `master-data-api:1.1.3` has no `/catalogue` API and must not be used.

## Status
Verified here on a fresh local stack: 50 unit tests and 13 end-to-end tests pass (project funding check, MoU verification incl. tampered / incomplete / unknown document, service-point overlap and clearing; partner compliance for compliant, unknown and missing-number cases; assistance ProGres confirmation, duplicate refusal on add and on update; renewal SMS to the person's phone with recorded status; no-phone case; two-stage approvals).
**Assumptions:** the permit alert window defaults to 60 days and the overlap radius to 500 m (neither is specified anywhere); the assistance type, intervention and service-type lists are ours; an MoU needs 3 signatures and 2 e-Seals unless set per MoU.
**Not built:** scheduled expiry scan/reminder (flagging is manual) and scheduled MoU re-check, a map view of service points (overlap is calculated and shown as text), creating the MoU and signing requests from RPCMS (done in UGPass), sending expenditure to AMP, offline field app/GPS, self-reliance survey, national dashboard, data scopes for sharing with other registries, Helm/production deployment, biometric capture for ProGres.
**Not verified in a real browser:** rendering of the dropdowns and list columns; sign-in as `alex.carter`/`nina.patel` in the UI (approvals were driven through the same API calls).
**Known gaps:** `request_ref` on renewals is not enforced unique; a change request that fails at approval for another reason stays pending until rejected.
