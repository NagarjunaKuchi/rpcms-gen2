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

## Status
Working on the dev stack (verified by hand): stack boots; extension migrates; assistance events can be added by change request;
the duplicate-assistance rule (same ProGres ID + assistance type + cycle) is enforced at approval.
Not built yet: external-system mocks (ProGres, UGPass, URSB, NGO Bureau, AMP, NIMES), the demo-screen runner, offline handover ingest,
UI labels/translations, ID renewal, self-reliance survey, national dashboard. Not verified: login to the staff UI with `admin`/`admin`.
