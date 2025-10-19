# Sample Generation Port Allocation & Container Naming - FIXED ✅

> **Legacy Note:** The implementation originally described here lived in
> `simple_generation_service.py`. That logic now resides in
> `generation.py` (`GenerationService`), with the legacy module retained only
> as a compatibility shim. The diagnostic details below remain relevant for
> understanding how the current service handles ports and container naming.

## Issue Summary
When generating multiple applications across different models using the sample generator wizard, two critical issues occurred:

1. **Port Conflicts**: Apps from different models with the same app_number tried to use identical ports
2. **Container Naming Conflicts**: All containers used generic names like "app_backend" instead of unique model-specific names

## Root Causes

### Port Allocation
- `SimpleGenerationService.get_ports()` used a simple formula based only on `app_num`
- Formula: `backend_port = 5001 + (app_num * 2)`
- This meant `anthropic/app1` and `openai/app1` both tried to use port 5003

### Container Naming
- `.env.example` template had hardcoded `PROJECT_NAME=myapp`
- Docker Compose used this generic name for all containers
- Result: All backend containers were named "app_backend", causing conflicts

## Solutions Implemented

### 1. Port Allocation Service Integration
**File**: `src/app/services/simple_generation_service.py`

Changed from simple formula to centralized port allocation:
```python
def get_ports(self, model_slug: str, app_num: int) -> Tuple[int, int]:
    from app.services.port_allocation_service import get_port_allocation_service
    
    port_service = get_port_allocation_service()
    port_pair = port_service.get_or_allocate_ports(model_slug, app_num)
    
    return port_pair.backend, port_pair.frontend
```

**Benefits**:
- Tracks allocations per `(model, app_num)` in database
- Prevents conflicts across all models
- Automatic gap filling when ports are released

### 2. Unique PROJECT_NAME Generation
**File**: `src/app/services/simple_generation_service.py`

```python
safe_model_slug = model_slug.replace('_', '-').replace('.', '-')
project_name = f"{safe_model_slug}-app{app_num}"

substitutions = {
    'PROJECT_NAME': project_name,  # e.g., "anthropic-claude-4-5-haiku-20251001-app1"
    'BACKEND_PORT': str(backend_port),
    'FRONTEND_PORT': str(frontend_port),
    # ...
}
```

**File**: `misc/scaffolding/react-flask/.env.example`
```bash
# Changed from:
PROJECT_NAME=myapp

# To:
PROJECT_NAME={{PROJECT_NAME}}
```

### 3. Automatic .env File Creation
**File**: `src/app/services/simple_generation_service.py`

```python
# Create .env from .env.example for Docker Compose
env_example = app_dir / '.env.example'
env_file = app_dir / '.env'
if env_example.exists():
    env_file.write_text(env_example.read_text(encoding='utf-8'), encoding='utf-8')
```

## Results

### Port Allocations (No Conflicts ✅)
```
Model                                     App    Backend    Frontend
anthropic_claude-4.5-haiku-20251001       1      5001       8001
anthropic_claude-4.5-haiku-20251001       2      5003       8003
anthropic_claude-4.5-haiku-20251001       3      5005       8005
openai_gpt-5-mini-2025-08-07              1      5007       8007
openai_gpt-5-mini-2025-08-07              2      5009       8009
openai_gpt-5-mini-2025-08-07              3      5011       8011
```

### Container Names (Unique ✅)
```
anthropic-claude-4-5-haiku-20251001-app1_backend   → 0.0.0.0:5001->5001/tcp
anthropic-claude-4-5-haiku-20251001-app1_frontend  → 0.0.0.0:8001->80/tcp

openai-gpt-5-mini-2025-08-07-app1_backend          → 0.0.0.0:5007->5007/tcp
openai-gpt-5-mini-2025-08-07-app1_frontend         → 0.0.0.0:8007->80/tcp
```

## Utility Scripts Created

### 1. Fix Existing Apps
`scripts/fix_generated_app_ports.py`
- Re-scaffolds all existing generated apps
- Applies correct PORT allocations and PROJECT_NAME
- Creates .env files from .env.example

**Usage**:
```bash
python scripts/fix_generated_app_ports.py
```

### 2. Check Port Allocations
`scripts/check_port_allocations.py`
- Displays all port allocations from database
- Checks for conflicts
- Useful for debugging

**Usage**:
```bash
python scripts/check_port_allocations.py
```

## Testing Performed

### 1. Port Allocation Test
- ✅ Generated 6 apps (3 per model)
- ✅ All got unique ports
- ✅ No database conflicts

### 2. Container Naming Test
- ✅ Started containers for multiple apps
- ✅ Each got unique names
- ✅ Docker names matched PROJECT_NAME from .env

### 3. Concurrent Start Test
- ✅ Started multiple apps simultaneously
- ✅ No port bind failures
- ✅ All containers healthy

## Files Modified

1. `src/app/services/simple_generation_service.py` - Port allocation + PROJECT_NAME + .env creation
2. `misc/scaffolding/react-flask/.env.example` - Template with {{PROJECT_NAME}} placeholder

## Scripts Created

1. `scripts/fix_generated_app_ports.py` - Bulk fix utility
2. `scripts/check_port_allocations.py` - Audit utility

## Documentation Created

1. `docs/fixes/PORT_ALLOCATION_FIX.md` - Detailed technical documentation

## Migration for Existing Apps

For apps generated before this fix:
```bash
# Option 1: Fix all apps at once
python scripts/fix_generated_app_ports.py

# Option 2: Clean up and regenerate
1. Stop and remove all containers
2. Delete generated apps
3. Regenerate using the wizard
```

## Next Steps

1. **Test in Production**: Generate new samples via web UI
2. **Monitor Logs**: Check for any port/naming issues
3. **Update Tests**: Add integration tests for port allocation
4. **Documentation**: Update user-facing docs if needed

## Status: ✅ COMPLETE

All issues have been fixed and tested. The sample generation system now properly:
- Allocates unique ports per model+app combination
- Generates unique container names
- Creates .env files automatically
- Prevents all port and naming conflicts
