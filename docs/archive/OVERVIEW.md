# Project Overview

> Navigation: [Architecture](ARCHITECTURE.md) · [Request Flow](REQUEST_FLOW.md) · [Analysis Pipeline](ANALYSIS_PIPELINE.md) · [Data Model](DATA_MODEL.md) · [Routes](ROUTES_REFERENCE.md) · [Services](SERVICES_REFERENCE.md) · [Dev Guide](DEVELOPMENT_GUIDE.md) · [Observability](OBSERVABILITY.md) · [Templates](TEMPLATES.md) · [Frontend](frontend/FRONTEND_ARCHITECTURE.md)

The Thesis App Rework platform orchestrates generation, execution and multi-dimensional analysis of AI‑generated applications ("model apps") across multiple LLM providers. It provides:

1. An operator-facing Flask + HTMX + Bootstrap 5 web UI for browsing models & generated apps, launching analyses, and viewing results.
2. A Celery task layer that offloads long-running or I/O-bound analysis work.
3. A set of containerized analyzer microservices (static-analyzer, dynamic-analyzer, performance-tester, ai-analyzer) communicating via WebSockets (ports 2001‑2004 + gateway 8765).
4. Lightweight in-process Analysis Engines (`analysis_engines.py`) giving a uniform synchronous contract (`engine.run(...)`) primarily leveraged by Celery tasks, but available for fast-path tests.
5. A relational database (SQLAlchemy) capturing model metadata, port allocations, generated application inventory, and analysis/test results with JSON payloads.
6. An experimental Sample Generation subsystem (`/api/sample-gen/*`) for AI-backed code artifact generation + manifest tracking.
7. Automated documentation & structured templates for maintainability and reproducibility of research experiments.

## High-Level Flow

User action (UI click / HTMX request) → Flask Route → Service Locator (business logic) → (optional) Celery Task → Analyzer Engine (via `AnalyzerIntegration` → subprocess → WebSocket) → Analyzer container executes tools → Progress events / result JSON returned → Persisted in DB → HTMX partial refresh updates UI.

Sample generation diverges: Route → Service Locator → synchronous generation service (OpenRouter or mock) → on-disk + manifest update → JSON response (no Celery).

## Key Concepts

| Concept | Description | Canonical Sources |
|---------|-------------|-------------------|
| Model Capability | Metadata + pricing + capabilities per AI model | `ModelCapability` in `app/models/__init__.py` |
| Generated Application | One concrete generated app variant for a model (`model_slug` + `app_number`) | `GeneratedApplication` |
| Port Configuration | Backend & frontend port reservation for a (model, app) pair | `PortConfiguration` |
| Analysis (Security/Performance/ZAP/AI) | Persisted result rows with JSON blob storing tool output | `SecurityAnalysis`, `PerformanceTest`, `ZAPAnalysis`, `OpenRouterAnalysis` |
| Batch Analysis | Logical grouping of multiple analyses triggered together | `BatchAnalysis` |
| Service Locator | Central registry giving routes controlled access to business logic | `service_locator.py` |
| Analysis Engines | Uniform run contract for analyzer types (security/static/dynamic/performance) | `services/analysis_engines.py` |
| Disabled Models | Environment‑gated exclusion from analysis | `DISABLED_ANALYSIS_MODELS` env + `app/tasks.py` |
| Sample Generation | Synchronous template → code artifact pipeline | `sample_generation_service`, `/api/sample-gen/*` |
| Analyzer Manager | CLI + orchestration for analyzer Docker services | `analyzer/analyzer_manager.py` |
| HTMX Partials | Fine-grained UI fragments returned to the browser for incremental updates | `src/templates/partials/**` |
| Template Compatibility Layer | Shim enabling legacy template paths to resolve after restructure | `app/utils/template_paths.py` |

## Architecture Layers

1. **Presentation**: Flask routes + Jinja templates + Bootstrap 5 + HTMX fragments
2. **Services**: Business logic (model/catalog, docker orchestration hooks, batch, sample gen)
3. **Analysis Engines**: Thin synchronous wrappers around analyzer integration (used by tasks & selective tests)
4. **Asynchronous Layer**: Celery tasks (analysis, batch, container ops) + WebSocket bridge
5. **Analyzer Microservices**: Dockerized specialized analyzers (static, dynamic, performance, AI)
6. **Persistence**: SQLAlchemy models + JSON columns for large result payloads
7. **Documentation & Tooling**: Auto-generated references + MkDocs site
8. **Experimental Generation**: Synchronous sample code generation + manifest tracking

