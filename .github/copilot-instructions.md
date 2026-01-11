# ThesisAppRework AI Agent Instructions

## Architecture Overview

This is a Flask-based platform for analyzing AI-generated applications. The system has three main layers:

1. **Flask Web App** (`src/app/`) - Web UI, REST API, SQLite database
2. **Analyzer Microservices** (`analyzer/services/`) - Docker containers for static, dynamic, performance, and AI analysis
3. **Background Services** - Task execution, pipeline orchestration, maintenance (all in `src/app/services/`)

Communication between Flask and analyzers uses **WebSocket protocol** defined in [analyzer/shared/protocol.py](analyzer/shared/protocol.py).

## Key Conventions

### Service Pattern
All business logic lives in `src/app/services/`. Services are registered via `ServiceLocator` in [src/app/services/service_locator.py](src/app/services/service_locator.py):
```python
# Access services via ServiceLocator
from app.services.service_locator import ServiceLocator
model_svc = ServiceLocator.get_model_service()
```

### Model Slugs
Models are identified by slugs like `anthropic_claude-3-5-haiku` (format: `{provider}_{model-name}`). Results are stored at `results/{model_slug}/app{N}/task_{id}/`.

### Status Enums
Use enums from [src/app/constants.py](src/app/constants.py):
```python
from app.constants import AnalysisStatus, AnalysisType
task.status = AnalysisStatus.RUNNING
```

### Time Handling
Always use timezone-aware UTC datetimes:
```python
from app.utils.time import utc_now
created_at = utc_now()
```

## Development Commands

```powershell
# Start full stack (Docker containers + Flask)
./start.ps1 -Mode Start

# Quick dev mode without analyzers
./start.ps1 -Mode Dev -NoAnalyzer

# Rebuild containers (fast, cached)
./start.ps1 -Mode Rebuild

# Full clean rebuild
./start.ps1 -Mode CleanRebuild
```

## Testing

```powershell
# Fast unit tests (excludes integration/slow/analyzer)
pytest -m "not integration and not slow and not analyzer"

# Run specific test file
pytest tests/unit/test_task_service.py -v

# Integration tests (requires Docker analyzers)
pytest tests/integration/ -m integration
```

Test markers defined in [pytest.ini](pytest.ini): `unit`, `integration`, `slow`, `analyzer`, `smoke`, `api`, `websocket`.

Test fixtures in [tests/conftest.py](tests/conftest.py) provide `app`, `client`, `db_session` with automatic isolation.

## File Organization

- **Routes**: `src/app/routes/` (web UI) and `src/app/routes/api/` (REST endpoints)
- **Models**: `src/app/models/` - SQLAlchemy models, use `AnalysisTask` for analysis tracking
- **Templates**: `src/templates/` - Jinja2 with HTMX for dynamic updates
- **Analyzer configs**: `analyzer/configs/` - Tool configurations (Bandit, Semgrep, etc.)

## Adding New Features

### New Service
1. Create service class in `src/app/services/`
2. Register in `ServiceLocator._register_core_services()`
3. Add typed getter method to `ServiceLocator`

### New API Endpoint
Add to `src/app/routes/api/`. Pattern:
```python
@api_bp.route('/analysis/<task_id>', methods=['GET'])
@require_api_key
def get_analysis(task_id):
    # Implementation
```

### New Analyzer Tool
1. Add tool to appropriate service in `analyzer/services/`
2. Update config in `analyzer/configs/`
3. Add message types to [analyzer/shared/protocol.py](analyzer/shared/protocol.py) if needed

## Common Patterns

### Database Operations
```python
from app.extensions import db
from app.models import AnalysisTask

task = AnalysisTask.query.filter_by(task_id=task_id).first()
db.session.add(new_task)
db.session.commit()
```

### Error Handling
Services raise specific exceptions from `app/services/service_base.py`. API routes return JSON errors with appropriate status codes.

### Background Task Execution
Tasks flow: `PENDING` → `RUNNING` → `COMPLETED`/`FAILED`. The `TaskExecutionService` polls for pending tasks every 2-5 seconds.
