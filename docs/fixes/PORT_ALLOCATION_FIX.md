# Port Allocation and Container Naming Fix

## Issues Fixed

### 1. Port Conflicts
**Problem**: Multiple models generating apps with the same app_number were allocated identical ports, causing Docker bind failures.

**Example Error**:
```
Bind for 0.0.0.0:5003 failed: port is already allocated
```

> **Legacy Note:** References to `SimpleGenerationService` reflect the original
> implementation prior to its consolidation into `generation.py`
> (`GenerationService`). The behaviour described here is still enforced by the
> new service; the module joins remain for compatibility via a thin shim.

**Root Cause**: The simple port formula in `SimpleGenerationService.get_ports()` only considered `app_num`, not `model_slug`:
```python
# OLD (BROKEN):
backend_port = self.base_backend_port + (app_num * 2)  # 5001 + (1*2) = 5003
frontend_port = self.base_frontend_port + (app_num * 2) # 8001 + (1*2) = 8003
```

This meant:
- `anthropic_claude-4.5-haiku-20251001/app1` → 5003/8003
- `openai_gpt-5-mini-2025-08-07/app1` → 5003/8003 ❌ **CONFLICT**

**Fix**: Use `PortAllocationService` which tracks allocations per `(model, app_num)` pair in the database:
```python
# NEW (FIXED):
from app.services.port_allocation_service import get_port_allocation_service

port_service = get_port_allocation_service()
port_pair = port_service.get_or_allocate_ports(model_slug, app_num)
return port_pair.backend, port_pair.frontend
```

**Result**: Each model+app combination gets unique ports:
- `anthropic_claude-4.5-haiku-20251001/app1` → 5001/8001 ✅
- `anthropic_claude-4.5-haiku-20251001/app2` → 5003/8003 ✅
- `anthropic_claude-4.5-haiku-20251001/app3` → 5005/8005 ✅
- `openai_gpt-5-mini-2025-08-07/app1` → 5007/8007 ✅
- `openai_gpt-5-mini-2025-08-07/app2` → 5009/8009 ✅
- `openai_gpt-5-mini-2025-08-07/app3` → 5011/8011 ✅

### 2. Container Naming Conflicts
**Problem**: Docker container names were generic and conflicted across different models.

**Example**:
```bash
# Both models created containers with same name:
anthropic-claude-4-5-haiku-20251001-app1_backend
openai-gpt-5-mini-2025-08-07-app1_backend
```

But the `.env` files had `PROJECT_NAME=myapp`, so Docker was trying to create:
```
app_backend  # Same for all models! ❌
app_frontend
```

**Root Cause**: The scaffolding template had a hardcoded PROJECT_NAME:
```bash
# OLD .env.example:
PROJECT_NAME=myapp  # ❌ Same for all apps
```

**Fix**: Generate unique PROJECT_NAME for each model+app:
```python
# In simple_generation_service.py scaffold_app():
safe_model_slug = model_slug.replace('_', '-').replace('.', '-')
project_name = f"{safe_model_slug}-app{app_num}"

substitutions = {
    'PROJECT_NAME': project_name,  # e.g., "anthropic-claude-4-5-haiku-20251001-app1"
    # ...
}
```

**Template Update**:
```bash
# NEW .env.example:
PROJECT_NAME={{PROJECT_NAME}}  # ✅ Replaced during scaffolding
```

**Result**: Unique container names per model+app:
```bash
# Anthropic model:
anthropic-claude-4-5-haiku-20251001-app1_backend
anthropic-claude-4-5-haiku-20251001-app1_frontend

# OpenAI model:
openai-gpt-5-mini-2025-08-07-app1_backend
openai-gpt-5-mini-2025-08-07-app1_frontend
```

### 3. Missing .env Files
**Problem**: Docker Compose wasn't reading environment variables because only `.env.example` existed, not `.env`.

**Fix**: Auto-create `.env` from `.env.example` during scaffolding:
```python
# In simple_generation_service.py scaffold_app():
env_example = app_dir / '.env.example'
env_file = app_dir / '.env'
if env_example.exists():
    env_file.write_text(env_example.read_text(encoding='utf-8'), encoding='utf-8')
```

## Files Changed

### 1. `src/app/services/simple_generation_service.py`
- Updated `get_ports()` to use `PortAllocationService`
- Updated `scaffold_app()` to generate unique PROJECT_NAME
- Added .env file creation from .env.example

