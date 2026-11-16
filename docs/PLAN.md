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
