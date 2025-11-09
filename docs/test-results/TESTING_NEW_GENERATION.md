# Testing the New Generation System

## Quick Start: Generate a Test App

### Option 1: Via Web UI
1. Start Flask app: `python src/main.py`
2. Navigate to Sample Generator wizard
3. Select a template (e.g., `auth_user_login`)
4. Select a model (e.g., `openai/gpt-4o-mini`)
5. Click "Generate"
6. Check generated app in `generated/apps/{model}/app{number}/`

### Option 2: Via API
```bash
# Using PowerShell
$body = @{
    template_slug = "auth_user_login"
    model_slug = "openai_gpt-4o-mini"  
    app_num = 9999
    generate_frontend = $true
    generate_backend = $true
    scaffold = $true
} | ConvertTo-Json

Invoke-RestMethod -Method POST -Uri "http://localhost:5000/api/gen/generate" `
    -Headers @{"Content-Type"="application/json"; "Authorization"="Bearer YOUR_TOKEN"} `
    -Body $body
```

### Option 3: Direct Python
```python
import asyncio
from src.app.services.generation import get_generation_service

async def test():
    service = get_generation_service()
    result = await service.generate_full_app(
        model_slug='openai_gpt-4o-mini',
        app_num=9999,
        template_slug='auth_user_login',
        generate_frontend=True,
        generate_backend=True
    )
    print(f"Success: {result['success']}")
    print(f"Backend: {result['backend_generated']}")
    print(f"Frontend: {result['frontend_generated']}")
    print(f"App dir: {result['app_dir']}")
    
asyncio.run(test())
```

## What to Check

### 1. Generated Backend (`generated/apps/{model}/app{N}/backend/app.py`)
```python
# Should have ALL of these:
✓ from flask import Flask, request, jsonify
✓ from flask_cors import CORS  
✓ from flask_sqlalchemy import SQLAlchemy
✓ import os, logging
✓ app = Flask(__name__)
✓ CORS(app)
✓ db = SQLAlchemy()
✓ class User(db.Model): ...
✓ def setup_app(app): ...
✓ @app.route('/health')
✓ @app.route('/api/...')
✓ @app.errorhandler(404)
✓ @app.errorhandler(500)
✓ if __name__ == '__main__':
    if 'setup_app' in globals():
        setup_app(app)
    port = int(os.environ.get('FLASK_RUN_PORT', ...))
    app.run(host='0.0.0.0', port=port)
```

### 2. Generated Frontend (`generated/apps/{model}/app{N}/frontend/src/App.jsx`)
```javascript
// Should have ALL of these:
✓ import React, { useState, useEffect } from 'react';
✓ import axios from 'axios';
✓ import 'bootstrap/dist/css/bootstrap.min.css';
✓ import './App.css';
✓ const API_URL = 'http://backend:5000';  // NOT localhost!
✓ function App() { ... }
✓ export default App;
```

### 3. Dependencies Updated
```bash
# Check requirements.txt has new packages
cat generated/apps/{model}/app{N}/backend/requirements.txt

# Should include (based on what LLM generated):
Flask==3.0.0
Flask-CORS==4.0.0
Flask-SQLAlchemy==3.1.1
bcrypt==4.1.2        # if using password hashing
PyJWT==2.8.0         # if using JWT tokens
```

## Testing Docker Build

```bash
cd generated/apps/{model}/app{N}

# Build
docker compose build

# Check for errors
# Should see: "✓ app.py syntax check passed"
# Should see: "✓ Flask app imports successfully"

# Run
docker compose up -d

# Check health
curl http://localhost:{BACKEND_PORT}/health
# Should return: {"status":"healthy","service":"backend"}

# Check frontend
curl http://localhost:{FRONTEND_PORT}
# Should return HTML with React app

# View logs
docker compose logs backend
docker compose logs frontend

# Stop
docker compose down
```

## Common Issues and Fixes

### Issue: Backend missing Flask app init
**Cause**: LLM ignored prompt or old prompt was cached
**Fix**: Check `misc/templates/two-query/backend.md.jinja2` is updated
**Workaround**: Manually add to generated file:
```python
app = Flask(__name__)
CORS(app)
```

### Issue: Frontend uses localhost instead of backend:5000
**Cause**: Auto-replacement regex failed
**Fix**: Check merge_frontend() method has localhost→backend replacement
**Workaround**: Manually edit API_URL in App.jsx

### Issue: Generated code truncated
**Cause**: Hit model's max_tokens limit
**Fix**: Increase max_tokens in MODEL_MAX_TOKENS dict in generation.py
**Workaround**: Use a model with larger context window

### Issue: Import errors (e.g., safe_str_cmp)
**Cause**: LLM generated code for older library versions
**Fix**: Update requirements.txt or regenerate with better prompt
**Note**: This is expected - LLM knowledge cutoff may be outdated

## Logs to Check

### Generation Logs
```python
# Look for these in console or logs/app.log:
"Starting simplified backend merge (direct overwrite)..."
"Extracted {N} chars of Python code from LLM response"
"✓ Wrote {N} chars to {path}"
"Inferred {N} backend dependencies: [...]"
```

### Success Indicators
```
✅ Backend merge succeeded
✅ Frontend merge succeeded  
✓ Added {N} dependencies to backend requirements
```

### Failure Indicators
```
❌ No Python code block found in generation response
❌ Backend code validation failed
❌ Target app.py missing
```

## Performance Metrics

Track these for regression testing:
- Time to scaffold: < 2 seconds
- Time to generate backend: 5-30 seconds (model dependent)
- Time to generate frontend: 5-30 seconds (model dependent)
- Time to merge code: < 1 second
- Docker build time: 30-120 seconds
- Container startup: < 10 seconds

## Regression Tests

Before deploying, verify:
1. Generate 5 different apps with 3 different models
2. All should have complete Flask initialization
3. All should have if __name__ block
4. All frontends should use backend:5000
5. All should build in Docker successfully
6. At least 80% should start containers without errors

## Next: Batch Testing

Create script to test multiple apps:
```python
# test_batch_generation.py
models = ['openai/gpt-4o-mini', 'anthropic/claude-3-haiku']
templates = ['auth_user_login', 'crud_todo_list', 'api_url_shortener']

for model in models:
    for template in templates:
        # Generate
        # Verify completeness
        # Build Docker
        # Report results
```
