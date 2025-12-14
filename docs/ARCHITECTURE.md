# Architecture Overview

ThesisAppRework is a Flask-based web application with containerized microservices for analyzing AI-generated applications. The system evaluates code quality, security, performance, and requirements compliance.

## System Architecture

```mermaid
flowchart TB
    subgraph Client["Client Layer"]
        Browser["Web Browser"]
        API["REST API Client"]
    end

    subgraph Flask["Flask Application :5000"]
        Routes["Routes & API"]
        Services["Service Layer"]
        Tasks["Task Execution"]
        DB[(SQLite)]
    end

    subgraph Analyzers["Analyzer Microservices"]
        Static["Static Analyzer\n:2001"]
        Dynamic["Dynamic Analyzer\n:2002"]
        Perf["Performance Tester\n:2003"]
        AI["AI Analyzer\n:2004"]
    end

    subgraph Storage["Storage Layer"]
        Generated["generated/apps/"]
        Results["results/"]
    end

    Browser --> Routes
    API --> Routes
    Routes --> Services
    Services --> Tasks
    Services --> DB
    Tasks -->|WebSocket| Static
    Tasks -->|WebSocket| Dynamic
    Tasks -->|WebSocket| Perf
    Tasks -->|WebSocket| AI
    Static --> Generated
    Dynamic --> Generated
    Perf --> Generated
    AI --> Generated
    Static --> Results
    Dynamic --> Results
    Perf --> Results
    AI --> Results
```

## Component Details

### Flask Application

| Component | Location | Purpose |
|-----------|----------|---------|
| Entry Point | [src/main.py](../src/main.py) | Server startup, logging |
| App Factory | [src/app/factory.py](../src/app/factory.py) | Initialization, DI setup |
| Service Locator | [src/app/services/service_locator.py](../src/app/services/service_locator.py) | Dependency injection |
| Models | [src/app/models/](../src/app/models/) | SQLAlchemy ORM |
| Routes | [src/app/routes/](../src/app/routes/) | Web endpoints |
| API | [src/app/api/](../src/app/api/) | REST API endpoints |

### Analyzer Services

| Service | Port | Tools | Source |
|---------|------|-------|--------|
| Static | 2001 | Bandit, Semgrep, ESLint, Pylint, Ruff, MyPy | [analyzer/services/static-analyzer/](../analyzer/services/static-analyzer/) |
| Dynamic | 2002 | OWASP ZAP, nmap, curl probes | [analyzer/services/dynamic-analyzer/](../analyzer/services/dynamic-analyzer/) |
| Performance | 2003 | Locust, aiohttp, Apache ab | [analyzer/services/performance-tester/](../analyzer/services/performance-tester/) |
| AI | 2004 | OpenRouter LLM analysis | [analyzer/services/ai-analyzer/](../analyzer/services/ai-analyzer/) |

## Service Layer

```mermaid
flowchart LR
    subgraph ServiceLocator["ServiceLocator"]
        Model["ModelService"]
        Gen["GenerationService"]
        Docker["DockerService"]
        Cache["DockerCacheService"]
        Inspect["AnalysisInspectionService"]
        Unified["UnifiedResultsService"]
        Report["ReportService"]
        Health["HealthCheckService"]
    end

    subgraph Background["Background Services"]
        TaskExec["TaskExecutionService"]
        Maint["MaintenanceService"]
        Pipeline["PipelineExecutionService"]
    end

    Factory["factory.py"] --> ServiceLocator
    Factory --> Background
    TaskExec -->|dispatches| AnalyzerManager
    AnalyzerManager["AnalyzerManager"] -->|WebSocket| Containers["Analyzer Containers"]
```

### Background Services

| Service | Purpose | Polling | Default |
|---------|---------|---------|---------|
| TaskExecutionService | Executes PENDING analysis tasks | 2-10s | Auto-start |
| MaintenanceService | Cleanup orphans, stuck tasks | Manual/hourly | **Manual** |
| PipelineExecutionService | Automation pipelines | Event-driven | Auto-start |

> **Note**: MaintenanceService is manual by default as of Nov 2025. Run via `./start.ps1 -Mode Maintenance` or set `MAINTENANCE_AUTO_START=true`.

See [BACKGROUND_SERVICES.md](./BACKGROUND_SERVICES.md) for detailed configuration and debugging.

## Data Flow

### Analysis Task Lifecycle

```mermaid
sequenceDiagram
    participant U as User/API
    participant F as Flask
    participant DB as Database
    participant T as TaskExecutionService
    participant A as AnalyzerManager
    participant S as Analyzer Service
    participant R as Results Storage

    U->>F: Create analysis request
    F->>DB: Insert AnalysisTask (PENDING)
    F->>U: Return task_id

    loop Poll every 2-10s
        T->>DB: Query PENDING tasks
    end

    T->>DB: Update status (RUNNING)
    T->>A: Dispatch analysis
    A->>S: WebSocket connect
    
    loop Progress frames
        S->>A: progress_update
    end
    
    S->>A: *_analysis_result (terminal)
    A->>R: Save consolidated JSON
    A->>T: Return results
    T->>DB: Update status (COMPLETED)
```

