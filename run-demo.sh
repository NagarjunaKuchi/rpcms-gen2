#!/usr/bin/env bash
# Runs the demo use case against the running dev stack. Needs a FRESH stack (./reset.sh && ./deploy.sh).
#   ./run-demo.sh [--records N]
set -euo pipefail
cd "$(dirname "$0")"
eval "$(bash scripts/prepare-tests.sh)"
export RP_CHECKOUT
exec "$PY" scripts/run_demo.py "$@"
