# ThesisAppRework AI Agent Instructions

## Architecture Overview

This is a Flask-based platform for analyzing AI-generated applications. The system automates the full lifecycle: **generate apps from LLMs → build containers → run multi-tool analysis → aggregate results**.

### System Layers

```
┌─────────────────────────────────────────────────────────────────┐
│  Web UI (Flask + HTMX)     │  REST API (/api/v1/)              │
├─────────────────────────────────────────────────────────────────┤
│  Celery Worker (Pipeline Orchestration)                         │
│  └── PipelineExecutionService: Generation → Analysis → Done     │
├─────────────────────────────────────────────────────────────────┤
│  Analyzer Gateway (ws://localhost:8765)                         │
│  └── Routes requests to analyzer microservices                  │
├─────────────────────────────────────────────────────────────────┤
│  Analyzer Services (Docker containers, ports 2001-2004)         │
│  ├── static-analyzer:2001   (Bandit, Semgrep, ESLint, etc.)    │
│  ├── dynamic-analyzer:2002  (OWASP ZAP, Nmap)                  │
│  ├── performance-tester:2003 (Locust, Artillery, ab)           │
│  └── ai-analyzer:2004       (LLM-powered code review)          │
└─────────────────────────────────────────────────────────────────┘
```

### Key Files

| Component | Path | Purpose |
|-----------|------|---------|
| Pipeline Orchestration | `src/app/services/pipeline_execution_service.py` | Two-stage pipeline: generation → analysis |
| Task Execution | `src/app/services/task_execution_service.py` | Celery tasks, WebSocket dispatch |
| Docker Manager | `src/app/services/docker_manager.py` | Container lifecycle for generated apps |
| WebSocket Protocol | `analyzer/shared/protocol.py` | Message types for Flask↔Analyzer communication |
| Generation V2 | `src/app/services/generation_v2/` | LLM-based app generation |

---

## Automation Pipeline

### Pipeline Lifecycle

```
User initiates pipeline (UI/API)
        ↓
┌──────────────────────────────────────────────────────────────┐
│  GENERATION STAGE                                             │
│  ├── Parallel LLM calls (5 concurrent, ThreadPoolExecutor)   │
│  ├── Code saved to generated/{model_slug}/app{N}/            │
│  └── Docker images built for each app                        │
└──────────────────────────────────────────────────────────────┘
        ↓
┌──────────────────────────────────────────────────────────────┐
│  ANALYSIS STAGE                                               │
│  ├── App containers started (backend:500X, frontend:800X)    │
│  ├── 4 analyzer types run in parallel per app                │
│  │   ├── Static: code scanning (no container needed)         │
│  │   ├── Dynamic: OWASP ZAP security scan (needs container)  │
│  │   ├── Performance: load testing (needs container)         │
│  │   └── AI: LLM code review (no container needed)           │
│  └── Results saved to results/{model_slug}/app{N}/task_{id}/ │
└──────────────────────────────────────────────────────────────┘
        ↓
Pipeline complete (COMPLETED/PARTIAL_SUCCESS/FAILED)
```

### Pipeline Model (`PipelineExecution`)

```python
# Key fields
pipeline_id: str           # Unique identifier
status: str               # pending|running|paused|completed|partial_success|failed
current_stage: str        # 'generation' or 'analysis'
config_json: {
    'generation': { 'mode': 'generate', 'models': [...], 'templates': [...] },
    'analysis': { 'enabled': True, 'tools': [...], 'autoStartContainers': True }
}
progress_json: {
    'generation': { 'total': N, 'completed': M, 'failed': F, 'results': [...] },
    'analysis': { 'total': N, 'completed': M, 'main_task_ids': [...] }
}
```

### Concurrency & Parallelism

| Stage | Default Concurrency | Config Key | Notes |
|-------|---------------------|------------|-------|
| Generation | 5 jobs | `MAX_CONCURRENT_GENERATION` | ThreadPoolExecutor(10 workers) |
| Analysis | 2-3 tasks | `maxConcurrentTasks` in config | Semaphore for container builds |
| Per-App Analysis | 4 analyzers | Parallel subtasks | All 4 types run simultaneously |

### Circuit Breaker Pattern

Prevents cascading failures when analyzer services are unhealthy:
```python
# Threshold: 3 failures → 120s cooldown
_is_service_circuit_open(service_name)  # Check before dispatch
_record_service_failure(service_name)   # On error
_record_service_success(service_name)   # Reset on success
```

---

## Docker Container Management

### Generated App Containers

Apps are built and run as Docker containers for dynamic/performance analysis:

```
generated/{model_slug}/app{N}/
├── docker-compose.yml      # Defines backend + frontend services
├── backend/
│   ├── Dockerfile
│   └── app.py, requirements.txt, etc.
└── frontend/
    ├── Dockerfile
    └── src/, package.json, etc.
```

**Container naming**: `{model-slug-sanitized}_app{N}_{service}`
- Example: `anthropic-claude-4-5-sonnet-app1_backend`

**Port allocation**:
- Backend: `500X` (5001, 5002, ...)
- Frontend: `800X` (8001, 8002, ...)
- Managed by `PortConfiguration` model

