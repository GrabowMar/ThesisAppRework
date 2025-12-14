# Deployment Guide

Production deployment for ThesisAppRework.

## Deployment Options

| Option | Complexity | Best For |
|--------|------------|----------|
| Single Server | Low | Development, small scale |
| Docker Compose | Medium | Production, single host |
| Kubernetes | High | Scale, high availability |

## Single Server Deployment

### Requirements

- Ubuntu 22.04+ / Windows Server 2022
- Python 3.10+
- Docker Engine 24+
- 4GB RAM minimum, 8GB recommended
- 50GB disk space

### Setup

```bash
# Clone repository
git clone https://github.com/GrabowMar/ThesisAppRework.git
cd ThesisAppRework

# Setup Python environment
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with production values

# Initialize database
python src/init_db.py

# Build analyzer containers
cd analyzer
docker compose build
cd ..
```

### Production Configuration

`.env` settings for production:

```bash
# Flask
FLASK_DEBUG=0
SECRET_KEY=<generate-secure-key>

# Logging
LOG_LEVEL=INFO

# Analyzers
ANALYZER_ENABLED=true
ANALYZER_AUTO_START=true

# Timeouts
STATIC_ANALYSIS_TIMEOUT=600
SECURITY_ANALYSIS_TIMEOUT=900
PERFORMANCE_TIMEOUT=300

# API
OPENROUTER_API_KEY=sk-...
```

### Running with Gunicorn

```bash
# Install gunicorn
pip install gunicorn

# Run
gunicorn -w 4 -b 0.0.0.0:5000 'src.app.factory:create_app()'
```

### Systemd Service

`/etc/systemd/system/thesisapp.service`:

```ini
[Unit]
Description=ThesisAppRework Flask Application
After=network.target docker.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/ThesisAppRework
Environment="PATH=/opt/ThesisAppRework/.venv/bin"
ExecStart=/opt/ThesisAppRework/.venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 'src.app.factory:create_app()'
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable thesisapp
sudo systemctl start thesisapp
```

## Docker Compose Deployment

### Full Stack

```bash
# Build and start all services
docker compose -f docker-compose.yml up -d --build

# Check status
docker compose ps

# View logs
docker compose logs -f
```

### Services

| Service | Port | Description |
|---------|------|-------------|
| flask | 5000 | Web application |
| static-analyzer | 2001 | Static analysis |
| dynamic-analyzer | 2002 | Security scanning |
| performance-tester | 2003 | Load testing |
| ai-analyzer | 2004 | AI analysis |
| redis | 6379 | Task queue |

### Scaling Analyzers

```bash
# Scale specific service
docker compose up -d --scale static-analyzer=2

# Resource adjustment in docker-compose.yml
services:
  static-analyzer:
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '2.0'
```

## Nginx Reverse Proxy

`/etc/nginx/sites-available/thesisapp`:

```nginx
upstream flask {
    server 127.0.0.1:5000;
}

server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://flask;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /socket.io {
        proxy_pass http://flask;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    client_max_body_size 100M;
}
```

### SSL with Certbot

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## Monitoring

### Health Checks

```bash
# Application health
curl http://localhost:5000/api/health

# Analyzer health
curl http://localhost:5000/api/health/analyzers

# CLI health check
python analyzer/analyzer_manager.py health
```

### Logging

Logs location:
- Flask: `logs/app.log`
- Analyzers: `docker compose logs <service>`

Log rotation with logrotate:

```
/opt/ThesisAppRework/logs/*.log {
    daily
    rotate 14
    compress
    missingok
    notifempty
}
```

### Metrics

Consider integrating:
- Prometheus + Grafana for metrics
- Sentry for error tracking
- ELK stack for log aggregation

## Backup

### Database

```bash
# SQLite backup
cp src/data/thesis_app.db backups/thesis_app_$(date +%Y%m%d).db
```

### Results

```bash
# Backup results directory
tar -czf backups/results_$(date +%Y%m%d).tar.gz results/
```

### Automated Backup Script

```bash
#!/bin/bash
BACKUP_DIR=/opt/backups
DATE=$(date +%Y%m%d)

# Database
cp /opt/ThesisAppRework/src/data/thesis_app.db $BACKUP_DIR/db_$DATE.db

# Results
tar -czf $BACKUP_DIR/results_$DATE.tar.gz /opt/ThesisAppRework/results/

# Cleanup old backups (keep 30 days)
find $BACKUP_DIR -mtime +30 -delete
```

## Security Checklist

- [ ] Change default `SECRET_KEY`
- [ ] Enable HTTPS (SSL/TLS)
- [ ] Configure firewall (ufw/iptables)
- [ ] Restrict database file permissions
- [ ] Set up API rate limiting
- [ ] Enable log monitoring
- [ ] Regular security updates
- [ ] Backup strategy in place

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Container fails to start | Check `docker compose logs <service>` |
| Database locked | Stop all processes, restart Flask |
| Out of memory | Increase container limits, add swap |
| Port conflict | Check `netstat -tlnp`, stop conflicting service |
| Analyzer timeout | Increase `*_TIMEOUT` env variables |

### Recovery Commands

```bash
# Restart all services
docker compose restart

# Rebuild specific container
docker compose up -d --build static-analyzer

# Fast incremental rebuild (30-90s, uses cache)
./start.ps1 -Mode Rebuild

# Clean rebuild (12-18min, no cache)
./start.ps1 -Mode CleanRebuild

# Fix stuck tasks
python scripts/fix_task_statuses.py

# Maintenance cleanup (7-day grace period for orphan apps)
./start.ps1 -Mode Maintenance

# Full wipeout (WARNING: removes all data)
./start.ps1 -Mode Wipeout

# Reset admin password
./start.ps1 -Mode Password
```

## Orchestrator Commands Reference

| Mode | Description |
|------|-------------|
| `Start` | Full stack: Flask + Analyzer containers |
| `Stop` | Stop all services |
| `Dev` | Development mode (Flask only) |
| `Status` | Show status dashboard |
| `Logs` | Tail Flask and analyzer logs |
| `Rebuild` | Fast incremental container rebuild |
| `CleanRebuild` | Full rebuild without cache |
| `Maintenance` | Run manual cleanup (7-day orphan grace period) |
| `Reload` | Hot reload for code changes |
| `Wipeout` | Full reset (WARNING: data loss) |
| `Password` | Reset admin password |

## Related

- [Architecture](./ARCHITECTURE.md)
- [Background Services](./BACKGROUND_SERVICES.md)
- [API Reference](./api-reference.md)
- [Development Guide](./development-guide.md)
- [Troubleshooting](./TROUBLESHOOTING.md)
