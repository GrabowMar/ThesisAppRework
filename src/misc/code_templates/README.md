# Code Templates Directory

Canonical location for scaffolding code templates used by the sample generation and app scaffolding services.

## Structure
- `backend/` Flask backend skeleton (app.py.template, requirements.txt, Dockerfile.template)
- `frontend/` React/Vite frontend skeleton (package.json.template, vite.config.js.template, index.html.template, Dockerfile.template, src/App.jsx.template, src/App.css)
- `docker-compose.yml.template` model/app compose baseline

## Placeholders
Templates now use double-brace placeholders:
- `{{model_name}}`
- `{{model_name_lower}}`
- `{{model_prefix}}`
- `{{backend_port}}`
- `{{frontend_port}}`
- `{{port}}` (contextual: backend or frontend depending on file path)

These are resolved by `ProjectOrganizer` or `AppScaffoldingService`.

## Deprecations
The previously nested `code_templates/code_templates` directory is deprecated and will be ignored by tests. Remove it entirely if still present.
