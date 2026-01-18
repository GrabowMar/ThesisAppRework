# Template System

This directory contains Jinja2 templates for generating AI prompts.

## Structure

```
templates/
├── four-query/
│   ├── backend_user.md.jinja2      # Query 1: models + user routes
│   ├── backend_admin.md.jinja2     # Query 2: admin routes (uses models from Q1)
│   ├── frontend_user.md.jinja2     # Query 3: user page + API functions
│   └── frontend_admin.md.jinja2    # Query 4: admin page + admin API functions
├── two-query/
│   ├── backend.md.jinja2           # Legacy fallback (backend)
│   └── frontend.md.jinja2          # Legacy fallback (frontend)
└── unguarded/
    ├── backend.md.jinja2           # Single-file backend prompt
    ├── frontend.md.jinja2          # Minimal-file frontend prompt
    └── fullstack.md.jinja2         # Fullstack unguarded prompt (optional)
```

## Template Types

### four-query (recommended)
A four-step, single-file generation approach:
1. Backend user prompt → generates complete `app.py` (models + user routes + auth)
2. Backend admin prompt → merges admin routes into same `app.py`
3. Frontend user prompt → generates complete `App.jsx` (all components + HomePage + LoginPage + auth)
4. Frontend admin prompt → merges AdminPage into same `App.jsx`

**Single-File Architecture:**
- Backend: ONE `app.py` file with ALL code (~500-800 lines)
- Frontend: ONE `App.jsx` file with ALL code (~600-900 lines)
- Simpler for LLMs - no file splitting or complex imports

The HomePage (in App.jsx) serves **both public and logged-in users** via conditional rendering:
- Public users: read-only view of ALL data with "Sign in" CTAs
- Logged-in users: same content + create/edit/delete buttons + additional features

### two-query
A two-step generation approach:
1. **Backend First**: Generate backend code with API endpoints
2. **Frontend Second**: Generate frontend that consumes the backend API

### unguarded
Looser prompts intended for simpler “single-file/minimal-file” generation where scaffolding rules differ.

### Template Selection
The generation service prefers the 4-query templates in guarded mode for consistent quality and strong constraint enforcement.
The 2-query templates remain as a backward-compatible fallback.

## Template Variables

Templates have access to these variables from requirements JSON files:

### From Requirements
- `slug` - Unique identifier matching the requirements filename (e.g., "crud_todo_list")
- `name` - Display name (e.g., "XSD Validator")
- `description` - App description
- `backend_requirements` - List of backend feature requirements
- `frontend_requirements` - List of frontend UI requirements
- `admin_requirements` - List of admin feature requirements (guarded Query 2/4)
- `api_endpoints` - Pre-formatted endpoint list text for user endpoints
- `admin_api_endpoints` - Pre-formatted endpoint list text for admin endpoints

### From Scaffolding
- `scaffolding_app_py` - Backend app.py content
- `scaffolding_requirements_txt` - Backend requirements.txt
- `scaffolding_package_json` - Frontend package.json
- `scaffolding_index_html` - Frontend index.html
- `scaffolding_app_jsx` - Frontend App.jsx
- `scaffolding_app_css` - Frontend App.css
- `scaffolding_vite_config` - Frontend vite.config.js
- `scaffolding_main_jsx` - Frontend main.jsx

## Usage

These templates are rendered by the generation service:

```python
from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader('misc/templates'))
template = env.get_template('two-query/backend.md.jinja2')
prompt = template.render(
    name="My App",
    description="App description",
    backend_requirements=["Feature 1", "Feature 2"],
    scaffolding_app_py=scaffolding_code,
    # ... other variables
)
```

## Adding New Templates

1. Create a new directory under `templates/` (e.g., `templates/single-query/`)
2. Add Jinja2 template files (`.md.jinja2` extension)
3. Use the same template variables as shown above
4. Update the generation service to support the new template type

## Best Practices

- Keep templates focused on clear instructions and explicit output formats
- Use structured decomposition (models → routes → UI → validation)
- Include success criteria + common anti-patterns to reduce iteration
- Avoid “reasoning leakage”: allow internal planning but require code-only output
- Test templates across all requirement sets
