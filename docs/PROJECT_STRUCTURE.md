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
│   │   ├── testing.py            # ✅ Testing & validation views
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
│   │   ├── container_service.py  # 🚧 High-level app container orchestration (STUB)
│   │   ├── port_service.py       # 🚧 Dynamic port allocation (PARTIAL stub)
│   │   └── analyzer_service.py   # 🚧 Unified multi-tool analysis coordination (STUB)
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
│   │   ├── batch.html            # ✅ Batch operations page
│   │   ├── statistics.html       # ✅ Metrics & trends page
│   │   ├── testing.html          # ✅ Testing tools page
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
│       ├── testing/              # ✅ Security/performance test forms & results
│       └── system_status.html    # ✅ System status summary block
│
├── static/                       # Consolidated static assets
│   ├── css/
│   │   ├── adminlte.css          # ✅ Theme overrides
│   │   └── security-analysis.css # ✅ Security analysis styling
│   └── js/
│       ├── testing-dashboard.js  # ✅ Testing page polling dashboard logic
│       ├── realtime-dashboard.js # ✅ Optional Socket.IO realtime glue (flag-gated)
│       ├── testing-forms.js      # ✅ Testing forms helpers & UX
│       ├── enhanced-results.js   # ✅ Results table, filters, charts
│       └── analyzer-integration.js # ✅ Analyzer services WS integration (optional)
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
Planned / Stub:
- ContainerService (compose lifecycle w/ PortService & DB updates)
- AnalyzerService (unified multi-tool scheduling layer)
- Higher-fidelity BackgroundService tasks (periodic cleanup, health scans)
Pattern:
- Service Locator centralizes lazy instantiation & reuse

### Route Layer (Web Interface)
- Modular Blueprints: UI pages separated by domain (dashboard, analysis, models, batch, testing, statistics, advanced)
- Fine-Grained API Subpackage: The `routes/api/` folder decomposes endpoints for maintainability & discoverability
- HTMX + Progressive Enhancement: Partial templates return fragment responses for dynamic updates
- Separate WebSocket REST helper blueprint mounted at `/api/websocket` (see `app/routes/api/websocket.py`) for starting/canceling analyses and querying WS service state
- Some UI blueprints intentionally expose small JSON/HTMX utilities under paths like `/analysis/api/...` or `/advanced/api/...` which are not part of the main `/api` blueprint; they serve page-specific partials or JSON
- Legacy Aggregated API retained as `api.py.backup` for reference during transition
  
See also: `docs/ROUTES.md` for a comprehensive, blueprint-grouped route inventory.

### Data Layer
- SQLAlchemy ORM models (analysis, applications, port config, security results, etc.)
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
**Legacy Artifacts**: 🗃️ Contained / documented (api.py.backup, route_* docs)  
**Services**: Mixed (core implemented, orchestration stubs pending)  
**Documentation**: Up-to-date (reflects refactor phases)  
**Test Coverage**: Growing (needs expansion for new services)  
**Readiness**: Ready for continued feature implementation
