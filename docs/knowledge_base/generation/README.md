# Application Generation

## Quick Start

```bash
# Generate via CLI
python scripts/test_simple_generation.py

# Or via API
curl -X POST http://localhost:5000/api/gen/generate \
  -H "Content-Type: application/json" \
  -d '{"model": "openai_gpt-4", "template_id": 1, "app_name": "my-app"}'
```

## Architecture

### NEW Simple Generation System ✅

**Use ONLY**: `/api/gen/*` endpoints
- Clean, maintainable codebase
- Proper scaffolding from `misc/scaffolding/react-flask/`
- 5-step backend workflow + 16-point validation
- 8-step frontend workflow + 20-point validation
- Full Docker infrastructure included

**Location**: `src/app/services/simple_generation_service.py`

### OLD Complex System ❌ DEPRECATED

**DO NOT USE**: `/api/sample-gen/*` endpoints
- 3700+ line monolithic service
- Complex, hard-to-maintain code
- Being phased out

**Location**: `src/app/services/sample_generation_service.py` (deprecated)

## Generation Workflow

### Backend (Flask/SQLAlchemy)
1. **Template Selection**: Choose from 60+ enhanced templates
2. **Code Generation**: AI generates code with procedural guardrails
3. **Validation**: 16-point quality check (imports, routes, models, etc.)
4. **Scaffolding**: Docker files, configs from `misc/scaffolding/`
5. **Organization**: Proper file structure in `generated/apps/<id>/`

### Frontend (React/Vite)
1. **Project Init**: Create Vite project structure
2. **Component Generation**: AI creates React components
3. **Validation**: 20-point check (syntax, imports, hooks, etc.)
4. **Configuration**: Vite config, port allocation
5. **Containerization**: Dockerfile, nginx config

## Templates

Located in `misc/app_templates/`:
- **60+ enhanced templates** with procedural guardrails
- **Categories**: CRUD, API, Dashboard, E-commerce, etc.
- **Placeholders**: `{{backend_port|5000}}`, `{{frontend_port|8000}}`

### Template Structure
```python
{
    "id": 1,
    "name": "Task Manager",
    "description": "CRUD app with tasks",
    "backend_requirements": ["Flask-SQLAlchemy", "Flask-CORS"],
    "frontend_framework": "react",
    "code_template": "..."  # With {{placeholders}}
}
```

## Port Allocation

Automatic via `PortAllocationService`:
- **Backend**: 5001, 5002, 5003, ... (incremental)
- **Frontend**: 8001, 8002, 8003, ... (incremental)

Ports substituted during scaffolding in `ProjectOrganizer._scaffold_if_needed()`.

## Docker Infrastructure

All generated apps include:
```
generated/apps/<app_id>/
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app.py
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   └── src/
├── docker-compose.yml
├── .env
└── nginx.conf
```

### Backfill Existing Apps
```bash
python scripts/backfill_docker_files.py
```

## Validation

### Backend Checks
- Valid Python syntax
- Proper imports
- Flask routes defined
- SQLAlchemy models correct
- CORS configured
- Port placeholders replaced

### Frontend Checks
- Valid JSX/TypeScript syntax
- React imports present
- Component structure valid
- Hooks used correctly
- API calls configured
- Vite config present

## API Endpoints

### Generate Application
```bash
POST /api/gen/generate
{
  "model": "openai_gpt-4",
  "template_id": 1,
  "app_name": "my-app",
  "description": "Optional custom description"
}

Response: { "task_id": "...", "app_id": 123 }
```

### Check Progress
```bash
GET /api/gen/status/<task_id>
Response: { "status": "processing", "progress": 60 }
```

### Get Result
```bash
GET /api/gen/result/<app_id>
Response: { "app_id": 123, "files": [...], "ports": {...} }
```

## Troubleshooting

**Generation fails**: Check `logs/` for errors
**Port conflicts**: Restart port allocation service
**Validation errors**: Review generated code in `generated/apps/<id>/`
**Docker build fails**: Check Dockerfile syntax and dependencies

## Best Practices

1. **Use simple generation system** (`/api/gen/*`)
2. **Choose appropriate template** for use case
3. **Review generated code** before running
4. **Test in Docker** environment
5. **Monitor ports** to avoid conflicts
6. **Backup templates** have `.bak` extensions for rollback
