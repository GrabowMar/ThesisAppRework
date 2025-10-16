# Port Allocation System - Key Points

## Fully Automatic ✅

The port allocation system is **completely automatic** and requires **zero configuration**:

### When You Create an App

```python
# When this is called during app generation:
app_dir = self._scaffold_if_needed(model_name, app_num)

# Ports are automatically allocated:
# 1. Check database for existing allocation
# 2. If not found, get next available port pair
# 3. Save to database
# 4. Return ports for template substitution
```

### No Hardcoding Needed

The system works with **ANY model name**:
- ✅ Works with existing models in the database
- ✅ Works with brand new models never seen before
- ✅ No configuration files to update
- ✅ No model lists to maintain

### Example Flow

```
User creates app for "new_model_xyz" (never seen before)
    ↓
System calls _scaffold_if_needed("new_model_xyz", 1)
    ↓
System calls _compute_ports("new_model_xyz", 1)
    ↓
PortAllocationService.get_or_allocate_ports("new_model_xyz", 1)
    ↓
Database check: No existing allocation found
    ↓
Find next free port pair: backend=5XXX, frontend=8XXX
    ↓
Save to database with unique constraints
    ↓
Return PortPair(backend=5XXX, frontend=8XXX)
    ↓
Ports used in template substitution
    ↓
App created with unique ports ✅
```

## Key Principles

1. **Automatic**: Happens during app creation, not separately
2. **Dynamic**: Works with any model name
3. **Persistent**: Saved to database immediately
4. **Safe**: Unique constraints prevent conflicts
5. **Transparent**: Check allocations anytime with `port_manager.py`

## What You Don't Need to Do

- ❌ Configure port ranges per model
- ❌ Maintain lists of models
- ❌ Update port configuration files
- ❌ Manually assign ports
- ❌ Check for conflicts yourself

## What Happens Automatically

- ✅ Port allocation on first use
- ✅ Database persistence
- ✅ Conflict prevention
- ✅ Next available port discovery
- ✅ Template substitution

## Management (Optional)

You can inspect and manage ports if needed:

```bash
# See what's allocated
python scripts/port_manager.py stats

# Check for any issues
python scripts/port_manager.py check

# List all allocations
python scripts/port_manager.py list

# Release ports (if removing an app)
python scripts/port_manager.py release model_name app_num
```

But for normal usage, **you don't need to do anything** - it just works!

## Summary

**Before**: Ports hardcoded, conflicts common, manual management
**After**: Fully automatic, no conflicts, zero configuration

The system is designed to be invisible - you create apps and ports are handled automatically.
