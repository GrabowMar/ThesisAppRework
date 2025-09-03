# Architecture

> Navigation: [Overview](OVERVIEW.md) · [Request Flow](REQUEST_FLOW.md) · [Analysis Pipeline](ANALYSIS_PIPELINE.md) · [Data Model](DATA_MODEL.md) · [Routes](ROUTES_REFERENCE.md) · [Services](SERVICES_REFERENCE.md) · [Dev Guide](DEVELOPMENT_GUIDE.md) · [Observability](OBSERVABILITY.md)

This section describes the layered architecture, major components, and integration contracts of the platform.

## Layered View

```
┌──────────────────────────────────────────────────────────────┐
│ Presentation Layer                                           │
│  - Flask Routes (Blueprints)                                 │
│  - HTMX Partials & Jinja Templates                           │
└───────────────▲──────────────────────────────────────────────┘
				│
┌──────────────────────────────────────────────────────────────┐
│ Service Layer (Business Logic)                               │
│  - ServiceLocator / domain services                          │
│  - Model, Port alloc, Docker hooks, Batch, Generation        │
│  - Analyzer Integration (subprocess + WS)                    │
└───────────────▲──────────────────────────────────────────────┘
				│
┌───────────────┴──────────────────────────────────────────────┐
│ Analysis Engines Layer                                       │
│  - security / static / dynamic / performance                 │
│  - Uniform run(model, app, **opts)                           │
└───────────────▲──────────────────────────────────────────────┘
				│
┌───────────────┴──────────────────────────────────────────────┐
│ Asynchronous Orchestration                                   │
│  - Celery Tasks (analysis, batch, container ops)             │
│  - WebSocket Bridge (progress fan-out)                       │
└───────────────▲──────────────────────────────────────────────┘
				│
┌───────────────┴──────────────────────────────────────────────┐
│ Analyzer Microservices (Docker)                              │
│  - static / dynamic(ZAP) / performance / ai                  │
│  - Ports 2001-2004 (+ gateway 8765)                          │
└───────────────▲──────────────────────────────────────────────┘
				│
┌───────────────┴──────────────────────────────────────────────┐
│ Persistence                                                  │
│  - SQLAlchemy Models + JSON Results                          │
│  - Seed JSON (fallback)                                      │
└──────────────────────────────────────────────────────────────┘
```

### Mermaid Diagram (Layered Architecture)

```mermaid
flowchart TB
	subgraph UI[Presentation]
		R[Routes]\nHTMX Partials
		T[Templates]
	end
	subgraph S[Services]
		SL[ServiceLocator]
		DOM[Domain Services]
		INT[AnalyzerIntegration]
	end
	subgraph E[Engines]
		SEC[Security]
		STA[Static]
		DYN[Dynamic]
		PERF[Performance]
	end
	subgraph C[Async]
		CT[Celery Tasks]
		WB[WS Bridge]
	end
	subgraph A[Analyzers]
		SA[static]
		DA[dynamic]
		PA[performance]
		AA[ai]
	end
	subgraph P[Persistence]
		DB[(DB)]
		JSON[(Results JSON)]
	end
	UI --> S --> E --> C --> A
	S --> P
	C --> P
```

## Component Responsibilities

| Component | Responsibility | Key Modules |
|-----------|----------------|-------------|
| Flask Routes | Handle HTTP, minimal logic, delegate to services | `src/app/routes/*` |
| Templates/HTMX | UI composition & incremental updates | `src/templates` |
| Service Locator | Centralized instantiation/wiring of services | `service_locator.py` |
| Domain Services | Encapsulate model, port allocation, docker, analysis config logic | `app/services/*` |
| Celery Tasks | Offload long-running or I/O bound operations | `app/tasks.py` |
| Analyzer Bridge | Subprocess + WebSocket orchestration | `analyzer/analyzer_manager.py`, `app/services/analyzer_integration.py` |
| Analysis Engines | Uniform execution adapters | `analysis_engines.py` |
| Analyzer Microservices | Specialized analyzer containers | `analyzer/services/*` |
| Data Initialization | Seed DB from JSON fallback files | `DataInitializationService` |
| Observability | Logging, health endpoints, dashboards | `routes/api/system.py`, dashboards |

