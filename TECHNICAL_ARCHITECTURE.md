# Technical Architecture Documentation

## System Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Web Interface Layer                          │
├─────────────────────────────────────────────────────────────────┤
│ Flask Routes (HTMX) → Service Layer → Database → Containers     │
└─────────────────────────────────────────────────────────────────┘
```

### Component Diagram
```
┌──────────────────┐    ┌───────────────────┐    ┌─────────────────┐
│   Web Frontend   │    │   Service Layer   │    │   Data Layer    │
│                  │    │                   │    │                 │
│ • HTMX Templates │◄──►│ • Service Manager │◄──►│ • SQLite DB     │
│ • Bootstrap UI   │    │ • Core Services   │    │ • JSON Config   │
│ • Real-time      │    │ • CLI Analyzer    │    │ • File Storage  │
│   Updates        │    │                   │    │                 │
└──────────────────┘    └───────────────────┘    └─────────────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │ Container Layer │
                        │                 │
                        │ • Docker Mgmt   │
                        │ • Test Services │
                        │ • API Gateway   │
                        └─────────────────┘
```

## Service Architecture Details

### 1. Service Manager (`src/service_manager.py`)

#### ServiceLocator Pattern Implementation
```python
class ServiceLocator:
    """Centralized service registry and dependency injection."""
    
    @classmethod
    def get_docker_manager(cls) -> Optional[DockerManager]:
        """Get Docker management service."""
        
    @classmethod  
    def get_model_service(cls) -> Optional[ModelIntegrationService]:
        """Get model integration service."""
        
    @classmethod
    def get_batch_service(cls) -> Optional[BatchAnalysisService]:
        """Get batch analysis service."""
```

#### Service Registry
- **Factory Pattern**: Services created on-demand
- **Singleton Behavior**: Single instance per service type
- **Dependency Injection**: Automatic dependency resolution
- **Error Resilience**: Graceful degradation when services unavailable

### 2. Core Services Architecture (`src/core_services.py`)

#### Service Hierarchy
```
CacheableService (Abstract Base)
├── ModelIntegrationService
├── BatchAnalysisService  
├── DockerManager
├── SecurityAnalysisService
├── PerformanceService
├── ZAPService
└── OpenRouterService
```

#### Service Interface Pattern
```python
class CacheableService:
    """Base class for all cacheable services."""
    
    def __init__(self, app=None):
        self.app = app
        self.logger = logging.getLogger(self.__class__.__name__)
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes
        
    def get_cached_data(self, key: str) -> Optional[Any]:
        """Get data from cache with TTL check."""
        
    def set_cached_data(self, key: str, data: Any) -> None:
        """Set data in cache with timestamp."""
        
    def cleanup(self) -> None:
        """Cleanup service resources."""
```

### 3. Database Architecture (`src/models.py`)

#### Entity Relationship Diagram
```
ModelCapability ──┐
                  │
PortConfiguration ├─── GeneratedApplication ───┬─── SecurityAnalysis
                  │                            ├─── PerformanceTest  
                  │                            ├─── ZAPAnalysis
                  │                            ├─── OpenRouterAnalysis
                  │                            └─── ContainerizedTest
                  │
                  └─── BatchAnalysis ───┬─── BatchJob ─── BatchTask
                                        └─── Results Storage
```

#### Model Design Patterns

**Timestamp Management**
```python
def utc_now() -> datetime:
    """UTC timestamp helper - replaces deprecated datetime.utcnow()"""
    return datetime.now(timezone.utc)

# Applied to all models
created_at = db.Column(db.DateTime, default=utc_now)
updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
```

**JSON Field Handling**
```python
class SecurityAnalysis(db.Model):
    enabled_tools = db.Column(db.Text)  # JSON storage
    
    def get_enabled_tools(self) -> List[str]:
        """Parse JSON to list with error handling."""
        if self.enabled_tools:
            try:
                return json.loads(self.enabled_tools)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_enabled_tools(self, tools_list: List[str]) -> None:
        """Set tools list as JSON."""
        self.enabled_tools = json.dumps(tools_list) if tools_list else None
```

**Enum Status Management**
```python
from .constants import AnalysisStatus, JobStatus, TaskStatus

