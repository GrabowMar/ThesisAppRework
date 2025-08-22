# Project Structure - ThesisAppRework/src

## 📁 Current Structure (Updated)

```
src/
├── main.py                       # ✅ Application entry point
├── worker.py                     # ✅ Celery worker entry point
├── requirements.txt              # ✅ Python dependencies
├── start.ps1 / start.sh          # ✅ Cross-platform startup scripts
│
├── app/                          # Flask application package
│   ├── __init__.py               # ✅ Package init (exposes factory)
│   ├── factory.py                # ✅ Flask application factory
│   ├── models.py                 # ✅ Legacy/aggregated models (superseded by app/models/)
│   ├── constants.py              # ✅ Application enums & constants
│   ├── extensions.py             # ✅ DB, Celery, other extensions
│   ├── tasks.py                  # ✅ Celery task definitions
│   ├── data/                     # ✅ SQLite database storage
│   │   └── thesis_app.db
│   ├── models/                   # ✅ Structured model modules
│   │   └── analysis.py           # ✅ Analysis-related ORM models
│   │
│   ├── routes/                   # Modular Flask blueprints (UI + API segregation)
│   │   ├── __init__.py           # ✅ Blueprint registration helpers
│   │   ├── main.py               # ✅ Dashboard & landing views
│   │   ├── models.py             # ✅ Model catalog & app listing views
│   │   ├── analysis.py           # ✅ Analysis hub views
│   │   ├── batch.py              # ✅ Batch operations UI
│   │   ├── statistics.py         # ✅ Metrics & statistics views
│   │   ├── testing.py            # ❌ Removed (consolidated into analysis)
│   │   ├── advanced.py           # ✅ Advanced / experimental views
│   │   ├── errors.py             # ✅ Error handlers
│   │   ├── api/                  # ✅ REST/HTMX JSON endpoints (fine‑grained)
│   │   │   ├── __init__.py       # ✅ API blueprint init
│   │   │   ├── core.py           # ✅ Core system status endpoints
│   │   │   ├── dashboard.py      # ✅ Dashboard data endpoints
│   │   │   ├── models.py         # ✅ Model + application endpoints
│   │   │   ├── applications.py   # ✅ Application detail endpoints
│   │   │   ├── analysis.py       # ✅ Analysis orchestration endpoints
│   │   │   ├── statistics.py     # ✅ Statistical data endpoints
│   │   │   ├── system.py         # ✅ System & container status endpoints
│   │   │   └── misc.py           # ✅ Misc / utility endpoints
│   │   └── api.py.backup         # 🗃️ Legacy aggregated API (kept for reference)
│   │
│   ├── services/                 # Business logic layer (Service Locator pattern)
│   │   ├── __init__.py           # ✅ Export service factory helpers
│   │   ├── service_locator.py    # ✅ Central DI / lazy instantiation
│   │   ├── task_manager.py       # ✅ Async task tracking abstraction
│   │   ├── analyzer_integration.py # ✅ Bridge to external analyzer processes
│   │   ├── analyzer_config_service.py # ✅ Analyzer config & capability loading
│   │   ├── model_service.py      # ✅ Model + generated app metadata operations
│   │   ├── batch_service.py      # ✅ Batch submission + aggregation
│   │   ├── security_service.py   # ✅ Fully implemented security analysis (DB-backed)
│   │   ├── docker_manager.py     # ✅ Implemented low-level Docker/compose orchestration
│   │   ├── background_service.py # ✅ Background maintenance / cleanup helpers
│   │   ├── openrouter_service.py # ✅ OpenRouter model capability integration
│   │   ├── port_service.py       # 🚧 Dynamic port allocation (PARTIAL stub)
│   │   ├── websocket_integration.py  # ✅ Active WebSocket/HTMX bridge
│   │   └── celery_websocket_service.py # ✅ Celery + WS utility wrapper
│   │
│   ├── utils/                    # Utility helpers
│   │   ├── __init__.py
│   │   ├── helpers.py            # ✅ Generic helpers
│   │   └── validators.py         # ✅ Input validation
│   │
│   ├── static/                   # (Legacy in-package static - may migrate to top-level static/)
│   │   ├── css/
│   │   └── js/
│   │
│   └── (legacy templates moved to top-level `templates/` directory)
│
├── templates/                    # Global Jinja2 templates (HTMX + dashboard)
│   ├── base.html                 # ✅ Unified base layout (AdminLTE themed)
│   ├── single_page.html          # ✅ Lightweight single-page base
│   ├── pages/                    # Page-level views
│   │   ├── dashboard.html        # ✅ Interactive dashboard UI
│   │   ├── analysis.html         # ✅ Analysis hub screen
│   │   ├── applications.html     # ✅ Generated apps explorer
│   │   ├── models.html           # ✅ Model registry overview
│   │   ├── statistics.html       # ✅ Metrics & trends page
│   │   ├── system_status.html    # ✅ System/container status page
│   │   └── about.html            # ✅ About / info
│   └── partials/                 # HTMX-fragment & component templates
│       ├── active_batches.html   # ✅ Batch status widget
│       ├── analysis/             # ✅ Analysis dashboard components
│       ├── applications/         # ✅ Application detail/overview fragments
│       ├── apps_grid/            # ✅ App grid/list + detail modals
│       ├── batch/                # ✅ Batch CRUD fragments
│       ├── common/               # ✅ Shared UI (sidebar, errors, timeline)
│       ├── dashboard/            # ✅ Dashboard stats/health widgets
│       ├── models/               # ✅ Model catalog components
│       ├── statistics/           # ✅ Statistics section fragments
│       ├── testing/              # ❌ Removed (use analysis/create/* and analysis/list/*)
│       └── system_status.html    # ✅ System status summary block
│
├── static/                       # Consolidated static assets
│   ├── css/
│   │   ├── adminlte.css          # ✅ Theme overrides
│   │   └── security-analysis.css # ✅ Security analysis styling
│   └── js/
│       ├── dashboard.js          # ✅ Dashboard interactions
│       └── theme_toggle.js       # ✅ Theme toggle handling
│
├── config/                       # Configuration modules
│   ├── __init__.py               # ✅ Config package init
│   ├── settings.py               # ✅ App & environment settings
│   └── celery_config.py          # ✅ Celery configuration
│
├── docs/                         # Project docs & change logs
│   ├── API.md
│   ├── DEVELOPMENT.md
│   ├── IMPLEMENTATION_SUMMARY.md
│   ├── README.md
│   ├── ROUTES.md                 # ✅ Route organization reference
│   ├── route_*                   # 🗃️ Route refactor progress artifacts
│   └── TODO.md                   # ✅ Pending tasks & priorities
│
├── tests/                        # Test suite (expanding)
│   ├── __init__.py
│   ├── conftest.py               # ✅ Pytest fixtures
│   ├── unit/                     # ✅ Unit tests (add coverage)
│   └── integration/             # ✅ Integration / Celery tests
│
└── PROJECT_STRUCTURE.md          # ✅ (This file)
```

