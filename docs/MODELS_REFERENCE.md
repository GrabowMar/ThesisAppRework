# Models Reference

Reference documentation for supported AI models and their capabilities.

## Supported Providers

| Provider | Models | Capabilities |
|----------|--------|--------------|
| OpenAI | GPT-4, GPT-4 Turbo, GPT-3.5 | Code generation, analysis |
| Anthropic | Claude 3 Opus, Sonnet, Haiku | Code generation, reasoning |
| Google | Gemini Pro, Gemini Ultra | Multi-modal analysis |
| Meta | Llama 2, Code Llama | Open-source alternatives |
| Mistral | Mistral 7B, Mixtral | Fast inference |

## Model Slug Format

Models are identified by slugs in the format: `{provider}_{model-name}`

Examples:
- `openai_gpt-4`
- `anthropic_claude-3-opus`
- `google_gemini-pro`

### Slug Normalization

The system automatically normalizes model slugs to handle variants:

```python
from app.utils.slug_utils import normalize_model_slug

# These all normalize to the same slug:
normalize_model_slug("openai/gpt-4")      # "openai_gpt-4"
normalize_model_slug("OpenAI_GPT-4")      # "openai_gpt-4"
normalize_model_slug("openai_gpt-4:free") # "openai_gpt-4" (strips :free suffix)
```

The analyzer manager also tries variant lookups (see `_normalize_and_validate_app` in [analyzer/analyzer_manager.py](../analyzer/analyzer_manager.py)).

## Model Capabilities

### Code Generation

All models support generating:
- Flask/Python backends
- React/JavaScript frontends
- Full-stack applications

### Analysis Support

| Model | Static | Dynamic | Performance | AI Review |
|-------|--------|---------|-------------|-----------|
| GPT-4 | ✓ | ✓ | ✓ | ✓ |
| Claude 3 | ✓ | ✓ | ✓ | ✓ |
| Gemini | ✓ | ✓ | ✓ | ✓ |
| Llama 2 | ✓ | ✓ | ✓ | Limited |

## Generated Application Structure

Each generated app follows this structure:

```
generated/apps/{model_slug}/app{N}/
├── backend/
│   ├── app.py
│   ├── requirements.txt
│   └── ...
├── frontend/
│   ├── src/
│   ├── package.json
│   └── ...
├── .env
├── docker-compose.yml
└── README.md
```

### Application Tracking

Generated apps are tracked in the database (`GeneratedApplication` model) with:
- `model_slug` - Normalized model identifier
- `app_number` - Sequence number
- `provider` - Model provider (e.g., "openai", "anthropic")
- `template_name` - Requirement template used
- `generation_mode` - GUARDED or UNGUARDED
- `container_status` - Current Docker state
- `missing_since` - Timestamp when filesystem directory went missing (7-day grace period before deletion)
- `parent_app_id` - Links to parent if regeneration
- `batch_id` - Groups apps created together
- Generation failure tracking: `generation_failed`, `failure_reason`, `failure_count`
- Fix tracking: `fixes_applied`, `fix_count`, `last_fix_applied_at`, `analysis_status`

> **Note**: If an app's filesystem directory is deleted, it's marked with `missing_since` but not removed from DB for 7 days, allowing recovery.

## Port Allocation

Each app gets unique ports:

| Component | Port Range |
|-----------|------------|
| Backend | 3000-3999 |
| Frontend | 4000-4999 |
| Database | 5432+ |

Port assignments stored in `misc/port_config.json`.

## Model Configuration

### Via API

```bash
curl -X POST http://localhost:5000/api/generation/create \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "model_slug": "openai_gpt-4",
    "template": "crud_todo_list",
    "app_number": 1
  }'
```

### Via Web UI

1. Navigate to **Applications → Generate**
2. Select model from dropdown
3. Choose template
4. Configure options
5. Click **Generate**

## Model Comparison

When analyzing generated apps, consider:

| Metric | Description |
|--------|-------------|
| Code Quality | Linting score, type coverage |
| Security | Vulnerability count by severity |
| Performance | Response time, throughput |
| Compliance | Requirements coverage |

## Templates

Available application templates in `misc/requirements/`:

| Template | Category | Description |
|----------|----------|-------------|
| `crud_todo_list` | CRUD | Basic todo application |
| `crud_book_library` | CRUD | Book management system |
| `auth_user_login` | Auth | User authentication |
| `ecommerce_cart` | E-commerce | Shopping cart |
| `realtime_chat_room` | Real-time | WebSocket chat |
| `api_weather_display` | API | Weather data display |

## Related

- [Architecture](ARCHITECTURE.md)
- [Background Services](BACKGROUND_SERVICES.md)
- [API Reference](api-reference.md)
- [Analyzer Guide](ANALYZER_GUIDE.md)
- [Development Guide](development-guide.md)
