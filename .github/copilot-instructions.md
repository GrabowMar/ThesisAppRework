# AI Coding Agent Instructions for Thesis Research App

## Project Overview
This is a thesis research application that generates, containerizes, and analyzes AI-generated web applications across multiple models (OpenAI, Anthropic, Google, etc.). The system orchestrates batch operations on containerized apps for security analysis, performance testing, and vulnerability scanning.

## Core Architecture

### Service-Oriented Design with App Factory Pattern
- **Flask App Factory** (`src/app.py`) - Uses ServiceManager pattern with background service initialization
- **Containerized Testing Infrastructure** (`testing-infrastructure/`) - Microservices: security-scanner (8001), performance-tester (8002), zap-scanner (8003)
- **Batch Operations Service** (`src/batch_testing_service.py`) - ContainerBatchOperationService with ThreadPoolExecutor
- **HTMX Frontend** (`src/web_routes.py`) - Dynamic UI with hx-get/hx-post, performance logging decorators
- **Core Services** (`src/core_services.py`) - DockerManager, ScanManager, ModelIntegrationService with graceful degradation

### Critical Service Initialization Pattern
```python
# Services are initialized asynchronously to prevent blocking startup
service_manager = ServiceManager(app)
app.config['service_manager'] = service_manager

# Background thread initializes services with fallbacks
service_thread = threading.Thread(target=initialize_services_async, daemon=True)
```

### Data Flow & Container Orchestration
1. **App Generation**: `misc/generateApps.py` creates ~30 app types per model with docker-compose.yml
2. **Port Allocation**: Sequential backend (5001+) and frontend (8001+) ports per model/app combination
3. **Batch Processing**: ContainerBatchOperationService orchestrates concurrent operations (4 workers default)
4. **Analysis Pipeline**: Security → Performance → ZAP scanning via containerized microservices
5. **Results Storage**: SQLAlchemy with AnalysisStatus/JobStatus enums, graceful error handling

## Critical Development Patterns

### Docker Container Naming & Project Management
```python
# Always use DockerUtils for consistent naming
project_name = DockerUtils.get_project_name(model, app_num)  # "modelname_app1"
container_name = f"{project_name}_{container_type}"  # "modelname_app1_backend"

# Execute compose commands with proper project isolation
docker_manager.execute_compose_command(compose_path, ["up", "-d"], model, app_num)
```

### Service Locator Pattern with Fallback Chain
```python
# ServiceLocator provides graceful degradation
service = ServiceLocator.get_service('scan_manager')
if not service:
    # Falls back to mock clients when containers unavailable
    return legacy_implementation()
```

### HTMX Request Patterns
```html
<!-- Use hx-target and hx-swap for partial updates -->
<button hx-post="/api/containers/{{ model }}/{{ app_num }}/start"
        hx-target="#app-{{ model }}-{{ app_num }}"
        hx-swap="outerHTML">Start</button>

<!-- Auto-refresh with triggers -->
<div hx-get="/api/status/{{ model }}/{{ app_num }}"
     hx-trigger="load, every 15s"
     hx-swap="innerHTML">
```

### Thread-Safe Batch Operations
```python
# Always use operation locks for batch processing
with self.operation_lock:
    operation_id = str(uuid.uuid4())
    self.operations[operation_id] = operation_data

# Use ThreadPoolExecutor with configurable concurrency
executor = ThreadPoolExecutor(max_workers=operation['concurrency'])
```

## Essential Commands & Infrastructure

### Containerized Testing Infrastructure
```powershell
# Start all testing microservices
cd testing-infrastructure
python manage.py build    # Build all containers
python manage.py start    # Start infrastructure (ports 8001-8003)
python manage.py status   # Check service health

# Individual service management
python manage.py restart security-scanner
python manage.py logs performance-tester
```

