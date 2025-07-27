# Copilot Instructions - Thesis Research App

## Project Overview
This is a Flask-based research application for analyzing AI-generated applications across multiple models. The system manages thousands of generated apps (30+ per model), performs security analysis, and provides comparative insights through Docker containerization and automated testing.

## Core Architecture

### Application Structure
- **Main app**: `src/app.py` - Factory pattern with extension initialization
- **Models**: `src/models.py` - SQLAlchemy models with JSON field helpers and enums
- **Services**: `src/services/` - Business logic layer with unified IntegrationService
- **Routes**: `src/routes/` - Blueprint-based with HTMX endpoints
- **Templates**: `src/templates/` - Jinja2 with component-based organization

### Key Design Patterns

**IntegrationService Pattern**: All external operations go through `services/integration_service.py` which coordinates Docker, model lookup, and configuration services. Access via `utils/service_helpers.py`:
```python
from utils.service_helpers import get_integration_service_cached
service = get_integration_service_cached()
```

**JSON Field Helpers**: Models use helper methods for JSON fields:
```python
# Use get_*/set_* methods, not direct JSON access
analysis.set_enabled_tools({'bandit': True, 'safety': False})
tools = analysis.get_enabled_tools()
```

**Enum Status Management**: Use `AnalysisStatus` and `SeverityLevel` enums consistently:
```python
from models import AnalysisStatus, SeverityLevel
analysis.status = AnalysisStatus.RUNNING
issue.severity = SeverityLevel.HIGH
```

## Critical Workflows

### Database Initialization
Always run database setup before development:
```powershell
cd src
python init_db.py  # Creates tables, loads configs, creates sample data
```

## Research Data Architecture

### Generated Application Organization
Each AI model (30 total) generates 30 different application types in this structure:
```
misc/models/{model_name}/app{1-30}/
├── backend/           # Flask API (app.py, requirements.txt, Dockerfile)
├── frontend/          # Vite+React app (src/, package.json, Dockerfile)
└── docker-compose.yml # Container orchestration
```

**Model Examples**: 
- `anthropic_claude-3.7-sonnet/` - Anthropic Claude models
- `openai_gpt-4.1/`, `openai_o3/` - OpenAI models  
- `deepseek_deepseek-chat-v3-0324/` - DeepSeek models
- `google_gemini-2.5-flash/`, `google_gemini-2.5-pro/` - Google models
- `qwen_qwen3-14b/`, `qwen_qwen3-coder/` - Qwen models

**Application Types**: Login system (app1), chat app (app2), feedback system (app3), blog platform (app4), e-commerce cart (app5), note-taking (app6), file upload (app7), forum (app8), CRUD manager (app9), microblog (app10), polling system (app11), reservation system (app12), photo gallery (app13), cloud storage (app14), kanban board (app15), IoT dashboard (app16), fitness tracker (app17), wiki (app18), crypto wallet (app19), mapping app (app20), recipe manager (app21), learning platform (app22), finance tracker (app23), networking tool (app24), health monitor (app25), environment tracker (app26), team management (app27), art portfolio (app28), event planner (app29), research collaboration (app30).

### Port Management System
- **Frontend ports**: Start at 9051, increment by 2 (9053, 9055, ...)
- **Backend ports**: Frontend port - 3000 (6051, 6053, 6055, ...)
- **Pattern**: Each model/app combination gets unique ports from `port_config.json`
- **Docker networking**: Frontend connects to backend via internal Docker network

### Configuration Data
- **`model_capabilities.json`**: Complete OpenRouter API model metadata (2791 lines)
  - 30 models across 13 providers (Anthropic, OpenAI, DeepSeek, Google, Qwen, etc.)
  - Capabilities: context windows, pricing, function calling, vision support
  - Performance metrics: cost efficiency, safety scores
  - Loaded into `ModelCapability` table on app startup
- **`port_config.json`**: Port allocation for 900+ app instances (30 models × 30 apps, 4502 lines)
  - Frontend ports start at 9051, increment by 2 (9053, 9055...)
  - Backend ports are frontend_port - 3000 (6051, 6053, 6055...)
  - Each model/app gets unique port pair for Docker deployment
- **`models_summary.json`**: Additional model metadata and statistics

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

## File Conventions

- **Routes**: Use blueprints with URL prefixes (`/analysis`, `/batch`, `/performance`)
- **Services**: One service per domain, unified through IntegrationService
- **Models**: Include `to_dict()` methods and JSON field helpers
- **Templates**: Component-based in `templates/components/`, layouts in `templates/layouts/`
- **Static Files**: Organized by type in `src/static/`

### Service Access Pattern
Never instantiate services directly in routes. Use the helper pattern:
```python
# In routes
from utils.service_helpers import get_integration_service_cached
service = get_integration_service_cached()
models = service.get_all_models()
```

