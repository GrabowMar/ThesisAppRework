# Deployment

## Quick Deploy

```bash
# Clone repo
git clone <repo-url>
cd ThesisAppRework

# Set up environment
cp .env.example .env
nano .env  # Edit SECRET_KEY and other settings

# Build and start
docker compose up -d

# Create admin user
docker compose exec web python scripts/create_admin.py

# Access
# http://your-server:5000
```

## Production Checklist

- [ ] Generate secure `SECRET_KEY`
- [ ] Set `FLASK_ENV=production`
- [ ] Enable HTTPS (`SESSION_COOKIE_SECURE=true`)
- [ ] Configure firewall (allow 80, 443, block 5000)
- [ ] Set up reverse proxy (nginx/Caddy)
- [ ] Configure SSL certificates (Let's Encrypt)
- [ ] Set up backup system for database
- [ ] Enable monitoring and logging
- [ ] Disable debug mode
- [ ] Review CORS settings

## OVH/Cloud Deployment

### SSH Access
```bash
ssh -i ~/.ssh/id_ed25519_ovh ubuntu@<server-ip>
```

### Deploy Script
```bash
# On server
cd ~/ThesisAppRework
git pull
docker compose down
docker compose build
docker compose up -d
```

### Environment Variables

Critical production settings:
```env
FLASK_ENV=production
SECRET_KEY=<64-char-random-string>
SESSION_COOKIE_SECURE=true
REGISTRATION_ENABLED=false
CELERY_BROKER_URL=redis://redis:6379/0
OPENROUTER_API_KEY=<your-key>
```

## Reverse Proxy (nginx)

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket support
    location /ws/ {
        proxy_pass http://localhost:8765;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## Monitoring

### Health Check
```bash
curl http://localhost:5000/health
```

### Logs
```bash
docker compose logs -f web
docker compose logs -f celery-worker
```

### Service Status
```bash
docker compose ps
python analyzer/analyzer_manager.py health
```

## Backup

```bash
# Database backup
docker compose exec web tar -czf /tmp/backup.tar.gz /app/src/data/
docker compose cp web:/tmp/backup.tar.gz ./backup-$(date +%Y%m%d).tar.gz

# Generated apps backup
tar -czf generated-backup-$(date +%Y%m%d).tar.gz generated/apps/
```

## Troubleshooting

**Port conflicts**: Change ports in `docker-compose.yml`
**Permission errors**: Run `sudo chown -R $USER:$USER .`
**Database locked**: Restart services `docker compose restart`
**Out of disk space**: Clean up old containers and images
