# Project Overview

> Navigation: [Architecture](ARCHITECTURE.md) · [Request Flow](REQUEST_FLOW.md) · [Analysis Pipeline](ANALYSIS_PIPELINE.md) · [Data Model](DATA_MODEL.md) · [Routes](ROUTES_REFERENCE.md) · [Services](SERVICES_REFERENCE.md) · [Dev Guide](DEVELOPMENT_GUIDE.md) · [Observability](OBSERVABILITY.md) · [Templates](TEMPLATES.md)

The Thesis App Rework platform orchestrates generation, execution and multi-dimensional analysis of AI‑generated applications ("model apps") across multiple LLM providers. It provides:

1. An operator-facing Flask + HTMX web UI for browsing models & generated apps, launching analyses, and viewing results.
2. A Celery task layer that offloads long-running or I/O-bound analysis work.
3. A set of containerized analyzer microservices (static, dynamic/ZAP, performance, AI) communicating via WebSockets.
4. A relational database (SQLAlchemy) capturing model metadata, port allocations, generated application inventory, and analysis/test results with JSON payloads.
5. Automated documentation & structured templates for maintainability and reproducibility of research experiments.

## High-Level Flow

User action (UI click / HTMX request) → Flask Route → Service Locator (business logic) → (optionally) Celery Task → Analyzer WebSocket bridge → Analyzer container executes tools → Progress events / result JSON returned → Persisted in DB → HTMX partial refresh updates UI.

## Key Concepts

| Concept | Description | Canonical Sources |
|---------|-------------|-------------------|
| Model Capability | Metadata + pricing + capabilities per AI model | `ModelCapability` in `app/models/__init__.py` |
| Generated Application | One concrete generated app variant for a model (`model_slug` + `app_number`) | `GeneratedApplication` |
| Port Configuration | Backend & frontend port reservation for a (model, app) pair | `PortConfiguration` |
| Analysis (Security/Performance/ZAP/AI) | Persisted result rows with JSON blob storing tool output | `SecurityAnalysis`, `PerformanceTest`, `ZAPAnalysis`, `OpenRouterAnalysis` |
| Batch Analysis | Logical grouping of multiple analyses triggered together | `BatchAnalysis` |
| Service Locator | Central registry giving routes controlled access to business logic | `service_locator.py` |
| Analyzer Manager | CLI + orchestration for analyzer Docker services | `analyzer/analyzer_manager.py` |
| HTMX Partials | Fine-grained UI fragments returned to the browser for incremental updates | `src/templates/partials/**` |
| Template Compatibility Layer | Shim enabling legacy template paths to resolve after restructure | `app/utils/template_paths.py` |

## Architecture Layers

1. Presentation: Flask routes + Jinja templates (with HTMX for partial updates)
2. Services: Business logic (model querying, docker management, analysis queueing)
3. Tasks: Celery tasks performing analyses, container orchestration, maintenance jobs
4. Analyzer Microservices: Specialized containers accessible via WebSocket
5. Persistence: SQLAlchemy models + JSON columns for flexible result payloads
6. Documentation & Tooling: Auto-generated references + MkDocs site

See [Architecture](ARCHITECTURE.md) for detailed diagrams and cross-component responsibilities.

## Design Principles

- Database-first truth: Port allocations & model capabilities are loaded into DB; JSON files act as seed/fallback only.
- Non-blocking requests: Any potentially slow network or analysis work must occur in Celery tasks or background processes.
- Narrow route functions: Routes delegate to services; services encapsulate domain logic.
- Partial-first UX: Most data refresh interactions return small HTMX fragments, preserving state & reducing bandwidth.
- Extensibility: New analyzer types plug in via Celery task + analyzer container, reusing the bridge abstraction.
- Reproducibility: Generated application inventory & analysis configs are persisted with timestamps and JSON snapshots.

## Primary User Journeys

1. Browse Models → Filter/Sort → Drill into model details → View associated generated applications.
2. Open Applications Grid → Select apps → Configure analysis types → Launch multi-type analysis → Watch active tasks update.
3. Inspect Analysis Result → View summarized findings → Export detailed JSON/CSV → Compare across models.
4. Batch Workflow → Define batch criteria → Start batch → Monitor aggregated progress & success metrics.
5. System Monitoring → View dashboard → Check analyzer container health & system metrics (CPU/memory/network) → Take action (start/stop analyzers).

## When to Add a New Service

Add a service when logic: (a) touches multiple models/tables, (b) may be reused by more than one route, (c) has external I/O, or (d) needs isolated unit tests. Register it via `ServiceLocator.initialize()` ensuring minimal side effects during import.

## Adding a New Analyzer Type (Conceptual)

1. Implement the container / tool logic under `analyzer/services/<new-analyzer>/` with a WebSocket server exposing a consistent message protocol.
2. Extend Celery tasks to enqueue requests referencing the new analyzer type.
3. Update the front-end configuration partial to allow selecting the new analysis mode.
4. Persist results in a new table (JSON payload + summary metrics).
5. Add display partials + route endpoints for viewing and exporting results.

## Auto-Generated Documentation

Run:

```bash
python scripts/generate_docs.py   # Updates Routes & Services references
mkdocs build                      # Builds static site (requires requirements-docs.txt)
```

The MkDocs config (`mkdocs.yml`) uses `mkdocstrings` to build an API reference under `reference/` at build time.

## Cross-Linking Strategy

Every major doc begins with a navigation line for quick jumps. Add new documents to this nav header + `mkdocs.yml`.

## See Also

- [Request Flow](REQUEST_FLOW.md) – granular HTTP request & task life cycle
- [Analysis Pipeline](ANALYSIS_PIPELINE.md) – end-to-end analyzer interaction
- [Data Model](DATA_MODEL.md) – schema & JSON column semantics
- [Routes Reference](ROUTES_REFERENCE.md) – auto-generated URL inventory
- [Services Reference](SERVICES_REFERENCE.md) – public service APIs
- [Observability](OBSERVABILITY.md) – logs, metrics, health checks

---
_Last updated: 2025-08-24._ 
