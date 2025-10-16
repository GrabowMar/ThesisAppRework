# Route Refactoring Analysis

## Files Using DEPRECATED `sample_generation_service.py` (3700 lines)

### API Routes
1. **`src/app/routes/api/sample_generation.py`** - ENTIRE FILE DEPRECATED
   - Uses old service extensively
   - Endpoints: `/api/sample-gen/*`
   - Frontend reference: `wizard.html` line 2 uses `/api/sample-gen/generate/batch`

2. **`src/app/routes/api/templates_v2.py`** - PARTIALLY DEPRECATED
   - Imports `get_sample_generation_service` and `Template`
   - Lines 208, 295 use the service
   - Likely needed for template management

### Jinja Routes
3. **`src/app/routes/jinja/sample_generator.py`** - NEEDS EVALUATION
   - Main UI for sample generator at `/sample-generator`
   - Uses old service (line 19, 25)
   - Frontend still uses this page

## NEW System (Simple Generation)

### Correct Routes to Use
- **`src/app/routes/api/simple_generation.py`** ✅
  - Clean implementation
  - Endpoints: `/api/gen/*`
  - Uses `SimpleGenerationService` (~400 lines)

- **`src/app/routes/api/generation_v2.py`** ✅
  - Scaffolding-first approach
  - Endpoint: `/api/gen/v2/generate`

## Frontend References to Fix

### Templates Using OLD system
1. `src/templates/pages/sample_generator/partials/wizard.html:2`
   - **OLD**: `action="/api/sample-gen/generate/batch"`
   - **NEW**: Should use `/api/gen/generate-full` or `/api/gen/v2/generate`

## Refactoring Strategy

### Phase 1: Fix Frontend ✅
- Update wizard.html to use new API endpoints
- Test generation workflow

### Phase 2: Remove Deprecated Routes ✅
- Remove `src/app/routes/api/sample_generation.py`
- Update `src/app/routes/api/__init__.py` to remove import
- Remove old service file `src/app/services/sample_generation_service.py`

### Phase 3: Update Jinja Route ✅
- Refactor `src/app/routes/jinja/sample_generator.py` to use SimpleGenerationService
- Or create new UI for new system

### Phase 4: Clean up api.py ✅
- Remove backward-compat shims
- Consolidate duplicate endpoints
- Add proper error handling

## Bloat in `api.py` (650+ lines)

### Backward-Compat Shims (Lines ~45-80)
```python
@api_bp.route('/overview')
def dashboard_overview_compat():
    # Delegates to dashboard module
    
@api_bp.route('/stats')
def dashboard_stats_compat():
    # Delegates to dashboard module
```
**Action**: Check if any frontend code calls these directly, then remove

### Duplicate Endpoints
- `/models` (line 94) - delegates to models.py
- `/applications` (line 107) - basic implementation, should be in applications.py
- `/models/paginated` (line 120) - MASSIVE 450-line function with tons of filters

**Action**: 
- Move `/models/paginated` to `models.py`
- Remove wrapper endpoints
- Update any direct references

### Other Issues
- Inconsistent error handling
- Mixed concerns (dashboard, models, applications in one file)
- No proper docstrings for many functions

## Files NOT Connected to Frontend

### Check These for Removal
1. `results_v2.py` - Check if used
2. `templates_v2.py` - Partially used, may need refactor
3. `app_scaffolding.py` - Check usage

## Summary

**Total Lines to Remove**: ~4000+ lines
- `sample_generation_service.py`: 3700 lines
- `sample_generation.py`: 571 lines
- Various shims and duplicates: ~200 lines

**Files to Delete**: 2
**Files to Refactor**: 5+
**Frontend Files to Update**: 1
