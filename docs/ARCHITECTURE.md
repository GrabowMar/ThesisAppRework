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
┌───────────────┴──────────────────────────────────────────────┐
│ Service Layer (Business Logic)                               │
│  - ServiceLocator (factory/registry)                         │
│  - Model, Port, Docker, Task, Batch, Analyzer Integration    │
└───────────────▲──────────────────────────────────────────────┘
				│
┌───────────────┴──────────────────────────────────────────────┐
│ Asynchronous / Integration Layer                             │
│  - Celery Tasks (analysis, batch, container ops)             │
│  - WebSocket Bridge (AnalyzerIntegration / WebSocketIntegration)│
└───────────────▲──────────────────────────────────────────────┘
				│
┌───────────────┴──────────────────────────────────────────────┐
│ Analyzer Microservices (Docker)                              │
│  - static-analyzer / dynamic-analyzer / performance-tester   │
│  - ai-analyzer / security composite                          │
└───────────────▲──────────────────────────────────────────────┘
				│
┌───────────────┴──────────────────────────────────────────────┐
│ Persistence                                                   │
│  - SQLAlchemy Models + JSON Results                          │
│  - Seed JSON (fallback)                                      │
└──────────────────────────────────────────────────────────────┘
```

### Mermaid Diagram (Layered Architecture)

```mermaid
flowchart TB
	subgraph UI[Presentation Layer]
		R[Flask Routes]\nHTMX
		Tmpl[Jinja Templates]
	end
	subgraph S[Service Layer]
		SL[ServiceLocator]
		MS[Model/Port Services]
		TM[TaskManager]
		AI[AnalyzerIntegration]
	end
	subgraph C[Async Layer]
		CT[Celery Tasks]
		WB[WebSocket Bridge]
	end
	subgraph A[Analyzer Containers]
		SA[static]
		DA[dynamic/ZAP]
		PA[performance]
		AA[ai]
		SEC[security]
	end
	subgraph P[Persistence]
		DB[(Database)]
		JSON[(JSON Results)]
	end
	UI --> S --> C --> A
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
| Analyzer Bridge | WebSocket orchestration to analyzer containers | `analyzer/websocket_gateway.py`, `app/services/analyzer_integration.py` |
| Analyzer Microservices | Execute specialized analyses | `analyzer/services/*` |
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

## Analyzer Integration Contract

Messages (JSON) follow a command pattern: `{ "action": "run_static", "model": <slug>, "app": <n>, "options": {...} }`. Responses stream progress events until a terminal event with results payload. The bridge is intentionally narrow: START, PROGRESS, COMPLETE, ERROR.

## Error Containment

Failures in analyzer communication mark a single analysis as FAILED without destabilizing the Flask process. Celery’s retry/backoff capabilities can be selectively enabled per task type if reliability needs increase.

## Extensibility Points

| Extension | Required Steps |
|-----------|----------------|
| New Analyzer | Container + WebSocket handler + Celery task + result model/table + UI fragments |
| New Dashboard Metric | Add aggregation query (service), route endpoint, HTMX fragment template |
| Alternate Transport (e.g., gRPC) | Implement adapter parallel to WebSocketIntegration; register in ServiceLocator |
| Caching Layer | Introduce cache service; wrap service methods returning large JSON |

## Configuration Sources

| Source | Purpose | Precedence |
|--------|---------|------------|
| Environment Variables | Operational toggles (strict websocket, concurrency) | Highest |
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
User Browser --> Flask/HTMX (5000) --> Services --> DB (SQLite/Postgres) 
								\--> Celery (Redis broker) --> Analyzer Bridge --> Analyzer Containers (2001-2005)
```

## Observability Hooks

See [Observability](OBSERVABILITY.md) for log streams, health endpoints, and metrics fragments. Key endpoints: `/health`, `/system/health`, `/analyzer/status`.

---
_Last updated: 2025-08-24._ 
