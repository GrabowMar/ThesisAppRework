# Quick Test Reference Card

## 🚀 Quick Start

### Run All Tests (20 seconds)
```bash
python run_system_tests.py
```

### Run Specific Test File
```bash
pytest tests/test_web_ui_integration.py -v
pytest tests/test_analyzer_docker.py -v
```

### Run VS Code Task
```
Terminal → Run Task → "pytest - fast (no integration/slow/analyzer)"
```

---

## 📊 Test Coverage

| Category | Tests | Status |
|----------|-------|--------|
| Authentication | 2 | ✅ |
| Analysis List/HTMX | 3 | ✅ |
| Create Form | 6 | ✅ |
| Docker Containers | 2 | ✅ |
| Database | 2 | ✅ |
| Result Storage | 2 | ✅ |
| Analyzer CLI | 2 | ✅ |
| Docker Ports | 5 | ✅ |
| Tool Registry | 3 | ✅ |
| Flask Integration | 2 | ✅ |
| **TOTAL** | **35** | **✅** |

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

## 🧪 Test Types

### Fast Tests (default)
```bash
pytest -m "not integration and not slow and not analyzer"
```
Runs in ~20 seconds, no external dependencies.

### All Tests
```bash
pytest
```
Includes integration, slow, and analyzer tests.

### Specific Markers
```bash
pytest -m integration  # Database/API tests
pytest -m slow         # Tests >5 seconds
pytest -m analyzer     # Requires running analyzers
```

---

## 📝 Test Files

### `tests/test_web_ui_integration.py`
- Authentication (Bearer + session)
- Analysis list/HTMX endpoints
- Create form (custom tools + profiles)
- Docker analyzer verification
- Database application checks
- Result file system validation

### `tests/test_analyzer_docker.py`
- Analyzer manager CLI commands
- Docker container status/health
- Port accessibility (2001-2004)
- Container tool registry
- Result storage structure
- Flask app integration

### `run_system_tests.py`
- Prerequisites check (Flask + Docker)
- Test suite orchestration
- Summary reporting

---

## ✅ What's Validated

### Web UI
- ✅ Bearer token authentication
- ✅ Session cookie authentication
- ✅ Create form loads
- ✅ Custom tools submission
- ✅ Profile mode submission
- ✅ Form validation
- ✅ Task list loading (HTMX)

### Docker
- ✅ 4 containers running
- ✅ Health checks passing
- ✅ Ports accessible (2001-2004)
- ✅ Networks configured

### Database
- ✅ 8 applications exist
- ✅ Tasks recorded
- ✅ Proper slugs present

### File System
- ✅ Results directory exists
- ✅ Model directories present
- ✅ Task JSON files correct

---

## 🔍 Debugging Failed Tests

### "Flask app not running"
```bash
python src/main.py
```

### "Docker containers not running"
```bash
python analyzer/analyzer_manager.py start
```

### "Application not found"
```bash
python check_db_apps.py  # See valid model slugs
```

### "Import errors"
```bash
pip install -r requirements.txt
```

---

## 📚 Related Scripts

| Script | Purpose |
|--------|---------|
| `run_system_tests.py` | Main test runner |
| `check_db_apps.py` | List database apps |
| `quick_create_analysis.py` | Create analysis interactively |
| `verify_web_ui_with_token.py` | Bearer token verification |
| `demo_bearer_token_operations.py` | API usage examples |

---

## 🎯 Common Commands

```bash
# Quick health check
python run_system_tests.py

# Verbose output
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=html

# Stop on first failure
pytest tests/ -x

# Run specific test
pytest tests/test_web_ui_integration.py::TestAuthenticationFlow::test_bearer_token_valid -v

# Show print statements
pytest tests/ -s

# Run last failed
pytest --lf
```

---

## 🐛 Known Issues

None! All 35/35 tests passing ✅

---

## 📖 Full Documentation

See `SYSTEM_HEALTH_VERIFICATION.md` for comprehensive details.

---

**Last Updated**: 2025-11-01  
**Status**: All Systems Operational ✅
