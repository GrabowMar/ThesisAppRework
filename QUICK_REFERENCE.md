# Quick Reference: Analysis Methods

## Three Ways to Trigger Analysis

### 1️⃣ CLI (No Auth) 🚀 FASTEST
```bash
python analyzer/analyzer_manager.py analyze openai_codex-mini 1 security --tools bandit
```
✅ No authentication  
✅ Direct access  
❌ No UI visibility  

---

### 2️⃣ UI (Session Auth) 🖥️ USER-FRIENDLY
```
http://localhost:5000/analysis/create
Login: admin / (password from .env)
```
✅ User-friendly  
✅ Real-time progress  
❌ Manual only  

---

### 3️⃣ API (Bearer Token) 🔐 AUTOMATION
```bash
curl -X POST http://localhost:5000/api/analysis/run \
  -H "Authorization: Bearer $API_KEY_FOR_APP" \
  -H "Content-Type: application/json" \
  -d '{"model_slug": "openai_codex-mini", "app_number": 1, "tools": ["bandit"]}'
```
✅ Scriptable  
✅ Automated  
❌ Token required  

---

## API Endpoints

### Primary
```
POST /api/analysis/run
{
  "model_slug": "openai_codex-mini",
  "app_number": 1,
  "analysis_type": "security",
  "tools": ["bandit"],
  "priority": "normal"
}
```

### Alternative
```
POST /api/app/{model_slug}/{app_number}/analyze
{
  "analysis_type": "security",
  "tools": ["bandit"]
}
```

---

## Token Management

### Generate (via UI)
```
User Menu → API Access → Generate Token
```

### Generate (via API after login)
```bash
curl -X POST http://localhost:5000/api/tokens/generate \
  -H "Cookie: session=YOUR_SESSION"
```

### Verify
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:5000/api/tokens/verify
```

### Revoke
```bash
curl -X POST http://localhost:5000/api/tokens/revoke \
  -H "Authorization: Bearer $TOKEN"
```

---

## Result Files (All Methods)

### Location
```
results/{model_slug}/app{N}/task_{type}_{task_id}_{timestamp}/
```

### Files
- `{model}_{app}_task_{type}_{task_id}_{timestamp}.json` - Results
- `manifest.json` - Metadata

### Tool Results
```json
{
  "tool_results": {
    "static-analyzer_bandit": {...},
    "static-analyzer_safety": {...},
    "performance-tester_ab": {...},
    "dynamic-analyzer_zap": {...},
    "ai-analyzer_requirements-scanner": {...}
  }
}
```

---

## Prerequisites

### Start Services
```bash
# Flask app (Terminal 1)
cd src && python main.py

# Analyzers (Terminal 2)
python analyzer/analyzer_manager.py start
```

### Check Health
```bash
# Flask
curl http://localhost:5000/health

# Analyzers
python analyzer/analyzer_manager.py health
```

---

## Troubleshooting

### 401 Unauthorized
```bash
# Regenerate token
# Visit: http://localhost:5000 → API Access → Generate Token
```

### 404 Not Found
```bash
# Check Flask is running
curl http://localhost:5000/health
```

### No Results
```bash
# Check analyzers
python analyzer/analyzer_manager.py health

# Restart analyzers
python analyzer/analyzer_manager.py stop
python analyzer/analyzer_manager.py start
```

---

## Environment Setup

### Required in `.env`
```bash
# API Token (generate via UI)
API_KEY_FOR_APP=your-48-char-token-here

# Admin credentials
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-secure-password

# Flask secret (generate: python -c "import secrets; print(secrets.token_hex(32))")
SECRET_KEY=your-64-char-hex-here
```

---

## Full Documentation
- 📘 API Guide: `docs/API_AUTH_AND_METHODS.md`
- 📗 Implementation: `docs/IMPLEMENTATION_SUMMARY_API_ENDPOINTS.md`
- 📕 API Reference: `docs/reference/API_REFERENCE.md`
- 📙 CLI Reference: `docs/reference/CLI.md`
