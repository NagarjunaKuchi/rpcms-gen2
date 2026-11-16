#!/usr/bin/env bash
# Runs the end-to-end tests (test/e2e) against the running local stack, through the same staff API the UI uses.
# Use a FRESH stack (./reset.sh && ./deploy.sh): the mock external systems hold fixed sample data.
#   ./run-e2e.sh [pytest args]
set -euo pipefail
cd "$(dirname "$0")"
eval "$(bash scripts/prepare-tests.sh)"
export RP_CHECKOUT
exec "$PY" -m pytest test/e2e -q "$@"
