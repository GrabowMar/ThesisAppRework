# Copilot Instructions for ThesisAppRework

## Project Overview
**Purpose**: Research platform for generating and analyzing AI-generated applications across multiple dimensions (security, performance, code quality, AI reviews).

**Architecture**: Flask backend with Celery workers, Redis queue, Dockerized analyzer microservices (WebSocket-based), Bootstrap 5 + HTMX frontend with real-time updates.

**Key Directories**:
- `src/app/`: Flask application core
  - `routes/`: API and Jinja blueprints (organized: `api/`, `jinja/`, `websockets/`)
  - `services/`: Business logic (50+ services, see `ServiceLocator`)
  - `models/`: SQLAlchemy models (User, GeneratedApplication, AnalysisTask, etc.)
  - `tasks.py`: Celery task definitions with model gating
  - `factory.py`: App factory with extension initialization and service registration
  - `paths.py` + `constants.py`: Centralized path/enum definitions
- `analyzer/`: Analysis orchestration and microservices
  - `analyzer_manager.py`: CLI for container management and analysis execution
  - `services/`: Individual analyzer containers (static-analyzer:2001, dynamic-analyzer:2002, performance-tester:2003, ai-analyzer:2004)
  - `shared/`: WebSocket protocol and client utilities
- `generated/apps/`: AI-generated applications (structure: `{model_slug}/app{N}/`)
- `generated/metadata/`: Generation metadata (indices, runs)
- `generated/raw/`: Raw API payloads and responses
- `results/`: Analysis results (JSON, organized by model/app/task)
- `misc/`: Templates, scaffolding, requirements
  - `scaffolding/react-flask/`: Docker infrastructure templates (15 files)
  - `requirements/`: Template requirements JSONs (60+ templates)
  - `templates/`: V2 Jinja2-based prompt templates
- `docs/knowledge_base/`: Consolidated documentation (by topic)

## Essential Workflows

### Development
- **Run Flask App**: `cd src && python main.py` (port 5000)
  - Requires Celery worker: `celery -A app.tasks worker --loglevel=info`
  - Database auto-initializes on first run (SQLite: `src/data/thesis_app.db`)
- **Run Tests**: `pytest -m "not integration and not slow and not analyzer"` (fast suite)
  - VS Code tasks: "pytest - fast", "smoke: run http_smoke"
  - Markers: `@pytest.mark.integration`, `@pytest.mark.slow`, `@pytest.mark.analyzer`
