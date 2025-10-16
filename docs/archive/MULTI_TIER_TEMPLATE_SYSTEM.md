# Multi-Tier Template System - Implementation Guide

## Overview

**Problem**: Weaker AI models (< 30B parameters) struggle with complex templates designed for flagship models, resulting in:
- Fragmented/incomplete code
- Duplicate conflicting files  
- Apps far below target size (~200 lines vs. 700+ lines)
- Non-functional outputs

**Solution**: Multi-tier template system that automatically routes models to appropriate templates based on capability.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Generation Request                        │
│                  (app_num, model_slug)                       │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
        ┌─────────────────────────────┐
        │  get_model_capability_tier  │
        │   (model classification)    │
        └─────────────┬───────────────┘
                      │
         ┌────────────┴──────────────┐
         │                           │
    ┌────▼─────┐               ┌─────▼────┐
    │  'lite'  │               │'standard'│
    │ (< 30B)  │               │ (30B+)   │
    └────┬─────┘               └─────┬────┘
         │                           │
         ▼                           ▼
    ┌─────────────────┐    ┌──────────────────┐
    │app_templates_lite│    │  app_templates   │
    │  150-250 lines   │    │  300-500+ lines  │
    │  3 features      │    │  4+ features     │
    │  Prescriptive    │    │  Architectural   │
    └─────────────────┘    └──────────────────┘
```

---

## Model Classification Logic

### Tier: `lite` (Smaller/Weaker Models)

**Criteria**:
- < 30B parameters (7B, 8B, 13B, 17B, 20B)
- Known weak performers (explicit list)

**Examples**:
- `meta-llama/llama-4-scout-17b-16e-instruct` ✓
- `mistralai/mistral-7b` ✓
- `google/gemma-7b` ✓
- `microsoft/phi-3-mini` ✓

**Template Source**: `misc/app_templates_lite/`

### Tier: `standard` (Capable Models)

**Criteria**:
- ≥ 30B parameters or flagship models
- Default fallback for unknown models

**Examples**:
- `anthropic/claude-3.5-sonnet` ✓
- `openai/gpt-4` ✓
- `meta-llama/llama-3-70b` ✓
- `google/gemini-1.5-pro` ✓

**Template Source**: `misc/app_templates/`

---

## Template Comparison

| Aspect | Lite Templates | Standard Templates |
|--------|---------------|-------------------|
| **Target Size** | 150-250 backend, 200-300 frontend | 300-500+ backend, 400-600+ frontend |
| **Features** | 3 core features (fixed) | 4+ features (expandable) |
| **Instructions** | Step-by-step, numbered | Architectural guidance |
| **Code Examples** | Exact patterns with comments | Structure/organization patterns |
| **Complexity** | Simplified CRUD | Production-grade with transactions |
| **Success Criteria** | Exact endpoint/component list | Quality checklist |
| **Scaffolding** | More hand-holding | Expect model to figure it out |

### Example: Shopping Cart App

**Lite Template** (`app_5_backend_cart.md`):
```markdown
**STEP 3** (Lines 51-80): Implement the `/api/products` endpoint (GET)
- Query all products from database
- Return JSON list of products with id, name, price, stock

**STEP 4** (Lines 81-130): Implement the `/api/cart/add` endpoint (POST)
- Accept product_id and quantity in JSON
- Validate product exists and has sufficient stock
- Initialize session cart if needed (list of dicts)
```

**Standard Template** (`app_5_backend_cart.md`):
```markdown
Build a **comprehensive backend system** that implements **at minimum** 
the following core functionalities (expand beyond these with additional 
features that make sense for the application):

1. **Product Catalog Management:** Implement endpoints to list all 
   available products with filtering...
2. **Session-Based Shopping Cart:** Implement endpoints to manage a 
   shopping cart stored in the user's session...
