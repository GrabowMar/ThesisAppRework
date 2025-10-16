# Template Enhancement: Procedural Guardrails

## What Was Done

Instead of creating a multi-tier template system, we enhanced the **existing templates** with stronger guardrails and procedural structure to guide models step-by-step.

---

## Problem

Weak models like `llama-4-scout-17b` generated:
- Incomplete code (~200 lines vs 700+ target)
- Multiple conflicting files (7 App.jsx, 6 main.py versions)
- Missing implementations (pass statements, TODO comments)
- Non-functional outputs

## Solution: Procedural Guardrails

Added explicit step-by-step structure to all 30 backend templates:

### 1. **Procedural Workflow Section**

```markdown
### 📋 PROCEDURAL WORKFLOW (Follow This Sequence)

⚠️ IMPORTANT: Generate code in this exact order. 
Complete each step before moving to the next.

STEP 1: Imports & Configuration (First 30-40 lines)
```python
# Import all dependencies at the top
from flask import Flask, jsonify, request
# ... exact pattern shown
```
✓ Checkpoint: Verify all imports at top, app initialized

STEP 2: Database Models (Next 40-60 lines)
```python
db = SQLAlchemy(app)
class Product(db.Model):
    # ... exact pattern
```
✓ Checkpoint: All models defined with fields

STEP 3: Helper Functions (Next 30-50 lines)
... and so on
```

### 2. **Validation Checklist**

```markdown
### 🎯 VALIDATION CHECKLIST (Complete Before Submitting)

Code Structure:
- [ ] All imports at top (stdlib → third-party → local)
- [ ] Flask app initialized with all config
- [ ] Database models defined with all fields
- [ ] All endpoints implemented (not just stubs)

Error Handling:
- [ ] Try/except blocks on all database operations
- [ ] Proper HTTP status codes (200, 400, 404, 500)
- [ ] Validation for all input data
- [ ] Logging for errors and important events
```

### 3. **Explicit Constraints**

```markdown
### 🚫 CONSTRAINTS & BOUNDARIES

DO:
✅ Write complete, runnable code (no placeholders)
✅ Include proper error handling on every endpoint
✅ Use the scaffolding code templates as a base
✅ Add logging for debugging

DON'T:
❌ Use `pass` or `TODO` or `...` in final code
❌ Skip error handling ("happy path only")
❌ Create multiple versions of the same file

CODE SIZE EXPECTATIONS:
- Minimum: 300 lines (anything less is likely incomplete)
- Target: 400-500 lines (good comprehensive implementation)
- Maximum: 700 lines (don't over-engineer)
```

---

## Changes Made

### Files Modified
- **All 30 backend templates** in `misc/app_templates/*_backend_*.md`
- Each template enhanced with procedural workflow + validation + constraints

### Files Created
- `scripts/add_template_guardrails.py` - Enhancement script
- `misc/app_templates/*_backend_*.md.bak` - Backup of original templates
- `docs/TEMPLATE_GUARDRAILS.md` - This documentation

### Files Removed (Multi-Tier System)
- `misc/app_templates_lite/` directory (removed)
- `docs/MULTI_TIER_*.md` (removed)
- `docs/WEAK_MODEL_SUPPORT_SUMMARY.md` (removed)

### Code Reverted
- `src/app/paths.py` - Removed `APP_TEMPLATES_LITE_DIR`
- `src/app/services/sample_generation_service.py` - Removed model tier classification and routing logic

---

## How It Works

### Before Enhancement

```markdown
### 4. Implementation Requirements

Build a comprehensive backend system that implements at minimum 
the following core functionalities...

1. Product Catalog Management: Implement endpoints...
2. Session-Based Shopping Cart: Implement endpoints...
```

**Issue**: Too abstract, models don't know where to start or what order to follow.

### After Enhancement

```markdown
### 4. Implementation Requirements

[... existing requirements ...]

---

### 📋 PROCEDURAL WORKFLOW (Follow This Sequence)

⚠️ IMPORTANT: Generate code in this exact order.

STEP 1: Imports & Configuration (First 30-40 lines)
```python
from flask import Flask, jsonify, request, session
from flask_sqlalchemy import SQLAlchemy
# ... exact code pattern
```
✓ Checkpoint: Verify imports at top

STEP 2: Database Models (Next 40-60 lines)
```python
db = SQLAlchemy(app)
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
```
✓ Checkpoint: Models defined

[... continues through 5 steps ...]

### 🎯 VALIDATION CHECKLIST
- [ ] All imports at top
- [ ] All endpoints implemented (not stubs)
- [ ] Error handling on database ops
[... 12 more checkpoints ...]

### 🚫 CONSTRAINTS & BOUNDARIES
DON'T:
❌ Use `pass` or `TODO` in final code
❌ Create multiple versions of same file
CODE SIZE: 300-500 lines target
```

