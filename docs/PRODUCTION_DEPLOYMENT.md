# 🚀 Production Deployment Guide

Complete guide for deploying ThesisAppRework to production with HTTPS and security hardening.

## ✅ Pre-Deployment Checklist

### Security Configuration
- [x] ✅ Secure SECRET_KEY generated and set
- [x] ✅ Admin user created with strong password
- [x] ✅ Registration disabled (`REGISTRATION_ENABLED=false`)
- [ ] ⚠️ Enable HTTPS and set `SESSION_COOKIE_SECURE=true`
- [ ] Set up firewall rules
- [ ] Configure reverse proxy (nginx/Caddy)
- [ ] Set up SSL/TLS certificates (Let's Encrypt)

### Application Configuration
- [x] ✅ Database initialized
- [x] ✅ All dependencies installed
- [x] ✅ Docker containers built
- [ ] Configure production logging
- [ ] Set up monitoring (optional)
- [ ] Configure backup strategy

### Testing
- [x] ✅ Login system tested and working
- [x] ✅ All routes protected
- [ ] Test HTTPS redirect
- [ ] Test session timeout
- [ ] Load testing (optional)

---

## 🔒 HTTPS Setup with Nginx

### 1. Install Nginx and Certbot

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install nginx certbot python3-certbot-nginx

# CentOS/RHEL
sudo yum install nginx certbot python3-certbot-nginx
```

### 2. Nginx Configuration

Create `/etc/nginx/sites-available/thesisapp`:

```nginx
# Redirect HTTP to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name your-domain.com www.your-domain.com;
    
    # Let's Encrypt verification
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }
    
    # Redirect all other HTTP to HTTPS
    location / {
        return 301 https://$server_name$request_uri;
    }
}

