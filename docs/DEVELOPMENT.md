# Development Guide

## 🛠️ Development Environment Setup

### Prerequisites

1. **Python 3.11+** - Required for modern type hints and features
2. **Docker Desktop** - For containerized testing (optional but recommended)
3. **Git** - Version control
4. **Redis** - For Celery task queue (optional for basic usage)

### IDE Recommendations

- **VS Code** with Python extension
- **PyCharm** Professional or Community
- Configure linting (flake8, black, mypy)
- Set up debugging for Flask applications

### Environment Setup

```bash
# Clone repository
git clone https://github.com/GrabowMar/ThesisAppRework.git
cd ThesisAppRework

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows PowerShell
.venv\Scripts\Activate.ps1
# Windows CMD
.venv\Scripts\activate.bat
# Linux/Mac
source .venv/bin/activate

# Install dependencies
pip install -r src/requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt  # If exists
```

## 🏗️ Application Architecture

### Directory Structure

```
src/app/
├── routes/              # Flask blueprints
│   ├── main.py         # Dashboard and core routes
│   ├── models.py       # Model management routes
│   ├── analysis.py     # Analysis operation routes
│   └── api.py          # REST API endpoints
├── services/           # Business logic layer
│   ├── security_service.py     # ✅ Fully implemented
│   ├── docker_manager.py       # ✅ Fully implemented
│   ├── container_service.py    # 🚧 Stub (TODO)
│   ├── port_service.py         # 🚧 Stub (TODO)
│   └── analyzer_service.py     # 🚧 Stub (TODO)
├── templates/          # Jinja2 templates
├── static/            # CSS, JS, images
├── models.py          # SQLAlchemy models
└── factory.py         # Flask application factory
```

### Service Layer Pattern

Services are organized by functionality:

- **Fully Implemented**: Security service, Docker manager
- **Stub Services**: Container, Port, Analyzer services (see TODO.md)
- **Service Locator**: Centralized service registration and dependency injection

### Blueprint Organization

- **main**: Dashboard, health, batch overview
- **models**: Model browsing, application management
- **analysis**: Security/performance analysis operations
- **api**: REST endpoints and AJAX responses

## 🎯 Development Workflow

### 1. Feature Development

```bash
# Create feature branch
git checkout -b feature/your-feature-name

# Make changes
# ... development work ...

# Run tests
pytest tests/unit/ -v

# Check code quality
flake8 src/
black src/

# Commit changes
git add .
git commit -m "feat: description of feature"

# Push and create PR
git push origin feature/your-feature-name
```

### 2. Running the Application

```bash
# Navigate to src directory
cd src

# Run Flask application
python main.py

# Or use the run script
python run.py

# For production-like setup
gunicorn -w 4 -b 0.0.0.0:5000 "app.factory:create_app()"
```

### 3. Database Operations

```bash
# Initialize database
python -c "from app.extensions import init_db; init_db()"

# Run migrations (when implemented)
flask db upgrade

# Create new migration (when implemented)
flask db migrate -m "Description of changes"
```

### 4. Testing

```bash
# Unit tests only
pytest tests/unit/ -v

# Integration tests (requires Docker)
pytest tests/integration/ -v

# Specific test file
pytest tests/unit/test_security_service.py -v

# With coverage
pytest --cov=app tests/ --cov-report=html
```

## 🔧 Code Standards

### Python Style Guide

- **PEP 8** compliance
- **Type hints** for all function parameters and returns
- **Docstrings** for all classes and public methods
- **Maximum line length**: 88 characters (Black default)

### Code Example

## 🎨 UI Styling Conventions

- No inline CSS or embedded <style> blocks in templates/partials. All styles live in `src/static/css/theme.css`.
- Use Bootstrap/AdminLTE utilities wherever possible (e.g., spacing, text colors, display, grid).
- Visibility: use `d-none` to hide elements and show them by removing the class. Avoid `style.display` toggles.
- Progress bars: set widths via `data-width` attribute. The base template applies widths on load and after HTMX swaps.
- Provider badges: set `data-provider-color` where needed; base script applies background color.
- Activity timelines: use shared styles in `theme.css` (no template-level CSS).
- Logs: use `.container-logs` and `font-mono-sm` for consistent dark-themed log panes.
- Font sizing: prefer provided `fs-*` utility classes (e.g., `fs-0_9rem`, `fs-0_85rem`, `fs-0_8rem`).


