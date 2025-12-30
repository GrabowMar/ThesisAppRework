# Copilot instructions for ThesisAppRework

Use this as your working map for coding in this repo. Keep answers specific to these files, workflows, and conventions.

## Big picture
- Web app: Flask app in `src/` (entry: `src/main.py`, factory: `src/app/factory.py`). SocketIO is used when available; otherwise plain Flask.
- Analyzer system: 4 containerized services managed by `analyzer/analyzer_manager.py` and a WS gateway (`analyzer/websocket_gateway.py`). Services listen on:
  - static/code-quality: ws://localhost:2001
  - dynamic analyzer (ZAP etc.): ws://localhost:2002
  - performance tester (ab/aiohttp/locust): ws://localhost:2003
  - AI analyzer (OpenRouter-backed): ws://localhost:2004
  - Optional gateway for unified protocol: ws://0.0.0.0:8765
- Generated apps under `generated/apps/{model_slug}/app{N}/` are analyzed. Results are written to `results/{model_slug}/app{N}/task_{task_id}/...` plus a `manifest.json`.
- Tool outputs are normalized into a `tools` map; linters like ESLint/JSHint treat exit code 1 with findings as success (see `analyzer/README.md`). Legacy `analysis/` subfolders are auto-pruned.

## 🚀 Quick Debug & Development Reference (START HERE)

This section provides rapid diagnostics and solutions. **Use this first when encountering issues.**

### Instant health check
```bash
# Check everything at once
./start.ps1 -Mode Health

# Or manual breakdown:
./start.ps1 -Mode Status          # Dashboard view
python analyzer/analyzer_manager.py health   # Analyzer containers
curl http://localhost:5000/api/health        # Flask app (or use browser)
```

### Most common issues (90% of problems)

| Problem | One-liner fix |
|---------|---------------|
| **Flask not starting** | `./start.ps1 -Mode Stop` then `./start.ps1 -Mode Start` |
| **Port 5000 busy** | `taskkill /F /IM python.exe` (Windows) |
| **Analyzers offline** | `python analyzer/analyzer_manager.py start` |
| **Tasks stuck PENDING** | Restart Flask - TaskExecutionService starts fresh |
| **Tasks stuck RUNNING** | `python scripts/fix_task_statuses.py` |
| **API 401 errors** | Get new token: UI → User → API Access |
| **Container issues** | `./start.ps1 -Mode Rebuild` (fast) or `./start.ps1 -Mode CleanRebuild` (nuclear) |
| **Database locked** | Kill all Python, restart Flask |
| **Analysis timeout** | Increase `*_TIMEOUT` vars in `.env` (default: 1800s) |

### Quick service control
```bash
# Start/stop the whole stack
./start.ps1 -Mode Start    # Flask + Analyzers
./start.ps1 -Mode Stop     # Stop all
./start.ps1 -Mode Dev      # Flask only (fast dev mode)

# Analyzer-only control
python analyzer/analyzer_manager.py start
python analyzer/analyzer_manager.py stop
python analyzer/analyzer_manager.py restart

# Run analysis directly (CLI, no DB)
python analyzer/analyzer_manager.py analyze <model> <app> comprehensive
```

### See what's happening
```bash
./start.ps1 -Mode Logs                                    # All logs
python analyzer/analyzer_manager.py logs static-analyzer 50  # Container logs
Get-Content logs/app.log -Tail 50 -Wait                  # Flask logs (PowerShell)
```

### Database inspection (Python shell)
```python
from app.factory import create_app
from app.models import AnalysisTask, GeneratedApplication, AnalysisStatus
app = create_app()
with app.app_context():
    # Check pending tasks
    pending = AnalysisTask.query.filter_by(status=AnalysisStatus.PENDING).all()
    print(f"Pending: {len(pending)}")
    
    # Find a specific task
    task = AnalysisTask.query.filter_by(task_id="task_xxx").first()
    print(f"Status: {task.status}, Error: {task.error_message}")
    
    # List apps
    apps = GeneratedApplication.query.all()
    for app in apps[:5]:
        print(f"{app.model_slug}/app{app.app_number}: {app.container_status}")
```

### When nothing works - nuclear options
```bash
./start.ps1 -Mode Wipeout   # WARNING: Deletes all data, starts fresh
./start.ps1 -Mode Password  # Reset admin password
python src/init_db.py       # Reinitialize database (after backup!)
```

## Core developer workflows (Windows-friendly)
- **Quick start (recommended)**: Use `start.ps1` orchestrator for full stack management:
  - Interactive menu: `./start.ps1` (or just run the script)
  - Full stack: `./start.ps1 -Mode Start` (Flask + Analyzers)
  - Dev mode (Flask only): `./start.ps1 -Mode Dev -NoAnalyzer`
  - Status dashboard: `./start.ps1 -Mode Status`
  - View logs: `./start.ps1 -Mode Logs`
  - Stop all: `./start.ps1 -Mode Stop`
  - Health check: `./start.ps1 -Mode Health`
- **Manual start**:
  - Flask only (port 5000): run `src/main.py`. SocketIO is used if available.
  - Analyzers (Docker required): `python analyzer/analyzer_manager.py start` then `... status` or `... health`.
- Run an analysis directly (fastest for scripts):
  - `python analyzer/analyzer_manager.py analyze openai_gpt-4 1 security --tools bandit`
  - Comprehensive: `... analyze <model> <app> comprehensive`
  - Batch: `... batch models.json` or `... batch-models model1,model2`
  - Results: `... list-results [--model <model>]` or `... show-result <model> <app>`
