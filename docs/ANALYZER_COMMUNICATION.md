# Analyzer Communication Guide

This document explains how the Flask web platform communicates with the containerized analyzer services. It covers the transport layers, message formats, service ports, filesystem layout, orchestration, and troubleshooting.

## Overview

The system uses a dual architecture:
- Web Platform (Flask + Celery): Handles UI, tasks, and persistence
- Analyzer Services (Dockerized): Perform security, static, dynamic, performance, and AI analyses

Two complementary communication paths are used:
- Task orchestration path: Flask/Celery -> Analyzer Integration -> analyzer_manager.py (subprocess) -> WebSocket calls to analyzer services
- Live updates path: Browser SSE -> Gateway WebSocket (for progress and status events)

High-level flow:
1) User starts an analysis via Flask route or Batch form
2) Celery task dispatches and calls Analyzer Integration
3) Analyzer Integration shells out to `analyzer/analyzer_manager.py` with a specific command (analyze/start/health/etc.)
4) The manager connects to analyzer service(s) over WebSocket on ports 2001-2004 and coordinates the analysis
5) Results are saved to `analyzer/results/*.json` and (for DB-backed paths) persisted into the database
6) UI reads artifacts and/or DB records and renders results

## Key Ports and Services

- WebSocket Gateway (optional aggregator): 8765
- Static Analyzer (code security/quality): 2001
- Dynamic Analyzer (ZAP-like): 2002
- Performance Tester (Locust-based): 2003
- AI Analyzer (OpenRouter-backed): 2004
- Redis (for Celery, separate): 6379

Docker Compose defines these services in `analyzer/docker-compose.yml` with health checks and resource limits.

## Filesystem Layout and Mounts

- Host repository structure contains generated apps under `generated/<model_slug>/app<number>`
- Analyzer containers mount: `../generated` (host) → `/app/sources` (in-container, read-only)
- Each analyzer expects source code at: `/app/sources/<model_slug>/app<number>`
- Analyzer results are written to container-local `/app/results` and mapped/collected under host `analyzer/results/`

Important: `model_slug` must be non-empty. A missing slug yields a path like `/app/sources/app1` (incorrect), causing "Model path not found" errors.

## Transport Layers

### 1) Celery → AnalyzerIntegration → analyzer_manager.py

- Celery tasks (e.g., `security_analysis_task`, `static_analysis_task`, `dynamic_analysis_task`, `performance_test_task`, `ai_analysis_task`, and `batch_analysis_task`) call the Analyzer Integration service.
- Analyzer Integration executes `analyzer/analyzer_manager.py` via a subprocess:
  - Command layout: `python analyzer_manager.py analyze <model_slug> <app_number> <type>` (type: security|static|performance|dynamic|ai)
  - Environment is forced to UTF-8 on Windows to avoid console encoding issues.
  - Standard output is captured; the integration attempts to parse JSON; if parsing fails, raw text is returned in `raw_output`.
- Service orchestration (start/stop/status) also uses analyzer_manager subcommands (start/stop/status/health/logs).

CLI examples invoked by the integration:
- Start all services: `python analyzer_manager.py start`
- Check health: `python analyzer_manager.py health`
- Analyze one app: `python analyzer_manager.py analyze anthropic_claude-3.7-sonnet 1 security`

Timeouts used (approximate defaults; can vary per task):
- Static/Security: ~180–600s
- Performance: duration + 60s
- Dynamic (ZAP-like): ~600s
- AI: ~1200s

### 2) Browser SSE → Gateway WebSocket

- The Flask route `/analysis/events/stream` provides an SSE endpoint for the browser to receive live status streams.
- The SSE bridge connects to the Gateway WebSocket (default `ws://localhost:8765`) and forwards messages.
- SSE supports optional filtering by `correlation_id` to scope updates to a specific analysis.
- A small in-process ring buffer with JSONL persistence (in the gateway) can be used for replay and cross-session diagnostics.

## WebSocket Protocol (Analyzer Services)