```python
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class ExampleService:
    """
    Example service following project conventions.
    
    This service demonstrates:
    - Proper type hints
    - Comprehensive docstrings
    - Error handling patterns
    - Logging integration
    """
    
    def __init__(self, app: Flask):
        self.app = app
        self.config = app.config
        self.logger = logger
    
    def process_data(self, data: Dict[str, Any], 
                    validate: bool = True) -> Optional[Dict[str, Any]]:
        """
        Process input data with optional validation.
        
        Args:
            data: Input data dictionary
            validate: Whether to validate input data
            
        Returns:
            Processed data dictionary or None if processing fails
            
        Raises:
            ValueError: If validation fails and validate=True
        """
        try:
            if validate and not self._validate_data(data):
                raise ValueError("Data validation failed")
            
            # Processing logic here
            result = self._transform_data(data)
            
            self.logger.info(f"Successfully processed data with {len(result)} items")
            return result
            
        except Exception as e:
            self.logger.error(f"Error processing data: {e}")
            return None
    
    def _validate_data(self, data: Dict[str, Any]) -> bool:
        """Private method for data validation."""
        # Validation logic
        return True
    
    def _transform_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Private method for data transformation."""
        # Transformation logic
        return data
```

### Template Standards

- **HTMX attributes** for dynamic behavior
- **Bootstrap classes** for styling
- **Proper error handling** with user-friendly messages
- **Accessibility** considerations (ARIA labels, semantic HTML)

### Template Example

```html
<!-- partials/example_form.html -->
<form hx-post="{{ url_for('analysis.start_analysis') }}" 
      hx-target="#analysis-results"
      hx-indicator="#loading-spinner">
    
    <div class="mb-3">
        <label for="model-select" class="form-label">AI Model</label>
        <select class="form-select" id="model-select" name="model_slug" required>
            <option value="">Select a model...</option>
            {% for model in models %}
            <option value="{{ model.slug }}">{{ model.name }}</option>
            {% endfor %}
        </select>
    </div>
    
    <button type="submit" class="btn btn-primary">
        <i class="fas fa-play me-1"></i>Start Analysis
    </button>
    
    <div id="loading-spinner" class="htmx-indicator">
        <i class="fas fa-spinner fa-spin"></i> Processing...
    </div>
</form>

<div id="analysis-results">
    <!-- Results will be loaded here via HTMX -->
</div>
```

## 🧪 Testing Guidelines

### Test Structure

```
tests/
├── unit/                   # Unit tests for individual components
│   ├── test_services.py   # Service layer tests
│   ├── test_models.py     # Database model tests
│   └── test_routes.py     # Route handler tests
├── integration/           # Integration tests
│   ├── test_api.py       # API endpoint tests
│   └── test_workflows.py # End-to-end workflow tests
└── conftest.py           # Test configuration and fixtures
```

### Test Example

```python
import pytest
from unittest.mock import Mock, patch
from app.services.security_service import SecurityService

class TestSecurityService:
    """Test suite for SecurityService."""
    
    @pytest.fixture
    def security_service(self, app):
        """Create SecurityService instance for testing."""
        return SecurityService()
    
    def test_start_security_analysis_success(self, security_service):
        """Test successful security analysis start."""
        # Arrange
        model_slug = "test_model"
        app_number = 1
        tools = ["bandit", "safety"]
        
        # Act
        result = security_service.start_security_analysis(
            model_slug, app_number, tools
        )
        
        # Assert
        assert result is not None
        assert isinstance(result, str)  # Should return scan ID
    
    @patch('app.services.security_service.get_session')
    def test_start_security_analysis_database_error(self, mock_session, security_service):
        """Test security analysis start with database error."""
        # Arrange
        mock_session.side_effect = Exception("Database error")
        
        # Act & Assert
        with pytest.raises(Exception):
            security_service.start_security_analysis("test_model", 1)
```

## 🐳 Docker Development

### Using Docker for Testing

```bash
# Build analyzer containers
cd analyzer
docker-compose build

# Start analyzer services
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f security-scanner
```

### Container Integration

- Generated applications run in isolated containers
- Analysis tools run in separate containers
- Use `docker-compose.yml` files for orchestration
- Implement proper container health checks

## 🔍 Debugging

### Flask Application Debugging

```python
# Enable debug mode
export FLASK_ENV=development
export FLASK_DEBUG=1

# Run with debug server
python main.py
```

### Database Debugging

```python
# Enable SQL query logging
import logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# Query debugging in session
from app.extensions import get_session
with get_session() as session:
    # Your database operations
    pass
```

### HTMX Debugging

- Use browser dev tools Network tab
- Check HTMX request/response headers
- Use `hx-on` attributes for JavaScript hooks
- Enable HTMX debug mode in templates

## 📝 Documentation Standards

