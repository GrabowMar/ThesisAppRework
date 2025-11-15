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

## Core developer workflows (Windows-friendly)
- **Quick start (recommended)**: Use `start.ps1` orchestrator for full stack management:
  - Interactive menu: `./start.ps1` (or just run the script)
  - Full stack: `./start.ps1 -Mode Start` (Flask + Analyzers)
  - Dev mode (Flask only): `./start.ps1 -Mode Dev -NoAnalyzer`
  - Status dashboard: `./start.ps1 -Mode Status`
  - View logs: `./start.ps1 -Mode Logs`
  - Stop all: `./start.ps1 -Mode Stop`
- **Manual start**:
  - Flask only (port 5000): run `src/main.py`. SocketIO is used if available.
  - Analyzers (Docker required): `python analyzer/analyzer_manager.py start` then `... status` or `... health`.
- Run an analysis directly (fastest for scripts):
  - `python analyzer/analyzer_manager.py analyze openai_gpt-4 1 security --tools bandit`
  - Comprehensive: `... analyze <model> <app> comprehensive`
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
- Test organization: `tests/` (unit, smoke, integration/{api,websocket,analyzer,web_ui}); markers: `smoke`, `integration`, `slow`, `analyzer`, `api`, `websocket`, `web_ui`.
- End-to-end workflow docs: `analyzer/README.md`.

## Typical tasks you’ll automate
- Trigger analysis for an app created under `generated/apps/...`, then read consolidated results under `results/.../task_{id}/`.
- Add a new static/dynamic tool: extend the respective analyzer service to emit normalized tool entries and ensure `_aggregate_findings` can extract findings.
- Wire a new API endpoint to create `AnalysisTask`s and dispatch via analyzer manager or the WS gateway. Follow patterns in `src/app/services/*` and existing routes.

## API tokens (automation)
- Generate a Bearer token via UI (User → API Access) or see `docs/API_AUTH_AND_METHODS.md` for alternatives.
- Verify quickly: `GET /api/tokens/verify` with `Authorization: Bearer <token>`.
- Use with `POST /api/analysis/run` to create an `AnalysisTask` and kick off analysis; results are written to `results/{model}/app{N}/task_{task}/` and visible in the UI.

## API endpoints → services
- `POST /api/analysis/run` → creates `AnalysisTask`, then analyzer integration dispatches to containers (static/dynamic/perf/ai) via `AnalyzerManager` or the WS gateway.
- `POST /api/app/{model_slug}/{app_number}/analyze` → shorthand for running an analysis against a specific generated app.
- Gateway: `analyzer/websocket_gateway.py` listens on `ws://0.0.0.0:8765` and proxies to service WS endpoints (2001–2004), rebroadcasting progress frames to subscribers.

## AnalysisTask model and lifecycle
- **Key fields** (`src/app/models/analysis.py`):
  - `task_id` - Unique identifier (e.g., "task_abc123")
  - `target_model` - Model slug (normalized)
  - `target_app_number` - App number to analyze
  - `status` - Current state (see lifecycle below)
  - `analyzer_config_id` - Optional analyzer profile reference
  - `batch_id` - For batch processing grouping
  - `parent_task_id` - For subtask hierarchies
  - `is_main_task` - True for parent tasks in batch operations
  - `task_name` - Human-readable name
  - `result_summary` - JSON summary of results
  - `error_message` - Failure details if status is FAILED
  - Timestamps: `created_at`, `started_at`, `completed_at`
- **Status lifecycle**:
  - `PENDING` - Task created, waiting for execution (auto-picked by TaskExecutionService)
  - `RUNNING` - Currently executing analysis
  - `COMPLETED` - Successfully finished
  - `FAILED` - Error occurred (check `error_message`)
  - `CANCELLED` - User-cancelled or timed out
  - Auto-recovery: Stuck RUNNING tasks (>30min) → FAILED on startup; old PENDING tasks (>30min) → CANCELLED
- **TaskExecutionService** (background daemon in `src/app/services/task_execution_service.py`):
  - Polls database every 2s (test mode) or 10s (production) for PENDING tasks
  - Dispatches via `AnalyzerIntegrationService` to analyzer manager
  - Updates task status based on execution result
  - Writes filesystem results to `results/{model}/app{N}/task_{id}/`
  - Started automatically in `src/app/factory.py` during app initialization

