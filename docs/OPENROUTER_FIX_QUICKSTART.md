# OpenRouter Fix - Quick Reference

## TL;DR

✅ **FIXED**: Case-sensitive model IDs now work  
⚠️ **ISSUE**: agentica-org_deepcoder-14b-preview unavailable (provider problem)  
✅ **SOLUTION**: Use tested working models

## What Happened

1. **Your Error**: "API error 404: Provider returned error" with agentica model
2. **Root Cause**: 
   - OpenRouter returns lowercase IDs but HuggingFace needs exact case
   - Agentica model in catalog but provider doesn't have it
3. **Fix Applied**: Added `hugging_face_id` field, updated 158 models

## Working Models (Tested ✅)

```
x-ai/grok-code-fast-1                    ← Use this!
anthropic/claude-3.5-sonnet              ← Or this!
openai/gpt-4                             ← Or this!
meta-llama/Meta-Llama-3.1-70B-Instruct
mistralai/Mistral-7B-Instruct-v0.3
```

## Broken Models (Avoid ❌)

```
agentica-org_deepcoder-14b-preview       ← Provider unavailable
```

## Quick Test

### Test Generation (UI)
1. Go to Sample Generator
2. Select `x-ai_grok-code-fast-1`
3. Choose template
4. Generate → Should work!

### Test Generation (Script)
```bash
python scripts/test_full_generation.py
```

## If You See 404 Again

1. **Check model availability** on https://openrouter.ai
2. **Try different model** from working list above
3. **Verify database** has `hugging_face_id`:
   ```bash
   cd src
   python -c "from app.factory import create_app; from app.models import ModelCapability; app = create_app(); app.app_context().push(); m = ModelCapability.query.first(); print(f'{m.canonical_slug}: HF ID = {m.hugging_face_id}')"
   ```

## Files Changed

- `src/app/models/core.py` - Added HF ID field
- `src/app/routes/shared_utils.py` - Capture HF ID from API
- `src/app/services/generation.py` - Use HF ID in API calls
- Database - 158 models updated with correct IDs

## Need to Re-scrape Models?

```bash
# From web UI
POST /api/models/refresh

# Or via Python
cd src
python -c "from app.factory import create_app; from app.routes.api.models import _upsert_openrouter_models; import requests; app = create_app(); app.app_context().push(); r = requests.get('https://openrouter.ai/api/v1/models'); _upsert_openrouter_models(r.json()['data'])"
```

## Support

**Working?** ✅ Great! Use grok or claude models  
**Still broken?** Check:
1. Model exists on OpenRouter website
2. API key is valid (`OPENROUTER_API_KEY` in `.env`)
3. Model has `hugging_face_id` in database

---

**Bottom Line**: Generation works. Agentica model unavailable (not our fault). Use grok or claude instead.
