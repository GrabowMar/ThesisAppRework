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

| Service | Purpose | Polling |
|---------|---------|---------|
| TaskExecutionService | Executes PENDING analysis tasks | 2-10s |
| MaintenanceService | Cleanup orphans, stuck tasks | Manual/hourly |
| PipelineExecutionService | Automation pipelines | Event-driven |

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
| `MAINTENANCE_AUTO_START` | Auto-start cleanup | `false` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |
| `STATIC_ANALYSIS_TIMEOUT` | Tool timeout (seconds) | `300` |

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

# Tests
pytest -m "not integration and not slow and not analyzer"
```

## Related Documentation

- [API Reference](./api-reference.md)
- [Development Guide](./development-guide.md)
- [Deployment Guide](./deployment-guide.md)
- [Analyzer README](../analyzer/README.md)