## 🧹 Cleaned Up (Removed Files)

### ❌ Removed Legacy Files
- `src/app/routes.py` - Monolithic routes file (replaced by modular routes/)
- `src/run.py` - Legacy entry point (main.py is the proper entry point)
- `src/app.log` - Moved to `logs/app.log`
- `src/data/` - Empty directory removed
- `src/app/templates/pages/` - Empty directory removed
- `src/app/templates/components/` - Empty directory removed
- All `__pycache__/` directories and `.pyc` files

### 📁 Moved Files
- `src/app.log` → `logs/app.log`
- `src/README.md` → `src/docs/README.md`
- `src/IMPLEMENTATION_SUMMARY.md` → `src/docs/IMPLEMENTATION_SUMMARY.md`
- `src/test_celery_integration.py` → `src/tests/integration/test_celery_integration.py`

## 🏗️ Architecture Overview

### Service Layer (Business Logic)
Implemented:
- SecurityService (end-to-end DB + aggregation)
- DockerManager (compose orchestration + status/logs)
- ModelService (model & app metadata aggregation)
- BatchService (batch job orchestration)
- TaskManager (in-memory tracking for async tasks)
- AnalyzerIntegration / AnalyzerConfigService (bridging analyzer containers)
- OpenRouterService (external model metadata)
Partial / In Progress:
- PortService (basic port check + stub allocation logic)
- Higher-fidelity BackgroundService tasks (periodic cleanup, health scans)
Removed (legacy/unused):
- AnalyzerService (replaced by AnalyzerIntegration + Celery tasks)
- WebSocket Integration v2 shim
- ContainerService (unused stub)
- HuggingFace service stub
Pattern:
- Service Locator centralizes lazy instantiation & reuse

#### NEW: Analysis Engines Layer (2025-08 Refactor)

To reduce duplication and standardize execution flows a lightweight
`analysis_engines.py` module introduces small, focused engine classes
(`SecurityAnalyzerEngine`, `PerformanceAnalyzerEngine`, `StaticAnalyzerEngine`,
`DynamicAnalyzerEngine`). Each exposes a uniform:

```
engine.run(model_slug, app_number, **kwargs) -> EngineResult
```

They delegate to `AnalyzerIntegration` and normalize the response shape.
`analysis_service.py` gained optional `use_engine` flags on start methods
to permit synchronous invocation without Celery for fast paths / tests.

Legacy `AnalyzerService` was converted into a thin deprecated shim that
simply forwards to engines (and raises a `DeprecationWarning`).

Configuration convergence began with `analysis_config_models.py` which
contains lean dataclasses (`SecurityToolsConfig`, `PerformanceTestConfig`,
etc.) providing a single, simplified shape for callers while preserving
the richer legacy configs for future advanced use.

