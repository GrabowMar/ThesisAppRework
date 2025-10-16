# Template System V2 - Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    Template System V2 Flow                       │
└─────────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Requirements │     │ Scaffolding  │     │  Templates   │
│    (JSON)    │     │   (Code)     │     │  (Jinja2)    │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                    │
       │                    │                    │
       └────────────┬───────┴────────────────────┘
                    │
                    ▼
         ┌────────────────────┐
         │ TemplateRenderer   │
         │    Service         │
         └─────────┬──────────┘
                   │
                   │ Combines & Renders
                   ▼
         ┌────────────────────┐
         │  Rendered Prompt   │
         │    (Markdown)      │
         └─────────┬──────────┘
                   │
                   │ Send to Model
                   ▼
         ┌────────────────────┐
         │   AI Model         │
         │  (GPT-4, etc.)     │
         └─────────┬──────────┘
                   │
                   │ Returns Code
                   ▼
         ┌────────────────────┐
         │ Generated Code     │
         │  (Flask + React)   │
         └────────────────────┘


┌─────────────────────────────────────────────────────────────────┐
│                      Component Details                           │
└─────────────────────────────────────────────────────────────────┘

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Requirements (JSON)                                            ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
  misc/requirements/
    ├── xsd_verifier.json      ← What the app should do
    ├── base64_converter.json
    └── todo_app.json

  Structure:
    {
      "app_id": "...",
      "name": "...",
      "description": "...",
      "backend_requirements": [...],
      "frontend_requirements": [...]
    }

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Scaffolding (Code)                                             ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
  misc/scaffolding/react-flask/
    ├── backend/
    │   ├── app.py              ← Minimal Flask app
    │   └── requirements.txt
    └── frontend/
        ├── package.json        ← Minimal React + Vite
        ├── index.html
        └── src/
            ├── App.jsx
            └── App.css

  Purpose: Working starter code that runs but does nothing

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Templates (Jinja2)                                             ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
  misc/templates/two-query/
    ├── backend.md.jinja2       ← Prompt template for backend
    └── frontend.md.jinja2      ← Prompt template for frontend

  Variables Available:
    - {{ name }}
    - {{ description }}
    - {% for req in backend_requirements %}
    - {{ scaffolding_app_py }}
    - ... etc

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ TemplateRenderer Service                                       ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
  src/app/services/template_renderer.py

  Methods:
    list_requirements()          → ['xsd_verifier', ...]
    load_requirements(id)        → { app_id, name, ... }
    load_scaffolding(type)       → { backend: {...}, frontend: {...} }
    render_template(...)         → "# Goal: Generate..."
    preview(...)                 → { backend: "...", frontend: "..." }

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ API Routes (V2)                                                ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
  src/app/routes/api/templates_v2.py

  Endpoints:
    GET  /api/v2/templates/requirements
    GET  /api/v2/templates/requirements/<id>
    GET  /api/v2/templates/scaffolding
    GET  /api/v2/templates/template-types
    POST /api/v2/templates/preview
    POST /api/v2/templates/render/<component>
    POST /api/v2/templates/generate/backend
    POST /api/v2/templates/generate/frontend


┌─────────────────────────────────────────────────────────────────┐
│                    Example: XSD Validator                        │
└─────────────────────────────────────────────────────────────────┘

1. Load xsd_verifier.json
   ↓
   {
     "name": "XSD Validator",
     "backend_requirements": [
       "Accept XML file upload",
       "Validate against XSD schema",
       ...
     ]
   }

2. Load react-flask scaffolding
   ↓
   {
     "backend": {
       "app_py": "from flask import Flask...",
       "requirements_txt": "Flask==3.0.0..."
     }
   }

3. Render backend.md.jinja2
   ↓
   # Goal: Generate a Secure Flask Application - XSD Validator
   
   ## Requirements
   1. Accept XML file upload
   2. Validate against XSD schema
   ...
   
   ## Scaffolding
   ```python
   from flask import Flask...
   ```

4. Send to GPT-4
   ↓
   [8,283 character prompt]

5. Receive Generated Code
   ↓
   app.py (with validation logic)
   requirements.txt (with lxml added)

6. Repeat for frontend
   ↓
   [11,892 character prompt]
   
7. Final Result
   ↓
   generated/apps/openai_gpt-4/app_N/
     ├── backend/
     │   ├── app.py
     │   └── requirements.txt
     └── frontend/
         ├── package.json
         ├── index.html
         └── src/
             ├── App.jsx
             └── App.css
```