- **VS Code Tasks** (`.vscode/tasks.json`): use "Terminal → Run Task" and pick one of:
  - **Testing Tasks**:
    - `pytest: unit tests only` ⭐ (default, fastest ~5s) - Quick unit test cycle, excludes integration/slow/analyzer
    - `pytest: smoke tests` - Fast critical path health check (~10s)
    - `pytest: integration tests` - All integration tests across all suites
    - `pytest: api integration` - API endpoint integration tests only
    - `pytest: websocket integration` - WebSocket protocol tests only
    - `pytest: analyzer integration` - Analyzer service tests only (requires Docker)
    - `pytest: web ui integration` - Web UI interaction tests only
    - `pytest: all tests` - Full test suite (no marker filtering, ~2-5 min)
  - **Analysis Tasks**:
    - `analyzer: start services` - Start all analyzer Docker containers
    - `analyzer: stop services` - Stop all analyzer containers
    - `analyzer: service status` - Check container and port status
    - `analyzer: service health` - Health check across all services
  - **Maintenance Tasks**:
    - `flask: run dev server` - Start Flask development server (port 5000)
    - `db: run migrations` - Apply pending database migrations
    - `scripts: sync generated apps` - Sync filesystem apps to database
    - `scripts: fix task statuses` - Recover stuck/orphaned tasks
- **Tests**: prefer `pytest -m "not integration and not slow and not analyzer"` for quick cycles. Smoke tests via `pytest tests/smoke/`. Full suite runs without markers.
- **VS Code Test Explorer**: open Testing panel (Ctrl+Shift+T) for interactive test discovery, running individual tests, and debugging with breakpoints. Right-click any test to run/debug, view in Test Explorer sidebar for hierarchical organization.

### Choose your path: CLI vs UI vs API
- CLI (fast/dev/automation without DB records): use `analyzer/analyzer_manager.py` directly; writes results to `results/...` only.
- UI (interactive with DB tracking): submit via `/analysis/create`; real-time progress and results in the app.
- API (automation with DB tracking): `POST /api/analysis/run` with Bearer token; same result structure as UI.

## Key conventions and patterns
- Model slug normalization: analyzer accepts variants and normalizes slugs (see `analyzer/analyzer_manager.py` and `app.utils.slug_utils`). Prefer `provider_model-name` (e.g., `openai_gpt-4`).
- Port resolution for dynamic/perf tests: first from the app `.env` in `generated/apps/...`, else from DB/JSON (see `_resolve_app_ports`). When running inside containers, targets use `http://host.docker.internal:{port}`.
- Results contract (per task): `results/{model}/app{N}/task_{task}/` contains:
  - Primary consolidated JSON with `results.services`, flat `tools`, `summary`, and aggregated `findings` (see `save_task_results`).
  - Per-service snapshots under `services/`.
  - SARIF files extracted to `sarif/` subdirectory (e.g., `static_bandit.sarif.json`, `static_semgrep.sarif.json`) to reduce main JSON size.
  - Legacy `analysis/` folders are auto-migrated to task-based structure on discovery.
- WebSocket frames: services may stream progress; code waits for a terminal `*_analysis_result` frame and wraps partials when needed. When integrating, expect progress updates before final payloads.
- Environment flags commonly used:
  - `OPENROUTER_API_KEY` (AI analyzer), `LOG_LEVEL`, `ANALYZER_ENABLED`, `ANALYZER_AUTO_START`.
  - Timeouts: `STATIC_ANALYSIS_TIMEOUT`, `SECURITY_ANALYSIS_TIMEOUT`, `PERFORMANCE_TIMEOUT`.
- Service selection: you can gate tool lists via `--tools` (e.g., `--tools bandit,eslint`) and analyzer manager will pass them through to the service.

## Where to look when coding
- Flask wiring and services: `src/app/factory.py` (ServiceLocator, WS service selection, DB init, Jinja setup).
- Analyzer control, saving, and normalization: `analyzer/analyzer_manager.py` (`run_*` methods, `_aggregate_findings`, `_collect_normalized_tools`, result persistence).
- Unified WS gateway and shared protocol: `analyzer/websocket_gateway.py` and `analyzer/shared/protocol.py`.
- Test organization: `tests/` (unit, smoke, integration/{api,websocket,analyzer,web_ui}); markers: `smoke`, `integration`, `slow`, `analyzer`, `api`, `websocket`, `web_ui`, `async`.
- End-to-end workflow docs: `analyzer/README.md`.

### Key files quick reference

| Need to... | Look in... |
|------------|------------|
| Change Flask startup | `src/main.py`, `src/app/factory.py` |
| Add/modify API endpoint | `src/app/routes/api/*.py` |
| Change task execution | `src/app/services/task_execution_service.py` |
| Modify analysis flow | `analyzer/analyzer_manager.py` |
| Add new analyzer tool | `analyzer/services/{service}/main.py` |
| Change container config | `analyzer/docker-compose.yml` |
| Modify DB models | `src/app/models/*.py` |
| Add new service | `src/app/services/`, register in `factory.py` |
| Change UI templates | `src/templates/*.html` |
| Add tests | `tests/unit/`, `tests/integration/`, `tests/smoke/` |
| Update configs | `.env`, `analyzer/configs/` |

## Typical tasks you’ll automate
- Trigger analysis for an app created under `generated/apps/...`, then read consolidated results under `results/.../task_{id}/`.
- Add a new static/dynamic tool: extend the respective analyzer service to emit normalized tool entries and ensure `_aggregate_findings` can extract findings.
- Wire a new API endpoint to create `AnalysisTask`s and dispatch via analyzer manager or the WS gateway. Follow patterns in `src/app/services/*` and existing routes.