### Route Layer (Web Interface)
- Modular Blueprints: UI pages separated by domain (dashboard, analysis, models, batch, statistics, advanced)
- Fine-Grained API Subpackage: The `routes/api/` folder decomposes endpoints for maintainability & discoverability
- HTMX + Progressive Enhancement: Partial templates return fragment responses for dynamic updates
- Separate WebSocket REST helper blueprint mounted at `/api/websocket` (see `app/routes/api/websocket.py`) for starting/canceling analyses and querying WS service state
- Some UI blueprints intentionally expose small JSON/HTMX utilities under paths like `/analysis/api/...` or `/advanced/api/...` which are not part of the main `/api` blueprint; they serve page-specific partials or JSON
- Legacy Aggregated API retained as `api.py.backup` for reference during transition
  
See also: `docs/ROUTES.md` for a comprehensive, blueprint-grouped route inventory.

### Data Layer
- SQLAlchemy ORM models (analysis, applications, port config, security results, etc.)

## Service Layer Standardization (2025-08 Update)

To reduce boilerplate and clarify responsibilities the service layer adopted
lightweight shared utilities and a clear deprecation strategy:

### service_base.py
Located at `app/services/service_base.py`, this module provides:

- Exception hierarchy: `ServiceError`, `NotFoundError`, `ValidationError`, `ConflictError`, `OperationError`
- Helper: `ensure_dataclass_dict` (safe dataclass → dict)
- Helper: `deprecation_warning` (consistent `DeprecationWarning` emission)

All new/updated services raise these exceptions so route & API layers can map
them uniformly to HTTP responses.

### Deprecated Shims

Previously bloated or placeholder services are now minimal compatibility shims:

| Service | Status | Replacement / Direction |
|---------|--------|--------------------------|
| AnalyzerService | Deprecated shim | Analysis Engines (`analysis_engines.py`) + Celery tasks |
| ContainerService | Deprecated shim | `DockerManager` (low-level) or future external orchestrator |
| HuggingFaceService | Deprecated shim | Direct API utilities during batch ingest |
| PortService | Legacy (partial) | Opportunistic load via `ServiceLocator` + future refactor |

Each deprecated module exposes `DEPRECATED = True`. Public methods emit a
`DeprecationWarning` then raise `NotImplementedError` to make migration explicit
while avoiding sudden import failures.

### Guidelines for New Services
1. Keep synchronous services side‑effect free (no long-lived threads if avoidable).
2. Prefer Celery tasks or dedicated managers for external process orchestration.
3. Represent simple payloads with dataclasses; convert via `asdict` or helper.
4. Raise standardized exceptions only—avoid ad hoc custom exception classes.
5. Provide concise docstrings describing scope and explicit non‑responsibilities.

### Benefits
- Smaller, more readable service modules
- Consistent error handling path
- Easier unit testing (deterministic exceptions, pure functions)
- Clear migration story for legacy placeholders

These changes accompany the Analysis Engines refactor to continue the overall
goal of de‑bloating core logic and improving maintainability.
- SQLite (development) stored in `app/data/` with migration readiness (Alembic present at project root outside src)
- JSON fields for flexible analyzer result storage
- Future: switchable to Postgres (already abstracted by SQLAlchemy)

## 🎯 Recent Improvements

### 1. **Eliminated Conflicts**
- Removed duplicate routing systems
- Fixed import inconsistencies
- Cleaned up legacy files

### 2. **Proper Organization**
- Moved files to appropriate directories
- Organized templates by functionality
- Separated concerns cleanly

### 3. **Clear Structure**
- Documented stub services with implementation roadmap
- Established clear patterns for future development
- Created comprehensive documentation

### 4. **Development Ready**
- Fixed logging paths
- Cleaned up cache files
- Established proper entry points

## 🚀 Next Steps

1. Implement ContainerService (compose up/down, restart, health) integrating DockerManager + PortService
2. Flesh out PortService (DB-backed allocation, conflict detection, reservation lifecycle)
3. Implement AnalyzerService orchestration (queue fan-out to analyzer containers, result collation)
4. Expand test coverage (services: security, docker, model, batch; API endpoints; HTMX partial responses)
5. Add performance & load testing harness integration (link to analyzer performance tester)
6. Introduce background scheduled tasks (stale analysis cleanup, container health polling)
7. Prepare production config (env-based settings, Postgres & Redis externalization, container orchestration)
8. Security hardening (rate limiting, input validation audits, CSP headers)

## 🔧 Development Commands

```bash
# Launch (Flask + Celery worker separate terminals)
cd src
python main.py
celery -A app.tasks worker --loglevel=info

# Run (selective) tests
pytest tests/unit -q
pytest tests/integration -v

# Lint (if configured later)
ruff check .  # (planned)

# Clean Python caches (PowerShell)
Get-ChildItem -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force
```

---

**Structure Status**: ✅ Stable modular layout  
**Legacy Artifacts**: 🗃️ Contained / documented (api.py.backup, route_* docs); testing blueprint and partials removed in favor of analysis-only  
**Services**: Mixed (core implemented, orchestration stubs pending)  
**Documentation**: Up-to-date (reflects refactor phases)  
**Test Coverage**: Growing (needs expansion for new services)  
**Readiness**: Ready for continued feature implementation
