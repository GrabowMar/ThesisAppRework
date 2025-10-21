# 🤖 AI Model Quick Start Guide

## For Claude, GPT-4, and Other AI Assistants

### Authentication

**Your access credentials:**
```
Base URL: http://localhost:5000
Token: [Get from web UI: User Menu → API Access → Generate Token]
Header: Authorization: Bearer [your-token]
```

### Example: Getting Started with Claude

**User provides to Claude:**
```
I'm giving you API access to my Thesis Platform:
- Base URL: http://localhost:5000
- Token: abc123xyz789...

Please list all available AI models and their capabilities.
```

**Claude would execute:**
```bash
curl -H "Authorization: Bearer abc123xyz789..." \
     http://localhost:5000/api/models
```

### Key Endpoints

| Endpoint | Method | Description | Example |
|----------|--------|-------------|---------|
| `/api/models` | GET | List all AI models | `curl -H "Authorization: Bearer TOKEN" URL/api/models` |
| `/api/applications` | GET | List generated apps | `curl -H "Authorization: Bearer TOKEN" URL/api/applications` |
| `/api/gen/generate` | POST | Generate new app | See below |
| `/api/dashboard/stats` | GET | System statistics | `curl -H "Authorization: Bearer TOKEN" URL/api/dashboard/stats` |
| `/api/health` | GET | Health check (no auth) | `curl URL/api/health` |
| `/api/tokens/verify` | GET | Verify token validity | `curl -H "Authorization: Bearer TOKEN" URL/api/tokens/verify` |

### Example: Generate Application

```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai_gpt-4",
    "template_id": 1,
    "app_name": "my-awesome-app",
    "description": "A sample application"
  }' \
  http://localhost:5000/api/gen/generate
```

### Python Client Example

```python
import requests

class ThesisPlatformClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def list_models(self):
        """Get all available AI models."""
        response = requests.get(
            f"{self.base_url}/api/models",
            headers=self.headers
        )
        return response.json()
    
    def list_applications(self):
        """Get all generated applications."""
        response = requests.get(
            f"{self.base_url}/api/applications",
            headers=self.headers
        )
        return response.json()
    
    def generate_app(self, model: str, template_id: int, app_name: str):
        """Generate a new application."""
        payload = {
            "model": model,
            "template_id": template_id,
            "app_name": app_name
        }
        response = requests.post(
            f"{self.base_url}/api/gen/generate",
            json=payload,
            headers=self.headers
        )
        return response.json()
    
    def get_stats(self):
        """Get dashboard statistics."""
        response = requests.get(
            f"{self.base_url}/api/dashboard/stats",
            headers=self.headers
        )
        return response.json()

# Usage
client = ThesisPlatformClient(
    base_url="http://localhost:5000",
    token="your-token-here"
)

# List all models
models = client.list_models()
print(f"Available models: {len(models['models'])}")

# Generate an app
result = client.generate_app(
    model="openai_gpt-4",
    template_id=1,
    app_name="test-app"
)
print(f"Generation status: {result['status']}")
```

### JavaScript/Node.js Example

```javascript
class ThesisPlatformClient {
  constructor(baseUrl, token) {
    this.baseUrl = baseUrl;
    this.headers = {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    };
  }

  async listModels() {
    const response = await fetch(`${this.baseUrl}/api/models`, {
      headers: this.headers
    });
    return await response.json();
  }

  async generateApp(model, templateId, appName) {
    const response = await fetch(`${this.baseUrl}/api/gen/generate`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify({
        model,
        template_id: templateId,
        app_name: appName
      })
    });
    return await response.json();
  }
}

// Usage
const client = new ThesisPlatformClient(
  'http://localhost:5000',
  'your-token-here'
);

const models = await client.listModels();
console.log(`Found ${models.models.length} models`);
```

### Common Tasks

#### 1. List All Available Models
```bash
curl -H "Authorization: Bearer TOKEN" \
     http://localhost:5000/api/models
```

#### 2. Get System Health
```bash
curl http://localhost:5000/api/health
```

#### 3. Generate a React Application
```bash
curl -X POST \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model":"openai_gpt-4","template_id":1,"app_name":"react-demo"}' \
  http://localhost:5000/api/gen/generate
```

#### 4. List Generated Applications
```bash
curl -H "Authorization: Bearer TOKEN" \
     http://localhost:5000/api/applications
```

#### 5. Get Dashboard Statistics
```bash
curl -H "Authorization: Bearer TOKEN" \
     http://localhost:5000/api/dashboard/stats
```

### Error Handling

**Unauthorized (401)**
```json
{
  "error": "Unauthorized",
  "message": "Authentication required"
}
```
→ Check token is valid and properly formatted

**Not Found (404)**
```json
{
  "error": "Not Found"
}
```
→ Check endpoint URL is correct

**Server Error (500)**
```json
{
  "error": "Internal Server Error",
  "message": "..."
}
```
→ Check application logs

### Tips for AI Models

1. **Always include the Authorization header** with your token
2. **No cookies needed** - pure stateless API access
3. **JSON responses** for all API endpoints
4. **Health endpoint is public** - use it to check connectivity
5. **Tokens don't expire** - but can be revoked by the user
6. **One token per user** - generating a new one invalidates the old one

### Verification

Test your token is working:
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:5000/api/tokens/verify
```

Should return:
```json
{
  "valid": true,
  "user": {
    "username": "admin",
    "email": "admin@thesis.local",
    "is_admin": true
  }
}
```

### Security Notes

- Tokens are stored securely with bcrypt-level protection
- Use HTTPS in production environments
- Never log or expose tokens in error messages
- Tokens grant full access equivalent to logged-in user
- Revoke tokens when no longer needed
