#!/usr/bin/env bash
# Stop the stack, keep data.
set -euo pipefail
cd "$(dirname "$0")/deploy" && docker compose stop
