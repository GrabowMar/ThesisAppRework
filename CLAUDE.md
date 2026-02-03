# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ThesisAppRework is a research platform for analyzing AI-generated applications. It automates the complete workflow: generating web apps via LLM APIs, deploying them in Docker containers, and running comprehensive multi-faceted analysis (security, performance, code quality, AI review).

**Core Purpose**: Compare code quality, security, and performance across different LLM providers (OpenAI, Anthropic, Google, etc.) using standardized test cases.

## Essential Commands

### Development & Testing

```bash
# Start complete stack (Docker Compose - RECOMMENDED)
docker compose up -d

# Local development (Flask only, no background tasks)
./start.sh dev
# or Windows: ./start.ps1 -Mode Dev

# Run fast unit tests (skip integration/slow tests)
pytest -m "not integration and not slow and not analyzer"

# Run full pipeline test (generation + analysis end-to-end)
python run_full_pipeline_test.py

# Initialize/reset database
python src/init_db.py
```

### Service Management

```bash
# View logs
docker compose logs -f web
docker compose logs -f celery-worker

# Check service status
docker compose ps

# Restart services
docker compose restart

# Stop everything
docker compose down
```

### Analyzer Operations

```bash
# Located in analyzer/ directory
cd analyzer

# Start analyzer services
python analyzer_manager.py start

# Run comprehensive analysis
python analyzer_manager.py analyze <model_slug> <app_number> comprehensive

# Check analyzer health
python analyzer_manager.py health

# View analyzer logs
python analyzer_manager.py logs [service_name]
```

## Architecture Overview

### High-Level System Design

```
┌─────────────────────────────────────────────────────────────┐
│                 Docker Compose Stack                        │
├─────────────────────────────────────────────────────────────┤
│  Flask Web (:5000) • Redis • Celery Worker                 │
│         Routes • Services • Task Queue • DB                 │
└─────────────────────┬───────────────────────────────────────┘
                      │ WebSocket Communication
    ┌─────────────────┼─────────────────────┬────────────────┐
    ▼                 ▼                     ▼                ▼
┌────────┐      ┌────────┐           ┌────────┐       ┌────────┐
│ Static │      │Dynamic │           │  Perf  │       │   AI   │
│ :2001  │      │ :2002  │           │ :2003  │       │ :2004  │
└────────┘      └────────┘           └────────┘       └────────┘
 Bandit          ZAP                  Locust           GPT-4
 Semgrep         nmap                 aiohttp          Claude
 ESLint          curl                 ab               LLMs
```

### Request Flow

1. **Generation Phase**: User requests app generation via Web UI or API
2. **Orchestration**: `PipelineExecutionService` coordinates the workflow
3. **LLM Communication**: `GenerationService` calls OpenRouter API with requirement templates
4. **Container Deployment**: `DockerManager` builds and starts generated app containers
5. **Analysis Phase**: `AnalyzerManagerWrapper` dispatches analysis tasks via WebSocket to analyzer pool
6. **Result Aggregation**: `UnifiedResultService` consolidates results from all analyzers
7. **Persistence**: Results saved to `results/{model}/app{N}/task_{id}/`

### Service Layer Pattern

The codebase uses **Service Locator** pattern for dependency injection:

- All business logic lives in `src/app/services/`
- Access services via `ServiceLocator.get_<service_name>()`
- Services are registered during app factory initialization (`factory.py`)

**Critical Services**:
- `PipelineExecutionService` - Orchestrates Generation → Analysis pipeline (runs in Celery worker only)
- `TaskExecutionService` - Manages individual AnalysisTask lifecycle (runs in web container)
- `GenerationService` - LLM API integration and code generation
- `DockerManager` - Container lifecycle management for generated apps
- `AnalyzerManagerWrapper` - WebSocket communication with analyzer services
- `UnifiedResultService` - Result consolidation and normalization

### Docker Networking

**Networks**:
- `thesis-network` - Main network connecting Flask, Redis, Celery, and analyzers
- `thesis-apps-network` - Isolated network for generated app containers (dynamic analyzer access)

**Port Allocation**:
- Backend containers: 5001-5050
- Frontend containers: 8001-8050
- Analyzer services: 2001-2004 (with scale replicas: -2, -3, -4 suffixes)
- Web app: 5000 (exposed via Nginx on 80/443)

**Container Communication**:
- Flask/Celery → Analyzers: WebSocket over `thesis-network`
- Dynamic Analyzer → Generated Apps: HTTP over `thesis-apps-network`
- Performance Tester → Generated Apps: Host network mode (bypasses Docker network for realistic load testing)

### Database Architecture

