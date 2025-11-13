# Report Modal "No models available" - Fix Summary

## Problem
The report generation modal showed "No models available" even when generated apps existed in the filesystem under `generated/apps/`.

## Root Cause
The modal's query used an INNER JOIN between `ModelCapability` and `GeneratedApplication` tables:
```python
models_with_apps = db.session.query(ModelCapability).join(
    GeneratedApplication,
    ModelCapability.canonical_slug == GeneratedApplication.model_slug
).distinct().all()
```

This returned empty results when:
1. The `GeneratedApplication` table was empty (even if apps existed on filesystem)
2. Model slugs didn't match between tables due to normalization issues

## Solution Implemented

### 1. Enhanced `scripts/sync_generated_apps.py`
- **Added slug normalization** during filesystem scan using `app.utils.slug_utils.normalize_model_slug`
- **Added variant matching** to handle different slug formats using `generate_slug_variants`
- **Improved matching logic** to find models in database even with slug format differences
- **Uses canonical_slug** from matched model for database records to ensure consistency

### 2. Kept Original Query Design
- **Decision**: Keep showing only models with apps (not all models)
- **Rationale**: This is intentional design - reports should only be generated for models that have generated applications
- **Benefit**: Focuses users on actionable models

### 3. Added Verification Script
- Created `verify_report_models.py` to diagnose and verify the fix
- Shows exact query results that modal will use
- Helps troubleshoot slug mismatch issues

## Results

After running the sync script:
```bash
python scripts/sync_generated_apps.py
```

**Database populated with 6 apps across 3 models:**
- amazon / nova-pro-v1: 1 app
- anthropic / claude-haiku-4.5: 4 apps  
- arcee-ai / coder-large: 1 app

**Verification confirmed:**
✅ Models with apps query now returns 3 models (was 0)
✅ Report modal will display all 3 models with their apps
✅ Slug normalization ensures consistency between filesystem and database
✅ Modal JavaScript receives correct data: 3 models in modelsCache, 3 slugs in appsCache
✅ "No models available" issue is RESOLVED

**Test Results:**
```bash
python verify_report_models.py      # ✅ Database query returns 3 models
python inspect_modal_data.py        # ✅ Modal HTML contains correct model data
```

## Maintenance

**When new apps are generated:**
Run the sync script to update the database:
```bash
python scripts/sync_generated_apps.py
```

**To verify modal data:**
```bash
python verify_report_models.py
```

## Technical Details

**Slug Normalization:**
- Filesystem format: `provider_model-name` (e.g., `amazon_nova-pro-v1`)
- Normalizes slashes to underscores (e.g., `anthropic/claude` → `anthropic_claude`)
- Preserves hyphens in model names (e.g., `nova-pro-v1` stays as-is)
- Handles dots for version numbers (e.g., `4.5` → `4.5`)

**Database Schema:**
- `ModelCapability.canonical_slug` must match `GeneratedApplication.model_slug`
- Both use normalized underscore format after this fix
- INNER JOIN ensures only models with apps appear in report modal
