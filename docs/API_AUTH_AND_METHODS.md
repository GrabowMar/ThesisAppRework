# API Authentication & Analysis Methods

## Overview
This document explains how to trigger analysis using three different methods, all producing identical results.

## Prerequisites
1. **Flask App Running**: `cd src && python main.py` (port 5000)
2. **Analyzer Services Running**: `python analyzer/analyzer_manager.py start`
3. **User Account**: Create via `python scripts/create_admin.py`

---

## Method 1: CLI (No Authentication)

### Description
Direct command-line access via `analyzer_manager.py`. Bypasses Flask app entirely, no authentication needed.

### Usage
```bash
# Check analyzer health
python analyzer/analyzer_manager.py health

# Run security analysis with specific tool
python analyzer/analyzer_manager.py analyze openai_codex-mini 1 security --tools bandit

# Run comprehensive analysis (all tools)
python analyzer/analyzer_manager.py analyze openai_codex-mini 1 comprehensive

# Batch analysis
python analyzer/analyzer_manager.py batch batch.json
```

### Output
- Results written to: `results/{model_slug}/app{N}/task_{type}_{task_id}_{timestamp}/`
- Contains: `{model}_{app}_task_{type}_{task_id}_{timestamp}.json` (result file)
- Tool results: All 15 tools with service prefixes (e.g., `static-analyzer_bandit`)

### Pros
- No authentication required
- Direct access to analyzer services
- Fastest for automation/scripts
- Full WebSocket communication with containers

### Cons
- Bypasses Flask app (no database task tracking)
- No web UI visibility
- Results only on disk (not in database)

---

## Method 2: UI (Session Authentication)

### Description
Web form submission via `/analysis/create` endpoint. Uses Flask-Login session cookies.

### Authentication Setup
```bash
# 1. Start Flask app
cd src && python main.py

# 2. Login via browser
# Navigate to: http://localhost:5000/auth/login
# Credentials from .env:
#   Username: admin
#   Password: (value of ADMIN_PASSWORD in .env)
```

### Usage
1. **Navigate to Analysis Creation Wizard**:
   - URL: `http://localhost:5000/analysis/create`
   
2. **Select Application**:
   - Choose model (e.g., `openai_codex-mini`)
   - Choose app number (e.g., `1`)

3. **Choose Analysis Mode**:
   - **Profile Mode**: Pre-configured profiles (security, performance, quality)
   - **Custom Mode**: Select specific tools

4. **Submit Form**:
   - Creates `AnalysisTask` in database
   - Redirects to `/analysis/list`
   - Shows real-time progress

### Output
- Database record: `AnalysisTask` with full metadata
- Result files: Same structure as CLI (`results/{model}/app{N}/...`)
- UI visibility: Task list, progress tracking, result viewing

### Pros
- Full database tracking
- Real-time progress updates (WebSocket)
- Web UI for result viewing
- User-friendly interface

### Cons
- Requires browser session
- Manual form submission
- Not suitable for automation

---

## Method 3: API (Bearer Token Authentication)

### Description
RESTful API endpoints using Bearer token authentication. Ideal for automation and external integrations.

### Authentication Setup

#### Step 1: Generate API Token
```bash
# Via web UI (after login):
# 1. Navigate to: User Menu → API Access
# 2. Click "Generate Token"
# 3. Copy token (48-character string)

# Or via API (requires session):
curl -X POST http://localhost:5000/api/tokens/generate \
  -H "Cookie: session=YOUR_SESSION_COOKIE"
```

#### Step 2: Store Token
```bash
# Add to .env file:
API_KEY_FOR_APP=BWcG9nZYDiafqiynpiJ0BisNdZAJa9n5dblNRyT3vFeRuDLfVobJ4hdQ-Kwc9XkI
```

#### Step 3: Verify Token
```bash
curl -H "Authorization: Bearer $API_KEY_FOR_APP" \
  http://localhost:5000/api/tokens/verify
```

### Available Endpoints

