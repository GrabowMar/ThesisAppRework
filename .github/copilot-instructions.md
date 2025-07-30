# Copilot Instructions - Thesis Research App

## Project Overview
This is a Flask research application for analyzing AI-generated applications across 30+ models. The system manages 900+ generated apps (30 per model), performs security analysis, and provides comparative insights through Docker containerization and automated testing.

## Core Architecture

### Factory Pattern Application Structure
- **Factory**: `src/app.py` - Flask factory with background service initialization
- **Consolidated Services**: `src/core_services.py` - Single 6000+ line file containing all service classes
- **Database Models**: `src/models.py` - SQLAlchemy models with JSON field helpers and enums  
- **Web Routes**: `src/web_routes.py` - HTMX-powered routes in single 4800+ line file
- **Templates**: `src/templates/` - Jinja2 with component-based organization

### Critical Service Architecture Patterns

**ServiceManager Pattern**: All services are managed through `ServiceManager` and initialized via `ServiceInitializer`:
```python
# Services registered at app startup via ServiceManager
service_manager = ServiceManager(app)
service_initializer = ServiceInitializer(app, service_manager)
service_initializer.initialize_all()
```

**JSON Field Helpers**: Models use helper methods for JSON fields - never access directly:
```python
# Use get_*/set_* methods, not direct JSON access
analysis.set_enabled_tools({'bandit': True, 'safety': False})
tools = analysis.get_enabled_tools()
```

**Enum Status Management**: Use consistent enums from `models.py`:
```python
from models import AnalysisStatus, SeverityLevel
analysis.status = AnalysisStatus.RUNNING
issue.severity = SeverityLevel.HIGH
```

## Critical Workflows

### Application Startup Sequence
1. **Database Context**: Must run inside `with app.app_context()`
2. **Background Services**: Heavy services initialize in background threads
3. **Essential Services**: Batch service initializes synchronously as fallback

### Docker Container Management
```bash
# Development setup
cd src && python app.py  # Starts Flask app with background service initialization

# All Docker operations go through DockerManager in core_services.py
docker_manager.start_containers(compose_path, model, app_num)
docker_manager.stop_containers(compose_path, model, app_num) 
docker_manager.restart_containers(compose_path, model, app_num)
```

## Research Data Architecture

### Generated Application Organization
Each AI model generates 30 application types in `misc/models/{model_slug}/app{1-30}/`:
```
misc/models/anthropic_claude-3-sonnet/app1/
├── backend/           # Flask API + Dockerfile
├── frontend/          # Vite+React + Dockerfile  
└── docker-compose.yml # Port-configured orchestration
```

### Port Management System
- **Port calculation**: Frontend = 9000 + (app_num * 10), Backend = 6000 + (app_num * 10)
- **Docker projects**: Sanitized to `{model_slug}_app{num}` format
- **Port conflicts**: Resolved via `stop_conflicting_containers()` before startup

### Configuration Data Files (misc/)
- **`model_capabilities.json`** (2791 lines): OpenRouter model metadata → `ModelCapability` table
- **`port_config.json`** (4502 lines): Port mappings → `PortConfiguration` table  
- **`models_summary.json`**: Additional model statistics for UI display

## Application Generation System

### Generation Scripts (`misc/`)
- **`generateApps.py`** - Main orchestrator (701 lines)
  - Creates directory structures for all model/app combinations
  - Manages port allocation and Docker configuration
  - Handles template substitution and file creation
- **`combined.py`** - GUI application (6958 lines)  
  - OpenRouter API integration for code generation
  - Template-based prompt management
  - Automatic code extraction and file organization
  - Progress tracking and logging

### Template System (`misc/app_templates/`)
**60 prompt templates** for 30 application types, each with backend/frontend versions:
- `app_1_backend_login.md` / `app_1_frontend_login.md` - Authentication system
- `app_2_backend_chat.md` / `app_2_frontend_chat.md` - Real-time chat
- `app_4_backend_blog.md` / `app_4_frontend_blog.md` - Blog platform
- `app_15_backend_kanban.md` / `app_15_frontend_kanban.md` - Task boards
- ...and 26 more application types

### Docker Templates (`misc/code_templates/`)
- **`docker-compose.yml.template`** - Port placeholders ({backend_port}, {frontend_port})
- **`backend/Dockerfile`** - Flask app containerization
- **`frontend/Dockerfile`** - Vite+React containerization
- Template substitution system for multi-app deployment

