# Development Guide

Complete guide for setting up, developing, and contributing to the ThesisApp platform.

## Quick Start

### Prerequisites

- **Python 3.9+**
- **Docker & Docker Compose**
- **Redis** (for Celery)
- **Git**

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/YourOrg/ThesisAppRework.git
cd ThesisAppRework
```

2. **Set up Python environment**
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

3. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. **Initialize database**
```bash
cd src
python init_db.py
```

5. **Start analyzer services**
```bash
cd analyzer
docker-compose up -d
```

6. **Start the application**
```bash
# Terminal 1: Flask app
cd src
python main.py

# Terminal 2: Celery worker
cd src
celery -A app.tasks worker --loglevel=info

# Terminal 3: Celery beat (optional, for scheduled tasks)
cd src
celery -A app.tasks beat --loglevel=info
```

7. **Access the application**
- Web UI: http://localhost:5000
- API: http://localhost:5000/api
- Health Check: http://localhost:5000/health

## Project Structure

```
ThesisAppRework/
├── src/                          # Main application code
│   ├── app/                      # Flask application package
│   │   ├── routes/               # Route blueprints
│   │   │   ├── jinja/            # HTML page routes
│   │   │   ├── api/              # REST API routes
│   │   │   └── websockets/       # WebSocket routes
│   │   ├── services/             # Business logic services
│   │   ├── models/               # SQLAlchemy models
│   │   ├── tasks/                # Celery tasks
│   │   ├── utils/                # Utility functions
│   │   ├── extensions.py         # Flask extensions
│   │   ├── factory.py            # App factory
│   │   └── constants.py          # Application constants
│   ├── templates/                # Jinja2 templates
│   │   ├── layouts/              # Base layouts
│   │   ├── pages/                # Full page templates
│   │   └── shared/               # Shared components
│   ├── static/                   # Static assets
│   │   ├── css/                  # Stylesheets
│   │   ├── js/                   # JavaScript
│   │   └── images/               # Images
│   ├── config/                   # Configuration files
│   ├── main.py                   # Application entry point
│   └── worker.py                 # Celery worker entry point
├── analyzer/                     # Analyzer microservices
│   ├── services/                 # Individual analyzer services
│   ├── shared/                   # Shared analyzer code
│   ├── docker-compose.yml        # Analyzer stack
│   └── analyzer_manager.py       # CLI management tool
├── tests/                        # Test suite
├── scripts/                      # Utility scripts
├── docs/                         # Documentation
└── requirements.txt              # Python dependencies
```

## Application Status Management

The platform implements an intelligent application status system that balances performance with accuracy:

### Database Model Enhancement

```python
class GeneratedApplication(db.Model):
    # ... existing fields ...
    container_status = db.Column(db.String(50), default='stopped')
    last_status_check = db.Column(db.DateTime(timezone=True))
    
    def update_container_status(self, status: str) -> None:
        """Update container status and timestamp."""
        self.container_status = status
        self.last_status_check = utc_now()
    
    def is_status_fresh(self, max_age_minutes: int = 5) -> bool:
        """Check if the status is fresh enough to trust without Docker check."""
        if not self.last_status_check:
            return False
        age = utc_now() - self.last_status_check
        return age.total_seconds() < (max_age_minutes * 60)
```

### Service Layer

```python
# app/services/application_service.py
def refresh_all_application_statuses() -> Dict[str, Any]:
    """Refresh all application container statuses from Docker and update database."""
    # Bulk Docker status check with database sync
    # Returns summary of operation (total_checked, updated, errors)
    
def start_application(app_id: int) -> Dict[str, Any]:
    """Start application and update database status."""
    app = db.session.get(GeneratedApplication, app_id)
    app.update_container_status('running')
    # ... Docker operations ...
```

### API Endpoints

```python
@applications_bp.route('/applications/refresh-all-statuses', methods=['POST'])
def refresh_all_application_statuses():
    """Bulk refresh all application statuses from Docker."""
    
@applications_bp.route('/app/<model_slug>/<int:app_number>/status', methods=['GET'])  
def get_app_status(model_slug, app_number):
    """Get status with database sync and timing information."""