Defined in `analyzer/shared/protocol.py`:
- Message types (`MessageType`): ANALYSIS_REQUEST, BATCH_REQUEST, STATUS_REQUEST, CANCEL_REQUEST, ANALYSIS_RESULT, BATCH_RESULT, PROGRESS_UPDATE, STATUS_UPDATE, ERROR, HEARTBEAT, SERVICE_REGISTER, SERVICE_UNREGISTER, CONNECTION_ACK
- Service types (`ServiceType`): SECURITY_ANALYZER, PERFORMANCE_TESTER, DEPENDENCY_SCANNER, CODE_QUALITY, AI_ANALYZER, GATEWAY
- Core DTOs:
  - `WebSocketMessage`: envelope with `type`, `id`, `timestamp`, `data`, `client_id`, `correlation_id`
  - `AnalysisRequest` and specializations (Security, Performance, Dependency, CodeQuality, AI)
  - `AnalysisResult` and specializations (SecurityAnalysisResult, PerformanceTestResult)
  - `ProgressUpdate` for granular progress reporting
  - `ErrorMessage` and `HeartbeatMessage`

Typical message flow to a service:
1) Client sends `ANALYSIS_REQUEST` with `data` containing `model`, `app_number`, `analysis_type`, `source_path`, and options
2) Service emits `PROGRESS_UPDATE` messages during execution
3) Service emits `ANALYSIS_RESULT` on completion with `status` (completed/failed) and summary/metadata

Correlation IDs:
- Set `correlation_id` on messages to correlate progress and results to a single logical run.
- The SSE bridge forwards only messages matching the requested `correlation_id` when provided.

## Analyzer Manager (Bridge)

`analyzer/analyzer_manager.py` is a unified controller that:
- Starts/stops containers via Docker Compose
- Checks status/health and reads service logs
- Connects to each service via WebSocket and sends simple JSON commands (e.g., `static_analyze`, `dynamic_analyze`, `performance_test`, `ai_analysis`)
- Saves result artifacts into `analyzer/results/` following this naming pattern:
  - `<model_slug>_app<app_number>_<analysis_type>_<YYYYmmdd_HHMMSS>.json`

The manager also contains convenience functions for batch/comprehensive runs, ping tests, and overall health checks.

## Services at a Glance

- static-analyzer (2001): source path `/app/sources/<model_slug>/app<number>`, runs tools like bandit/pylint/flake8/mypy/eslint/stylelint; returns summary + per-tool details; can be queried via WebSocket JSON `{"type": "static_analyze", ...}`
- dynamic-analyzer (2002): runs ZAP-like scanning; accepts `target_urls`; stores results to `/app/results`
- performance-tester (2003): Locust-based; needs `target_url` (defaults can be inferred); reports RPS, latency distribution
- ai-analyzer (2004): LLM-backed code review/requirements checks; requires `OPENROUTER_API_KEY`; careful about quotas/timeouts

All services expose health checks and support simple `ping`/`health_check` messages.

## Path Resolution and Model/App Mapping

- Always pass a non-empty `model_slug` and `app_number` to map to `/app/sources/<model_slug>/app<number>`
- In the Flask batch route, server-side validation now rejects submissions with no models
- If apps are omitted but models are supplied, the server auto-expands to all known apps for those models based on the database (`GeneratedApplication`)

Common error and fix:
- Error: `Model path not found: /app/sources/app1` → Cause: missing model_slug → Fix: ensure model(s) selected; input sanitization prevents empty slugs

## Error Handling, Timeouts, and Retries

- Analyzer Integration sets UTF-8 environment and captures stdout/stderr; returns `success`, `stdout`, `stderr`, and `returncode`
- On JSON parse failure, the raw stdout is returned (so some operations are "best effort" if the manager prints human-readable summaries)
- Celery tasks:
  - Mark DB-backed analyses RUNNING/COMPLETED/FAILED
  - Apply limited retries for transient errors (timeouts/connection refused)
  - Use conservative timeouts per analysis type; performance tests time out based on duration

SSE/Gateway:
- The SSE route continues streaming until the underlying WebSocket disconnects or a stop signal is enqueued
- Basic filtering by `correlation_id` keeps noisy streams manageable

## Windows Considerations

- Use the provided `src/start.ps1` to start Flask, Redis, Celery (solo pool), and analyzer services; venv paths are respected
- UTF-8 enforcement for subprocess avoids Windows charmap crashes with emojis in logs
- Docker Desktop must be running; ensure ports 2001–2004 and 8765 are not blocked

