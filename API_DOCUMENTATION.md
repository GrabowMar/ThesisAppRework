# API Documentation

## Overview

This document provides comprehensive API documentation for the AI Model Testing Framework. The API supports both RESTful JSON endpoints and HTMX HTML fragment endpoints for real-time web interface updates.

## Base Configuration

**Base URL**: `http://localhost:5000`  
**Authentication**: Not implemented (development environment)  
**Content-Type**: `application/json` or `application/x-www-form-urlencoded`  
**Response Formats**: JSON (API endpoints), HTML (HTMX endpoints)

## API Endpoints

### 1. Models API

#### GET /testing/api/models
Get list of available AI models for testing.

**Response Format:**
```json
{
  "models": [
    {
      "id": "anthropic_claude-3.7-sonnet",
      "slug": "anthropic_claude-3.7-sonnet", 
      "name": "anthropic_claude-3.7-sonnet",
      "display_name": "anthropic_claude-3.7-sonnet",
      "provider": "anthropic",
      "status": "ready",
      "apps_count": 30
    }
  ]
}
```

**Example Request:**
```bash
curl -X GET http://localhost:5000/testing/api/models
```

### 2. Infrastructure Management API

#### GET /testing/api/infrastructure-status
Get real-time status of containerized testing services.

**Response Format:**
```json
{
  "services": {
    "api-gateway": {
      "status": "healthy",
      "url": "http://localhost:8000/health",
      "response_time": "0.045s"
    },
    "security-scanner": {
      "status": "healthy", 
      "url": "http://localhost:8001/health",
      "response_time": "0.032s"
    }
  },
  "overall_status": "healthy",
  "total_services": 5,
  "healthy_services": 5,
  "check_duration": "0.156s"
}
```

**Example Request:**
```bash
curl -X GET http://localhost:5000/testing/api/infrastructure-status
```

#### POST /testing/api/infrastructure/<action>
Manage testing infrastructure containers.

**Parameters:**
- `action`: One of `start`, `stop`, `restart`

**Request Body:**
```json
{
  "services": ["security-scanner", "performance-tester"],
  "wait_for_ready": true
}
```

**Response Format:**
```json
{
  "success": true,
  "message": "Services started successfully",
  "affected_services": ["security-scanner", "performance-tester"],
  "status": {
    "security-scanner": "started",
    "performance-tester": "started"
  }
}
```

### 3. Test Job Management API

#### GET /testing/api/jobs
Get list of all test jobs with pagination.

**Query Parameters:**
- `page`: Page number (default: 1)
- `per_page`: Items per page (default: 20)
- `status`: Filter by status (pending, running, completed, failed)
- `model`: Filter by model name

**Response Format:**
```json
{
  "jobs": [
    {
      "id": 123,
      "name": "Security Analysis - Claude 3.7",
      "status": "completed",
      "progress": 100,
      "model_name": "anthropic_claude-3.7-sonnet",
      "app_number": 1,
      "tools": ["bandit", "safety", "pylint"],
      "created_at": "2025-08-07T10:30:00Z",
      "completed_at": "2025-08-07T10:45:30Z",
      "duration": 930,
      "has_results": true
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 45,
    "total_pages": 3,
    "has_next": true,
    "has_prev": false
  }
}
```

#### POST /testing/api/create-test  
Create a new test job.

**Request Body:**
```json
{
  "name": "Security Analysis Test",
  "model": "anthropic_claude-3.7-sonnet",
  "app_number": 1,
  "test_types": ["security", "performance"],
  "tools": {
    "security": ["bandit", "safety", "pylint"],
    "performance": ["locust"]
  },
  "configuration": {
    "timeout": 3600,
    "parallel": true,
    "notify_on_completion": true
  }
}
```

**Response Format:**
```json
{
  "success": true,
  "message": "Test job created successfully",
  "job": {
    "id": 124,
    "name": "Security Analysis Test",
    "status": "pending",
    "estimated_duration": 1800,
    "test_id": "test-124-20250807"
  }
}
```

### 4. Job Control API

#### POST /testing/api/job/<job_id>/start
Start execution of a pending test job.

**Path Parameters:**
- `job_id`: Integer ID of the job

**Request Body:**
```json
{
  "priority": "normal",
  "force_restart": false
}
```

**Response Format:**
```json
{
  "success": true,
  "message": "Job started successfully", 
  "job": {
    "id": 124,
    "status": "running",
    "started_at": "2025-08-07T11:00:00Z",
    "estimated_completion": "2025-08-07T11:30:00Z"
  }
}
```

#### POST /testing/api/job/<job_id>/stop
Stop a running test job.

**Path Parameters:**
- `job_id`: Integer ID of the job

**Request Body:**
```json
{
  "reason": "User requested cancellation",
  "force": false
}
```

**Response Format:**
```json
{
  "success": true,
  "message": "Job stopped successfully",
  "job": {
    "id": 124,
    "status": "cancelled",
    "stopped_at": "2025-08-07T11:15:00Z",
    "completion_percentage": 65
  }
}
```

### 5. Job Monitoring API

