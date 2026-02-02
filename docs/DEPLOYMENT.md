# ThesisAppRework Deployment Guide

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Git
- Linux server (Ubuntu recommended)

### Fresh Deployment

```bash
# 1. Clone repository
git clone https://github.com/GrabowMar/ThesisAppRework.git
cd ThesisAppRework

# 2. Setup environment
cp .env.example .env

# 3. Add your OpenRouter API key to .env
echo "OPENROUTER_API_KEY=your-key-here" >> .env

# 4. Detect and set Docker GID (required for container management)
DOCKER_GID=$(stat -c '%g' /var/run/docker.sock)
echo "DOCKER_GID=$DOCKER_GID" >> .env

# 5. Create required directories with proper permissions
mkdir -p generated/apps generated/raw/responses generated/metadata results logs instance src/data
chmod -R 777 generated results logs instance src/data

# 6. Create Docker network
docker network create thesis-apps-network 2>/dev/null || true

# 7. Deploy
docker compose up -d --build
```

### Verify Deployment

```bash
# Check all containers are healthy
docker compose ps

# Check web container can access Docker
docker compose exec web python -c "import docker; print(docker.from_env().ping())"

# Check logs for errors
docker compose logs --tail=50 web celery-worker
```

### Create Admin User

```bash
docker compose exec -T web python -c "
from app.factory import create_app
from app.models.user import User
from app.extensions import db
app = create_app()
with app.app_context():
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(username='admin', email='admin@local.dev')
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print('Admin created: admin / admin123')
    else:
        print('Admin already exists')
"
```

## Common Issues

### Docker Permission Denied
**Symptom:** `permission denied while trying to connect to the Docker daemon socket`

**Fix:**
```bash
# Get Docker socket GID
DOCKER_GID=$(stat -c '%g' /var/run/docker.sock)
echo "DOCKER_GID=$DOCKER_GID" >> .env
docker compose up -d --force-recreate web celery-worker
```

### Pipeline Not Processing
**Symptom:** Pipeline stuck in "running" state, no generation happening

**Cause:** Web and celery-worker using separate databases

**Fix:** Ensure `./instance:/app/instance` volume is mounted in both web and celery-worker services in docker-compose.yml

### Directory Permission Errors
**Symptom:** `Permission denied: '/app/generated/...'`

**Fix:**
```bash
chmod -R 777 generated results logs instance src/data
docker compose restart
```

## Service Ports

| Service | Port | Description |
|---------|------|-------------|
| nginx | 80, 443 | Web UI (HTTP/HTTPS) |
| web | 5000 | Flask app (internal) |
| redis | 6379 | Task queue |
| analyzer-gateway | 8765 | WebSocket gateway |
| static-analyzer | 2001 | Static code analysis |
| dynamic-analyzer | 2002 | Dynamic security testing |
| performance-tester | 2003 | Performance benchmarks |
| ai-analyzer | 2004 | AI code review |

## Updating

```bash
cd /home/ubuntu/ThesisAppRework
git pull origin main
docker compose up -d --build
```

## Full Reset

```bash
# Stop everything
docker compose down -v

# Clean Docker
docker system prune -af --volumes

# Remove data
rm -rf generated/* results/* logs/* instance/*

# Redeploy
docker compose up -d --build
```