**ORM**: SQLAlchemy with SQLite (WAL mode enabled for concurrent access)

**Key Models** (`src/app/models/`):
- `GeneratedApplication` - Represents AI-generated apps (model_slug, app_number, ports, container status)
- `AnalysisTask` - Individual analysis job (status, type, results)
- `PipelineExecution` - End-to-end pipeline tracking (generation + analysis)
- `PortConfiguration` - Dynamic port allocation registry
- `User` - Authentication (optional, disabled by default)

**Transaction Safety**:
- ALWAYS commit explicitly in service methods
- ALWAYS rollback in exception handlers
- Use `from app.extensions import db` for session access

### Analysis Pipeline Details

**Four Analyzer Types** (WebSocket-based microservices):

1. **Static Analyzer** (port 2001)
   - Python: Bandit, Semgrep, Pylint, Ruff, Flake8
   - JavaScript: ESLint, npm audit
   - Outputs: SARIF files (extracted to `sarif/` subdirectory to reduce JSON size)

2. **Dynamic Analyzer** (port 2002)
   - OWASP ZAP security scanning
   - Network probing (nmap, curl)
   - Vulnerability detection

3. **Performance Tester** (port 2003)
   - Load testing: Locust, Apache Bench, aiohttp
   - Runs on host network for accurate performance metrics

4. **AI Analyzer** (port 2004)
   - LLM-powered code review via OpenRouter
   - Requirements compliance checking
   - Best practices evaluation

**Result Structure**:
```
results/{model_slug}/app{N}/task_{task_id}/
├── consolidated.json           # Unified results from all analyzers
├── service_snapshots/          # Per-service raw outputs
│   ├── static.json
│   ├── dynamic.json
│   ├── performance.json
│   └── ai.json
└── sarif/                      # Extracted SARIF files (60-80% size reduction)
    ├── static_bandit.sarif.json
    ├── static_semgrep.sarif.json
    └── static_consolidated.sarif.json
```

## Code Style & Standards

### Python Conventions

- **Python Version**: 3.12+
- **Type Hints**: MANDATORY for all functions and methods
  ```python
  from typing import Optional, Dict, List, Any

  def process_results(task_id: str, data: Dict[str, Any]) -> Optional[str]:
      ...
  ```
- **Docstrings**: Google-style for all public functions/classes
- **Imports**: Absolute imports starting from `src` or `app`
  ```python
  from app.services.service_locator import ServiceLocator
  from app.utils.paths import get_project_root
  ```
- **Path Handling**: ALWAYS use `pathlib.Path` or `app.utils.paths`, NEVER `os.path.join` with hardcoded slashes

### Error Handling

- Use custom exceptions from `app.utils.errors`:
  - `AppError` - Base application error
  - `NotFoundHTTPError` - 404 errors
  - `ValidationError` - Input validation failures
  - `ServiceError` - Service layer errors

- Logging pattern:
  ```python
  from app.utils.logging_config import get_logger
  logger = get_logger(__name__)

  logger.info("Operation started", extra={'task_id': task_id})
  logger.error("Operation failed", exc_info=True)
  ```

### Testing

**Pytest Markers** (respect these for fast test runs):
- `unit` - Fast tests, no I/O
- `integration` - Database/service interaction
- `slow` - Long-running tests
- `analyzer` - Real Docker analyzer tests

**Run fast tests**:
```bash
pytest -m "not integration and not slow and not analyzer"
```

**Fixtures** (`conftest.py`):
- `app_context` - Flask application context
- `db_session` - Database session with rollback
- `client` - Flask test client

## Critical Workflows

### The Analysis Pipeline (Step-by-Step)

1. **User Initiates**: Web UI or API request (`POST /api/analysis/run`)
2. **Pipeline Created**: `PipelineExecutionService` creates `PipelineExecution` record (status: PENDING)
3. **Generation Phase**:
   - `GenerationService.generate_full_app()` calls OpenRouter API
   - Code saved to `generated/apps/{model_slug}/app{N}/`
   - Ports allocated from `PortConfiguration`
4. **Container Build**:
   - `DockerManager.build_app_images()` builds backend + frontend images
   - Images tagged: `thesisapp-{model}-app{N}-backend`, `thesisapp-{model}-app{N}-frontend`
5. **Container Startup**:
   - `DockerManager.start_app_containers()` launches containers on allocated ports
   - Health checks ensure containers are ready
6. **Analysis Dispatch**:
   - `AnalyzerManagerWrapper.run_comprehensive_analysis()` dispatches to analyzer pool
   - WebSocket messages sent to 4 analyzer services in parallel