- **Initialize/Reset DB**: `cd src && python init_db.py`
- **Create Admin User**: `python scripts/create_admin.py` (interactive) or set `ADMIN_USERNAME`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` in `.env`
- **Generate API Token**: `python scripts/generate_api_token.py` (for programmatic access)
- **Cleanup Logs**: `python scripts/log_cleanup.py` (maintenance utility)

### Analyzer Services
- **Start Services**: `python analyzer/analyzer_manager.py start`
- **Run Analysis**: `python analyzer/analyzer_manager.py analyze <model> <app> [type] [--tools ...]`
  - Types: `comprehensive`, `security`, `performance`, `static`, `dynamic`, `ai`
  - Tool filtering: `--tools bandit eslint` (service-specific, case-insensitive)
- **Batch Analysis**: `python analyzer/analyzer_manager.py batch <batch.json>`
  - Format: `[["model_slug", app_num], ...]`
- **Health/Status**: `python analyzer/analyzer_manager.py health` or `status`
- **Logs**: `python analyzer/analyzer_manager.py logs [service] [lines]`
- **Build Images**: `pwsh -NoProfile -ExecutionPolicy Bypass -Command "& .\analyzer\build.ps1"`
- **Stop Services**: `python analyzer/analyzer_manager.py stop`

## Patterns & Conventions

### Code Generation (Scaffolding-First Architecture)
**Location**: `src/app/services/generation.py` + `src/app/routes/api/generation.py`

**Philosophy**: Scaffolding (Docker infrastructure) is SACRED and copied first; AI generates ONLY application code files.

**Workflow**:
1. **Copy scaffolding** from `misc/scaffolding/react-flask/` (docker-compose.yml, Dockerfiles, configs)
2. **Allocate ports** via `PortAllocationService` (deterministic: model hash + app number)
3. **Substitute placeholders** in scaffolding: `{{backend_port|5000}}`, `{{frontend_port|8000}}`
4. **Generate code** via OpenRouter using requirements from `misc/requirements/{template_id}.json`
5. **Extract and merge** AI output into scaffolding structure

**API Endpoints** (require authentication):
- `POST /api/gen/generate` - Generate full app (frontend + backend)
- `GET /api/gen/templates` - List available requirement templates
- `GET /api/gen/apps` - List all generated apps
- `GET /api/gen/apps/<model>/<num>` - Get app details

**Template System**:
- Requirements: `misc/requirements/*.json` (4 templates: 1.json, 2.json, 3.json, 4.json - numeric naming only)
- Prompts: `misc/templates/*.jinja2` (V2 Jinja2-based system)
- Scaffolding: `misc/scaffolding/react-flask/` (15 files, NEVER modify directly)

**Port Allocation**:
- Base ports: backend 5001, frontend 8001
- Deterministic assignment: `hash(model_slug) + app_number`
- Database-backed via `PortConfiguration` model
- Auto-populates from `misc/port_config.json` on startup

**See**: `docs/features/SAMPLE_GENERATOR_REWRITE.md` for complete system details

### Analysis Architecture
**Analyzer Services** (WebSocket-based microservices):
- Each service runs in Docker, listens on dedicated port (2001-2004)
- Communication: WebSocket protocol (see `analyzer/shared/protocol.py`)
- Results: Written to `results/{model}/{appN}/analysis/{task_id}/service_name.json`
- Tool normalization: All services emit standardized `tool_results` map with per-tool status

**Tool Selection & Gating**:
- Per-analysis tool filtering: `--tools bandit eslint` (case-insensitive)
- Model-level gating: `DISABLED_ANALYSIS_MODELS=model1,model2` (skip analysis entirely)
- Implementation: `app/tasks.py` checks `is_analysis_disabled_for_model()`

**Legacy Result Pruning**: Per-service folders (e.g., `static-analyzer/`) auto-deleted after each run; only consolidated `analysis/` directory retained.

### Service Architecture
**Service Locator Pattern**: `app/services/service_locator.py`
- Core services auto-registered: `ModelService`, `GenerationService`, `DockerManager`, `HealthService`, `AnalysisInspectionService`, `ResultsManagementService`
- Retrieval: `ServiceLocator.get_<service_name>()` or `ServiceLocator.get('service_name')`
- Components: Extensions managed via `app/extensions.py` (Celery, TaskManager, AnalyzerIntegration, WebSocketService)

**WebSocket Service** (Real-time Progress):
- Default: Celery-backed service (`celery_websocket_service.py`)
- Fallback: Mock service if Celery init fails (unless `WEBSOCKET_STRICT_CELERY=true`)
- Control: `WEBSOCKET_SERVICE=auto|celery|mock`

**Path Management**: ALL paths centralized in `app/paths.py` (use instead of hardcoding)
- Generated content: `GENERATED_APPS_DIR`, `GENERATED_RAW_API_DIR`, `GENERATED_METADATA_DIR`
- Templates: `TEMPLATES_V2_DIR`, `SCAFFOLDING_DIR`, `REQUIREMENTS_DIR`
- Legacy: `CODE_TEMPLATES_DIR`, `APP_TEMPLATES_DIR` (deprecated, use V2)

### Frontend & UI
- **Stack**: Jinja2 templates + Bootstrap 5 + HTMX (NO jQuery, NO inline SVG)
- **Template Legacy Mapping**: Auto-resolves pre-restructure paths via `attach_legacy_mapping_loader(app)`
- **Real-time Updates**: WebSocket-based progress updates (port 8765 gateway)
- **Routes**: Organized into `routes/api/` (JSON endpoints), `routes/jinja/` (HTML), `routes/websockets/`

### Database & Tasks
- **Database**: SQLite dev (`src/data/thesis_app.db`), PostgreSQL prod
- **Models**: Auto-imported in `factory.py` before `db.create_all()` to prevent "no such table" errors
- **Celery**: `@celery.task(bind=True, name='app.tasks.task_name')` pattern
- **Task Execution**: Lightweight in-process service (`task_execution_service.py`) advances AnalysisTask state for dev/tests

### Configuration & Environment
- **Environment**: `.env` auto-loaded in `factory.py` (project root)
- **Logging**: Set `LOG_LEVEL=DEBUG|INFO|WARNING|ERROR`
- **OpenRouter**: `OPENROUTER_API_KEY` required for AI analysis
  - Research mode: `OPENROUTER_ALLOW_ALL_PROVIDERS=true` (bypass zero data retention restrictions)
- **Redis**: Auto-synthesizes `REDIS_URL` from `REDIS_HOST`+`REDIS_PORT` if missing
- **Session**: `SESSION_COOKIE_SECURE`, `SESSION_LIFETIME`, `PERMANENT_SESSION_LIFETIME`
- **Registration**: `REGISTRATION_ENABLED=false` by default (admin-created users only)

## Authentication & API Access

### User Authentication
**All routes require authentication** (Flask-Login + bcrypt password hashing):
- Web UI: Redirects to `/auth/login` for unauthenticated users
- API endpoints: Returns `401 Unauthorized` JSON response
- Exceptions: `/auth/login`, `/auth/logout`, `/health` (public)

### Creating Users
```bash
# Interactive mode (recommended)
python scripts/create_admin.py

# Command-line mode
python scripts/create_admin.py <username> <email> <password> [full_name]

# Environment variables (for automation)
export ADMIN_USERNAME=admin
export ADMIN_EMAIL=admin@example.com
export ADMIN_PASSWORD=secure_password
python scripts/create_admin.py
```

### API Token Authentication
**For programmatic access (AI agents, scripts, Copilot integration)**:

1. **Generate token** (via web UI or API):
   - Web: User Menu → API Access → Generate Token
   - API: `POST /api/tokens/generate` (requires login session)

2. **Use token in requests**:
   ```bash
   # Authorization header (preferred)
   curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:5000/api/models
   
   # Query parameter (less secure, but convenient)
   curl http://localhost:5000/api/models?token=YOUR_TOKEN
   ```

3. **Token management endpoints**:
   - `POST /api/tokens/generate` - Generate new token
   - `POST /api/tokens/revoke` - Revoke current token
   - `GET /api/tokens/status` - Check token status
   - `GET /api/tokens/verify` - Verify token validity (requires token in header)

### Environment Configuration for API Access
```bash
# .env file (for external tools/agents)
API_KEY_FOR_APP=your-generated-token-here

# Admin credentials (for user creation)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=secure_password

# Session security
SECRET_KEY=random-64-char-hex-string
SESSION_COOKIE_SECURE=false  # Set to true in production with HTTPS
SESSION_LIFETIME=86400  # 24 hours
REGISTRATION_ENABLED=false  # Prevent unauthorized account creation
```

### Token Security Notes
- Tokens are 48-character URL-safe strings (via `secrets.token_urlsafe(48)`)
- Stored hashed in database, indexed for fast lookup
- Associated with user account (respects `is_active` and `is_admin` flags)
- No expiration by default (revoke manually via API or web UI)
- Token authentication automatically loads user into Flask-Login session

## Integration Points
- **AI Analysis**: Uses OpenRouter API (set `OPENROUTER_API_KEY`)
  - For research purposes: `OPENROUTER_ALLOW_ALL_PROVIDERS=true` (default)
  - Bypasses Zero Data Retention restrictions to allow all models
  - Configure via `OPENROUTER_SITE_URL` and `OPENROUTER_SITE_NAME`
  - Chat service: `app/services/openrouter_chat_service.py` (streaming + non-streaming)
- **Security/Performance Tools**: Bandit, Safety, OWASP ZAP, Locust, ESLint, PyLint, Flake8
- **Celery**: Task queue for async analysis jobs (Redis broker/backend)
- **WebSocket Gateway**: Real-time progress updates (port 8765, see `analyzer/websocket_gateway.py`)
- **Analyzer Microservices**: 
  - static-analyzer (2001): PyLint, Flake8, ESLint, Bandit, Safety
  - dynamic-analyzer (2002): OWASP ZAP, connectivity tests, nmap
  - performance-tester (2003): aiohttp, Apache Bench, Locust
  - ai-analyzer (2004): OpenRouter-based code review
- **Configuration Management**: `src/app/config/config_manager.py` for analyzer settings
- **Component System**: Extensions managed via `app/extensions.py` with component registry
- **Container Management**: Full Docker lifecycle through UI (start/stop/restart/build/logs) via `DockerManager` service

## Troubleshooting & Tips
- **Service Health**: `python analyzer/analyzer_manager.py health` or check `/health` endpoint
- **Logs**: `python analyzer/analyzer_manager.py logs [service] [lines]`
- **Common Issues**: Ensure Docker is running, ports are available, containers are healthy
- **Testing**: Use VS Code tasks for quick smoke/fast tests; maintain >90% coverage
  - Fast suite excludes: `@pytest.mark.integration`, `@pytest.mark.slow`, `@pytest.mark.analyzer`
- **WebSocket Services**: Can fall back to mock service if Celery unavailable (set `WEBSOCKET_SERVICE=mock`)
- **Database Init**: Models auto-imported in `factory.py` before `db.create_all()`
- **Path Structure**: All paths centralized in `src/app/paths.py` and `src/app/constants.py`
- **Template Changes**: `TEMPLATES_AUTO_RELOAD=True` ensures Jinja picks up changes without restart
- **WebSocket Handshake Errors**: Benign "opening handshake failed" logs from port scans/non-WS probes; log level reduced for `websockets.server`


## Development Patterns
- **Factory Pattern**: App creation in `src/app/factory.py` with extension initialization
- **Service Registration**: Use `ServiceLocator.initialize(app)` for dependency injection
- **Background Tasks**: Task execution service handles lightweight in-process task advancement
- **Analysis Engines**: Engine registry in `src/app/services/analysis_engines.py` (compatibility layer for new tool-based orchestration)
- **Configuration Hierarchy**: environment vars → `settings.py` → `config_manager.py`
- **Error Handling**: Rich error handlers with HTML + JSON negotiation (see `app/errors.py`)
- **Request Logging**: Automatic request/response logging with timing and `request_id`
- **Jinja Utilities**: 
  - Globals: `make_safe_dom_id`, `now`, `current_app`
  - Filters: `datetime`, `timeago` (human-readable relative time)
- **Testing Cache Busting**: Aggressively clears Jinja bytecode cache when `PYTEST_CURRENT_TEST` detected

## GitHub Copilot & AI Agent Integration

### Quick Setup for Copilot/AI Agents
1. **Ensure Flask app is running**: `cd src && python main.py` (port 5000)
2. **Create user account** (if not exists): `python scripts/create_admin.py`
3. **Generate API token**:
   ```bash
   # Via web UI: Login → User Menu → API Access → Generate Token
   # Or via API (after login):
   curl -X POST http://localhost:5000/api/tokens/generate -H "Cookie: session=..."
   ```
4. **Add token to `.env`**: `API_KEY_FOR_APP=<your-token-here>`
5. **Test authentication**:
   ```bash
   curl -H "Authorization: Bearer $API_KEY_FOR_APP" http://localhost:5000/api/models
   ```

### Key API Endpoints for AI Agents
All endpoints require authentication via `Authorization: Bearer <token>` header or `?token=<token>` query parameter.

#### Model Management
- `GET /api/models` - List all available AI models
- `GET /api/models/<slug>` - Get model details
- `GET /api/models/<slug>/apps` - List apps for model

#### Generation (Scaffolding-First)
- `POST /api/gen/generate` - Generate new app
  ```json
  {
    "model": "openai_gpt-4",
    "template_id": 1,
    "temperature": 0.3
  }
  ```
- `GET /api/gen/templates` - List requirement templates
- `GET /api/gen/apps` - List all generated apps
- `GET /api/gen/apps/<model>/<num>` - Get app details

#### Analysis Execution
- `POST /api/analysis/run` - Run analysis on app
  ```json
  {
    "model_slug": "openai_gpt-4",
    "app_number": 1,
    "analysis_type": "security",
    "tools": ["bandit", "safety"]
  }
  ```
- `GET /api/analysis/tasks/<task_id>` - Get task status
- `GET /api/analysis/tasks/<task_id>/results` - Get results

#### System Status
- `GET /health` - Quick health check (no auth required)
- `GET /api/system/status` - Detailed system status
- `GET /api/system/overview` - Dashboard overview

### Authentication Flow for AI Agents
```python
import requests

# Setup
BASE_URL = "http://localhost:5000"
TOKEN = "your-api-token-here"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# Example: List models
response = requests.get(f"{BASE_URL}/api/models", headers=HEADERS)
models = response.json()

# Example: Generate app
response = requests.post(
    f"{BASE_URL}/api/gen/generate",
    headers=HEADERS,
    json={
        "model": "openai_gpt-4",
        "template_id": 1
    }
)
result = response.json()

# Example: Run analysis
response = requests.post(
    f"{BASE_URL}/api/analysis/run",
    headers=HEADERS,
    json={
        "model_slug": "openai_gpt-4",
        "app_number": 1,
        "analysis_type": "comprehensive"
    }
)
task = response.json()
```

### Troubleshooting AI Agent Access
- **401 Unauthorized**: Token invalid, expired, or user inactive
  - Verify token: `GET /api/tokens/verify` with `Authorization: Bearer <token>`
  - Regenerate: Login to web UI → API Access → Generate Token
- **403 Forbidden**: User lacks admin permissions (some endpoints admin-only)
- **Token not in `.env`**: Set `API_KEY_FOR_APP=<token>` in project root `.env`
- **Flask not running**: Start with `cd src && python main.py`
- **Port conflict**: Check Flask is on port 5000 (or update BASE_URL)

### Best Practices for AI Agents
- **Use Authorization header** over query parameter for security
- **Check `/health` first** before making authenticated requests
- **Handle 401s gracefully**: Token may have been revoked, prompt for regeneration
- **Use specific analysis types**: `security`, `performance`, `static`, `dynamic`, `ai` (avoid `comprehensive` for faster results)
- **Filter tools explicitly**: `--tools bandit safety` to reduce execution time
- **Monitor task status**: Poll `GET /api/analysis/tasks/<task_id>` for completion
- **Respect rate limits**: Flask dev server is single-threaded (production uses Gunicorn)

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