```

### Frontend Integration

```javascript
// Smart polling that prefers database cache
function pollApplicationStatuses() {
    // Only check uncertain statuses frequently
    // Check definitive statuses every 5th cycle
    // Show status age in tooltips
}

function refreshAllStatuses() {
    // Bulk refresh with user feedback
    // Updates entire applications table
}
```

## Development Workflow

### 1. Setting Up Your Environment

**Python Environment**
```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Development dependencies
```

**Environment Variables**
```bash
# Required environment variables
export FLASK_ENV=development
export DATABASE_URL=sqlite:///src/data/thesis_app.db
export CELERY_BROKER_URL=redis://localhost:6379/0
export CELERY_RESULT_BACKEND=redis://localhost:6379/0
export OPENROUTER_API_KEY=your_api_key_here

# Optional development variables
export DEBUG=true
export LOG_LEVEL=DEBUG
export ANALYZER_AUTO_START=true
```

### 2. Running the Development Stack

**Option A: Full Stack with Scripts**
```bash
# Start all services
python scripts/start_services.py --mode development

# Stop all services
python scripts/stop_services.py
```

**Option B: Manual Service Management**
```bash
# Start Redis (if not running)
redis-server

# Start analyzer services
cd analyzer
docker-compose up -d

# Start Flask app
cd src
python main.py

# Start Celery worker (new terminal)
cd src
celery -A app.tasks worker --loglevel=info
```

### 3. Development Tools

**Code Quality**
```bash
# Linting
flake8 src/
pylint src/app/

# Type checking
mypy src/app/

# Code formatting
black src/
isort src/
```

**Testing**
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/app tests/

# Run specific test file
pytest tests/test_models.py

# Run with debug output
pytest -v -s tests/test_analysis.py
```

**Database Management**
```bash
# Create migration
cd src
flask db migrate -m "Description of changes"

# Apply migrations
flask db upgrade

# Reset database (development only)
python init_db.py --reset
```

## Architecture Deep Dive

### Service Layer Pattern

The application uses a Service Locator pattern for dependency injection:

```python
# services/service_locator.py
class ServiceLocator:
    _services = {}
    
    @classmethod
    def register(cls, name: str, service: object):
        cls._services[name] = service
    
    @classmethod
    def get(cls, name: str):
        return cls._services.get(name)

# In routes, never import services directly
from app.services.service_locator import ServiceLocator

def my_route():
    model_service = ServiceLocator.get_model_service()
    return model_service.get_models()
```

### Analysis Engine Pattern

All analysis types follow a uniform interface:

```python
# services/analysis_engines.py
class AnalysisEngine:
    def run(self, model: str, app: int, **options) -> dict:
        """Execute analysis and return results."""
        pass

class SecurityEngine(AnalysisEngine):
    def run(self, model: str, app: int, **options) -> dict:
        # Implementation
        return {"status": "completed", "results": {...}}
```

### Database Patterns

**Model Design**
```python
# models/__init__.py
class AnalysisBase(db.Model):
    __abstract__ = True
    
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.Enum(AnalysisStatus), default=AnalysisStatus.PENDING)
    started_at = db.Column(db.DateTime(timezone=True))
    completed_at = db.Column(db.DateTime(timezone=True))
    results_json = db.Column(db.Text)  # Large results stored as JSON
    metadata_json = db.Column(db.Text)  # Additional metadata
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)
```

**JSON Column Usage**
```python
def get_results(self) -> Dict[str, Any]:
    """Parse results JSON with error handling."""
    if self.results_json:
        try:
            return json.loads(self.results_json)
        except json.JSONDecodeError:
            return {}
    return {}

def set_results(self, results: Dict[str, Any]) -> None:
    """Store results as JSON."""
    self.results_json = json.dumps(results)
```

### Frontend Patterns

**HTMX Integration**
```html
<!-- Dynamic table updates -->
<table hx-get="/api/analysis/list" 
       hx-trigger="load, every 30s" 
       hx-target="this tbody"
       hx-swap="innerHTML">
    <tbody>
        <!-- Content loaded via HTMX -->
    </tbody>
</table>

<!-- Form submission with fragment update -->
<form hx-post="/api/analysis/start"
      hx-target="#analysis-results"
      hx-swap="innerHTML">
    <!-- Form fields -->
    <button type="submit" class="btn btn-primary">
        <i class="fas fa-play me-1"></i>
        Start Analysis
    </button>
</form>
```

