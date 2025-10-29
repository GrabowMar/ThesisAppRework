# Port Allocation Race Condition Fix

**Date:** October 28, 2025  
**Issue:** UNIQUE constraint failures during concurrent app generation

## Problem

When generating multiple apps concurrently (e.g., via the batch wizard), the port allocation service experienced race conditions that caused `UNIQUE constraint failed: port_configurations.backend_port` errors.

### Root Cause

The original `get_or_allocate_ports()` method had a time-of-check to time-of-use (TOCTOU) race condition:

1. Request A checks if ports are available → finds 5001/8001 free
2. Request B checks if ports are available → finds 5001/8001 free (same!)
3. Request A tries to register ports 5001/8001 → succeeds
4. Request B tries to register ports 5001/8001 → **UNIQUE constraint violation!**

### Manifestation

```
Port allocation failed for openai_gpt-4.1-mini-2025-04-14/app1. 
Ensure PortAllocationService is properly initialized. 
Error: (sqlite3.IntegrityError) UNIQUE constraint failed: port_configurations.backend_port
```

## Solution

### 1. Enhanced Race Condition Handling

Updated `_register_ports()` to gracefully handle duplicate allocations:

```python
def _register_ports(self, model_name: str, app_num: int, backend_port: int, frontend_port: int):
    # Check if allocation already exists
    existing_alloc = PortConfiguration.query.filter_by(
        model=model_name,
        app_num=app_num
    ).first()
    
    if existing_alloc:
        # Allocation already exists - this is OK, just use it
        logger.debug(f"Port allocation already exists...")
        return
    
    # Check for port conflicts
    conflict = PortConfiguration.query.filter(...).first()
    if conflict:
        raise ValueError(f"Port conflict: ...")
    
    # ... create new allocation with proper error handling
```

### 2. Retry Logic with Exponential Backoff

Added retry logic in `get_or_allocate_ports()`:

```python
max_retries = 5
retry_count = 0

while retry_count < max_retries:
    try:
        backend, frontend = self._find_next_free_ports()
        self._register_ports(model_name, app_num, backend, frontend)
        return PortPair(...)
    except ValueError as e:
        # Port conflict - retry with different ports
        retry_count += 1
        time.sleep(0.1 * retry_count)  # Exponential backoff
```

### 3. Improved Error Handling

- **ValueError**: Raised for port conflicts (retryable)
- **Other exceptions**: Database errors (non-retryable)
- **Duplicate UNIQUE errors**: Detected and handled gracefully

## Testing

Created comprehensive tests:

```bash
# Test duplicate allocations
python scripts/test_port_allocation.py

# List current allocations
python scripts/manage_ports.py list

# Check for conflicts
python scripts/manage_ports.py check

# Clean up orphaned allocations
python scripts/manage_ports.py cleanup
```

## Management Tools

### New Scripts

1. **`scripts/manage_ports.py`** - Port allocation management
   - `list` - Show all allocations
   - `check` - Check for conflicts
   - `cleanup [model]` - Remove orphaned allocations
   - `release <model> <app>` - Release specific allocation

2. **`scripts/test_port_allocation.py`** - Concurrency tests
   - Tests duplicate allocation handling
   - Tests concurrent different app allocations

### New Service Methods

- `cleanup_orphaned_allocations(model_name)` - Remove allocations for non-existent apps
- Enhanced error messages with retry information

## Prevention

### For Users

1. **Before batch generation**, check for existing allocations:
   ```bash
   python scripts/manage_ports.py list
   ```

2. **If regenerating apps**, either:
   - Delete the existing app directories first
   - Or use the cleanup command:
     ```bash
     python scripts/manage_ports.py cleanup openai_gpt-4.1-mini-2025-04-14
     ```

3. **After generation failures**, check for conflicts:
   ```bash
   python scripts/manage_ports.py check
   ```

### For Developers

1. **Always use `get_or_allocate_ports()`** - never manually create PortConfiguration records
2. **Handle ValueError exceptions** - they indicate retryable port conflicts
3. **Test concurrent scenarios** - use the test script before deploying changes

## SQLite Limitations

This implementation is optimized for SQLite which has limited locking capabilities:

- No `SELECT FOR UPDATE` with `NOWAIT` support
- No true row-level locking during transactions
- Retry-based approach is more reliable than database-level locks

For PostgreSQL deployments, this could be further optimized with proper row-level locking.

## Related Files

- `src/app/services/port_allocation_service.py` - Main service
- `src/app/models/core.py` - PortConfiguration model
- `scripts/manage_ports.py` - Management CLI
- `scripts/test_port_allocation.py` - Test suite

## Verification

The fix was verified with:

1. ✅ Unit tests for duplicate allocations
2. ✅ Unit tests for concurrent different app allocations  
3. ✅ Manual testing with existing allocations
4. ✅ Cleanup script validation

## Future Improvements

1. Add database migration to create composite index on (model, app_num)
2. Consider PostgreSQL-specific optimizations for production
3. Add Prometheus metrics for port allocation failures/retries
4. Implement port reservation system for planned batch generations
