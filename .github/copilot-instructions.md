## AI Coding Agent Instructions (Project-Specific Playbook)

Purpose: Enable immediate productive changes to this dual-stack system (Flask web platform + containerized analyzer microservices) without re-discovering conventions.

### 1. High-Level Architecture
Web UI (Flask + HTMX) lives under `src/`; analysis microservices & orchestration under `analyzer/`.
Flow (core analysis): User action → Flask route/service layer → Celery task (`src/app/tasks.py`) → WebSocket to analyzer service (ports 2001‑2005) → result JSON persisted → HTMX fragment update.

### 2. Key Directories & Files
`src/app/services/` business logic (access ONLY via ServiceLocator).  
`src/app/services/analyzer_integration.py` WebSocket/bridge.  
`analyzer/analyzer_manager.py` CLI & orchestration of analyzer containers.  
`misc/models/{model_slug}/app{N}/` generated apps (backend/frontend compose).  
`misc/port_config.json` + DB table `port_configuration` authoritative port map (DB first, JSON fallback).  
`scripts/build_start_app.py` build & run a single generated app.  
`src/templates/` reorganized (see Template Restructure below).  

### 3. Core Patterns
Service Locator: `from app.services.service_locator import ServiceLocator` (never import concrete services directly in routes/tests).  
Results Storage: Large/variable analyzer outputs stored as JSON text columns; always expose a `get_*()` method that returns parsed dict.  
HTMX: Forms & buttons return partials; routes should detect `HX-Request` header when differing full-page vs fragment.  
Async Work: Only Celery tasks talk to analyzer containers; do not perform blocking WebSocket calls inside request threads.  
Port Logic: Never recompute ports—always resolve through model+app lookup service (DB) then fallback JSON.

### 4. Template Restructure (Aug 2025)
Canonical paths: `layouts/`, `pages/<domain>/`, shared widgets under `ui/elements/`.  
Compatibility shim: `src/app/utils/template_paths.py` (`render_template_compat`) remaps legacy `views/...` etc.—use only while migrating; prefer new paths in new code.  
When adding a new feature page: create under `pages/<domain>/` + extend a layout in `layouts/`.

### 5. Analyzer Services
Containers: static (2001), dynamic/ZAP (2002), performance (2003), ai (2004), security (2005).  
Start/stop via `python analyzer_manager.py start|stop|status`.  
Single run: `python analyzer_manager.py analyze <model> <app> <type>` (types: security, static, ai, performance, comprehensive).  
Batch: `python analyzer_manager.py batch <file.json>` (array of `[model, app]`).  
Results saved under `analyzer/results/` (timestamped); web app later ingests/persists.

### 6. Development & Test Workflows
Platform startup (Windows PowerShell from `src/`): `./start.ps1 flask-only` (UI) or `./start.ps1 start` (UI + Celery + Redis + analyzer bridge).  
Generated app build/run: `python scripts/build_start_app.py --model anthropic_claude-3.7-sonnet --app 1 [--rebuild]`.  
Unit/integration tests: root `pytest -q`; Celery flow examples in `tests/integration/`.  
Smoke HTTP script: `python scripts/http_smoke.py`.  

### 7. Data & Naming Conventions
Model slugs: keep original hyphens (e.g. `anthropic_claude-3.7-sonnet`). Compose service/container names normalize to underscores: `{normalized_model}_app{N}_{backend|frontend}`.  
Do NOT embed port numbers in container names (legacy removed).  
Always reference container names through helper (`ContainerNames.get_container_name(...)`) if available.  
JSON result columns: never store Python objects—serialize once, parse on access.

### 8. Safe Change Guidelines (Agent DO / DON'T)
DO: Go through ServiceLocator for business logic; add new services there.  
DO: Add new analyzer interaction via `analyzer_integration` abstraction (not raw websockets in routes).  
DO: Prefer partial template updates with HTMX targets; keep IDs stable.  
DO: Use existing port + container utilities; fail fast if port missing.  
DON'T: Introduce blocking network calls in request thread.  
DON'T: Recalculate or hard-code new port ranges.  
DON'T: Bypass compatibility shim when editing legacy route until all old paths are migrated.

### 9. Minimal Example (Security Analysis Trigger)
```python
from app.services.service_locator import ServiceLocator
def start_security(model_slug: str, app_number: int):
    task = ServiceLocator.get_analysis_service().queue_security_analysis(model_slug, app_number)
    return {"task_id": task.id}
```

### 10. Observability & Troubleshooting
Logs: `logs/app.log`, analyzer container logs via `analyzer_manager.py logs [service]`.  
If analysis seems stalled: check Celery worker (`src/celery_worker.log`) then analyzer status CLI.  
WebSocket handshake noise in static analyzer is usually benign (reduced log level already).

If unsure about a pattern, inspect `docs/PROJECT_STRUCTURE.md` or existing service implementations before adding new concepts.