#### 1. Run Analysis (Primary Endpoint)
```bash
POST /api/analysis/run

# Request body:
{
  "model_slug": "openai_codex-mini",
  "app_number": 1,
  "analysis_type": "security",
  "tools": ["bandit", "safety"],  # Optional
  "priority": "normal"  # Optional: normal, high, low
}

# Example:
curl -X POST http://localhost:5000/api/analysis/run \
  -H "Authorization: Bearer $API_KEY_FOR_APP" \
  -H "Content-Type: application/json" \
  -d '{
    "model_slug": "openai_codex-mini",
    "app_number": 1,
    "analysis_type": "security",
    "tools": ["bandit"]
  }'

# Response:
{
  "success": true,
  "task_id": "abc123def456",
  "message": "Analysis task created successfully",
  "data": {
    "task_id": "abc123def456",
    "model_slug": "openai_codex-mini",
    "app_number": 1,
    "analysis_type": "security",
    "status": "pending",
    "created_at": "2025-10-27T10:00:00",
    "tools_count": 1,
    "priority": "normal"
  }
}
```

#### 2. Application-Specific Analysis
```bash
POST /api/app/{model_slug}/{app_number}/analyze

# Request body:
{
  "analysis_type": "security",
  "tools": ["bandit"],
  "priority": "normal"
}

# Example:
curl -X POST http://localhost:5000/api/app/openai_codex-mini/1/analyze \
  -H "Authorization: Bearer $API_KEY_FOR_APP" \
  -H "Content-Type: application/json" \
  -d '{"analysis_type": "security", "tools": ["bandit"]}'
```

#### 3. Custom Analysis (Legacy)
```bash
POST /api/analysis/tool-registry/custom-analysis

# Request body:
{
  "model_slug": "openai_codex-mini",
  "app_number": 1,
  "tools": ["bandit"],
  "containers": ["static-analyzer"]
}
```

### Authentication Methods

#### Header (Recommended)
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:5000/api/analysis/run
```

#### Query Parameter (Less Secure)
```bash
curl http://localhost:5000/api/models?token=YOUR_TOKEN
```

### Python Example
```python
import requests
import os
from dotenv import load_dotenv

# Load token from .env
load_dotenv()
token = os.getenv('API_KEY_FOR_APP')

# Setup
base_url = 'http://localhost:5000'
headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}

# Run analysis
response = requests.post(
    f'{base_url}/api/analysis/run',
    headers=headers,
    json={
        'model_slug': 'openai_codex-mini',
        'app_number': 1,
        'analysis_type': 'security',
        'tools': ['bandit']
    }
)

result = response.json()
print(f"Task ID: {result['task_id']}")
```

### Output
- Database record: `AnalysisTask` with full metadata
- Result files: Same structure as CLI and UI
- JSON response: Task ID and status for polling

### Pros
- Fully automated
- No browser required
- Scriptable and integrable
- Same output as UI method

### Cons
- Requires token management
- Must handle token expiration
- Less user-friendly for manual testing

---

## Result File Structure

All three methods produce identical result file structures:

### Directory Structure
```
results/
└── {model_slug}/
    └── app{N}/
        └── task_{type}_{task_id}_{timestamp}/
            ├── {model}_{app}_task_{type}_{task_id}_{timestamp}.json  # Results
            └── manifest.json  # Metadata
