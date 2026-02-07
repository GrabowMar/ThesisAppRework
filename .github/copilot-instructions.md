# ThesisAppRework — AI Agent Instructions

Research platform that generates web apps via LLM APIs, deploys them in Docker, and runs automated analysis (security, performance, code quality, AI review) to compare models.

## Architecture (5 components)

```
Flask Web (:5000) → Redis → Celery Worker → 4 Analyzer Microservices (WebSocket)
                                           → Docker (generated app containers)
```

- **Flask app** (`src/app/`): Factory pattern, Service Locator DI, SQLAlchemy/SQLite, Jinja2+HTMX frontend
- **Celery worker** (`src/app/celery_worker.py`): Runs `PipelineExecutionService` exclusively (`ENABLE_PIPELINE_SERVICE=true` only here, `false` in web container)
- **Analyzers** (`analyzer/services/`): Static(:2001), Dynamic(:2002), Performance(:2003), AI(:2004) — communicate via WebSocket protocol defined in `analyzer/shared/protocol.py`
- **Generated apps** (`generated/apps/{model_slug}/app{N}/`): Each has backend+frontend, built/started by `DockerManager`
- **Results** (`results/{model_slug}/app{N}/task_{id}/`): `consolidated.json` + `service_snapshots/` + `sarif/`

## Service Locator Pattern

All business logic in `src/app/services/`. Access via `ServiceLocator`:
```python
from app.services.service_locator import ServiceLocator
docker_mgr = ServiceLocator.get_docker_manager()
```
Register new services in `ServiceLocator._register_core_services()` with a typed getter method.

## Code Conventions

**Imports** — use `from app.` (absolute) or `from ..` (relative). Never `from src.app.`:
```python
from app.services.service_locator import ServiceLocator
from app.extensions import db
from ..models import AnalysisTask
```

**Logging** — two patterns coexist. Newer services use `get_logger()`, most use stdlib:
```python
# Preferred for new service code:
from app.utils.logging_config import get_logger
logger = get_logger('my_service')  # → "ThesisApp.my_service"

# Also common (60+ files):
import logging
logger = logging.getLogger(__name__)
```

**Exceptions** — two layers:
```python
# Service layer (raise in services):
from app.services.service_base import ServiceError, NotFoundError, ValidationError, ConflictError, OperationError

# HTTP layer (raise in routes):
from app.utils.errors import AppError, NotFoundHTTPError, BadRequestError
```
Route error handlers in `app/errors/handlers.py` auto-map service exceptions to HTTP status codes.

**Database** — explicit commit/rollback, use `db.session.flush()` for multi-step transactions:
```python
from app.extensions import db
try:
    db.session.add(entity)
    db.session.commit()
except Exception:
    db.session.rollback()
    raise
```

**Paths** — use `pathlib.Path` or `app.paths` constants. Never hardcode `/` separators.

**Type hints** — mandatory on all functions. Google-style docstrings.

## Commands

```bash
docker compose up -d              # Full stack
pytest -m "not integration and not slow and not analyzer"  # Fast tests
ruff check src/                   # Lint
python src/init_db.py             # Reset DB
```

## Key Files

| Purpose | Location |
|---------|----------|
| App factory | `src/app/factory.py` |
| Models | `src/app/models/` (core.py, analysis_models.py, pipeline.py) |
| Service Locator | `src/app/services/service_locator.py` |
| Pipeline orchestrator | `src/app/services/pipeline_execution_service.py` |
| Docker management | `src/app/services/docker_manager.py` |
| Generation engine | `src/app/services/generation_v2/service.py` |
| Result consolidation | `src/app/services/unified_result_service.py` |
| WebSocket protocol | `analyzer/shared/protocol.py` — **DO NOT BREAK** |
| App requirement templates | `misc/requirements/*.json` (30 templates) |
| Status enums | `src/app/constants.py` |
| HTMX templates | `src/templates/` |

## Docker Networking

- `thesis-network`: Flask ↔ Redis ↔ Celery ↔ Analyzers
- `thesis-apps-network`: Dynamic analyzer ↔ generated app containers
- Performance tester uses bridge networks + `extra_hosts: host.docker.internal` to reach generated app containers
- Flask/Celery mount `/var/run/docker.sock` to manage generated containers on host
- Ports: generated backends 5001+, frontends 8001+ (dynamically allocated), analyzers 2001-2004

## Frontend Pattern

Jinja2 + HTMX with Bootstrap. Key patterns:
- `hx-get`/`hx-post` with `hx-swap="innerHTML"` for partial updates
- `hx-trigger="load, every 60s"` for polling
- `hx-trigger="revealed once"` for lazy loading
- Modal pattern: `bootstrap.Modal.getInstance(el) || new bootstrap.Modal(el)` (never create duplicates)

## Critical Rules

1. `analyzer/shared/protocol.py` defines the WebSocket message contract — changing it breaks all 4 analyzers
2. Only `celery-worker` runs `PipelineExecutionService` — web container has it disabled to prevent race conditions
3. Result loading priority: Cache → DB → Filesystem (`consolidated.json` preferred over raw files)
4. Generated app containers run on host Docker daemon, not nested — Docker socket mount is required
5. Never commit secrets — use `os.getenv()` and `.env` file
