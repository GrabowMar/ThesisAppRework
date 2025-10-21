## Quickstart

This guide gets you running ThesisAppRework fast, either locally or fully containerized. Windows commands are shown with PowerShell; Linux/macOS are equivalent.

### Prerequisites

- Python 3.12+
- Node.js (only needed when working with generated frontend apps)
- Docker Desktop (for analyzer microservices)
- Git

### Option A: Local app (no analyzers)

1) Create a virtual environment and install deps

```powershell
# from repo root
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

2) Initialize local SQLite DB (loads models via factory)

```powershell
cd src
python init_db.py
```

3) Run the Flask app (Celery optional for most pages)

```powershell
# In one terminal
cd src
python main.py

# Optional: Celery worker (for background tasks)
# celery -A app.tasks worker --loglevel=info
```

App runs at http://localhost:5000

### Option B: Full stack with analyzers

Analyzer services (static, dynamic, performance, AI) are containerized and managed by the analyzer manager.

```powershell
# from repo root
python analyzer/analyzer_manager.py start        # start redis, gateway, analyzer services
python analyzer/analyzer_manager.py health       # check health
python analyzer/analyzer_manager.py logs web 50  # example: tail logs
```

Run the Flask app separately as in Option A step 3.

### Environment

- Copy `.env.example` to `.env` (if present) or create `.env` with at least:
  - SECRET_KEY=your_random_key
  - OPENROUTER_API_KEY=... (only needed for AI analysis)
- Environment is auto-loaded by `src/app/factory.py`.

### Smoke checks

```powershell
# quick pytest run (Windows task exists in VS Code)
. .\.venv\Scripts\Activate.ps1
pytest -q

# HTTP smoke
python scripts/http_smoke.py
```

### Common workflows

- Start/Stop analyzers, run an analysis, list results: see [OPERATIONS.md](./OPERATIONS.md)
- Generate a sample app with the new generator: see [SIMPLE_GENERATION_SYSTEM.md](./SIMPLE_GENERATION_SYSTEM.md)
