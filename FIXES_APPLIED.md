# Code Generation Fixes Applied

**Date:** November 11, 2025

## Issues Found and Fixed

### Issue 1: Random App Number Generation (Duplicate Apps)
**Problem:** UI was generating random app numbers instead of sequential ones, causing multiple apps to be created when user requested only one.

**Root Cause:**
- `model_details.html`: `Math.floor(Math.random() * 1000) + 1`
- `sample_generator_wizard.js`: `Date.now() % 10000`

**Fix Applied:**
- Added new API endpoint: `GET /api/models/<model_slug>/next-app-number`
- Returns sequential app numbers based on existing apps in database
- Updated UI to call this endpoint before generating

**Files Modified:**
1. `src/templates/pages/models/model_details.html` - Changed `generateApplication()` to async and fetch next app number
2. `src/static/js/sample_generator_wizard.js` - Replaced random number with API call
3. `src/app/routes/api/models.py` - Added `api_model_next_app_number()` endpoint

---

### Issue 2: Invalid Model ID for OpenRouter API
**Problem:** DeepSeek model generation failed with "deepseek-ai/DeepSeek-V3.1 is not a valid model ID"

**Root Cause:**
Database had incorrect `hugging_face_id` with wrong casing:
```
Model ID: deepseek/deepseek-chat-v3.1  ✓ (correct)
HF ID: deepseek-ai/DeepSeek-V3.1       ✗ (invalid - wrong casing)
Base ID: deepseek/deepseek-chat-v3.1   ✓ (correct)
```

Code was preferring `hugging_face_id` which had invalid casing.

**Fix Applied:**
Changed model ID selection priority:
1. `hugging_face_id` (if valid)
2. **`base_model_id` (NEW - normalized, no variant suffix)** ← Now uses this
3. `model_id` (fallback)

**File Modified:**
- `src/app/services/generation.py` - Updated `CodeGenerator.generate()` method

---

### Issue 3: Poor Error Visibility
**Problem:** When API calls failed, errors weren't logged with enough detail for debugging

**Fix Applied:**
- Added detailed error logging showing attempted model ID
- Error messages now include which model ID was tried
- Full error response logged for debugging

**File Modified:**
- `src/app/services/generation.py` - Enhanced error handling in `CodeGenerator.generate()`

---

## Expected Results

### Before Fixes:
❌ Each click created new app with random number (app5456, app6100, etc.)
❌ API calls failed with "not a valid model ID" error
❌ Scaffold created but no actual AI-generated code
❌ Hard to debug what went wrong

### After Fixes:
✅ Sequential app numbering (app1, app2, app3, etc.)
✅ Correct model ID used for API calls (base_model_id)
✅ Better error messages showing which model ID was attempted
✅ Only one app created per user request

---

## Testing Recommendations

1. **Test Sequential Numbering:**
   - Go to a model detail page
   - Click "Generate Application"
   - Verify it creates app1, then app2, then app3 (not random numbers)

2. **Test DeepSeek Model:**
   - Try generating with `deepseek_deepseek-chat-v3.1`
   - Should now use `deepseek/deepseek-chat-v3.1` instead of `deepseek-ai/DeepSeek-V3.1`
   - Check logs for confirmation of model ID used

3. **Verify Error Logging:**
   - If generation fails, check logs for detailed error message
   - Should show: "API error <code>: <message> (tried model ID: <model_id>)"

---

## Database Status Check

Run this to verify model IDs:
```bash
cd src
python -c "from app.factory import create_app; from app.models import ModelCapability; app = create_app(); ctx = app.app_context(); ctx.push(); m = ModelCapability.query.filter_by(canonical_slug='deepseek_deepseek-chat-v3.1').first(); print(f'Will now use: {m.base_model_id or m.model_id}')"
```

Expected output: `Will now use: deepseek/deepseek-chat-v3.1`

---

## Next Steps

1. **Re-run Failed Generations:** 
   - The apps in `generated/apps/` with only scaffold code can be regenerated
   - They should now work with the correct model ID

2. **Monitor Logs:**
   - Watch for any new "not a valid model ID" errors
   - If they occur, the detailed logging will show which model has issues

3. **Consider Data Cleanup:**
   - You may want to delete the duplicate apps (app5456/app6100, app5901/app6501, etc.)
   - Or regenerate them to get actual AI code instead of scaffold-only

---

## Files Changed Summary

- `src/templates/pages/models/model_details.html` - Sequential numbering
- `src/static/js/sample_generator_wizard.js` - Sequential numbering  
- `src/app/routes/api/models.py` - New endpoint for next app number
- `src/app/services/generation.py` - Model ID priority + error logging
