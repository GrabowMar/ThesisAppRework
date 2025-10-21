# ThesisAppRework Documentation

Platform for analyzing AI-generated applications with security, performance, and quality analysis.

## Quick Links

- [Architecture](architecture.md) - System design and components
- [Quick Start](QUICKSTART.md) - Get up and running in 5 minutes
- [Operations](OPERATIONS.md) - Day-to-day operations guide

## Topics

### [Authentication](authentication/)
User authentication, API tokens, session management, security best practices.

### [Containerization](containerization/)
Docker setup, container management, generated app containerization, port allocation.

### [Dashboard](dashboard/)
UI overview, real-time updates, tabbed interface, container controls.

### [Deployment](deployment/)
Production deployment, OVH/cloud setup, reverse proxy, monitoring, backups.

### [Development](development/)
Project structure, patterns, API development, database, debugging, testing.

### [Generation](generation/)
Application generation system, templates, validation, Docker infrastructure.

### [OpenRouter](openrouter/)
AI model integration, configuration, research mode, model comparison.

### [Testing](testing/)
Test suite, analyzer testing, coverage, CI/CD integration.

## Core Workflows

### Generate Application
```bash
# Start services
docker compose up -d

# Generate app
curl -X POST http://localhost:5000/api/gen/generate \
  -H "Content-Type: application/json" \
  -d '{"model": "openai_gpt-4", "template_id": 1}'
```

### Run Analysis
```bash
# Start analyzers
python analyzer/analyzer_manager.py start

# Analyze app
python analyzer/analyzer_manager.py analyze openai_gpt-4 1 security --tools bandit
```

### Deploy to Production
```bash
# Set environment
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")

# Build and deploy
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Create admin
docker compose exec web python scripts/create_admin.py
```

## Architecture Overview

```
┌─────────────────────────────────────────────┐
│           Flask Web Application             │
│  (Routes, Services, Models, Templates)      │
└─────────────┬───────────────────────────────┘
              │
              ├─> Redis (Task Queue)
              ├─> Celery Workers (Background Jobs)
              ├─> SQLite/PostgreSQL (Database)
              │
              └─> Analyzer Services (Docker)
                  ├─> Static Analyzer (2001)
                  ├─> Dynamic Analyzer (2002)
                  ├─> Performance Tester (2003)
                  └─> AI Analyzer (2004)
```

## Key Technologies

- **Backend**: Flask, Celery, SQLAlchemy
- **Frontend**: Bootstrap 5, HTMX, Jinja2
- **Database**: SQLite (dev), PostgreSQL (prod)
- **Queue**: Redis
- **Containers**: Docker, Docker Compose
- **AI**: OpenRouter API (multiple models)
- **Analysis**: Bandit, Safety, PyLint, ESLint, OWASP ZAP, Locust

## Environment Variables

Critical settings in `.env`:

```env
# Core
FLASK_ENV=production
SECRET_KEY=<random-64-char-string>

# Authentication
REGISTRATION_ENABLED=false
SESSION_COOKIE_SECURE=true
SESSION_LIFETIME=86400

# OpenRouter
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_ALLOW_ALL_PROVIDERS=true

# Services
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
```

## Support

- **Issues**: Check logs in `logs/` directory
- **Errors**: Review error traces in console output
- **Database**: Inspect with `sqlite3 src/data/thesis_app.db`
- **Containers**: Check status with `docker compose ps`

## Project Status

✅ Authentication system complete  
✅ Docker containerization complete  
✅ Simple generation system active  
✅ Analyzer services operational  
✅ Dashboard and UI complete  
✅ Production deployment tested  

## Next Steps

1. Set up your environment (see [Quick Start](QUICKSTART.md))
2. Configure authentication (see [Authentication](authentication/))
3. Generate your first app (see [Generation](generation/))
4. Run analysis (see [Testing](testing/))
5. Deploy to production (see [Deployment](deployment/))