## Services Overview

See [Services Reference](SERVICES_REFERENCE.md) for API-level details. High-level groups:
- Infrastructure: DockerManager, PortService
- Domain Data: ModelService, OpenRouterService, DataInitializationService
- Analysis Orchestration: TaskManager, AnalyzerIntegration, WebSocketIntegration, SecurityService
- Configuration: AnalyzerConfigService, AnalyzerConfig (value objects)
- Batch & Background: BatchAnalysisService, BackgroundTaskService

## Request vs Task Boundary

| Operation Type | Route Thread | Celery Task | Rationale |
|----------------|-------------|-------------|-----------|
| Quick data fetch (stats, list) | ✓ | ✗ | Millisecond DB-bound work |
| Start analysis | Initiate only | Heavy lifting | Avoid blocking, scale workers |
| Container (re)build | Initiate only | Build inside task | CPU & I/O intensive |
| Batch orchestration | Initiate only | Expand + parallel tasks | Potentially many sub-analyses |

## Analyzer Integration & Engines Contract

Messages (JSON) use command pattern: `{ "action": "run_<type>", "model": <slug>, "app": <n>, "options": {...} }`.
Engines wrap integration calls to normalize output (`EngineResult`) for tasks or synchronous test execution. Progress events surface through the WebSocket bridge; Celery tasks persist terminal JSON & summary metrics.

## Error Containment

Failures in analyzer communication mark a single analysis as FAILED without destabilizing the Flask process. Celery’s retry/backoff capabilities can be selectively enabled per task type if reliability needs increase.

## Extensibility Points

| Extension | Required Steps |
|-----------|----------------|
| New Analyzer | Container + WebSocket handler + engine registration + Celery task + result model/table + UI fragments |
| New Dashboard Metric | Add aggregation query (service), route endpoint, HTMX fragment template |
| Alternate Transport (e.g., gRPC) | Implement adapter parallel to WebSocketIntegration; register in ServiceLocator |
| Caching Layer | Introduce cache service; wrap service methods returning large JSON |

## Configuration Sources

| Source | Purpose | Precedence |
|--------|---------|------------|
| Environment Variables | Operational toggles (disabled models, timeouts) | Highest |
| Database | Canonical runtime state (models, ports, analysis configs) | High |
| JSON Seed Files (`misc/`) | Bootstrapping & fallback | Low |

## Security & Hardening (Future)

Current deployment assumes trusted local environment. For multi-user or hosted deployment:
1. Add authentication (OIDC / JWT) + role-based route guards.
2. Enable HTTPS termination (reverse proxy).
3. Sandbox analyzer containers with resource limits & seccomp profiles.
4. Validate / sanitize any dynamic template-rendered analyzer content.
5. Rate-limit mutation endpoints (start/stop/restart operations).

## Performance Considerations

- Avoid synchronous websocket waits in request context (always delegate to Celery).
- Minimize repeated JSON parse cost (cache parsed results for duration of request or use memoization in services).
- Use targeted indices (see [Data Model](DATA_MODEL.md)).
- Parallelize batch analyses across Celery workers (tune concurrency/prefetch).

## Deployment Diagram (Conceptual)

```
User Browser --> Flask/HTMX (5000) --> Services --> Engines --> DB (SQLite/Postgres)
				\--> Celery (Redis) --> Analyzer Bridge --> Analyzer Containers (2001-2004 + gateway)
```

## Observability Hooks

See [Observability](OBSERVABILITY.md) for log streams, health endpoints, and metrics fragments. Key endpoints: `/health`, `/system/health`, `/analyzer/status`.

---
_Last updated: 2025-09-03._ 