7. **Result Collection**:
   - Each analyzer saves results to `results/{model}/app{N}/task_{id}/service_snapshots/`
   - SARIF files extracted to `sarif/` subdirectory
8. **Consolidation**:
   - `UnifiedResultService` merges all service results
   - Saves `consolidated.json`
9. **Cleanup**:
   - Legacy per-service result folders pruned
   - Pipeline status updated to COMPLETED

### Docker Socket Access

**CRITICAL**: Flask/Celery containers mount `/var/run/docker.sock` to manage generated app containers.

**Security Context**:
- Containers run with `group_add: "${DOCKER_GID:-0}"` to access Docker socket
- This grants permission to create/stop/remove containers on the host
- Generated app containers are created on the host Docker daemon, NOT nested

**Container Management Pattern**:
```python
from app.services.docker_manager import DockerManager

docker_mgr = ServiceLocator.get_docker_manager()

# Build images
docker_mgr.build_app_images(model_slug="anthropic_claude-3-5-sonnet", app_number=1)

# Start containers
docker_mgr.start_app_containers(model_slug="anthropic_claude-3-5-sonnet", app_number=1)

# Stop containers
docker_mgr.stop_app_containers(model_slug="anthropic_claude-3-5-sonnet", app_number=1)
```

### Celery Task Distribution

**Broker**: Redis (`redis://redis:6379/0`)

**Workers**: Single `celery-worker` container processes all background tasks

**Task Registry** (`src/app/services/task_registry.py`):
- `run_comprehensive_analysis_task` - Analysis orchestration
- Tasks are registered via decorator: `@shared_task(bind=True)`

**Pipeline Service Isolation**:
- `ENABLE_PIPELINE_SERVICE=false` in web container (prevents race conditions)
- `ENABLE_PIPELINE_SERVICE=true` in celery-worker container (ONLY container that processes pipelines)

## Environment Variables

**Required**:
- `OPENROUTER_API_KEY` - OpenRouter API key for LLM generation and AI analysis

**Important**:
- `SECRET_KEY` - Flask secret (auto-generated in dev, MUST set in production)
- `DATABASE_URL` - Database URI (default: `sqlite:////app/instance/app.db`)
- `CELERY_BROKER_URL` - Redis URL for Celery (default: `redis://redis:6379/0`)
- `LOG_LEVEL` - Logging verbosity (DEBUG, INFO, WARNING, ERROR)

**Feature Flags**:
- `ANALYZER_ENABLED` - Enable analyzer integration (default: true)
- `ANALYZER_AUTO_START` - Auto-start analyzers on app startup (default: false)
- `REGISTRATION_ENABLED` - Allow new user registration (default: false)
- `ENABLE_PIPELINE_SERVICE` - Enable pipeline polling service (default: true, set false in web container)

**Analyzer URLs** (comma-separated for load balancing):
- `STATIC_ANALYZER_URLS` - e.g., `ws://static-analyzer:2001,ws://static-analyzer-2:2001`
- `DYNAMIC_ANALYZER_URLS`
- `PERF_TESTER_URLS`
- `AI_ANALYZER_URLS`

## Common Patterns

### Adding a New Service

1. Create service class in `src/app/services/new_service.py`:
   ```python
   from typing import Optional
   from app.utils.logging_config import get_logger

   logger = get_logger(__name__)

   class NewService:
       def __init__(self):
           self.initialized = True

       def do_work(self, param: str) -> Optional[str]:
           """Do work with proper error handling."""
           try:
               # Implementation
               return "result"
           except Exception as e:
               logger.error("Work failed", exc_info=True)
               raise ServiceError(f"Failed to do work: {e}")
   ```

2. Register in `ServiceLocator` (`src/app/services/service_locator.py`):
   ```python
   # In _register_core_services():
   from .new_service import NewService
   cls.register('new_service', NewService())

   # Add getter method:
   @classmethod
   def get_new_service(cls) -> Optional["NewService"]:
       return cls.get('new_service')
   ```

### Accessing Database Models

```python
from app.extensions import db
from app.models import AnalysisTask, GeneratedApplication

# Query
task = AnalysisTask.query.filter_by(task_id=task_id).first()

# Create
new_task = AnalysisTask(
    task_id="unique-id",
    status=AnalysisStatus.PENDING
)
db.session.add(new_task)

# Update
task.status = AnalysisStatus.COMPLETED
task.completed_at = datetime.now()

# Commit (ALWAYS explicit)
db.session.commit()

# Rollback on error
try:
    db.session.commit()
except Exception:
    db.session.rollback()
    raise
```

### WebSocket Communication with Analyzers

