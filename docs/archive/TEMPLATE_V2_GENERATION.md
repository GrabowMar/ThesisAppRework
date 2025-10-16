# Template V2 Generation Guide

## Overview

The V2 template system now fully integrates with the existing code generation pipeline. You can generate applications using:

1. **Modular Requirements** (JSON files in `misc/requirements/`)
2. **Scaffolding Code** (minimal working templates in `misc/scaffolding/`)
3. **Jinja2 Templates** (prompt templates in `misc/templates/`)

This guide explains how to use the V2 generation endpoints.

---

## Quick Start

### 1. Generate Backend Code

**Endpoint:** `POST /api/v2/templates/generate/backend`

**Request:**
```json
{
  "requirement_id": "base64_converter",
  "model": "openai/gpt-4",
  "scaffolding_type": "react-flask",
  "template_type": "two-query",
  "temperature": 0.7,
  "max_tokens": 4000
}
```

**Response:**
```json
{
  "success": true,
  "message": "Backend code generated successfully",
  "data": {
    "result_id": "20240101_120000_base64_converter_backend",
    "app_num": 100,
    "success": true,
    "model": "openai/gpt-4",
    "requirement_id": "base64_converter",
    "requirement_name": "Base64 Encoder/Decoder",
    "duration": 12.5,
    "total_tokens": 3245
  }
}
```

### 2. Generate Frontend Code

**Endpoint:** `POST /api/v2/templates/generate/frontend`

**Request:**
```json
{
  "requirement_id": "base64_converter",
  "model": "openai/gpt-4",
  "scaffolding_type": "react-flask",
  "template_type": "two-query",
  "temperature": 0.7,
  "max_tokens": 4000
}
```

**Response:** Same structure as backend response.

---

## Available Requirements

Current V2 requirements in `misc/requirements/`:

| ID | Name | Description | Backend Reqs | Frontend Reqs |
|----|------|-------------|--------------|---------------|
| `xsd_verifier` | XML Schema Validator | Validate XML against XSD schemas | 6 | 8 |
| `base64_converter` | Base64 Encoder/Decoder | Encode/decode Base64 | 6 | 8 |
| `todo_app` | Simple Todo List | CRUD todo app | 7 | 10 |

---

## Generation Workflow

### Behind the Scenes

When you call the generate endpoints, the system:

1. **Loads Requirements**: Reads JSON file from `misc/requirements/{id}.json`
2. **Loads Scaffolding**: Gets minimal code from `misc/scaffolding/{type}/`
3. **Renders Template**: Uses Jinja2 to combine requirements + scaffolding into prompt
4. **Creates Template Object**: Wraps prompt in internal Template structure
5. **Calls Generation Service**: Uses existing `SampleGenerationService.generate_async()`
6. **Extracts Code**: Parses response, extracts code blocks, organizes files
7. **Saves Output**: Writes to `generated/apps/{model}/app_100/`

### App Number Assignment

V2 templates use **app_num 100** to avoid conflicts with old template system (which uses 1-60+).

### Output Structure

Generated code appears in:
```
generated/apps/{model}/app_100/
├── backend/
│   ├── app.py
│   ├── requirements.txt
│   └── ... (other files)
├── frontend/
│   ├── package.json
│   ├── src/
│   └── ... (other files)
└── metadata.json
```

---

## Parameter Reference

### Required Parameters

- `requirement_id` (string): ID of the requirement JSON file (e.g., "todo_app")
- `model` (string): Model identifier (e.g., "openai/gpt-4", "anthropic/claude-3-sonnet")

### Optional Parameters

- `scaffolding_type` (string, default: "react-flask"): Which scaffolding to use
- `template_type` (string, default: "two-query"): Which template set to use
- `temperature` (float, default: 0.7): Model temperature (0.0-2.0)
- `max_tokens` (int, default: 4000): Maximum tokens in response

---

## Advanced Usage

### Preview Before Generation

Use the preview endpoint to see what prompt will be sent:

**Endpoint:** `POST /api/v2/templates/preview`

