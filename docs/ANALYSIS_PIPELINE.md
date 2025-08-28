# Analysis Pipeline

> Navigation: [Overview](OVERVIEW.md) · [Architecture](ARCHITECTURE.md) · [Request Flow](REQUEST_FLOW.md) · [Data Model](DATA_MODEL.md) · [Routes](ROUTES_REFERENCE.md) · [Services](SERVICES_REFERENCE.md) · [Dev Guide](DEVELOPMENT_GUIDE.md) · [Observability](OBSERVABILITY.md)

This document details the end-to-end lifecycle of an analysis or test (security, static, dynamic/ZAP, performance, AI) from user initiation through result persistence and UI update.

## 1. Initiation (User Interaction)

Entry points:
1. HTMX form/button on an applications or analysis dashboard fragment.
2. Bulk action selection (batch or multi-app selection).
3. API call (automation scripts / external client).

Routes invoke service methods via `ServiceLocator` (e.g., `TaskManager.start_security_analysis`, `BatchAnalysisService.start_job`). If the route is interactive (HTMX) it returns a fragment acknowledging queueing while background work proceeds.

## 2. Task Dispatch (Celery Layer)

Services encapsulate parameter validation and enrichment (ports, model existence, config application) then enqueue Celery tasks. A typical pattern:

1. Build payload (model_slug, app_number, analysis types, options).
2. Generate unique task/analysis ID (UUID).
3. Persist preliminary row (status = PENDING) in the respective table.
4. Call `celery_app.send_task` or task `.delay()` method.

Celery ensures isolation from the request thread and allows distributed scaling of workers.

## 3. Analyzer Bridge (WebSocket Integration)

The Celery task invokes `AnalyzerIntegration` / `WebSocketIntegration` to communicate with analyzer microservices:

- Establish (or reuse) WebSocket connection to the appropriate analyzer service (static-analyzer, dynamic-analyzer, performance-tester, ai-analyzer, security).
- Transmit a JSON command: `{ "action": "run_<type>", "model": <slug>, "app": <n>, "options": {...} }`.
- Register callbacks for incremental progress events.

## 4. Microservice Execution

Analyzer containers perform specialized tooling:

| Analyzer | Example Tools / Actions | Output Characteristics |
|----------|-------------------------|------------------------|
| static | Bandit, ESLint, Pylint, Safety | Findings lists, severity metrics |
| dynamic (ZAP) | Passive/active ZAP scans | Vulnerabilities with confidence levels |
| security (comprehensive) | Aggregation orchestrating static + dynamic | Consolidated summary + per-tool results |
| performance | ApacheBench / custom HTTP benchmarking | Latency percentiles, throughput, error rates |
| ai | Meta-analysis / classification of code quality or risk | Natural language summaries + categorical scores |

Progress events are streamed over WebSocket as JSON messages (e.g., `{"event":"progress","id":...,"pct":42}`) and forwarded to interested subscribers.

## 5. Progress Propagation & Event Logging

The bridge updates:
1. BackgroundTask / BatchJob progress (in-memory or DB).
2. Analysis row status (e.g., RUNNING → COMPLETED / FAILED).
3. WebSocket or HTMX polling endpoints provide near real-time UI refresh data.

Event logs are optionally persisted (see `CeleryWebSocketService.get_event_log`).

## 6. Result Assembly & Persistence

Upon completion:
- Raw tool outputs (possibly large) serialized into JSON columns.
- Derived metrics (counts, severity distributions, percentile stats) may be computed and stored in summary fields.
- Status updated to COMPLETED (or FAILED with error message captured).

## 7. UI Update Pathways

Two complementary mechanisms:
1. HTMX Polling: Fragments request `/analysis/.../results` endpoints; server returns updated partial.
2. WebSocket Broadcast: Bridge/service broadcasts `analysis_completed` message enabling immediate UI refresh for listening clients.

## 8. Batch Workflow Specifics

For batch jobs:
- A `BatchJob` record tracks total tasks, completed count, failures, derived completion %. 
- Each sub-analysis is enqueued separately referencing the parent job ID.
- Cancellation requests propagate to outstanding Celery tasks and analyzer operations via the bridge.

## 9. Error Handling & Retries

| Stage | Error Types | Handling |
|-------|-------------|----------|
| Validation | Missing model/app, invalid tool set | Raise service-level ValidationError; route returns 4xx or fragment message |
| Task Dispatch | Broker unreachable | Logged; task may retry with exponential backoff |
| WebSocket Connect | Service down / timeout | Bridge marks service unhealthy; analysis set FAILED; surfaced in status endpoints |
| Tool Execution | Tool crash, parse errors | Captured in results JSON under `errors`; status FAILED but partial findings persisted |

## 10. Cancellation Flow

1. User triggers cancel endpoint.
2. Service invokes `WebSocketIntegration.cancel_analysis` sending cancel command to analyzer.
3. Task updates DB status to CANCELED; UI fragment reflects termination.

## 11. Data Retention & Cleanup

Periodic cleanup jobs (manual now, schedulable later) remove aged analyses beyond retention horizon (`SecurityService.cleanup_old_scans`, `BatchAnalysisService.cleanup_old_jobs`). Large JSON payload pruning or summarization can be introduced here.

## 12. Extending the Pipeline

To add a new analysis type:
1. Define analyzer container + WebSocket protocol message shape.
2. Add service facade method (e.g., `TaskManager.start_<type>`).
3. Create model/table for results + migration.
4. Implement Celery task bridging to container.
5. Add UI trigger + status/result fragments.
6. Update this doc & reference tables.

## 13. Sequence Overview (Textual)

User Action → Route → Service Validation → Celery Task Enqueue → Analyzer Bridge Connect → Analyzer Execution (stream events) → Persist Intermediate & Final Results → Broadcast Completion → HTMX/WebSocket UI Update → (Optional) Batch Aggregation Update.

## 14. Observability Hooks

- Health endpoints (`/analyzer/status`, `/system/health`) expose analyzer + system metrics.
- Dashboard fragments show running counts & performance trends.
- Logs unify bridge + task events for forensic analysis.

---
_Last updated: 2025-08-24._ 