**Template Organization**
```html
<!-- layouts/base.html -->
<!DOCTYPE html>
<html>
<head>
    {% block head %}
    <title>{% block title %}ThesisApp{% endblock %}</title>
    <link href="/static/css/bootstrap.min.css" rel="stylesheet">
    {% endblock %}
</head>
<body>
    {% block content %}{% endblock %}
    {% block scripts %}
    <script src="/static/js/bootstrap.bundle.min.js"></script>
    <script src="/static/js/htmx.min.js"></script>
    {% endblock %}
</body>
</html>

<!-- pages/analysis/dashboard.html -->
{% extends "layouts/base.html" %}

{% block title %}Analysis Dashboard{% endblock %}

{% block content %}
<div class="container-fluid">
    {% include "shared/analysis_grid.html" %}
</div>
{% endblock %}
```

## Testing Strategy

### Test Organization

```
tests/
├── unit/                         # Unit tests
│   ├── test_models.py
│   ├── test_services.py
│   └── test_utils.py
├── integration/                  # Integration tests
│   ├── test_api.py
│   ├── test_analysis_flow.py
│   └── test_websockets.py
├── e2e/                         # End-to-end tests
│   ├── test_ui_flows.py
│   └── test_analysis_pipeline.py
└── conftest.py                  # Pytest configuration
```

### Writing Tests

**Model Tests**
```python
def test_security_analysis_lifecycle():
    """Test SecurityAnalysis model lifecycle."""
    analysis = SecurityAnalysis(
        application_id=1,
        analysis_name="Test Security Analysis"
    )
    db.session.add(analysis)
    db.session.commit()
    
    # Test status transitions
    analysis.status = AnalysisStatus.RUNNING
    analysis.started_at = utc_now()
    
    # Test JSON methods
    results = {"total_issues": 5, "severity": "medium"}
    analysis.set_results(results)
    assert analysis.get_results() == results
```

**Service Tests**
```python
@pytest.fixture
def model_service():
    return ModelService(mock_app)

def test_model_service_get_models(model_service):
    """Test ModelService.get_models()."""
    models = model_service.get_models()
    assert isinstance(models, list)
    assert len(models) > 0
    assert all(hasattr(m, 'model_id') for m in models)
```

**API Tests**
```python
def test_analysis_api_start_security(client):
    """Test starting security analysis via API."""
    response = client.post('/api/analysis/security', json={
        'application_id': 1,
        'analysis_name': 'Test Security Analysis',
        'tools': {'bandit_enabled': True}
    })
    
    assert response.status_code == 201
    data = response.get_json()
    assert 'analysis_id' in data
    assert data['status'] == 'pending'
```

### Test Configuration

```python
# conftest.py
@pytest.fixture(scope='session')
def app():
    """Create test Flask application."""
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()

@pytest.fixture
def auth_headers():
    """Create authentication headers for API tests."""
    return {'Authorization': 'Bearer test_token'}
```

## Deployment

### Development Deployment

**Using Docker Compose**
```yaml
# docker-compose.dev.yml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "5000:5000"
    environment:
      - FLASK_ENV=development
      - DATABASE_URL=postgresql://user:pass@db:5432/thesis_app
    depends_on:
      - db
      - redis
    volumes:
      - ./src:/app/src
  
  worker:
    build: .
    command: celery -A app.tasks worker --loglevel=info
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
    depends_on:
      - redis
  
  db:
    image: postgres:14
    environment:
      - POSTGRES_DB=thesis_app
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
  
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
```

### Production Deployment

**Environment Configuration**
```bash
# production.env
FLASK_ENV=production
DEBUG=false
DATABASE_URL=postgresql://user:secure_password@db_host:5432/thesis_app
CELERY_BROKER_URL=redis://redis_host:6379/0
SECRET_KEY=your_secure_secret_key
OPENROUTER_API_KEY=your_production_api_key
```

**Gunicorn Configuration**
```python
# gunicorn.conf.py
bind = "0.0.0.0:5000"
workers = 4
worker_class = "gevent"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
timeout = 30
keepalive = 2
```