See [Architecture](ARCHITECTURE.md) for detailed diagrams and cross-component responsibilities.

## Design Principles

- Database-first truth: Port allocations & model capabilities persist in DB; JSON seed files are fallback/bootstrapping only.
- Gated execution: `DISABLED_ANALYSIS_MODELS` short-circuits task dispatch early (uniform skip payloads).
- Non-blocking requests: Slow/network work is Celery-offloaded (engines are still invoked inside tasks except controlled test paths).
- Narrow route layer: Routes validate & delegate; no analyzer subprocess calls directly in request context.
- Partial-first UX: Return minimal HTMX fragments; stable DOM IDs ease incremental replacement.
- Extensible analyzers: Add container + engine + Celery task; reuse protocol & integration.
- Reproducibility: Generated app inventory, manifest, and analysis configs timestamped for experiment traceability.
- **Progressive enhancement**: Core functionality works without JavaScript; HTMX augments experience.

## Primary User Journeys

1. **Browse Models** → Filter/Sort → Drill into model details → View associated generated applications.
2. **Applications Grid** → Select app → Launch security/static/dynamic/performance analysis (Celery task queued) → Poll/fragment refresh.
3. **Sample Generation** (optional) → Upsert template → Generate code → Inspect manifest + structure.
4. **Inspect Analysis Result** → Summaries + raw JSON (lazy parse) → Export.
5. **Batch Workflow** → Multi-app enqueue → Aggregate progress dashboard.
6. **System Monitoring** → Analyzer container health & task metrics.

## Analysis Types

The platform supports multiple analysis types defined in `constants.py`:

- **security**: General security analysis (static code analysis)
- **performance**: Performance testing using Locust
- **zap_security**: Dynamic security testing using OWASP ZAP
- **openrouter**: AI-powered code analysis using OpenRouter models
- **code_quality**: Code quality analysis (linting, complexity)

Each analysis type has:
- Dedicated analyzer container service
- Corresponding database model for storing results
- Analysis engine with uniform `run()` interface
- Celery task for asynchronous execution

## Frontend Architecture

The UI is built with:
- **Flask + Jinja2**: Server-side rendering
- **Bootstrap 5**: CSS framework (no jQuery dependency)
- **HTMX**: Progressive enhancement for dynamic updates
- **Font Awesome**: Icon library (solid style only)
- **Vanilla JavaScript**: Minimal client-side scripting

Templates are organized in a clear hierarchy:
- `layouts/`: Page skeletons
- `pages/{domain}/`: Complete page views
- `ui/elements/`: Reusable components
- `partials/{domain}/`: HTMX fragments

See [Frontend Architecture](frontend/FRONTEND_ARCHITECTURE.md) for detailed guidance.

## When to Add a New Service

Add a service when logic: (a) touches multiple models/tables, (b) may be reused by more than one route, (c) has external I/O, or (d) needs isolated unit tests. Register it via `ServiceLocator.initialize()` ensuring minimal side effects during import.

## Adding a New Analyzer Type (Conceptual)

1. Implement the container / tool logic under `analyzer/services/<new-analyzer>/` with a WebSocket server exposing a consistent message protocol.
2. Add the service to `analyzer/docker-compose.yml` with appropriate port and health checks.
3. Extend `analyzer_manager.py` to support the new analyzer type in CLI commands.
4. Create an analysis engine in `analysis_engines.py` with uniform `run()` interface.
5. Add Celery task to enqueue requests referencing the new analyzer type.
6. Create database model for storing results (following existing patterns).
7. Update the front-end configuration partial to allow selecting the new analysis mode.
8. Add display partials + route endpoints for viewing and exporting results.

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
- [Frontend Architecture](frontend/FRONTEND_ARCHITECTURE.md) – UI patterns and best practices
- [Frontend Development](frontend/FRONTEND_DEVELOPMENT.md) – Development workflow

---
### Current Technology Stack

- **Backend**: Flask with SQLAlchemy, Celery for async tasks
- **Frontend**: Bootstrap 5 + HTMX + Font Awesome icons
- **Analyzers**: Docker containers with WebSocket communication
- **Database**: SQLite (dev) with JSON columns for complex data
- **Task Queue**: Celery with Redis backend
- **Testing**: Pytest with ephemeral test database

---
_Last updated: 2025-09-16 (modernized with Bootstrap 5, clarified analyzer types)._ 
