# Task Cleanup Configuration Guide

## Overview

The system includes two mechanisms for cleaning up stuck or stale analysis tasks:

1. **Startup Cleanup** (`src/app/factory.py`) - Runs once when Flask app starts
2. **Maintenance Service** (`src/app/services/maintenance_service.py`) - Runs periodically (default: hourly)

Both have been configured with **conservative timeouts** to minimize false positives and avoid cancelling legitimate tasks.

---

## Key Changes (November 2025)

### Previous Behavior (AGGRESSIVE)
- ❌ 30-minute timeout for both RUNNING and PENDING tasks
- ❌ No grace period for recently created tasks
- ❌ Same cutoff for stuck processes vs queued tasks
- ❌ High risk of cancelling legitimate tasks during app restarts

### New Behavior (CONSERVATIVE)
- ✅ **2-hour timeout** for RUNNING tasks (very likely stuck after restart)
- ✅ **4-hour timeout** for PENDING tasks (allows for long queues)
- ✅ **5-minute grace period** - recently created tasks are never touched
- ✅ **Detailed logging** with timestamps and task ages
- ✅ **Opt-out via environment variable** for development

---

## Environment Variables

### Startup Cleanup Configuration

```bash
# Disable startup cleanup entirely (useful for development)
STARTUP_CLEANUP_ENABLED=false  # Default: true

# Timeout for RUNNING tasks (in minutes)
STARTUP_CLEANUP_RUNNING_TIMEOUT=120  # Default: 120 (2 hours)

# Timeout for PENDING tasks (in minutes)
STARTUP_CLEANUP_PENDING_TIMEOUT=240  # Default: 240 (4 hours)

# Grace period - skip tasks created within this window (in minutes)
STARTUP_CLEANUP_GRACE_PERIOD=5  # Default: 5 (5 minutes)
```

### Example Configurations

**Development** (disable cleanup):
```bash
STARTUP_CLEANUP_ENABLED=false
```

**Production** (default - conservative):
```bash
# No env vars needed - defaults are already conservative
```

**High-throughput** (longer queue times):
```bash
STARTUP_CLEANUP_RUNNING_TIMEOUT=180  # 3 hours
STARTUP_CLEANUP_PENDING_TIMEOUT=480  # 8 hours
STARTUP_CLEANUP_GRACE_PERIOD=10      # 10 minutes
```

**Aggressive cleanup** (legacy behavior - NOT recommended):
```bash
STARTUP_CLEANUP_RUNNING_TIMEOUT=30   # 30 minutes
STARTUP_CLEANUP_PENDING_TIMEOUT=30   # 30 minutes
STARTUP_CLEANUP_GRACE_PERIOD=0       # No grace period
```

---

## Maintenance Service Configuration

The maintenance service (`MaintenanceService`) runs periodically and uses the same conservative approach:

- **RUNNING tasks**: Cleaned up after **2 hours** of being stuck
- **PENDING tasks**: Cleaned up after **4 hours** of waiting
- **Grace period**: **5 minutes** - recently created tasks are always preserved

These are configured in `src/app/services/maintenance_service.py`:

```python
self.config = {
    'stuck_task_timeout_minutes': 120,       # 2 hours for RUNNING tasks
    'pending_task_timeout_minutes': 240,     # 4 hours for PENDING tasks
    'grace_period_minutes': 5,               # Skip recent tasks
}
```

To modify, edit the file directly or extend the class initialization.

---

## How Cleanup Works

### Startup Cleanup (factory.py)

Runs **once** when Flask app initializes:

```
1. Check if STARTUP_CLEANUP_ENABLED=true (default: yes)
2. Calculate cutoff times:
   - RUNNING cutoff = now - STARTUP_CLEANUP_RUNNING_TIMEOUT (default: 2h)
   - PENDING cutoff = now - STARTUP_CLEANUP_PENDING_TIMEOUT (default: 4h)
   - Grace cutoff = now - STARTUP_CLEANUP_GRACE_PERIOD (default: 5m)

3. Find stuck RUNNING tasks:
   - Status = RUNNING
   - started_at < RUNNING cutoff (>2 hours old)
   - started_at < grace cutoff (not created in last 5 minutes)
   → Mark as FAILED

4. Find old PENDING tasks:
   - Status = PENDING
   - created_at < PENDING cutoff (>4 hours old)
   - created_at < grace cutoff (not created in last 5 minutes)
   → Mark as CANCELLED

5. Log detailed information:
   - Task ID, creation/start time, age in minutes
   - Total counts by status
   - Applied timeout thresholds
```

### Maintenance Service (hourly)

Runs **periodically** (default: every hour) with same logic as startup cleanup.

---

## Logging Output

### Successful Cleanup (Stuck Tasks Found)

```
[INFO] Cleaned up stuck RUNNING task: task_abc123 (started: 2025-11-16 10:00:00, age: 150m)
[INFO] Cleaned up old PENDING task: task_xyz789 (created: 2025-11-16 06:00:00, age: 250m)
[INFO] Startup cleanup: processed 2 tasks (1 RUNNING, 1 PENDING) [timeouts: RUNNING>120m, PENDING>240m]
```

