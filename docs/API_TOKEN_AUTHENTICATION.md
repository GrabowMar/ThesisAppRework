# API Token Authentication for AI Models

## Overview

The Thesis Platform now supports dual authentication:
- **Cookie-based sessions** for browser users (unchanged)
- **API token authentication** for programmatic access (AI models, curl, scripts)

## Quick Start for AI Models (like Claude)

### 1. Get Your Token

1. Log in to the web interface
2. Go to **User Menu → API Access**
3. Click "Generate New Token"
4. Copy and save the token (it's only shown once)

### 2. Use the Token

Include the token in the `Authorization` header:

```bash
curl -H "Authorization: Bearer YOUR_TOKEN_HERE" \
     http://localhost:5000/api/models
```

### 3. Token in Query Parameter (Alternative)

For convenience, you can also pass the token as a query parameter:

```bash
curl "http://localhost:5000/api/models?token=YOUR_TOKEN_HERE"
```

**Note:** Header method is more secure and recommended.

## For AI Assistants

When an AI model (like Claude, GPT-4, etc.) wants to interact with this platform:

### Authentication Setup
```
Base URL: http://localhost:5000
Token: [Your generated API token]
Header: Authorization: Bearer [token]
```

### Common API Endpoints

#### List Models
```bash
GET /api/models
# Returns all available AI models with capabilities
```

#### List Applications
```bash
GET /api/applications
# Returns all generated applications
```

#### Generate Application
```bash
POST /api/gen/generate
Content-Type: application/json

{
  "model": "openai_gpt-4",
  "template_id": 1,
  "app_name": "my-app"
}
```

#### Get Dashboard Stats
```bash
GET /api/dashboard/stats
# Returns system statistics and metrics
```

#### Health Check
```bash
GET /api/health
# Check if the system is running
```

#### Verify Token
```bash
GET /api/tokens/verify
Authorization: Bearer YOUR_TOKEN
# Verify if your token is valid
```

## Token Management

### Generate Token (Web UI or API)
```bash
POST /api/tokens/generate
# Requires being logged in with cookie
# Returns: { "token": "...", "usage": "..." }
```

### Revoke Token
```bash
POST /api/tokens/revoke
# Requires being logged in
# Invalidates current token
```

### Check Token Status
```bash
GET /api/tokens/status
# Returns: { "has_token": true/false, "created_at": "..." }
```

## Example: Claude Using the API

```markdown
I have access to your Thesis Platform API with the following credentials:
- Base URL: http://localhost:5000
- Token: abc123...xyz789

Could you list all available models and generate a sample React application?
```

Claude would then:
1. Call `GET /api/models` with the token
2. Call `POST /api/gen/generate` with appropriate payload

## Python Example

```python
import requests

BASE_URL = "http://localhost:5000"
TOKEN = "your_token_here"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# List models
response = requests.get(f"{BASE_URL}/api/models", headers=headers)
models = response.json()

# Generate app
payload = {
    "model": "openai_gpt-4",
    "template_id": 1,
    "app_name": "test-app"
}
response = requests.post(f"{BASE_URL}/api/gen/generate", 
                        json=payload, 
                        headers=headers)
result = response.json()
```

## Security Notes

1. **Never commit tokens** to version control
2. **Tokens are permanent** until revoked
3. **One token per user** - generating a new one invalidates the old one
4. **Tokens bypass 2FA** (if enabled) - keep them secure
5. **Use HTTPS** in production to prevent token interception

## Unauthorized Response

If authentication fails, you'll receive:

```json
{
  "error": "Unauthorized",
  "message": "Authentication required"
}
```

With HTTP status code **401**.

## CLI Script for Token Generation

```bash
# First login and get session cookie
curl -c cookies.txt -X POST http://localhost:5000/auth/login \
  -d "username=admin&password=admin123"

# Generate token using session
curl -b cookies.txt -X POST http://localhost:5000/api/tokens/generate

# Save the returned token for future use
```

## Troubleshooting

### "Invalid or expired token"
- Token may have been revoked
- Generate a new token from the web UI

### "Unauthorized" on all requests
- Check that token is included in header
- Verify token format: `Bearer YOUR_TOKEN`
- Ensure user account is still active

### Token not working immediately after generation
- There's no delay - tokens work instantly
- Check for typos in the token value
- Ensure no extra whitespace in header