### HTMX Integration
Many routes return partial HTML for HTMX. Look for `render_template()` calls returning fragments:
```python
@main_bp.route('/dashboard')
def dashboard():
    return render_template('components/dashboard_content.html', **context)
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

### Key Directory Structure

**`misc/` - Research Data & Generation Assets**
- `models/` - **30 AI model folders** (anthropic_claude-3.7-sonnet, deepseek_*, etc.)
  - Each model has `app1/` through `app30/` subdirectories
  - Each app contains `backend/` (Flask API), `frontend/` (Vite+React), `docker-compose.yml`
- `app_templates/` - **60 markdown prompt files** (app_1_backend_login.md, app_1_frontend_login.md, etc.)
  - Templates for 30 different application types (login, chat, blog, etc.)
  - Separate backend/frontend prompts for each app type
- `code_templates/` - Docker templates and scaffolding
  - `docker-compose.yml.template` - Template with port placeholders
  - `backend/`, `frontend/` - Base Dockerfile templates
- `model_capabilities.json` - **2791 lines** of model metadata (context windows, pricing, features)
- `port_config.json` - **4502 lines** of port mappings for all model/app combinations
- `generateApps.py` - **701 lines** - Application generation orchestrator
- `combined.py` - **6958 lines** - GUI for code generation and extraction

**`src/` - Flask Application Core**
- `app.py` - Factory pattern app creation, extension initialization
- `models.py` - SQLAlchemy models with JSON field helpers (400+ lines)
- `config.py` - Multi-environment configuration with tool settings
- `init_db.py` - Database initialization and sample data creation
- `extensions.py` - Flask extension instances (db, migrate, cache)
- `data/thesis_app.db` - SQLite database file
- `routes/` - Blueprint modules (7 files: main, analysis, batch, performance, zap, config, docker_integration_example)
- `services/` - Business logic layer (10 service files including integration_service.py)
- `templates/` - Jinja2 templates (base.html, components/, layouts/, pages/, partials/, errors/)
- `utils/` - Helper functions (service_helpers.py for service access, helpers.py for utilities)
- `logs/` - Application logs (rotating, thesis_app.log)

## Testing Patterns

### Analysis Testing
Security analysis involves multiple tools (bandit, safety, pylint, eslint). Test with:
```python
# Create analysis with proper tool configuration
analysis.set_enabled_tools({
    'backend': {'bandit': True, 'safety': True},
    'frontend': {'eslint': True, 'npm_audit': True}
})
```

### Docker Integration
Applications are containerized. The IntegrationService handles Docker operations:
```python
service = get_integration_service_cached()
status = service.get_container_status(model_slug, app_number)
```

## Common Gotchas

1. **Service Initialization**: IntegrationService requires app_root_path and models_base_dir. Check `app.py` initialization.

2. **JSON Field Access**: Always use helper methods (`get_*`/`set_*`) for JSON fields in models.

3. **Database Context**: Configuration loading happens in app context. Ensure `db.create_all()` is called first.

4. **Port Management**: Generated apps use predictable port patterns (frontend = backend + 3000). Check `PortConfiguration` model.

5. **Analysis State**: Always check `AnalysisStatus` before operations. Running analyses can't be modified.

6. **Template Context**: Service helpers are injected into templates via `inject_template_vars()` in `app.py`.

## Service Layer Architecture

### Services Directory (`src/services/`)
- **`integration_service.py`** - Main coordinator for all external operations
- **`docker_service.py`** - Docker container management (start/stop/status)
- **`docker_operations_service.py`** - Advanced Docker operations  
- **`model_lookup_service.py`** - AI model metadata and port lookups
- **`analysis_service.py`** - Security analysis orchestration
- **`batch_service.py`** - Queue-based batch analysis processing
- **`performance_service.py`** - Load testing and performance metrics
- **`zap_service.py`** - OWASP ZAP security scanning
- **`config_loader_service.py`** - Configuration file loading into database
- **`model_service.py`** - Model CRUD operations

### Routes Directory (`src/routes/`)
- **`main.py`** - Dashboard, home page, HTMX endpoints
- **`analysis.py`** - Security analysis workflows (/analysis)
- **`batch.py`** - Batch processing management (/batch)
- **`performance.py`** - Performance testing (/performance)  
- **`zap.py`** - ZAP security scanning (/zap)
- **`config.py`** - Configuration management (/config)
- **`docker_integration_example.py`** - Docker integration examples

### Template Organization (`src/templates/`)
- **`components/`** - Reusable UI components (navbar, sidebar, breadcrumbs, modals)
- **`layouts/`** - Base layouts and page structures
- **`pages/`** - Complete page templates
- **`partials/`** - HTMX partial templates
- **`errors/`** - HTTP error pages (404, 500, etc.)

## Integration Points

- **Docker**: All generated apps are containerized with docker-compose
- **Security Tools**: bandit, safety, pylint, eslint, npm_audit, snyk (optional)
- **ZAP Scanner**: For security scanning of running applications  
- **Performance Testing**: Custom load testing with configurable parameters
- **Batch Processing**: Queue-based analysis of multiple model/app combinations

## Common Gotchas

1. **Service Initialization**: IntegrationService requires app_root_path and models_base_dir. Check `app.py` initialization.

2. **JSON Field Access**: Always use helper methods (`get_*`/`set_*`) for JSON fields in models.

3. **Database Context**: Configuration loading happens in app context. Ensure `db.create_all()` is called first.

4. **Port Management**: Generated apps use predictable port patterns (frontend = backend + 3000). Check `PortConfiguration` model.

5. **Analysis State**: Always check `AnalysisStatus` before operations. Running analyses can't be modified.

6. **Template Context**: Service helpers are injected into templates via `inject_template_vars()` in `app.py`.

7. **Model Directory Structure**: Each model/app follows exact naming: `misc/models/{canonical_slug}/app{number}/`

8. **Docker Template Variables**: Use exact placeholder names `{backend_port}`, `{frontend_port}`, `{model_prefix}` in templates

This is a research-focused application dealing with large-scale AI model comparison, so expect operations on thousands of generated applications with complex analysis pipelines.
