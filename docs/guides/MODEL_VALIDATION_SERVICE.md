# Model Validation & Migration - Permanent Service Layer

## Overview

Model validation and migration logic has been moved from one-time scripts to permanent service layer components that run automatically on app startup and can be invoked via CLI or programmatically.

## Architecture

### Service Components

1. **`ModelValidator`** (`src/app/services/model_validator.py`)
   - Validates model IDs against live OpenRouter catalog
   - Case-insensitive matching
   - Provider namespace normalization
   - Fuzzy matching for suggestions
   - **Used by:** Generation service, migration service

2. **`ModelMigrationService`** (`src/app/services/model_migration.py`)
   - Database migration operations
   - Bulk validation and fixing
   - Provider namespace corrections
   - **Used by:** Startup initialization, CLI commands

3. **CLI Commands** (`src/app/cli/models.py`)
   - Manual validation and fixing
   - Dry-run support
   - Human-readable output

### Integration Points

```
App Startup (factory.py)
    ↓
ModelMigrationService.validate_and_fix_all_models()
    ↓
ModelValidator (validates against OpenRouter catalog)
    ↓
Database updated with corrected model IDs
```

```
Generation Request
    ↓
GenerationService._generate_with_chat()
    ↓
ModelValidator.is_valid_model_id() + suggest_correction()
    ↓
Runtime validation & auto-correction
    ↓
OpenRouter API call with correct model ID
```

## Provider Namespace Normalization

### Automatic Mapping

The `ModelValidator` maintains a permanent mapping of organization names to OpenRouter provider names:

```python
PROVIDER_NAMESPACE_MAP = {
    'deepseek-ai': 'deepseek',      # DeepSeek-AI org → deepseek provider
    'MiniMaxAI': 'minimax',          # MiniMaxAI org → minimax provider
    'LiquidAI': 'liquid',            # LiquidAI org → liquid provider
    'Alibaba-NLP': 'alibaba',        # Alibaba-NLP org → alibaba provider
    'ai21labs': 'ai21',              # AI21 Labs org → ai21 provider
    'ByteDance-Seed': 'bytedance',   # ByteDance org → bytedance provider
    'CohereForAI': 'cohere',         # Cohere org → cohere provider
    'meituan-longcat': 'meituan',    # Meituan org → meituan provider
    'zai-org': 'zhipu',              # ZAI org → zhipu provider (GLM models)
    'z-ai': 'zhipu',
}
```

### How It Works

1. **On App Startup:**
   - `ModelMigrationService` runs `validate_and_fix_all_models()`
   - Scans all database models
   - Normalizes provider namespaces automatically
   - Commits fixes to database

2. **At Runtime (Generation):**
   - `ModelValidator.normalize_provider_namespace()` called
   - Provider prefix checked against map
   - Normalized ID validated against OpenRouter
   - Suggestion returned if ID still invalid

3. **Example Flow:**
   ```
   Database: deepseek-ai/DeepSeek-R1
       ↓ normalize_provider_namespace()
   Normalized: deepseek/deepseek-r1
       ↓ is_valid_model_id()
   OpenRouter Catalog: ✅ FOUND
   ```

## Usage

### Automatic (Recommended)

Model validation runs automatically on every app startup:

```bash
# Just start the app
python src/main.py

# Logs will show:
# [INFO] Running model ID validation and fixes...
# [INFO] ✅ Fixed 3 model IDs on startup
# [INFO] ✅ 292/296 models validated successfully
```

### Manual CLI Commands

```bash
# Navigate to src directory
cd src

# Validate all models (read-only)
python -m app.cli.models validate

# Preview fixes (dry-run)
python -m app.cli.models fix --dry-run

# Apply fixes
python -m app.cli.models fix

# Normalize provider namespaces only
python -m app.cli.models normalize
python -m app.cli.models normalize --dry-run
```

### Programmatic Usage

```python
from app import create_app
from app.services.model_migration import get_migration_service
from app.services.model_validator import get_validator

app = create_app()

with app.app_context():
    # Validate all models
    migration = get_migration_service()
    result = migration.validate_and_fix_all_models(dry_run=True)
    
    print(f"Valid: {result['summary']['valid']}")
    print(f"Invalid: {result['summary']['invalid']}")
    
    # Get suggestions for invalid models
    for invalid in result['unfixable']:
        print(f"{invalid['slug']}: {invalid['reason']}")
    
    # Check specific model
    validator = get_validator()
    is_valid = validator.is_valid_model_id('deepseek-ai/DeepSeek-R1')
    # Returns False, but suggest_correction() will return 'deepseek/deepseek-r1'
```

## Runtime Behavior

### Generation Service Integration

When generating an app, the generation service:

1. Retrieves model from database
2. Builds OpenRouter model ID: `hugging_face_id or base_model_id or model_id`
3. Validates with `ModelValidator.is_valid_model_id()`
4. If invalid, calls `ModelValidator.suggest_correction()`
5. Auto-applies correction if suggestion found
6. Logs warning and uses corrected ID
7. Continues with generation using valid ID

**No manual intervention needed** - corrections happen automatically.

### Validation Strategies

The validator tries multiple strategies in order:

1. **Exact match** (case-insensitive)
   ```python
   'anthropic/claude-haiku-4.5' → ✅ VALID
   ```

2. **Provider namespace normalization**
   ```python
   'deepseek-ai/DeepSeek-R1' 
       → normalize to 'deepseek/deepseek-r1'
       → ✅ VALID
   ```

3. **Fuzzy matching** (≥60% similarity)
   ```python
   'ai21/jamba-mini' 
       → closest match: 'ai21/jamba-mini-1.7' (88% similar)
       → ✅ CORRECTED
   ```

