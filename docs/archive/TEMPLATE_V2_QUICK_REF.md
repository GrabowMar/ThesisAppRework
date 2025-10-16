# Template System V2 - Quick Reference

## 📁 Directory Structure
```
misc/
├── requirements/       # JSON files defining what apps should do
├── scaffolding/       # Minimal working starter code  
└── templates/         # Jinja2 prompt templates
```

## 🚀 Quick Start

### Test the System
```bash
python scripts/test_template_v2.py
```

### Use the API
```bash
# List requirements
curl http://localhost:5000/api/v2/templates/requirements

# Preview templates
curl -X POST http://localhost:5000/api/v2/templates/preview \
  -H "Content-Type: application/json" \
  -d '{"requirement_id": "xsd_verifier"}'
```

### Use in Python
```python
from app.services.template_renderer import get_template_renderer

renderer = get_template_renderer()

# Preview both templates
preview = renderer.preview('two-query', 'xsd_verifier', 'react-flask')
print(preview['backend'])   # Backend prompt
print(preview['frontend'])  # Frontend prompt
```

## 📝 Add New App

1. Create `misc/requirements/my_app.json`:
```json
{
  "app_id": "my_app",
  "name": "My App",
  "description": "What it does",
  "backend_requirements": ["Feature 1", "Feature 2"],
  "frontend_requirements": ["UI 1", "UI 2"]
}
```

2. That's it! The system will automatically use existing scaffolding and templates.

## 🔧 Available Apps

1. **XSD Validator** - Validate XML against XSD schemas
2. **Base64 Converter** - Encode/decode Base64 text
3. **Simple Todo** - Basic todo list manager

## 📚 Key Files

- `src/app/services/template_renderer.py` - Core service
- `src/app/routes/api/templates_v2.py` - API endpoints
- `misc/README.md` - Full documentation
- `docs/TEMPLATE_SYSTEM_V2_SUMMARY.md` - Complete summary

## 🎯 Template Variables

Templates have access to:
- `name` - App name
- `description` - App description  
- `backend_requirements[]` - List of backend features
- `frontend_requirements[]` - List of frontend features
- `scaffolding_*` - All scaffolding files

## 📊 Status

✅ Backend service complete
✅ API routes complete
✅ 3 example requirements
✅ 1 scaffolding type (react-flask)
✅ 1 template type (two-query)
✅ Tests passing

⏳ Frontend UI integration (future work)
⏳ Generation service integration (future work)
