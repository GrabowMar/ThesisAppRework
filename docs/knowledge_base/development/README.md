# Development Guide

## Quick Start

```bash
# Clone and setup
git clone <repo-url>
cd ThesisAppRework
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Initialize database
cd src && python init_db.py

# Create admin user
python scripts/create_admin.py

# Start development server
python src/main.py
```

## Project Structure

```
ThesisAppRework/
├── analyzer/              # Analysis microservices
│   ├── services/         # Individual analyzers (static, dynamic, etc.)
│   └── analyzer_manager.py
├── generated/apps/       # AI-generated applications
├── src/
│   ├── app/
│   │   ├── routes/       # Flask blueprints
│   │   ├── services/     # Business logic
│   │   ├── models/       # Database models
│   │   └── tasks/        # Celery tasks
│   └── main.py          # Application entry point
├── scripts/              # Utility scripts
├── tests/                # Test suite
└── docs/                 # Documentation
```

## Key Patterns

### Service Locator
Core services registered in `app/services/service_locator.py`:
```python
from app.services.service_locator import ServiceLocator
service = ServiceLocator.get('service_name')
```

### Factory Pattern
App creation in `src/app/factory.py`:
```python
from app.factory import create_app
app = create_app()
```

### Background Tasks
Celery tasks in `src/app/tasks/`:
```python
from app.tasks import celery

@celery.task(bind=True, name='app.tasks.my_task')
def my_task(self, arg1, arg2):
    # Task implementation
    pass
```

## Configuration

All config in `src/app/config/`:
- `settings.py`: Application settings
- `config_manager.py`: Analyzer configuration

Load via environment variables (`.env` file):
```env
FLASK_ENV=development
SECRET_KEY=dev-key
OPENROUTER_API_KEY=sk-...
```

## Database

### Models
Located in `src/app/models/`. Auto-imported by factory pattern.

### Migrations
```bash
# Initialize database
python src/init_db.py

# Direct SQL access
sqlite3 src/data/thesis_app.db
```

## Testing

```bash
# Run all tests
pytest

# Fast tests only (no integration/analyzer)
pytest -m "not integration and not slow and not analyzer"

# Specific test file
pytest tests/test_models.py

# With coverage
pytest --cov=src/app
```

### VS Code Tasks
- `pytest - fast`: Quick smoke tests
- `pytest - quick smoke (venv)`: Venv-aware tests
- `smoke: run http_smoke`: HTTP endpoint tests

## API Development

### Research API
Located in `src/app/routes/api/research.py`. Provides:
- Model comparison
- Batch analysis
- Results aggregation

### Generation API
New simplified system at `/api/gen/*`:
- `POST /api/gen/generate`: Generate application
- `GET /api/gen/status/<task_id>`: Check progress
- `GET /api/gen/result/<app_id>`: Get result

**IMPORTANT**: Old system (`/api/sample-gen/*`) is DEPRECATED - do not use.

## Analyzer Development

### Create New Analyzer
1. Create service in `analyzer/services/my_analyzer/`
2. Add Dockerfile and requirements
3. Register in `analyzer/docker-compose.yml`
4. Update `analyzer_manager.py`

### Test Analyzer
```bash
python analyzer/analyzer_manager.py analyze <model> <app> <type> --tools <tool1,tool2>
```

## OpenRouter Integration

Configure via environment:
```env
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_ALLOW_ALL_PROVIDERS=true  # For research
OPENROUTER_SITE_URL=http://localhost:5000
OPENROUTER_SITE_NAME=ThesisAppRework
```

Models loaded from `misc/openrouter_models.json`.

## Common Tasks

### Add New Route
1. Create blueprint in `src/app/routes/`
2. Register in `src/app/factory.py`
3. Add authentication check if needed

### Add New Model
Update `misc/openrouter_models.json` and restart.

### Update Dependencies
```bash
pip install <package>
pip freeze > requirements.txt
```

## Debugging

### Flask Debug Mode
Set `FLASK_ENV=development` in `.env`.

### Celery Worker Logs
```bash
docker compose logs -f celery-worker
```

### Database Inspection
```bash
sqlite3 src/data/thesis_app.db
.tables
.schema users
SELECT * FROM users;
```

## Code Style

- **Python**: PEP 8, use `black` for formatting
- **Templates**: Jinja2 with Bootstrap 5
- **JavaScript**: Minimal, prefer HTMX
- **No jQuery or inline SVG**
