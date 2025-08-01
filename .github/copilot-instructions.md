# AI Agent Instructions for Thesis Research App

## Project Overview
This is a Flask-based research platform that analyzes **900+ AI-generated applications** across 30 different AI models. The app manages Docker containers, performs security analysis, runs performance tests, and provides batch processing capabilities through an HTMX-enhanced web interface.

## Core Architecture

### Application Factory Pattern
- **Entry Point**: `src/app.py` - Uses ApplicationFactory pattern with lazy service initialization
- **Service Management**: `src/core_services.py` - Consolidated service classes with thread-safe operations
- **Database Models**: `src/models.py` - SQLAlchemy models for AI models, port configs, and analysis results
- **Web Routes**: `src/web_routes.py` - HTMX-enabled blueprints with ResponseHandler for partial updates

### Key Services (all in `core_services.py`)
- `DockerManager` - Container lifecycle management with project name sanitization
- `BatchAnalysisService` - Threaded job execution with task workers  
- `ScanManager` - Security analysis coordination
- `ModelIntegrationService` - AI model metadata from JSON files

## Critical Development Patterns

### Docker Integration
- **Project Names**: Use `DockerUtils.get_project_name(model, app_num)` for consistent naming
- **Port Allocation**: Models have pre-allocated port ranges from `misc/port_config.json`
- **Container Operations**: Always use operation locks via `DockerUtils.get_operation_lock(project_name)`
- **App Directory Structure**: `misc/models/{model_name}/app{N}/` contains docker-compose.yml files

### HTMX Frontend Architecture
- **Template Structure**: `src/templates/pages/` for full pages, `src/templates/partials/` for HTMX fragments
- **Response Handling**: Use `ResponseHandler.render_response()` to auto-detect HTMX vs full page requests
- **Dynamic Updates**: Container status, analysis results, and batch jobs update via HTMX partials
- **Error Handling**: `src/static/js/errorHandling.js` provides global HTMX error management

### Database & Models
- **JSON Fields**: Use `get_capabilities()`/`set_capabilities()` helpers for complex data in models
- **Migration**: Flask-Migrate is configured; run `flask db migrate` for schema changes
- **Lazy Loading**: Database population happens on first access via `DatabasePopulator`

## Essential Commands

### Development Workflow
```powershell
# Setup (Windows PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Database initialization (if needed)
flask db init
flask db migrate -m "Initial migration"
flask db upgrade

# Run application
python src/app.py
# Access at http://127.0.0.1:5000
```

### Testing & Analysis
```powershell
# Run security analysis tests
python test_cli_analysis.py

# Test frontend integration
python test_frontend_integration.py

# Run performance tests (if Locust configured)
python -m locust -f src/performance_service.py
```

## Project-Specific Conventions

### Model & App Identification
- **Models**: Identified by slugs like `anthropic_claude-3.7-sonnet` 
- **Apps**: Numbered 1-30 per model (e.g., `app1`, `app2`)
- **Container Names**: Format `{project_name}_{container_type}_{port}`

### Configuration Files
- `misc/model_capabilities.json` - AI model metadata (context length, pricing, features)
- `misc/port_config.json` - Docker port allocations per model/app
- `misc/models_summary.json` - Model display information

### Security Analysis Tools
- **Backend**: bandit, safety, semgrep (Python)
- **Frontend**: ESLint, retire.js, Snyk (JavaScript/React)
- **Integration**: Via `npx` for frontend tools, direct Python imports for backend

### Service Error Handling
- All services inherit from `BaseService` with cleanup methods
- Use `@handle_errors` decorator for consistent API error responses
- Thread-safe operations use `self._lock` (RLock from BaseService)

## Common Gotchas

1. **Model Names**: Contains slashes and special chars - always use `DockerUtils.sanitize_project_name()`
2. **HTMX Partials**: Check `request.headers.get('HX-Request')` to return appropriate template
3. **Container States**: Cache Docker status for 10 seconds to avoid API overload
4. **Batch Jobs**: Use `TaskStatus` and `JobStatus` enums, not strings
5. **JSON Serialization**: Use `CustomJSONEncoder` for datetime/enum handling

## File Structure Priorities
- **Core Logic**: `src/core_services.py` (2500+ lines of consolidated services)
- **Web Interface**: `src/web_routes.py` + `src/templates/`
- **Data Models**: `src/models.py` 
- **Generated Apps**: `misc/models/{model}/app{N}/` (900+ app instances)
- **Analysis Results**: `reports/{model}/app{N}/` directory structure

Focus on the service layer (`core_services.py`) for business logic, use the existing template patterns for UI changes, and always consider Docker container lifecycle management when working with app analysis features.