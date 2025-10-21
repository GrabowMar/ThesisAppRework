# OpenRouter Integration

## Quick Setup

```bash
# Set API key in .env
OPENROUTER_API_KEY=sk-or-v1-...

# For research (bypass Zero Data Retention)
OPENROUTER_ALLOW_ALL_PROVIDERS=true

# Optional metadata
OPENROUTER_SITE_URL=http://localhost:5000
OPENROUTER_SITE_NAME=ThesisAppRework
```

## Configuration

### Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `OPENROUTER_API_KEY` | API authentication | Required |
| `OPENROUTER_ALLOW_ALL_PROVIDERS` | Bypass ZDR restrictions | `true` |
| `OPENROUTER_SITE_URL` | Identify your app | `http://localhost:5000` |
| `OPENROUTER_SITE_NAME` | App name for tracking | `ThesisAppRework` |

### Model Configuration

Models loaded from `misc/openrouter_models.json`:
```json
{
  "openai_gpt-4": {
    "name": "GPT-4",
    "provider": "OpenAI",
    "context_length": 8192,
    "supports_function_calling": true
  }
}
```

## Usage

### Code Generation
```python
from app.services.openrouter_service import OpenRouterService

service = OpenRouterService()
response = service.generate_code(
    model="openai_gpt-4",
    prompt="Create a Flask app...",
    temperature=0.7
)
```

### Model Comparison
```bash
# Via API
POST /api/research/compare
{
  "models": ["openai_gpt-4", "anthropic_claude-3.5-sonnet"],
  "template_id": 1
}
```

## Research Mode

Setting `OPENROUTER_ALLOW_ALL_PROVIDERS=true` enables:
- Access to all models (including non-ZDR)
- Full model comparison capabilities
- Research and evaluation features

**Note**: For production, consider setting to `false` to comply with data retention policies.

## Model Gating

Disable specific models from analysis:
```env
DISABLED_ANALYSIS_MODELS=model1,model2,model3
```

Models will still be available for generation but not for automated analysis.

## Troubleshooting

**401 Unauthorized**: Check API key validity
**Model not found**: Verify model ID in `openrouter_models.json`
**Rate limits**: Implement exponential backoff
**ZDR errors**: Enable `OPENROUTER_ALLOW_ALL_PROVIDERS=true`

## API Reference

**Base URL**: `https://openrouter.ai/api/v1/chat/completions`

**Headers**:
```
Authorization: Bearer ${OPENROUTER_API_KEY}
HTTP-Referer: ${OPENROUTER_SITE_URL}
X-Title: ${OPENROUTER_SITE_NAME}
```

**Request Body**:
```json
{
  "model": "openai/gpt-4",
  "messages": [{"role": "user", "content": "..."}],
  "temperature": 0.7,
  "max_tokens": 2000
}
```