### Docker Networks

```yaml
# docker-compose.yml networks
thesis-network:        # Core services (web, analyzers, redis)
thesis-apps-network:   # External network for generated app containers
```

**Important**: Dynamic analyzer uses `thesis-apps-network` to reach app containers. Performance tester uses `host.docker.internal` for host-mode access.

### Container Lifecycle

```python
# DockerManager methods
start_containers(model_slug, app_number)   # Build & start
stop_containers(model_slug, app_number)    # Graceful shutdown  
build_containers(model_slug, app_number, no_cache=True)  # Force rebuild
get_container_health(model_slug, app_number)  # Poll health status
```

---

## Key Conventions

### Service Pattern
All business logic lives in `src/app/services/`. Services are registered via `ServiceLocator`:
```python
from app.services.service_locator import ServiceLocator
pipeline_svc = ServiceLocator.get_pipeline_execution_service()
docker_mgr = ServiceLocator.get_docker_manager()
```

### Model Slugs
Format: `{provider}_{model-name}` (e.g., `anthropic_claude-4-5-sonnet-20250929`)
- Used for directory paths: `generated/{model_slug}/app{N}/`
- Used for results: `results/{model_slug}/app{N}/task_{id}/`

### Status Enums
```python
from app.constants import AnalysisStatus, PipelineStatus
task.status = AnalysisStatus.RUNNING
pipeline.status = PipelineStatus.COMPLETED
```

### Time Handling
Always use timezone-aware UTC:
```python
from app.utils.time import utc_now
created_at = utc_now()
```

---

## Development Commands

```bash
# Start full stack (Docker containers + Flask)
./start.ps1 -Mode Start      # Windows
./start.sh                   # Linux

# Quick dev mode without analyzers
./start.ps1 -Mode Dev -NoAnalyzer

# Rebuild containers (fast, cached)
./start.ps1 -Mode Rebuild

# Full clean rebuild (wipes images)
./start.ps1 -Mode CleanRebuild

# Clean up generated app containers/images
docker ps -a --format '{{.Names}}' | grep -E '^(anthropic|google|openai)' | xargs docker rm -f
docker images --format '{{.Repository}}' | grep -E '^(anthropic|google|openai)' | xargs docker rmi -f
```

---

## Testing

```bash
# Fast unit tests (excludes integration/slow/analyzer)
pytest -m "not integration and not slow and not analyzer"

# Run specific test file
pytest tests/unit/test_task_service.py -v

# Integration tests (requires Docker analyzers)
pytest tests/integration/ -m integration

# Pipeline-specific tests
pytest tests/unit/test_pipeline_execution_service.py -v
```

Test markers: `unit`, `integration`, `slow`, `analyzer`, `smoke`, `api`, `websocket`

---

## File Organization

```
src/app/
├── routes/           # Web UI routes
├── routes/api/       # REST API endpoints
├── models/           # SQLAlchemy models (PipelineExecution, AnalysisTask, etc.)
├── services/         # Business logic (pipeline, docker, task execution)
└── constants.py      # Status enums, config constants

analyzer/
├── services/         # Analyzer microservices (static, dynamic, perf, ai)
├── shared/           # Shared protocol, utilities
├── configs/          # Tool configurations (Bandit, Semgrep rules)
└── websocket_gateway.py  # Routes requests to analyzers

generated/            # LLM-generated app code
├── apps/             # {model_slug}/app{N}/ directories
├── raw/              # Raw LLM responses
└── metadata/         # Generation metadata

results/              # Analysis outputs
└── {model_slug}/app{N}/task_{id}/
    ├── analysis.json
    ├── sarif/
    └── manifest.json
```

---

## Adding New Features

### New Analyzer Tool
1. Add tool execution in `analyzer/services/{analyzer}/main.py`
2. Add config in `analyzer/configs/`
3. Update message handling if new message type needed

### New Pipeline Stage
1. Add stage handler in `PipelineExecutionService._process_{stage}_stage()`
2. Update `_transition_to_{next_stage}()` logic
3. Add progress tracking in `progress_json`

### New API Endpoint
```python
# src/app/routes/api/
@api_bp.route('/pipeline/<pipeline_id>/status', methods=['GET'])
@require_api_key
def get_pipeline_status(pipeline_id):
    pipeline = PipelineExecution.query.filter_by(pipeline_id=pipeline_id).first_or_404()
    return jsonify(pipeline.to_dict())
```

---

## Troubleshooting

### Dynamic Analyzer Can't Reach App Containers
- Ensure app containers are on `thesis-apps-network`
- Check container name resolution: `docker exec dynamic-analyzer ping {container-name}`
- Verify ports are exposed correctly in generated `docker-compose.yml`

### Pipeline Stuck in RUNNING
- Check `celery-worker` logs: `docker logs thesisapprework-celery-worker-1`
- Verify Redis is healthy: `docker exec redis redis-cli ping`
- Check circuit breaker status in logs

### Container Build Failures
- Clean up old images: `docker system prune -f`
- Check generated Dockerfile syntax in `generated/{model}/app{N}/`
- Verify Docker socket permissions in container
