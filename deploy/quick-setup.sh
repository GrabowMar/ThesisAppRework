#!/bin/bash
#
# ThesisApp Quick Setup - Run this on your Ubuntu server
# curl -fsSL https://raw.githubusercontent.com/GrabowMar/ThesisAppRework/main/deploy/quick-setup.sh | sudo bash
#

set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║          ThesisApp Quick Deployment for Ubuntu 24.04           ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Check root
if [[ $EUID -ne 0 ]]; then
    echo "❌ Please run as root: sudo bash $0"
    exit 1
fi

echo "📦 Installing prerequisites..."
apt-get update -qq
apt-get install -y -qq curl git ca-certificates gnupg lsb-release nginx ufw >/dev/null 2>&1

echo "🐳 Installing Docker..."
if ! command -v docker &>/dev/null; then
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg 2>/dev/null
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list >/dev/null
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin >/dev/null 2>&1
    systemctl start docker
    systemctl enable docker >/dev/null 2>&1
fi

echo "👤 Creating app user..."
id thesisapp &>/dev/null || useradd -m -s /bin/bash thesisapp
usermod -aG docker thesisapp

echo "📥 Cloning repository..."
mkdir -p /opt/thesisapp
rm -rf /opt/thesisapp/*
git clone --depth 1 https://github.com/GrabowMar/ThesisAppRework.git /opt/thesisapp >/dev/null 2>&1
chown -R thesisapp:thesisapp /opt/thesisapp

echo "⚙️ Creating environment..."
SECRET_KEY=$(openssl rand -hex 32)
cat > /opt/thesisapp/.env << EOF
FLASK_ENV=production
SECRET_KEY=${SECRET_KEY}
HOST=0.0.0.0
PORT=5000
DATABASE_URL=sqlite:////app/src/data/thesis_app.db
LOG_LEVEL=INFO
OPENROUTER_API_KEY=
OPENROUTER_ALLOW_ALL_PROVIDERS=true
REGISTRATION_ENABLED=false
SESSION_COOKIE_SECURE=false
SESSION_LIFETIME=86400
DOCKER_BUILDKIT=1
COMPOSE_DOCKER_CLI_BUILD=1
EOF
chown thesisapp:thesisapp /opt/thesisapp/.env
chmod 600 /opt/thesisapp/.env

echo "🔥 Configuring firewall..."
ufw --force enable >/dev/null 2>&1
ufw allow 22/tcp >/dev/null 2>&1
ufw allow 80/tcp >/dev/null 2>&1
ufw allow 443/tcp >/dev/null 2>&1

echo "🌐 Configuring Nginx..."
cat > /etc/nginx/sites-available/thesisapp << 'NGINX'
upstream thesisapp {
    server 127.0.0.1:5000;
    keepalive 32;
}
server {
    listen 80;
    listen [::]:80;
    server_name _;
    client_max_body_size 50M;
    location / {
        proxy_pass http://thesisapp;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 300s;
    }
}
NGINX
ln -sf /etc/nginx/sites-available/thesisapp /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t >/dev/null 2>&1 && systemctl reload nginx

echo "🏗️ Building containers (this takes 5-10 minutes)..."
cd /opt/thesisapp
sudo -u thesisapp docker compose build --parallel 2>&1 | grep -E "^(#|Successfully|Building)" || true

echo "🚀 Starting application..."
sudo -u thesisapp docker compose up -d

echo "⏳ Waiting for services to start..."
sleep 15

# Check if running
if curl -sf http://localhost:5000/health >/dev/null 2>&1; then
    STATUS="✅ RUNNING"
else
    STATUS="⚠️ STARTING (check logs)"
fi

IP=$(hostname -I | awk '{print $1}')

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║               🎉 Deployment Complete! 🎉                       ║"
echo "╠════════════════════════════════════════════════════════════════╣"
echo "║  Status: $STATUS"
echo "║  URL: http://$IP"
echo "╠════════════════════════════════════════════════════════════════╣"
echo "║  Commands:                                                      ║"
echo "║    cd /opt/thesisapp && docker compose logs -f   # View logs   ║"
echo "║    cd /opt/thesisapp && docker compose ps        # Status      ║"
echo "║    cd /opt/thesisapp && docker compose restart   # Restart     ║"
echo "╠════════════════════════════════════════════════════════════════╣"
echo "║  ⚠️ IMPORTANT: Add OpenRouter API key for AI features:         ║"
echo "║    nano /opt/thesisapp/.env                                    ║"
echo "╚════════════════════════════════════════════════════════════════╝"