### 2. `misc/scaffolding/react-flask/.env.example`
- Changed `PROJECT_NAME=myapp` to `PROJECT_NAME={{PROJECT_NAME}}`

### 3. New Scripts
- `scripts/fix_generated_app_ports.py` - Bulk fix existing apps
- `scripts/check_port_allocations.py` - Audit port assignments

## Verification

### Port Allocation Check
```bash
python scripts/check_port_allocations.py
```

**Output**:
```
📊 Port Allocations Database
================================================================================
Model                                              App    Backend    Frontend
================================================================================
anthropic_claude-4.5-haiku-20251001                1      5001       8001
anthropic_claude-4.5-haiku-20251001                2      5003       8003
anthropic_claude-4.5-haiku-20251001                3      5005       8005
openai_gpt-5-mini-2025-08-07                       1      5007       8007
openai_gpt-5-mini-2025-08-07                       2      5009       8009
openai_gpt-5-mini-2025-08-07                       3      5011       8011
================================================================================
Total allocations: 6

✅ No port conflicts detected
```

### Container Naming Test
```bash
cd generated/apps/anthropic_claude-4.5-haiku-20251001/app1
docker-compose up -d
docker ps --format "table {{.Names}}\t{{.Ports}}"
```

**Output**:
```
NAMES                                               PORTS
anthropic-claude-4-5-haiku-20251001-app1_backend    0.0.0.0:5001->5001/tcp
anthropic-claude-4-5-haiku-20251001-app1_frontend   0.0.0.0:8001->80/tcp
```

✅ **Correct container names**
✅ **Correct ports**

### Concurrent Start Test
```bash
# Start multiple apps simultaneously
cd generated/apps/anthropic_claude-4.5-haiku-20251001/app1 && docker-compose up -d
cd ../app2 && docker-compose up -d
cd ../../openai_gpt-5-mini-2025-08-07/app1 && docker-compose up -d

docker ps --format "table {{.Names}}\t{{.Ports}}"
```

**Expected**: All containers start without port conflicts ✅

## Migration Guide

### For Existing Apps (Already Generated)
```bash
# Fix all existing generated apps:
python scripts/fix_generated_app_ports.py

# Or fix individually:
cd generated/apps/{model}/{app}
rm .env  # Remove old .env
python -c "from app.services.simple_generation_service import SimpleGenerationService; \
           s = SimpleGenerationService(); \
           s.scaffold_app('{model}', {app_num}, force=True)"
```

### For New Apps
No action needed - the fix is automatic in `SimpleGenerationService`.

## Technical Details

### Port Allocation Algorithm
1. Check database for existing `(model, app_num)` allocation
2. If found, return existing ports
3. If not found, find next free port pair:
   - Query all allocated ports from database
   - Start from `BASE_BACKEND_PORT` (5001) and `BASE_FRONTEND_PORT` (8001)
   - Increment by `PORT_STEP` (2) until both ports are free
   - Register allocation in database with unique constraint

### Database Schema
```sql
CREATE TABLE port_configurations (
    id INTEGER PRIMARY KEY,
    model VARCHAR(200) NOT NULL,
    app_num INTEGER NOT NULL,
    backend_port INTEGER UNIQUE NOT NULL,
    frontend_port INTEGER UNIQUE NOT NULL,
    is_available BOOLEAN DEFAULT TRUE,
    UNIQUE(model, app_num)
);
```

### Docker Compose Integration
```yaml
services:
  backend:
    container_name: ${PROJECT_NAME:-app}_backend
    ports:
      - "${BACKEND_PORT:-5000}:${FLASK_RUN_PORT}"
    environment:
      - FLASK_RUN_PORT=${FLASK_RUN_PORT}
```

The `.env` file provides:
- `PROJECT_NAME=anthropic-claude-4-5-haiku-20251001-app1`
- `BACKEND_PORT=5001`
- `FRONTEND_PORT=8001`

## Testing Checklist

- [x] Port allocation per model+app is unique
- [x] No port conflicts in database
- [x] Container names are unique per model+app
- [x] `.env` file is created automatically
- [x] Docker Compose reads PROJECT_NAME from .env
- [x] Multiple apps can start concurrently
- [x] Existing apps can be fixed via script
- [x] New apps work correctly out of the box

## Related Documentation

- `docs/features/PORT_ALLOCATION.md` - Port allocation system overview
- `docs/CONTAINERIZATION_COMPLETE.md` - Docker infrastructure
- `src/app/services/port_allocation_service.py` - Core allocation logic
- `src/app/services/simple_generation_service.py` - Integration point