### Task Status Lifecycle

```mermaid
stateDiagram-v2
    [*] --> PENDING: Task created
    PENDING --> RUNNING: TaskExecutionService picks up
    PENDING --> CANCELLED: Timeout (>4h) or user cancel
    RUNNING --> COMPLETED: Success
    RUNNING --> FAILED: Error
    RUNNING --> PARTIAL_SUCCESS: Some subtasks failed
    RUNNING --> FAILED: Timeout (>2h)
    COMPLETED --> [*]
    FAILED --> [*]
    CANCELLED --> [*]
    PARTIAL_SUCCESS --> [*]
```

## Database Schema

```mermaid
erDiagram
    GeneratedApplication ||--o{ AnalysisTask : "analyzed by"
    AnalysisTask ||--o{ AnalysisResult : "produces"
    AnalysisTask ||--o{ AnalysisTask : "parent/subtask"
    AnalyzerConfiguration ||--o{ AnalysisTask : "configures"
    User ||--o{ APIToken : "owns"
    User ||--o{ AnalysisTask : "creates"
    
    GeneratedApplication {
        int id PK
        string model_slug
        int app_number
        string provider
        string template_name
        string container_status
        datetime missing_since
    }
    
    AnalysisTask {
        string task_id PK
        string status
        string target_model
        int target_app_number
        int progress_percentage
        bool is_main_task
        string parent_task_id FK
        string service_name
        json result_summary
        string error_message
    }
    
    AnalysisResult {
        int id PK
        string task_id FK
        string tool_name
        string severity
        string file_path
        json sarif_metadata
    }
    
    AnalyzerConfiguration {
        int id PK
        string name
        json config_data
        bool is_default
    }
```

## Communication Patterns

### WebSocket Protocol

Analyzer services communicate via WebSocket using a shared protocol defined in [analyzer/shared/protocol.py](../analyzer/shared/protocol.py).

| Message Type | Direction | Purpose |
|--------------|-----------|---------|
| `*_analysis_request` | Client→Service | Start analysis |
| `progress_update` | Service→Client | Progress % |
| `*_analysis_result` | Service→Client | Final result |
| `error` | Service→Client | Error details |

### Connection Resilience (Dec 2025)

The system implements robust connection handling for analyzer services:

```mermaid
flowchart TB
    subgraph PreFlight["Pre-flight Checks"]
        Check["TCP Port Check"]
        WS["WebSocket Handshake"]
    end
    
    subgraph Retry["Retry Logic"]
        R1["Attempt 1"]
        R2["Attempt 2 (2s delay)"]
        R3["Attempt 3 (4s delay)"]
        R4["Final (8s delay)"]
    end
    
    subgraph Circuit["Circuit Breaker"]
        Open["OPEN (5min cooldown)"]
        Closed["CLOSED (normal)"]
        HalfOpen["HALF-OPEN (test)"]
    end
    
    Check -->|success| WS
    Check -->|fail| R1
    R1 -->|fail| R2
    R2 -->|fail| R3
    R3 -->|fail| R4
    R4 -->|3 failures| Open
    Open -->|5min| HalfOpen
    HalfOpen -->|success| Closed
```

| Feature | Behavior |
|---------|----------|
| Pre-flight checks | TCP port + WebSocket handshake before starting subtasks |
| Exponential backoff | 2s → 4s → 8s delays between retries |
| Circuit breaker | 3 consecutive failures → 5-minute cooldown |
| Auto-recovery | Services available again after cooldown or first success |

### REST API Authentication

Bearer token authentication via `Authorization: Bearer <token>` header. Tokens managed through User → API Access in the web UI.

## Deployment Architecture

```mermaid
flowchart TB
    subgraph Host["Host Machine"]
        Flask["Flask App\n:5000"]
        Gateway["WS Gateway\n:8765"]
    end

    subgraph Docker["Docker Compose"]
        Static["static-analyzer\n:2001"]
        Dynamic["dynamic-analyzer\n:2002"]
        Perf["performance-tester\n:2003"]
        AI["ai-analyzer\n:2004"]
        Redis["Redis\n:6379"]
        Celery["Celery Worker"]
    end

    subgraph Volumes["Mounted Volumes"]
        Apps["generated/apps\n(read-only)"]
        Res["results/\n(read-write)"]
    end

    Flask -->|WebSocket| Static
    Flask -->|WebSocket| Dynamic
    Flask -->|WebSocket| Perf
    Flask -->|WebSocket| AI
    Gateway --> Static
    Gateway --> Dynamic
    Gateway --> Perf
    Gateway --> AI
    Celery --> Redis
    Static --> Apps
    Static --> Res
    Dynamic --> Apps
    Dynamic --> Res
```

