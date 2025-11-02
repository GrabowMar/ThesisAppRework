# Quick Test Reference Card

## 🚀 Quick Start

### Run Unit Tests (Fast - ~5 seconds)
```bash
pytest -m "not integration and not slow and not analyzer"
```

### Run Smoke Tests (Critical paths - ~10 seconds)
```bash
pytest tests/smoke/ -v
```

### Run All Tests
```bash
pytest tests/ -v
```

### VS Code Tasks
```
Terminal → Run Task → Select:
- "pytest: unit tests only" (default, fastest)
- "pytest: smoke tests" (quick health check)
- "pytest: integration tests" (all integration)
- "pytest: api integration" (API tests only)
- "pytest: websocket integration" (WebSocket tests only)
- "pytest: analyzer integration" (Analyzer tests only)
- "pytest: web ui integration" (Web UI tests only)
```

### VS Code Test Explorer
Open Testing panel (Ctrl+Shift+T) to discover and run tests interactively with debugging support.

---

## 📂 Test Organization

```
tests/
├── smoke/                      # Fast critical path tests (~10s)
│   ├── test_analyzer_health.py
│   └── test_http_endpoints.py
├── integration/                # Integration tests (requires services)
│   ├── api/                   # API endpoint tests
│   ├── websocket/             # WebSocket protocol tests
│   ├── analyzer/              # Analyzer service tests
│   └── web_ui/                # Web UI interaction tests
├── routes/                     # Route unit tests
├── services/                   # Service unit tests
└── conftest.py                # Shared fixtures

scripts/
├── diagnostics/               # Check/verify scripts
│   ├── check_apps.py
│   ├── check_tasks.py
│   └── verify_container_tools.py
└── maintenance/               # One-off admin scripts
    ├── cleanup_old_tasks.py
    ├── reaggregate_all_tasks.py
    └── demo_bearer_token_operations.py
```

---

## 🧪 Test Markers

Run tests by marker to target specific categories:

```bash
pytest -m smoke           # Fast smoke tests
pytest -m integration     # Integration tests
pytest -m analyzer        # Analyzer service tests
pytest -m api            # API endpoint tests
pytest -m websocket      # WebSocket tests
pytest -m web_ui         # Web UI tests
pytest -m slow           # Slow-running tests
```

Combine markers:
```bash
pytest -m "integration and api"           # API integration only
pytest -m "not integration and not slow"  # Fast unit tests
```

---

## 🔧 Prerequisites Check

```bash
# Flask app running?
curl http://localhost:5000

# Docker containers up?
docker ps --filter name=analyzer

# Analyzer status
python analyzer/analyzer_manager.py status
```

---

## 🎯 Common Test Commands

```bash
# Run specific test file
pytest tests/integration/api/test_api_analysis_endpoint.py -v

# Run specific test
pytest tests/smoke/test_http_endpoints.py::test_health_endpoint -v

# Verbose output
pytest tests/ -v

# Show print statements
pytest tests/ -s

# Stop on first failure
pytest tests/ -x

# Run last failed
pytest --lf

# With coverage
pytest tests/ --cov=src --cov-report=html
```

---

## 🐛 Debugging Tests

### VS Code Debugging
Use Run & Debug panel (Ctrl+Shift+D) and select:
- "Debug Unit Tests" - Fast unit tests with breakpoints
- "Debug Smoke Tests" - Smoke tests with debugging
- "Debug Integration Tests" - Integration tests with debugging
- "Debug Current Test File" - Debug the currently open test file

### Common Issues

**"Flask app not running"**
```bash
python src/main.py
```

**"Docker containers not running"**
```bash
python analyzer/analyzer_manager.py start
```

**"Application not found"**
```bash
python scripts/diagnostics/check_db_apps.py
```

**"Import errors"**
```bash
pip install -r requirements.txt
```

---

## 📊 Diagnostic Scripts

Use scripts in `scripts/diagnostics/` for troubleshooting:

| Script | Purpose |
|--------|---------|
| `check_apps.py` | List applications via API |
| `check_db_apps.py` | Verify database applications |
| `check_tasks.py` | Check task status |
| `check_tools.py` | Verify tool registry |
| `check_env.py` | Check environment config |
| `verify_container_tools.py` | Test Docker tool availability |

```bash
python scripts/diagnostics/check_tasks.py
python scripts/diagnostics/verify_container_tools.py
```

---

## 🔨 Maintenance Scripts

Scripts in `scripts/maintenance/` for admin tasks:

```bash
# Clean up old tasks
python scripts/maintenance/cleanup_old_tasks.py

# Reaggregate task results
python scripts/maintenance/reaggregate_task.py <task_id>
python scripts/maintenance/reaggregate_all_tasks.py

# Demo Bearer token operations
python scripts/maintenance/demo_bearer_token_operations.py

# Quick analysis creation
python scripts/maintenance/quick_create_analysis.py
```

---

## 📚 Related Documentation

- **Testing Architecture**: `docs/knowledge_base/testing/README.md`
- **API Authentication**: `docs/API_AUTH_AND_METHODS.md`
- **Analysis Workflow**: `docs/ANALYSIS_WORKFLOW_TESTING.md`
- **Test Reports**: `docs/knowledge_base/testing/reports/`

---

**Last Updated**: 2025-11-01  
**Status**: Reorganized and pytest-integrated ✅