4. **No match found**
   ```python
   'unknown/fake-model' → ❌ UNFIXABLE
   ```

## Database Impact

### Fields Modified

The migration service updates the following fields:

- `hugging_face_id` (preferred, if present)
- `base_model_id` (fallback, if `hugging_face_id` empty)
- `model_id` (last resort)

### Transaction Safety

All fixes are committed in a single transaction:
- Batch processing of all models
- Single `db.commit()` at end
- Rollback on any error
- No partial updates

### Example Fix

**Before:**
```sql
SELECT canonical_slug, hugging_face_id FROM model_capabilities 
WHERE canonical_slug = 'deepseek_deepseek-r1';

-- Result:
-- deepseek_deepseek-r1 | deepseek-ai/DeepSeek-R1
```

**After (automatic fix on startup):**
```sql
SELECT canonical_slug, hugging_face_id FROM model_capabilities 
WHERE canonical_slug = 'deepseek_deepseek-r1';

-- Result:
-- deepseek_deepseek-r1 | deepseek/deepseek-r1
```

## Monitoring & Logs

### Startup Logs

```
[INFO] Running model ID validation and fixes...
[INFO] Fixed deepseek_deepseek-r1: deepseek-ai/DeepSeek-R1 → deepseek/deepseek-r1 (Provider namespace normalized)
[INFO] Fixed minimax_minimax-01: MiniMaxAI/MiniMax-Text-01 → minimax/minimax-01 (Provider namespace normalized)
[INFO] ✅ Fixed 22 model IDs on startup
[INFO] ✅ 292/296 models validated successfully
[WARNING] ⚠️  4 models could not be auto-fixed
```

### Generation Logs

```
[WARNING] Invalid model ID detected: deepseek-ai/DeepSeek-V3
[WARNING] Auto-correcting: deepseek-ai/DeepSeek-V3 → deepseek/deepseek-chat
[INFO] Reason: Provider namespace normalized
[INFO] Using OpenRouter model: deepseek/deepseek-chat
```

## Migration from Scripts

### Old Approach (One-Time Scripts)

```bash
# Had to manually run scripts after database changes
python scripts/validate_and_fix_model_ids.py --fix
python scripts/fix_provider_namespaces.py --fix
python scripts/check_remaining_models.py
```

**Problems:**
- Manual intervention required
- Easy to forget after database updates
- Scripts drift from actual service behavior
- No automatic recovery

### New Approach (Permanent Services)

```bash
# Just start the app - fixes applied automatically
python src/main.py
```

**Benefits:**
- ✅ Automatic on every startup
- ✅ Self-healing database
- ✅ Runtime validation catches issues
- ✅ CLI available for manual operations
- ✅ Consistent with generation service behavior

## Testing

### Unit Tests

```python
def test_provider_namespace_normalization():
    from app.services.model_validator import get_validator
    
    validator = get_validator()
    
    # Test normalization
    assert validator.normalize_provider_namespace('deepseek-ai/DeepSeek-R1') == 'deepseek/deepseek-r1'
    assert validator.normalize_provider_namespace('MiniMaxAI/MiniMax-01') == 'minimax/minimax-01'
    
    # Test validation with normalization
    assert validator.is_valid_model_id('deepseek-ai/DeepSeek-R1')  # Auto-normalized
```

### Integration Tests

```python
def test_startup_model_migration(app):
    with app.app_context():
        # Simulate invalid model in database
        model = ModelCapability.query.first()
        model.hugging_face_id = 'deepseek-ai/DeepSeek-V3'
        db.session.commit()
        
        # Run migration
        from app.services.model_migration import get_migration_service
        migration = get_migration_service()
        result = migration.validate_and_fix_all_models(dry_run=False)
        
        # Check fix was applied
        model.refresh()
        assert model.hugging_face_id == 'deepseek/deepseek-chat'
```

## Future Enhancements

1. **Periodic Catalog Refresh**
   - Cache OpenRouter catalog for 24h
   - Background refresh to catch new models
   - Notification when new models available

2. **Provider Mapping Updates**
   - Monitor OpenRouter for provider changes
   - Automatic mapping updates from external config
   - Support for provider aliases

3. **Validation Metrics**
   - Track validation success rate
   - Alert on high failure rate
   - Dashboard showing model health

4. **Batch Operations**
   - Bulk model import with validation
   - CSV export/import with auto-correction
   - API endpoint for validation as a service

## Troubleshooting

### Issue: "Cannot validate without catalog"

**Cause:** `OPENROUTER_API_KEY` not set or invalid

**Solution:**
```bash
# Check .env file
grep OPENROUTER_API_KEY .env

# If missing, add it:
echo "OPENROUTER_API_KEY=sk-or-v1-..." >> .env
```

### Issue: Models still invalid after fix

**Cause:** Model genuinely doesn't exist in OpenRouter

**Solution:**
```bash
# Check which models are unfixable
cd src
python -m app.cli.models validate

# Review unfixable models and either:
# 1. Remove from database (if deprecated)
# 2. Research correct OpenRouter model ID
# 3. Add to PROVIDER_NAMESPACE_MAP if new provider
```

### Issue: Startup slowdown

**Cause:** Validation runs on every startup, fetches catalog from API

**Solution:**
```python
# Disable startup validation (not recommended)
# In factory.py, comment out:
# migration_svc.validate_and_fix_all_models(dry_run=False, auto_fix=True)

# Better: Implement catalog caching (future enhancement)
```

## Summary

The permanent service layer provides:
- **Automatic** model validation on startup
- **Runtime** auto-correction during generation
- **Persistent** provider namespace normalization
- **Manual** CLI for debugging and inspection
- **Self-healing** database with zero manual intervention

**Scripts are now deprecated** - all functionality moved to services.