```

### Result File Contents
```json
{
  "metadata": {
    "model_slug": "openai_codex-mini",
    "app_number": 1,
    "analysis_type": "security",
    "task_id": "abc123def456",
    "created_at": "2025-10-27T10:00:00",
    "completed_at": "2025-10-27T10:02:15",
    "duration_seconds": 135
  },
  "tool_results": {
    "static-analyzer_bandit": {
      "status": "completed",
      "exit_code": 0,
      "issues_found": 5,
      "findings": [...]
    },
    "static-analyzer_safety": {
      "status": "completed",
      "exit_code": 0,
      "vulnerabilities_found": 2,
      "findings": [...]
    },
    "performance-tester_ab": {
      "status": "completed",
      "requests_per_second": 850,
      "findings": [...]
    },
    "dynamic-analyzer_zap": {
      "status": "completed",
      "alerts": 3,
      "findings": [...]
    },
    "ai-analyzer_requirements-scanner": {
      "status": "completed",
      "requirements_met": 8,
      "requirements_failed": 2,
      "findings": [...]
    }
  },
  "summary": {
    "total_tools": 15,
    "completed": 15,
    "failed": 0,
    "total_findings": 127
  }
}
```

### Tool Naming Convention
All tools prefixed with service name:
- `static-analyzer_*`: bandit, safety, pylint, flake8, eslint, jshint, mypy, semgrep, vulture
- `dynamic-analyzer_*`: zap, nmap, curl
- `performance-tester_*`: ab, aiohttp, locust
- `ai-analyzer_*`: requirements-scanner

---

## Comparison Matrix

| Feature | CLI | UI | API |
|---------|-----|-----|-----|
| **Authentication** | None | Session (cookies) | Bearer token |
| **Automation** | ✅ Excellent | ❌ Manual | ✅ Excellent |
| **Database Tracking** | ❌ No | ✅ Yes | ✅ Yes |
| **Real-time Progress** | ✅ Terminal | ✅ WebSocket | ⚠️ Polling |
| **Result Visibility** | 📁 Disk only | 🖥️ Web UI | 📊 API + UI |
| **User-Friendly** | ⚠️ Technical | ✅ Easy | ⚠️ Technical |
| **External Integration** | ✅ Shell scripts | ❌ Not suitable | ✅ REST APIs |
| **Speed** | ✅ Fast | ⚠️ Slower | ✅ Fast |
| **Token Management** | N/A | N/A | 🔑 Required |

---

## Best Practices

### For Development
- **Use CLI**: Fast iteration, no auth overhead
- Check results: `ls -l results/openai_codex-mini/app1/`

### For Production
- **Use API**: Automated workflows, CI/CD integration
- Store token securely: Environment variables, secrets manager
- Implement token rotation policy

### For End Users
- **Use UI**: User-friendly, no technical knowledge required
- Session-based auth: No token management

### For Scripts/Automation
- **Use CLI**: Quick one-off analyses
- **Use API**: Scheduled/triggered analyses with result tracking

---

## Troubleshooting

### CLI Method
```bash
# Check analyzer services
python analyzer/analyzer_manager.py health

# View logs
python analyzer/analyzer_manager.py logs static-analyzer 100

# Restart services
python analyzer/analyzer_manager.py stop
python analyzer/analyzer_manager.py start
```

### UI Method
```bash
# Check Flask app
curl http://localhost:5000/health

# Check login
# Visit: http://localhost:5000/auth/login
# Credentials from .env: ADMIN_USERNAME, ADMIN_PASSWORD
```

### API Method
```bash
# Verify token
curl -H "Authorization: Bearer $API_KEY_FOR_APP" \
  http://localhost:5000/api/tokens/verify

# Check API health
curl http://localhost:5000/health

# Regenerate token (via UI or API)
curl -X POST http://localhost:5000/api/tokens/revoke \
  -H "Authorization: Bearer $API_KEY_FOR_APP"
```

### Common Issues

#### 401 Unauthorized (API)
- Token invalid, expired, or revoked
- Solution: Regenerate token via UI or check .env file

#### 404 Not Found (API)
- Endpoint doesn't exist or Flask not running
- Solution: Check endpoint spelling, verify Flask is on port 5000

#### No Results Written (CLI)
- Analyzer services not running
- Solution: `python analyzer/analyzer_manager.py start`

#### Results Only Show One Service
- **FIXED**: Previously, timestamp collisions caused overwrites
- Now: All tasks have unique directories with task_id
- Verify: Check `results/{model}/app{N}/` for multiple task directories

---

## Testing All Methods

Run comprehensive test script:
```bash
# Prerequisites:
# 1. Flask app running (cd src && python main.py)
# 2. Analyzer services running (python analyzer/analyzer_manager.py start)
# 3. .env file configured (API_KEY_FOR_APP, ADMIN_PASSWORD)

python scripts/test_all_analysis_methods.py
```

Expected output:
```
✅ CLI: Analysis completed, results written
✅ UI: Analysis submitted via form
✅ API: Analysis started via /api/analysis/run
✅ All methods produce identical result structure
```

---

## Related Documentation
- **API Reference**: `docs/reference/API_REFERENCE.md`
- **CLI Reference**: `docs/reference/CLI.md`
- **Copilot Instructions**: `.github/copilot-instructions.md`
- **Analysis Workflow**: `docs/features/ANALYSIS.md`