# HTTPS Server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name your-domain.com www.your-domain.com;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    
    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    # Logging
    access_log /var/log/nginx/thesisapp_access.log;
    error_log /var/log/nginx/thesisapp_error.log;
    
    # Max upload size
    client_max_body_size 50M;
    
    # Proxy to Flask application
    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 300s;
    }
    
    # Static files (if serving directly)
    location /static/ {
        alias /app/src/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

### 3. Enable Site and Get SSL Certificate

```bash
# Enable the site
sudo ln -s /etc/nginx/sites-available/thesisapp /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Get SSL certificate (interactive)
sudo certbot --nginx -d your-domain.com -d www.your-domain.com

# Reload nginx
sudo systemctl reload nginx

# Enable auto-renewal
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer
```

### 4. Update Application Configuration

Update `.env`:

```env
SESSION_COOKIE_SECURE=true
```

Restart containers:

```bash
docker compose restart web celery-worker
```

---

## 🔥 Firewall Configuration

### Using UFW (Ubuntu)

```bash
# Allow SSH (important!)
sudo ufw allow ssh

# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Allow Docker subnet (if needed)
sudo ufw allow from 172.17.0.0/16

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status
```

### Using firewalld (CentOS/RHEL)

```bash
# Allow services
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --permanent --add-service=ssh

# Reload
sudo firewall-cmd --reload

# Check status
sudo firewall-cmd --list-all
```

---

## 📊 Monitoring Setup (Optional)

### Application Logs

```bash
# View Flask logs
docker compose logs -f web

# View Celery logs
docker compose logs -f celery-worker

# View all logs
docker compose logs -f
```

### Health Monitoring

Set up automated health checks:

```bash
# Create health check script
cat > /usr/local/bin/check-thesisapp.sh << 'EOF'
#!/bin/bash
response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/health)
if [ $response -eq 200 ]; then
    echo "✅ ThesisApp healthy"
    exit 0
else
    echo "❌ ThesisApp unhealthy (HTTP $response)"
    # Optional: Send alert
    exit 1
fi
EOF

chmod +x /usr/local/bin/check-thesisapp.sh

# Add to crontab (every 5 minutes)
(crontab -l 2>/dev/null; echo "*/5 * * * * /usr/local/bin/check-thesisapp.sh >> /var/log/thesisapp-health.log 2>&1") | crontab -
```

---

## 💾 Backup Strategy

### Database Backup

```bash
# Create backup script
cat > /usr/local/bin/backup-thesisapp-db.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/backups/thesisapp"
DATE=$(date +%Y%m%d_%H%M%S)
DB_PATH="/path/to/ThesisAppRework/src/data/thesis_app.db"

mkdir -p $BACKUP_DIR
cp $DB_PATH $BACKUP_DIR/thesis_app_$DATE.db
gzip $BACKUP_DIR/thesis_app_$DATE.db

# Keep only last 30 days
find $BACKUP_DIR -name "thesis_app_*.db.gz" -mtime +30 -delete

echo "Backup completed: thesis_app_$DATE.db.gz"
EOF

chmod +x /usr/local/bin/backup-thesisapp-db.sh

# Daily backup at 2 AM
(crontab -l 2>/dev/null; echo "0 2 * * * /usr/local/bin/backup-thesisapp-db.sh >> /var/log/thesisapp-backup.log 2>&1") | crontab -
```

### Docker Volume Backup

```bash
# Backup script for Docker volumes
docker compose down
tar czf thesisapp-volumes-$(date +%Y%m%d).tar.gz src/data generated results logs
docker compose up -d
```

---

## 🔄 Deployment Process

### Initial Deployment

```bash
# 1. Clone repository
git clone https://github.com/YourUsername/ThesisAppRework.git
cd ThesisAppRework

# 2. Configure environment
cp .env.example .env
nano .env  # Update with production values

# 3. Build and start
docker compose build
docker compose up -d

# 4. Initialize database
docker compose exec web python src/init_db.py

# 5. Create admin user
docker compose exec web python scripts/create_admin.py

# 6. Verify health
curl http://localhost:5000/health
```

### Updates and Maintenance

```bash
# Pull latest changes
git pull origin main

# Rebuild containers
docker compose build

# Restart with zero downtime
docker compose up -d --no-deps --build web celery-worker

# Check status
docker compose ps
```

---

## 🛠️ Troubleshooting

### Container won't start

```bash
# Check logs
docker compose logs web

# Check resources
docker stats

# Restart
docker compose restart web
```

### Database locked

```bash
# Stop all services
docker compose down

# Start only web service
docker compose up web

# Check for file permissions
ls -la src/data/
```

### SSL Certificate Issues

```bash
# Renew certificates manually
sudo certbot renew

# Test renewal
sudo certbot renew --dry-run

# Check certificate expiry
sudo certbot certificates
```

---

## 📈 Performance Optimization

### Nginx Caching

Add to nginx location block:

```nginx
location /static/ {
    alias /app/src/static/;
    expires 1y;
    add_header Cache-Control "public, immutable";
    access_log off;
}
```

### Database Optimization

```bash
# Optimize SQLite database
docker compose exec web sqlite3 /app/src/data/thesis_app.db "VACUUM;"
docker compose exec web sqlite3 /app/src/data/thesis_app.db "ANALYZE;"
```

### Container Resource Limits

Update `docker-compose.yml` with appropriate limits based on your server:

```yaml
deploy:
  resources:
    limits:
      memory: 2G
      cpus: '1.0'
```

---

## 🎯 Post-Deployment Verification

Run through this checklist after deployment:

- [ ] Access site via HTTPS (https://your-domain.com)
- [ ] Verify HTTP redirects to HTTPS
- [ ] Test login with admin credentials
- [ ] Check all main pages load
- [ ] Verify SSL certificate is valid (A+ rating on SSL Labs)
- [ ] Test session timeout
- [ ] Check application health endpoint
- [ ] Verify logs are being written
- [ ] Test backup script
- [ ] Document admin credentials securely

---

## 📞 Support

For issues during deployment:

1. Check application logs: `docker compose logs -f`
2. Review nginx error log: `sudo tail -f /var/log/nginx/thesisapp_error.log`
3. Verify environment variables: `docker compose config`
4. Check health endpoint: `curl http://localhost:5000/health`

---

**Next Steps:**
1. Set up your domain's DNS to point to your server
2. Follow the HTTPS setup section above
3. Configure firewall rules
4. Set up automated backups
5. Configure monitoring

**Your application is ready for production deployment! 🚀**
