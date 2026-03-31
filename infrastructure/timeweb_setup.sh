#!/usr/bin/env bash
set -euo pipefail

echo "=== PersonalAI Sergiy — Timeweb VPS Setup ==="

# Update system
apt-get update && apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh

# Install Docker Compose v2
apt-get install -y docker-compose-plugin

# Create app user
useradd -m -s /bin/bash personalai || true
usermod -aG docker personalai

# Create app directory
mkdir -p /opt/personalai
chown personalai:personalai /opt/personalai

# Firewall
apt-get install -y ufw
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# Swap (2GB)
if [ ! -f /swapfile ]; then
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

# Install certbot for SSL
apt-get install -y certbot

echo ""
echo "=== Setup complete ==="
echo "Next steps:"
echo "  1. Clone repo: git clone <repo-url> /opt/personalai"
echo "  2. Copy .env: cp .env.example .env && nano .env"
echo "  3. SSL: certbot certonly --standalone -d your-domain.ru"
echo "  4. Start: cd /opt/personalai && docker compose -f docker-compose.prod.yml up -d"
