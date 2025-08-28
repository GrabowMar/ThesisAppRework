# Development Guide

> Navigation: [Overview](OVERVIEW.md) · [Architecture](ARCHITECTURE.md) · [Request Flow](REQUEST_FLOW.md) · [Analysis Pipeline](ANALYSIS_PIPELINE.md) · [Data Model](DATA_MODEL.md) · [Routes](ROUTES_REFERENCE.md) · [Services](SERVICES_REFERENCE.md) · [Observability](OBSERVABILITY.md)

Practical instructions for setting up the environment, extending functionality, and contributing safely.

## 1. Environment Setup

1. Python 3.11+ recommended.
2. Create venv: `python -m venv .venv` then activate.
3. Install core deps: `pip install -r src/requirements.txt`.
4. (Docs optional) `pip install -r docs/requirements-docs.txt`.
5. Initialize DB (first run): `python src/init_db.py` or run the population script.
6. Start stack: `./src/start.ps1 start -Docs` (Windows PowerShell) or `./src/start.sh start` (Linux/Mac; docs flag TBD).

## 2. Key Commands (start.ps1)

| Action | Description |
|--------|-------------|
| `./start.ps1 flask-only` | Run only Flask app (no Celery / analyzer) |
| `./start.ps1 start` | Full stack (Flask + Celery + Redis + bridge) |
| `./start.ps1 start -Docs` | Full stack + live docs (MkDocs) |
| `./start.ps1 docs-serve` | Serve docs only |
| `./start.ps1 docs-stop` | Stop docs server |
| `./start.ps1 stop` | Stop all components |

## 3. Dependency Boundaries

- Routes may only call services through `ServiceLocator`.
- Services may use other services (inject via ServiceLocator to avoid cycles) but must not import routes.
- Celery tasks call services; they must not import web-layer objects except serialization helpers.
- Analyzer microservices communicate strictly through WebSocket protocol spec; no direct DB access.

## 4. Adding a New Service
1. Create `app/services/<name>_service.py` defining a class with a clear public API.
2. Register in `service_locator.py` (lazy singleton or factory pattern consistent with existing entries).
3. Add docstring describing responsibilities & expected inputs/outputs.
4. Reference only via `ServiceLocator.get_<name>_service()` elsewhere.
5. Add to [Services Reference](SERVICES_REFERENCE.md) (auto-regeneration will capture if pattern matches).

## 5. Adding a New Route
1. Choose blueprint (or create new in `app/routes/`).
2. Keep function body minimal: validate -> delegate to service -> format response.
3. Provide HTMX fragment vs full page logic (check `HX-Request`).
4. Update or create template fragment under `templates/pages/...` or `templates/ui/...`.
5. Re-run doc generator to update [Routes Reference](ROUTES_REFERENCE.md).

## 6. Creating a Celery Task
1. Define task in `app/tasks.py` (or a dedicated tasks module imported there).
2. Use descriptive name: `analysis_run_security` etc.
3. Wrap logic in service call ensuring idempotency where possible.
4. Return structured dict (status, identifiers) for clarity.

## 7. Extending Analyzer Pipeline (New Analyzer Type)
| Step | Action |
|------|--------|
| 1 | Implement container under `analyzer/services/<your-analyzer>/` |
| 2 | Expose WebSocket action(s) in gateway (if new) |
| 3 | Add Celery task invoking `AnalyzerIntegration` with new action |
| 4 | Add DB table / migration for result storage if needed |
| 5 | Add service facade method (e.g., `queue_<type>_analysis`) |
| 6 | Add UI button + fragment templates |
| 7 | Update docs (Analysis Pipeline & Services Reference) |

## 8. Database Migrations
1. Modify or add model (SQLAlchemy) file.
2. Generate migration (Alembic): `alembic revision --autogenerate -m "describe change"` (ensure env configured).
3. Review generated script; adjust for JSON/text columns or indexes.
4. Apply: `alembic upgrade head`.
5. Run smoke tests.

## 9. Testing Strategy
| Test Type | Scope | Location |
|-----------|-------|----------|
| Unit | Service methods (pure logic) | `src/tests/unit/` (create if absent) |
| Integration | Route + service interactions, Celery deferred (mock) | `src/tests/integration/` |
| Analyzer Bridge | WebSocket protocol handling | `analyzer/tests/` |
| End-to-End (smoke) | Full stack basic flows | `scripts/http_smoke.py` |

Guidelines:
- Prefer deterministic tests (avoid real network to containers unless necessary: use fixtures/mocks).
- Use factory helpers to instantiate domain objects.
- Keep unit tests < 100ms each local.

## 10. Logging Conventions
- Use structured log messages where feasible: `logger.info("analysis.started", extra={...})` (future improvement).
- Current baseline: module-level `logging.getLogger(__name__)`.
- Avoid printing to stdout; rely on loggers so start scripts can redirect.

## 11. Error Handling Patterns
| Situation | Pattern |
|-----------|--------|
| Expected missing resource | Raise custom NotFound -> route 404 handler |
| Transient analyzer error | Retry (future) or mark task FAILED |
| Validation error | Return fragment with error banner; 422 status optionally |
| Unexpected exception | Log stack trace → generic user-facing message |

## 12. Performance Tips
- Batch DB reads when rendering dashboards.
- Cache parsed large JSON result blobs per-request (simple dict memoization) to avoid re-parsing.
- Avoid synchronous WebSocket calls in routes (delegate to tasks always).
- Tune Celery worker concurrency according to CPU and I/O profile.

## 13. Style & Linting (Future)
Introduce tooling:
- black / isort / flake8 or ruff
- mypy for gradual typing (start with services most reused)

## 14. Documentation Workflow
| Activity | Command |
|----------|---------|
| Regenerate references | `python scripts/generate_docs.py` (if present) |
| Serve docs | `./src/start.ps1 docs-serve` |
| With app | `./src/start.ps1 start -Docs` |

## 15. Adding Navigation to New Doc Pages
Include the standard nav line (see top of this file) to ensure cross-links remain consistent.

## 16. Security Considerations (Dev)
- Do not trust analyzer output for direct HTML injection—sanitize or escape in templates.
- Keep secrets out of repo (use env vars), especially API keys for external model providers.
- Validate user-supplied model/app identifiers strictly.

## 17. Release / Deployment Checklist (Manual)
1. Run tests & smoke script.
2. Regenerate docs, review diffs.
3. Bump version (if versioning introduced).
4. Generate migration & upgrade DB.
5. Tag & push.
6. (Optional) Build container images for analyzers with version tags.

## 18. Troubleshooting Quick Table
| Symptom | Likely Cause | Check |
|---------|--------------|-------|
| Analysis stuck queued | Celery worker not running | `celery_worker.log` |
| No progress events | WebSocket bridge down | `analyzer_manager.py status` |
| Port resolution fails | Missing DB record / stale JSON fallback | Port service logs |
| Docs not loading | MkDocs server not started | `start.ps1 -Docs` flag |
| Container build slow | Uncached layers | `logs/analyzer-build.log` |

## 19. Future Enhancements Roadmap
- Push-based client progress (SSE/WebSocket).
- Artifact versioning & diff view between analyses.
- Role-based access control.
- Central metrics & tracing instrumentation.

---
_Last updated: 2025-08-24._ 