## API tokens (automation)
- **Quick access for Copilot**: Read token from `.env` file: `API_KEY_FOR_APP` variable contains a valid Bearer token
- Generate a Bearer token via UI (User → API Access) or see `docs/API_AUTH_AND_METHODS.md` for alternatives.
- Verify quickly: `GET /api/tokens/verify` with `Authorization: Bearer <token>`.
- Use with `POST /api/analysis/run` to create an `AnalysisTask` and kick off analysis; results are written to `results/{model}/app{N}/task_{task}/` and visible in the UI.

### Dynamic API Token for Copilot Automation
When automating via API calls, use the token from `.env`:
```bash
# Token location: .env file, variable API_KEY_FOR_APP
# Current token: DZHnCEy0b2rkWu6RI8wDMgSZ2NTSPNOLMVr7AU-HqcqgghDmLoZfN2XMYEz4FVsT

# Example API calls:
# Generate app:
curl -X POST http://localhost:5000/api/gen/generate \
  -H "Authorization: Bearer $API_KEY_FOR_APP" \
  -H "Content-Type: application/json" \
  -d '{"model_slug": "deepseek/deepseek-v3.2", "template_slug": "crud_todo_list"}'

# Run analysis:
curl -X POST http://localhost:5000/api/analysis/run \
  -H "Authorization: Bearer $API_KEY_FOR_APP" \
  -H "Content-Type: application/json" \
  -d '{"model_slug": "deepseek_deepseek-v3.2", "app_number": 1, "analysis_type": "comprehensive"}'
```

## API endpoints → services
- `POST /api/analysis/run` → creates `AnalysisTask`, then analyzer integration dispatches to containers (static/dynamic/perf/ai) via `AnalyzerManager` or the WS gateway.
- `POST /api/app/{model_slug}/{app_number}/analyze` → shorthand for running an analysis against a specific generated app.
- Gateway: `analyzer/websocket_gateway.py` listens on `ws://0.0.0.0:8765` and proxies to service WS endpoints (2001–2004), rebroadcasting progress frames to subscribers.

### API Modules (all in `src/app/routes/api/`)
| Module | Prefix | Purpose |
|--------|--------|--------|
| `analysis` | `/api/analysis/` | Analysis operations, tool registry |
| `applications` | `/api/apps/` | App CRUD, container ops |
| `container_tools` | `/api/container-tools/` | Container tool operations |
| `core` | `/api/` | Health, status endpoints |
| `dashboard` | `/api/dashboard/` | Dashboard stats |
| `export` | `/api/export/` | Export results |
| `generation` | `/api/gen/` | App generation |
| `models` | `/api/models/` | Model management |
| `reports` | `/api/reports/` | Report generation |
| `results` | `/api/results/` | Results retrieval |
| `statistics` | `/api/statistics/` | Aggregated stats |
| `system` | `/api/system/` | System ops, config |
| `tasks_realtime` | `/api/tasks/` | Real-time task updates (SSE) |
| `templates` | `/api/templates/` | Template management |
| `tokens` | `/api/tokens/` | API token management |
| `tool_registry` | `/api/tool-registry/` | Available tools |

## AnalysisTask model and lifecycle
- **Key fields** (`src/app/models/analysis.py`):
  - `task_id` - Unique identifier (e.g., "task_abc123")
  - `target_model` - Model slug (normalized)
  - `target_app_number` - App number to analyze
  - `status` - Current state (see lifecycle below)
  - `service_name` - e.g., 'static-analyzer' for subtasks
  - `analyzer_config_id` - Optional analyzer profile reference
  - `batch_id` - For batch processing grouping
  - `parent_task_id` - For subtask hierarchies
  - `is_main_task` - True for parent tasks in batch operations
  - `task_name` - Human-readable name
  - `progress_percentage`, `progress_message` - Progress tracking
  - `result_summary` - JSON summary of results
  - `error_message` - Failure details if status is FAILED
  - `retry_count`, `max_retries` (default: 3) - For automatic retry on transient failures
  - Timestamps: `created_at`, `started_at`, `completed_at`
- **Status lifecycle**:
  - `INITIALIZING` - Task created, subtasks being created (unified analysis)
  - `PENDING` - Task created, waiting for execution (auto-picked by TaskExecutionService)
  - `RUNNING` - Currently executing analysis
  - `COMPLETED` - Successfully finished
  - `PARTIAL_SUCCESS` - Some subtasks succeeded, some failed
  - `FAILED` - Error occurred (check `error_message`)
  - `CANCELLED` - User-cancelled or timed out
  - Auto-recovery: Stuck RUNNING tasks (>30min) → FAILED on startup; old PENDING tasks (>30min) → CANCELLED
- **TaskExecutionService** (background daemon in `src/app/services/task_execution_service.py`):
  - Polls database every 2s (test mode) or 5s (production) for PENDING tasks
  - Dispatches via `AnalyzerIntegrationService` to analyzer manager
  - Updates task status based on execution result
  - Writes filesystem results to `results/{model}/app{N}/task_{id}/`
  - Started automatically in `src/app/factory.py` during app initialization
  - **Automatic retry**: Tasks that fail due to service unavailability are retried up to 3 times with exponential backoff

## Background services (auto-started)

### Startup Sequence (CRITICAL ORDER)

The Flask app initialization follows a **specific sequence**:

1. **MaintenanceService initializes FIRST** (manual mode by default - no auto-start)
2. **TaskExecutionService starts SECOND** → Picks up PENDING tasks

**New maintenance behavior (as of Nov 2025)**:
- Maintenance is now **manual by default** (controlled via `start.ps1 -Mode Maintenance`)
- Apps get a **7-day grace period** before deletion (tracked via `missing_since` timestamp)
- Auto-start only if `MAINTENANCE_AUTO_START=true` environment variable is set
- This prevents aggressive auto-cleanup during development

### TaskExecutionService (`src/app/services/task_execution_service.py`)
**Purpose**: Asynchronous task execution daemon that processes pending analysis tasks.

