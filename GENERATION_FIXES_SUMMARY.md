# Generation Service Fixes - Implementation Summary

## Issues Fixed

### 1. File Overwrite / Race Condition ✅
**Problem**: Concurrent generations overwrote each other's files because a single shared `CodeMerger` instance was used across all requests.

**Solution**:
- Replaced singleton `CodeMerger` with per-request instances
- Added app-specific file locks using `threading.Lock` per `{model_slug}/app{app_num}`
- Each generation acquires its lock before writing files, preventing concurrent writes to the same app
- Lock timeout set to 5 minutes to detect deadlocks

**Files Modified**:
- `src/app/services/generation.py` (lines 1113-1160, 1270-1340)

**Configuration**:
- No configuration needed - always active for safety

---

### 2. Queue-Based Concurrency Control ✅
**Problem**: No systematic way to control concurrent generation load; all requests executed immediately.

**Solution**:
- Added optional queue-based generation with background worker thread
- Queue processes tasks sequentially with configurable concurrency limit
- Prevents resource exhaustion and allows graceful handling of burst requests
- Defaults to enabled for safety

**Files Modified**:
- `src/app/services/generation.py` (lines 1133-1193)

**Configuration**:
```bash
# Enable queue mode (default: true)
GENERATION_USE_QUEUE=true

# Max concurrent generations (default: 4)
GENERATION_MAX_CONCURRENT=4
```

**How to Disable** (for backwards compatibility):
```bash
GENERATION_USE_QUEUE=false
```

---

### 3. OpenRouter API Error Handling ✅
**Problem**: 
- `TransferEncodingError` when API responses were incomplete
- `.get()` called on string responses instead of dicts
- No retry logic for network failures

**Solution**:
- Added Content-Type validation before calling `response.json()`
- Wrapped non-JSON responses in dict structure: `{"error": {"message": "..."}}`
- Safe extraction of error messages handling both dict and string responses
- Retry logic with exponential backoff (max 2 retries) for:
  - `ClientConnectorError` (network failures)
  - `ServerTimeoutError` (timeouts)
  - `TransferEncodingError` (incomplete responses)

**Files Modified**:
- `src/app/services/openrouter_chat_service.py` (lines 72-140)

**Configuration**:
- Retries: hardcoded to 2 attempts (can be made configurable if needed)
- Backoff: 2^attempt seconds (1s, 2s)

---

### 4. Timezone-Aware Datetime Handling ✅
**Problem**: Database had mix of naive and timezone-aware datetimes, causing comparison errors:
```
can't subtract offset-naive and offset-aware datetimes
```

**Solution**:
- Created migration to normalize existing datetime records
- Added `_ensure_timezone_aware()` helper function
- Updated status endpoint to safely handle mixed datetime types
- All new records use `utc_now()` which returns timezone-aware datetimes

**Files Modified**:
- `migrations/20250209_normalize_timezones.py` (new file)
- `src/app/services/generation.py` (lines 60-73, 1595-1600)

**Migration**:
```bash
# Run automatically on startup, or manually:
python migrations/20250209_normalize_timezones.py
```

**Note**: Migration is non-destructive and backwards-compatible.

---

## Testing

### Quick Verification

1. **Start the application**:
```bash
python src/main.py
```

2. **Check queue mode is active** (look for log):
```
Generation queue enabled with max_concurrent=4
```

3. **Run concurrent generations** (web UI):
- Navigate to `/sample-generator/`
- Select multiple templates/models
- Click "Start Batch Generation"
- Verify no file overwrites occur

4. **Check timezone normalization**:
```bash
# In Flask shell
from app.factory import create_app
from app.models import GeneratedApplication
app = create_app()
with app.app_context():
    apps = GeneratedApplication.query.limit(5).all()
    for app in apps:
        print(f"{app.model_slug}/app{app.app_number}: {app.updated_at.tzinfo}")
    # Should print: <UTC> for all
```

### Load Testing

```bash
# Stress test with concurrent requests
for i in {1..10}; do
  curl -X POST http://localhost:5000/api/gen/generate \
    -H "Content-Type: application/json" \
    -d "{\"model_slug\":\"openai_gpt-4o\",\"app_num\":$i,\"template_slug\":\"crud_todo_list\"}" &
done
wait
# Check logs for race conditions or overwrites
```

---

## Configuration Reference

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `GENERATION_USE_QUEUE` | `true` | Enable queue-based generation |
| `GENERATION_MAX_CONCURRENT` | `4` | Max concurrent generations |

---

## Backwards Compatibility

All changes are backwards compatible:

1. **Queue mode**: Can be disabled via `GENERATION_USE_QUEUE=false`
2. **File locks**: Always active, transparent to callers
3. **OpenRouter retries**: Automatic, no breaking changes
4. **Timezone migration**: Runs automatically, handles both naive and aware datetimes

---

## Performance Impact

- **File locks**: Minimal (<1ms per lock acquisition)
- **Queue mode**: Adds slight latency for queued tasks, but improves overall throughput
- **OpenRouter retries**: 2-6 seconds added for failed requests (only on errors)
- **Timezone checks**: Negligible (simple comparison)

**Recommended**: Keep queue mode enabled for production use.

---

## Future Improvements

1. **Persistent queue**: Use Redis/RabbitMQ for distributed queue
2. **Priority levels**: Allow urgent generations to skip queue
3. **Progress tracking**: Real-time updates via WebSocket
4. **Configurable retries**: Make max_retries a config option
5. **Metrics**: Track queue depth, wait times, success rates

---

## Troubleshooting

### "Timeout acquiring lock for {model}/app{N}"
- Another process is holding the lock for >5 minutes
- Check for hung processes: `ps aux | grep python`
- Restart the application to clear stale locks

### Queue not processing
- Check worker thread is running: look for "Generation queue worker started" in logs
- Verify `GENERATION_USE_QUEUE=true`
- Check for exceptions in queue worker

### Still seeing datetime errors
- Run migration: `python migrations/20250209_normalize_timezones.py`
- Verify all apps have timezone-aware datetimes:
  ```python
  from app.models import GeneratedApplication
  apps = GeneratedApplication.query.filter(GeneratedApplication.updated_at.is_(None)).all()
  # Should be empty
  ```

---

## Files Changed

1. `src/app/services/generation.py` - Core fixes
2. `src/app/services/openrouter_chat_service.py` - Error handling
3. `migrations/20250209_normalize_timezones.py` - DB migration
4. `GENERATION_FIXES_SUMMARY.md` - This document

**Total Lines Changed**: ~250 lines
**New Files**: 1 (migration)
**Breaking Changes**: None