### Development Workflow
```powershell
# Initialize and run main application
cd src
python app.py  # Uses app factory, auto-initializes services

# Generate AI applications from templates
python misc/generateApps.py  # Creates containerized apps for all models

# Database operations
flask db upgrade  # Apply migrations
flask db init     # Initialize migrations (if needed)

# Testing
pytest tests/ -v                    # Full test suite
pytest tests/test_containerized_services.py  # Container integration tests
```

## Model Integration & Template System

### App Generation Architecture
- **Templates**: `misc/app_templates/app_{1-30}_{backend|frontend}.md` define 30 distinct app types
- **Generated Structure**: `misc/models/{model_slug}/app{1-30}/docker-compose.yml`
- **Port Configuration**: Auto-generated in `misc/port_config.json` with conflict resolution
- **Model Metadata**: `misc/models_summary.json` with capabilities, pricing, context windows

### Container Lifecycle Management
```python
# Standard container operations pattern
docker_manager = get_docker_manager()
result = docker_manager.start_containers(compose_path, model, app_num)
if result['success']:
    # Wait for health check before proceeding
    healthy = docker_manager._wait_for_container_health(container_name, timeout=60)
```

## Database Models & Status Management

### Key Models with Status Tracking
```python
# Use proper enums for consistent state management
class AnalysisStatus(enum.Enum):
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

# Models include JSON fields for extensibility
model_capability.set_capabilities({'supports_vision': True, 'context_window': 128000})
```

### Critical Model Relationships
- **ModelCapability**: AI model metadata with capabilities_json field
- **PortConfiguration**: Model/app → port mappings with availability tracking
- **GeneratedApplication**: App instances with container_status tracking
- **SecurityAnalysis/PerformanceTest**: Results with tool-specific boolean flags

## Error Handling & Resilience

### Graceful Service Degradation
```python
# All services include fallback mechanisms
try:
    return containerized_service.analyze(model, app_num)
except Exception:
    logger.warning("Containerized service unavailable, using fallback")
    return legacy_analyzer.analyze(model, app_num)
```

### Container Health & Timeout Management
- **Health Checks**: All containers expose `/health` endpoints
- **Timeouts**: 60s for container operations, 300s for builds, 30s for API calls
- **Retry Logic**: 3 attempts with exponential backoff for container operations
- **Cache Strategy**: 10-second container status cache to reduce Docker API calls

## Testing Strategy

### Test Infrastructure
- **conftest.py**: SQLite in-memory database with realistic fixtures
- **Mock Services**: TestingInfrastructureClasses provides fallback mocks
- **Container Tests**: `test_containerized_services.py` validates microservice integration
- **HTMX Testing**: Uses test_client with htmx_headers fixture for partial rendering

### Integration Testing Patterns
```python
# Test both success and failure paths
def test_container_operation_with_fallback(mock_docker_manager):
    mock_docker_manager.client = None  # Simulate Docker unavailable
    result = service.run_analysis(model, app_num)
    assert result['status'] == 'fallback_used'
```

## Performance & Monitoring

### Caching & Optimization
- **DockerCache**: Caches container statuses with TTL to reduce API calls
- **Service Manager**: Lazy initialization of heavy services (Docker, scan tools)
- **HTMX**: Reduces full page reloads, uses targeted partial updates
- **Background Tasks**: Service initialization and long-running operations run in daemon threads

### Resource Management
- **Concurrency Limits**: Default 4 workers for batch operations, configurable via BATCH_MAX_WORKERS
- **Memory Constraints**: Each testing container limited to 512MB via docker-compose
- **Connection Pooling**: SQLAlchemy connection pooling with 300s recycle time

## Critical Integration Points

When working with this codebase, always consider:

1. **Container Dependencies**: Check if testing infrastructure is running before using analysis features
2. **Service Boundaries**: Main app coordinates, containers do the work, results flow back via API
3. **State Consistency**: Use proper enum values and status tracking across all operations
4. **HTMX Patterns**: Maintain hx-target/hx-swap consistency for UI updates
5. **Port Conflicts**: Verify port availability before starting new containers
6. **Graceful Degradation**: Always provide fallback when containerized services unavailable
