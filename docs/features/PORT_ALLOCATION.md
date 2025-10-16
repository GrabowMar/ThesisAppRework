# Port Allocation System
## Centralized Port Management for Generated Applications

### Overview

The port allocation system ensures that every generated application receives unique backend and frontend ports. This prevents conflicts and enables multiple models and applications to run simultaneously without port collisions.

### Key Features

- **Centralized Management**: Single source of truth for all port allocations
- **Automatic Allocation**: Dynamically finds the next available port pair
- **Conflict Prevention**: Database-backed allocation prevents race conditions
- **Pre-configuration Support**: Loads existing ports from `port_config.json`
- **Thread-Safe**: Atomic database operations ensure consistency

### Architecture

#### Core Service: `PortAllocationService`

Located in `src/app/services/port_allocation_service.py`, this service provides:

1. **Port Allocation**: `get_or_allocate_ports(model_name, app_num)` - Main entry point
2. **Conflict Detection**: `check_port_conflicts()` - Validates no duplicate ports
3. **Port Release**: `release_ports(model_name, app_num)` - Frees ports for reuse
4. **Statistics**: `get_all_allocations()` - Lists all current allocations

#### Database Model: `PortConfiguration`

Stores port allocations in the database with these fields:

```python
model: str              # Model name (e.g., "openai_gpt-4")
app_num: int           # Application number (1-based)
backend_port: int      # Unique backend port (5001+)
frontend_port: int     # Unique frontend port (8001+)
is_available: bool     # Availability flag
```

Unique constraint: `(model, app_num)` ensures one allocation per model/app pair.

### Port Allocation Strategy

1. **Check Database**: First checks if ports already exist for model/app
2. **Load from JSON**: Reads pre-configured ports from `misc/port_config.json`
3. **Dynamic Allocation**: Finds next free port pair if not found
4. **Register**: Saves allocation to database for future lookups

### Port Ranges

- **Backend Ports**: Start at 5001, increment by 2
- **Frontend Ports**: Start at 8001, increment by 2
- **Maximum Port**: 65535 (standard limit)

**Automatic Allocation**: Ports are allocated dynamically when an app is created. No hardcoding needed!

Example allocations (generated automatically):
```
model_a/app1:  backend=5001, frontend=8001
model_a/app2:  backend=5003, frontend=8003
model_b/app1:  backend=5005, frontend=8005
model_c/app1:  backend=5007, frontend=8007
```

### Integration Points

The port allocation service is integrated throughout the codebase:

#### 1. Sample Generation Service (`sample_generation_service.py`)

- **PortAllocator**: Uses centralized service for all port lookups
- **ProjectOrganizer**: Gets ports when scaffolding app directories

```python
from app.services.port_allocation_service import get_port_allocation_service

# Service is automatically used by ProjectOrganizer when apps are created
# You typically don't need to call this directly - it happens automatically!
service = get_port_allocation_service()
port_pair = service.get_or_allocate_ports(model_name, app_number)
print(f"Backend: {port_pair.backend}, Frontend: {port_pair.frontend}")
```

#### 2. App Scaffolding Service (`app_scaffolding_service.py`)

Uses centralized service in `get_app_ports()` method for scaffold generation.

#### 3. Port Resolution (`utils/port_resolution.py`)

Fallback resolution logic uses database-backed allocations as primary source.

### Management Tools

#### CLI: `scripts/port_manager.py`

Utility script for managing port allocations:

```bash
# List all allocations
python scripts/port_manager.py list

# Check for conflicts
python scripts/port_manager.py check

# Show statistics
python scripts/port_manager.py stats

# Release a specific allocation
python scripts/port_manager.py release openai_gpt-4 1
```

### How It Works

The system is **fully automatic** - no configuration or hardcoding required:

1. **App Creation**: When `_scaffold_if_needed(model_name, app_num)` is called
2. **Port Lookup**: System checks if ports exist for this model/app
3. **Auto-Allocation**: If not found, next free port pair is allocated
4. **Database Persistence**: Allocation is saved automatically
5. **Template Substitution**: Ports are injected into config files

**Zero Configuration**: Just create apps and ports are handled automatically!

The previous system:
- ❌ Only used app number (ignored model)
- ❌ All models' app1 got 5001/8001

The new system:
- ✅ Automatic allocation per model/app
- ✅ Database-backed persistence
- ✅ Dynamic - works with ANY model

### Testing

Test script: `test_port_allocation.py`

```bash
python test_port_allocation.py
```

Validates:
- Unique port assignment per model/app
- No conflicts between allocations
- Proper database persistence
- Service API correctness

### Best Practices

1. **Always use the service**: Never calculate ports manually
2. **Check conflicts regularly**: Run `port_manager.py check` before deployments
3. **Pre-configure for production**: Use `port_config.json` for stable assignments
4. **Monitor allocations**: Use `port_manager.py stats` to track usage
5. **Clean up unused ports**: Release ports when apps are removed

### Troubleshooting

#### All apps getting same ports (5001/8001)

**Cause**: Old code path bypassing centralized service

**Solution**: Ensure all services import and use `get_port_allocation_service()`

#### Port conflicts after generation

**Cause**: Race condition or stale cache

**Solution**: 
```bash
python scripts/port_manager.py check
python scripts/port_manager.py list
```

#### Ports not persisting

**Cause**: Database transaction not committed

**Solution**: Check `db.session.commit()` in service code

### API Reference

#### `PortAllocationService`

```python
class PortAllocationService:
    def get_or_allocate_ports(model_name: str, app_num: int) -> PortPair
    def release_ports(model_name: str, app_num: int) -> bool
    def check_port_conflicts() -> List[str]
    def get_all_allocations() -> List[Dict[str, Any]]
```

#### `PortPair`

```python
@dataclass
class PortPair:
    backend: int
    frontend: int
    model: str
    app_num: int
```

### Future Enhancements

- [ ] Port pool management (reserve ranges per model)
- [ ] Automatic cleanup of orphaned allocations
- [ ] Port usage metrics and analytics
- [ ] REST API endpoint for external tools
- [ ] Docker port mapping validation
- [ ] Automatic port conflict resolution

### Related Documentation

- [Project Structure](PROJECT_STRUCTURE.md)
- [Development Guide](DEVELOPMENT_GUIDE.md)
- [Sample Generator Rework](SAMPLE_GENERATOR_REWORK.md)