## File Architecture & Conventions

### Service Access Pattern (Critical)
Never instantiate services directly. Use ServiceManager pattern from `core_services.py`:
```python
# From routes - get service via helper functions
from web_routes import get_docker_manager, get_scan_manager
docker_manager = get_docker_manager()
scan_manager = get_scan_manager()

# Services are registered at startup via ServiceManager
service_manager = current_app.config.get('service_manager')
docker_manager = service_manager.get_service('docker_manager')
```

### Database Model Patterns
```python
# JSON fields - always use helpers, never direct access
model.set_enabled_tools({'bandit': True})  # ✓ Correct
model.enabled_tools_json = json.dumps({})  # ✗ Wrong

# Enum usage
from models import AnalysisStatus
analysis.status = AnalysisStatus.RUNNING  # ✓ Correct
analysis.status = 'running'               # ✗ Wrong
```

### Docker Container Naming
```python
# Project names are sanitized model slugs
project_name = get_docker_project_name(model, app_num)
# Result: "anthropic_claude_3_sonnet_app1" 

# Container discovery patterns
backend_name = f"{project_name}_backend_{backend_port}"
frontend_name = f"{project_name}_frontend_{frontend_port}"
```

## Development Commands

### Environment Setup
```powershell
# Activate virtual environment (project uses .venv)
.venv\Scripts\Activate.ps1

# Initialize database
cd src
python init_db.py

# Run application
python app.py
```

### Key File Structure (Consolidated Architecture)

**`src/` - Main Application**
- `app.py` - Flask factory with ServiceManager initialization
- `core_services.py` - **All services in one 6000+ line file** (DockerManager, ScanManager, etc.)
- `models.py` - SQLAlchemy models with JSON helpers (ModelCapability, PortConfiguration, etc.)
- `web_routes.py` - **All routes in one 4800+ line file** with HTMX endpoints
- `extensions.py` - Flask extension instances (db, migrate, cache)
- `data/thesis_app.db` - SQLite database

**`misc/` - Research Data & Generation**
- `models/` - **30 AI model directories** each with `app1/` through `app30/` subdirectories
- `generateApps.py` - **701 lines** - Application structure generator
- `model_capabilities.json` - **2791 lines** - OpenRouter model metadata
- `port_config.json` - **4502 lines** - Port mappings for all combinations

### Template Organization
- `base.html` - Main layout with HTMX integration
- `pages/` - Full page templates (dashboard.html, app_details.html, etc.)
- `partials/` - HTMX partial templates for dynamic updates
- `components/` - Reusable UI components

## Critical Patterns & Anti-Patterns

### Service Initialization (Critical)
```python
# ✓ Correct - Services initialize in background threads at startup
with app.app_context():
    service_manager = ServiceManager(app)
    service_initializer = ServiceInitializer(app, service_manager)
    
    # Heavy services run in background thread
    def initialize_services():
        service_initializer.initialize_all()
    threading.Thread(target=initialize_services, daemon=True).start()
```

### Docker Operations (Essential)
```python
# All Docker operations use project-based naming and conflict resolution
project_name = get_docker_project_name(model, app_num)
# Results in: "anthropic_claude_3_sonnet_app1"

# Always cleanup before starting containers
cleanup_success, cleanup_output = stop_conflicting_containers(project_name)
docker_manager.start_containers(compose_path, model, app_num)
```

### JSON Data Handling
```python
# ✓ Always use model helper methods
analysis.set_enabled_tools({'bandit': True, 'safety': False})
capabilities = model.get_capabilities()

# ✗ Never access JSON fields directly
analysis.enabled_tools_json = json.dumps({})  # Wrong!
```

## Common Gotchas

1. **Service Initialization**: Services must initialize within `app.app_context()` - heavy services run in background threads

2. **Docker Project Names**: Use `get_docker_project_name()` for consistent sanitization - container names include ports

3. **Port Management**: Ports calculated as frontend=9000+(app_num*10), backend=6000+(app_num*10) 

4. **Database Context**: All configuration loading happens in app context after `db.create_all()`

5. **Container Conflicts**: Always run `stop_conflicting_containers()` before starting new containers

6. **File Paths**: Generated apps follow exact pattern `misc/models/{canonical_slug}/app{number}/`

This is a research-focused application dealing with large-scale AI model comparison and containerized deployment analysis.

ALWAYS USE WINDOWS POWERSHELL NOT BASH!!!!