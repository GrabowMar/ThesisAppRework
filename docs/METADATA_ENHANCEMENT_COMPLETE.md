# Metadata Collection Enhancement - Complete

## Summary

Successfully enhanced the generation system to collect comprehensive metadata from OpenRouter API, including native token counts, cost information, and provider details. Also cleaned up the folder structure to maintain only 3 top-level directories.

## Changes Made

### 1. Enhanced Metadata Collection (`src/app/services/generation.py`)

**Added asyncio import:**
- Added `import asyncio` for async sleep functionality

**Updated `_save_metadata` method:**
- Changed from sync to async function signature
- After saving basic metadata, now makes secondary API call to OpenRouter's `/api/v1/generation` endpoint
- Waits 1 second after initial response before querying generation stats (per OpenRouter docs)
- Collects comprehensive metadata including:

**Basic Fields (from initial response):**
- `run_id`: Unique identifier for the generation run
- `timestamp`: ISO format timestamp of metadata save
- `model_slug`: Canonical model identifier
- `app_num`: Application number
- `component`: 'frontend' or 'backend'
- `model_used`: OpenRouter model ID
- `status`: HTTP response status
- `generation_id`: OpenRouter generation ID for stats lookup
- `prompt_tokens`: Normalized token count (GPT-4o tokenizer)
- `completion_tokens`: Normalized output tokens
- `total_tokens`: Sum of prompt + completion
- `finish_reason`: Normalized finish reason
- `native_finish_reason`: Provider-specific finish reason
- `temperature`: Generation temperature parameter
- `max_tokens`: Maximum token limit

