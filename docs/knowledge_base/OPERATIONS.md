## Operations

This page covers day‑to‑day commands and checks.

### Start/Stop analyzer stack

```powershell
# start containers (redis, gateway, analyzers)
python analyzer/analyzer_manager.py start

# health summary
python analyzer/analyzer_manager.py health

# view logs (examples)
python analyzer/analyzer_manager.py logs gateway 100
python analyzer/analyzer_manager.py logs static-analyzer 100

# stop everything
python analyzer/analyzer_manager.py stop
```

### Run an analysis

```powershell
# analyze a generated app with a selected model
python analyzer/analyzer_manager.py analyze <model> <appId> [type] [--tools ...]

# batch file example (JSON array of [model, appId])
python analyzer/analyzer_manager.py batch analyzer/batches/example.json

# list most recent results
python analyzer/analyzer_manager.py results
```

Outputs land in `results/` as timestamped JSON.

### Flask app

```powershell
# from repo root
cd src
python main.py

# optional: celery worker
# celery -A app.tasks worker --loglevel=info
```

### Health checks

- Web health endpoint: `GET /health` — checks database, Celery, analyzers
- CLI: `python analyzer/analyzer_manager.py health`

### Environment and secrets

- Create `.env` in repo root; it’s loaded by the app factory
- Important vars: `SECRET_KEY`, `OPENROUTER_API_KEY` (if using AI analysis)

### Troubleshooting tips

- Ensure Docker is running and required ports are free
- For analyzer issues: check gateway and specific analyzer logs
- For auth issues: confirm `SECRET_KEY` is set and database initialized
- For AI analysis: confirm OpenRouter API key and provider access
