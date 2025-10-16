# Template System V2

This directory contains the new modular template system for AI code generation.

## Directory Structure

```
misc/
├── requirements/          # App requirement definitions (JSON)
│   ├── xsd_verifier.json
│   ├── base64_converter.json
│   └── todo_app.json
│
├── scaffolding/           # Minimal working code scaffolds
│   └── react-flask/
│       ├── backend/
│       │   ├── app.py
│       │   └── requirements.txt
│       └── frontend/
│           ├── package.json
│           ├── index.html
│           └── src/
│               ├── App.jsx
│               └── App.css
│
└── templates/             # Jinja2 prompt templates
    └── two-query/
        ├── backend.md.jinja2
        └── frontend.md.jinja2
```

## How It Works

### 1. Requirements (JSON)
Define what the app should do in a structured JSON format:

```json
{
  "app_id": "xsd_verifier",
  "name": "XSD Validator",
  "description": "A tool to validate XML documents against XSD schemas",
  "backend_requirements": [
    "Accept XML file upload via POST endpoint",
    "Validate XML against provided XSD schema",
    ...
  ],
  "frontend_requirements": [
    "Form to upload XML file",
    "Display validation results",
    ...
  ]
}
```

### 2. Scaffolding
Minimal, working starter code that does nothing but runs:

**Backend** (`scaffolding/react-flask/backend/app.py`):
- Basic Flask app with health check endpoint
- Runs on port 5000

**Frontend** (`scaffolding/react-flask/frontend/`):
- Basic React + Vite setup
- Connects to backend health check
- Runs on port 5173

### 3. Templates (Jinja2)
Prompt templates that combine requirements + scaffolding:

**Backend Template** (`templates/two-query/backend.md.jinja2`):
```markdown
# Goal: Generate {{ name }}

## Requirements
{% for req in backend_requirements %}
- {{ req }}
{% endfor %}

## Scaffolding
```python
{{ scaffolding_app_py }}
```
...
```

### 4. Generation Flow

1. **Select Requirements**: Choose from `requirements/*.json`
2. **Load Scaffolding**: Load files from `scaffolding/react-flask/`
3. **Render Template**: Combine requirements + scaffolding into prompt
4. **Send to Model**: Backend first, then frontend
5. **Extract Code**: Parse model response and save files

## API Usage

### List Available Requirements
```bash
GET /api/v2/templates/requirements
```

### Preview Templates
```bash
POST /api/v2/templates/preview
{
  "requirement_id": "xsd_verifier",
  "scaffolding_type": "react-flask",
  "template_type": "two-query"
}
```

### Generate Backend
```bash
POST /api/v2/templates/generate/backend
{
  "requirement_id": "xsd_verifier",
  "model": "openai/gpt-4",
  "scaffolding_type": "react-flask",
  "template_type": "two-query"
}
```

## Adding New Apps

### 1. Create Requirements JSON
Create `misc/requirements/my_app.json`:
```json
{
  "app_id": "my_app",
  "name": "My App",
  "description": "What my app does",
  "backend_requirements": ["Feature 1", "Feature 2"],
  "frontend_requirements": ["UI 1", "UI 2"]
}
```

### 2. Generate Code
The system will automatically:
- Inject requirements into templates
- Include scaffolding code
- Send to AI model
- Extract and save generated code

## Template Variables

Templates have access to these variables:

**From Requirements JSON:**
- `app_id` - Unique identifier
- `name` - Display name
- `description` - App description
- `backend_requirements` - List of backend features
- `frontend_requirements` - List of frontend features

**From Scaffolding:**
- `scaffolding_app_py` - Backend app.py content
- `scaffolding_requirements_txt` - Backend requirements.txt
- `scaffolding_package_json` - Frontend package.json
- `scaffolding_index_html` - Frontend index.html
- `scaffolding_app_jsx` - Frontend App.jsx
- `scaffolding_app_css` - Frontend App.css

## Benefits Over Old System

✅ **Modular**: Requirements, scaffolding, templates are separate
✅ **Reusable**: Same scaffolding for all apps
✅ **Dynamic**: Jinja2 allows flexible template logic
✅ **Maintainable**: Change scaffolding once, affects all generations
✅ **Scalable**: Easy to add new requirements, scaffolding types, templates

## Migration Notes

- Old system: `misc/app_templates/` - **Removed**
- Old system: `misc/code_templates/` - **Removed**
- New system: Structured in `requirements/`, `scaffolding/`, `templates/`
- Legacy compatibility: Not maintained, clean break for better architecture
