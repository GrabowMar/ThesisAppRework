# V2 Template UI Integration Guide

## Quick Start

The V2 template system UI component is ready to use. This guide shows how to integrate it into the existing sample generator interface.

---

## Option 1: Add as New Tab (Recommended)

### Step 1: Update `sample_generator_main.html`

Add a new tab to the navigation:

```html
<!-- Add to the nav-tabs section -->
<li class="nav-item">
    <a class="nav-link" data-bs-toggle="tab" href="#v2-tab">
        <i class="bi bi-stars"></i> V2 Templates
    </a>
</li>
```

Add the tab content:

```html
<!-- Add to the tab-content section -->
<div class="tab-pane fade" id="v2-tab">
    {% include 'pages/sample_generator/partials/v2_generation_tab.html' %}
</div>
```

### Step 2: Test

1. Start Flask app: `cd src && python main.py`
2. Navigate to `/sample-generator`
3. Click "V2 Templates" tab
4. Select requirement and model
5. Click "Generate Code"

---

## Option 2: Add to Existing Generation Tab

### Update `generation_tab.html`

Add at the bottom of the file:

```html
<!-- Include V2 component -->
{% include 'pages/sample_generator/partials/v2_generation_tab.html' %}
```

---

## Option 3: Standalone Page

### Create new route in `src/app/routes/ui.py`:

```python
@ui_bp.route('/sample-generator-v2')
def sample_generator_v2():
    """V2 Template System UI"""
    return render_template('pages/sample_generator_v2.html')
```

### Create `src/templates/pages/sample_generator_v2.html`:

```html
{% extends "layouts/app.html" %}
{% block title %}Sample Generator V2{% endblock %}

{% block content %}
<div class="container-fluid py-4">
    <h1>Code Generator - V2 Templates</h1>
    {% include 'pages/sample_generator/partials/v2_generation_tab.html' %}
</div>
{% endblock %}
```

---

## Component Features

### What's Included

✅ **Requirement Selection** - Dropdown populated from `/api/v2/templates/requirements`  
✅ **Model Selection** - Reuses existing model API  
✅ **Component Toggle** - Choose backend, frontend, or both  
✅ **Preview** - See rendered prompts before generation  
✅ **Progress Tracking** - Real-time generation status  
✅ **Results Display** - Links to generated code  
✅ **Error Handling** - User-friendly error messages  
✅ **Advanced Options** - Temperature and max tokens configuration  
✅ **Info Modal** - Documentation about V2 system  

### Dependencies

- Bootstrap 5 (already included)
- Bootstrap Icons (already included)
- Fetch API (native browser support)
- No jQuery required

---

## API Endpoints Used

The component calls these V2 endpoints:

1. `GET /api/v2/templates/requirements` - Load available requirements
2. `POST /api/v2/templates/preview` - Preview templates
3. `POST /api/v2/templates/generate/backend` - Generate backend
4. `POST /api/v2/templates/generate/frontend` - Generate frontend

And existing endpoints:

1. `GET /api/models` - Load available models

---

## Customization

### Change Default Temperature

Edit `v2_generation_tab.html`:

```html
<input type="number" class="form-control" id="v2-temperature" 
       value="0.7" min="0" max="2" step="0.1">
```

Change `value="0.7"` to your preferred default.

### Change Default Max Tokens

```html
<input type="number" class="form-control" id="v2-max-tokens" 
       value="4000" min="1000" max="8000" step="500">
```

### Add More Requirements

1. Create JSON file in `misc/requirements/my_app.json`
2. Restart Flask app
3. New requirement appears in dropdown automatically

### Styling

The component uses standard Bootstrap 5 classes:
- `card` for containers
- `form-control` for inputs
- `btn btn-success` for buttons
- `alert alert-info` for messages

Customize by overriding Bootstrap variables or adding custom CSS.

---

## Testing Checklist

Before deploying:

- [ ] Requirements dropdown loads correctly
- [ ] Model dropdown loads correctly
- [ ] Requirement description updates on selection
- [ ] Preview modal shows backend/frontend prompts
- [ ] Generate button triggers API calls
- [ ] Progress indicator shows during generation
- [ ] Results display after successful generation
- [ ] Error messages show on failure
- [ ] Advanced options (temperature, max tokens) work
- [ ] Info modal displays V2 system information

---

## Troubleshooting

### Issue: Dropdowns Empty

**Cause:** API endpoints not responding  
**Fix:** 
1. Check Flask app is running
2. Check `templates_v2_bp` is registered in `src/app/routes/__init__.py`
3. Check logs for errors

### Issue: Generation Button Does Nothing

**Cause:** JavaScript errors  
**Fix:**
1. Open browser console (F12)
2. Look for JavaScript errors
3. Check fetch requests in Network tab

### Issue: "CORS Error"

**Cause:** API requests blocked by CORS  
**Fix:** Ensure Flask-CORS is configured (already should be in `factory.py`)

### Issue: Generation Fails

**Cause:** Various (API key, rate limits, etc.)  
**Fix:**
1. Check `OPENROUTER_API_KEY` in `.env`
2. Check model is available (not rate limited)
3. Check logs in `logs/` directory

---

## Example Usage Flow

1. **User opens V2 tab**
   - Sees 3 requirements in dropdown
   - Sees all available models

2. **User selects "Todo App"**
   - Description shows: "Simple CRUD todo list with filters"

3. **User clicks "Preview Templates"**
   - Modal opens with backend/frontend prompts
   - User reviews ~8,300 char backend prompt
   - User reviews ~11,900 char frontend prompt

4. **User selects "openai/gpt-4"**
   - Model selector shows OpenAI section

5. **User clicks "Generate Code"**
   - Progress bar shows "Generating backend..."
   - Then "Generating frontend..."
   - After ~30 seconds, success message appears

6. **User sees results**
   - "Backend: ✓ Generated successfully (12.5s, 3245 tokens)"
   - "Frontend: ✓ Generated successfully (15.2s, 4123 tokens)"
   - Link to view generated app

---

## Performance Notes

- Requirements API call: ~10ms
- Models API call: ~50ms (cached)
- Preview API call: ~100ms (template rendering)
- Generation API call: 10-60s (depends on model)

The UI loads quickly, but generation takes time due to LLM processing.

---

## Future Enhancements

Potential additions to the UI:

- [ ] Batch generation (multiple requirements at once)
- [ ] Generation history (past generations)
- [ ] Custom requirements editor (create requirements in UI)
- [ ] Code diff viewer (compare generated versions)
- [ ] Download as ZIP button
- [ ] Share generation link
- [ ] Real-time streaming progress (via WebSocket)

---

## Complete Integration Example

### File: `src/templates/pages/sample_generator/sample_generator_main.html`

```html
<!-- Add to nav tabs -->
<ul class="nav nav-tabs">
    <li class="nav-item">
        <a class="nav-link active" data-bs-toggle="tab" href="#generation-tab">Generate</a>
    </li>
    <li class="nav-item">
        <a class="nav-link" data-bs-toggle="tab" href="#v2-tab">V2 Templates</a>  <!-- NEW -->
    </li>
    <!-- other tabs... -->
</ul>

<!-- Add to tab content -->
<div class="tab-content">
    <div class="tab-pane fade show active" id="generation-tab">
        {% include 'pages/sample_generator/partials/generation_tab.html' %}
    </div>
    <div class="tab-pane fade" id="v2-tab">  <!-- NEW -->
        {% include 'pages/sample_generator/partials/v2_generation_tab.html' %}
    </div>
    <!-- other tab panes... -->
</div>
```

That's it! The component is self-contained and requires no additional JavaScript files or CSS.

---

## Support

For issues or questions:
- Check `docs/TEMPLATE_V2_COMPLETE.md` for system overview
- Check `docs/TEMPLATE_V2_GENERATION.md` for API usage
- Check logs in `logs/` directory
- Review API responses in browser Network tab