**Lifecycle**:
- Initialized and started automatically in `src/app/factory.py` during app creation
- Runs in separate daemon thread (non-blocking)
- Polls database every **2 seconds** (test mode) or **5 seconds** (production)
- Gracefully stops on app shutdown (waits for current task to complete)

**Operation**:
1. Queries database for tasks with `status=PENDING` ordered by priority DESC, created_at ASC
2. Picks oldest high-priority task (or oldest task if no priority set)
3. Dispatches to `AnalyzerIntegrationService.run_analysis()`
4. Updates task status: `PENDING` → `RUNNING` → `COMPLETED`/`FAILED`
5. Writes results to `results/{model}/app{N}/task_{id}/`
6. Stores summary in `task.result_summary` JSON field

**Debugging**:
```python
# Check if service is running
from app.services.service_locator import ServiceLocator
service = ServiceLocator.get_task_execution_service()
print(f"Running: {service._running}")  # Should be True
print(f"Current task: {service._current_task_id}")  # None if idle

# Find stuck tasks
from app.models import AnalysisTask, AnalysisStatus
stuck = AnalysisTask.query.filter_by(status=AnalysisStatus.RUNNING).all()
for task in stuck:
    print(f"{task.task_id}: running since {task.started_at}")

# Manual recovery (if service died)
python scripts/fix_task_statuses.py
```

**Configuration**:
- Poll interval: set via `TASK_POLL_INTERVAL` env var (default: 5s prod, 2s test)
- Max concurrent: currently 1 task at a time (sequential execution)
- Timeout: inherits from `TASK_TIMEOUT` (default 1800s = 30min)

### MaintenanceService (`src/app/services/maintenance_service.py`)
**Purpose**: Manual cleanup and recovery of orphaned resources (now manual by default).

**NEW BEHAVIOR (Nov 2025)**:
- **Manual operation by default** - run via `./start.ps1 -Mode Maintenance`
- **7-day grace period** for missing apps before deletion
- **missing_since timestamp tracking** - apps marked when filesystem directory disappears
- **Auto-restore** - if directory reappears, `missing_since` is cleared (no deletion)

**Lifecycle**:
- Initialized in `src/app/factory.py` with `auto_start=False` (manual mode)
- Auto-start only if `MAINTENANCE_AUTO_START=true` env var is set
- When auto-started, runs once on initialization then hourly

**Manual Cleanup** (recommended - via `./start.ps1 -Mode Maintenance`):
1. **Orphan app tracking**: Apps missing from filesystem get `missing_since` timestamp
2. **7-day grace period**: Only deletes apps missing for >7 days
3. **Auto-restore**: Clears `missing_since` if filesystem directory reappears
4. **Orphan tasks**: Cancels tasks targeting non-existent apps
5. **Stuck tasks**: RUNNING >2 hours → FAILED, PENDING >4 hours → CANCELLED
6. **Old tasks**: Deletes completed/failed/cancelled tasks >30 days old

**Configuration**:
```python
# Default config in MaintenanceService.__init__
config = {
    'cleanup_orphan_apps': True,
    'cleanup_orphan_tasks': True,
    'cleanup_stuck_tasks': True,
    'cleanup_old_tasks': True,
    'task_retention_days': 30,
    'stuck_task_timeout_minutes': 120,  # 2 hours for RUNNING
    'pending_task_timeout_minutes': 240,  # 4 hours for PENDING
    'grace_period_minutes': 5,  # Skip very recent tasks
    'orphan_app_retention_days': 7,  # NEW: 7-day grace period for missing apps
}
```

**Environment Variables**:
- `MAINTENANCE_AUTO_START=true` - Enable automatic background cleanup (default: false)
- `MAINTENANCE_INTERVAL_SECONDS=3600` - Cleanup interval when auto-started (default: 1 hour)

**Usage**:
```bash
# Recommended: Manual cleanup via orchestrator
./start.ps1 -Mode Maintenance

# Or run Python directly
python -c "from app.factory import create_app; from app.services.maintenance_service import get_maintenance_service; \
app = create_app(); \
with app.app_context(): get_maintenance_service()._run_maintenance()"
```

**Database Schema Change**:
- Run `python scripts/add_missing_since_column.py` once to add `missing_since` column
- Column: `missing_since` (DATETIME, nullable, default NULL)
- Tracks when app filesystem directory first went missing

**Logs**: All cleanup operations logged to `logs/app.log` with INFO level:
```
[MaintenanceService] Marked 2 apps as missing (grace period: 7 days)
[MaintenanceService] Restored 1 apps (filesystem directories reappeared)
[MaintenanceService] Found 1 orphan apps ready for deletion (missing for >7 days)
[MaintenanceService] Cleaned up 1 orphan app records
```

## Gotchas and non-obvious behaviors

### Maintenance Service Changes (Nov 2025)
- **Apps no longer auto-deleted on startup** - maintenance is manual by default
- **7-day safety buffer** - apps must be missing for a week before deletion
- **Reversible marking** - restoring filesystem directory clears `missing_since` flag
- **Legacy script deprecated** - `scripts/cleanup_generated_apps.py` bypasses safety mechanisms; use `start.ps1 -Mode Maintenance` instead
- **Migration required** - run `scripts/add_missing_since_column.py` once to add new column

### Result Storage Evolution
- **Don't assume `results/analysis/` exists**: New runs organize by `task_{id}` at app root level (`results/{model}/app{N}/task_{id}/`)
- **Legacy migration**: Old `analysis/` subfolders are auto-migrated to task-based structure on discovery
- **SARIF extraction**: SARIF data (from bandit/semgrep) extracted to separate `sarif/` subdirectory:
  - Main JSON contains **references only** (e.g., `{"sarif_file": "sarif/static_bandit.sarif.json"}`)
  - Actual SARIF in `results/{model}/app{N}/task_{id}/sarif/static_bandit.sarif.json`
  - Reduces main consolidated JSON size by 60-80% for large codebases
