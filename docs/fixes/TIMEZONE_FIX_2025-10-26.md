# Analysis Task Timezone Fix

## Problem
Analysis tasks were failing with the error: **"can't subtract offset-naive and offset-aware datetimes"**

This error occurred when trying to calculate `actual_duration` by subtracting `started_at` from `completed_at` timestamps.

## Root Cause
The codebase had inconsistent datetime usage:
- `task_execution_service.py` used `datetime.utcnow()` which creates **naive** (timezone-unaware) datetime objects
- Other parts of the codebase (like Celery tasks) used `datetime.now(timezone.utc)` which creates **timezone-aware** datetime objects
- When Python tries to subtract a naive datetime from an aware datetime (or vice versa), it raises a TypeError

## Solution
Fixed all datetime assignments in `task_execution_service.py` to use timezone-aware datetimes consistently:

### Changes Made

1. **Import timezone**: Added `from datetime import datetime, timezone` to ensure timezone support

2. **Replaced all `datetime.utcnow()` calls** with `datetime.now(timezone.utc)`
   - This ensures all timestamps created in the task execution service are timezone-aware (UTC)

3. **Added defensive handling for duration calculation**:
   ```python
   # Ensure both timestamps are timezone-aware before subtraction
   start = task_db.started_at if task_db.started_at.tzinfo else task_db.started_at.replace(tzinfo=timezone.utc)
   end = task_db.completed_at if task_db.completed_at.tzinfo else task_db.completed_at.replace(tzinfo=timezone.utc)
   task_db.actual_duration = (end - start).total_seconds()
   ```
   - This handles cases where database might have mixed naive/aware timestamps from before the fix

### Files Modified
- `src/app/services/task_execution_service.py`: Main fix
  - All `datetime.utcnow()` → `datetime.now(timezone.utc)`
  - Added timezone-aware duration calculations at 3 locations

## Verification
1. Created test script (`test_datetime_fix.py`) that creates new tasks and verifies no timezone errors occur
2. Test passed: New tasks complete successfully with duration calculated correctly
3. Cleared legacy error messages from 12 affected tasks using `clear_timezone_errors.py`

## Results
- ✅ New analysis tasks execute without timezone errors
- ✅ Duration calculations work correctly
- ✅ Subtasks execute and report status properly
- ✅ Analysis results are now properly saved and displayed

## Prevention
Going forward, always use timezone-aware datetimes in Python code:
- **Preferred**: `datetime.now(timezone.utc)` for current UTC time
- **Avoid**: `datetime.utcnow()` (creates naive datetimes)
- **For specific timezones**: `datetime.now(timezone)` with appropriate timezone object

## Testing
To verify the fix works:
```bash
python test_datetime_fix.py
```

Expected output: "✅ SUCCESS: No timezone error!"