## Runbook (Common Commands)

From repository root (PowerShell):

```powershell
# Start analyzer stack (builds containers if needed)
cd analyzer
python analyzer_manager.py start

# Check status/health
python analyzer_manager.py status
python analyzer_manager.py health

# Show logs
python analyzer_manager.py logs static-analyzer 100

# Run a quick analysis
python analyzer_manager.py analyze anthropic_claude-3.7-sonnet 1 security

# Batch from a JSON list of [model, app]
python analyzer_manager.py batch example_batch.json
```

Flask/Celery:
- UI create page: `/analysis/create` (batch)
- Start batch (HTMX/API): POST `/analysis/batch/start`
- Results (artifacts view): `/analysis/results/<model_slug>/<app_number>`
- SSE stream for live events: `/analysis/events/stream?correlation_id=<id>`

## Troubleshooting Checklist

1) Model path errors
- Ensure model is selected in batch form (server rejects empty models)
- Verify `generated/<model_slug>/app<number>` exists on host
- Confirm docker-compose mount: `../generated:/app/sources:ro`

2) Port issues
- Check container status (`python analyzer_manager.py status`)
- Verify ports are accessible (localhost:2001..2004, 8765)
- Confirm firewall/VPN is not blocking

3) No live updates
- Ensure gateway is running (container healthy) and SSE route reachable
- Check WebSocket URI (`ws://localhost:8765`) in SSE bridge

4) JSON parsing failures in integration
- Some manager operations print human-readable summaries; the integration returns `raw_output`
- Inspect `analyzer/results/*.json` artifacts for structured data

5) Windows-specific
- Use the venv and `start.ps1`; avoid non-UTF-8 terminals; make sure Docker Desktop is up

## Extending and Customizing

- Add new analyzer services by defining a port, WebSocket endpoint, Dockerfile, and healthcheck in `analyzer/docker-compose.yml`
- Extend the WebSocket protocol by introducing new `MessageType` values and corresponding data classes
- Wire new operations in `analyzer_manager.py` and add wrappers in `app/services/analyzer_integration.py`
- Update UI routes and batch form to surface new analysis types and options

## 2025-08 Enhancements (Locust & OWASP ZAP)

### Performance Tester (Locust Integration)
The performance tester now attempts a short headless Locust run for the first target URL when the `locust` package/CLI is available. Default parameters:
- Users: 15
- Spawn rate: 3 users/sec
- Duration: 15s

Override by passing a config object when initiating a performance test:
```json
{
  "locust": { "users": 30, "spawn_rate": 5, "run_time": "30s" }
}
```
Results appear under the key `locust` inside the first URL result with summary metrics:
`requests_per_second`, `p95_response_time_ms`, `average_response_time_ms`, `total_requests`, `failures`.

### Dynamic Analyzer (Optional OWASP ZAP Scan)
If the Python client `python-owasp-zap-v2.4` is installed and a ZAP daemon is reachable at `http://localhost:${ZAP_PORT}` (default 8090), the dynamic analyzer performs:
1. Spider scan for the first reachable URL.
2. Passive scan wait (bounded time window).
3. Attempted short active scan (best effort; failure does not abort overall analysis).

Output structure under `zap_scan` includes:
`alert_counts` (High/Medium/Low/Informational), `total_alerts`, `active_scan` status, and capped `alerts_sample` (first 25 alerts).

Environment variables:
- `ZAP_PORT` (default 8090)
- `ZAP_API_KEY` (optional)

If unreachable, returns `{"status": "unreachable", "message": "No ZAP daemon ..."}` instead of failing the entire dynamic analysis.

## References

- `analyzer/docker-compose.yml` — services, ports, mounts
- `analyzer/analyzer_manager.py` — CLI orchestrator and WebSocket client
- `analyzer/shared/protocol.py` — message types and DTOs
- `src/app/services/analyzer_integration.py` — subprocess bridge to manager
- `src/app/tasks.py` — Celery tasks for all analysis types
- `src/app/routes/analysis.py` — endpoints and SSE bridge
- `docs/CELERY_COMMUNICATION.md` — complementary Celery orchestration details
