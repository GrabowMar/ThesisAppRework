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

## Template Restructuring (2025-08)

The Jinja template layer was reorganized to simplify navigation and reduce deep nested folders.

### New High-Level Structure

```
src/templates/
  layouts/            # Base, dashboard, full-width, modal, etc.
  pages/              # Feature (domain) pages and their domain-scoped partials
    analysis/
    applications/
    models/
    batch/
    statistics/
    system/
    about/
    index/            # Former dashboard index page
  ui/
    elements/         # Reusable shared widgets
      common/
      navigation/
      forms/
      dashboard/
      misc/
  errors/
  RESTRUCTURE_MAPPING.json  # Generated report
```

Domain-specific components now live in `pages/<domain>/partials/`. Truly shared widgets moved to `ui/elements/` categorized by concern.

### Migration Script

Script: `scripts/restructure_templates.py`

Capabilities:
* Dry-run default — shows planned moves and reference rewrites
* Applies moves with `--apply` (creates timestamped backups under `src/templates/template_backups/<timestamp>/`)
* Updates `{% include %}` / `{% extends %}` paths and removes self-recursive includes
* Adds a slug header comment to migrated files for traceability
* Generates `RESTRUCTURE_MAPPING.json` containing mapping metadata
* Supports `--rollback <timestamp>` to restore from a backup

Examples:

```bash
# Preview changes
python scripts/restructure_templates.py

# Apply restructuring
python scripts/restructure_templates.py --apply

# Rollback (choose timestamp dir name from template_backups)
python scripts/restructure_templates.py --rollback 20250823_101530
```

### Updating Python References

If any Flask `render_template` calls referenced old paths (e.g. `views/analysis/list.html`), update them to the new path (`pages/analysis/list.html`). Most includes were automatically rewritten; search for the old prefixes to confirm nothing remains:

```bash
grep -R "views/" src/app || echo "No legacy view references"
```

### Rationale

Problems addressed:
* Too many parallel top-level buckets (`components`, `partials`, `fragments`, `views`)
* Difficulty locating domain-specific vs shared snippets
* Redundant self-including component templates

Benefits:
* Clear feature ownership (`pages/<domain>/*`)
* Easier to audit and prune unused shared widgets
* Simplified mental model for adding new partials

### Follow-Up Opportunities
* Introduce Jinja macros for repeated table / card patterns in `ui/macros/`
* Add unit tests that render critical templates to catch missing includes after future moves
* Create a linter script ensuring no new templates are added at root without classification

### Legacy Path Compatibility Wrapper

To minimize churn in Python route modules immediately after the restructure, a compatibility shim was added at `src/app/utils/template_paths.py`.

Key points:
* Provides `render_template_compat` which transparently remaps legacy template names using `RESTRUCTURE_MAPPING.json`.
* Heuristics also cover simple patterns (e.g. `views/` -> `pages/`, and the moved error partial).
* Context keys commonly storing partial paths (e.g. `main_partial`) are remapped automatically.

Usage pattern (inside a route file):

```python
from ..utils.template_paths import render_template_compat as render_template

return render_template('views/applications/index.html', **context)  # auto-remapped to pages/applications/index.html
```

Over time you can replace legacy paths with their canonical new counterparts and then optionally remove the shim once `grep` shows no `views/` or `partials/common/error.html` references remain.

