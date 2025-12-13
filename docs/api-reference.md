# API Reference

REST API documentation for ThesisAppRework.

## Authentication

All API endpoints require Bearer token authentication:

```
Authorization: Bearer <token>
```

Generate tokens via **User → API Access** in the web UI, or see [src/app/api/tokens.py](../src/app/api/tokens.py).

### Verify Token

```http
GET /api/tokens/verify
```

**Response:** `200 OK` with token info, or `401 Unauthorized`.

## Analysis Endpoints

### Run Analysis

```http
POST /api/analysis/run
Content-Type: application/json

{
  "model_slug": "openai_gpt-4",
  "app_number": 1,
  "analysis_type": "comprehensive",
  "tools": ["bandit", "eslint"]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `model_slug` | string | Yes | Target model (e.g., `openai_gpt-4`) |
| `app_number` | int | Yes | Application number |
| `analysis_type` | string | Yes | `comprehensive`, `security`, `static`, `dynamic`, `performance`, `ai` |
| `tools` | array | No | Specific tools to run |

**Response:**
```json
{
  "task_id": "task_abc123",
  "status": "PENDING",
  "message": "Analysis task created"
}
```

### Analyze Specific App

```http
POST /api/app/{model_slug}/{app_number}/analyze
Content-Type: application/json

{
  "analysis_type": "security"
}
```

### Get Task Status

```http
GET /api/analysis/task/{task_id}
```

**Response:**
```json
{
  "task_id": "task_abc123",
  "status": "RUNNING",
  "progress_percentage": 45,
  "started_at": "2025-12-13T10:00:00Z",
  "service_name": "static"
}
```

### Get Task Results

```http
GET /api/analysis/task/{task_id}/results
```

Returns consolidated analysis results. See [Results Format](#results-format).

### List Tasks

```http
GET /api/analysis/tasks?status=COMPLETED&model=openai_gpt-4&limit=10
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status |
| `model` | string | Filter by model slug |
| `app_number` | int | Filter by app number |
| `limit` | int | Max results (default: 50) |
| `offset` | int | Pagination offset |

## Application Endpoints

### List Applications

```http
GET /api/apps
```

### Get Application

```http
GET /api/apps/{model_slug}/{app_number}
```

### Get Application Status

```http
GET /api/apps/{model_slug}/{app_number}/status
```

Returns container status, port assignments, and health.

## Results Format

Analysis results follow this structure:

```json
{
  "metadata": {
    "model_slug": "openai_gpt-4",
    "app_number": 1,
    "timestamp": "2025-12-13T10:30:00Z",
    "analyzer_version": "1.0.0"
  },
  "results": {
    "task": {
      "task_id": "task_abc123",
      "started_at": "...",
      "completed_at": "..."
    },
    "summary": {
      "total_findings": 15,
      "severity_breakdown": {
        "critical": 0,
        "high": 2,
        "medium": 8,
        "low": 5
      },
      "tools_used": ["bandit", "eslint", "semgrep"]
    },
    "tools": {
      "bandit": {
        "status": "success",
        "findings_count": 3,
        "execution_time": 2.5
      }
    },
    "findings": [
      {
        "tool": "bandit",
        "severity": "medium",
        "message": "Possible SQL injection",
        "file": "app.py",
        "line": 42
      }
    ]
  }
}
```

## Health Endpoints

### System Health

```http
GET /api/health
```

### Analyzer Health

```http
GET /api/health/analyzers
```

Returns status of all analyzer containers (ports 2001-2004).

## Error Responses

| Status | Description |
|--------|-------------|
| `400` | Bad request (invalid parameters) |
| `401` | Unauthorized (missing/invalid token) |
| `404` | Resource not found |
| `422` | Validation error |
| `500` | Internal server error |
| `503` | Service unavailable (analyzers offline) |

```json
{
  "error": "error_code",
  "message": "Human-readable description",
  "details": {}
}
```

## Rate Limits

No rate limits currently enforced. Consider implementing for production deployments.

## WebSocket API

Real-time updates available via SocketIO when `flask-socketio` is installed:

```javascript
const socket = io('/analysis');
socket.on('task_progress', (data) => {
  console.log(`Task ${data.task_id}: ${data.progress}%`);
});
```

Events:
- `task_progress` - Progress updates
- `task_completed` - Task finished
- `task_failed` - Task error

## CLI Alternative

For automation without database tracking, use the analyzer CLI directly:

```bash
python analyzer/analyzer_manager.py analyze <model> <app> <type> [--tools tool1,tool2]
```

Results written to `results/{model}/app{N}/task_{id}/` only (no DB record).

## Related

- [Architecture](./architecture.md)
- [Development Guide](./development-guide.md)
