# ThesisApp Production Deployment Guide

## Server Information
- **Server**: ns3086089.ip-145-239-65.eu
- **IP**: 145.239.65.130
- **OS**: Ubuntu Server 24.04 LTS "Noble Numbat"
- **Hardware**: Intel Xeon E5-1650v2 (6c/12t), 32GB RAM, 120GB SSD

---

## 🚀 Quick Deployment (One-Command)

```bash
# SSH into your server
ssh root@145.239.65.130

# Download and run deployment script
curl -fsSL https://raw.githubusercontent.com/GrabowMar/ThesisAppRework/main/deploy/deploy.sh -o deploy.sh
chmod +x deploy.sh
sudo ./deploy.sh
```

---

## 📋 Manual Step-by-Step Deployment

### 1. Connect to Server

```bash
ssh root@145.239.65.130
```

### 2. Update System

```bash
apt update && apt upgrade -y
apt install -y curl git wget htop net-tools ufw fail2ban nginx certbot python3-certbot-nginx
```

### 3. Install Docker

```bash
# Add Docker's GPG key
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

# Add repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Start Docker
systemctl start docker
systemctl enable docker
```

### 4. Create Application User

```bash
useradd -m -s /bin/bash thesisapp
usermod -aG docker thesisapp
mkdir -p /opt/thesisapp
chown -R thesisapp:thesisapp /opt/thesisapp
```

### 5. Clone Repository

```bash
cd /opt/thesisapp
sudo -u thesisapp git clone https://github.com/GrabowMar/ThesisAppRework.git .
```

### 6. Configure Environment

```bash
# Create .env file
cat > /opt/thesisapp/.env << 'EOF'
FLASK_ENV=production
SECRET_KEY=$(openssl rand -hex 32)
HOST=0.0.0.0
PORT=5000
DATABASE_URL=sqlite:////app/src/data/thesis_app.db
LOG_LEVEL=INFO
OPENROUTER_API_KEY=your-api-key-here
OPENROUTER_ALLOW_ALL_PROVIDERS=true
REGISTRATION_ENABLED=false
SESSION_COOKIE_SECURE=true
SESSION_LIFETIME=86400
DOCKER_BUILDKIT=1
COMPOSE_DOCKER_CLI_BUILD=1
EOF

chown thesisapp:thesisapp /opt/thesisapp/.env
chmod 600 /opt/thesisapp/.env
```

### 7. Configure Firewall

```bash
ufw --force enable
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw reload
```

### 8. Build and Start Containers

```bash
cd /opt/thesisapp
sudo -u thesisapp docker compose build --parallel
sudo -u thesisapp docker compose up -d
```

### 9. Configure Nginx

```bash
cat > /etc/nginx/sites-available/thesisapp << 'EOF'
upstream thesisapp {
    server 127.0.0.1:5000;
    keepalive 32;
}

server {
    listen 80;
    listen [::]:80;
    server_name _;

    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    access_log /var/log/nginx/thesisapp_access.log;
    error_log /var/log/nginx/thesisapp_error.log;

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
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 300s;
    }

    location /health {
        proxy_pass http://thesisapp/health;
        proxy_http_version 1.1;
        access_log off;
    }
}
EOF

ln -sf /etc/nginx/sites-available/thesisapp /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
```

### 10. Create Systemd Service

```bash
cat > /etc/systemd/system/thesisapp.service << 'EOF'
[Unit]
Description=ThesisApp Docker Compose Application
Requires=docker.service
After=docker.service network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
User=thesisapp
WorkingDirectory=/opt/thesisapp
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable thesisapp.service
```

---

## 🔒 SSL Setup (Optional but Recommended)

If you have a domain pointed to your server:

```bash
# Replace with your domain
DOMAIN="your-domain.com"

# Update Nginx config
sed -i "s/server_name _;/server_name $DOMAIN;/" /etc/nginx/sites-available/thesisapp
nginx -t && systemctl reload nginx

# Get SSL certificate
certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN

# Enable auto-renewal
systemctl enable certbot.timer
systemctl start certbot.timer
```

---

## 📊 Management Commands

### Check Status
```bash
cd /opt/thesisapp
docker compose ps
```

### View Logs
```bash
cd /opt/thesisapp
docker compose logs -f --tail=100
```

### Restart Services
```bash
cd /opt/thesisapp
docker compose restart
```

### Update Application
```bash
cd /opt/thesisapp
git pull origin main
docker compose down
docker compose build --parallel
docker compose up -d
```

### Stop Everything
```bash
cd /opt/thesisapp
docker compose down
```

---

## 🔧 Troubleshooting

### Container Won't Start
```bash
# Check logs
docker compose logs web

# Check if ports are in use
netstat -tlnp | grep -E "5000|80|443"
```

### Database Issues
```bash
# Access container shell
docker compose exec web bash

# Check database file
ls -la /app/src/data/
```

### Nginx Issues
```bash
# Test config
nginx -t

# Check logs
tail -f /var/log/nginx/error.log
```

### Memory Issues
```bash
# Check memory usage
free -h
docker stats --no-stream
```

---

## 📁 Directory Structure (on server)

```
/opt/thesisapp/
├── .env                    # Environment variables
├── docker-compose.yml      # Container orchestration
├── Dockerfile              # Flask app container
├── src/                    # Flask application
├── analyzer/               # Analyzer services
├── generated/apps/         # Generated applications
├── results/                # Analysis results
└── logs/                   # Application logs
```

---

## 🌐 Access Points

After deployment:
- **Application**: http://145.239.65.130
- **Health Check**: http://145.239.65.130/health

---

## ⚠️ Security Notes

1. **Change default credentials** - Create a new admin user immediately
2. **Add OpenRouter API key** - Edit `/opt/thesisapp/.env` to enable AI features
3. **Set up SSL** - Use certbot for HTTPS if you have a domain
4. **Monitor logs** - Check `/var/log/nginx/` and Docker logs regularly
5. **Keep updated** - Run `apt update && apt upgrade` periodically
6. **Backup database** - The SQLite DB is at `/opt/thesisapp/src/data/thesis_app.db`

---

## 💡 Resource Estimates

With your server specs (6c/12t, 32GB RAM):
- **Web container**: ~512MB-2GB RAM
- **Redis**: ~64MB RAM  
- **Celery worker**: ~512MB-1GB RAM
- **Analyzer containers**: ~1-2GB each (4 total)
- **Total**: ~8-12GB RAM usage with all services

Your server has plenty of headroom for this workload.
