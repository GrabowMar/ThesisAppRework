## Architecture

ThesisAppRework is a platform for analyzing AI‑generated applications for security, performance, and code quality, with optional AI reviews.

Core components:

- Flask backend (routes, services, models, tasks)
- Celery worker for background jobs
- Redis for queues
- Dockerized analyzer microservices (static, dynamic, performance, AI)
- WebSocket gateway for live progress updates
- Bootstrap 5 + HTMX frontend (Jinja templates)

### Repository structure (high level)

- `src/app/` — Flask app (routes, services, models, tasks)
- `analyzer/` — Analyzer orchestration, Docker Compose, service management
- `analyzer/services/` — Individual analyzer microservices
- `results/` — Analysis outputs (JSON, timestamped)
- `generated/apps/` — AI‑generated apps for analysis
- `scripts/` — Utility scripts
- `docs/` — Documentation (this folder)

Important centralization:

- Paths and constants: `src/app/paths.py`, `src/app/constants.py`
- Configuration hierarchy: environment vars → `settings.py` → `config_manager.py`
- Service registration: `app/services/service_locator.py`
- Engine registry: `app/services/analysis_engines.py`
- App factory + extensions: `src/app/factory.py`

### Analyzer services

Each analyzer runs in its own container, communicates via the gateway, and writes results into `results/`. Ports by default:

- static‑analyzer (2001)
- dynamic‑analyzer (2002)
- performance‑tester (2003)
- ai‑analyzer (2004)
- gateway (8765)

### Generation system (new)

The old complex generator is deprecated. Use only the new simplified generator and `/api/gen/*` endpoints. See [SIMPLE_GENERATION_SYSTEM.md](./SIMPLE_GENERATION_SYSTEM.md).