### Container Resources

| Service | Memory | CPU |
|---------|--------|-----|
| static-analyzer | 1GB | 1.0 |
| dynamic-analyzer | 2GB | 1.0 |
| performance-tester | 1GB | 0.5 |
| ai-analyzer | 512MB | 0.5 |

## Results Storage

```
results/
└── {model_slug}/
    └── app{N}/
        └── task_{id}/
            ├── {model}_app{N}_task_{id}_{timestamp}.json  # Consolidated
            ├── manifest.json                              # Metadata
            ├── sarif/                                     # SARIF files
            │   ├── static_bandit.sarif.json
            │   └── static_semgrep.sarif.json
            └── services/                                  # Per-service
                ├── static.json
                ├── dynamic.json
                └── ai.json
```

See [analyzer/README.md](../analyzer/README.md) for detailed result format documentation.

## Environment Configuration

| Variable | Purpose | Default |
|----------|---------|---------|
| `OPENROUTER_API_KEY` | AI analyzer authentication | Required |
| `ANALYZER_ENABLED` | Enable analyzer integration | `true` |
| `ANALYZER_AUTO_START` | Auto-start containers | `false` |
| `MAINTENANCE_AUTO_START` | Auto-start cleanup service | `false` |
| `USE_CELERY_ANALYSIS` | Use Celery instead of ThreadPoolExecutor | `false` |
| `TASK_POLL_INTERVAL` | Task polling interval (seconds) | `10` (prod), `2` (test) |
| `LOG_LEVEL` | Logging verbosity | `INFO` |
| `STATIC_ANALYSIS_TIMEOUT` | Static tool timeout (seconds) | `300` |
| `SECURITY_ANALYSIS_TIMEOUT` | Security tool timeout (seconds) | `600` |
| `PERFORMANCE_TIMEOUT` | Performance test timeout (seconds) | `300` |
| `TASK_TIMEOUT` | Overall task timeout (seconds) | `1800` |

## Task Execution

The system uses **ThreadPoolExecutor** by default (8 workers) for parallel task execution. Celery is available as an optional alternative for distributed workloads.

```mermaid
flowchart LR
    subgraph Executor["Default: ThreadPoolExecutor"]
        Pool["8 Worker Threads"]
        Queue["Task Queue"]
    end
    
    subgraph Optional["Optional: Celery"]
        Redis["Redis Broker"]
        Workers["Celery Workers"]
    end
    
    Flask["Flask App"] --> Pool
    Pool --> Queue
    Flask -.->|USE_CELERY_ANALYSIS=true| Redis
    Redis --> Workers
```

| Mode | Environment | Use Case |
|------|-------------|----------|
| ThreadPoolExecutor | Default | Single-server, development |
| Celery + Redis | `USE_CELERY_ANALYSIS=true` | Multi-server, production scale |

## Container Management

### Rebuild Strategies

| Command | Time | Cache | Use Case |
|---------|------|-------|----------|
| `./start.ps1 -Mode Rebuild` | 30-90s | BuildKit cache | Code changes, dependency updates |
| `./start.ps1 -Mode CleanRebuild` | 12-18min | No cache | Dockerfile changes, cache corruption |

BuildKit optimizations used:
- `--mount=type=cache,target=/root/.cache/pip` - Persistent pip cache
- `--mount=type=cache,target=/root/.npm` - Persistent npm cache
- Shared base image across analyzer services

## Quick Reference

```bash
# Start everything
./start.ps1 -Mode Start

# Flask only (dev)
./start.ps1 -Mode Dev -NoAnalyzer

# Analyzer management
python analyzer/analyzer_manager.py start
python analyzer/analyzer_manager.py status
python analyzer/analyzer_manager.py health

# Run analysis
python analyzer/analyzer_manager.py analyze openai_gpt-4 1 comprehensive

# Container rebuilds
./start.ps1 -Mode Rebuild        # Fast (cached)
./start.ps1 -Mode CleanRebuild   # Full rebuild

# Maintenance (manual)
./start.ps1 -Mode Maintenance

# Other utilities
./start.ps1 -Mode Wipeout        # Full reset
./start.ps1 -Mode Password       # Reset admin password
./start.ps1 -Mode Reload         # Hot reload

# Tests
pytest -m "not integration and not slow and not analyzer"
```

## Related Documentation

- [Background Services](./BACKGROUND_SERVICES.md) - TaskExecution, Maintenance, Pipeline services
- [API Reference](./api-reference.md) - REST API and WebSocket documentation
- [Analyzer Guide](./ANALYZER_GUIDE.md) - Analyzer services and tools
- [Development Guide](./development-guide.md) - Contributing and testing
- [Deployment Guide](./deployment-guide.md) - Production deployment
- [Troubleshooting](./TROUBLESHOOTING.md) - Common issues and recovery
- [Analyzer README](../analyzer/README.md) - Detailed result formats