**Benefits**:
- ✅ Clear sequence (Step 1 → Step 2 → ...)
- ✅ Line count expectations (30-40, then 40-60, etc.)
- ✅ Checkpoints after each step
- ✅ Explicit code examples (not just descriptions)
- ✅ Validation checklist to review
- ✅ Hard constraints (no pass, no TODO)

---

## Expected Results

### Weak Models (llama-4-scout-17b, mistral-7b)

**Before Guardrails**:
```
❌ ~200 lines (incomplete)
❌ 7 conflicting App.jsx files
❌ Missing implementations (pass statements)
❌ Non-functional
```

**After Guardrails**:
```
✅ 350-450 lines (more complete)
✅ Single coherent file structure
✅ Fewer pass/TODO statements
✅ Better chance of functionality
```

**Improvement**: From ~20% success rate → ~60% success rate (estimated)

### Strong Models (Claude, GPT-4)

**No Negative Impact**: Strong models already follow good practices, procedural workflow doesn't constrain them - they can still expand beyond the steps.

---

## Testing

### Verify Enhanced Template

```bash
# Check that guardrails were added
cat misc/app_templates/app_5_backend_cart.md | grep "PROCEDURAL WORKFLOW"
cat misc/app_templates/app_5_backend_cart.md | grep "VALIDATION CHECKLIST"
cat misc/app_templates/app_5_backend_cart.md | grep "CONSTRAINTS & BOUNDARIES"
```

### Test Generation with Enhanced Template

```bash
# Generate app with weak model using enhanced template
curl -X POST http://localhost:5000/api/sample-gen/generate \
  -H "Content-Type: application/json" \
  -d '{
    "template_id": "5",
    "model": "meta-llama/llama-4-scout-17b-16e-instruct"
  }'

# Check generated output:
# - Should be >300 lines
# - Should have clear structure (imports → models → endpoints)
# - Should have fewer pass/TODO statements
# - Should be more likely to run
```

---

## Advantages Over Multi-Tier System

| Aspect | Multi-Tier | Procedural Guardrails |
|--------|-----------|----------------------|
| **Complexity** | High (model classification, routing) | Low (just enhanced templates) |
| **Maintenance** | 60 standard + 60 lite = 120 templates | 60 templates only |
| **Code Changes** | Modified generation service logic | No service logic changes |
| **Model Detection** | Required capability tier classification | Not needed |
| **Fallback** | Complex (lite → standard fallback) | Simple (all models use same templates) |
| **Testing** | Need to test routing, classification | Just test generation |

**Simpler is Better**: Procedural guardrails achieve 80% of the benefit with 20% of the complexity.

---

## Rollback

If guardrails cause issues:

```bash
# Restore original templates from backups
cd misc/app_templates
for f in *.md.bak; do
    mv "$f" "${f%.bak}"
done

# Or use git
git checkout misc/app_templates/*.md
```

---

## Future Enhancements

### 1. Add Concrete Code Examples

Instead of:
```markdown
STEP 3: Implement validation
```

Show exact pattern:
```markdown
STEP 3: Implement validation
```python
def validate_product_id(product_id):
    if not product_id or not isinstance(product_id, int):
        return None, "Invalid product ID"
    product = Product.query.get(product_id)
    if not product:
        return None, "Product not found"
    return product, None
```
```

### 2. Add Common Pitfalls Section

```markdown
### ⚠️ COMMON MISTAKES TO AVOID

❌ Forgetting to initialize database: `db.create_all()`
❌ Not handling None values from queries
❌ Missing CORS for cross-origin requests
❌ Hardcoding ports instead of using {{backend_port}}
```

### 3. Add Success Criteria

```markdown
### ✅ YOUR CODE IS COMPLETE WHEN:

1. `python app.py` runs without errors
2. All endpoints return valid JSON
3. Database initializes with sample data
4. No pass/TODO/... statements remain
5. Code passes basic smoke test
```

---

## Conclusion

**Status**: ✅ IMPLEMENTED (30/30 templates enhanced)

**Result**: Templates now guide models step-by-step through code generation with:
- Clear procedural workflow (5 steps)
- Validation checklist (16 items)
- Explicit constraints (DOs and DON'Ts)
- Line count expectations (300-500 target)

**Impact**: Even weak models should generate better, more complete code by following the structured workflow.

**Simple & Effective**: No complex system, just better prompts! 🎯
