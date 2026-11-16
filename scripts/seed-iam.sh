#!/usr/bin/env bash
# Seeds the IAM login provider + RBAC (idempotent). Required once after the stack is up,
# otherwise staff-api rejects tokens with "Unknown Issuer".
set -euo pipefail
cd "$(dirname "$0")/../deploy"
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U iam_service_user -d iam_service < seed-iam.sql
