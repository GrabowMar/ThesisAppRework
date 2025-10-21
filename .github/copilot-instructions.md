# Copilot Instructions for ThesisAppRework

## Project Overview
- **Purpose**: Platform for analyzing AI-generated applications (security, performance, code quality, AI reviews)
- **Architecture**: Flask backend, Celery workers, Redis queue, Dockerized analyzer microservices, Bootstrap 5 + HTMX frontend
- **Key Directories**:
  - `src/app/`: Flask app (routes, services, models, tasks)
  - `analyzer/`: Analyzer orchestration, Docker Compose, service management
  - `analyzer/services/`: Individual analyzer microservices (static, dynamic, performance, AI)
  - `results/`: Analysis outputs (JSON, timestamped)
  - `generated/apps/`: AI-generated applications for analysis (now moved to project root)
  - `scripts/`: Utility scripts (e.g., `find_unused_files_report.py`)
  - `docs/`: Architecture, API, and development documentation

## Essential Workflows
- **Start All Services**: `python analyzer/analyzer_manager.py start`
- **Run Analysis**: `python analyzer/analyzer_manager.py analyze <model> <app> [type] [--tools ...]`
- **Batch Analysis**: `python analyzer/analyzer_manager.py batch <batch.json>`
- **View Results**: See `results/` directory or use `python analyzer/analyzer_manager.py results`
- **Stop Services**: `python analyzer/analyzer_manager.py stop`
- **Run Tests**: `pytest` (see also VS Code tasks for fast/smoke tests)
- **Build Analyzer Images**: `pwsh -NoProfile -ExecutionPolicy Bypass -Command "& .\analyzer\build.ps1"`
- **Flask App**: `cd src && python main.py` (requires Celery worker: `celery -A app.tasks worker --loglevel=info`)
- **Initialize DB**: `cd src && python init_db.py`
- **Test Simple Generation**: `python scripts/test_simple_generation.py`

## Patterns & Conventions
- **Analyzer Services**: Each service runs in its own container, communicates via WebSocket, and writes results to `results/`
- **Batch Files**: JSON arrays of `[model, app]` pairs for batch analysis
- **Templates**: Use double-brace `{{placeholder}}` in code templates (see `misc/code_templates/`)
- **App Templates**: Enhanced with procedural guardrails (60 templates in `misc/app_templates/`)
- **Sample Generation**: NEW simplified system at `/api/gen/*` - see `docs/SIMPLE_GENERATION_SYSTEM.md`
  - **CRITICAL**: Old complex system (`/api/sample-gen/*`) is DEPRECATED - DO NOT USE
  - **CRITICAL**: Old service `sample_generation_service.py` (3700 lines) - DO NOT USE
  - **USE ONLY**: `simple_generation_service.py` for all new generation work
  - **USE ONLY**: `/api/gen/*` endpoints for all new frontend work
  - Proper scaffolding from `misc/scaffolding/react-flask/`
  - Backend: Clean code generation with proper file placement
  - Frontend: React/Vite with proper port configuration
  - See `docs/features/SAMPLE_GENERATOR_REWRITE.md` for complete details
  - Backend: 5-step workflow + 16-point validation (Flask/SQLAlchemy patterns)
  - Frontend: 8-step workflow + 20-point validation (React/Vite patterns)
  - All templates have `.bak` backups for rollback
- **Containerization**: All generated apps include complete Docker infrastructure
  - Scaffolding: `misc/scaffolding/react-flask/` (15 files: Dockerfiles, compose, configs)
  - Port Allocation: Automatic via `PortAllocationService` (BASE_BACKEND_PORT=5001, BASE_FRONTEND_PORT=8001)
  - Placeholders: `{{backend_port|5000}}` and `{{frontend_port|8000}}` syntax
  - Substitution: Happens in `ProjectOrganizer._scaffold_if_needed()`
  - Backfill: Use `scripts/backfill_docker_files.py` for existing apps
- **Frontend**: Jinja2 templates, Bootstrap 5, HTMX for dynamic UI; no jQuery or inline SVG
- **Environment**: Configure via `.env` (loads automatically in `factory.py`)
- **Database**: SQLite for dev, PostgreSQL for prod; migrations via Flask CLI
- **Celery Tasks**: Use `@celery.task(bind=True, name='app.tasks.task_name')` pattern
- **Service Locator**: Core services registered in `app/services/service_locator.py`
- **WebSocket Bridge**: Celery-backed or mock service for real-time progress updates
- **Model Gating**: Disable analysis for specific models via `DISABLED_ANALYSIS_MODELS=model1,model2`

## Integration Points
- **AI Analysis**: Uses OpenRouter API (set `OPENROUTER_API_KEY`)
  - For research purposes: `OPENROUTER_ALLOW_ALL_PROVIDERS=true` (default)
  - Bypasses Zero Data Retention restrictions to allow all models
  - Configure via `OPENROUTER_SITE_URL` and `OPENROUTER_SITE_NAME`
- **Security/Performance**: Bandit, Safety, OWASP ZAP, Locust, ESLint, PyLint, Flake8
- **Celery**: Task queue for async analysis jobs
- **WebSocket Gateway**: Real-time progress updates (port 8765)
- **Analyzer Microservices**: static-analyzer (2001), dynamic-analyzer (2002), performance-tester (2003), ai-analyzer (2004)
- **Configuration Management**: `src/app/config/config_manager.py` for analyzer settings
- **Component System**: Extensions managed via `app/extensions.py` with component registry
- **Container Management**: Full Docker lifecycle through UI (start/stop/restart/build/logs) via `DockerManager` service

## Troubleshooting & Tips
- **Service Health**: `python analyzer/analyzer_manager.py health` or check `/health` endpoint
- **Logs**: `python analyzer/analyzer_manager.py logs [service] [lines]`
- **Common Issues**: Ensure Docker is running, ports are available, containers are healthy
- **Testing**: Use VS Code tasks for quick smoke/fast tests; maintain >90% coverage
- **WebSocket Services**: Can fall back to mock service if Celery unavailable (set `WEBSOCKET_SERVICE=mock`)
- **Database Init**: Models auto-imported in `factory.py` before `db.create_all()`
- **Path Structure**: All paths centralized in `src/app/paths.py` and `src/app/constants.py`


## Development Patterns
- **Factory Pattern**: App creation in `src/app/factory.py` with extension initialization
- **Service Registration**: Use `ServiceLocator.initialize(app)` for dependency injection
- **Background Tasks**: Task execution service handles lightweight in-process task advancement
- **Analysis Engines**: Engine registry in `src/app/services/analysis_engines.py`
- **Configuration**: Hierarchical config: environment vars → `settings.py` → `config_manager.py`
- **Error Handling**: Rich error handlers with HTML + JSON negotiation
- **Request Logging**: Automatic request/response logging with timing and request_id

## References
- See `docs/knowledge_base/INDEX.md` for complete documentation index
- Topic-specific docs in `docs/knowledge_base/<topic>/README.md`
- Example batch file:
  ```json
  [
    ["anthropic_claude-3.7-sonnet", 1],
    ["openai_gpt-4", 2]
  ]
  ```
- Example analysis command:
  ```sh
  python analyzer/analyzer_manager.py analyze openai_gpt-4 2 security --tools bandit
  ```

---
For new patterns or unclear conventions, check `/docs` or ask for clarification in the repo.
