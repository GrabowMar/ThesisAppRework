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
- Start Flask (port 5000): run `src/main.py`. SocketIO is used if available.
- Start analyzers (Docker required): `python analyzer/analyzer_manager.py start` then `... status` or `... health`.
- Run an analysis directly (fastest for scripts):
  - `python analyzer/analyzer_manager.py analyze openai_gpt-4 1 security --tools bandit`
  - Comprehensive: `... analyze <model> <app> comprehensive`
- VS Code Tasks: use "Terminal → Run Task" and pick one of:
  - `pytest: unit tests only` (default, fastest) - Quick unit test cycle
  - `pytest: smoke tests` - Fast critical path health check
  - `pytest: integration tests` - All integration tests
  - `pytest: api integration` / `websocket integration` / `analyzer integration` / `web ui integration` - Targeted suites
- Tests: prefer `pytest -m "not integration and not slow and not analyzer"` for quick cycles. Smoke tests via `pytest tests/smoke/`. Full suite runs without markers.
- VS Code Test Explorer: open Testing panel (Ctrl+Shift+T) for interactive test discovery and debugging.

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

## Gotchas
- Don’t assume `results/analysis/` exists—new runs group by `task_{id}` at the app root; helper code migrates any legacy folders automatically.
- Dynamic/perf analysis requires resolvable ports; ensure the generated app writes `.env` with `BACKEND_PORT` and `FRONTEND_PORT` or populate the DB fallback.
- Linter exit codes: treat “findings present” exit code 1 as success if JSON output exists; only infra/process failures are errors.

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

## Orientation hacks (fast path)
- Find latest consolidated result for a model/app: look under `results/{model}/app{N}/task_*/` and open the most recent `{model}_app{N}_task_*.json`; the flat `tools` map shows per-tool status quickly.
- Need ports for dynamic/perf? First check `generated/apps/{model}/app{N}/.env` for `BACKEND_PORT`/`FRONTEND_PORT`; else DB via `PortConfiguration` (auto-populated from `misc/port_config.json` by `ServiceLocator`).
- Slug issues: normalize with `app.utils.slug_utils.normalize_model_slug`; `_normalize_and_validate_app` in `analyzer/analyzer_manager.py` also tries variants.
- Where tool findings come from: `_aggregate_findings` and `_extract_*_findings` in `analyzer/analyzer_manager.py`; if adding a tool, ensure it lands in `analysis.results` and is summarized into the flat `tools` map.
- WebSocket progress vs final: gateway (`analyzer/websocket_gateway.py`) rebroadcasts `progress_update`; manager waits for `*_analysis_result`. Expect progress frames before the terminal payload.
- Quick analyzer sanity: `python analyzer/analyzer_manager.py status` (containers + ports), `... health`, `... logs static-analyzer 100`.
- Windows + Docker tip: services talk to generated apps via `http://host.docker.internal:{port}` when running inside containers—don’t use `localhost` from the containers.
- SocketIO fallback: `src/main.py` prefers SocketIO if available; otherwise `app.run`. Real-time UI depends on whether `app.extensions.SOCKETIO_AVAILABLE` is true.
- Service wiring: `src/app/factory.py` initializes `ServiceLocator` and registers services (model, generation, docker, analysis inspection, unified results); see `src/app/services/service_locator.py`.
- Universal results: if present, `analyzer/universal_results.py` emits an additional `*_universal.json`; primary source of truth remains the consolidated task JSON under `task_{id}/`.

### Quick code/data probes
- DB quick check (inside a Flask shell-like snippet): import `create_app` then inspect `PortConfiguration`/`AnalysisTask` under app context.
- Tests as examples: see `tests/integration/analyzer/test_unified_execution.py`, `tests/integration/websocket/test_unified_protocol.py`, `tests/test_task_orchestration.py`; run fast set via VS Code Task "pytest: unit tests only".
- Smoke tests: `tests/smoke/` for critical path health checks (HTTP endpoints, analyzer services).
- Troubleshoot noisy WS logs: internal websockets loggers are lowered in gateway/services; handshake stack traces from stray probes are benign.
