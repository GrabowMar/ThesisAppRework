# Maintenance Service - Quick Reference

## What It Does
Automatically prevents database-filesystem desynchronization by cleaning up:
- ✅ Orphan app records (database entries without filesystem directories)
- ✅ Orphan tasks (tasks targeting non-existent apps)
- ✅ Stuck tasks (RUNNING/PENDING for too long)
- ✅ Old terminal tasks (COMPLETED/FAILED/CANCELLED older than retention period)

## How It Works
- **Runs automatically** on Flask app startup
- **Initial cleanup** executes immediately (prevents startup issues)
- **Periodic cleanup** runs every 1 hour (configurable)
- **Silent operation** logs events, no UI notifications
- **Zero maintenance** required - fully automated

## Configuration

### Default Behavior
```bash
# No configuration needed - runs with sensible defaults:
# - Interval: 1 hour
# - Retention: 30 days
# - Stuck timeout: 60 minutes
# - All cleanup tasks enabled

python src/main.py
```

### Custom Configuration
```bash
# Run cleanup every 30 minutes
MAINTENANCE_INTERVAL_SECONDS=1800 python src/main.py

# Keep tasks for only 7 days
MAINTENANCE_TASK_RETENTION_DAYS=7 python src/main.py

# Mark tasks as stuck after 30 minutes
MAINTENANCE_STUCK_TASK_TIMEOUT_MINUTES=30 python src/main.py

# Disable maintenance (not recommended)
MAINTENANCE_ENABLED=false python src/main.py
```

## Monitoring

### Check Status Programmatically
```python
from app.services.maintenance_service import get_maintenance_service

service = get_maintenance_service()
status = service.get_status()

print(f"Runs: {status['stats']['runs']}")
print(f"Orphan apps cleaned: {status['stats']['orphan_apps_cleaned']}")
print(f"Orphan tasks cleaned: {status['stats']['orphan_tasks_cleaned']}")
print(f"Stuck tasks cleaned: {status['stats']['stuck_tasks_cleaned']}")
print(f"Old tasks cleaned: {status['stats']['old_tasks_cleaned']}")
print(f"Errors: {status['stats']['errors']}")
```

### Check Logs
```bash
# Look for maintenance activity in app logs
grep -i "maintenance" logs/app.log

# Windows PowerShell
Select-String -Pattern "maintenance" -Path logs\app.log
```

## What Gets Logged

### Normal Operation (No Cleanup Needed)
```
INFO  maintenance_thread  Maintenance service daemon thread started
INFO  maintenance          Maintenance service started (interval=3600 seconds = 1h)
INFO  maintenance_thread  Running initial maintenance on startup...
INFO  maintenance_thread  Starting maintenance run...
DEBUG maintenance_thread  Maintenance completed in 0.2s: no cleanup needed
```

### When Cleanup Happens
```
INFO  maintenance_thread  Starting maintenance run...
INFO  maintenance_thread  Found 2 orphan app records (database records without filesystem directories)
DEBUG maintenance_thread    Deleting orphan app: openai_codex-mini/app4658
INFO  maintenance_thread  Cleaned up 2 orphan app records
INFO  maintenance_thread  Found 5 orphan tasks (targeting non-existent apps)
INFO  maintenance_thread  Cancelled 5 orphan tasks
INFO  maintenance_thread  Found 3 stuck tasks (2 RUNNING, 1 PENDING) older than 60 minutes
INFO  maintenance_thread  Cleaned up 3 stuck tasks
INFO  maintenance_thread  Maintenance completed in 0.5s: orphan_apps=2, orphan_tasks=5, stuck_tasks=3, old_tasks=0
```

## Important Notes

### What Gets Cleaned
✅ Database records for deleted apps  
✅ Tasks for non-existent apps  
✅ Tasks stuck in RUNNING/PENDING  
✅ Old terminal tasks (COMPLETED/FAILED/CANCELLED)

### What Does NOT Get Cleaned
❌ Result files in `results/{model}/app{N}/task_{id}/` (preserved per user requirement)  
❌ Active apps and their tasks  
❌ Recent tasks within retention period  
❌ Tasks making normal progress

### When Cleanup Runs
- ✅ **Startup**: Immediate cleanup on app initialization
- ✅ **Periodic**: Every 1 hour (default) while app runs
- ❌ **Not on demand**: No manual trigger endpoint (yet)

## Troubleshooting

### Service Not Running
```python
# Check if service initialized
from app.services.maintenance_service import get_maintenance_service
service = get_maintenance_service()
if not service:
    print("Service not initialized - check factory.py imports")
```

### Too Aggressive Cleanup
```bash
# Increase retention period (e.g., 90 days)
MAINTENANCE_TASK_RETENTION_DAYS=90 python src/main.py

# Increase stuck task timeout (e.g., 2 hours)
MAINTENANCE_STUCK_TASK_TIMEOUT_MINUTES=120 python src/main.py
```

### Not Cleaning Up Fast Enough
```bash
# Run more frequently (e.g., every 15 minutes)
MAINTENANCE_INTERVAL_SECONDS=900 python src/main.py
```

### High Error Count
```python
# Check error statistics
service = get_maintenance_service()
status = service.get_status()
if status['stats']['errors'] > 0:
    # Check logs for stack traces
    print("Review logs/app.log for error details")
```

## Files Modified

| File | Purpose |
|------|---------|
| `src/app/services/maintenance_service.py` | Main service implementation |
| `src/app/factory.py` | Service initialization |
| `src/config/settings.py` | Configuration variables |
| `MAINTENANCE_SERVICE_IMPLEMENTATION.md` | Full documentation |

## Test Scripts

| Script | Purpose |
|--------|---------|
| `test_maintenance.py` | Quick functionality test |
| `verify_maintenance_implementation.py` | Full verification suite |

## Need Help?

See full documentation: `MAINTENANCE_SERVICE_IMPLEMENTATION.md`
