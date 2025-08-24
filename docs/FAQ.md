# Frequently Asked Questions

> Navigation: [Overview](OVERVIEW.md) · [Architecture](ARCHITECTURE.md) · [Request Flow](REQUEST_FLOW.md) · [Analysis Pipeline](ANALYSIS_PIPELINE.md) · [Data Model](DATA_MODEL.md) · [Routes](ROUTES_REFERENCE.md) · [Services](SERVICES_REFERENCE.md) · [Dev Guide](DEVELOPMENT_GUIDE.md) · [Observability](OBSERVABILITY.md)

## General

### What problem does this platform solve?
It standardizes generation, orchestration, and multi-dimensional analysis (static, dynamic/ZAP, security tooling, performance, AI meta-analysis) of LLM-generated web application artifacts across many models.

### How is scalability handled?
Slow or CPU / I/O heavy operations (analyzers, container actions) are delegated to Celery workers and analyzer microservices; the Flask request layer remains responsive, using HTMX for incremental updates.

### Where do analysis results live?
Result JSON is stored in dedicated tables (`SecurityAnalysis`, `PerformanceTest`, `ZAPAnalysis`, etc.) with large outputs serialized into JSON text columns. Retrieval helper methods parse into Python dicts on access.

## Architecture & Components

### What are analyzer microservices?
Dockerized services (static, dynamic/ZAP, performance, AI) each exposing a WebSocket interface for command + streaming progress messages. They are orchestrated via `analyzer_manager.py` and a bridge service.

### Why a Service Locator instead of direct imports?
To centralize instantiation, avoid circular imports, and make swapping implementations (e.g., mocked services in tests) straightforward. Routes request services through `ServiceLocator` only.

### How are ports assigned for generated applications?
The `PortService` fetches allocations from the database (`port_configuration` table). If missing, it may seed from `misc/port_config.json`. Ports are never randomly recomputed ad hoc.

### How do HTMX fragments integrate with full pages?
Routes detect the `HX-Request` header (or simply return partials by convention) and render small snippet templates. The browser swaps DOM targets without a full page refresh, enabling near real-time updates.

## Development Workflow

### How do I start the platform for development?
Use `./start.ps1 flask-only` to run only the Flask UI, or `./start.ps1 start` to launch Flask + Celery + Redis + analyzer bridge.

### How do I (re)generate documentation?
1. `python scripts/generate_docs.py` (updates route & service references)
2. `pip install -r requirements-docs.txt` (first time / when deps change)
3. `mkdocs serve` (live preview) or `mkdocs build` (static site)

### How do I add a new analyzer type?
1. Create a new service under `analyzer/services/<new>/` implementing the WebSocket protocol.
2. Add Celery task logic invoking the bridge (`AnalyzerIntegration`).
3. Add a results table with JSON column + accessors.
4. Update UI fragments to trigger and display results.
5. Extend docs: pipeline description + service reference.

### How do I run a single generated app?
`python scripts/build_start_app.py --model <model_slug> --app <n>` optionally with `--rebuild` to force image rebuild.

## Data & Persistence

### Why store raw JSON blobs instead of structured columns?
Tool outputs evolve quickly; JSON preserves flexibility while summary metrics can be promoted to columns later if needed for indexing/queries.

### How is model capability data refreshed?
`ModelService.populate_database_from_files()` seeds/refreshes from `misc/model_capabilities.json` & `misc/models_summary.json`. OpenRouter-specific enrichment uses the `OpenRouterService`.

## Reliability & Observability

### Where do logs go?
Primary application logs under `logs/app.log`; Celery worker logs `src/celery_worker.log`; analyzer container logs accessible via CLI (`python analyzer/analyzer_manager.py logs <service>` or via API routes).

### How do I diagnose a stuck analysis?
1. Check Celery task state via `/tasks/status` endpoint or UI fragment.
2. Inspect analyzer service status `/analyzer/status`.
3. View container logs for the relevant analyzer.
4. Confirm WebSocket bridge connectivity (health endpoint / logs).

### How are outdated analyses cleaned up?
Services (e.g., `SecurityService`, `BatchAnalysisService`) expose cleanup methods invoked manually or via scheduled tasks (future enhancement). They prune old rows based on age thresholds.

## Testing

### Are there integration tests for the pipeline?
Yes, under `tests/integration/` (Celery flow examples) plus analyzer gateway tests under `analyzer/tests/` (where present). Expand by simulating WebSocket messages and asserting DB persistence.

### How should services be unit tested?
Import via `ServiceLocator` or inject mocked dependencies; focus on pure logic (input validation, DB queries, transformation) while stubbing external I/O.

## Extensibility

### What is the minimal contract for a new analyzer engine?
Provide a `run(model_slug, app_number, **options)` method returning a dict-like result with progress callbacks or streaming messages over the standardized protocol.

### Can I swap the transport (WebSocket) layer?
Yes—abstracted by `AnalyzerIntegration` & `WebSocketIntegration`. Implement an alternative adapter and register it in the Service Locator.

## Security

### Are there authentication/authorization layers?
Currently routes assume a trusted environment (research workstation). Hardening (auth, RBAC, CSRF) would be a future enhancement listed in hardening recommendations.

### How are untrusted analyzer outputs handled?
Outputs are stored as JSON and rendered with appropriate escaping in templates (Jinja autoescape on). Avoid executing embedded code; treat any dynamic content as untrusted.

## Performance

### What are main performance risks?
1. Large JSON result parsing on every request (cache/memoize heavy results).
2. Overlapping container builds consuming CPU.
3. High-frequency HTMX polling fragments (consider websockets or backoff).

### Optimization strategies?
Batch DB queries in services, add composite indexes on frequent filters (model_slug, app_number, status), and offload expensive summarization to periodic background tasks writing snapshot tables.

---
_Last updated: 2025-08-24._ 
