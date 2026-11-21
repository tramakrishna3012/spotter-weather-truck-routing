#!/usr/bin/env bash
# Idempotent bootstrap script for Oracle Cloud Always Free Ubuntu 22.04 / 24.04 VMs
# (works on both Ampere ARM64 A1 and AMD64 E2.1.Micro instances).
#
# Run once on a fresh OCI Ubuntu VM:
#   chmod +x deploy/oracle/bootstrap-ubuntu.sh
#   sudo ./deploy/oracle/bootstrap-ubuntu.sh

set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Please run as root (e.g. sudo ./deploy/oracle/bootstrap-ubuntu.sh)." >&2
  exit 1
fi

TARGET_USER="${SUDO_USER:-ubuntu}"

echo "==> [1/4] Updating system packages and installing prerequisites..."
apt-get update -y
apt-get install -y --no-install-recommends \
  ca-certificates \
  curl \
  gnupg \
  git \
  lsb-release \
  iptables-persistent

echo "==> [2/4] Installing Docker Engine & Docker Compose plugin..."
if ! command -v docker >/dev/null 2>&1; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL --proto '=https' --tlsv1.2 https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  ARCH="$(dpkg --print-architecture)"
  CODENAME="$(. /etc/os-release && echo "${VERSION_CODENAME}")"
  echo "deb [arch=${ARCH} signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
else
  echo "Docker already installed: $(docker --version)"
fi

if id "${TARGET_USER}" >/dev/null 2>&1; then
  usermod -aG docker "${TARGET_USER}"
  echo "Added ${TARGET_USER} to docker group (re-login to use docker without sudo)."
fi

echo "==> [3/4] Configuring 2 GB swapfile if total RAM < 3 GB (protects builds on 1 GB AMD Micro VMs)..."
TOTAL_RAM_MB="$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)"
if [[ "${TOTAL_RAM_MB}" -lt 3072 && ! -f /swapfile ]]; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  if ! grep -q '^/swapfile ' /etc/fstab; then
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
  fi
  echo "Created and enabled 2 GB /swapfile."
else
  echo "Swap not needed or /swapfile already exists (RAM: ${TOTAL_RAM_MB} MB)."
fi

echo "==> [4/4] Opening HTTP (80) and HTTPS (443) in Oracle Ubuntu local iptables..."
# OCI Ubuntu images include a default REJECT rule in INPUT; insert ACCEPT rules before REJECT.
for PORT in 80 443; do
  if ! iptables -C INPUT -p tcp --dport "${PORT}" -m conntrack --ctstate NEW,ESTABLISHED -j ACCEPT 2>/dev/null; then
    iptables -I INPUT 6 -p tcp --dport "${PORT}" -m conntrack --ctstate NEW,ESTABLISHED -j ACCEPT
  fi
done
if ! iptables -C INPUT -p udp --dport 443 -m conntrack --ctstate NEW,ESTABLISHED -j ACCEPT 2>/dev/null; then
  iptables -I INPUT 6 -p udp --dport 443 -m conntrack --ctstate NEW,ESTABLISHED -j ACCEPT
fi
netfilter-persistent save

echo ""
echo "Bootstrap complete!"
echo "Next steps:"
echo "  1. Ensure TCP ports 80 and 443 are also open in your OCI VCN Security List (Ingress Rules)."
echo "  2. Log out and back in so '${TARGET_USER}' has docker group permissions."
echo "  3. Copy .env.example -> .env, configure production values, and run:"
echo "       docker compose -f docker-compose.prod.yml up -d --build"
