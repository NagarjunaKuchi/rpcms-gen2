#!/usr/bin/env bash
# One-command local (dev) deployment of RPCMS on OpenG2P Gen2.
#   ./deploy.sh            install Docker if missing, build, start, seed, smoke-test
#   ./deploy.sh --no-test  skip the smoke tests
# Ubuntu 22.04. DEV ONLY: fixed passwords, no TLS.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"; cd "$ROOT"
PLATFORM_REF=674a34347b5dab48960279bcd846183df3160140   # registry-platform commit whose test helpers the smoke tests reuse
RUN_TESTS=1; [ "${1:-}" = "--no-test" ] && RUN_TESTS=0
log() { printf '\n==> %s\n' "$*"; }

if ! command -v docker >/dev/null 2>&1; then
  log "Docker not found: running scripts/bootstrap-ubuntu.sh"
  bash scripts/bootstrap-ubuntu.sh
  echo "Docker was just installed and your user added to the 'docker' group."
  echo "LOG OUT AND BACK IN (a new login shell is required), then run ./deploy.sh again." ; exit 0
fi
if ! docker info >/dev/null 2>&1; then
  echo "Cannot talk to Docker. If you were just added to the 'docker' group, log out and back in. Do not use sudo." >&2; exit 1
fi
for p in 3000 15432 18080 18081 18082 18083 18090 18091; do
  if ss -ltn 2>/dev/null | awk '{print $4}' | grep -q ":${p}\$"; then
    # ignore if it is our own stack
    if ! docker ps --format '{{.Names}} {{.Ports}}' | grep -q "deploy-.*:${p}->"; then
      echo "Port ${p} is already in use by something other than this stack. Free it first (see: docker ps / ss -ltnp)." >&2; exit 1
    fi
  fi
done

log "Building images and starting the stack (first run downloads/builds several GB; be patient)"
( cd deploy && docker compose up -d --build )

log "Waiting for staff-api to become healthy (up to 5 min)"
cid="$(cd deploy && docker compose ps -q staff-api)"
for i in $(seq 1 60); do
  st="$(docker inspect -f '{{.State.Health.Status}}' "$cid" 2>/dev/null || echo none)"
  [ "$st" = healthy ] && break
  [ "$st" = exited ] && { echo "staff-api exited; see: cd deploy && docker compose logs staff-api --tail 80" >&2; exit 1; }
  sleep 5
done
[ "$st" = healthy ] || { echo "staff-api not healthy after 5 min (status: $st)." >&2; exit 1; }

log "Waiting for the metadata seed (db-seed) to finish"
sid="$(cd deploy && docker compose ps -a -q db-seed)"
for i in $(seq 1 60); do
  s="$(docker inspect -f '{{.State.Status}}' "$sid")"; [ "$s" = exited ] && break; sleep 5
done
code="$(docker inspect -f '{{.State.ExitCode}}' "$sid")"
[ "$s" = exited ] && [ "$code" = 0 ] || { echo "db-seed did not finish cleanly (status=$s exit=$code); see: cd deploy && docker compose logs db-seed --tail 60" >&2; exit 1; }

log "Seeding IAM login provider and roles"
bash scripts/seed-iam.sh

log "Making sure workers are up"
( cd deploy && docker compose up -d celery-worker celery-beat )
sleep 5

if [ "$RUN_TESTS" = 1 ]; then
  log "Smoke tests (reuse registry-platform test helpers @ ${PLATFORM_REF:0:7})"
  CACHE="$ROOT/.cache"; mkdir -p "$CACHE"
  if [ ! -d "$CACHE/registry-platform/.git" ]; then
    git clone -q https://github.com/OpenG2P/registry-platform.git "$CACHE/registry-platform"
  fi
  git -C "$CACHE/registry-platform" fetch -q origin "$PLATFORM_REF" 2>/dev/null || git -C "$CACHE/registry-platform" fetch -q origin
  git -C "$CACHE/registry-platform" checkout -q "$PLATFORM_REF"
  [ -x "$CACHE/venv/bin/python" ] || python3 -m venv "$CACHE/venv"
  "$CACHE/venv/bin/pip" install -q httpx python-dotenv
  export RP_CHECKOUT="$CACHE/registry-platform"
  "$CACHE/venv/bin/python" scripts/probe_api.py
  "$CACHE/venv/bin/python" scripts/test_assistance.py | tail -n 12
fi

cat <<EOF

RPCMS (dev) is up.
  Staff UI        http://localhost:3000        login: admin / admin   (Keycloak realm 'staff')
  Keycloak        http://localhost:18080 (on the VM)  admin console: admin / admin
  Staff API       http://localhost:18082/docs
  Partner API     http://localhost:18083/docs
To use the UI from your PC's browser (dev setup; the stack's Keycloak hostname is fixed to 'keycloak:8080'):
  1. Add this line to your PC's hosts file (Windows: C:\\Windows\\System32\\drivers\\etc\\hosts, as Administrator):
         127.0.0.1  keycloak
  2. Open an SSH tunnel to the VM (note local 8080 -> Keycloak):
         ssh -L 3000:localhost:3000 -L 8080:localhost:18080 -L 18081:localhost:18081 -L 18082:localhost:18082 <user>@<vm>
  3. Browse http://localhost:3000   (the sign-in page will be at http://keycloak:8080)
Stop: ./stop.sh     Wipe all data: ./reset.sh
EOF
