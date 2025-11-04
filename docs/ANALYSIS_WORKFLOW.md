# Analysis Workflow Documentation

## 📋 Overview

The ThesisAppRework analysis system evaluates AI-generated applications through a comprehensive, multi-layered approach. This document describes the complete workflow from submission to results.

## 🎯 Analysis Types

### 1. Comprehensive Analysis
**Complete evaluation across all dimensions**

- **Static Analysis**: Code quality, style, complexity
- **Security Analysis**: Vulnerability scanning, dependency checks
- **Dynamic Analysis**: Runtime behavior, OWASP ZAP scanning
- **Performance Testing**: Load testing, response times
- **AI Analysis**: OpenRouter-powered code review

**When to use**: Full evaluation of production-ready applications

**Duration**: 10-15 minutes per application

### 2. Security Analysis
**Focused security assessment**

- Bandit (Python security issues)
- Safety (dependency vulnerabilities)
- ESLint security plugins (JavaScript)
- OWASP ZAP (dynamic security scanning)

**When to use**: Security audits, compliance checks

**Duration**: 5-8 minutes per application

### 3. Static Analysis
**Code quality without execution**

- Linters (ESLint, PyLint, JSHint)
- Formatters (Black, Prettier)
- Complexity analysis
- Style consistency

**When to use**: Development iterations, CI/CD pipelines

**Duration**: 2-3 minutes per application

### 4. Dynamic Analysis
**Runtime behavior testing**

- Connectivity checks (curl, nmap)
- OWASP ZAP security scanning
- API endpoint testing
- Response validation

**When to use**: Integration testing, security validation

**Duration**: 5-7 minutes per application

### 5. Performance Testing
**Load and stress testing**

- Apache Bench (ab)
- Aiohttp built-in testing
- Locust load testing
- Response time metrics

**When to use**: Scalability assessment, optimization

**Duration**: 3-5 minutes per application

### 6. AI Analysis
**Intelligent code review**

- OpenRouter AI evaluation
- Code smell detection
- Architectural recommendations
- Best practices review

**When to use**: Code review automation, learning feedback

**Duration**: 2-4 minutes per application

## 🚀 Workflow Paths

### Path 1: CLI (Direct Analysis)

**Best for**: Development, scripting, automation without DB tracking

```bash
# Start analyzer services
python analyzer/analyzer_manager.py start

# Run analysis directly
python analyzer/analyzer_manager.py analyze openai_gpt-4 1 comprehensive

# Check results
ls results/openai_gpt-4/app1/task_*/
```

**Flow:**
```
CLI Command → Analyzer Manager → Docker Containers → Results Files
                                                        ↓
                                                 results/{model}/app{N}/task_{id}/
```

**Characteristics:**
- ✅ Fastest execution (no web layer)
- ✅ Simple result files
- ✅ Perfect for scripts/automation
- ❌ No database tracking
- ❌ No real-time progress updates
- ❌ No web UI visibility

---

### Path 2: Web UI (Interactive Analysis)

**Best for**: Interactive exploration, monitoring, team collaboration

```
1. Navigate to http://localhost:5000
2. Go to "Analysis" section
3. Select model and app
4. Choose analysis type
5. Click "Start Analysis"
6. Watch real-time progress
7. View results in browser
```

**Flow:**
```
Web Browser → Flask Routes → Analysis Queue Service → AnalysisTask (DB)
                                       ↓
                                Analyzer Manager → Docker Containers
                                       ↓
                            Results written + DB updated
                                       ↓
                         WebSocket notification → Real-time UI update
```

**Characteristics:**
- ✅ Real-time progress tracking
- ✅ Full database integration
- ✅ User-friendly interface
- ✅ Team collaboration features
- ✅ Historical view of analyses
- ❌ Requires web app running
- ❌ Slightly slower (web overhead)

---

### Path 3: REST API (Programmatic Analysis)

**Best for**: Automation, CI/CD, external integrations with DB tracking

```bash
# Get Bearer token (once)
TOKEN=$(curl -X POST http://localhost:5000/api/tokens/create \
  -H "Content-Type: application/json" \
  -d '{"username":"admin", "password":"secret"}' | jq -r '.token')

# Submit analysis
curl -X POST http://localhost:5000/api/analysis/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model_slug": "openai_gpt-4",
    "app_number": 1,
    "analysis_type": "comprehensive"
  }'

# Check status
curl http://localhost:5000/api/analysis/task/{task_id} \
  -H "Authorization: Bearer $TOKEN"

# Get results
curl http://localhost:5000/api/analysis/results/{task_id} \
  -H "Authorization: Bearer $TOKEN"
```

