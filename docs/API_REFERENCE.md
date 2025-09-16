# API Reference

Complete reference for all REST API endpoints in the ThesisApp platform.

## Core API Endpoints

### Health & Status

#### `GET /health`
System health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "components": {
    "database": "healthy",
    "celery": "healthy", 
    "analyzer": "healthy"
  },
  "timestamp": "2025-09-16T10:30:00Z"
}
```

#### `GET /api/system/status`
Detailed system status including service information.

**Response:**
```json
{
  "services": {
    "flask": {"status": "running", "uptime": 3600},
    "celery": {"status": "running", "workers": 2},
    "analyzers": {"status": "healthy", "containers": 4}
  },
  "metrics": {
    "active_analyses": 3,
    "pending_tasks": 1,
    "completed_today": 45
  }
}
```

## Model Management API

### Model Operations

#### `GET /api/models`
List all available AI models with filtering and pagination.

**Query Parameters:**
- `provider` (optional): Filter by provider (openai, anthropic, etc.)
- `installed` (optional): Filter by installation status (true/false)
- `page` (optional): Page number for pagination
- `limit` (optional): Results per page (default: 50)

**Response:**
```json
{
  "models": [
    {
      "id": 1,
      "model_id": "gpt-4",
      "canonical_slug": "openai_gpt-4",
      "provider": "openai",
      "model_name": "GPT-4",
      "is_free": false,
      "installed": true,
      "context_window": 8192,
      "capabilities": {
        "function_calling": true,
        "vision": false,
        "streaming": true
      }
    }
  ],
  "pagination": {
    "total": 150,
    "page": 1,
    "pages": 3,
    "per_page": 50
  }
}
```

#### `GET /api/models/{slug}`
Get detailed information about a specific model.

**Response:**
```json
{
  "model": {
    "id": 1,
    "model_id": "gpt-4",
    "canonical_slug": "openai_gpt-4",
    "provider": "openai",
    "model_name": "GPT-4",
    "pricing": {
      "input_price_per_token": 0.00003,
      "output_price_per_token": 0.00006
    },
    "capabilities": {
      "function_calling": true,
      "vision": false,
      "streaming": true,
      "json_mode": true
    },
    "applications": [
      {
        "app_number": 1,
        "app_type": "web_app",
        "status": "completed",
        "has_backend": true,
        "has_frontend": true
      }
    ]
  }
}
```

#### `POST /api/models/sync`
Synchronize models from external providers.

**Request Body:**
```json
{
  "providers": ["openai", "anthropic"],
  "force_update": false
}
```

**Response:**
```json
{
  "status": "success",
  "synced": {
    "openai": 25,
    "anthropic": 8
  },
  "updated": 3,
  "added": 2
}
```

## Application Management API

### Application Operations

#### `GET /api/applications`
List generated applications with filtering.

**Query Parameters:**
- `model_slug` (optional): Filter by model
- `status` (optional): Filter by generation status
- `has_backend` (optional): Filter by backend presence
- `has_frontend` (optional): Filter by frontend presence

**Response:**
```json
{
  "applications": [
    {
      "id": 1,
      "model_slug": "openai_gpt-4",
      "app_number": 1,
      "app_type": "web_app",
      "provider": "openai",
      "generation_status": "completed",
      "has_backend": true,
      "has_frontend": true,
      "backend_framework": "flask",
      "frontend_framework": "react",
      "container_status": "running",
      "ports": {
        "frontend": 3001,
        "backend": 8001,
        "is_available": true
      },
      "created_at": "2025-09-16T09:00:00Z",
      "updated_at": "2025-09-16T09:15:00Z"
    }
  ]
}
```

#### `POST /api/applications/{id}/start`
Start application containers.

**Response:**
```json
{
  "status": "success",
  "container_status": "starting",
  "ports": {
    "frontend": 3001,
    "backend": 8001
  }
}
```

#### `POST /api/applications/{id}/stop`
Stop application containers.

**Response:**
```json
{
  "status": "success",
  "container_status": "stopped"
}
```

## Analysis API

### Security Analysis

#### `POST /api/analysis/security`
Start a security analysis.

**Request Body:**
```json
{
  "application_id": 1,
  "analysis_name": "Security Audit",
  "tools": {
    "bandit_enabled": true,
    "safety_enabled": true,
    "eslint_enabled": true,
    "pylint_enabled": true
  },
  "config": {
    "severity_threshold": "medium",
    "max_issues_per_tool": 1000,
    "timeout_minutes": 30
  }
}
```

**Response:**
```json
{
  "analysis_id": 123,
  "status": "pending",
  "estimated_duration": 600,
  "progress_url": "/api/analysis/123/progress"
}
```

#### `GET /api/analysis/{id}/progress`
Get analysis progress and current status.

**Response:**
```json
{
  "analysis_id": 123,
  "status": "running",
  "progress": {
    "current_step": "bandit_scan",
    "completed_steps": ["initialization", "file_discovery"],
    "remaining_steps": ["safety_check", "eslint_scan", "report_generation"],
    "percentage": 35
  },
  "started_at": "2025-09-16T10:00:00Z",
  "estimated_completion": "2025-09-16T10:10:00Z"
}
```

#### `GET /api/analysis/{id}/results`
Get completed analysis results.

**Response:**
```json
{
  "analysis_id": 123,
  "status": "completed",
  "summary": {
    "total_issues": 15,
    "critical_severity_count": 2,
    "high_severity_count": 5,
    "medium_severity_count": 6,
    "low_severity_count": 2,
    "tools_run_count": 4,
    "tools_failed_count": 0
  },
  "results": {
    "bandit": {
      "issues_found": 8,
      "severity_breakdown": {
        "critical": 1,
        "high": 3,
        "medium": 3,
        "low": 1
      }
    },
    "safety": {
      "vulnerabilities_found": 3,
      "packages_scanned": 25
    }
  },
  "completed_at": "2025-09-16T10:08:45Z",
  "analysis_duration": 525.3
}
```

### Performance Analysis

#### `POST /api/analysis/performance`
Start a performance test.

**Request Body:**
```json
{
  "application_id": 1,
  "test_type": "load",
  "config": {
    "users": 50,
    "spawn_rate": 5.0,
    "test_duration": 300,
    "target_url": "http://localhost:3001"
  }
}
```

**Response:**
```json
{
  "test_id": 456,
  "status": "pending",
  "estimated_duration": 300,
  "progress_url": "/api/analysis/performance/456/progress"
}
```

### ZAP Security Analysis

#### `POST /api/analysis/zap`
Start OWASP ZAP security scan.

**Request Body:**
```json
{
  "application_id": 1,
  "target_url": "http://localhost:3001",
  "scan_type": "active",
  "config": {
    "spider_config": {
      "max_depth": 5,
      "max_duration": 10
    },
    "active_scan_config": {
      "strength": "medium",
      "threshold": "medium"
    }
  }
}
```

### AI Analysis

#### `POST /api/analysis/ai`
Start AI-powered code analysis.

**Request Body:**
```json
{
  "application_id": 1,
  "analyzer_model": "gpt-4",
  "analysis_prompt": "Review this code for security vulnerabilities and code quality issues",
  "config": {
    "max_tokens": 4000,
    "temperature": 0.1
  }
}
```

## Batch Analysis API

### Batch Operations

#### `POST /api/batch/create`
Create a new batch analysis job.

**Request Body:**
```json
{
  "batch_id": "security_audit_2025_09_16",
  "analysis_types": ["security", "performance"],
  "filters": {
    "model_filter": ["openai_gpt-4", "anthropic_claude-3"],
    "app_filter": [1, 2, 3]
  },
  "config": {
    "parallel_execution": true,
    "timeout_minutes": 60
  }
}
```

**Response:**
```json
{
  "batch_id": "security_audit_2025_09_16",
  "status": "pending",
  "total_tasks": 6,
  "progress_url": "/api/batch/security_audit_2025_09_16/progress"
}
```

#### `GET /api/batch/{batch_id}/progress`
Get batch job progress.

**Response:**
```json
{
  "batch_id": "security_audit_2025_09_16",
  "status": "running",
  "progress": {
    "total_tasks": 6,
    "completed_tasks": 2,
    "failed_tasks": 0,
    "progress_percentage": 33.3
  },
  "tasks": [
    {
      "task_id": "sec_001",
      "model_slug": "openai_gpt-4",
      "app_number": 1,
      "analysis_type": "security",
      "status": "completed"
    }
  ]
}
```

## Sample Generation API

### Code Generation

#### `POST /api/sample-gen/generate`
Generate code samples using AI.

**Request Body:**
```json
{
  "model": "gpt-4",
  "app_num": 1,
  "template": "web_app",
  "requirements": [
    "Flask backend with REST API",
    "React frontend with responsive design",
    "User authentication",
    "Database integration"
  ]
}
```

**Response:**
```json
{
  "result_id": "gen_789",
  "status": "success",
  "generation_time": 15.3,
  "output": {
    "backend": {
      "framework": "Flask",
      "files_generated": 8,
      "features": ["REST API", "Authentication", "Database Models"]
    },
    "frontend": {
      "framework": "React",
      "files_generated": 12,
      "features": ["Responsive Design", "Authentication UI", "API Integration"]
    }
  }
}
```

#### `GET /api/sample-gen/manifest`
Get generation manifest and history.

**Response:**
```json
{
  "total_generations": 150,
  "recent_generations": [
    {
      "result_id": "gen_789",
      "model": "gpt-4",
      "app_num": 1,
      "success": true,
      "timestamp": "2025-09-16T11:00:00Z",
      "duration": 15.3
    }
  ],
  "statistics": {
    "success_rate": 0.95,
    "average_duration": 18.7,
    "most_used_model": "gpt-4"
  }
}
```

## Real-time API (WebSocket)

### WebSocket Events

#### Connection
```
ws://localhost:5000/ws
```

#### Event Types

**Analysis Progress**
```json
{
  "type": "analysis_progress",
  "data": {
    "analysis_id": 123,
    "status": "running",
    "progress": 45,
    "current_step": "safety_check"
  }
}
```

**Task Status**
```json
{
  "type": "task_status",
  "data": {
    "task_id": "task_456",
    "status": "completed",
    "result": "success"
  }
}
```

**System Health**
```json
{
  "type": "system_health",
  "data": {
    "component": "analyzer",
    "status": "healthy",
    "containers": {
      "static-analyzer": "running",
      "dynamic-analyzer": "running",
      "performance-tester": "running",
      "ai-analyzer": "running"
    }
  }
}
```

## Error Responses

All API endpoints return consistent error responses:

```json
{
  "status": "error",
  "status_code": 400,
  "message": "Validation failed",
  "error": "Bad Request",
  "error_id": "req_abc123",
  "timestamp": "2025-09-16T10:30:00Z",
  "details": {
    "field": "application_id",
    "error": "Application not found"
  }
}
```

### HTTP Status Codes

- **200**: Success
- **201**: Created
- **400**: Bad Request (validation error)
- **401**: Unauthorized
- **403**: Forbidden
- **404**: Not Found
- **409**: Conflict (resource already exists)
- **422**: Unprocessable Entity (business logic error)
- **429**: Too Many Requests (rate limit)
- **500**: Internal Server Error
- **503**: Service Unavailable (analyzer down)

## Rate Limiting

- **Analysis API**: 10 requests per minute per IP
- **Batch API**: 5 requests per minute per IP
- **Sample Generation**: 20 requests per minute per IP
- **Other endpoints**: 100 requests per minute per IP

## Authentication

Currently, the API uses session-based authentication for web UI and optional API key authentication for programmatic access (when configured).

## Pagination

List endpoints support pagination with these parameters:
- `page`: Page number (1-based)
- `limit`: Items per page (max 100)

Pagination info is returned in the response:
```json
{
  "pagination": {
    "total": 500,
    "page": 2,
    "pages": 10,
    "per_page": 50,
    "has_next": true,
    "has_prev": true
  }
}
```