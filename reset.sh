#!/usr/bin/env bash
# Remove the stack AND ALL ITS DATA (containers + volumes). Asks first.
set -euo pipefail
cd "$(dirname "$0")/deploy"
read -r -p "This deletes ALL RPCMS dev data (database, files). Type 'yes' to continue: " a
a="$(printf %s "$a" | tr -d "[:space:]" | tr "[:upper:]" "[:lower:]")"   # tolerate CR/spaces/case from pasted input
[ "$a" = yes ] || { echo aborted; exit 1; }
docker compose down -v
