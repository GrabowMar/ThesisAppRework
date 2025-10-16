# Simple Generation System

## Overview

The sample generator backend has been completely reimplemented with a focus on simplicity, reliability, and proper scaffolding integration.

## Architecture

### Old System (3700+ lines, BROKEN)
- ❌ Overcomplicated service with too many responsibilities
- ❌ Broken scaffolding that doesn't copy templates correctly  
- ❌ Complex port replacement logic that fails
- ❌ Multiple file numbering (index_02.html, package_01.json)
- ❌ Missing Docker infrastructure files
- ❌ Unreliable code extraction with validation layers

### New System (Clean & Simple)
- ✅ **Simple Service**: `simple_generation_service.py` (~400 lines)
  - Does ONE thing well: generate code via AI and save it
  - Clean separation of concerns
  - Predictable file organization

- ✅ **Simple API**: `simple_generation.py` 
  - Clear, focused endpoints
  - No complex workflows
  - Direct responses

- ✅ **Proper Scaffolding**: Uses `misc/scaffolding/react-flask/` templates
  - Copies ALL files exactly as-is
  - Correct placeholder substitution: `{{backend_port|5000}}` → actual port
  - Creates complete Docker infrastructure
  - No file duplication

## How It Works

### 1. Scaffolding (`/api/gen/scaffold`)

```bash
POST /api/gen/scaffold
{
  "model_slug": "x-ai/grok-code-fast-1",
  "app_num": 1,
  "force": false
}
```

**What it does:**
1. Creates directory: `generated/apps/x-ai_grok-code-fast-1/app1/`
2. Copies ALL files from `misc/scaffolding/react-flask/`:
   - `docker-compose.yml`
   - `backend/Dockerfile`
   - `backend/.dockerignore`
   - `backend/requirements.txt` (template)
   - `frontend/Dockerfile`
   - `frontend/nginx.conf`
   - `frontend/vite.config.js` (template with port)
   - `frontend/.dockerignore`
   - `.env.example`
3. Replaces placeholders:
   - `{{backend_port|5000}}` → `5001` (for app1)
   - `{{frontend_port|8000}}` → `8001` (for app1)
   - Other environment variables

### 2. Code Generation (`/api/gen/generate`)

```bash
POST /api/gen/generate
{
  "template_id": 1,
  "model_slug": "x-ai/grok-code-fast-1",
  "app_num": 1,
  "component": "frontend",  // or "backend"
  "temperature": 0.3,
  "max_tokens": 16000,
  "scaffold": true
}
```

**What it does:**
1. Scaffolds app (if `scaffold: true`)
2. Loads template from `misc/app_templates/app_1_frontend_*.md`
3. Sends to OpenRouter API with proper system prompt
4. Extracts code blocks from AI response
5. Saves to appropriate files:
   - **Frontend**: `frontend/src/App.jsx`, `frontend/src/main.jsx`, etc.
   - **Backend**: `backend/app.py`, `backend/requirements.txt`, etc.

### 3. Full Generation (`/api/gen/generate-full`)

```bash
POST /api/gen/generate-full
{
  "template_id": 1,
  "model_slug": "x-ai/grok-code-fast-1",
  "app_num": 1,
  "temperature": 0.3,
  "generate_frontend": true,
  "generate_backend": true
}
```

**What it does:**
1. Scaffolds app
2. Generates frontend (separate API call)
3. Generates backend (separate API call)
4. Returns combined results

## Port Allocation

Simple, predictable formula:
- Backend port: `5001 + (app_num * 2)`
- Frontend port: `8001 + (app_num * 2)`

Examples:
- App 1: backend=5001, frontend=8001
- App 2: backend=5003, frontend=8003
- App 3: backend=5005, frontend=8005

## File Organization

### Expected Structure After Generation