```python
from app.services.analyzer_manager_wrapper import AnalyzerManagerWrapper

wrapper = AnalyzerManagerWrapper()

# Send analysis request
result = await wrapper.run_comprehensive_analysis(
    model_slug="anthropic_claude-3-5-sonnet",
    app_number=1,
    analysis_type="comprehensive"
)

# Result structure:
# {
#   'status': 'success' | 'error',
#   'results': {...},
#   'error_message': str (if error)
# }
```

## File Structure Reference

```
ThesisAppRework/
├── src/                          # Main application
│   ├── main.py                   # Entry point (Flask app creation)
│   ├── app/
│   │   ├── factory.py            # Flask app factory (initialization logic)
│   │   ├── extensions.py         # Flask extensions (SQLAlchemy, SocketIO)
│   │   ├── models/               # Database models
│   │   ├── services/             # Business logic layer
│   │   │   ├── service_locator.py
│   │   │   ├── pipeline_execution_service.py
│   │   │   ├── task_execution_service.py
│   │   │   ├── generation_v2/service.py
│   │   │   └── docker_manager.py
│   │   ├── routes/               # Web routes
│   │   │   ├── api/              # REST API endpoints
│   │   │   ├── jinja/            # HTML routes (HTMX-powered)
│   │   │   └── websockets/       # WebSocket handlers
│   │   ├── utils/                # Utilities (paths, logging, errors)
│   │   └── config/               # Configuration files
│   ├── templates/                # Jinja2 templates
│   └── data/                     # SQLite database location
│
├── analyzer/                     # Analyzer microservices
│   ├── analyzer_manager.py       # CLI for analyzer operations
│   ├── services/                 # Individual analyzer implementations
│   │   ├── static-analyzer/
│   │   ├── dynamic-analyzer/
│   │   ├── performance-tester/
│   │   └── ai-analyzer/
│   ├── configs/                  # Analyzer configurations
│   └── shared/                   # Shared protocol definitions
│
├── generated/                    # AI-generated applications
│   ├── apps/                     # Generated app code
│   │   └── {model_slug}/app{N}/
│   │       ├── backend/
│   │       ├── frontend/
│   │       └── docker-compose.yml
│   ├── raw/                      # Raw LLM responses
│   └── metadata/                 # Generation metadata
│
├── results/                      # Analysis results
│   └── {model_slug}/app{N}/task_{id}/
│       ├── consolidated.json
│       ├── service_snapshots/
│       └── sarif/
│
├── misc/                         # Utilities and templates
│   ├── requirements/             # App requirement templates (JSON)
│   ├── scaffolding/              # Base templates (React + Flask)
│   └── port_config.json          # Port allocation configuration
│
├── docker-compose.yml            # Main stack definition
├── Dockerfile                    # Flask app container
├── start.sh / start.ps1          # Orchestrator scripts
└── run_full_pipeline_test.py    # End-to-end testing
```

## Troubleshooting

### Stuck Tasks on Startup

The app automatically cleans up stuck tasks on startup:
- Tasks in RUNNING state for >2 hours → marked FAILED
- Tasks in PENDING state for >4 hours → marked CANCELLED
- Disable with `STARTUP_CLEANUP_ENABLED=false`

### Analyzer Connection Failures

1. Check analyzer services are running:
   ```bash
   docker compose ps
   # Should see: static-analyzer, dynamic-analyzer, performance-tester, ai-analyzer
   ```

2. Check analyzer health:
   ```bash
   cd analyzer
   python analyzer_manager.py health
   ```

3. Check WebSocket URLs in environment:
   ```bash
   # In docker-compose.yml, verify:
   - STATIC_ANALYZER_URLS=ws://static-analyzer:2001,...
   ```

### Docker Socket Permission Denied

Ensure `DOCKER_GID` is set correctly:
```bash
# In .env or docker-compose.yml:
DOCKER_GID=$(getent group docker | cut -d: -f3)
# Usually 999 on Linux, 0 on Docker Desktop
```

### Database Locked Errors

SQLite WAL mode is enabled for concurrent access. If you still see locks:
1. Check `SQLALCHEMY_ENGINE_OPTIONS` in `factory.py` (timeout=30, pool_size=10)
2. Ensure no external processes are holding locks
3. Restart services: `docker compose restart`

## Additional Documentation

Detailed guides are in the `docs/` directory:
- `docs/ARCHITECTURE.md` - In-depth system design
- `docs/QUICKSTART.md` - Installation and first steps
- `docs/API_REFERENCE.md` - REST API documentation
- `docs/ANALYZER_GUIDE.md` - Analyzer service details
- `docs/TROUBLESHOOTING.md` - Common issues and solutions
