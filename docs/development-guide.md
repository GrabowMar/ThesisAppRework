# Development Guide

Setup and development workflow for ThesisAppRework.

## Prerequisites

- Python 3.10+
- Docker Desktop (for analyzers)
- Node.js 18+ (for frontend tools)
- Git

## Quick Setup

```bash
# Clone and setup
git clone https://github.com/GrabowMar/ThesisAppRework.git
cd ThesisAppRework

# Create virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1  # Windows
source .venv/bin/activate   # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings (OPENROUTER_API_KEY, etc.)

# Initialize database
python src/init_db.py

# Start development server
./start.ps1 -Mode Dev -NoAnalyzer
```

## Project Structure

```
ThesisAppRework/
├── src/                    # Flask application
│   ├── main.py            # Entry point
│   ├── app/
│   │   ├── factory.py     # App factory
│   │   ├── models/        # SQLAlchemy models
│   │   ├── services/      # Business logic
│   │   ├── routes/        # Web routes
│   │   └── api/           # REST API
│   └── templates/         # Jinja2 templates
├── analyzer/              # Analyzer microservices
│   ├── analyzer_manager.py
│   ├── services/          # Container services
│   └── shared/            # Shared code
├── generated/apps/        # AI-generated applications
├── results/               # Analysis results
├── tests/                 # Test suite
└── docs/                  # Documentation
```

## Development Modes

### Flask Only (Fast)

```bash
./start.ps1 -Mode Dev -NoAnalyzer
# Or directly:
python src/main.py
```

Access at http://localhost:5000

### Full Stack

```bash
./start.ps1 -Mode Start
```

Starts Flask + all analyzer containers.

### Interactive Menu

```bash
./start.ps1
```

## Running Tests

### VS Code Test Explorer

Open **Testing** panel (Ctrl+Shift+T) for interactive test discovery and debugging.

### Command Line

```bash
# Fast unit tests (recommended for development)
pytest -m "not integration and not slow and not analyzer"

# Smoke tests
pytest tests/smoke/

# Specific test file
pytest tests/unit/test_analyzer_manager.py

# With coverage
pytest --cov=src --cov-report=html
```

### Test Markers

| Marker | Description |
|--------|-------------|
| `unit` | Fast unit tests |
| `smoke` | Critical path health checks |
| `integration` | Requires services |
| `slow` | Long-running tests |
| `analyzer` | Requires Docker analyzers |

## Code Style

### Python

- Follow PEP 8
- Type hints encouraged
- Docstrings for public functions

```python
def analyze_app(model_slug: str, app_number: int) -> dict:
    """Run analysis on a generated application.
    
    Args:
        model_slug: Normalized model identifier
        app_number: Application number (1-indexed)
        
    Returns:
        Analysis results dictionary
    """
```

### Linting

```bash
# Ruff (fast)
ruff check src/

# MyPy (type checking)
mypy src/
```

## Adding a New Analyzer Tool

1. **Update service handler** in [analyzer/services/{service}/](../analyzer/services/):

```python
async def run_new_tool(self, source_path: str) -> dict:
    # Implementation
    return {"status": "success", "findings": [...]}
```

2. **Register in tool map** within service's main handler

3. **Update aggregation** in [analyzer/analyzer_manager.py](../analyzer/analyzer_manager.py):
   - Add to `_collect_normalized_tools()`
   - Add to `_aggregate_findings()` if needed

4. **Add tests** in `tests/unit/` and `tests/integration/analyzer/`

## Adding a New API Endpoint

1. **Create route** in [src/app/api/](../src/app/api/):

```python
@api_bp.route('/new-endpoint', methods=['POST'])
@require_auth
def new_endpoint():
    data = request.get_json()
    # Implementation
    return jsonify({"result": "..."})
```

2. **Register blueprint** (if new file) in [src/app/factory.py](../src/app/factory.py)

3. **Add tests** in `tests/integration/api/`

4. **Document** in [api-reference.md](./api-reference.md)

## Database Migrations

Using Flask-Migrate:

```bash
# Create migration
flask db migrate -m "Description"

# Apply migrations
flask db upgrade

# Or via VS Code task: "db: run migrations"
```

## Debugging

### Flask Debug Mode

Set in `.env`:
```
FLASK_DEBUG=1
LOG_LEVEL=DEBUG
```

### VS Code Launch Configurations

See `.vscode/launch.json` for debugger configs:
- **Flask App** - Debug web server
- **Pytest** - Debug tests
- **Analyzer Manager** - Debug CLI

### Common Issues

| Issue | Solution |
|-------|----------|
| Port 5000 in use | `./start.ps1 -Mode Stop` or kill process |
| Analyzer connection failed | `python analyzer/analyzer_manager.py start` |
| Database locked | Restart Flask, check for zombie processes |
| Import errors | Activate venv, reinstall requirements |

## Environment Variables

Key variables for development:

```bash
# Required
OPENROUTER_API_KEY=sk-...

# Development
FLASK_DEBUG=1
LOG_LEVEL=DEBUG
ANALYZER_ENABLED=true
ANALYZER_AUTO_START=false

# Database
DATABASE_URL=sqlite:///src/data/thesis_app.db

# Timeouts (seconds)
STATIC_ANALYSIS_TIMEOUT=300
SECURITY_ANALYSIS_TIMEOUT=600
```

## Git Workflow

```bash
# Feature branch
git checkout -b feature/my-feature

# Make changes, commit
git add .
git commit -m "feat: add new feature"

# Push and create PR
git push -u origin feature/my-feature
```

Commit prefixes: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`

## Related

- [Architecture](./architecture.md)
- [API Reference](./api-reference.md)
- [Deployment Guide](./deployment-guide.md)
