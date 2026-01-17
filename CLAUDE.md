# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ThesisAppRework is a Flask-based platform for analyzing AI-generated applications. It evaluates code quality, security vulnerabilities, performance, and requirements compliance across multiple AI models (OpenAI, Anthropic, etc.).

**Core Architecture:**
- **Flask Web App** (`src/app/`) - Web UI, REST API, SQLite database
- **Analyzer Microservices** (`analyzer/services/`) - Docker containers for static, dynamic, performance, and AI analysis
- **Background Services** - Task execution via Celery, pipeline orchestration, maintenance (all in `src/app/services/`)

Communication between Flask and analyzers uses **WebSocket protocol** defined in `analyzer/shared/protocol.py`.

## Commands

### Docker Stack (Recommended)

```bash
# Start complete stack (Flask + Redis + Celery + Analyzers)
docker compose up -d

# View logs
docker compose logs -f web
docker compose logs -f celery-worker

# Check status
docker compose ps

# Stop everything
docker compose down
```

### PowerShell Orchestrator (Windows Development)

```powershell
# Start full stack with live monitoring
./start.ps1 -Mode Start

# Quick dev mode without analyzers (faster iteration)
./start.ps1 -Mode Dev -NoAnalyzer

# Rebuild containers (fast, uses cache)
./start.ps1 -Mode Rebuild

# Full clean rebuild
./start.ps1 -Mode CleanRebuild

# Manual maintenance (cleanup old tasks/apps)
./start.ps1 -Mode Maintenance

# Stop all services
./start.ps1 -Mode Stop
```

### Local Development (Alternative)

```bash
# Setup Python environment
python -m venv .venv
.venv\Scripts\Activate.ps1   # Windows
source .venv/bin/activate     # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Initialize database
python src/init_db.py

# Run Flask locally
python src/main.py
```

**Note:** Analyzers still require Docker containers even in local dev mode.

### Testing

```bash
# Fast unit tests (recommended for development)
pytest -m "not integration and not slow and not analyzer"

# Run specific test file
pytest tests/unit/test_task_service.py -v

# Run specific test
pytest tests/unit/test_task_service.py::test_create_task -v

# Integration tests (requires Docker analyzers)
pytest tests/integration/ -m integration

# Smoke tests (critical paths)
pytest tests/smoke/

# All tests
pytest
```

**Test markers** (defined in `pytest.ini`):
- `unit` - Fast unit tests
- `integration` - Integration tests (requires Docker)
- `slow` - Slow tests (>1s)
- `analyzer` - Tests requiring analyzer services
- `smoke` - Fast smoke tests for critical paths
- `api` - REST API endpoint tests
- `websocket` - WebSocket protocol tests

**VS Code:** Use Testing panel (Ctrl+Shift+T) for interactive test explorer.

## Architecture Patterns

### Service Locator Pattern

All business logic lives in `src/app/services/`. Services are centrally registered via `ServiceLocator` in `src/app/services/service_locator.py`:

```python
from app.services.service_locator import ServiceLocator

# Access services via ServiceLocator
model_svc = ServiceLocator.get_model_service()
docker_mgr = ServiceLocator.get_docker_manager()
```

**Adding a new service:**
1. Create service class in `src/app/services/`
2. Register in `ServiceLocator._register_core_services()`
3. Add typed getter method to `ServiceLocator`

### Model Slugs

Models are identified by slugs: `{provider}_{model-name}` (e.g., `anthropic_claude-3-5-haiku`).

Results are stored at: `results/{model_slug}/app{N}/task_{task_id}/`

### Status Enums

Always use enums from `src/app/constants.py`:

```python
from app.constants import AnalysisStatus, AnalysisType

task.status = AnalysisStatus.RUNNING
```

**Key enums:**
- `AnalysisStatus` - CREATED, PENDING, RUNNING, COMPLETED, PARTIAL_SUCCESS, FAILED, CANCELLED
- `AnalysisType` - CUSTOM, UNIFIED, SECURITY, PERFORMANCE, etc.
- `GenerationMode` - GUARDED (structured scaffolding), UNGUARDED (full AI control)

### Time Handling

Always use timezone-aware UTC datetimes:

```python
from app.utils.time import utc_now

created_at = utc_now()
```

### Database Operations

```python
from app.extensions import db
from app.models import AnalysisTask

task = AnalysisTask.query.filter_by(task_id=task_id).first()
db.session.add(new_task)
db.session.commit()
```

**Key models** (in `src/app/models/`):
- `AnalysisTask` - Analysis tracking
- `GeneratedApplication` - AI-generated apps
- `AnalysisPipeline` - Automation pipelines
- `User` - Authentication
- `PortConfiguration` - Port management

### Background Task Flow