### Code Documentation

- **Module docstrings**: Explain purpose and dependencies
- **Class docstrings**: Describe class responsibility
- **Method docstrings**: Use Google style with Args/Returns/Raises
- **Inline comments**: Explain complex logic only

### API Documentation

- Document all REST endpoints
- Include request/response examples
- Specify error codes and handling
- Use OpenAPI specification when possible

## 🚀 Deployment

### Development Deployment

```bash
# Using Flask development server
python main.py

# Using Gunicorn (production-like)
gunicorn -w 4 -b 0.0.0.0:5000 "app.factory:create_app()"
```

### Production Considerations

- Use proper WSGI server (Gunicorn, uWSGI)
- Configure reverse proxy (Nginx)
- Set up SSL/TLS certificates
- Configure proper logging and monitoring
- Use environment variables for secrets
- Set up database migrations
- Configure Celery workers for production

## 🔒 Security Best Practices

### Application Security

- Validate all user inputs
- Use parameterized queries (SQLAlchemy ORM)
- Implement proper session management
- Add CSRF protection for forms
- Sanitize output in templates

### Container Security

- Use non-root users in containers
- Implement resource limits
- Regular security updates
- Network isolation between services

## 📊 Performance Optimization

### Application Performance

- Use database connection pooling
- Implement caching for frequently accessed data
- Optimize database queries
- Use async processing for long-running tasks

### Monitoring

- Add application metrics
- Monitor database performance
- Track container resource usage
- Implement health checks

## 🤝 Contributing Guidelines

### Before Contributing

1. Read TODO.md for current priorities
2. Check existing issues and PRs
3. Discuss major changes in issues first

### Code Review Process

1. Ensure all tests pass
2. Check code follows style guidelines
3. Verify documentation is updated
4. Test functionality manually
5. Review for security considerations

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
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] TODO.md updated if applicable
```

---

## 📞 Getting Help

- Check existing documentation first
- Look at similar implementations in codebase
- Create GitHub issue for bugs or feature requests
- Follow established patterns and conventions
- Ask questions in PR reviews

---

## 🧩 Partials & HTMX Conventions

This project favors small, reusable Jinja partials and HTMX-driven updates. The goals are consistency, no inline JS where avoidable, and seamless progressive enhancement.

Guidelines
- File locations
    - Keep reusable fragments under `src/templates/partials/**` grouped by domain (dashboard, analysis, testing, etc.).
    - Alias partials can live as thin includes to preserve legacy paths (e.g., `partials/apps_grid/grid.html` → `partials/apps_grid/apps_grid.html`).
- Page shell
    - Prefer `{% extends 'single_page.html' %}` for simple pages.
    - Use blocks in `single_page.html`:
        - `page_badges`: right under the title for chips/states
        - `page_actions`: right-aligned action buttons; legacy `page_actions_partial` still works inside
- Sidebar & macros
    - Use `templates/macros/ui.html` macros for nav links to ensure active state + aria-current.
    - Centralize menu in `partials/common/sidebar_links.html` and include it from `base.html`.
- HTMX usage
    - Favor `hx-get` for idempotent updates; use `hx-post` for writes.
    - Default indicator: global `#globalSpinner` is auto-toggled via `htmx:beforeRequest/afterOnLoad` hooks. You can still set `hx-indicator` locally for per-widget spinners.
    - Default swap: prefer `hx-swap="innerHTML transition:true"` for main panels; `outerHTML` when replacing a container (cards/lists).
    - Re-init JS after swaps: `base.html` binds an `htmx:afterSwap` hook to rewire tooltips and AdminLTE widgets.
- Theming
    - Light/dark toggle lives in `static/js/theme_toggle.js`; styles in `static/css/theme.css`.
    - Add dark-mode overrides with `body.theme-dark ...` selectors.

Examples
```html
<!-- Card that refreshes itself -->
<div id="recentCombined"
         hx-get="/analysis/api/recent/combined"
         hx-trigger="load, every 60s"
         hx-swap="outerHTML">
    {% include 'partials/analysis/recent_combined.html' %}
    <!-- global spinner is automatically shown; add hx-indicator for per-card spinner if needed -->
    <!-- <div class="htmx-indicator small text-muted"><i class="fas fa-spinner fa-spin"></i> Loading…</div> -->
  
</div>
```

Acceptance checklist for a new partial
- Lives under the correct `partials/**` folder
- No blocking inline scripts; re-init via global hooks where possible
- Works with HTMX (target, swap, indicator as needed)
- Degrades gracefully without JS (static render is acceptable)
- Accessible labels and semantics
