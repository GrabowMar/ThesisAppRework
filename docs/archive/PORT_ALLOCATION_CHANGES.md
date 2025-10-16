# Port Allocation System Refactoring - File Changes

## Summary
Implemented a centralized port allocation system to prevent port conflicts when generating multiple AI model applications.

## New Files Created

### Core Implementation
- `src/app/services/port_allocation_service.py` - Centralized port allocation service with database-backed tracking

### Management & Testing
- `scripts/port_manager.py` - CLI tool for managing port allocations (list, check, stats, release)
- `test_port_allocation.py` - Test script to verify port allocation correctness

### Documentation
- `docs/PORT_ALLOCATION.md` - Comprehensive guide to the port allocation system
- `docs/PORT_ALLOCATION_REFACTORING.md` - Summary of changes and migration guide
- `docs/PORT_ALLOCATION_QUICK_REF.py` - Quick reference with code examples

## Modified Files

### Core Services
1. `src/app/services/sample_generation_service.py`
   - **ProjectOrganizer class**:
     - Updated `__init__()` to use centralized port service
     - Modified `_compute_ports()` to accept `model_name` parameter
     - Changed port calculation to use `port_service.get_or_allocate_ports()`
   
   - **PortAllocator class**:
     - Updated `__init__()` to use centralized port service
     - Simplified `get_ports_for_model_app()` to delegate to port service
     - Removed `_load_port_config()` and `_fallback_port()` methods
     - Updated `reload_configuration()` to recreate service instance

2. `src/app/services/app_scaffolding_service.py`
   - **AppScaffoldingService class**:
     - Added port service initialization in `__init__()`
     - Updated `get_app_ports()` signature to include `model_name` parameter
     - Changed port calculation to use centralized service
     - Updated `preview_generation()` to pass model name to `get_app_ports()`
     - Updated `_write_config_files()` to pass model name to `get_app_ports()`

### Documentation
3. `docs/ARCHITECTURE.md`
   - Added PortAllocationService to service responsibilities section

## Key Changes

### Before (Broken)
```python
def _compute_ports(self, app_num: int) -> tuple[int, int]:
    offset = (app_num - 1) * self.ports_per_app
    backend_port = self.base_backend_port + offset  # Always 5001 for app1
    frontend_port = self.base_frontend_port + offset  # Always 8001 for app1
    return backend_port, frontend_port
```

Result: All models' app1 got 5001/8001 (CONFLICT!)

### After (Fixed)
```python
def _compute_ports(self, model_name: str, app_num: int) -> tuple[int, int]:
    port_pair = self.port_service.get_or_allocate_ports(model_name, app_num)
    return port_pair.backend, port_pair.frontend
```

Result: Each model/app gets unique ports (NO CONFLICTS!)

## Database Schema
Uses existing `PortConfiguration` model with unique constraints:
- Unique constraint on `(model, app_num)` - one allocation per model/app
- Unique constraint on `backend_port` - no duplicate backend ports
- Unique constraint on `frontend_port` - no duplicate frontend ports

## Testing
Run tests to verify:
```bash
# Basic functionality test
python test_port_allocation.py

# Check for conflicts
python scripts/port_manager.py check

# View statistics
python scripts/port_manager.py stats

# Unit tests
pytest tests/test_smoke.py -v
```

## Migration Notes
- **Backward Compatible**: Existing port allocations preserved
- **Automatic Migration**: Service reads from existing `port_config.json`
- **No Breaking Changes**: All existing APIs maintained
- **Database-Backed**: Allocations persist across restarts

## Usage Examples

### Basic Usage
```python
from app.services.port_allocation_service import get_port_allocation_service

service = get_port_allocation_service()
port_pair = service.get_or_allocate_ports("openai_gpt-4", 1)
print(f"Backend: {port_pair.backend}, Frontend: {port_pair.frontend}")
```

### CLI Management
```bash
# List all allocations
python scripts/port_manager.py list

# Check for conflicts
python scripts/port_manager.py check

# Show statistics
python scripts/port_manager.py stats

# Release ports
python scripts/port_manager.py release openai_gpt-4 1
```

## Benefits
1. ✅ **Conflict Prevention** - Guaranteed unique ports per model/app
2. ✅ **Centralized Management** - Single source of truth
3. ✅ **Automatic Allocation** - No manual intervention needed
4. ✅ **Database-Backed** - Persistent across restarts
5. ✅ **Easy Debugging** - CLI tools for inspection
6. ✅ **Thread-Safe** - Atomic database operations

## Verification
After deployment, verify with:
```bash
# Check for any conflicts
python scripts/port_manager.py check

# Should output: ✅ No port conflicts found!
```

## References
- Implementation: `src/app/services/port_allocation_service.py`
- Full Guide: `docs/PORT_ALLOCATION.md`
- Migration Guide: `docs/PORT_ALLOCATION_REFACTORING.md`
- Quick Reference: `docs/PORT_ALLOCATION_QUICK_REF.py`
- Management Tool: `scripts/port_manager.py`