### No Cleanup Needed

```
[DEBUG] Startup cleanup: no stuck tasks found [timeouts: RUNNING>120m, PENDING>240m]
```

### Cleanup Disabled

```
[INFO] Startup task cleanup disabled via STARTUP_CLEANUP_ENABLED env var
```

---

## Task Error Messages

When a task is cleaned up, the `error_message` field is populated:

**RUNNING task (stuck)**:
```
Task stuck in RUNNING state for 150 minutes - cleaned up on app startup
```

**PENDING task (old)**:
```
Old pending task (250 minutes old) - cleaned up on app startup
```

**Maintenance service** (similar format):
```
Task stuck in RUNNING state for 150 minutes (timeout: 120m) - cleaned by maintenance
Task stuck in PENDING state for 250 minutes (timeout: 240m) - cleaned by maintenance
```

---

## Troubleshooting

### Tasks Are Being Cancelled Unexpectedly

**Symptom**: Tasks created just before app restart are cancelled on startup.

**Root Cause**: Tasks fell outside the grace period during restart window.

**Solutions**:
1. Increase grace period: `STARTUP_CLEANUP_GRACE_PERIOD=10` (10 minutes)
2. Increase PENDING timeout: `STARTUP_CLEANUP_PENDING_TIMEOUT=480` (8 hours)
3. Disable startup cleanup in dev: `STARTUP_CLEANUP_ENABLED=false`

### Tasks Are Stuck and Not Being Cleaned Up

**Symptom**: RUNNING tasks stuck for hours/days, not being cleaned up.

**Root Cause**: Timeouts are too long, or maintenance service not running.

**Solutions**:
1. Reduce timeouts: `STARTUP_CLEANUP_RUNNING_TIMEOUT=60` (1 hour)
2. Check maintenance service is running: `MaintenanceService._running` should be `True`
3. Manually trigger cleanup: `python scripts/fix_task_statuses.py`

### App Restarts Are Slow Due to Cleanup

**Symptom**: Flask app takes long time to start.

**Root Cause**: Large number of stuck tasks being processed.

**Solutions**:
1. Run manual cleanup before restart: `python scripts/fix_task_statuses.py`
2. Increase `task_retention_days` to auto-delete old tasks sooner
3. Disable startup cleanup temporarily: `STARTUP_CLEANUP_ENABLED=false`

---

## Migration Notes

### Upgrading from Legacy Behavior

If you had tasks configured with the old 30-minute timeout:

1. **No action required** - defaults are now conservative (2h/4h)
2. **To restore legacy behavior** (not recommended):
   ```bash
   STARTUP_CLEANUP_RUNNING_TIMEOUT=30
   STARTUP_CLEANUP_PENDING_TIMEOUT=30
   STARTUP_CLEANUP_GRACE_PERIOD=0
   ```
3. **Check logs** after first restart to see what was cleaned up

### Database Schema

No database migrations required - cleanup logic only updates existing fields:
- `status` (RUNNING → FAILED, PENDING → CANCELLED)
- `error_message` (populated with cleanup reason)
- `completed_at` (set to cleanup timestamp)

---

## Best Practices

1. **Development**: Disable startup cleanup to avoid interrupting active work
   ```bash
   STARTUP_CLEANUP_ENABLED=false
   ```

2. **Production**: Use defaults (conservative timeouts minimize false positives)
   ```bash
   # No env vars needed - defaults are production-ready
   ```

3. **High-throughput environments**: Increase PENDING timeout to allow for long queues
   ```bash
   STARTUP_CLEANUP_PENDING_TIMEOUT=480  # 8 hours
   ```

4. **Monitoring**: Check logs regularly for cleanup activity:
   ```bash
   grep "Startup cleanup" logs/app.log
   grep "Cleaned up.*PENDING" logs/app.log
   ```

5. **Recovery**: Use `scripts/fix_task_statuses.py` for manual intervention if needed

---

## Related Documentation

- [API Authentication Methods](./API_AUTH_AND_METHODS.md) - Task creation via API
- [Analyzer README](../analyzer/README.md) - Task execution workflow
- [Copilot Instructions](../.github/copilot-instructions.md) - System architecture overview

---

## Summary

The new cleanup configuration is **conservative by default**:

| Setting | Old Value | New Value | Rationale |
|---------|-----------|-----------|-----------|
| RUNNING timeout | 30 min | 120 min | Reduce false positives during restarts |
| PENDING timeout | 30 min | 240 min | Allow for long queues and slow startup |
| Grace period | 0 min | 5 min | Never touch recently created tasks |
| Opt-out | No | Yes | Development flexibility |
| Logging | Basic | Detailed | Easier debugging |

**Result**: Dramatically reduced false positives while still cleaning up genuinely stuck tasks.