class BatchJob(db.Model):
    status = db.Column(db.Enum(JobStatus), default=JobStatus.PENDING, index=True)
    
    # Consistent status handling across all models
    # PENDING → RUNNING → COMPLETED/FAILED/CANCELLED
```

## Web Architecture (`src/web_routes.py`)

### 1. Blueprint Organization

#### Blueprint Structure
```python
# Core blueprints
main_bp = Blueprint('main', __name__)           # Dashboard, basic pages
api_bp = Blueprint('api', __name__, url_prefix='/api')  # RESTful APIs
testing_bp = Blueprint('testing', __name__, url_prefix='/testing')  # Testing UI

# Specialized blueprints  
batch_bp = Blueprint('batch', __name__, url_prefix='/batch')
analysis_bp = Blueprint('analysis', __name__, url_prefix='/analysis')
statistics_bp = Blueprint('statistics', __name__, url_prefix='/statistics')
```

#### Route Patterns
```python
# HTMX-specific routes return HTML fragments
@testing_bp.route("/api/job/<job_id>/progress")
def get_job_progress(job_id):
    """Return progress HTML fragment for HTMX."""
    return render_template('partials/job_progress.html', job=job)

# API routes return JSON
@api_bp.route("/models")
def api_models():
    """Return JSON list of available models."""
    return jsonify({"models": models_list})
```

### 2. HTMX Integration Architecture

#### Request/Response Flow
```
Browser HTMX Request → Flask Route → Service Layer → Database
                 ←  HTML Fragment ←  Template Render ←  Data
```

#### HTMX Patterns
```html
<!-- Real-time updates with polling -->
<div hx-get="/testing/api/infrastructure-status" 
     hx-trigger="every 5s"
     hx-target="#infrastructure-status">
    Loading...
</div>

<!-- Modal interactions -->
<button hx-get="/testing/api/job/123/results"
        hx-target="#modal-content" 
        data-bs-toggle="modal">
    View Results
</button>

<!-- Form submissions -->
<form hx-post="/testing/api/create-test"
      hx-target="#test-results"
      hx-indicator="#loading">
    <!-- Form fields -->
</form>
```

### 3. Template Architecture

#### Template Hierarchy
```
templates/
├── base.html                    # Base layout with Bootstrap + HTMX
├── dashboard/
│   ├── index.html              # Main dashboard
│   └── stats.html              # Statistics page
├── testing/
│   ├── unified_security_testing.html  # Main testing interface
│   └── partials/               # HTMX fragments
│       ├── test_jobs_list.html
│       ├── job_progress.html
│       ├── job_results.html
│       ├── job_logs.html
│       ├── infrastructure_status.html
│       └── test_form_modal.html
├── analysis/
│   ├── security_results.html
│   ├── performance_results.html
│   └── batch_results.html
└── components/
    ├── modals/
    ├── forms/
    └── tables/