- **Per-service snapshots**: Each service writes detailed output to `services/{service-name}.json` for debugging

### Port Resolution for Dynamic/Performance Tests
- **Priority order**: 
  1. Generated app `.env` file (`generated/apps/{model}/app{N}/.env` with `BACKEND_PORT`/`FRONTEND_PORT`)
  2. Database `PortConfiguration` model (auto-populated from `misc/port_config.json`)
  3. Error if neither exists
- **Container networking**: Services inside Docker must use `http://host.docker.internal:{port}` (not `localhost`) to reach generated apps
- **Port conflicts**: Dynamic port allocation (3000-4999) prevents conflicts; check `misc/port_config.json` for current mappings

### Linter Exit Code Handling
- **ESLint/JSHint special case**: Exit code 1 with valid JSON output = **success** (findings present, not an error)
- **Actual failures**: Exit code >1 OR invalid/missing JSON output = error (infrastructure/process failure)
- **Status normalization**: Tool status becomes `success` (with findings), `no_issues` (clean), or `error` (failed to run)
- **Why**: Linters return non-zero when they find issues; this is expected behavior, not a failure

### Task Execution Timing
- **Not immediate**: Tasks created via UI/API enter `PENDING` state; TaskExecutionService picks them up asynchronously
- **Poll interval**: 2s (test mode) or 5s (production) between polls
- **Sequential execution**: Currently 1 task at a time; subsequent tasks wait in queue
- **Check progress**: Query `task.status` to see state; `RUNNING` means actively executing, check `task.started_at` for how long

### Analyzer Connection Resilience (Dec 2025)
- **Pre-flight health checks**: Before starting subtasks, system verifies all required analyzer services (ports 2001-2004) are accessible
- **Retry with exponential backoff**: WebSocket connections retry up to 3 times with 2s/4s/8s delays for transient failures
- **TCP port check before WebSocket**: Uses socket-level check to verify port accessibility before attempting WebSocket handshake
- **Clear error messages**: If services are down, error clearly states which services are inaccessible and how to fix
- **Circuit breaker**: After 3 consecutive failures to a service, that service is put in 5-minute cooldown
- **Recovery**: Services automatically become available again after cooldown expires or on first success
- **Automatic task retry**: Tasks that fail pre-flight checks are automatically rescheduled (up to 3 retries with 30s/60s/120s delays)
- **Transient failure recovery**: Failed tasks due to service unavailability are auto-recovered when services become available (checked every 5 min)
- **Configuration**: `PREFLIGHT_MAX_RETRIES` and `TRANSIENT_FAILURE_MAX_RETRIES` env vars control retry limits (default: 3)

### Container Rebuild Strategies
- **Fast incremental** (`./start.ps1 -Mode Rebuild`): 
  - Uses BuildKit cache mounts (30-90 seconds)
  - Preserves pip/npm package caches between builds
  - Rebuilds only changed layers
  - **Use this** for code changes, dependency updates
- **Clean rebuild** (`./start.ps1 -Mode CleanRebuild`):
  - No cache, full rebuild (12-18 minutes)
  - Pulls base images, reinstalls everything
  - **Use this** for major dependency changes, Dockerfile modifications, cache corruption
- **BuildKit optimizations**:
  - `--mount=type=cache,target=/root/.cache/pip` - Persistent pip cache
  - `--mount=type=cache,target=/root/.npm` - Persistent npm cache
  - Shared base image across all analyzer services reduces rebuild time

### WebSocket Frame Sequences
- **Progress updates**: Services emit `progress_update` frames during long operations (e.g., scanning files)
- **Terminal frame**: Wait for frame with type ending in `_analysis_result` (e.g., `static_analysis_result`)
- **Don't return early**: First frame might be progress (0%), not the final result
- **Gateway behavior**: `analyzer/websocket_gateway.py` rebroadcasts all frames to subscribers; clients must filter

### SocketIO Availability Fallback
- **Preferred mode**: SocketIO for real-time updates (progress bars, live logs)
- **Fallback mode**: Standard Flask if SocketIO import fails or not installed
- **Check availability**: `from app.extensions import SOCKETIO_AVAILABLE` (boolean)
- **Impact**: UI still functional without SocketIO, but uses polling instead of push updates
- **When it happens**: Fresh installs without `flask-socketio` in requirements, or import errors

## Minimal examples
- Start services then run a security pass:
  - `python analyzer/analyzer_manager.py start`
  - `python analyzer/analyzer_manager.py analyze anthropic_claude-3.7-sonnet 1 security --tools bandit,safety`
- Programmatic use:
  ```python
  from analyzer.analyzer_manager import AnalyzerManager
  import asyncio
  async def go():
      m = AnalyzerManager()
      await m.run_comprehensive_analysis("openai_gpt-4", 1)
  asyncio.run(go())
  ```

Keep contributions aligned with these patterns and prefer citing concrete files from above in your outputs.

## Common development scenarios

### Scenario: Running your first analysis
```bash
# 1. Start everything
./start.ps1 -Mode Start

# 2. Wait for containers (check health)
python analyzer/analyzer_manager.py health

# 3. Run analysis (CLI - fast, no DB tracking)
python analyzer/analyzer_manager.py analyze openai_gpt-4 1 comprehensive

# 4. Results are in: results/openai_gpt-4/app1/task_xxx/
```