**Flow:**
```
HTTP Client → API Endpoint → Authentication → Analysis Queue Service
                                                      ↓
                                              AnalysisTask (DB)
                                                      ↓
                                              Analyzer Manager → Containers
                                                      ↓
                                        Results + DB + Optional WebSocket
```

**Characteristics:**
- ✅ Full automation capability
- ✅ Database tracking
- ✅ Authentication/authorization
- ✅ Programmatic access to all features
- ✅ Async operation (fire and forget)
- ⚠️ Requires token management
- ⚠️ RESTful overhead

---

## 🏗️ Architecture Components

### 1. Flask Application (`src/`)
- **Routes**: Web UI and API endpoints
- **Services**: Business logic, orchestration
- **Models**: Database entities (SQLAlchemy)
- **WebSocket**: Real-time progress updates

### 2. Analyzer Manager (`analyzer/analyzer_manager.py`)
- **Container Control**: Start/stop/restart services
- **Analysis Orchestration**: Dispatch to services
- **Result Aggregation**: Consolidate findings
- **WebSocket Communication**: Service interaction

### 3. Analyzer Services (Docker Containers)
- **Static Analyzer** (port 2001): ESLint, PyLint, JSHint
- **Dynamic Analyzer** (port 2002): ZAP, connectivity
- **Performance Tester** (port 2003): ab, locust, aiohttp
- **AI Analyzer** (port 2004): OpenRouter integration
- **WebSocket Gateway** (port 8765): Unified protocol

### 4. Generated Applications (`generated/apps/`)
- Source code created by AI models
- Organized by `{model_slug}/app{N}/`
- Contains `.env` with port configuration

### 5. Results Storage (`results/`)
- Organized by `{model_slug}/app{N}/task_{task_id}/`
- Contains consolidated JSON results
- Service-specific snapshots
- SARIF reports (security findings)

---

## 📊 Data Flow

### Submission → Execution → Results