```
generated/apps/x-ai_grok-code-fast-1/app1/
├── docker-compose.yml          ← Scaffolding (with ports)
├── .env.example                ← Scaffolding
├── backend/
│   ├── Dockerfile              ← Scaffolding
│   ├── .dockerignore           ← Scaffolding
│   ├── app.py                  ← AI Generated
│   └── requirements.txt        ← AI Generated or scaffolding
└── frontend/
    ├── Dockerfile              ← Scaffolding
    ├── .dockerignore           ← Scaffolding
    ├── nginx.conf              ← Scaffolding
    ├── vite.config.js          ← Scaffolding (with port 8001)
    ├── package.json            ← AI Generated or scaffolding
    ├── index.html              ← AI Generated or scaffolding
    └── src/
        ├── App.jsx             ← AI Generated
        ├── App.css             ← AI Generated or scaffolding
        └── main.jsx            ← AI Generated or scaffolding
```

## Code Extraction Logic

Simple pattern matching:
1. Find all \`\`\`language code blocks
2. Determine file based on:
   - Language (python, jsx, html, css, json)
   - Code patterns (Flask imports, React imports, etc.)
   - Component type (frontend vs backend)
3. Save to ONE file per type (no numbering)

### Frontend Files
- **JSX with `export default` + function** → `frontend/src/App.jsx`
- **JSX with `ReactDOM.createRoot`** → `frontend/src/main.jsx`
- **HTML with `<!DOCTYPE>`** → `frontend/index.html`
- **CSS** → `frontend/src/App.css`
- **JSON with package info** → `frontend/package.json`

### Backend Files
- **Python with `Flask` or `app = Flask`** → `backend/app.py`
- **Python without Flask** → `backend/main.py`
- **Text/requirements** → `backend/requirements.txt`

## Migration from Old System

### For Frontend Code
Update your JavaScript to use the new endpoints:

```javascript
// OLD (complex, broken)
fetch('/api/sample-gen/generate', {
  method: 'POST',
  body: JSON.stringify({
    template_id: 1,
    model: 'x-ai/grok-code-fast-1',
    create_backup: false,
    generate_frontend: true,
    generate_backend: true
  })
})

// NEW (simple, works)
fetch('/api/gen/generate-full', {
  method: 'POST',
  body: JSON.stringify({
    template_id: 1,
    model_slug: 'x-ai/grok-code-fast-1',
    app_num: 1,
    generate_frontend: true,
    generate_backend: true
  })
})
```

### Testing the New System

```bash
# 1. Scaffold an app
curl -X POST http://localhost:5000/api/gen/scaffold \
  -H "Content-Type: application/json" \
  -d '{"model_slug":"x-ai/grok-code-fast-1","app_num":1}'

# 2. Generate frontend
curl -X POST http://localhost:5000/api/gen/generate \
  -H "Content-Type: application/json" \
  -d '{
    "template_id":1,
    "model_slug":"x-ai/grok-code-fast-1",
    "app_num":1,
    "component":"frontend"
  }'

# 3. Generate backend
curl -X POST http://localhost:5000/api/gen/generate \
  -H "Content-Type: application/json" \
  -d '{
    "template_id":1,
    "model_slug":"x-ai/grok-code-fast-1",
    "app_num":1,
    "component":"backend"
  }'

# 4. List all apps
curl http://localhost:5000/api/gen/apps
```

## Benefits

1. **Reliable Scaffolding**: Docker infrastructure is always correct
2. **No File Duplication**: Each file type saved to ONE location
3. **Predictable Ports**: Simple formula, no complex allocation service
4. **Clean Code**: Easy to understand, maintain, and debug
5. **Simple API**: Clear, focused endpoints
6. **Separation of Concerns**: Each component does ONE thing

## Next Steps

1. Update frontend UI to use new `/api/gen/*` endpoints
2. Test with all models and templates
3. Remove old complex service after migration
4. Add batch generation support (if needed)

## Old System (Deprecated)

The old system remains available at `/api/sample-gen/*` endpoints but should not be used:
- ⚠️ `sample_generation_service.py` (3735 lines) - DO NOT USE
- ⚠️ `/api/sample-gen/*` endpoints - DO NOT USE

Use the new system at `/api/gen/*` instead.