**Nginx Configuration**
```nginx
# nginx.conf
upstream thesis_app {
    server app:5000;
}

server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://thesis_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location /static/ {
        alias /app/src/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    location /ws {
        proxy_pass http://thesis_app;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## Performance Optimization

### Database Optimization

**Query Optimization**
```python
# Use select_related for foreign keys
applications = GeneratedApplication.query.options(
    db.selectinload(GeneratedApplication.security_analyses)
).all()

# Add database indexes
class SecurityAnalysis(db.Model):
    application_id = db.Column(db.Integer, db.ForeignKey('generated_applications.id'), 
                              nullable=False, index=True)
    status = db.Column(db.Enum(AnalysisStatus), default=AnalysisStatus.PENDING, index=True)
```

**Connection Pooling**
```python
# config/database.py
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_size': 10,
    'pool_recycle': 3600,
    'pool_pre_ping': True,
    'max_overflow': 20
}
```

### Celery Optimization

**Worker Configuration**
```python
# config/celery_config.py
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000
CELERY_TASK_SOFT_TIME_LIMIT = 3600
CELERY_TASK_TIME_LIMIT = 3900
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_SEND_TASK_EVENTS = True
```

**Task Optimization**
```python
@celery.task(bind=True, soft_time_limit=1800)
def run_security_analysis(self, analysis_id):
    """Run security analysis with proper error handling."""
    try:
        # Task implementation
        pass
    except SoftTimeLimitExceeded:
        # Handle timeout gracefully
        pass
```

### Frontend Optimization

**Asset Optimization**
- Use CDN for Bootstrap and Font Awesome
- Minimize custom CSS and JavaScript
- Implement lazy loading for large tables
- Use HTMX for efficient partial updates

**Caching Strategy**
```python
# Add caching headers for static assets
@app.after_request
def add_cache_headers(response):
    if request.endpoint == 'static':
        response.cache_control.max_age = 31536000  # 1 year
        response.cache_control.public = True
    return response
```

## Security Considerations

### Input Validation

```python
from marshmallow import Schema, fields, validate

class AnalysisRequestSchema(Schema):
    application_id = fields.Integer(required=True, validate=validate.Range(min=1))
    analysis_name = fields.String(required=True, validate=validate.Length(min=1, max=200))
    tools = fields.Dict(required=False)
```

### Output Sanitization

```python
# Always use Jinja2's auto-escaping
{{ user_input }}  # Automatically escaped

# For trusted HTML content
{{ trusted_html|safe }}

# In Python
from markupsafe import escape
safe_output = escape(user_input)
```

### API Security

```python
# Rate limiting
from flask_limiter import Limiter

limiter = Limiter(
    app,
    key_func=lambda: request.remote_addr,
    default_limits=["100 per hour"]
)

@app.route('/api/analysis', methods=['POST'])
@limiter.limit("10 per minute")
def start_analysis():
    pass
```

## Monitoring and Logging

### Structured Logging

```python
import structlog

logger = structlog.get_logger(__name__)

def start_analysis(analysis_id):
    logger.info("Starting analysis", 
                analysis_id=analysis_id, 
                user_id=current_user.id)
    try:
        # Analysis logic
        logger.info("Analysis completed successfully", analysis_id=analysis_id)
    except Exception as e:
        logger.error("Analysis failed", 
                    analysis_id=analysis_id, 
                    error=str(e))
```

### Health Monitoring

```python
@app.route('/health')
def health_check():
    checks = {
        'database': check_database_health(),
        'redis': check_redis_health(),
        'analyzers': check_analyzer_health()
    }
    
    overall_status = 'healthy' if all(checks.values()) else 'degraded'
    
    return {
        'status': overall_status,
        'checks': checks,
        'timestamp': datetime.utcnow().isoformat()
    }
```

## Contributing

### Code Style

- Follow PEP 8 for Python code
- Use type hints where possible
- Write descriptive docstrings
- Keep functions small and focused
- Use meaningful variable names

### Git Workflow

1. Create feature branch from `main`
2. Make changes with clear commit messages
3. Write/update tests for new functionality
4. Ensure all tests pass
5. Create pull request with description
6. Code review and merge

### Pull Request Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests pass
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No new warnings introduced
```

This development guide provides the foundation for productive development on the ThesisApp platform.