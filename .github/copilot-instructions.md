# ThesisAppRework - AI Assistant Instructions

## Project Overview
Flask-based web application for researching and testing AI models with HTMX frontend. The system analyzes model-generated web applications stored in `misc/models/` and communicates with containerized testing infrastructure via API contracts.

## ⚠️ CRITICAL: Database First, Not JSON
**ALWAYS use SQLAlchemy models from `src/models.py` for data operations.**
- ❌ DO NOT modify files in `misc/` directory - they are reference data only
- ✅ DO use database queries via SQLAlchemy for all data operations
- ✅ DO check `misc/port_config.json` for port allocations (READ-ONLY)
- ✅ DO reference `misc/models/` for app structure (READ-ONLY)

## Available APIs & Services

### Core Service APIs (via ServiceLocator)
```python
from src.service_manager import ServiceLocator

# Available services - USE THESE:
docker_manager = ServiceLocator.get_docker_manager()
scan_manager = ServiceLocator.get_scan_manager()
model_service = ServiceLocator.get_model_service()
port_manager = ServiceLocator.get_port_manager()
batch_service = ServiceLocator.get_batch_service()
```

### Web API Endpoints (HTMX)
All endpoints return HTML fragments for HTMX, NOT JSON:
- `GET /` - Dashboard
- `GET /models` - Models overview
- `GET /models/<model>/apps` - Model's applications
- `GET /app/<model>/<app_num>` - App details
- `POST /app/<model>/<app_num>/start` - Start containers
- `POST /app/<model>/<app_num>/stop` - Stop containers
- `GET /app/<model>/<app_num>/logs` - Container logs (HTML fragment)
- `POST /batch/start` - Start batch analysis
- `GET /batch/<batch_id>/status` - Batch status (HTML fragment)
- `POST /analysis/security/<model>/<app_num>` - Run security scan
- `POST /analysis/performance/<model>/<app_num>` - Run performance test

### Database Models (USE THESE, NOT JSON)
```python
from src.models import (
    ModelCapability,        # AI model metadata
    PortConfiguration,      # Port allocations
    GeneratedApplication,   # App instances
    SecurityAnalysis,       # Security results
    PerformanceTest,       # Performance results
    BatchAnalysis,         # Batch jobs
    ContainerizedTest      # Container test tracking
)

# Example: Query models from database
with get_session() as session:
    models = session.query(ModelCapability).filter_by(provider='anthropic').all()
    app = session.query(GeneratedApplication).filter_by(
        model_slug='anthropic_claude-3.7-sonnet',
        app_number=1
    ).first()
```

## Testing Tools & Infrastructure

### Unified CLI Analyzer (`src/unified_cli_analyzer.py`)
Primary testing interface that orchestrates all analysis:
```python
from src.unified_cli_analyzer import UnifiedCLIAnalyzer

analyzer = UnifiedCLIAnalyzer()
# Provides batch operations and testing coordination
```

### Containerized Testing Services
Located in `testing-infrastructure/containers/`:
- **security-scanner**: Bandit, Safety, PyLint, ESLint, npm audit
- **performance-tester**: Locust-based load testing
- **zap-scanner**: OWASP ZAP security scanning
- **ai-analyzer**: OpenRouter-based code analysis

### API Contracts (Pydantic Models)
```python
from testing_infrastructure.shared.api_contracts.testing_api_models import (
    TestRequest,
    TestResponse,
    SecurityTestRequest,
    PerformanceTestRequest
)
```

## Architecture & Key Components

### Core Application (MVC-ish Pattern)
- **Entry**: `src/app.py` - Flask app with service initialization
- **Routes**: `src/web_routes.py` - HTMX endpoints returning HTML
- **Services**: `src/core_services.py` - Business logic
- **Service Manager**: `src/service_manager.py` - Service registry & locator
- **Models**: `src/models.py` - SQLAlchemy database models
- **Database**: SQLite in `src/data/thesis_app.db`

### Model Management (`misc/` - READ ONLY!)
- Apps in `misc/models/{provider}_{model_name}/app{1-30}/`
- Port config: `misc/port_config.json` - READ for port lookups
- Each app has: `backend/`, `frontend/`, `docker-compose.yml`

## Development Patterns

### HTMX + Flask Pattern
```python
# CORRECT: Return HTML fragments for HTMX
@web_routes.route('/analysis/status/<id>')
def get_status(id):
    analysis = db.session.query(SecurityAnalysis).get(id)
    return render_template('partials/analysis_status.html', analysis=analysis)

# WRONG: Don't return JSON to HTMX endpoints
# return jsonify({"status": "complete"})  # ❌
```

### Service Access Pattern
```python
# CORRECT: Use ServiceLocator
from src.service_manager import ServiceLocator

docker_manager = ServiceLocator.get_docker_manager()
if docker_manager:
    containers = docker_manager.list_containers()

# WRONG: Don't create services directly
# docker_manager = DockerManager()  # ❌
```

### Database Pattern
```python
# CORRECT: Use database models with context managers
from src.extensions import get_session
from src.models import GeneratedApplication

with get_session() as session:
    app = GeneratedApplication(
        model_slug="anthropic_claude-3.7-sonnet",
        app_number=1,
        provider="anthropic"
    )
    session.add(app)
    session.commit()

# WRONG: Don't modify JSON files
# with open('misc/some_file.json', 'w') as f:  # ❌
```

## Critical Workflows

### Starting Analysis (Windows)
```bash
# Main app
python src/app.py

# Testing infrastructure (optional, for containerized tests)
cd testing-infrastructure
docker-compose up
```

### Running Tests
```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests (requires infrastructure)
pytest tests/integration/ -v
```

## File Structure Rules
- **Constants**: `src/constants.py` - Enums and constants
- **Static**: `src/static/js/` - HTMX extensions, error handling
- **Templates**: `templates/partials/` - HTMX fragments
- **Model apps**: READ ONLY from `misc/models/`

## Windows-Specific Notes
- Use `pathlib.Path` for file operations
- Check ports in database (PortConfiguration model)
- Handle SQLite locks with proper session management

## Common Pitfalls & Solutions

### ❌ DON'T:
1. Return JSON to HTMX endpoints - return HTML fragments
2. Modify files in `misc/` - they're reference data
3. Hardcode ports - query PortConfiguration model
4. Create services directly - use ServiceLocator
5. Access JSON files for data - use database models

### ✅ DO:
1. Use database models for all data operations
2. Return HTML fragments from web routes
3. Use ServiceLocator for service access
4. Check existing patterns in codebase
5. Use context managers for database sessions

## Testing Analyzer Integration
When adding analyzers:
1. Define models in `testing_api_models.py`
2. Add service in `core_services.py`
3. Update `service_manager.py`
4. Add container in `testing-infrastructure/containers/`
5. Create database migration if needed

## Key Files Reference
- Port lookups: Check PortConfiguration model (NOT misc/port_config.json)
- Model data: Query ModelCapability model
- App status: Query GeneratedApplication model
- Analysis results: Query SecurityAnalysis, PerformanceTest models
- Service access: `src/service_manager.py` ServiceLocator class
