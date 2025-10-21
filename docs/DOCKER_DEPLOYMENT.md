# Docker Deployment Guide

This guide explains how to run ThesisApp in Docker containers.

## Prerequisites

- Docker Engine 20.10+ or Docker Desktop
- Docker Compose V2 (comes with Docker Desktop)
- At least 8GB RAM available for Docker
- 10GB disk space

## Quick Start

1. **Clone the repository** (if not already done):
   ```bash
   git clone <repository-url>
   cd ThesisAppRework
   ```

2. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env and add your OPENROUTER_API_KEY
   ```

3. **Build and start all services**:
   ```bash
   docker compose up -d
   ```

4. **Access the application**:
   - Web UI: http://localhost:5000
   - Health check: http://localhost:5000/health
   - API docs: http://localhost:5000/api/docs (if available)

5. **View logs**:
   ```bash
   # All services
   docker compose logs -f
   
   # Specific service
   docker compose logs -f web
   docker compose logs -f celery-worker
   ```

## Services Overview

The Docker Compose stack includes:

- **web**: Flask web application (port 5000)
- **celery-worker**: Background task processor
- **redis**: Message broker and cache (port 6379)
- **analyzer-gateway**: WebSocket gateway (port 8765)
- **static-analyzer**: Static code analysis (port 2001)
- **dynamic-analyzer**: Dynamic security testing (port 2002)
- **performance-tester**: Performance benchmarking (port 2003)
- **ai-analyzer**: AI-powered code review (port 2004)

## Configuration

### Environment Variables

Edit `.env` file with your configuration:

```bash
# Flask Configuration
FLASK_ENV=production              # or development
SECRET_KEY=your-secret-key        # Change this!
LOG_LEVEL=INFO                    # DEBUG, INFO, WARNING, ERROR

# Database (SQLite in container)
DATABASE_URL=sqlite:////app/src/data/thesis_app.db

# Redis
REDIS_URL=redis://redis:6379/0

# OpenRouter API (required for AI analysis)
OPENROUTER_API_KEY=your-key-here
OPENROUTER_ALLOW_ALL_PROVIDERS=true

# Celery Workers
CELERY_WORKER_CONCURRENCY=2       # Adjust based on CPU cores
```

### Volume Mounts

Data persists in the following locations:

- `./generated/apps`: AI-generated applications for analysis
- `./results`: Analysis results and reports
- `./logs`: Application logs
- `./src/data`: SQLite database (if using SQLite)
- `redis-data`: Redis persistence (Docker volume)

## Common Commands

### Start Services
```bash
# Start all services
docker compose up -d

# Start specific service
docker compose up -d web

# Start with logs visible
docker compose up
```

### Stop Services
```bash
# Stop all services
docker compose down

# Stop and remove volumes (WARNING: deletes data)
docker compose down -v
```

### View Status
```bash
# Check service status
docker compose ps

# Check service health
docker compose ps --format json | jq
```

### Scale Services
```bash
# Run multiple workers
docker compose up -d --scale celery-worker=3
```

### Rebuild Services
```bash
# Rebuild after code changes
docker compose build

# Rebuild specific service
docker compose build web

# Rebuild without cache
docker compose build --no-cache
```

### Execute Commands
```bash
# Run Flask shell
docker compose exec web python -c "from app import create_app; app = create_app(); app.app_context().push()"

# Initialize database
docker compose exec web python src/init_db.py

# Run tests (if available)
docker compose exec web pytest
```

### View Logs
```bash
# All services (follow)
docker compose logs -f

# Specific service (last 100 lines)
docker compose logs --tail=100 web