### Scenario: Debugging a failed analysis task
```bash
# 1. Find the task
python -c "
from app.factory import create_app
from app.models import AnalysisTask
app = create_app()
with app.app_context():
    task = AnalysisTask.query.filter_by(task_id='task_xxx').first()
    print(f'Status: {task.status}')
    print(f'Error: {task.error_message}')
    print(f'Started: {task.started_at}')
"

# 2. Check analyzer logs
python analyzer/analyzer_manager.py logs static-analyzer 100

# 3. If container issue, rebuild
./start.ps1 -Mode Rebuild
```

### Scenario: Adding a new static analysis tool
```python
# 1. In analyzer/services/static-analyzer/main.py, add handler:
async def run_my_new_tool(self, source_path: str) -> dict:
    # Run your tool
    result = subprocess.run(['mytool', source_path], capture_output=True)
    return {
        "status": "success" if result.returncode == 0 else "error",
        "findings": parse_output(result.stdout),
        "raw_output": result.stdout.decode()
    }

# 2. Register in the tool dispatcher (same file)
# 3. Update analyzer_manager.py:_collect_normalized_tools()
# 4. Add tests in tests/unit/
# 5. Rebuild container: ./start.ps1 -Mode Rebuild
```

### Scenario: Creating a new API endpoint
```python
# 1. In src/app/routes/api/my_module.py:
from flask import Blueprint, jsonify, request
from app.decorators import require_auth

bp = Blueprint('my_api', __name__, url_prefix='/api/my')

@bp.route('/endpoint', methods=['POST'])
@require_auth
def my_endpoint():
    data = request.get_json()
    # Do something
    return jsonify({"status": "success", "data": result})

# 2. Register in src/app/factory.py:
from app.routes.api import my_module
app.register_blueprint(my_module.bp)

# 3. Test with curl:
curl -X POST http://localhost:5000/api/my/endpoint \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"key": "value"}'
```

### Scenario: Investigating slow performance
```bash
# 1. Enable debug logging
# In .env: LOG_LEVEL=DEBUG

# 2. Check what's taking time
./start.ps1 -Mode Logs

# 3. Profile specific analyzer
python analyzer/analyzer_manager.py analyze model 1 static --tools bandit

# 4. Check container resources
docker stats

# 5. If needed, increase resources in analyzer/docker-compose.yml
```

### Scenario: Running tests before PR
```bash
# Quick unit tests (always run these)
pytest -m "not integration and not slow and not analyzer" -v

# Smoke tests (run before every PR)
pytest tests/smoke/ -v

# Full integration (run for major changes)
pytest tests/integration/ -v

# With coverage
pytest --cov=src --cov-report=html -m "not slow"
```

## Documentation architecture

The repository maintains two documentation tiers:

1. **This file (`.github/copilot-instructions.md`)**: Authoritative source of truth for AI assistants and developers. Contains detailed implementation specifics, gotchas, and code-level guidance. Updated with each feature change.

2. **Public docs (`docs/` folder)**: User-facing documentation for setup, API reference, and conceptual architecture. Derived from this file but simplified for readability.

**When updating documentation**:
- Update this file FIRST with implementation details
- Then propagate changes to relevant files in `docs/`
- Keep `docs/` focused on "how to use" rather than "how it works internally"

**Documentation files in `docs/`**:
| File | Purpose |
|------|---------|
| [QUICKSTART.md](../docs/QUICKSTART.md) | Getting started, prerequisites, first run |
| [ARCHITECTURE.md](../docs/ARCHITECTURE.md) | System design, data flow, component overview |
| [api-reference.md](../docs/api-reference.md) | REST API endpoints, WebSocket events, authentication |
| [ANALYZER_GUIDE.md](../docs/ANALYZER_GUIDE.md) | Analyzer services, tools, CLI usage |
| [BACKGROUND_SERVICES.md](../docs/BACKGROUND_SERVICES.md) | TaskExecution, Maintenance, Pipeline services |
| [TROUBLESHOOTING.md](../docs/TROUBLESHOOTING.md) | Common issues, recovery procedures |
| [deployment-guide.md](../docs/deployment-guide.md) | Production deployment, Docker, environment |
| [development-guide.md](../docs/development-guide.md) | Contributing, testing, code style |
| [MODELS_REFERENCE.md](../docs/MODELS_REFERENCE.md) | Model slugs, providers, templates |
| [GENERATION_PROCESS.md](../docs/GENERATION_PROCESS.md) | App generation workflow, GUARDED mode, scaffolding |
| [TEMPLATE_SPECIFICATION.md](../docs/TEMPLATE_SPECIFICATION.md) | Requirement template format, 30 templates list |
| [ANALYSIS_PIPELINE.md](../docs/ANALYSIS_PIPELINE.md) | 21 analysis tools, 4 services, SARIF output |

## Repository organization (clean state)
- **Root directory**: Only essential files (README.md, requirements.txt, pytest.ini, docker-compose.yml, start.ps1)
- **No temporary files**: Status markdown files and debug scripts have been cleaned up (Nov 2025)
- **All tests in `tests/`**: No root-level test scripts - use `pytest` from the official test suite
- **Documentation in `docs/`**: Comprehensive guides in `docs/`, reference materials in `docs/guides/`
- **Clean outputs**: `generated/` for apps, `results/` for analysis data, `reports/` for generated reports
- **Scripts organized**: Utility/maintenance scripts in `scripts/`, not scattered in root

## Debugging quick reference

### 🔴 STOP - Diagnose first
Before making changes, run these diagnostics:
```bash
# 1. Check what's running
./start.ps1 -Mode Status

# 2. Health check all services
python analyzer/analyzer_manager.py health

# 3. View recent logs
./start.ps1 -Mode Logs

# 4. Check Flask is responding
curl http://localhost:5000/api/health
# PowerShell: Invoke-WebRequest -Uri http://localhost:5000/api/health -UseBasicParsing
```

