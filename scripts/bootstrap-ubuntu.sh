#!/usr/bin/env bash
# Prepare a fresh Ubuntu 22.04 VM: git, python venv/pip, Docker Engine + Compose plugin.
# Idempotent. Run as a normal sudo-capable user:  bash scripts/bootstrap-ubuntu.sh
set -euo pipefail

if [ "$(id -u)" -eq 0 ]; then echo "Run as a normal user with sudo, not root." >&2; exit 1; fi
. /etc/os-release
[ "${ID}" = "ubuntu" ] || { echo "Ubuntu expected, found ${ID}" >&2; exit 1; }

sudo apt-get update -y
sudo apt-get install -y ca-certificates curl gnupg git jq python3 python3-venv python3-pip

if ! command -v docker >/dev/null 2>&1; then
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo apt-get update -y
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"

echo "--- versions"; docker --version; sudo docker compose version; git --version; python3 --version
echo "--- resources"; nproc; free -g | sed -n 2p; df -h / | tail -1
echo
echo "Done. LOG OUT AND BACK IN (or run: newgrp docker) so 'docker' works without sudo."
