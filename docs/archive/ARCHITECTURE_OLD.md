# System Architecture

> Comprehensive architectural overview of the ThesisApp AI Model Analysis Platform

---

## 📋 Table of Contents

- [System Overview](#system-overview)
- [Architecture Layers](#architecture-layers)
- [Component Details](#component-details)
- [Data Flow](#data-flow)
- [Technology Stack](#technology-stack)
- [Design Patterns](#design-patterns)
- [Deployment Architecture](#deployment-architecture)

---

## System Overview

ThesisApp is a **microservices-based platform** for generating, executing, and analyzing AI-generated applications with real-time monitoring and comprehensive multi-dimensional analysis.

### High-Level Architecture

```mermaid
graph TB
    subgraph "Client Layer"
        Browser[Web Browser]
        CLI[CLI Tools]
    end
    
    subgraph "Application Layer"
        Web[Flask Web App<br/>:5000]
        API[REST API]
        WS[WebSocket Client]
        Tasks[Celery Workers]
    end
    
    subgraph "Analyzer Layer"
        Gateway[WebSocket Gateway<br/>:8765]
        Static[Static Analyzer<br/>:2001]
        Dynamic[Dynamic Analyzer<br/>:2002]
        Perf[Performance Tester<br/>:2003]
        AI[AI Analyzer<br/>:2004]
    end
    
    subgraph "Data Layer"
        DB[(PostgreSQL/SQLite)]
        Redis[(Redis Cache)]
        FS[File System<br/>generated/apps, results/]
    end
    
    subgraph "External Services"
        OpenRouter[OpenRouter API]
        Docker[Docker Engine]
    end
    
    Browser --> Web
    CLI --> API
    Browser --> WS
    
    Web --> API
    Web --> Tasks
    API --> DB
    WS --> Gateway
    
    Tasks --> Static
    Tasks --> Dynamic
    Tasks --> Perf
    Tasks --> AI
    Tasks --> Redis
    Tasks --> FS
    
    Static --> Gateway
    Dynamic --> Gateway
    Perf --> Gateway
    AI --> Gateway
    
    AI --> OpenRouter
    Tasks --> Docker
    Static --> Docker
    Dynamic --> Docker
    Perf --> Docker
    
    style Browser fill:#4CAF50
    style Web fill:#2196F3
    style Gateway fill:#FF9800
    style DB fill:#9C27B0
```

### Core Capabilities

| Capability | Description | Components |
|------------|-------------|------------|
| **Generation** | AI-powered app creation from templates | Flask, Celery, OpenRouter |
| **Execution** | Docker orchestration of generated apps | Docker Engine, Compose |
| **Analysis** | Multi-dimensional testing and review | 4 analyzer services, 15 tools |
| **Monitoring** | Real-time progress and status tracking | WebSocket Gateway, Redis |
| **Management** | App lifecycle and result management | Flask, Database, File System |

---

## Architecture Layers

### 1. Presentation Layer

**Purpose**: User interaction and visualization

```mermaid
graph LR
    A[Templates] --> B[Jinja2 Rendering]
    B --> C[HTML Pages]
    C --> D[Bootstrap 5 UI]
    D --> E[HTMX Enhancements]
    E --> F[Client Browser]
    
    G[Static Assets] --> D
    H[JavaScript] --> D
    
    style A fill:#4CAF50
    style D fill:#2196F3
    style F fill:#FF9800
```

**Components**:
- **Templates**: Jinja2 templates in `src/templates/`
  - Pages: Full page templates
  - Partials: HTMX fragments for dynamic loading
  - Components: Reusable UI elements
- **Static Assets**: CSS, JavaScript, images in `src/static/`
- **UI Framework**: Bootstrap 5 (no jQuery dependency)
- **Progressive Enhancement**: HTMX for dynamic updates
- **Icons**: Font Awesome (solid style)

### 2. Application Layer

**Purpose**: Business logic and request handling

```mermaid
graph TB
    subgraph "Flask Application"
        Routes[Route Blueprints]
        Services[Business Services]
        Models[Database Models]
        Tasks[Celery Tasks]
    end
    
    Routes --> Services
    Services --> Models
    Services --> Tasks
    Models --> DB[(Database)]
    Tasks --> Queue[(Redis Queue)]
    
    style Routes fill:#4CAF50
    style Services fill:#2196F3
    style Tasks fill:#FF9800
```

**Components**:
- **Flask App**: Main application server
  - Routes: Domain-separated blueprints
  - Middleware: Request logging, error handling
  - Extensions: SQLAlchemy, Celery, CORS
- **Services**: Business logic layer
  - `GenerationService`: App creation
  - `AnalysisService`: Test orchestration
  - `PortAllocationService`: Port management
  - `ContainerService`: Docker operations
  - `ResultsService`: Result management
- **Models**: Database entities via SQLAlchemy
  - `GeneratedApplication`
  - `AnalysisTask`
  - `ModelCapability`
  - `PortAllocation`
- **Celery Tasks**: Async job processing
  - `generate_application`: App generation
  - `analyze_application`: Analysis execution
  - Background workers for long-running operations

### 3. Analyzer Layer

**Purpose**: Specialized analysis microservices

```mermaid
graph TB
    subgraph "Static Analyzer :2001"
        S1[Security Tools]
        S2[Quality Tools]
        S3[Metrics Tools]
    end
    
    subgraph "Dynamic Analyzer :2002"
        D1[Runtime Testing]
        D2[OWASP ZAP]
        D3[Behavior Analysis]
    end
    
    subgraph "Performance Tester :2003"
        P1[Load Testing]
        P2[Benchmarking]
        P3[Resource Monitoring]
    end
    
    subgraph "AI Analyzer :2004"
        A1[Code Review]
        A2[Architecture Analysis]
        A3[Best Practices]
    end
    
    Gateway[WebSocket Gateway<br/>:8765]
    
    S1 --> Gateway
    S2 --> Gateway
    S3 --> Gateway
    D1 --> Gateway
    D2 --> Gateway
    D3 --> Gateway
    P1 --> Gateway
    P2 --> Gateway
    P3 --> Gateway
    A1 --> Gateway
    A2 --> Gateway
    A3 --> Gateway
    
    style Gateway fill:#FF9800
```

**Services**:

| Service | Port | Purpose | Tools |
|---------|------|---------|-------|
| **static-analyzer** | 2001 | Code analysis without execution | Bandit, Safety, Pylint, Flake8, ESLint, Radon, Semgrep |
| **dynamic-analyzer** | 2002 | Runtime behavior testing | OWASP ZAP, runtime monitors |
| **performance-tester** | 2003 | Load and performance testing | Locust, Apache Bench, custom load |
| **ai-analyzer** | 2004 | AI-powered code review | OpenRouter models, custom prompts |

**WebSocket Gateway** (Port 8765):
- Central hub for real-time communication
- Broadcasts progress updates from all analyzers
- Handles client subscriptions and unsubscriptions

### 4. Data Layer

**Purpose**: Persistent and transient data storage

```mermaid
graph LR
    subgraph "Persistent Storage"
        DB[(PostgreSQL/SQLite)]
        FS[File System]
    end
    
    subgraph "Transient Storage"
        Redis[(Redis)]
    end
    
    subgraph "External Storage"
        Docker[Docker Volumes]
    end
    
    App[Application] --> DB
    App --> FS
    App --> Redis
    App --> Docker
    
    style DB fill:#9C27B0
    style Redis fill:#FF9800
    style FS fill:#4CAF50
```

**Storage Types**:

| Storage | Type | Purpose | Example |
|---------|------|---------|---------|
| **Database** | PostgreSQL/SQLite | Structured data | Apps, tasks, results metadata |
| **File System** | Local disk | Generated apps, results | `generated/apps/`, `results/` |
| **Redis** | In-memory cache | Task queue, caching | Celery broker, status cache |
| **Docker Volumes** | Container storage | Persistent container data | Database files, logs |

---

## Component Details

### Flask Application

**Location**: `src/app/`

**Structure**:
```
app/
├── __init__.py           # App factory
├── factory.py            # Application initialization
├── extensions.py         # Flask extensions
├── routes/              # Blueprint routes
│   ├── dashboard.py
│   ├── models.py
│   ├── analysis.py
│   ├── tasks.py
│   └── api/            # API endpoints
├── services/           # Business logic
│   ├── sample_generation_service.py
│   ├── analysis_orchestrator.py
│   ├── port_allocation_service.py
│   ├── container_service.py
│   └── results_service.py
├── models/             # Database models
│   ├── application.py
│   ├── task.py
│   └── capability.py
└── tasks/              # Celery tasks
    ├── generation_tasks.py
    └── analysis_tasks.py
```

**Key Features**:
- **Factory Pattern**: App creation via `create_app()`
- **Blueprint Architecture**: Domain-separated routes
- **Service Locator**: Dependency injection for services
- **Extension Management**: Centralized extension initialization

### Analyzer Microservices

**Location**: `analyzer/services/`

**Structure**:
```
services/
├── static-analyzer/
│   ├── Dockerfile
│   ├── analyzer.py      # Main analyzer logic
│   ├── requirements.txt
│   └── tools/          # Individual tool integrations
├── dynamic-analyzer/
│   ├── Dockerfile
│   ├── analyzer.py
│   └── tools/
├── performance-tester/
│   ├── Dockerfile
│   ├── tester.py
│   └── tools/
└── ai-analyzer/
    ├── Dockerfile
    ├── analyzer.py
    └── prompts/        # AI review prompts
```

**Communication Protocol**:
```python
# WebSocket message format
{
    "type": "progress",
    "task_id": "task_20251014_143022",
    "analyzer": "static-analyzer",
    "tool": "bandit",
    "status": "running",
    "progress": 45,
    "message": "Scanning file 3 of 12"
}
```

### Tool Registry

**Location**: `src/app/services/analysis_engines.py`

**Registry Structure**:
```python
@dataclass
class ToolDefinition:
    name: str                    # Tool identifier
    container: str               # Container hosting tool
    category: str                # security, performance, quality, ai
    description: str             # Human-readable description
    requires_running_app: bool   # Needs app container running
    default_enabled: bool        # Enabled by default
    timeout_seconds: int         # Execution timeout

TOOL_REGISTRY: Dict[str, ToolDefinition] = {
    "bandit": ToolDefinition(
        name="bandit",
        container="static-analyzer",
        category="security",
        description="Python security linter",
        requires_running_app=False,
        default_enabled=True,
        timeout_seconds=60
    ),
    # ... 14 more tools
}
```

**Tool Resolution**:
```mermaid
graph LR
    Request[Analysis Request] --> Parse[Parse Tool Names]
    Parse --> Validate{Valid Tools?}
    Validate -->|Yes| Group[Group by Container]
    Validate -->|No| Error[Error Response]
    Group --> Route[Route to Containers]
    Route --> Execute[Execute Tools]
    Execute --> Collect[Collect Results]
    
    style Request fill:#4CAF50
    style Group fill:#2196F3
    style Collect fill:#FF9800
```

---

## Data Flow

### Application Generation Flow

```mermaid
sequenceDiagram
    participant User
    participant Web as Flask Web
    participant Celery
    participant Gen as Generation Service
    participant AI as OpenRouter API
    participant DB as Database
    participant FS as File System
    
    User->>Web: Generate App Request
    Web->>Celery: Queue Task
    Web-->>User: Task ID
    
    Celery->>Gen: Start Generation
    Gen->>Gen: Classify Model (Tier)
    Gen->>Gen: Select Template
    Gen->>DB: Allocate Ports
    Gen->>FS: Create Scaffold
    Gen->>AI: Generate Code
    AI-->>Gen: Code Response
    Gen->>FS: Save Application
    Gen->>DB: Register App
    Celery->>Web: Task Complete
    Web-->>User: Success Notification
```

### Analysis Execution Flow

```mermaid
sequenceDiagram
    participant User
    participant Web as Flask Web
    participant Celery
    participant Orch as Orchestrator
    participant Static
    participant Dynamic
    participant Perf
    participant AI
    participant WS as WebSocket
    participant DB
    
    User->>Web: Analysis Request
    Web->>Celery: Queue Task
    Web-->>User: Task ID
    
    Celery->>Orch: Start Analysis
    
    par Static Analysis
        Orch->>Static: Run Security/Quality
        Static->>WS: Progress Update
        WS-->>User: Display Progress
        Static-->>Orch: Results
    and Dynamic Analysis
        Orch->>Dynamic: Run Runtime Tests
        Dynamic->>WS: Progress Update
        Dynamic-->>Orch: Results
    and Performance Testing
        Orch->>Perf: Run Load Tests
        Perf->>WS: Progress Update
        Perf-->>Orch: Results
    and AI Review
        Orch->>AI: Run Code Review
        AI->>WS: Progress Update
        AI-->>Orch: Results
    end
    
    Orch->>Orch: Consolidate Results
    Orch->>DB: Save Metadata
    Orch->>FS: Save Full Results
    Celery->>Web: Task Complete
    Web-->>User: Results Available
```

### Real-Time Progress Flow

```mermaid
graph LR
    A[Analyzer Service] -->|WebSocket| B[Gateway :8765]
    B -->|Broadcast| C[Connected Clients]
    C -->|Display| D[User Interface]
    
    E[Task Status] -->|Redis PubSub| F[Celery Workers]
    F -->|Update| A
    
    style A fill:#4CAF50
    style B fill:#FF9800
    style D fill:#2196F3
```

---

## Technology Stack

### Backend

| Technology | Version | Purpose |
|------------|---------|---------|
| **Python** | 3.9+ | Core language |
| **Flask** | 3.0+ | Web framework |
| **SQLAlchemy** | 2.0+ | ORM |
| **Celery** | 5.3+ | Task queue |
| **Redis** | Latest | Cache/broker |
| **PostgreSQL** | 12+ | Production database |
| **SQLite** | 3+ | Development database |

### Frontend

| Technology | Version | Purpose |
|------------|---------|---------|
| **Bootstrap** | 5.3+ | UI framework |
| **HTMX** | 1.9+ | Dynamic updates |
| **Font Awesome** | 6.0+ | Icons |
| **Jinja2** | 3.1+ | Templating |

### Infrastructure

| Technology | Version | Purpose |
|------------|---------|---------|
| **Docker** | Latest | Containerization |
| **Docker Compose** | Latest | Multi-container orchestration |
| **WebSockets** | - | Real-time communication |

### Analysis Tools

| Tool | Language | Purpose |
|------|----------|---------|
| **Bandit** | Python | Security scanning |
| **Safety** | Python | Dependency checking |
| **Pylint** | Python | Code quality |
| **Flake8** | Python | Style checking |
| **ESLint** | JavaScript | JS linting |
| **Radon** | Python | Complexity analysis |
| **Semgrep** | Multi | Pattern matching |
| **OWASP ZAP** | Java | Dynamic security |
| **Locust** | Python | Load testing |
| **Apache Bench** | C | HTTP benchmarking |

---

## Design Patterns

### 1. Factory Pattern

**Used For**: Application creation

```python
def create_app(config_name='default'):
    """Factory function for creating Flask app"""
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    celery.config_from_object(app.config)
    
    # Register blueprints
    from app.routes import dashboard, models, analysis
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(models.bp)
    app.register_blueprint(analysis.bp)
    
    return app
```

### 2. Service Locator

**Used For**: Dependency injection

```python
class ServiceLocator:
    _services = {}
    
    @classmethod
    def register(cls, name, service):
        cls._services[name] = service
    
    @classmethod
    def get(cls, name):
        return cls._services.get(name)

# Usage
ServiceLocator.register('generation', GenerationService())
gen_service = ServiceLocator.get('generation')
```

### 3. Repository Pattern

**Used For**: Data access abstraction

```python
class ApplicationRepository:
    def get_by_id(self, app_id):
        return GeneratedApplication.query.get(app_id)
    
    def get_by_model_and_number(self, model_slug, app_number):
        return GeneratedApplication.query.filter_by(
            model_slug=model_slug,
            app_number=app_number
        ).first()
    
    def list_all(self, filters=None):
        query = GeneratedApplication.query
        if filters:
            query = self._apply_filters(query, filters)
        return query.all()
```

### 4. Strategy Pattern

**Used For**: Model tier selection

```python
def get_model_capability_tier(model_slug: str) -> str:
    """Determine appropriate template tier for model"""
    
    # Strategy 1: Explicit lite list
    if model_slug in KNOWN_LITE_MODELS:
        return 'lite'
    
    # Strategy 2: Parameter count
    model = ModelCapability.query.filter_by(
        canonical_slug=model_slug
    ).first()
    
    if model and model.parameters_billions:
        if model.parameters_billions >= 30:
            return 'standard'
        else:
            return 'lite'
    
    # Strategy 3: Default
    return 'standard'
```

### 5. Observer Pattern

**Used For**: Real-time progress updates

```python
class ProgressObserver:
    def __init__(self, task_id):
        self.task_id = task_id
        self.subscribers = []
    
    def subscribe(self, callback):
        self.subscribers.append(callback)
    
    def notify(self, progress_data):
        for callback in self.subscribers:
            callback(progress_data)

# Usage
observer = ProgressObserver(task_id)
observer.subscribe(websocket_client.send)
observer.notify({"progress": 50, "message": "Halfway done"})
```

---

## Deployment Architecture

### Development Environment

```mermaid
graph TB
    subgraph "Local Machine"
        Flask[Flask Dev Server<br/>:5000]
        Celery[Celery Worker]
        Redis[Redis<br/>:6379]
        DB[(SQLite)]
    end
    
    subgraph "Docker"
        Static[Static Analyzer]
        Dynamic[Dynamic Analyzer]
        Perf[Performance]
        AI[AI Analyzer]
        Gateway[WebSocket Gateway]
    end
    
    Flask --> Celery
    Flask --> Redis
    Flask --> DB
    Celery --> Static
    Celery --> Dynamic
    Celery --> Perf
    Celery --> AI
    Static --> Gateway
    Dynamic --> Gateway
    Perf --> Gateway
    AI --> Gateway
```

### Production Environment

```mermaid
graph TB
    subgraph "Load Balancer"
        LB[Nginx/HAProxy]
    end
    
    subgraph "Application Servers"
        Flask1[Flask + Gunicorn<br/>Instance 1]
        Flask2[Flask + Gunicorn<br/>Instance 2]
        Flask3[Flask + Gunicorn<br/>Instance 3]
    end
    
    subgraph "Worker Pool"
        Worker1[Celery Worker 1]
        Worker2[Celery Worker 2]
        Worker3[Celery Worker 3]
    end
    
    subgraph "Analyzer Cluster"
        Static[Static Analyzer<br/>N instances]
        Dynamic[Dynamic Analyzer<br/>N instances]
        Perf[Performance<br/>N instances]
        AI[AI Analyzer<br/>N instances]
    end
    
    subgraph "Data Services"
        PG[(PostgreSQL<br/>Primary)]
        PGR[(PostgreSQL<br/>Replica)]
        RedisC[Redis Cluster]
        NFS[Shared Storage]
    end
    
    LB --> Flask1
    LB --> Flask2
    LB --> Flask3
    
    Flask1 --> PG
    Flask2 --> PG
    Flask3 --> PG
    
    Flask1 --> RedisC
    Flask2 --> RedisC
    Flask3 --> RedisC
    
    Worker1 --> Static
    Worker1 --> Dynamic
    Worker2 --> Perf
    Worker3 --> AI
    
    PG --> PGR
    
    Flask1 --> NFS
    Flask2 --> NFS
    Flask3 --> NFS
    Worker1 --> NFS
    Worker2 --> NFS
    Worker3 --> NFS
```

---

## Next Steps

- **[Getting Started](GETTING_STARTED.md)** - Setup and installation
- **[Features](features/)** - Detailed feature documentation
- **[Guides](guides/)** - How-to guides
- **[Reference](reference/)** - Technical reference

---

**Last Updated**: October 2025  
**Architecture Version**: 2.0
