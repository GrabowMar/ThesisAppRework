# Project Structure (Concise)

Purpose: Orientation for contributors and automated agents. Factual, minimal, cross-links to detailed docs.

## Top-Level (src/)
| File/Dir | Role |
|----------|------|
| `main.py` | Flask app entry (creates app, optional SocketIO) |
| `worker.py` | Celery worker bootstrap (Flask context wrapper) |
| `app/` | Application package (routes, services, models, tasks) |
| `templates/` | Jinja templates (pages + HTMX partials) |
| `static/` | Consolidated static assets (css/js) |
| `config/` | Settings + Celery config modules |
| `tests/` | Pytest suite (unit + integration) |
| `generated/` | Generated model application artifacts (ports, compose) |
| `misc/` | Seed/fallback JSON (models, capabilities, ports) |
| `logs/` | Runtime logs |
| `analyzer/` | Analyzer microservices (docker-compose + services) |

## Key Packages
### `app/routes/`
Blueprints: domain separation (dashboard, models, analysis, tasks, statistics, advanced, errors) + `api/` subpackage (JSON + HTMX fragment endpoints). Legacy aggregate retained as `api.py.backup`.

### `app/services/`
Domain + integration layer. Access strictly via `ServiceLocator`.
Core services: model, batch, docker_manager, analyzer_integration, openrouter, security, task_manager, background (maintenance).  
Engines: `analysis_engines.py` (security | static | dynamic | performance) — uniform `run()` contract.
Deprecated shims expose `DEPRECATED = True` and raise on use (see `LEGACY_REMOVALS.md`).

### `app/tasks.py`
Celery task definitions; gating logic uses `DISABLED_ANALYSIS_MODELS` env to early-skip analysis tasks.

### `app/models/`
ORM models (capabilities, generated apps, analyses). Large analyzer outputs stored in JSON columns; parsing deferred to services. Enhanced with intelligent status tracking (`last_status_check` timestamps) for container state management.

## Application Status System
Database-cached container status with Docker sync. See `APPLICATION_STATUS_SYSTEM.md` for:
- Smart caching to minimize Docker API calls
- Bulk refresh endpoints for manual synchronization  
- Frontend polling optimization
- Status age tracking and freshness validation

## Analyzer Stack (`analyzer/`)
`docker-compose.yml` defines: gateway (8765), static-analyzer (2001), dynamic-analyzer (2002), performance-tester (2003), ai-analyzer (2004), redis (6379). Results persisted under per-service volumes and/or `results/`.

## Generated Applications (`generated/`)
Layout: `generated/<model_slug>/app<number>/` (slug keeps hyphens). Ports resolved primarily via DB (`PortConfiguration`); fallback JSON only if absent. Compose files built via `scripts/build_start_app.py`.

## Sample Generation Subsystem
Synchronous API (`/api/sample-gen/*`) uses in-memory registry + manifest under `generated/indices/generation_manifest.json` (project root). Does NOT use Celery; safe for fast test flows.

## Template Conventions
Pages: `templates/pages/*.html`; partials: `templates/partials/**`. Detect HTMX with `HX-Request` header. Shared wrapper macros live under `partials/common/` (see `TEMPLATES.md`). Frontend uses Bootstrap 5 + Font Awesome icons (no inline SVG).

## Error Handling
Central handlers in `routes/errors.py` map internal `ServiceError` subclasses to JSON or HTML; request id injected. See `ERROR_HANDLING.md`.

## Common Extension Points
| Extension | Touch Points |
|----------|--------------|
| New analyzer type | analyzer service+Dockerfile, manager command, engine registry, Celery task, ORM model, UI partials |
| New service | `app/services/<name>_service.py` + register in `service_locator.py` |
| New analysis table | ORM model + migration + JSON result/accessors |
| New page | Route blueprint (or existing), `templates/pages/*`, partials for fragments |

## Conventions
1. Routes delegate; no analyzer subprocess or heavy logic inline.
2. Services return plain dicts / dataclasses; raise standardized service exceptions.
3. Engines only wrap analyzer integration; persistence happens in tasks/services.
4. Avoid hard-coded ports; always resolve via DB/service.
5. Large JSON blobs: store raw once; parse lazily.

## Minimal Dev Commands
```bash
python src/main.py                  # Run Flask
celery -A app.tasks worker -l info  # Worker
pytest -q                           # Tests
python scripts/build_start_app.py --model <slug> --app 1 --rebuild
```

## Status Snapshot (2025-09-16)
Stable: layering, engines, analyzer stack, Bootstrap 5 frontend.  
In Progress: richer port allocation & background tasks.  
Completed: Bootstrap 5 migration, frontend documentation consolidation.  
Deprecated: legacy analyzer service & container/port shims (see `LEGACY_REMOVALS.md`).

_Last updated: 2025-09-16._
