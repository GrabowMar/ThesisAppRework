## AI Coding Agent Instructions (Project Playbook)

Purpose: Immediate productive edits to this Flask + Celery + analyzer microservices platform without rediscovering architecture. KEEP IT CONCRETE & PROJECT-SPECIFIC.

### 1. System Flow (Single Sentence)
User action → Flask route → ServiceLocator → (optional) Celery task → `analyzer_manager.py` / WebSocket bridge → analyzer containers (2001‑2004) → JSON results persisted → HTMX fragment refresh.

### 2. Critical Entry Points
App entry: `src/main.py` (uses app factory + optional SocketIO).  
Celery worker: `src/worker.py` (wraps tasks with Flask context).  
Tasks: `src/app/tasks.py` (only place that should perform long-running analyzer calls).  
Analyzer CLI: `analyzer/analyzer_manager.py` (start/stop/analyze/batch/logs).  
Build generated app containers: `scripts/build_start_app.py`.  

### 3. Service & Engine Pattern
NEVER import concrete services directly in routes/tests; always: `from app.services.service_locator import ServiceLocator`.  
Analysis engines (`analysis_engines.py`) abstract execution; deprecated legacy wrappers emit `DeprecationWarning`. Use engines or the analysis service via ServiceLocator (future‑proof).  
All new services raise standardized exceptions from `service_base.py` (e.g. `NotFoundError`, `ValidationError`).

### 4. Generated Applications & Ports
Generated sources: `generated/{model_slug}/app{N}` (model slug keeps hyphens).  
Container names normalize hyphens to underscores; NEVER bake port numbers into names.  
Resolve ports via DB `PortConfiguration`; fallback to `src/misc/port_config.json` only if DB missing. Do NOT hard-code or invent new port ranges.

### 5. Analyzer Invocation Rules
Only Celery tasks (or analysis engines in controlled test fast paths) may block on analyzer work.  
Subprocess bridge: `app/services/analyzer_integration.py` shells out to `analyzer_manager.py` (enforces UTF‑8, parses stdout JSON).  
Direct WebSocket protocol lives in `analyzer/shared/protocol.py`; do not handcraft WS JSON in routes—extend the protocol classes instead.

### 6. HTMX & Templates
Distinguish full vs fragment with `HX-Request` header.  
Return partials from `templates/partials/**` for dynamic panels; keep stable `id` / `hx-target` attributes.  
Legacy template path shim: `app/utils/template_paths.py`—acceptable only for migration; new pages go in `templates/pages/` + extend `base.html`.

### 7. Data & JSON Practices
Large analyzer outputs: store serialized once in `results_json` / `metadata_json`; parse lazily in services (add helper if repeating).  
Status enum lifecycle: PENDING → RUNNING → COMPLETED|FAILED (never invent new states without updating docs + tasks).  
When adding a new analysis table: mirror existing columns (status, started_at, completed_at, results_json, metadata_json) + minimal summary metrics.

### 8. Sample Generation Subsystem
API lives under `/api/sample-gen/*`; synchronous (no Celery) via `sample_generation_service`.  
Tests show canonical flow (`tests/test_sample_generation_api.py`); follow manifest update pattern (see `tests/test_generation_manifest.py`).  
Concurrent generation guarded by internal service limits—re‑use service rather than duplicating logic.

### 9. Testing Conventions
Pytest fixtures: `tests/conftest.py` creates ephemeral SQLite DB; do not assume persistent IDs.  
Prefer engine/service level tests over route tests for complex logic.  
For analyzer-dependent paths, isolate by mocking subprocess call in `analyzer_integration` instead of faking WebSocket traffic.

### 10. Safe Change Checklist (DO / AVOID)
DO register new services in `ServiceLocator.initialize()`; keep side effects lazy.  
DO route all long-running work through Celery tasks or engines.  
DO reuse container & port helpers; fail fast if lookup missing.  
AVOID embedding model/app specific logic in templates (put in services).  
AVOID synchronous analyzer subprocess calls inside request handlers.  
AVOID duplicating JSON parsing—introduce helper if pattern repeats 3+ times.

### 11. Adding a New Analyzer Type (Minimal Steps)
1) Define container & port in `analyzer/docker-compose.yml` + protocol messages.  
2) Extend `analyzer_manager.py` (analyze subcommand).  
3) Add service/engine wrapper method → Celery task function.  
4) Create ORM table + migration (status, timings, results_json, metadata_json).  
5) Add HTMX partials for start/progress/result; wire route via ServiceLocator.  
6) Update this file & `docs/ANALYSIS_PIPELINE.md`.

### 12. Observability & Troubleshooting
Primary logs: `logs/app.log` (Flask), `logs/celery_worker.log` (worker), analyzer container logs via `python analyzer_manager.py logs <service>`.  
If task appears stuck: check Celery worker log → run `analyzer_manager.py health` → inspect `analyzer/results/*` artifact.  
Common issue: missing model slug leads to `/app/sources/app1` path error—validate inputs before enqueue.

### 13. Command Snippets (PowerShell)
Start full stack: `./start.ps1 start`  | UI only: `./start.ps1 flask-only`  
Run tests fast: `pytest -q`  | Focused: `pytest tests/test_sample_generation_api.py -q`  
Manual analysis: `cd analyzer; python analyzer_manager.py analyze anthropic_claude-3.7-sonnet 1 security`  
Build app containers: `python scripts/build_start_app.py --model anthropic_claude-3.7-sonnet --app 1 --rebuild`

### 14. When Unsure
Consult `docs/PROJECT_STRUCTURE.md` & `docs/ARCHITECTURE.md` BEFORE adding new abstractions. Emulate existing analysis table + task shapes for consistency.

_Last updated: 2025-09-03 (merged & condensed for agent use)._ 