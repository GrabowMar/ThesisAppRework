# Sample Generation API

This document describes the experimental Sample Generation endpoints that allow you to:

1. Load or define backend application templates
2. Trigger AI (OpenRouter) backed code generation for one or more templates and models
3. Retrieve generation results and extracted code block metadata
4. Inspect the organized on-disk project structure of generated outputs

> Status: Experimental / Internal. The API surface or storage layout may change.

## Environment / Prerequisites

Set an OpenRouter API key in the environment (or `.env`) before using generation endpoints:

```
# .env
OPENROUTER_API_KEY=sk-or-...  # Provide a valid key
LOG_LEVEL=INFO                # Adjust logging level (DEBUG, INFO, WARNING)
```

The application factory automatically loads `.env` on startup (using python-dotenv if available) and refreshes `OPENROUTER_API_KEY` every 60s, so you can rotate the key without restarting the server.

The service uses `aiohttp` for async HTTP calls. Ensure the dependency is installed in the main application environment (already present in analyzer requirements). If missing:

```
pip install aiohttp>=3.9.0
```

Generated files are written under the `generated/` directory (created automatically). By default ONLY extracted code files are persisted (raw markdown output is now disabled to reduce noise and disk usage). To also keep the full raw model output set an environment variable `SAMPLE_GEN_SAVE_MARKDOWN=1` before starting the app.

Default layout (markdown saving OFF):
```
generated/
  apps/
    <model_name_sanitized>/
      app<app_num>/
        backend/ (if applicable)
        frontend/ (if applicable)
        docker-compose.yml (if generated)
```

If `SAMPLE_GEN_SAVE_MARKDOWN=1` is set:
```
generated/
  apps/
    <model_name_sanitized>/app<app_num>/...
  markdown/
    <model_name_sanitized>/
      app_<num>_<name>.md  # raw model output (same content returned via result API)
```

## Base URL

All endpoints are prefixed with:

```
/api/sample-gen
```

## Endpoints

### Get Generation Status
`GET /api/sample-gen/status`

Returns current generation activity information:
```json
{
  "in_flight_count": 2,
  "max_concurrent": 5,
  "available_slots": 3,
  "in_flight_keys": ["template1_model_1234567890"]
}
```

### List Templates
`GET /api/sample-gen/templates`

Returns currently loaded templates (in-memory). Initially empty until you load or upsert.

### Load Templates From Directory
`POST /api/sample-gen/templates/load-dir`

Body:
```json
{ "directory": "path/to/templates" }
```
Loads `*.md` or `*.txt` files recursively; assigns incremental `app_num` order.

### Upsert Templates
`POST /api/sample-gen/templates/upsert`

Body:
```json
{
  "templates": [
    {"app_num": 1, "name": "orders_api", "content": "Spec text...", "requirements": ["Flask", "PostgreSQL"]}
  ]
}
```
If `app_num` duplicates an existing one it is replaced (in-memory reset currently rebuilds full list, so supply all desired templates each call).

### Generate (Single)
`POST /api/sample-gen/generate`

Body:
```json
{
  "template_id": "1",          // numeric id or template name
  "model": "openai/gpt-4.1",   // OpenRouter model slug
  "temperature": 0.6,           // optional
  "max_tokens": 14000           // optional
}
```
Response includes a `result_id` you can later query.

### Generate (Batch)
`POST /api/sample-gen/generate/batch`

Body:
```json
{
  "template_ids": ["1", "2"],
  "models": ["openai/gpt-4.1", "anthropic/claude-3.5"],
  "parallel_workers": 3
}
```
Executes combinations concurrently with a semaphore limiting in-flight tasks.

### List Results (With Filtering)
`GET /api/sample-gen/results?model=openai/gpt-4&success=true&limit=10&offset=0`

Returns metadata for all results with optional filtering:
- `model`: Filter by specific model name
- `success`: Filter by success status (true/false)
- `limit`: Maximum results to return (default: 100)
- `offset`: Skip first N results for pagination (default: 0)

Does not include full markdown content to save bandwidth.

### Get Result
`GET /api/sample-gen/results/<result_id>?include_content=true`

Retrieves a specific result. Add `include_content=true` to embed raw markdown model output.

### Delete Result
`DELETE /api/sample-gen/results/<result_id>`

Removes a specific result from both memory and database (if persisted).

### Cleanup Old Results
`POST /api/sample-gen/cleanup`

Body:
```json
{
  "max_age_days": 7,    // Delete results older than N days
  "dry_run": true       // Optional: preview without deletion
}
```
Removes old results based on age. Returns count of deleted items.

### Regenerate Result
`POST /api/sample-gen/regenerate`

Body:
```json
{
  "result_id": "existing_result_id",
  "temperature": 0.7,     // Optional override
  "max_tokens": 15000     // Optional override
}
```
Reruns generation using the same template and model as the original result.

### Get Project Structure
`GET /api/sample-gen/structure`

Returns current `generated/` directory structure summarizing extracted files.

## Notes & Limitations

- Persistence: Results are stored both in-memory and database (if available) with fallback support. Memory cache provides fast access while DB ensures durability.
- Concurrency: Maximum 5 concurrent generations to prevent API overload. Check `/status` endpoint for current activity.
- Rate Limits: 429 responses trigger backoff (30s * attempt). After retries, failures are recorded with `success=false`.
- Security: No authentication layer is enforced here; if deployed, wrap endpoints with existing auth/role checks.
- Async Strategy: Uses `asyncio.run` inside request handlers, which blocks the worker process. For production scale, integrate with Celery or background tasks.
- Result Management: Filtering, pagination, deletion, and cleanup endpoints provide comprehensive result lifecycle management.

## Example cURL Usage

```bash
# Check generation status
curl http://localhost:5000/api/sample-gen/status

# Load templates
curl -X POST http://localhost:5000/api/sample-gen/templates/upsert \
  -H "Content-Type: application/json" \
  -d '{"templates":[{"app_num":1,"name":"orders_api","content":"Orders API dealing with CRUD operations","requirements":["Flask","SQLAlchemy"]}]}'

# Generate code
curl -X POST http://localhost:5000/api/sample-gen/generate \
  -H "Content-Type: application/json" \
  -d '{"template_id":"1","model":"openai/gpt-4.1"}'

# List results with filtering
curl "http://localhost:5000/api/sample-gen/results?model=openai/gpt-4&success=true&limit=5"

# Get specific result with content
curl "http://localhost:5000/api/sample-gen/results/some_result_id?include_content=true"

# Regenerate existing result
curl -X POST http://localhost:5000/api/sample-gen/regenerate \
  -H "Content-Type: application/json" \
  -d '{"result_id":"some_result_id","temperature":0.8}'

# Delete result
curl -X DELETE http://localhost:5000/api/sample-gen/results/some_result_id

# Cleanup old results (dry run)
curl -X POST http://localhost:5000/api/sample-gen/cleanup \
  -H "Content-Type: application/json" \
  -d '{"max_age_days":7,"dry_run":true}'
```

## Future Enhancements (Ideas)

- ✅ Persist results & metadata to database (IMPLEMENTED)
- ✅ Result filtering and pagination (IMPLEMENTED)
- ✅ Result management (deletion, cleanup, regeneration) (IMPLEMENTED)
- ✅ Concurrency controls (IMPLEMENTED)
- Streaming responses or SSE for long generations
- Background task queue integration
- Automatic model capability discovery via OpenRouter catalog
- Template versioning and diffing
- Security / quota controls
- Content size caps and filesystem storage for large results
- Duplicate detection via content hashing
- Batch progress reporting with interim status updates
