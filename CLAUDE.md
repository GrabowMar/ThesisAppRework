# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working on this repository. For full architecture details, see `.github/copilot-instructions.md`.

## Project Summary

ThesisAppRework is a research platform: generate web apps via LLMs → deploy in Docker → analyze (security, performance, code quality, AI review) → compare models. Flask + Celery + Redis + 4 analyzer microservices.

## Essential Commands

```bash
# Full stack
docker compose up -d

# Fast tests (skip slow/integration/analyzer)
pytest -m "not integration and not slow and not analyzer"

# Lint
ruff check src/

# Reset database
python src/init_db.py
```

## Architecture Quick Reference

- **App factory**: `src/app/factory.py` → registers blueprints, extensions, services
- **Service Locator**: `src/app/services/service_locator.py` — all services accessed via `ServiceLocator.get_<name>()`
- **Pipeline flow**: Web UI → API → Celery task → PipelineExecutionService → GenerationService → DockerManager → AnalyzerManagerWrapper → UnifiedResultService
- **Analyzer protocol**: `analyzer/shared/protocol.py` (WebSocket messages — do not break)
- **Two exception layers**: `app.services.service_base` (ServiceError hierarchy for services) + `app.utils.errors` (AppError hierarchy for HTTP)
- **Celery isolation**: `ENABLE_PIPELINE_SERVICE=false` in web, `true` in celery-worker only

## Code Style

- Python 3.12+, mandatory type hints, Google-style docstrings
- Imports: `from app.services.xxx import Xxx` (absolute) or relative `from ..models import X`
- Logging: `get_logger('name')` for new services, `logging.getLogger(__name__)` also common
- Database: explicit `db.session.commit()` / `db.session.rollback()` in try/except
- Paths: `pathlib.Path` or `app.paths` constants, never hardcoded slashes

## Testing

Markers: `unit`, `integration`, `slow`, `analyzer`. Fixtures: `app_context`, `db_session`, `client` in `conftest.py`.

## Key Directories

| Directory | Content |
|-----------|---------|
| `src/app/services/` | Business logic (50+ service modules) |
| `src/app/models/` | SQLAlchemy models (15 files) |
| `src/app/routes/api/` | REST API endpoints (17 blueprints) |
| `src/app/routes/jinja/` | HTML page routes (HTMX) |
| `src/templates/` | Jinja2 templates |
| `analyzer/services/` | 4 analyzer microservice implementations |
| `generated/apps/` | AI-generated app code (`{model_slug}/app{N}/`) |
| `results/` | Analysis results (`{model_slug}/app{N}/task_{id}/`) |
| `misc/requirements/` | 30 JSON app requirement templates |
| `docs/` | Documentation (served at `/docs` in the web UI) |

## Docker Networks & Ports

- `thesis-network`: main infrastructure
- `thesis-apps-network`: dynamic analyzer ↔ generated app containers
- Generated backends: 5001-5050, frontends: 8001-8050
- Analyzers: 2001-2004 (with replicas on 205x ports)
- Docker socket mounted in Flask/Celery for host container management

## Environment Variables

Required: `OPENROUTER_API_KEY`. Important: `SECRET_KEY`, `CELERY_BROKER_URL`, `LOG_LEVEL`, `ENABLE_PIPELINE_SERVICE`, `ANALYZER_ENABLED`.

Analyzer URLs (comma-separated for load balancing): `STATIC_ANALYZER_URLS`, `DYNAMIC_ANALYZER_URLS`, `PERF_TESTER_URLS`, `AI_ANALYZER_URLS`.