```
┌─────────────────────────────────────────────────────────────┐
│ 1. SUBMISSION PHASE                                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  User Input (CLI/UI/API)                                    │
│         ↓                                                    │
│  Validation (model exists, app exists, ports configured)    │
│         ↓                                                    │
│  Create AnalysisTask (DB record with pending status)        │
│         ↓                                                    │
│  Generate task_id (UUID-based)                              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. DISPATCH PHASE                                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Analyzer Manager receives request                          │
│         ↓                                                    │
│  Normalize model slug (handle variants)                     │
│         ↓                                                    │
│  Resolve app path and ports                                 │
│         ↓                                                    │
│  Update task status → 'running'                             │
│         ↓                                                    │
│  Create result directory structure                          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. EXECUTION PHASE                                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Static     │  │   Security   │  │   Dynamic    │     │
│  │  Analyzer    │  │   Analyzer   │  │   Analyzer   │     │
│  │ (Port 2001)  │  │ (Port 2001)  │  │ (Port 2002)  │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │                  │                  │             │
│         └──────────────────┴──────────────────┘             │
│                            ↓                                 │
│  ┌──────────────┐  ┌──────────────┐                        │
│  │ Performance  │  │      AI      │                        │
│  │   Tester     │  │   Analyzer   │                        │
│  │ (Port 2003)  │  │ (Port 2004)  │                        │
│  └──────┬───────┘  └──────┬───────┘                        │
│         │                  │                                 │
│         └──────────────────┘                                 │
│                   ↓                                          │
│         WebSocket Communication                             │
│         Progress Updates (streaming)                        │
│         Tool Results (normalized)                           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. AGGREGATION PHASE                                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Collect results from all services                          │
│         ↓                                                    │
│  Normalize tool results (success/error/timeout)             │
│         ↓                                                    │
│  Extract findings by severity (critical/high/medium/low)    │
│         ↓                                                    │
│  Generate SARIF reports (security findings)                 │
│         ↓                                                    │
│  Calculate summary statistics                               │
│         ↓                                                    │
│  Create consolidated JSON                                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. PERSISTENCE PHASE                                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Write to results/{model}/app{N}/task_{id}/                │
│    ├── {model}_app{N}_task_{id}_{timestamp}.json           │
│    ├── manifest.json                                        │
│    ├── sarif/                                               │
│    │   ├── bandit.sarif                                     │
│    │   ├── eslint.sarif                                     │
│    │   └── semgrep.sarif                                    │
│    └── services/                                            │
│        ├── static_snapshot.json                             │
│        ├── security_snapshot.json                           │
│        ├── dynamic_snapshot.json                            │
│        ├── performance_snapshot.json                        │
│        └── ai_snapshot.json                                 │
│         ↓                                                    │
│  Update AnalysisTask in database                            │
│    - status → 'completed' or 'failed'                       │
│    - completed_at → timestamp                               │
│    - result_summary → JSON blob                             │
│         ↓                                                    │
│  Send WebSocket notification (if UI connected)              │
│         ↓                                                    │
│  Prune legacy result directories                            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. CONSUMPTION PHASE                                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  UI: Display results in web dashboard                       │
│  API: Return JSON via /api/analysis/results/{task_id}      │
│  CLI: Read from results/ directory                          │
│  Automation: Parse consolidated JSON                        │
│  Reports: Generate PDF/HTML from data                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔍 Result Structure

### Consolidated Result JSON

```json
{
  "metadata": {
    "model_slug": "openai_gpt-4",
    "app_number": 1,
    "task_id": "task_a1b2c3d4",
    "analysis_type": "comprehensive",
    "timestamp": "2025-11-04T15:30:00Z",
    "analyzer_version": "2.0.0",
    "duration_seconds": 847.23
  },
  "summary": {
    "total_findings": 42,
    "findings_by_severity": {
      "critical": 2,
      "high": 8,
      "medium": 15,
      "low": 17
    },
    "findings_by_tool": {
      "bandit": 12,
      "eslint": 18,
      "zap": 8,
      "safety": 4
    },
    "tools_executed": 14,
    "tools_successful": 12,
    "tools_failed": 2
  },
  "tools": {
    "bandit": {
      "tool": "bandit",
      "status": "success",
      "executed": true,
      "total_issues": 12,
      "duration_seconds": 3.45
    },
    "eslint": {
      "tool": "eslint",
      "status": "success",
      "executed": true,
      "total_issues": 18,
      "duration_seconds": 2.78
    },
    "zap": {
      "tool": "zap",
      "status": "timeout",
      "executed": true,
      "total_issues": 0,
      "duration_seconds": 300.0,
      "error": "Scan timeout after 300 seconds"
    }
  },
  "findings": [
    {
      "tool": "bandit",
      "severity": "high",
      "message": "SQL injection vulnerability detected",
      "file": "src/database.py",
      "line": 42,
      "recommendation": "Use parameterized queries"
    }
  ],
  "services": {
    "static": { "status": "completed", "findings": 30 },
    "security": { "status": "completed", "findings": 20 },
    "dynamic": { "status": "timeout", "findings": 0 },
    "performance": { "status": "completed", "findings": 0 },
    "ai": { "status": "completed", "findings": 0 }
  }
}
```

---

## 🛠️ Tool Normalization

### Tool Status Values

- **`success`**: Tool ran and produced results
- **`error`**: Tool failed due to process/infrastructure issue
- **`timeout`**: Tool exceeded time limit
- **`not_available`**: Tool not installed/accessible
- **`no_issues`**: Tool ran successfully but found nothing
- **`completed`**: Generic successful completion

### Linter Exit Code Handling

**ESLint and JSHint** traditionally exit with code `1` when lint findings are present. The analyzer now treats this as **success** (not error) when JSON output is available.

**Only true failures** (exit code > 1, missing output, crashes) are marked as `error`.

This prevents false negatives in tool availability reporting.

---

## 📈 Monitoring & Progress

### Real-Time Updates (WebSocket)

```javascript
// Connect to WebSocket
const ws = new WebSocket('ws://localhost:8765');

// Listen for progress
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  if (data.type === 'progress_update') {
    console.log(`Service: ${data.service}`);
    console.log(`Progress: ${data.progress}%`);
    console.log(`Message: ${data.message}`);
  }
  
  if (data.type === 'analysis_complete') {
    console.log('Analysis finished!');
    console.log(`Results: ${data.result_path}`);
  }
};
```

### Database Tracking

```python
from app.models import AnalysisTask

# Query tasks
tasks = AnalysisTask.query.filter_by(
    status='running',
    target_model='openai_gpt-4'
).all()

# Check progress
for task in tasks:
    print(f"Task: {task.task_id}")
    print(f"Status: {task.status}")
    print(f"Progress: {task.progress_percentage}%")
    print(f"Started: {task.started_at}")
    print(f"Elapsed: {task.elapsed_time}")
