# Development Guide

## Getting Started

### Prerequisites

- Python 3.8+
- Virtual environment tool (venv, virtualenv, or conda)
- Docker (for analyzer services)

### Installation

1. **Clone the repository**
   ```bash
   cd src2
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize database**
   ```bash
   python run.py
   ```

### Project Structure

```
src2/
├── app/                    # Core application code
│   ├── models/            # SQLAlchemy database models
│   ├── routes/            # Flask route handlers
│   ├── services/          # Business logic services
│   ├── utils/             # Utility functions
│   ├── templates/         # Jinja2 HTML templates
│   └── static/            # CSS, JavaScript, assets
├── config/                # Configuration files
├── data/                  # Database files
├── tests/                 # Test suite
└── docs/                  # Documentation
```

## Development Workflow

### 1. Database Models

All data operations use SQLAlchemy models in `app/models/`:

```python
from app.models import ModelCapability, GeneratedApplication

# Query models
models = ModelCapability.query.all()
app = GeneratedApplication.query.filter_by(model_slug='...')
```

### 2. Services

Business logic is organized in services (`app/services/`):

```python
from app.services.service_locator import ServiceLocator

model_service = ServiceLocator.get_model_service()
models = model_service.get_all_models()
```

### 3. Routes

Routes return HTML fragments for HTMX, not JSON:

```python
@models_bp.route('/<model_slug>/apps')
def model_apps(model_slug):
    apps = model_service.get_model_apps(model_slug)
    return render_template('components/app_list.html', apps=apps)
```

### 4. Templates

Use Jinja2 templates with HTMX:

```html
<div hx-get="/models/{{ model_slug }}/apps" 
     hx-target="#app-list" 
     hx-trigger="load">
  Loading...
</div>
```

## Key Principles

### Database First
- ❌ **DON'T**: Modify JSON files in `misc/` directory
- ✅ **DO**: Use SQLAlchemy models for all data operations

### HTMX Frontend
- ❌ **DON'T**: Return JSON from web routes
- ✅ **DO**: Return HTML fragments for HTMX

### Service Architecture
- ❌ **DON'T**: Create services directly in routes
- ✅ **DO**: Use ServiceLocator pattern

### External Integration
- ❌ **DON'T**: Hardcode file paths or ports
- ✅ **DO**: Use configuration and database models

## Testing

### Unit Tests
```bash
pytest tests/unit/ -v
```

### Integration Tests
```bash
pytest tests/integration/ -v
```

### Coverage
```bash
pytest --cov=app tests/
```

## Debugging

### Database Inspection
```bash
# SQLite CLI
sqlite3 data/thesis_app.db
.tables
.schema model_capabilities
```

### Logging
Logs are written to `logs/app.log`. Adjust log level in configuration:

```python
LOG_LEVEL = 'DEBUG'  # INFO, WARNING, ERROR
```

## Common Tasks

### Adding a New Model
1. Add to `misc/model_capabilities.json`
2. Run data sync (will be implemented)
3. Model appears in database automatically

### Adding a New Service
1. Create service class in `app/services/`
2. Register in `ServiceLocator._register_core_services()`
3. Use via `ServiceLocator.get_service_name()`

### Adding a New Route
1. Create blueprint in `app/routes/`
2. Register blueprint in `app/__init__.py`
3. Add templates in `app/templates/`

### Adding Analysis Types
1. Define database models for results
2. Create analyzer service methods
3. Add routes for triggering analysis
4. Create templates for displaying results

## External Dependencies

### Analyzer Services
- Located in `../analyzer/` directory
- Communicate via WebSocket/HTTP
- Services: security-scanner, performance-tester, ai-analyzer

### Model Data
- Located in `../misc/` directory (read-only)
- Port configurations in database
- Generated apps in `../misc/models/`

## Deployment

### Development
```bash
python run.py
```

### Production
Use a proper WSGI server:
```bash
gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()"
```
