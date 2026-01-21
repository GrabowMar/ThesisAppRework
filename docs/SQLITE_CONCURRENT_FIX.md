# SQLite Concurrent Access Fix

## Problem

**Error**: `sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) database is locked`

This error occurred because the application has multiple background services (TaskExecutionService, MaintenanceService, PipelineExecutionService) running in separate threads, all accessing the same SQLite database concurrently. SQLite's default configuration doesn't handle concurrent writes well, leading to database lock errors.

## Solution

Applied two-part fix in [src/app/factory.py](../src/app/factory.py):

### 1. SQLAlchemy Engine Options (Line ~135)

Added connection pool and timeout settings:

```python
engine_options = {
    'connect_args': {
        'timeout': 30,  # Wait up to 30 seconds for locks
        'check_same_thread': False,  # Allow multi-thread access
    },
    'pool_size': 10,
    'max_overflow': 20,
    'pool_pre_ping': True,
    'pool_recycle': 3600,
}
```

**Key changes:**
- **timeout=30**: Wait 30 seconds instead of failing immediately on lock
- **check_same_thread=False**: Allow database access from multiple threads
- **pool_size/max_overflow**: Connection pooling to reduce lock contention
- **pool_pre_ping**: Verify connections before use (prevents stale connections)

### 2. WAL Mode Enabled (Line ~265)

Enabled Write-Ahead Logging mode for better concurrent access:

```python
with db.engine.connect() as conn:
    conn.execute(text("PRAGMA journal_mode=WAL"))
    conn.execute(text("PRAGMA synchronous=NORMAL"))
    conn.execute(text("PRAGMA busy_timeout=30000"))
    conn.commit()
```

**Benefits:**
- **WAL mode**: Readers don't block writers, writers don't block readers
- **synchronous=NORMAL**: Faster writes while maintaining safety
- **busy_timeout**: Database-level 30-second timeout for lock operations

## Why WAL Mode?

SQLite's default **DELETE** journal mode blocks all readers during writes. **WAL mode** allows:
- Multiple readers simultaneously
- Readers concurrent with a single writer
- Better performance under concurrent access

Trade-offs:
- Slightly more disk I/O (acceptable for this use case)
- Creates `-wal` and `-shm` files alongside `.db` file
- Still limited to one writer at a time (but with better queuing)

## Verification

After restarting the Flask app:

1. Check logs for: `SQLite WAL mode enabled for concurrent access`
2. Verify database files: `thesis_app.db`, `thesis_app.db-wal`, `thesis_app.db-shm`
3. No more `database is locked` errors during concurrent operations

## When to Migrate to PostgreSQL

SQLite with WAL mode handles moderate concurrency well, but consider PostgreSQL if:
- Frequent high-volume writes across multiple services
- Need for true concurrent writes (SQLite: 1 writer, PostgreSQL: many writers)
- Database size exceeds 100GB
- Require advanced features (replication, stored procedures, etc.)

For this application (background services + web requests), SQLite with WAL is sufficient.

## Related Files

- [src/app/factory.py](../src/app/factory.py) - Database configuration
- [src/app/services/task_execution_service.py](../src/app/services/task_execution_service.py) - Background task executor
- [src/app/services/maintenance_service.py](../src/app/services/maintenance_service.py) - Maintenance service
- [docs/BACKGROUND_SERVICES.md](./BACKGROUND_SERVICES.md) - Background services documentation

## References

- [SQLite WAL Mode](https://www.sqlite.org/wal.html)
- [SQLAlchemy Engine Configuration](https://docs.sqlalchemy.org/en/20/core/engines.html)
- [SQLite Concurrent Access Patterns](https://www.sqlite.org/threadsafe.html)