```

---

## Implementation Details

### 1. Model Capability Detection

**Function**: `get_model_capability_tier(model_slug: str) -> str`

**Location**: `src/app/services/sample_generation_service.py` (lines ~80-120)

**Logic**:
```python
def get_model_capability_tier(model_slug: str) -> str:
    model_lower = model_slug.lower()
    
    # Explicit lite list
    LITE_MODELS = ['llama-4-scout', 'mistral-7b', 'gemma-7b', ...]
    for lite_model in LITE_MODELS:
        if lite_model in model_lower:
            return 'lite'
    
    # Parameter-based classification
    SMALL_SIZE_INDICATORS = ['7b', '8b', '9b', '13b', '14b', '17b', '20b']
    for size in SMALL_SIZE_INDICATORS:
        if size in model_lower:
            return 'lite'
    
    return 'standard'  # Default
```

### 2. Template Loading

**Location**: `SampleGenerationService.__init__()` (lines ~2595-2610)

```python
# Load standard templates
paired_count = self.template_registry.load_frontend_backend_pairs(
    self.app_templates_dir
)

# Load lite templates
if self.app_templates_lite_dir.exists():
    lite_count = self.template_registry.load_frontend_backend_pairs(
        self.app_templates_lite_dir
    )
```

### 3. Template Selection

**Location**: `generate_async()` method (lines ~3085-3115)

```python
# Determine model capability tier
model_tier = get_model_capability_tier(model)

# Filter candidates based on tier
if model_tier == 'lite':
    # Prefer templates from app_templates_lite directory
    lite_candidates = [
        t for t in candidates 
        if t.file_path and 'app_templates_lite' in str(t.file_path)
    ]
    if lite_candidates:
        candidates = lite_candidates
    else:
        # Fallback to standard if no lite templates available
        logger.warning("No lite templates found, using standard")
```

---

## Available Lite Templates

| App # | Backend | Frontend | Features |
|-------|---------|----------|----------|
| 1 | ✅ Login System | 🔄 (TODO) | Register, Login, Profile |
| 5 | ✅ Shopping Cart | ✅ Product Browser | Products, Cart, Totals |
| 10 | 🔄 (TODO) | 🔄 (TODO) | Todo CRUD |

**Note**: Only 3 lite templates created as proof-of-concept. Add more as needed.

---

## Usage

### Automatic (Recommended)

The system automatically detects model capability and routes to appropriate templates:

```python
# This automatically uses lite templates for weak models
service = get_sample_generation_service()
result = await service.generate_async(
    template_id="5",  # Shopping cart
    model="meta-llama/llama-4-scout-17b-16e-instruct",  # Weak model
    generate_frontend=True,
    generate_backend=True
)
# → Uses app_templates_lite/app_5_backend_cart.md (150-250 lines)
```

```python
# This automatically uses standard templates for strong models
result = await service.generate_async(
    template_id="5",
    model="anthropic/claude-3.5-sonnet",  # Strong model
    generate_frontend=True,
    generate_backend=True
)
# → Uses app_templates/app_5_backend_cart.md (300-500+ lines)
```

### Manual Override (Advanced)

To force a specific template tier (not recommended):

```python
# Force lite template even for strong model
template = service.template_registry.get_by_path(
    "misc/app_templates_lite/app_5_backend_cart.md"
)
```

---

## Testing

### Test Lite Template with Weak Model

```bash
# Generate app using weak model (should use lite template)
curl -X POST http://localhost:5000/api/sample-gen/generate \
  -H "Content-Type: application/json" \
  -d '{
    "template_id": "5",
    "model": "meta-llama/llama-4-scout-17b-16e-instruct",
    "generate_frontend": true,
    "generate_backend": true
  }'
```

**Expected Result**:
- Logs show: `Model capability tier for 'meta-llama/llama-4-scout-17b-16e-instruct': lite`
- Logs show: `Using lite template candidates`
- Generated `app.py`: 150-250 lines
- Has exactly 4 endpoints (health + 3 features)
- Code is simple, functional, complete

### Test Standard Template with Strong Model

```bash
# Generate app using strong model (should use standard template)
curl -X POST http://localhost:5000/api/sample-gen/generate \
  -H "Content-Type: application/json" \
  -d '{
    "template_id": "5",
    "model": "anthropic/claude-3.5-sonnet",
    "generate_frontend": true,
    "generate_backend": true
  }'
