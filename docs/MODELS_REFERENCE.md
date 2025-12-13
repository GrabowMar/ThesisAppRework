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
- [API Reference](api-reference.md)
- [Analyzer Guide](ANALYZER_GUIDE.md)