#### GET /testing/api/job/<job_id>/progress
Get real-time progress information for a running job.

**Path Parameters:**
- `job_id`: Integer ID of the job

**Response Format:**
```json
{
  "job_id": 124,
  "status": "running",
  "progress": 45,
  "current_task": "Running safety scan",
  "completed_tasks": 3,
  "total_tasks": 7,
  "eta_seconds": 890,
  "eta_formatted": "14 minutes 50 seconds",
  "last_updated": "2025-08-07T11:10:30Z",
  "tasks": [
    {
      "name": "Bandit scan",
      "status": "completed",
      "progress": 100,
      "duration": 45
    },
    {
      "name": "Safety check", 
      "status": "running",
      "progress": 80,
      "estimated_remaining": 15
    }
  ]
}
```

#### GET /testing/api/job/<job_id>/results
Get detailed results for a completed job.

**Path Parameters:**
- `job_id`: Integer ID of the job

**Response Format:**
```json
{
  "job_id": 124,
  "status": "completed",
  "summary": {
    "total_issues": 12,
    "critical_issues": 2,
    "high_issues": 3,
    "medium_issues": 5,
    "low_issues": 2,
    "tools_run": ["bandit", "safety", "pylint"],
    "execution_time": 930
  },
  "results": {
    "security": {
      "bandit": {
        "issues_found": 8,
        "severity_breakdown": {
          "high": 2,
          "medium": 4,
          "low": 2
        },
        "files_scanned": 15,
        "execution_time": 45
      }
    },
    "performance": {
      "locust": {
        "requests_per_second": 125.4,
        "average_response_time": 250,
        "error_rate": 0.02,
        "max_response_time": 1250
      }
    }
  },
  "artifacts": [
    {
      "name": "bandit_report.json",
      "type": "application/json",
      "size": 15420,
      "download_url": "/testing/api/job/124/artifact/bandit_report.json"
    }
  ],
  "logs": {
    "available": true,
    "url": "/testing/api/job/124/logs"
  }
}
```

#### GET /testing/api/job/<job_id>/logs
Get execution logs for a job.

**Path Parameters:**
- `job_id`: Integer ID of the job

**Query Parameters:**
- `level`: Log level filter (debug, info, warning, error)
- `tail`: Number of recent lines (default: 100)
- `download`: Set to 'true' to download as file

**Response Format:**
```json
{
  "job_id": 124,
  "logs": [
    {
      "timestamp": "2025-08-07T11:00:15Z",
      "level": "info",
      "message": "Starting bandit security scan",
      "component": "security-scanner"
    },
    {
      "timestamp": "2025-08-07T11:00:45Z", 
      "level": "warning",
      "message": "Found potential SQL injection vulnerability in user.py:45",
      "component": "bandit"
    }
  ],
  "total_lines": 245,
  "filtered_lines": 100
}
```

### 6. Statistics API

#### GET /testing/api/stats
Get system-wide testing statistics.

**Response Format:**
```json
{
  "jobs": {
    "total": 156,
    "pending": 3,
    "running": 2,
    "completed": 145,
    "failed": 6
  },
  "models": {
    "total_available": 25,
    "most_tested": [
      {
        "model": "anthropic_claude-3.7-sonnet",
        "test_count": 45
      },
      {
        "model": "openai_gpt-4o",
        "test_count": 38
      }
    ]
  },
  "performance": {
    "average_job_duration": 1245,
    "total_execution_time": 195420,
    "success_rate": 96.15
  },
  "recent_activity": [
    {
      "timestamp": "2025-08-07T11:00:00Z",
      "event": "job_completed",
      "job_id": 123,
      "model": "anthropic_claude-3.7-sonnet"
    }
  ]
}
```

### 7. Export API

#### GET /testing/api/export
Export test results in various formats.

**Query Parameters:**
- `format`: Export format (csv, json, pdf)
- `job_ids`: Comma-separated list of job IDs
- `date_from`: Start date (YYYY-MM-DD)
- `date_to`: End date (YYYY-MM-DD)
- `models`: Comma-separated list of models
- `status`: Filter by status

**Example Request:**
```bash
curl -X GET "http://localhost:5000/testing/api/export?format=csv&date_from=2025-08-01&models=anthropic_claude-3.7-sonnet"
```

**Response:**
- Content-Type varies by format
- Content-Disposition header for file download
- Actual file content in response body

## HTMX Endpoints

### 1. Partial Template Endpoints

These endpoints return HTML fragments for HTMX integration, enabling real-time UI updates without page reloads.

#### GET /testing/api/jobs (HTMX)
Returns HTML fragment for job list.

**Headers:**
```
HX-Request: true
Accept: text/html
```

**Response:** HTML table rows for job list

#### GET /testing/api/job/<job_id>/progress (HTMX)
Returns HTML fragment for progress display.

**Response:** HTML progress bar and status information

#### GET /testing/api/infrastructure-status (HTMX) 
Returns HTML fragment for infrastructure status.

**Response:** HTML status cards for each service

### 2. Modal Content Endpoints

#### GET /testing/api/job/<job_id>/results (HTMX)
Returns HTML modal content for test results.

