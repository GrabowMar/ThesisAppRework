# Making Weak Models Generate Better Code - Quick Summary

## Problem
**meta-llama_llama-4-scout-17b-16e-instruct** (and similar small models) generated subpar, barely working apps:
- Only ~200 lines vs. target 700+ lines
- Fragmented code (7 different App.jsx files, 6 different main.py files)
- Missing components, incomplete functions
- Non-functional outputs

## Root Cause
Small models (< 30B parameters) can't handle complex, architectural templates designed for flagship models like Claude/GPT-4.

## Solution: Multi-Tier Template System

### Automatic Model Classification
```python
get_model_capability_tier(model_slug) -> 'lite' | 'standard'
```

**Lite Tier** (< 30B parameters):
- `llama-4-scout-17b`, `mistral-7b`, `gemma-7b`, etc.
- Uses simplified templates from `misc/app_templates_lite/`

**Standard Tier** (30B+ parameters):
- `claude-3.5-sonnet`, `gpt-4`, `llama-3-70b`, etc.
- Uses production templates from `misc/app_templates/`

### Template Differences

| Aspect | Lite Templates | Standard Templates |
|--------|---------------|-------------------|
| **Lines** | 150-250 (backend), 200-300 (frontend) | 300-500+ (backend), 400-600+ (frontend) |
| **Features** | 3 fixed features | 4+ expandable features |
| **Style** | Step-by-step numbered instructions | Architectural guidance |
| **Examples** | Exact code with "YOUR CODE HERE" | Structure patterns |
| **Complexity** | Simple CRUD | Production-grade with transactions |

### Example: Lite Template

```markdown
**STEP 3** (Lines 51-80): Implement the `/api/products` endpoint (GET)
- Query all products from database
- Return JSON list of products with id, name, price, stock

# Then show exact code skeleton:
@app.route('/api/products', methods=['GET'])
def get_products():
    # YOUR CODE HERE
    # 1. Query all products: Product.query.all()
    # 2. Convert to list of dicts
    # 3. Return JSON response
    pass
```

## Files Changed

1. **Created**:
   - `misc/app_templates_lite/` directory
   - `misc/app_templates_lite/README.md` (system overview)
   - `misc/app_templates_lite/app_1_backend_login.md` (lite auth template)
   - `misc/app_templates_lite/app_5_backend_cart.md` (lite e-commerce template)
   - `misc/app_templates_lite/app_5_frontend_cart.md` (lite React template)
   - `docs/MULTI_TIER_TEMPLATE_SYSTEM.md` (full documentation)

2. **Modified**:
   - `src/app/paths.py` - Added `APP_TEMPLATES_LITE_DIR` constant
   - `src/app/services/sample_generation_service.py`:
     - Added `get_model_capability_tier()` function (lines ~80-120)
     - Modified `SampleGenerationService.__init__()` to load lite templates
     - Modified `generate_async()` to filter templates by model tier

## How It Works

```
┌─────────────────────┐
│ Generation Request  │
│   app_num=5, model  │
└──────────┬──────────┘
           │
           ▼
┌──────────────────────────────┐
│ get_model_capability_tier()  │
│ "llama-4-scout" → 'lite'     │
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────────┐
│ Filter templates:            │
│ Prefer app_templates_lite/   │
│ for 'lite' tier models       │
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────────┐
│ Use simplified template      │
│ → 150-250 lines, 3 features  │
└──────────────────────────────┘
```

## Testing

```bash
# Test with weak model (auto-uses lite template)
curl -X POST http://localhost:5000/api/sample-gen/generate \
  -H "Content-Type: application/json" \
  -d '{
    "template_id": "5",
    "model": "meta-llama/llama-4-scout-17b-16e-instruct"
  }'

# Check logs:
# "Model capability tier for '...scout...': lite"
# "Using lite template candidates"
```

## Expected Results

### Before (Standard Template)
- ❌ 7 conflicting App.jsx files
- ❌ ~200 total lines (target was 700+)
- ❌ Missing components
- ❌ Barely functional

### After (Lite Template)
- ✅ Clean file structure (no duplicates)
- ✅ 150-250 lines (realistic for small model)
- ✅ All 3 core features working
- ✅ Functional, complete app

## Lite Templates Available

| App | Backend | Frontend |
|-----|---------|----------|
| 1 - Login | ✅ | 🔄 TODO |
| 5 - Shopping Cart | ✅ | ✅ |
| 10 - Todo List | 🔄 TODO | 🔄 TODO |

**Note**: Only 3 templates created as proof-of-concept. Add more as needed.

## Next Steps

1. **Test with weak models** - Verify lite templates produce better results
2. **Add more lite templates** - Cover apps 1-30
3. **Monitor metrics**:
   - Line count by model tier
   - Success rate by tier
   - Functional completeness
4. **Iterate on lite templates** - Refine based on actual model outputs
5. **Consider "advanced" tier** - For 70B+ models with even higher expectations

## Rollback

If this causes issues:
```bash
# 1. Remove lite template loading (lines ~2603-2608 in sample_generation_service.py)
# 2. Comment out tier classification in generate_async()
# 3. Delete misc/app_templates_lite/ if needed
```

---

**Bottom Line**: Small models now have realistic, achievable templates that play to their strengths instead of expecting them to match GPT-4/Claude capabilities.
