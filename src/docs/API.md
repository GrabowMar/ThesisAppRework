# API Documentation

## Overview

The ThesisApp API provides programmatic access to AI model testing functionality.

## Base URL

```
http://localhost:5000/api
```

## Authentication

Currently, no authentication is required for API endpoints.

## Endpoints

### Models

#### GET /api/models

Get all available AI models.

**Response:**
```json
{
  "models": [
    {
      "id": 1,
      "model_slug": "anthropic_claude-3.7-sonnet",
      "provider": "anthropic",
      "model_name": "Claude 3.7 Sonnet",
      "supports_vision": false,
      "supports_function_calling": true,
      "app_count": 30
    }
  ]
}
```

#### GET /api/models/{model_slug}/apps

Get applications for a specific model.

**Response:**
```json
{
  "model_slug": "anthropic_claude-3.7-sonnet",
  "apps": [
    {
      "app_number": 1,
      "app_type": "login",
      "container_status": "stopped",
      "backend_port": 6051,
      "frontend_port": 9051
    }
  ]
}
```

## Error Responses

All endpoints return appropriate HTTP status codes:

- `200` - Success
- `400` - Bad Request
- `404` - Not Found
- `500` - Internal Server Error
- `501` - Not Implemented

Error response format:
```json
{
  "error": "Error message",
  "status": "error"
}
```