### Common issues and fixes

| Symptom | Quick Fix |
|---------|-----------|
| Flask won't start (port 5000 in use) | `./start.ps1 -Mode Stop` or `taskkill /F /IM python.exe` |
| Analyzers not responding | `python analyzer/analyzer_manager.py start` |
| Tasks stuck in PENDING | Check TaskExecutionService is running (see below) |
| Tasks stuck in RUNNING | `python scripts/fix_task_statuses.py` |
| Database locked | Stop Flask, kill zombie Python processes, restart |
| 401 on API calls | Regenerate token via UI → User → API Access |
| Container build fails | `./start.ps1 -Mode CleanRebuild` |
| Analysis timeout | Increase `*_TIMEOUT` in `.env` (default: 1800s) |
| Circuit breaker triggered | Wait 5 min or restart service: `docker restart static-analyzer` |

### Debug TaskExecutionService
```python
# In Python REPL or script
from app.factory import create_app
from app.services.service_locator import ServiceLocator
from app.models import AnalysisTask, AnalysisStatus

app = create_app()
with app.app_context():
    # Check if service is running
    service = ServiceLocator.get_task_execution_service()
    print(f"Running: {service._running}")  # Should be True
    print(f"Current task: {service._current_task_id}")
    
    # Find stuck tasks
    stuck = AnalysisTask.query.filter_by(status=AnalysisStatus.RUNNING).all()
    for task in stuck:
        print(f"{task.task_id}: running since {task.started_at}")
    
    # Count pending
    pending = AnalysisTask.query.filter_by(status=AnalysisStatus.PENDING).count()
    print(f"Pending tasks: {pending}")
```

### Debug analyzer containers
```bash
# Check container status
docker ps -a | findstr analyzer

# View specific container logs
docker logs static-analyzer --tail 100

# Check port binding
docker port static-analyzer

# Test WebSocket manually
# Windows PowerShell
Test-NetConnection -ComputerName localhost -Port 2001
Test-NetConnection -ComputerName localhost -Port 2002
Test-NetConnection -ComputerName localhost -Port 2003
Test-NetConnection -ComputerName localhost -Port 2004

# Restart specific service
docker restart static-analyzer
```

### Debug API issues
```bash
# Verify token
curl http://localhost:5000/api/tokens/verify -H "Authorization: Bearer <token>"

# Check task status
curl http://localhost:5000/api/analysis/task/<task_id> -H "Authorization: Bearer <token>"

# PowerShell equivalent
Invoke-WebRequest -Uri "http://localhost:5000/api/analysis/task/<task_id>" `
  -Headers @{"Authorization"="Bearer <token>"}
```

### Recovery commands cheat sheet
```bash
# Gentle restart
./start.ps1 -Mode Stop
./start.ps1 -Mode Start

# Fix stuck tasks
python scripts/fix_task_statuses.py

# Maintenance cleanup (7-day orphan grace)
./start.ps1 -Mode Maintenance

# Fast container rebuild (30-90s)
./start.ps1 -Mode Rebuild

# Nuclear option - clean rebuild (12-18 min)
./start.ps1 -Mode CleanRebuild

# Full wipeout (WARNING: removes all data)
./start.ps1 -Mode Wipeout

# Reset admin password
./start.ps1 -Mode Password

# Sync filesystem apps to DB
python scripts/sync_generated_apps.py
```

### Log locations
| Component | Location |
|-----------|----------|
| Flask | `logs/app.log` |
| Analyzers | `docker logs <container>` |
| All combined | `./start.ps1 -Mode Logs` |
| Specific analyzer | `python analyzer/analyzer_manager.py logs static-analyzer 100` |

## Development patterns

### Adding a new analyzer tool
1. **Implement handler** in `analyzer/services/{service}/main.py`:
   ```python
   async def run_new_tool(self, source_path: str) -> dict:
       return {"status": "success", "findings": [...]}
   ```
2. **Register** in tool map within service's main handler
3. **Update aggregation** in `analyzer/analyzer_manager.py`:
   - Add to `_collect_normalized_tools()`
   - Add to `_aggregate_findings()` if findings need extraction
4. **Add tests** in `tests/unit/` and `tests/integration/analyzer/`

### Adding a new API endpoint
1. **Create route** in `src/app/routes/api/{module}.py`:
   ```python
   @bp.route('/new-endpoint', methods=['POST'])
   @require_auth
   def new_endpoint():
       data = request.get_json()
       return jsonify({"result": "..."})
   ```
2. **Register blueprint** (if new file) in `src/app/factory.py`
3. **Add tests** in `tests/integration/api/`
4. **Document** in `docs/api-reference.md`

### Running tests
```bash
# Fast unit tests (recommended for dev loop)
pytest -m "not integration and not slow and not analyzer"

# Smoke tests (critical path)
pytest tests/smoke/

# Specific test
pytest tests/unit/test_analyzer_manager.py -v

