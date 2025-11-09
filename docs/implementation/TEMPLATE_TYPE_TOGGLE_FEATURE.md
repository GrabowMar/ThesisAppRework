# Template Type Toggle Feature

## Overview
Added user-controllable template type selection to the Sample Generator wizard, allowing manual override of the automatic template selection based on model output limits.

## Feature Details

### What It Does
- **Auto mode** (default): Automatically selects compact templates for models with <8000 token output limit, full templates for ≥8000
- **Full mode**: Forces use of detailed full templates regardless of model capability
- **Compact mode**: Forces use of concise compact templates regardless of model capability

### UI Location
**Sample Generator → Step 3: Review & Generate → Generation Options**

New card with:
- **Template Type dropdown** with 3 options: Auto / Full / Compact
- **Hint text** explaining when auto uses which template
- **Info card** showing example models for each category

### Technical Implementation

#### Frontend (wizard.html)
```html
<select class="form-select" id="template-type-preference">
  <option value="auto" selected>Auto (based on model output limit)</option>
  <option value="full">Full templates (detailed instructions)</option>
  <option value="compact">Compact templates (concise instructions)</option>
</select>
```

#### JavaScript (sample_generator_wizard.js)
```javascript
const templateType = templateTypeEl ? templateTypeEl.value : 'auto';

body: JSON.stringify({
  // ... other params
  template_type: templateType  // 'auto', 'full', or 'compact'
})
```

#### API Route (generation.py)
```python
template_type = data.get('template_type', 'auto')

result = asyncio.run(service.generate_full_app(
    # ... other params
    template_type=template_type
))
```

#### Generation Service (generation.py)
```python
@dataclass
class GenerationConfig:
    # ... other fields
    template_type: str = 'auto'  # 'auto', 'full', or 'compact'

async def generate_full_app(
    # ... other params
    template_type: str = 'auto'
) -> dict:
```

#### Template Selection Logic (_build_prompt)
```python
template_type = getattr(config, 'template_type', 'auto')

if template_type == 'full':
    use_compact = False
    logger.info(f"Using FULL template for {component} (forced by user preference)")
elif template_type == 'compact':
    use_compact = True
    logger.info(f"Using COMPACT template for {component} (forced by user preference)")
else:  # 'auto'
    token_limit = get_model_token_limit(config.model_slug)
    use_compact = token_limit < 8000
```

## Model Categories

### Full Templates (≥8000 tokens)
- GPT-4o (16384 tokens)
- GPT-4o-mini (16384 tokens)
- Claude 4.5 Sonnet/Haiku (8192 tokens)
- Claude 3.5 Sonnet (8192 tokens)
- Gemini 1.5 Pro/Flash (8192 tokens)
- Gemini 2.0 Flash (8192 tokens)
- Mistral Large/Medium/Codestral (8192 tokens)

### Compact Templates (<8000 tokens)
- GPT-3.5 Turbo (4096 tokens)
- GPT-4 (8192 tokens but treated as 4096)
- GPT-4 Turbo (4096 tokens)
- Claude 3 Opus/Sonnet/Haiku (4096 tokens)
- Llama 3.1/3.2 models (4096 tokens)
- Gemini Pro (2048 tokens)
- Default fallback (4096 tokens)

## Use Cases

### When to Use Full Templates
- **Weak models** that benefit from detailed instructions and examples
- **Code quality priority** over generation speed/cost
- **Complex requirements** that need extensive guidance

### When to Use Compact Templates
- **Strong models** that work well with concise instructions
- **Cost optimization** (fewer input tokens = lower cost)
- **Speed priority** (less to process = faster generation)
- **Token budget constraints**

### When to Use Auto
- **Default choice** for most use cases
- **Trust the system** to pick based on model capabilities
- **Consistent behavior** across different model tiers

## Testing

Test script: `test_template_type_option.py`

Results:
```
[OK] openai_gpt-3.5-turbo with auto → compact (4342 chars)
[OK] openai_gpt-3.5-turbo with full → full (10555 chars)
[OK] openai_gpt-4o with compact → compact (4342 chars)
```

All three modes working correctly with proper overrides.

## Files Modified

1. `src/templates/pages/sample_generator/partials/wizard.html`
   - Added Generation Options card in Step 3
   - Template Type dropdown selector
   - Info text and examples

2. `src/static/js/sample_generator_wizard.js`
   - Read template_type preference from UI
   - Pass to generation API

3. `src/app/routes/api/generation.py`
   - Accept template_type parameter
   - Pass to generation service
   - Log selection for debugging

4. `src/app/services/generation.py`
   - Add template_type to GenerationConfig
   - Add template_type parameter to generate_full_app
   - Update _build_prompt to respect preference
   - Enhanced logging for template selection

5. `misc/templates/README.md`
   - Documented template selection logic
   - Added model categorization

## API Usage

```bash
POST /api/gen/generate
{
  "model_slug": "openai_gpt-3.5-turbo",
  "app_num": 1,
  "template_slug": "crud_todo_list",
  "generate_frontend": true,
  "generate_backend": true,
  "template_type": "full"  // NEW: 'auto', 'full', or 'compact'
}
```

Default: `"template_type": "auto"`

## Benefits

1. **Flexibility**: Override automatic selection when needed
2. **Experimentation**: Test same model with different instruction styles
3. **Optimization**: Fine-tune cost vs quality tradeoff
4. **Debugging**: Force specific template to isolate issues
5. **Control**: User decides what works best for their use case

## Backward Compatibility

- Default value is 'auto' (existing behavior)
- API accepts requests without template_type parameter
- No breaking changes to existing integrations