Tasks flow through states: `PENDING` → `RUNNING` → `COMPLETED`/`FAILED`

**Execution models:**
1. **TaskExecutionService** - In-process polling (dev mode, polls every 2-5s)
2. **Celery Worker** - Production distributed processing (Docker stack)

The `PipelineExecutionService` handles automation pipelines (only runs in Celery worker to prevent race conditions).

## Code Organization

### Routes
- `src/app/routes/` - Web UI routes
- `src/app/routes/api/` - REST API endpoints

**API Pattern:**
```python
@api_bp.route('/analysis/<task_id>', methods=['GET'])
@require_api_key
def get_analysis(task_id):
    # Implementation
```

### Templates
- `src/templates/` - Jinja2 templates with HTMX for dynamic updates

### Analyzer Configs
- `analyzer/configs/` - Tool configurations (Bandit, Semgrep, ESLint, etc.)

### WebSocket Protocol

Flask communicates with analyzer microservices via WebSocket. Key message types in `analyzer/shared/protocol.py`:
- `ANALYSIS_REQUEST` / `ANALYSIS_RESULT`
- `PROGRESS_UPDATE`
- `ERROR`
- `HEARTBEAT`

Service types: `SECURITY_ANALYZER`, `PERFORMANCE_TESTER`, `AI_ANALYZER`, etc.

## Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `OPENROUTER_API_KEY` | AI analyzer API key | Yes | - |
| `SECRET_KEY` | Flask secret key | Yes (prod) | dev-secret-key |
| `FLASK_ENV` | Environment | No | development |
| `DATABASE_URL` | Database URI | No | sqlite:///src/data/thesis_app.db |
| `ANALYZER_ENABLED` | Enable analyzers | No | true |
| `LOG_LEVEL` | Logging level | No | INFO |
| `CELERY_BROKER_URL` | Redis URL for Celery | No | redis://redis:6379/0 |
| `REGISTRATION_ENABLED` | Allow user registration | No | false |
| `IN_DOCKER` | Running in Docker | Auto-set | - |

## Key Design Decisions

### Flask Factory Pattern
Application is created via `create_app()` in `src/app/factory.py`. This enables multiple app instances for testing and supports different configurations.

### Docker-First Architecture
- Main stack: `docker-compose.yml` (web, redis, celery-worker, analyzers)
- Analyzer services: Independent containers with WebSocket endpoints
- Generated apps: Run in isolated containers on `thesis-apps-network`

### Celery Integration
- **Web container**: ENABLE_PIPELINE_SERVICE=false (prevents race conditions)
- **Celery worker**: ENABLE_PIPELINE_SERVICE=true (only container processing pipelines)
- Prefork mode: Pipeline service starts via Celery signals after fork

### Result Storage
Analysis results are stored in filesystem:
```
results/{model_slug}/app{N}/task_{task_id}/
├── summary.json
├── static_analysis.json
├── dynamic_analysis.json
├── performance_test.json
└── ai_analysis.json
```

### Startup Task Cleanup
On app startup, stuck/old tasks are cleaned up:
- RUNNING tasks >2 hours old → marked FAILED
- PENDING tasks >4 hours old → marked CANCELLED
- Configurable via `STARTUP_CLEANUP_*` env vars

### Auto-Sync Generated Apps
Filesystem apps in `generated/apps/{model_slug}/app{N}/` are automatically synced to database on startup.

## Common Pitfalls

1. **Don't import `current_app` at module level** - Use within request context or pass app instance
2. **Read files before editing** - Always use Read tool first, then Edit (never Write existing files)
3. **Model slugs must match format** - `{provider}_{model-name}` with underscores
4. **Time must be timezone-aware** - Use `utc_now()` from `app.utils.time`
5. **Services must be registered** - Add to `ServiceLocator._register_core_services()`
6. **WebSocket service selection** - Celery-backed by default, mock for tests
7. **Pipeline service race conditions** - Only enable in ONE container (celery-worker in Docker stack)

## API Authentication

All REST endpoints require Bearer token authentication:

```bash
curl -X POST http://localhost:5000/api/analysis/run \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"model_slug": "openai_gpt-4", "app_number": 1, "analysis_type": "unified"}'
```

Generate tokens via **User → API Access** in the web UI.

## Tech Stack

- **Backend**: Flask 3.x, SQLAlchemy, Flask-SocketIO
- **Database**: SQLite (development), supports PostgreSQL (production)
- **Task Queue**: Celery + Redis
- **Containers**: Docker, Docker Compose
- **Analysis Tools**: Bandit, Semgrep, ESLint, OWASP ZAP, Locust, OpenRouter API
- **Testing**: pytest, pytest-asyncio
- **Frontend**: Jinja2 templates, HTMX, Tailwind CSS