```

**Expected Result**:
- Logs show: `Model capability tier for 'anthropic/claude-3.5-sonnet': standard`
- Logs show: No lite template filtering
- Generated `app.py`: 300-500+ lines
- Has 5+ endpoints (expanded features)
- Code is production-grade with transactions

---

## Creating New Lite Templates

### Guidelines

1. **Keep it Simple**: 3 core features maximum
2. **Be Prescriptive**: Step-by-step with line number targets
3. **Show Examples**: Exact code patterns, not just descriptions
4. **Set Expectations**: "Your app.py should have exactly X endpoints"
5. **Limit Scope**: No advanced features (auth, payments, transactions)
6. **Target Size**: 150-250 backend, 200-300 frontend

### Template Structure

```markdown
# Goal: [Simple, Clear Objective]

Generate a working [app type] with exactly 3 core features: [A, B, C].

---

### **1. What You're Building**
[Simple description, specific role]
**Target Size**: 150-250 lines

---

### **2. Step-by-Step Instructions**
**STEP 1** (Lines 1-25): [Exact task]
**STEP 2** (Lines 26-50): [Exact task]
...

---

### **3. Required Code Structure**
```python
# Show exact skeleton with comments
# Use "YOUR CODE HERE" for implementation sections
```

---

### **4. Success Checklist**
- [✓] Exactly N endpoints
- [✓] Specific feature list
- [✓] Line count target
```

### Process

1. Copy existing lite template as starting point
2. Simplify features to 3 core ones
3. Add step-by-step instructions with line numbers
4. Include code skeleton with comment placeholders
5. Set realistic size targets (150-250 backend, 200-300 frontend)
6. Test with weak model (llama-4-scout-17b)
7. Iterate until output is functional and complete

---

## Monitoring & Debugging

### Check Which Template Was Used

```python
# Look for these log messages:
# "Model capability tier for 'model-name': lite"
# "Using lite template candidates"
# "Found backend template: app_5_backend_cart (path: ...app_templates_lite/...)"
```

### Common Issues

**Issue**: Weak model still gets standard template
- **Cause**: No lite template exists for that app_num
- **Fix**: Create lite template or model falls back to standard

**Issue**: Strong model gets lite template
- **Cause**: Model slug matches lite pattern (unlikely)
- **Fix**: Adjust `get_model_capability_tier()` logic

**Issue**: Generated code still too small
- **Cause**: Model is too weak even for lite templates
- **Fix**: Add to `DISABLED_ANALYSIS_MODELS` or use stronger model

---

## Future Enhancements

### Tier Expansion

```
lite → standard → advanced
7-20B   30-70B     70B+

Simple → Production → Enterprise
```

### Dynamic Scaling

```python
def get_target_lines(model_tier: str, app_complexity: str) -> Tuple[int, int]:
    targets = {
        ('lite', 'simple'): (150, 250),
        ('lite', 'medium'): (200, 300),
        ('standard', 'simple'): (250, 400),
        ('standard', 'medium'): (400, 600),
        ('advanced', 'medium'): (600, 1000),
    }
    return targets.get((model_tier, app_complexity), (300, 500))
```

### Model-Specific Guidance

```python
# Add model-specific quirks/strengths
MODEL_QUIRKS = {
    'llama-4-scout': "Prefer explicit imports, avoid f-strings",
    'mistral-7b': "Strong at FastAPI, weak at Flask",
}
```

---

## Rollback

If the multi-tier system causes issues:

```bash
# 1. Remove lite template loading
git diff src/app/services/sample_generation_service.py
# Remove lines ~2603-2608 (lite template loading)

# 2. Remove tier classification logic
# Comment out get_model_capability_tier() calls in generate_async()

# 3. Keep lite templates but don't use them
# They won't be selected without explicit file path
```

---

## Metrics to Track

- **Success Rate by Tier**: % of generations that produce functional apps
- **Line Count by Tier**: Average lines generated (lite: 150-250, standard: 300-500+)
- **Endpoint Count**: Number of API endpoints implemented
- **Compilation Errors**: Syntax/import errors by tier
- **Functional Completeness**: % of apps that pass basic smoke tests

---

**Result**: Even weak models like `llama-4-scout-17b` can now generate functional, complete applications by using simpler, more prescriptive templates tailored to their capabilities.
