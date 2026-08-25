#!/usr/bin/env bash
# One-shot Hetzner Ubuntu 24.04 provisioning for addrlens.de.
# Idempotent — safe to re-run after partial failures.
# Invocation (on the box, as root): sudo bash ops/deploy/bootstrap.sh
set -euo pipefail

DEPLOY_USER="${DEPLOY_USER:-sapta}"
SRV_ROOT="/srv/addrlens"
REPO_ROOT="${SRV_ROOT}/repo/v0.1"

log() { printf '[bootstrap] %s\n' "$*"; }

if [ "$EUID" -ne 0 ]; then
    echo "bootstrap.sh must run as root (sudo bash ops/deploy/bootstrap.sh)"
    exit 1
fi

# --- 1. System packages -----------------------------------------------------
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
    ca-certificates curl gnupg lsb-release \
    ufw fail2ban unattended-upgrades \
    git tzdata

timedatectl set-timezone Europe/Berlin

# --- 2. Docker Engine + Compose plugin --------------------------------------
if ! command -v docker >/dev/null 2>&1; then
    log "installing docker"
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
        | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.gpg] \
        https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io \
                       docker-buildx-plugin docker-compose-plugin
fi
usermod -aG docker "$DEPLOY_USER"

# --- 3. Directory layout ----------------------------------------------------
mkdir -p "$SRV_ROOT"/{models,data/osm,logs}
chown -R "$DEPLOY_USER:$DEPLOY_USER" "$SRV_ROOT"
touch "$SRV_ROOT/.env.production"
chmod 600 "$SRV_ROOT/.env.production"
chown "$DEPLOY_USER:$DEPLOY_USER" "$SRV_ROOT/.env.production"

# --- 4. Swap (4 GB) — RAM headroom for llama.cpp + Index spikes -------------
if [ ! -f /swapfile ]; then
    log "creating 4 GB swapfile"
    fallocate -l 4G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
    sysctl -w vm.swappiness=10
    grep -q '^vm.swappiness' /etc/sysctl.conf \
        || echo 'vm.swappiness=10' >> /etc/sysctl.conf
fi

# --- 5. Firewall ------------------------------------------------------------
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw --force enable

# --- 6. fail2ban (SSH brute-force protection) -------------------------------
systemctl enable --now fail2ban

# --- 7. Unattended security upgrades ----------------------------------------
dpkg-reconfigure -f noninteractive unattended-upgrades
systemctl enable --now unattended-upgrades

# --- 8. Docker log rotation (avoid 40 GB disk fill) -------------------------
mkdir -p /etc/docker
cat >/etc/docker/daemon.json <<'JSON'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "20m", "max-file": "5" }
}
JSON
systemctl restart docker

# --- 9. Systemd unit for OSM weekly refresh ---------------------------------
if [ -d "$REPO_ROOT/ops/systemd" ]; then
    install -m 0644 "$REPO_ROOT/ops/systemd/refresh-osm-amenities.service" \
        /etc/systemd/system/
    install -m 0644 "$REPO_ROOT/ops/systemd/refresh-osm-amenities.timer" \
        /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable --now refresh-osm-amenities.timer
else
    log "WARN: $REPO_ROOT/ops/systemd not found — clone the repo first, then re-run"
fi

log "bootstrap complete. next:"
log "  1. hf download bartowski/Qwen2.5-1.5B-Instruct-GGUF Qwen2.5-1.5B-Instruct-Q4_K_M.gguf --local-dir $SRV_ROOT/models"
log "  2. fill $SRV_ROOT/.env.production"
log "  3. cd $REPO_ROOT && docker compose -f docker-compose.yml -f docker-compose.prod.yml build"
log "  4. cd $REPO_ROOT && docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm --entrypoint python app -m scripts.refresh_osm_amenities"
log "  5. cd $REPO_ROOT && docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file $SRV_ROOT/.env.production up -d"
