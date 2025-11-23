# Template System

This directory contains Jinja2 templates for generating AI prompts.

## Structure

```
templates/
└── two-query/
    ├── backend.md.jinja2           # Full backend template
    └── frontend.md.jinja2          # Full frontend template
```

## Template Types

### two-query
A two-step generation approach:
1. **Backend First**: Generate backend code with API endpoints
2. **Frontend Second**: Generate frontend that consumes the backend API

### Template Selection
The generation service uses the standard full templates for all models to ensure consistent quality and detailed instructions.

## Template Variables

Templates have access to these variables from requirements JSON files:

### From Requirements
- `app_id` - Unique identifier (e.g., "xsd_verifier")
- `name` - Display name (e.g., "XSD Validator")
- `description` - App description
- `backend_requirements` - List of backend feature requirements
- `frontend_requirements` - List of frontend UI requirements

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

- Keep templates focused on clear instructions
- Include scaffolding code in the prompts
- Provide specific patterns and guidelines
- Ensure templates work with variable content lengths
- Test templates with different requirement sets
