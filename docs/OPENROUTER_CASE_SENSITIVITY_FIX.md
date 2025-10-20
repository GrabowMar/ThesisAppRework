# OpenRouter Case Sensitivity Fix

## Problem Description

**Root Cause**: OpenRouter API has a case-sensitivity inconsistency:
- Their `/api/v1/models` list endpoint returns **lowercase model IDs**: `agentica-org/deepcoder-14b-preview`
- But the actual providers (like Chutes/HuggingFace) expect **case-sensitive** names: `agentica-org/DeepCoder-14B-Preview`

**Error Message**:
```json
{
  "error": {
    "message": "Provider returned error",
    "code": 404,
    "metadata": {
      "raw": '{"detail":"model not found: agentica-org/DeepCoder-14B-Preview"}',
      "provider_name": "Chutes"
    }
  }
}
```

## Evidence

### OpenRouter Models API Response
```json
{
  "id": "agentica-org/deepcoder-14b-preview:free",          // ← Lowercase
  "canonical_slug": "agentica-org/deepcoder-14b-preview",  // ← Lowercase
  "hugging_face_id": "agentica-org/DeepCoder-14B-Preview", // ← CORRECT CASE
  "name": "Agentica: Deepcoder 14B Preview (free)"
}
```

### Test Results
- ✅ **Working**: `x-ai/grok-code-fast-1` (all lowercase, no HF provider)
- ❌ **Failing**: `agentica-org/deepcoder-14b-preview` (lowercase, HF provider expects case-sensitive)

## Solution Options

### Option A: Store HuggingFace ID (Recommended)
**Pros**: Most reliable, matches provider expectations
**Cons**: Requires database schema change

```python
# Add to ModelCapability
hugging_face_id = db.Column(db.String(200), index=True)

# Use in OpenRouterChatService
model_to_use = db_model.hugging_face_id or db_model.model_id
```

### Option B: Runtime Model Lookup
**Pros**: Always current, no schema change
**Cons**: Extra API call overhead

```python
# Cache OpenRouter models list
# Look up correct case before each chat completion
```

### Option C: Update Existing model_id Fields
**Pros**: Simple, no schema change
**Cons**: Need to re-scrape all models, may break existing queries

## Immediate Fix (Implemented)

1. **Document the issue** ✅
2. **Add hugging_face_id field** to ModelCapability schema
3. **Update model scraper** to capture `hugging_face_id` from OpenRouter
4. **Update OpenRouterChatService** to prefer `hugging_face_id` over `model_id`
5. **Backfill existing models** with correct case from OpenRouter API

## Files to Update

### 1. Database Schema
```python
# src/app/models/core.py
class ModelCapability(db.Model):
    # ... existing fields ...
    hugging_face_id = db.Column(db.String(200), index=True)  # NEW
```

### 2. Model Scraper
```python
# src/app/routes/shared_utils.py - _upsert_openrouter_models()
existing.hugging_face_id = model_data.get('hugging_face_id')  # NEW
```

### 3. Chat Service
```python
# src/app/services/openrouter_chat_service.py
# Use hugging_face_id when available
```

### 4. Generation Service
```python
# src/app/services/generation.py
# Pass hugging_face_id to chat service
model_to_use = model.hugging_face_id or model.model_id
```

## Migration Steps

1. Run database migration to add `hugging_face_id` column
2. Run backfill script to populate from OpenRouter API
3. Update services to use `hugging_face_id` when available
4. Test with failing models (agentica, etc.)

## Testing Checklist

- [ ] Database migration successful
- [ ] All models have `hugging_face_id` populated
- [ ] agentica-org/deepcoder-14b-preview generation works
- [ ] Existing working models still work (grok, claude, gpt-4)
- [ ] UI shows correct model IDs
- [ ] Comparison page works with both ID formats

## Related Files

- `src/app/models/core.py` - ModelCapability schema
- `src/app/routes/shared_utils.py` - Model scraping
- `src/app/services/openrouter_chat_service.py` - API calls
- `src/app/services/generation.py` - Generation orchestration
- `scripts/test_agentica_generation.py` - Reproduction test
- `scripts/check_openrouter_model.py` - Model verification

## References

- OpenRouter Models API: https://openrouter.ai/api/v1/models
- Error in screenshot: 3 failed generations with agentica-org_deepcoder-14b-preview
- Working test: x-ai/grok-code-fast-1 end-to-end success

---

**Status**: Problem identified, solution designed
**Next Step**: Implement database migration and backfill script
**Priority**: HIGH - blocks generation for HuggingFace-backed models
