# ThesisAppRework

This repo hosts a Flask web app plus a containerized analyzer stack for evaluating generated apps.

## 🚀 Quick Start

- **Start Flask app**: `python src/main.py` (port 5000)
- **Start analyzers**: `python analyzer/analyzer_manager.py start`
- **Run tests**: `pytest -m "not integration and not slow and not analyzer"` (fast unit tests)
- **Smoke tests**: `pytest tests/smoke/ -v` (quick health check)

## 📂 Repository Structure

```
src/                    # Flask web application
analyzer/               # Containerized analyzer services (Docker)
tests/                  # Pytest test suite
  ├── smoke/           # Fast critical path tests
  ├── integration/     # Integration tests (api, websocket, analyzer, web_ui)
  ├── routes/          # Route unit tests
  └── services/        # Service unit tests
scripts/
  ├── diagnostics/     # Troubleshooting scripts (check_*.py, verify_*.py)
  └── maintenance/     # Admin scripts (cleanup, reaggregation, demos)
docs/                   # Documentation
  ├── guides/          # User and developer guides
  ├── knowledge_base/  # Architecture, testing, operations
  └── reference/       # API, CLI, database reference
generated/              # Generated applications to analyze
results/                # Analysis results and findings
```

## 📚 Documentation

- **Quick start**: `docs/README.md`
- **Testing guide**: `docs/guides/QUICK_TEST_GUIDE.md`
- **Agent guidance**: `.github/copilot-instructions.md` (architecture, workflows, conventions)
- **API authentication**: `docs/API_AUTH_AND_METHODS.md`
- **Analysis workflow**: `docs/ANALYSIS_WORKFLOW_TESTING.md`

## 🧪 Testing

### VS Code Integration
- Open Testing panel (Ctrl+Shift+T) for interactive test discovery
- Use "Terminal → Run Task" for predefined test suites
- Debug tests with Run & Debug panel (Ctrl+Shift+D)

### Common Test Commands
```bash
pytest -m "not integration and not slow"  # Fast unit tests (~5s)
pytest tests/smoke/                       # Smoke tests (~10s)
pytest tests/integration/api/             # API integration tests
pytest tests/integration/analyzer/        # Analyzer tests
pytest -m "integration and api"           # Combined markers
```

See `docs/guides/QUICK_TEST_GUIDE.md` for complete testing documentation.

## 🔧 Diagnostic Tools

```bash
python scripts/diagnostics/check_tasks.py          # Check task status
python scripts/diagnostics/check_db_apps.py        # Verify database apps
python scripts/diagnostics/verify_container_tools.py  # Test Docker tools
```

## 🔨 Maintenance

```bash
python scripts/maintenance/cleanup_old_tasks.py    # Clean up old tasks
python scripts/maintenance/reaggregate_all_tasks.py  # Reaggregate results
```