# Multiple services
docker compose logs -f web celery-worker
```

## Troubleshooting

### Service Won't Start

1. **Check logs**:
   ```bash
   docker compose logs <service-name>
   ```

2. **Check health status**:
   ```bash
   docker compose ps
   ```

3. **Verify ports are available**:
   ```bash
   # Check if ports are already in use
   netstat -tulpn | grep -E '5000|6379|8765|200[1-4]'
   ```

### Database Issues

1. **Reset database**:
   ```bash
   # Stop services
   docker compose down
   
   # Remove database file
   rm -rf src/data/thesis_app.db
   
   # Restart and reinitialize
   docker compose up -d
   docker compose exec web python src/init_db.py
   ```

### Redis Connection Issues

1. **Check Redis is running**:
   ```bash
   docker compose ps redis
   docker compose exec redis redis-cli ping
   ```

2. **Restart Redis**:
   ```bash
   docker compose restart redis
   ```

### Analyzer Services Issues

1. **Check analyzer gateway**:
   ```bash
   docker compose logs analyzer-gateway
   ```

2. **Restart all analyzers**:
   ```bash
   docker compose restart static-analyzer dynamic-analyzer performance-tester ai-analyzer
   ```

### Docker Desktop on Windows

If you encounter permission issues:

1. **Enable WSL 2 backend** (recommended):
   - Settings → General → Use WSL 2 based engine

2. **Increase resources**:
   - Settings → Resources → Advanced
   - Allocate at least 8GB RAM and 4 CPU cores

3. **File sharing**:
   - Settings → Resources → File Sharing
   - Add project directory

### Container Logs

View detailed container logs:

```bash
# Show last 200 lines
docker compose logs --tail=200 web

# Follow logs in real-time
docker compose logs -f --tail=50 web celery-worker

# Show timestamps
docker compose logs -t web
```

## Production Deployment

### Database

For production, use PostgreSQL instead of SQLite:

1. Add PostgreSQL service to `docker-compose.yml`:
   ```yaml
   postgres:
     image: postgres:15-alpine
     environment:
       POSTGRES_DB: thesisapp
       POSTGRES_USER: thesisapp
       POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
     volumes:
       - postgres-data:/var/lib/postgresql/data
   ```

2. Update `.env`:
   ```bash
   DATABASE_URL=postgresql://thesisapp:password@postgres:5432/thesisapp
   ```

### Security

1. **Change default secrets**:
   ```bash
   # Generate random secret key
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

2. **Use Docker secrets** (Swarm mode):
   ```yaml
   secrets:
     secret_key:
       external: true
   ```

3. **Enable HTTPS** (use nginx/traefik as reverse proxy)

4. **Limit resource usage** (already configured in compose file)

### Monitoring

1. **Health checks**: All services have built-in health checks

2. **Prometheus metrics** (add if needed):
   ```yaml
   prometheus:
     image: prom/prometheus
     volumes:
       - ./prometheus.yml:/etc/prometheus/prometheus.yml
   ```

3. **Logging**: Consider using ELK stack or similar

## Development Mode

For local development with hot-reload:

1. **Override compose file**:
   ```yaml
   # docker-compose.override.yml
   version: '3.8'
   services:
     web:
       volumes:
         - ./src:/app/src
       environment:
         - FLASK_ENV=development
       command: python src/main.py --reload
   ```

2. **Start with override**:
   ```bash
   docker compose up -d
   ```

## Maintenance

### Backup Data

```bash
# Backup database
docker compose exec web tar czf /tmp/backup.tar.gz /app/src/data
docker compose cp web:/tmp/backup.tar.gz ./backup.tar.gz

# Backup volumes
docker run --rm -v thesis_redis-data:/data -v $(pwd):/backup alpine tar czf /backup/redis-data.tar.gz /data
```

### Update Images

```bash
# Pull latest base images
docker compose pull

# Rebuild with latest images
docker compose build --pull

# Restart with new images
docker compose up -d
```

### Clean Up

```bash
# Remove stopped containers
docker compose down

# Remove unused images
docker image prune -a

# Remove unused volumes
docker volume prune

# Complete cleanup (WARNING: removes all Docker resources)
docker system prune -a --volumes
```

## Support

For issues and questions:
- Check logs: `docker compose logs -f`
- Review documentation in `docs/` directory
- Open GitHub issue with logs and configuration

## Next Steps

After successful deployment:

1. **Initialize database**: `docker compose exec web python src/init_db.py`
2. **Create admin user** (if applicable)
3. **Configure analyzers** via web UI
4. **Run test analysis** to verify setup
5. **Set up backups** and monitoring
