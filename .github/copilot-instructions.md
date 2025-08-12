# AI Model Analysis Platform - Coding Agent Instructions

This is a Flask-based research platform for analyzing AI-generated web applications across multiple models (GPT, Claude, Gemini, etc.). The system combines web interface management with containerized analysis services.

## 🏗️ Architecture Overview

### Dual Architecture Pattern
- **Web Platform** (`src/`): Flask app with HTMX for managing models, applications, and analysis results
- **Analyzer Services** (`analyzer/`): Containerized microservices for security, performance, and AI-powered analysis

### Service Integration
```python
# Core services communicate via:
from app.services.analyzer_integration import get_analyzer_integration
analyzer = get_analyzer_integration()  # Bridge between Flask and analyzer containers
```

## 🎯 Key Development Patterns

### Service Locator Pattern
```python
# All business logic goes through service locator
from app.services.service_locator import ServiceLocator
model_service = ServiceLocator.get_model_service()
batch_service = ServiceLocator.get_batch_service()
```

### Database Models with JSON Fields
```python
# Core pattern: SQLAlchemy models with JSON storage for flexible data
class SecurityAnalysis(db.Model):
    results_json = db.Column(db.Text)  # Store complex analysis results
    
    def get_results(self) -> Dict[str, Any]:
        return json.loads(self.results_json) if self.results_json else {}
```

### HTMX-Powered Dynamic UI
Templates use HTMX for dynamic updates without page reloads:
```html
<form hx-post="/api/analysis/start" hx-target="#results" hx-indicator="#spinner">
```

## 🚀 Essential Commands

### Development Startup
```bash
cd src
# Full stack (Flask + Celery + Analyzer services)
powershell .\start.ps1 start

# Flask only for UI development
powershell .\start.ps1 flask-only

# Check all service status
powershell .\start.ps1 status
```

### Analyzer Operations
```bash
cd analyzer
# Manage containerized analysis services
python analyzer_manager.py start        # Start all containers
python analyzer_manager.py analyze anthropic_claude-3.7-sonnet 1 security
python analyzer_manager.py batch models.json
```

### Database Operations
```python
# Initialize database (run from src/)
from app.extensions import init_db; init_db()

# CLI app for database operations
from app.factory import create_cli_app
app = create_cli_app()
```

## 📁 Critical File Locations

### Configuration
- `src/config/settings.py` - Environment-specific configs
- `misc/port_config.json` - Dynamic port allocation for 1000+ AI apps
- `misc/model_capabilities.json` - AI model metadata and pricing

### Generated Applications
- `misc/models/{model_name}/app_{number}/` - AI-generated application code
- Port allocation: Backend (5000-7000), Frontend (8000-10000) ranges

### Service Integration Points
- `src/app/services/analyzer_integration.py` - Bridge to analyzer containers
- `analyzer/shared/protocol.py` - WebSocket communication protocol
- `src/app/tasks.py` - Celery integration for async analysis

## 🔧 Project-Specific Conventions

### Model Slug Format
Model identifiers use underscores: `anthropic_claude-3.7-sonnet`, `openai_gpt-4o`

### Analysis Workflow
1. **Web UI**: User selects model/app via Flask routes
2. **Task Queue**: Celery dispatches analysis jobs
3. **Containers**: Analyzer services process via WebSocket
4. **Results**: JSON stored in database, displayed via HTMX

### Port Management
```python
# Port allocation is pre-calculated and stored
# Each model/app gets unique frontend/backend ports
# Backend: 6051, Frontend: 9051 for anthropic_claude-3.7-sonnet app 1
```

### Service Communication
```python
# Analyzer services expose WebSocket endpoints on ports 2001-2005
# Flask app communicates via analyzer_integration service
# Results flow: Container → WebSocket → Celery Task → Database → UI
```

## 🧪 Testing Patterns

### Service Testing
```python
# Test services in isolation
def test_security_service(app):
    security_service = SecurityService()
    result = security_service.start_security_analysis("test_model", 1)
```

### Integration Testing
```python
# Full workflow testing
pytest tests/integration/test_celery_integration.py
```

## 🚨 Important Constraints

### Container Dependencies
- Docker must be running for analyzer services
- Redis required for Celery (auto-started by start.ps1)
- WebSocket connections need proper error handling

### Data Model Relationships
```python
# Generated applications link to multiple analysis types
app = GeneratedApplication.query.filter_by(model_slug="...", app_number=1).first()
security_analyses = app.security_analyses  # One-to-many relationship
```

### Performance Considerations
- Port allocation pre-computed (4500+ entries in port_config.json)
- Analysis results stored as JSON for flexibility
- HTMX prevents full page reloads during long-running analyses

## 🔄 Background Processing

### Celery Integration
```python
# Tasks defined in src/app/tasks.py
from app.tasks import run_security_analysis
task = run_security_analysis.delay(model_slug, app_number)
```

### Task Monitoring
```python
# Check task status via components
components = get_components()
task_manager = components.task_manager
status = task_manager.get_task_status(task_id)
```

## 📊 Data Flow Examples

### Starting Security Analysis
```
User → Flask Route → Celery Task → Analyzer Container → WebSocket → Database → HTMX Update
```

### Batch Processing
```
JSON Config → Batch Service → Multiple Celery Tasks → Parallel Analysis → Aggregated Results
```

Always check `src/PROJECT_STRUCTURE.md` and `docs/DEVELOPMENT.md` for current implementation status and TODOs.