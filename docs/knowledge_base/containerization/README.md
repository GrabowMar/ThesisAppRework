# Containerization & Docker

## Quick Start

```bash
# Build and start all services
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f web

# Stop all
docker compose down
```

## Architecture

The platform runs in Docker with multiple services:
- **web**: Flask application (port 5000)
- **celery-worker**: Background task processor
- **redis**: Task queue and cache
- **analyzer services**: Microservices for code analysis (ports 2001-2004)

## Generated Apps Containerization

All generated applications include complete Docker infrastructure:

```
generated/apps/<app_id>/
├── backend/
│   └── Dockerfile          # Python/Flask backend
├── frontend/
│   └── Dockerfile          # React/Vite frontend
├── docker-compose.yml      # Orchestration config
├── .env                    # Environment config
└── nginx.conf              # Reverse proxy config
```

### Port Allocation

Ports are automatically assigned to avoid conflicts:
- **Backend**: Starting from 5001 (incremental)
- **Frontend**: Starting from 8001 (incremental)

Managed by `PortAllocationService` in `src/app/services/port_allocation_service.py`.

## Container Management via UI

The web interface provides full Docker lifecycle management:

- **Start/Stop/Restart**: Control individual containers or entire apps
- **Build**: Rebuild images after code changes
- **Logs**: View real-time container logs
- **Status**: Monitor health and resource usage

Available in: Dashboard → Applications → Container Actions

## Deployment

### Production Build

```bash
# Build for production
docker compose -f docker-compose.yml -f docker-compose.prod.yml build

# Deploy
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Environment Variables

Configure via `.env`:
```env
FLASK_ENV=production
SECRET_KEY=<random-secure-key>
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
```

## Troubleshooting

**Ports in use**: Check `docker compose ps` and stop conflicting containers
**Build failures**: Run `docker compose build --no-cache`
**Network issues**: Restart Docker daemon
**Volume permissions**: Run `chmod -R 777 generated/` on Linux