## Background services (auto-started)

### Startup Sequence (CRITICAL ORDER)

The Flask app initialization follows a **specific sequence** to prevent old tasks from auto-executing on reboot:

1. **MaintenanceService starts FIRST** → Cancels old PENDING tasks (>30min old)
2. **TaskExecutionService starts SECOND** → Only picks up fresh PENDING tasks

This ensures that analysis tasks left over from previous sessions (e.g., before a crash or reboot) are **cancelled** before the task executor can pick them up.

### TaskExecutionService (`src/app/services/task_execution_service.py`)
**Purpose**: Asynchronous task execution daemon that processes pending analysis tasks.

**Lifecycle**:
- Initialized and started automatically in `src/app/factory.py` during app creation
- Runs in separate daemon thread (non-blocking)
- Polls database every **2 seconds** (test mode) or **10 seconds** (production)
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
- Poll interval: set via `TASK_POLL_INTERVAL` env var (default: 10s prod, 2s test)
- Max concurrent: currently 1 task at a time (sequential execution)
- Timeout: inherits from `TASK_TIMEOUT` (default 1800s = 30min)

### MaintenanceService (`src/app/services/maintenance_service.py`)
**Purpose**: Automated cleanup and recovery of orphaned resources.

**Lifecycle**:
- **CRITICAL**: Initialized in `src/app/factory.py` **BEFORE** TaskExecutionService (prevents old tasks from auto-executing)
- Runs **once immediately** on app initialization (startup cleanup)
- Then runs hourly via background thread

**Startup Cleanup** (runs automatically every app start, **BEFORE** TaskExecutionService):
1. **Stuck task recovery**: Tasks in RUNNING state for >30 minutes → FAILED
2. **Stale pending tasks**: Tasks in PENDING state for >30 minutes → CANCELLED ⚠️ **This prevents old generation/analysis tasks from running after reboot**
3. **Filesystem sync**: Scans `generated/apps/` and creates missing `GeneratedApp` DB records
4. **Legacy migration**: Moves old `results/.../analysis/` folders to task-based structure

**Hourly Cleanup** (if enabled):
1. **Orphaned apps**: Filesystem apps in `generated/apps/` not in database → delete if >7 days old
2. **Empty result dirs**: Result folders with no JSON files → delete
3. **Old log rotation**: Rotate logs in `logs/` if >100MB

**Usage**:
```python
# Manual trigger (Python shell)
from app.services.maintenance_service import MaintenanceService
service = MaintenanceService(app)
service.run_startup_cleanup()  # Safe to run anytime
service.cleanup_orphaned_apps()  # Manual orphan cleanup

# Check what would be cleaned (dry run)
orphans = service._find_orphaned_apps()
for app_path in orphans:
    print(f"Would delete: {app_path}")
```

**Logs**: All cleanup operations logged to `logs/app.log` with INFO level:
```
[MaintenanceService] Recovered 3 stuck tasks (RUNNING > 30min)
[MaintenanceService] Cancelled 1 stale pending task
[MaintenanceService] Synced 12 filesystem apps to database
[MaintenanceService] Deleted 2 orphaned apps (older than 7 days)
```

## Gotchas and non-obvious behaviors

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
- **Poll interval**: 2s (test mode) or 10s (production) between polls
- **Sequential execution**: Currently 1 task at a time; subsequent tasks wait in queue
- **Check progress**: Query `task.status` to see state; `RUNNING` means actively executing, check `task.started_at` for how long

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

## Repository organization (clean state)
- **Root directory**: Only essential files (README.md, requirements.txt, pytest.ini, docker-compose.yml, start.ps1)
- **No temporary files**: Status markdown files and debug scripts have been cleaned up (Nov 2025)
- **All tests in `tests/`**: No root-level test scripts - use `pytest` from the official test suite
- **Documentation in `docs/`**: Comprehensive guides in `docs/`, reference materials in `docs/guides/`
- **Clean outputs**: `generated/` for apps, `results/` for analysis data, `reports/` for generated reports
- **Scripts organized**: Utility/maintenance scripts in `scripts/`, not scattered in root

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
