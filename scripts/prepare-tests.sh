#!/usr/bin/env bash
# Prepares the test environment (shared by deploy.sh and run-e2e.sh): a pinned checkout of the
# registry-platform test helpers + a venv. Prints two lines to stdout: RP_CHECKOUT=... and PY=...
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLATFORM_REF=674a34347b5dab48960279bcd846183df3160140
CACHE="$ROOT/.cache"; mkdir -p "$CACHE"
{
  [ -d "$CACHE/registry-platform/.git" ] || git clone -q https://github.com/OpenG2P/registry-platform.git "$CACHE/registry-platform"
  git -C "$CACHE/registry-platform" fetch -q origin "$PLATFORM_REF" 2>/dev/null || git -C "$CACHE/registry-platform" fetch -q origin
  git -C "$CACHE/registry-platform" checkout -q "$PLATFORM_REF"
  [ -x "$CACHE/venv/bin/python" ] || python3 -m venv "$CACHE/venv"
  "$CACHE/venv/bin/pip" install -q httpx python-dotenv pytest
} >&2
echo "RP_CHECKOUT=$CACHE/registry-platform"
echo "PY=$CACHE/venv/bin/python"