# With coverage
pytest --cov=src --cov-report=html
```

### VS Code integration
- **Test Explorer**: Ctrl+Shift+T → Run/debug individual tests with breakpoints
- **Tasks**: Terminal → Run Task → Pick from testing/analysis/maintenance tasks
- **Launch configs**: F5 → Debug Flask App, Pytest, or Analyzer Manager

## Orientation hacks (fast path)
- Find latest consolidated result for a model/app: look under `results/{model}/app{N}/task_*/` and open the most recent `{model}_app{N}_task_*.json`; the flat `tools` map shows per-tool status quickly.
- Need ports for dynamic/perf? First check `generated/apps/{model}/app{N}/.env` for `BACKEND_PORT`/`FRONTEND_PORT`; else DB via `PortConfiguration` (auto-populated from `misc/port_config.json` by `ServiceLocator`).
- Slug issues: normalize with `app.utils.slug_utils.normalize_model_slug`; `_normalize_and_validate_app` in `analyzer/analyzer_manager.py` also tries variants.
- Where tool findings come from: `_aggregate_findings` and `_extract_*_findings` in `analyzer/analyzer_manager.py`; if adding a tool, ensure it lands in `analysis.results` and is summarized into the flat `tools` map.
- WebSocket progress vs final: gateway (`analyzer/websocket_gateway.py`) rebroadcasts `progress_update`; manager waits for `*_analysis_result`. Expect progress frames before the terminal payload.
- Quick analyzer sanity: `python analyzer/analyzer_manager.py status` (containers + ports), `... health`, `... logs static-analyzer 100`.
- Windows + Docker tip: services talk to generated apps via `http://host.docker.internal:{port}` when running inside containers—don't use `localhost` from the containers.
- SocketIO fallback: `src/main.py` prefers SocketIO if available; otherwise `app.run`. Real-time UI depends on whether `app.extensions.SOCKETIO_AVAILABLE` is true.
- Service wiring: `src/app/factory.py` initializes `ServiceLocator` and registers services (model, generation, docker, analysis inspection, unified results); see `src/app/services/service_locator.py`.
- Universal results: if present, `analyzer/universal_results.py` emits an additional `*_universal.json`; primary source of truth remains the consolidated task JSON under `task_{id}/`.
- TaskExecutionService debugging: check `task.status`, `task.started_at`, `task.error_message`; stuck tasks auto-recover on next app restart; manually force recovery via `scripts/fix_task_statuses.py`.
- Container rebuild strategies: incremental (fast, with cache) vs clean (slow, no cache); BuildKit cache mounts in `analyzer/Dockerfile` speed up pip/npm installs; shared base image reduces rebuild time for code-only changes.
- **Service health checks**: Use `python analyzer/analyzer_manager.py health` for comprehensive health check (container status, port connectivity, WebSocket handshake); faster than manual `docker ps` + `curl` checks.
- **Log aggregation**: `./start.ps1 -Mode Logs` tails both Flask and analyzer logs simultaneously; use `python analyzer/analyzer_manager.py logs <service> <lines>` for specific service logs (e.g., `... logs static-analyzer 100`).
- **Task prioritization**: Tasks with higher `priority` field execute first; same priority = FIFO (oldest first); set via `AnalysisTask.priority` (integer, higher = more urgent).
- **Batch operations**: Use `analyzer/analyzer_manager.py batch models.json` for multi-model analysis; creates parent task with subtasks; parent marked `is_main_task=True`, children have `parent_task_id` set.

### Quick code/data probes
- DB quick check (inside a Flask shell-like snippet): import `create_app` then inspect `PortConfiguration`/`AnalysisTask` under app context.
- Tests as examples: see `tests/integration/analyzer/test_unified_execution.py`, `tests/integration/websocket/test_unified_protocol.py`, `tests/test_task_orchestration.py`; run fast set via VS Code Task "pytest: unit tests only".
- Smoke tests: `tests/smoke/` for critical path health checks (HTTP endpoints, analyzer services).
- Troubleshoot noisy WS logs: internal websockets loggers are lowered in gateway/services; handshake stack traces from stray probes are benign.

## Environment variables reference

### Required
| Variable | Purpose |
|----------|---------|
| `OPENROUTER_API_KEY` | AI analyzer authentication (sk-or-v1-...) |
| `SECRET_KEY` | Flask session encryption |

### Flask/App
| Variable | Purpose | Default |
|----------|---------|---------|
| `FLASK_DEBUG` | Debug mode (1=on, 0=off) | `0` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |
| `DATABASE_URL` | Database connection | `sqlite:///src/data/thesis_app.db` |

### Analyzer
| Variable | Purpose | Default |
|----------|---------|---------|
| `ANALYZER_ENABLED` | Enable analyzer integration | `true` |
| `ANALYZER_AUTO_START` | Auto-start containers | `false` |
| `STATIC_ANALYSIS_TIMEOUT` | Static tool timeout (seconds) | `1800` |
| `SECURITY_ANALYSIS_TIMEOUT` | Security tool timeout | `1800` |
| `PERFORMANCE_TIMEOUT` | Performance test timeout | `1800` |
| `AI_ANALYSIS_TIMEOUT` | AI analysis timeout | `2400` |

### Task Execution
| Variable | Purpose | Default |
|----------|---------|---------|
| `TASK_POLL_INTERVAL` | How often to check for tasks | `5` (prod), `2` (test) |
| `TASK_TIMEOUT` | Overall task timeout | `1800` |
| `PREFLIGHT_MAX_RETRIES` | Service availability retries | `3` |
| `TRANSIENT_FAILURE_MAX_RETRIES` | Auto-recovery attempts | `3` |

### Maintenance
| Variable | Purpose | Default |
|----------|---------|---------|
| `MAINTENANCE_AUTO_START` | Auto-start cleanup | `false` |
| `MAINTENANCE_INTERVAL_SECONDS` | Cleanup interval | `3600` |
| `STARTUP_CLEANUP_ENABLED` | Startup task cleanup | `true` |
| `STARTUP_CLEANUP_RUNNING_TIMEOUT` | RUNNING task timeout (min) | `120` |
| `STARTUP_CLEANUP_PENDING_TIMEOUT` | PENDING task timeout (min) | `240` |

### Celery (optional)
| Variable | Purpose | Default |
|----------|---------|---------|
| `USE_CELERY_ANALYSIS` | Use Celery instead of ThreadPool | `false` |
| `CELERY_BROKER_URL` | Redis broker URL | `redis://localhost:6379/0` |