```

---

## 🔧 Configuration

### Environment Variables

```bash
# Flask Configuration
FLASK_ENV=development
FLASK_DEBUG=1
DATABASE_URL=sqlite:///thesis_app.db

# Analyzer Configuration
ANALYZER_ENABLED=true
ANALYZER_AUTO_START=false
LOG_LEVEL=INFO

# Timeouts (seconds)
STATIC_ANALYSIS_TIMEOUT=300
SECURITY_ANALYSIS_TIMEOUT=600
PERFORMANCE_TIMEOUT=300
DYNAMIC_ANALYSIS_TIMEOUT=600

# AI Analyzer (requires API key)
OPENROUTER_API_KEY=sk-or-v1-xxxxx

# WebSocket Gateway
GATEWAY_HOST=0.0.0.0
GATEWAY_PORT=8765
```

### Port Configuration

Stored in `misc/port_config.json` and loaded into database:

```json
{
  "openai_gpt-4": {
    "1": { "backend": 3001, "frontend": 3002 },
    "2": { "backend": 3003, "frontend": 3004 }
  },
  "anthropic_claude-3.7-sonnet": {
    "1": { "backend": 3005, "frontend": 3006 },
    "2": { "backend": 3007, "frontend": 3008 }
  }
}
```

---

## 🐛 Troubleshooting

### Analysis Stuck in "Pending"

**Cause**: Analyzer services not running or queue not processing

**Solution**:
```bash
# Check analyzer status
python analyzer/analyzer_manager.py status

# Start if needed
python analyzer/analyzer_manager.py start

# Check Docker containers
docker ps | grep analyzer
```

### "No Port Configuration Found"

**Cause**: App ports not configured in database or `.env`

**Solution**:
```bash
# Check app .env file
cat generated/apps/openai_gpt-4/app1/.env

# Verify database port config
python scripts/diagnostics/check_db_apps.py

# Reload port config
python -c "from src.app import create_app; app = create_app(); app.extensions['service_locator'].get('docker').reload_port_config()"
```

### Analysis Timeout

**Cause**: Service took longer than configured timeout

**Solution**:
```bash
# Increase timeout in .env
SECURITY_ANALYSIS_TIMEOUT=900  # 15 minutes

# Or pass tools to skip slow ones
python analyzer/analyzer_manager.py analyze model 1 security --tools bandit,safety
```

### WebSocket Connection Errors

**Cause**: Service crashed or not responding

**Solution**:
```bash
# Check service health
python analyzer/analyzer_manager.py health

# Check service logs
python analyzer/analyzer_manager.py logs static-analyzer 100

# Restart service
python analyzer/analyzer_manager.py restart
```

### Missing Results

**Cause**: Analysis failed silently or results not persisted

**Solution**:
```bash
# Check task status in database
python scripts/diagnostics/check_tasks.py

# Look for error messages
python -c "from app import create_app; app = create_app(); with app.app_context(): from app.models import AnalysisTask; t = AnalysisTask.query.filter_by(task_id='task_xxx').first(); print(t.error_message)"

# Check results directory
ls -la results/openai_gpt-4/app1/
```

---

## 📚 Related Documentation

- **[Analyzer README](../analyzer/README.md)** - Service architecture and CLI
- **[API Documentation](API_AUTH_AND_METHODS.md)** - REST API reference
- **[Testing Guide](guides/QUICK_TEST_GUIDE.md)** - Testing workflows
- **[Database Models](reference/DATABASE_SCHEMA.md)** - Data structures
- **[WebSocket Protocol](reference/WEBSOCKET_PROTOCOL.md)** - Real-time communication

---

## 🎯 Best Practices

### For Development
1. Use **CLI path** for fast iteration
2. Run **static analysis** frequently during coding
3. Run **comprehensive** before commits
4. Use **--tools** to focus on specific concerns

### For CI/CD
1. Use **API path** with Bearer tokens
2. Implement **timeout handling** (services may timeout)
3. Parse **consolidated JSON** for pass/fail
4. Archive results for historical comparison

### For Production
1. Use **Web UI path** for visibility
2. Enable **WebSocket updates** for progress
3. Set **appropriate timeouts** based on app size
4. Monitor **database growth** and cleanup old tasks

### For Teams
1. Share **API tokens** securely
2. Use **priority flags** for urgent analyses
3. Review **aggregated findings** in dashboards
4. Export **SARIF reports** for security teams

---

**Last Updated**: November 4, 2025  
**Version**: 2.0.0  
**Maintainer**: ThesisAppRework Team
