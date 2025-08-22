# Thesis App Platform

This repository hosts the Flask-based research platform and associated analyzer microservices for generating, running, and analyzing AI-generated web applications.

## Application Containerization

Each generated model application lives under `misc/models/{model_slug}/app{N}` with a `docker-compose.yml` defining two services:

- `<normalized_model>_app{N}_backend`
- `<normalized_model>_app{N}_frontend`

Normalization: replace `/` and `-` with `_` in the model slug.

### Port Assignment

Ports are centrally stored in the database (table `port_configuration`) and mirrored in `misc/port_config.json` for fallback. Each record supplies:

```json
{
  "{model_slug}_{N}": {"backend": <backend_port>, "frontend": <frontend_port>}
}
```

Backend and frontend containers expose the same internal port number they are bound to externally (no translation). The backend Flask app reads `APP_PORT` (injected via compose) so the code is not regenerated per port.

### Container Naming Convention

We standardized container names (removed legacy trailing port suffix):

```
{normalized_model}_app{N}_backend
{normalized_model}_app{N}_frontend
```

Use `ContainerNames.get_container_name(model, app_num, ContainerNames.BACKEND|FRONTEND)` in server code to avoid string drift.

### Build & Start a Specific App

Use the helper script:

```bash
python scripts/build_start_app.py --model anthropic_claude-3.7-sonnet --app 1 --rebuild
```

This will:
1. Resolve ports from DB (or fallback JSON)
2. Run `docker compose build` (with `--no-cache` if `--rebuild` specified)
3. Start containers detached

### Stopping Containers

From the app directory:
```bash
cd misc/models/anthropic_claude-3.7-sonnet/app1
docker compose down
```

### Verifying Runtime

- Backend: `curl http://localhost:<backend_port>/`
- Frontend: open `http://localhost:<frontend_port>/`

### Regenerating Apps

Existing generation scripts (`misc/generateApps.py`, `misc/generateOutputs.py`) still contain the legacy port computation logic. For now we "trust the DB"; do **not** recompute new ports unless explicitly migrating. Future enhancement: make generation scripts read `port_config.json` strictly instead of recomputing.

## Template Diagnostics (Pending)

A forthcoming test will directly render `comprehensive_start_result.html` to ensure native loader resolution (historically a fallback HTML bypass existed).

## Analyzer Integration (Summary)

Analyzer services (security, performance, dynamic/ZAP, AI) run via separate docker-compose in `analyzer/`. The Flask app communicates through the analyzer integration layer and Celery tasks.

## Quick Development Loop

```bash
# Start only Flask (from src/)
./start.ps1 flask-only

# Run tests (root)
pytest -q

# Build & run one generated app
python scripts/build_start_app.py --model anthropic_claude-3.7-sonnet --app 1
```

## Next Documentation Enhancements
- Add section covering comprehensive analysis orchestration flow
- Add template troubleshooting log examples
- Replace hard-coded port references in UI templates with context-driven values

---
For detailed analyzer operations see `analyzer/README.md`.
