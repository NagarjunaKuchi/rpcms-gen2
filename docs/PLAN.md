# Plan
0. Baseline: run registry-platform compose gate on the Linux VM.
1. Repo skeleton (this commit).
2. Refugee extension: ProGres ID, partner assistance-event register, duplicate-assistance rule, AWE policies.
3. External-system mocks (ProGres, UGPass, URSB, NGO Bureau, AMP, NIMES).
4. Use-case runner against Gen2 APIs.
5. deploy.sh / stop.sh / reset.sh.
First release: demo screens 1-6, 9, 10. Screens 7, 8 and national dashboard follow.
Status: nothing here has been run yet.

## Findings
- Phase 0 (2026-11-16, Ubuntu 22.04 VM): registry-platform compose gate brought the base stack up healthy
  (keycloak, iam, awe, partner-management, consent-manager, id-generator, minio, staff-api, partner-api, celery).
- Upstream bug (registry-platform develop @674a343): reference extension migration aborts with
  `IdentifierError: idx_g2p_register_household_housing_and_services_search_text_trigram exceeds 63 characters`
  (registry-core names the trigram index `idx_<table>_search_text_trigram`, so a table name must be <= 39 chars;
  intake-form tables <= 39 too). Tables created after it (land, livelihood, livestock...) never exist, so the
  gate's functional seed fails. staff-api still starts.
- Here: housing and vulnerability tables renamed (g2p_*_household_housing, g2p_intake_form_indiv_vulnerability).
  Rule for new registers: len("idx_" + table + "_search_text_trigram") <= 63.
  Not yet run against a database.

## Assistance-event register (added, not yet run)
- Table g2p_register_assistance_event: child (TABLE) register of Individual, fields = registrant ProGres ID, partner, project, assistance type,
  cycle, quantity/amount, delivery date, capture channel (ONLINE / OFFLINE_HANDOVER), offline batch, ProGres-authenticated flag.
- Duplicate-assistance rule = platform register deduplication: dedup_is_enabled=TRUE, threshold 100 (score is 0-100),
  deduplicate_schema EXACT on registrant_progres_id (0.4) + assistance_type (0.3) + distribution_cycle (0.3).
- Open questions to verify on the VM: that dedup runs for child-table registers on change request/ingest, and what the API returns for a match.
- UI labels have no translations yet (screens will show keys).

## Finding 2 (upstream, 2026-11-16): staff-api base images fail to boot
Published `openg2p/openg2p-registry-staff-api` `0.0.0-develop.716` and `1.2.1` both crash: `iam-core@509f7ec`
imports `openg2p_fastapi_common.utils.crypto`, but bundled `openg2p-fastapi-common@02a8c18` exposes
`openg2p_fastapi_common.crypto`. Verified on the VM with `python -c "import openg2p_fastapi_common.utils.crypto"` on
both bare base images. Our workaround reinstalls iam-core@8f02f18 (--no-deps) in docker/staff-api/Dockerfile.
Not yet reported upstream. Unverified: whether other iam-core consumers or the bene/agent portals are affected.