#### GET /testing/api/new-test-form (HTMX)
Returns HTML form for creating new tests.

## Error Handling

### Standard Error Response Format

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid model name provided",
    "details": {
      "field": "model", 
      "provided_value": "invalid-model",
      "valid_options": ["anthropic_claude-3.7-sonnet", "openai_gpt-4o"]
    }
  },
  "timestamp": "2025-08-07T11:00:00Z",
  "request_id": "req-123456789"
}
```

### HTTP Status Codes

- **200 OK**: Successful request
- **201 Created**: Resource created successfully
- **400 Bad Request**: Invalid request parameters
- **404 Not Found**: Resource not found
- **409 Conflict**: Resource conflict (e.g., job already running)
- **422 Unprocessable Entity**: Validation errors
- **500 Internal Server Error**: Server error
- **503 Service Unavailable**: Infrastructure services unavailable

### Common Error Codes

- `VALIDATION_ERROR`: Request validation failed
- `RESOURCE_NOT_FOUND`: Requested resource does not exist
- `RESOURCE_CONFLICT`: Resource state conflict
- `INFRASTRUCTURE_ERROR`: Container services unavailable
- `DATABASE_ERROR`: Database operation failed
- `TIMEOUT_ERROR`: Operation timed out

## Rate Limiting

**Current Implementation**: None (development environment)

**Planned Implementation**:
- 100 requests per minute per IP
- 10 concurrent jobs per user
- 5 infrastructure management operations per minute

## WebSocket API (Future)

**Planned Endpoints:**
- `ws://localhost:5000/testing/jobs/live` - Real-time job updates
- `ws://localhost:5000/testing/infrastructure/live` - Infrastructure status updates

## SDK Examples

### Python SDK Example

```python
import requests
from typing import Dict, List, Optional

class ThesisTestingClient:
    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url
        self.session = requests.Session()
    
    def get_models(self) -> List[Dict]:
        """Get available models."""
        response = self.session.get(f"{self.base_url}/testing/api/models")
        response.raise_for_status()
        return response.json()["models"]
    
    def create_test(self, model: str, app_number: int, tools: List[str]) -> Dict:
        """Create a new test job."""
        data = {
            "model": model,
            "app_number": app_number,
            "test_types": ["security"],
            "tools": {"security": tools}
        }
        response = self.session.post(f"{self.base_url}/testing/api/create-test", json=data)
        response.raise_for_status()
        return response.json()
    
    def get_job_progress(self, job_id: int) -> Dict:
        """Get job progress."""
        response = self.session.get(f"{self.base_url}/testing/api/job/{job_id}/progress")
        response.raise_for_status()
        return response.json()
    
    def get_job_results(self, job_id: int) -> Dict:
        """Get job results."""
        response = self.session.get(f"{self.base_url}/testing/api/job/{job_id}/results")
        response.raise_for_status()
        return response.json()

# Usage
client = ThesisTestingClient()
models = client.get_models()
job = client.create_test("anthropic_claude-3.7-sonnet", 1, ["bandit", "safety"])
results = client.get_job_results(job["job"]["id"])
```

### JavaScript SDK Example

```javascript
class ThesisTestingClient {
    constructor(baseUrl = 'http://localhost:5000') {
        this.baseUrl = baseUrl;
    }
    
    async getModels() {
        const response = await fetch(`${this.baseUrl}/testing/api/models`);
        const data = await response.json();
        return data.models;
    }
    
    async createTest(model, appNumber, tools) {
        const data = {
            model,
            app_number: appNumber,
            test_types: ['security'],
            tools: { security: tools }
        };
        
        const response = await fetch(`${this.baseUrl}/testing/api/create-test`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        
        return await response.json();
    }
    
    async getJobProgress(jobId) {
        const response = await fetch(`${this.baseUrl}/testing/api/job/${jobId}/progress`);
        return await response.json();
    }
}

// Usage
const client = new ThesisTestingClient();
const models = await client.getModels();
const job = await client.createTest('anthropic_claude-3.7-sonnet', 1, ['bandit', 'safety']);
const progress = await client.getJobProgress(job.job.id);
```

## Testing the API

### Using curl

```bash
# Get available models
curl -X GET http://localhost:5000/testing/api/models

# Create a test
curl -X POST http://localhost:5000/testing/api/create-test \
  -H "Content-Type: application/json" \
  -d '{
    "model": "anthropic_claude-3.7-sonnet",
    "app_number": 1,
    "test_types": ["security"],
    "tools": {"security": ["bandit", "safety"]}
  }'

# Check job progress
curl -X GET http://localhost:5000/testing/api/job/123/progress

# Get infrastructure status
curl -X GET http://localhost:5000/testing/api/infrastructure-status
```

### Using Postman

Import the following collection structure:
- **Base URL**: `http://localhost:5000`
- **Collections**: Models, Jobs, Infrastructure, Export
- **Environment Variables**: `base_url`, `job_id`, `model_name`

This API documentation provides comprehensive coverage of all available endpoints for integrating with the AI Model Testing Framework.