**Request:**
```json
{
  "requirement_id": "todo_app",
  "scaffolding_type": "react-flask",
  "template_type": "two-query"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "backend": {
      "prompt": "# Goal: Generate a Secure & Production-Ready Flask...",
      "length": 8307
    },
    "frontend": {
      "prompt": "# Goal: Generate an Intuitive & Responsive React...",
      "length": 11907
    }
  }
}
```

### Generate Only Backend or Frontend

The endpoints are separated, so you can:
- Generate only backend: `POST /generate/backend`
- Generate only frontend: `POST /generate/frontend`
- Generate both: Call both endpoints sequentially

---

## Adding New Requirements

### 1. Create Requirements JSON

File: `misc/requirements/my_app.json`

```json
{
  "app_id": "my_app",
  "name": "My Application",
  "description": "What the app does",
  "backend_requirements": [
    "1. First backend feature",
    "2. Second backend feature"
  ],
  "frontend_requirements": [
    "1. First UI feature",
    "2. Second UI feature"
  ]
}
```

### 2. Test with Preview

```bash
curl -X POST http://localhost:5000/api/v2/templates/preview \
  -H "Content-Type: application/json" \
  -d '{"requirement_id": "my_app"}'
```

### 3. Generate Code

```bash
curl -X POST http://localhost:5000/api/v2/templates/generate/backend \
  -H "Content-Type: application/json" \
  -d '{
    "requirement_id": "my_app",
    "model": "openai/gpt-4"
  }'
```

---

## Troubleshooting

### Issue: "Requirement not found"

**Solution:** Check that `misc/requirements/{id}.json` exists and is valid JSON.

### Issue: "Model not found"

**Solution:** Verify model identifier. Use `/api/models` to list available models.

### Issue: "Generation failed"

**Solution:** 
1. Check `OPENROUTER_API_KEY` is set in `.env`
2. Verify model has capacity (not rate-limited)
3. Check logs in `logs/` directory

### Issue: "Invalid scaffolding type"

**Solution:** Currently only `react-flask` is supported. Check `misc/scaffolding/` for available types.

---

## Integration with UI

To integrate V2 templates into the web UI, see:
- Frontend templates: `src/templates/pages/sample_generator/`
- JavaScript: `src/static/js/sample_generator/`
- Example integration in `docs/TEMPLATE_V2_UI_INTEGRATION.md`

---

## Comparison: V1 vs V2

| Feature | V1 (Old) | V2 (New) |
|---------|----------|----------|
| Storage | 60 monolithic .md files | 3 requirements JSONs |
| Scaffolding | Embedded in each template | Separate, reusable files |
| Maintenance | 98% duplication | 0% duplication |
| Extensibility | Add full template file | Add JSON requirements |
| Template Engine | None (raw markdown) | Jinja2 |
| Flexibility | Fixed structure | Composable parts |

---

## Testing

Run integration tests:

```bash
# Test V2 template rendering
python scripts/test_template_v2.py

# Test V2 generation integration
python scripts/test_template_v2_integration.py
```

---

## API Reference

See full API documentation: `docs/TEMPLATE_V2_QUICK_REF.md`

### All V2 Endpoints

- `GET /api/v2/templates/requirements` - List available requirements
- `GET /api/v2/templates/scaffolding` - List scaffolding types
- `POST /api/v2/templates/preview` - Preview rendered templates
- `POST /api/v2/templates/render/backend` - Render backend only
- `POST /api/v2/templates/render/frontend` - Render frontend only
- `POST /api/v2/templates/generate/backend` - Generate backend code
- `POST /api/v2/templates/generate/frontend` - Generate frontend code

---

## Next Steps

1. **Test Generation**: Try generating with different requirements and models
2. **Update UI**: Integrate V2 endpoints into web interface
3. **Add Requirements**: Create more requirement JSONs for different app types
4. **Extend Scaffolding**: Add new scaffolding types (e.g., Vue+Django, Angular+NestJS)
5. **Custom Templates**: Create specialized template variants for different use cases
