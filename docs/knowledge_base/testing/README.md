# Testing & Analysis

## Quick Start

```bash
# Fast tests (no integration/analyzer)
pytest -m "not integration and not slow and not analyzer"

# All tests
pytest

# With coverage
pytest --cov=src/app --cov-report=html
```

## Test Structure

```
tests/
├── unit/              # Unit tests
├── integration/       # Integration tests
├── analyzer/          # Analyzer tests (slow)
└── conftest.py        # Fixtures and config
```

## Markers

- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.slow` - Slow-running tests
- `@pytest.mark.analyzer` - Analyzer service tests

## Analyzer Testing

### Start Analyzers
```bash
python analyzer/analyzer_manager.py start
python analyzer/analyzer_manager.py health
```

### Run Analysis
```bash
# Single analysis
python analyzer/analyzer_manager.py analyze openai_gpt-4 <app_id> security --tools bandit,safety

# Batch analysis
python analyzer/analyzer_manager.py batch batch_config.json
```

### Batch Configuration
```json
[
  ["openai_gpt-4", 1],
  ["anthropic_claude-3.5-sonnet", 2]
]
```

## Analysis Tools

### Static Analysis
- **Bandit**: Security vulnerability scanner
- **Safety**: Dependency security checker
- **PyLint**: Code quality analyzer
- **Flake8**: Style and syntax checker
- **ESLint**: JavaScript/React linter

### Dynamic Analysis
- **OWASP ZAP**: Security testing
- **Custom scanners**: Runtime behavior analysis

### Performance Testing
- **Locust**: Load testing
- **Response time analysis**
- **Resource usage monitoring**

### AI Analysis
- Uses OpenRouter models for code review
- Checks: security, performance, code quality, best practices

## Results

Results stored in `results/<timestamp>_<model>_<app>.json`:
```json
{
  "model": "openai_gpt-4",
  "app_id": 1,
  "analysis_type": "security",
  "tools": ["bandit", "safety"],
  "findings": [...],
  "summary": "..."
}
```

## VS Code Tasks

Available tasks in `.vscode/tasks.json`:
- `pytest - fast`: Quick smoke tests
- `pytest - quick smoke (venv)`: Venv tests
- `smoke: run http_smoke`: HTTP endpoint tests

Run via: `Terminal → Run Task → <task-name>`

## HTTP Smoke Tests

```bash
# Test all endpoints
python scripts/http_smoke.py

# Custom checks
python scripts/http_smoke.py --endpoints /api/health /api/models
```

## Coverage

```bash
# Generate coverage report
pytest --cov=src/app --cov-report=html

# View report
open htmlcov/index.html  # Mac/Linux
start htmlcov/index.html  # Windows
```

Target: >90% coverage for core functionality

## Troubleshooting

**Tests hang**: Check if analyzers are running
**Import errors**: Ensure PYTHONPATH includes `src/`
**Database locked**: Stop other processes accessing DB
**Port conflicts**: Change test ports in `conftest.py`

## CI/CD Integration

```yaml
# GitHub Actions example
- name: Run tests
  run: |
    pytest -m "not integration and not analyzer"
    
- name: Coverage
  run: |
    pytest --cov=src/app --cov-report=xml
```
