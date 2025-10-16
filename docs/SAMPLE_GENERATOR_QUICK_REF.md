# Sample Generator Backend - Quick Reference

## ⚠️ IMPORTANT - Use New System Only!

### ❌ DO NOT USE (Old, Broken)
- `/api/sample-gen/*` endpoints
- `sample_generation_service.py` (3700 lines)
- Any code referencing the old system

### ✅ USE ONLY (New, Working)
- `/api/gen/*` endpoints
- `simple_generation_service.py` (400 lines)
- `docs/SIMPLE_GENERATION_SYSTEM.md` for documentation

## Quick Commands

### Test the System
```bash
python scripts/test_simple_generation.py
```

### Find Broken Apps
```bash
python scripts/cleanup_broken_apps.py --dry-run
```

### Fix Broken Apps
```bash
python scripts/cleanup_broken_apps.py --fix
```

## API Quick Reference

### Scaffold an App
```bash
curl -X POST http://localhost:5000/api/gen/scaffold \
  -H "Content-Type: application/json" \
  -d '{"model_slug":"x-ai/grok-code-fast-1","app_num":1}'
```

### Generate Frontend
```bash
curl -X POST http://localhost:5000/api/gen/generate \
  -H "Content-Type: application/json" \
  -d '{
    "template_id":1,
    "model_slug":"x-ai/grok-code-fast-1",
    "app_num":1,
    "component":"frontend"
  }'
```

### Generate Both
```bash
curl -X POST http://localhost:5000/api/gen/generate-full \
  -H "Content-Type: application/json" \
  -d '{
    "template_id":1,
    "model_slug":"x-ai/grok-code-fast-1",
    "app_num":1
  }'
```

### List Apps
```bash
curl http://localhost:5000/api/gen/apps
```

## Port Allocation

Simple formula:
- **Backend**: `5001 + (app_num * 2)`
- **Frontend**: `8001 + (app_num * 2)`

Examples:
- App 1: backend=5001, frontend=8001
- App 2: backend=5003, frontend=8003
- App 3: backend=5005, frontend=8005

## File Structure

After generation, apps have this structure:
```
generated/apps/{model_slug}/app{N}/
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── Dockerfile
│   ├── .dockerignore
│   ├── app.py
│   └── requirements.txt
└── frontend/
    ├── Dockerfile
    ├── .dockerignore
    ├── nginx.conf
    ├── vite.config.js
    ├── package.json
    ├── index.html
    └── src/
        ├── App.jsx
        ├── App.css
        └── main.jsx
```

## Documentation

- `docs/SIMPLE_GENERATION_SYSTEM.md` - Complete system guide
- `docs/features/SAMPLE_GENERATOR_REWRITE.md` - Rewrite details
- `.github/copilot-instructions.md` - Updated instructions

## Common Issues

### Issue: App not scaffolded properly
**Solution**: Re-run scaffold endpoint with `force: true`

### Issue: Missing Docker files
**Solution**: Run `cleanup_broken_apps.py --fix`

### Issue: Port placeholders not replaced
**Solution**: This was a bug in old system. New system fixes it automatically.

### Issue: Multiple numbered files (index_02.html)
**Solution**: This was a bug in old system. New system creates ONE file per type.

## Migration Checklist

- [ ] Update frontend code to use `/api/gen/*` endpoints
- [ ] Test with a few apps
- [ ] Run cleanup script on existing apps
- [ ] Verify Docker containers start correctly
- [ ] Remove references to old `/api/sample-gen/*` endpoints
- [ ] Remove old `sample_generation_service.py` after migration complete