**OpenRouter-Specific Fields (from /api/v1/generation endpoint):**
- `native_tokens_prompt`: Actual billing tokens for input (model's native tokenizer)
- `native_tokens_completion`: Actual billing tokens for output
- `provider_name`: Provider that served the request (e.g., "Anthropic", "OpenAI")
- `model_used_actual`: Actual model used by provider
- `total_cost`: Total cost in USD (based on native tokens)
- `generation_time_ms`: Time taken to generate response in milliseconds
- `created_at`: Timestamp from OpenRouter
- `cancelled`: Whether generation was cancelled
- `upstream_id`: Provider's generation ID

**Error Handling:**
- If generation stats fetch fails, adds `generation_stats_error` field with error message
- Continues gracefully if OpenRouter endpoint unavailable

### 2. Cleaned Up Folder Structure (`src/app/paths.py`)

**Removed empty metadata subdirectories:**
- Deleted: `capabilities/`, `config/`, `failures/`, `large_content/`, `logs/`, `markdown/`, `stats/`, `summaries/`, `tmp/`
- Kept only: `indices/` (where `runs/` subdirectory contains per-run metadata)

**Updated `_GENERATED_DIRS` list:**
- Now only creates essential directories:
  - `generated/`
  - `generated/apps/`
  - `generated/raw/`
  - `generated/raw/responses/`
  - `generated/raw/payloads/`
  - `generated/metadata/`
  - `generated/metadata/indices/`

**Legacy paths retained** (for backwards compatibility in code, but not auto-created):
- `GENERATED_MARKDOWN_DIR`, `GENERATED_STATS_DIR`, etc. still defined but not in `_GENERATED_DIRS`
- Future code can reference these paths if needed, directories created on-demand

### 3. Test Scripts

**Created `scripts/test_metadata_collection.py`:**
- Tests scaffolding-only generation with test_model
- Verifies folder structure (apps, raw, metadata only)
- Confirms metadata subfolder contains only `indices/`

**Created `scripts/test_full_metadata.py`:**
- Tests full generation with real OpenRouter API call
- Uses `anthropic_claude-4.5-haiku-20251001` for fast testing
- Verifies all metadata fields present:
  - Basic fields (8/8 ✓)
  - Token fields (3/3 ✓)
  - OpenRouter fields (5/5 ✓)
- Reports comprehensive metadata with native tokens, cost, provider info

## Verification Results

### Test Output (Backend Generation Only)

```
=== Testing FULL Metadata Collection with Real API Call ===

Generating: anthropic_claude-4.5-haiku-20251001/app1 with template 1
Component: BACKEND ONLY (faster test)

✓ Generation result: True
  - Scaffolded: True
  - Backend generated: True

=== Verifying Folder Structure ===
Top-level folders: ['apps', 'metadata', 'raw']
✓ Correct structure: only apps, raw, metadata folders

Metadata subfolders: ['indices']
✓ Metadata only has indices subfolder

=== Verifying Raw Outputs ===
✓ Payloads written: [1 file]
✓ Responses written: [1 file]

=== Verifying Comprehensive Metadata ===
✓ Metadata written: [1 file]

Basic fields:
  ✓ run_id: anthropic_claude-4.5-haiku-20251001_app1_backend_20251019T194618
  ✓ timestamp: 2025-10-19T19:46:35.194175
  ✓ model_slug: anthropic_claude-4.5-haiku-20251001
  ✓ app_num: 1
  ✓ component: backend
  ✓ model_used: anthropic/claude-haiku-4.5
  ✓ status: 200
  ✓ generation_id: gen-1760895978-ebkEu4Oi0tWUe0I5IvmG

Token fields:
  ✓ prompt_tokens: 1703
  ✓ completion_tokens: 3322
  ✓ total_tokens: 5025

OpenRouter-specific fields:
  ✓ native_tokens_prompt: 1703
  ✓ native_tokens_completion: 3322
  ✓ provider_name: Anthropic
  ✓ total_cost: 0.018313
  ✓ generation_time_ms: 14947

✓ COMPLETE: All OpenRouter metadata fields present!
```

## File Organization

### Final Structure
```
generated/
├── apps/                    # Generated applications with Docker infrastructure
│   └── {model_slug}/
│       └── app{N}/
│           ├── docker-compose.yml
│           ├── backend/
│           └── frontend/
├── raw/                     # Raw API artifacts
│   ├── payloads/           # Request payloads sent to OpenRouter
│   │   └── {model_slug}/
│   │       └── app{N}/
│   │           └── {run_id}_payload.json
│   └── responses/          # Raw API responses from OpenRouter
│       └── {model_slug}/
│           └── app{N}/
│               └── {run_id}_response.json
└── metadata/               # Comprehensive metadata
    └── indices/
        └── runs/           # Per-run metadata
            └── {model_slug}/
                └── app{N}/
                    └── {run_id}_metadata.json
```

### Metadata File Structure
```json
{
  "run_id": "model_app1_backend_20251019T194618",
  "timestamp": "2025-10-19T19:46:35.194175",
  "model_slug": "anthropic_claude-4.5-haiku-20251001",
  "app_num": 1,
  "component": "backend",
  "model_used": "anthropic/claude-haiku-4.5",
  "status": 200,
  "generation_id": "gen-1760895978-ebkEu4Oi0tWUe0I5IvmG",
  
  "prompt_tokens": 1703,
  "completion_tokens": 3322,
  "total_tokens": 5025,
  
  "native_tokens_prompt": 1703,
  "native_tokens_completion": 3322,
  "provider_name": "Anthropic",
  "total_cost": 0.018313,
  "generation_time_ms": 14947,
  
  "finish_reason": "stop",
  "native_finish_reason": "end_turn",
  "temperature": 0.3,
  "max_tokens": 16000,
  
  "model_used_actual": "anthropic/claude-haiku-4.5",
  "created_at": "2025-10-19T19:46:35Z",
  "cancelled": false,
  "upstream_id": "msg_01abcd..."
}
```

## Benefits

1. **Complete Cost Tracking**: Native token counts + USD cost for accurate billing analysis
2. **Provider Transparency**: Know which provider served each request (important for load-balanced models)
3. **Performance Metrics**: Generation time in milliseconds for benchmarking
4. **Clean Structure**: Only 3 top-level folders instead of 10+
5. **Comprehensive Audit Trail**: Every generation has complete metadata for debugging/analysis
6. **Backwards Compatible**: Legacy path constants still defined, won't break existing code

## Testing

Run tests to verify:
```powershell
# Structure test (scaffolding only)
python scripts/test_metadata_collection.py

# Full metadata test (real API call)
python scripts/test_full_metadata.py
```

## Notes

- OpenRouter requires ~500-1500ms delay before generation stats are available
- Implementation uses 1000ms (1 second) delay which worked reliably in testing
- If stats fetch fails, generation still succeeds with basic metadata
- Normalized tokens (from main response) may differ from native tokens (used for billing)
- All metadata consolidated into single JSON file per generation run
