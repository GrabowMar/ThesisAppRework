# Fix for Duplicate Application Entries

## Issue
The Applications view was showing 4 Anthropic Claude Sonnet applications instead of 2, with two different slug formats appearing in the database.

## Root Cause
There were **duplicate entries** in the database with inconsistent naming conventions:
1. `anthropic_claude-3.5-sonnet` (with dot: `.5`) - **correct format from OpenRouter**
2. `anthropic_claude-3_5-sonnet` (with underscore: `_5`) - **incorrect filesystem-generated format**

## Changes Made

### 1. Database Cleanup - GeneratedApplication Table
- Deleted 2 orphaned entries with dot format (`anthropic_claude-3.5-sonnet`)
- Updated remaining 2 entries from underscore format to dot format
- **Result**: 2 applications with canonical slug `anthropic_claude-3.5-sonnet`

### 2. Database Cleanup - ModelCapability Table
- Removed duplicate entry with underscore format
- Kept the official OpenRouter format with dot (`anthropic_claude-3.5-sonnet`)
- **Result**: Single model entry matching OpenRouter's `anthropic/claude-3.5-sonnet`

### 3. Filesystem Rename
- Renamed folder from `anthropic_claude-3_5-sonnet` to `anthropic_claude-3.5-sonnet`
- **Result**: Filesystem now matches database canonical format

### 4. Docker Compose Updates
- Updated `app1/docker-compose.yml` container names:
  - `anthropic_claude-3_5-sonnet_backend_5061` → `anthropic_claude-3.5-sonnet_backend_5061`
  - `anthropic_claude-3_5-sonnet_frontend_8061` → `anthropic_claude-3.5-sonnet_frontend_8061`
- Updated `app2/docker-compose.yml` container names:
  - `anthropic_claude-3_5-sonnet_backend_5063` → `anthropic_claude-3.5-sonnet_backend_5063`
  - `anthropic_claude-3_5-sonnet_frontend_8063` → `anthropic_claude-3.5-sonnet_frontend_8063`

## Final State
✓ **Database**: 2 applications with `anthropic_claude-3.5-sonnet`
✓ **ModelCapability**: 1 model with `anthropic_claude-3.5-sonnet`
✓ **Filesystem**: 1 folder `anthropic_claude-3.5-sonnet/`
✓ **Docker**: Container names use consistent dot format

## Verification
Total applications in database:
- `anthropic_claude-3.5-sonnet/app1`
- `anthropic_claude-3.5-sonnet/app2`
- `x-ai_grok-4-fast/app1`
- `x-ai_grok-4-fast/app2`

The Applications view should now correctly show only 2 Anthropic applications instead of 4.

## Code Fixes Applied

### Sample Generation Service
Updated all regex patterns in `src/app/services/sample_generation_service.py`:
- **Line 1777**: `_scaffold_if_needed()` method
- **Line 2172**: `save_markdown()` method  
- **Line 2401**: `_write_raw_api_snapshots()` method
- **Line 2984**: Filesystem sync block

**Changed Pattern:**
```python
# Before (WRONG - converts dots to underscores):
safe_model = re.sub(r'[^\w\-_]', '_', model_name)

# After (CORRECT - preserves dots):
safe_model = re.sub(r'[^\w\-_.]', '_', model_name)
```

### Generation Statistics Service
Updated regex patterns in `src/app/services/generation_statistics.py`:
- **Line 119**: `_resolve_markdown_path()` function
- **Line 126**: `_safe_model_dir()` function

### Why This Matters
The regex pattern `[^\w\-_]` means "replace anything NOT in the set: word chars, hyphens, underscores"
- **Problem**: Dots (`.`) are not in this set, so `3.5` became `3_5`
- **Solution**: Added dot to allowed chars: `[^\w\-_.]` so `3.5` stays as `3.5`

## Prevention
Going forward, the system will:
1. ✓ **Preserve dots in model slugs** during filesystem operations
2. ✓ **Use OpenRouter canonical format** (e.g., `anthropic_claude-3.5-sonnet`)
3. ✓ **Generate consistent folder names** matching the database slugs
4. ✓ **Prevent duplicate entries** from inconsistent naming

### Validation
Test cases confirm the fix:
- ✓ `anthropic_claude-3.5-sonnet` → stays as `anthropic_claude-3.5-sonnet`
- ✓ `openai_gpt-4.0-turbo` → stays as `openai_gpt-4.0-turbo`  
- ✓ `anthropic/claude-3.5-sonnet` → becomes `anthropic_claude-3.5-sonnet` (slash replaced)
- ✓ Special chars and spaces still get sanitized properly