```

#### Template Patterns
```html
<!-- Base template structure -->
<!DOCTYPE html>
<html>
<head>
    <title>{% block title %}Thesis Research App{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
</head>
<body>
    {% block content %}{% endblock %}
    {% block scripts %}{% endblock %}
</body>
</html>

<!-- Partial template for HTMX -->
<div class="card">
    <div class="card-header">Test Job #{{ job.id }}</div>
    <div class="card-body">
        <div class="progress">
            <div class="progress-bar" style="width: {{ job.progress }}%">
                {{ job.progress }}%
            </div>
        </div>
    </div>
</div>
```

## Testing Infrastructure Architecture

### 1. Container Service Architecture

#### Service Mesh Design
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   API Gateway   │    │  Test Services   │    │ Main Flask App  │
│   (Port 8000)   │◄──►│                  │◄──►│   (Port 5000)   │
│                 │    │ • Security:8001  │    │                 │
│ • Authentication│    │ • Performance:02 │    │ • Web Interface │
│ • Rate Limiting │    │ • ZAP:8003       │    │ • Result Storage│
│ • Request Route │    │ • Coordinator:05 │    │ • Job Management│
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

#### Service Communication Pattern
```python
# Request flow from main app to containers
def submit_containerized_test(test_request: TestRequest) -> str:
    """Submit test to appropriate container service."""
    
    # 1. Route to correct service based on test type
    endpoint = get_service_endpoint(test_request.test_type)
    
    # 2. Transform request to container format
    container_request = transform_request(test_request)
    
    # 3. Submit via HTTP API
    response = requests.post(f"{endpoint}/submit", json=container_request)
    
    # 4. Return test ID for tracking
    return response.json()["test_id"]
```

### 2. API Contract Architecture

#### Contract Definition Pattern
```python
# Pydantic models for type safety
from pydantic import BaseModel
from typing import List, Optional
from enum import Enum

class TestType(str, Enum):
    SECURITY_BACKEND = "security_backend"
    SECURITY_FRONTEND = "security_frontend"
    PERFORMANCE = "performance"
    ZAP_SCAN = "zap_scan"

class TestRequest(BaseModel):
    model_name: str
    app_number: int
    test_type: TestType
    configuration: Optional[Dict[str, Any]] = None

class TestResponse(BaseModel):
    test_id: str
    status: str
    message: str
    estimated_duration: Optional[int] = None
```

#### Container Model Compatibility
```python
# Conversion functions maintain compatibility
def convert_testing_status_to_analysis_status(container_status: TestingStatus) -> AnalysisStatus:
    """Convert container status to main app status."""
    mapping = {
        TestingStatus.PENDING: AnalysisStatus.PENDING,
        TestingStatus.RUNNING: AnalysisStatus.RUNNING,
        TestingStatus.COMPLETED: AnalysisStatus.COMPLETED,
        TestingStatus.FAILED: AnalysisStatus.FAILED,
        TestingStatus.TIMEOUT: AnalysisStatus.FAILED  # Timeout maps to failed
    }
    return mapping.get(container_status, AnalysisStatus.FAILED)
```

## Data Flow Architecture

### 1. Test Execution Flow

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   User Action   │    │   Job Creation  │    │  Test Execution │
│                 │    │                 │    │                 │
│ • Select Model  │───►│ • Validate      │───►│ • Route to      │
│ • Choose Tools  │    │ • Create Job    │    │   Container     │
│ • Configure     │    │ • Store Config  │    │ • Execute Tools │
│ • Submit        │    │ • Queue Tasks   │    │ • Collect Results│
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Progress Update │    │ Result Storage  │    │ User Interface  │
│                 │    │                 │    │                 │
│ • Status Check  │◄───│ • Parse Results │◄───│ • View Progress │
│ • Progress %    │    │ • Store in DB   │    │ • View Results  │
│ • ETA Calc      │    │ • Update Status │    │ • Export Data   │
│ • Notifications │    │ • Trigger UI    │    │ • Download Logs │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 2. Data Persistence Strategy

#### Layered Storage Approach
```
┌─────────────────────────────────────────────────────────────────┐
│                     Application Layer                          │
├─────────────────────────────────────────────────────────────────┤
│                     Service Layer                              │
├─────────────────────────────────────────────────────────────────┤
│    Database Layer     │    File System     │   Cache Layer    │
│                       │                    │                  │
│ • SQLite Database     │ • Model Apps       │ • In-Memory      │
│ • Structured Data     │ • Log Files        │ • Service Cache  │
│ • Relationships       │ • Export Files     │ • Query Cache    │
│ • Transactions        │ • Static Assets    │ • Session Data   │
└─────────────────────────────────────────────────────────────────┘
```

#### Data Consistency Patterns
```python
# Transaction management
@db.session.begin():
    # Create job
    job = BatchJob(name="Security Analysis", status=JobStatus.PENDING)
    db.session.add(job)
    db.session.flush()  # Get ID without committing
    
    # Create related tasks
    for model in models:
        task = BatchTask(job_id=job.id, model=model, status=TaskStatus.PENDING)
        db.session.add(task)
    
    # Commit all or none
    db.session.commit()
```

## Performance Architecture

### 1. Caching Strategy

#### Multi-Level Caching
```python
class CacheManager:
    """Multi-level cache implementation."""
    
    def __init__(self):
        self.memory_cache = {}          # L1: In-memory (fastest)
        self.redis_cache = None         # L2: Redis (shared)
        self.database_cache = {}        # L3: Database queries
        
    def get(self, key: str) -> Optional[Any]:
        # Try L1 first
        if key in self.memory_cache:
            return self.memory_cache[key]
            
        # Try L2 if available
        if self.redis_cache:
            value = self.redis_cache.get(key)
            if value:
                self.memory_cache[key] = value  # Promote to L1
                return value
                
        # Try L3 (database)
        return self._database_lookup(key)
```

#### Service-Level Caching
```python
class ModelIntegrationService(CacheableService):
    """Cached model service."""
    
    def get_all_models(self) -> List[AIModel]:
        """Get models with caching."""
        cache_key = "all_models"
        
        # Check cache first
        cached_models = self.get_cached_data(cache_key)
        if cached_models:
            return cached_models
            
        # Load from database
        models = self._load_models_from_db()
        
        # Cache the result
        self.set_cached_data(cache_key, models)
        return models
```

### 2. Database Optimization

#### Query Optimization Patterns
```python
# Eager loading to prevent N+1 queries
def get_job_with_tasks(job_id: int) -> BatchJob:
    return BatchJob.query.options(
        joinedload(BatchJob.tasks),
        joinedload(BatchJob.analysis_results)
    ).filter_by(id=job_id).first()

# Index strategy for performance
class BatchJob(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.Enum(JobStatus), index=True)      # Query by status
    created_at = db.Column(db.DateTime, index=True)         # Time-based queries
    model_name = db.Column(db.String(100), index=True)      # Filter by model
```

#### Connection Management
```python
# Context manager for automatic cleanup
from src.extensions import get_session

def get_analysis_results(job_id: int) -> List[Dict]:
    with get_session() as session:
        # Session automatically cleaned up
        results = session.query(SecurityAnalysis).filter_by(
            batch_job_id=job_id
        ).all()
        return [result.to_dict() for result in results]
```

## Security Architecture

### 1. Input Validation

#### Request Validation Pipeline
```python
from pydantic import BaseModel, validator
from typing import List

class TestCreationRequest(BaseModel):
    model_name: str
    app_number: int
    tools: List[str]
    
    @validator('model_name')
    def validate_model_name(cls, v):
        # Whitelist validation
        allowed_patterns = [r'^[a-zA-Z0-9_-]+$']
        if not any(re.match(pattern, v) for pattern in allowed_patterns):
            raise ValueError('Invalid model name format')
        return v
    
    @validator('app_number')
    def validate_app_number(cls, v):
        if not 1 <= v <= 30:
            raise ValueError('App number must be between 1 and 30')
        return v
    
    @validator('tools')
    def validate_tools(cls, v):
        allowed_tools = ['bandit', 'safety', 'pylint', 'eslint', 'npm-audit']
        invalid_tools = set(v) - set(allowed_tools)
        if invalid_tools:
            raise ValueError(f'Invalid tools: {invalid_tools}')
        return v
```

### 2. Container Security

#### Isolation Strategy
```yaml
# docker-compose.yml security configuration
version: '3.8'
services:
  security-scanner:
    image: thesis-security-scanner
    networks:
      - thesis-network
    environment:
      - PYTHONPATH=/app
    read_only: true
    tmpfs:
      - /tmp
    cap_drop:
      - ALL
    cap_add:
      - DAC_OVERRIDE  # Only for file analysis
    security_opt:
      - no-new-privileges:true
```

## Monitoring & Observability

### 1. Logging Architecture

#### Structured Logging Pattern
```python
import logging
import json
from datetime import datetime

class StructuredLogger:
    """Structured logging for better observability."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        
    def log_event(self, level: str, event: str, **kwargs):
        """Log structured event."""
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': level,
            'event': event,
            'service': self.logger.name,
            **kwargs
        }
        
        self.logger.info(json.dumps(log_data))

# Usage
logger = StructuredLogger('BatchService')
logger.log_event('info', 'job_created', job_id=123, model='claude-3')
```

### 2. Health Monitoring

#### Service Health Checks
```python
class HealthMonitor:
    """Monitor system health across all components."""
    
    def get_system_health(self) -> Dict[str, Any]:
        return {
            'database': self._check_database(),
            'services': self._check_services(),
            'containers': self._check_containers(),
            'storage': self._check_storage(),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _check_database(self) -> Dict[str, Any]:
        try:
            with get_session() as session:
                session.execute('SELECT 1')
                return {'status': 'healthy', 'response_time': '< 10ms'}
        except Exception as e:
            return {'status': 'unhealthy', 'error': str(e)}
```

This technical architecture provides the foundation for a robust, scalable, and maintainable AI model testing framework with clear separation of concerns and well-defined interfaces between components.
