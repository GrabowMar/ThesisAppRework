# Database Table Cleanup Guide

## Overview
After removing unused database models from the codebase, you need to drop the corresponding tables from your database.

## Tables to Drop

The following tables are orphaned (no longer have model definitions):

1. `batch_queues` - Batch job queue entries
2. `batch_dependencies` - Batch job dependencies
3. `batch_schedules` - Recurring batch schedules
4. `batch_resource_usage` - Batch resource metrics
5. `batch_templates` - Batch configuration templates
6. `test_results` - Test result storage
7. `event_logs` - System event logs
8. `requirement_matches_cache` - Requirements analysis cache

## Method 1: Automated Script (Recommended)

Use the provided script to safely drop tables:

```powershell
# Dry run first (see what would be dropped)
.venv\Scripts\python.exe scripts\drop_unused_tables.py --dry-run

# Actually drop the tables
.venv\Scripts\python.exe scripts\drop_unused_tables.py
```

The script will:
- Check which tables exist
- Show row counts (warn if data present)
- Ask for confirmation before dropping
- Drop tables with CASCADE to handle any foreign keys

## Method 2: Manual SQL

If you prefer to drop tables manually:

### SQLite (Development)

```sql
DROP TABLE IF EXISTS batch_queues;
DROP TABLE IF EXISTS batch_dependencies;
DROP TABLE IF EXISTS batch_schedules;
DROP TABLE IF EXISTS batch_resource_usage;
DROP TABLE IF EXISTS batch_templates;
DROP TABLE IF EXISTS test_results;
DROP TABLE IF EXISTS event_logs;
DROP TABLE IF EXISTS requirement_matches_cache;
```

### PostgreSQL (Production)

```sql
DROP TABLE IF EXISTS batch_queues CASCADE;
DROP TABLE IF EXISTS batch_dependencies CASCADE;
DROP TABLE IF EXISTS batch_schedules CASCADE;
DROP TABLE IF EXISTS batch_resource_usage CASCADE;
DROP TABLE IF EXISTS batch_templates CASCADE;
DROP TABLE IF EXISTS test_results CASCADE;
DROP TABLE IF EXISTS event_logs CASCADE;
DROP TABLE IF EXISTS requirement_matches_cache CASCADE;
```

## Verification

After dropping tables, verify the cleanup:

```powershell
# Run verification script
.venv\Scripts\python.exe scripts\verify_cleanup.py
```

You should see:
- ✅ All verifications passed
- ✓ All removed models absent
- ✓ All kept models present

## Backup Recommendation

Before dropping any tables, create a backup:

### SQLite
```powershell
# Backup database file
Copy-Item src\instance\app.db src\instance\app.db.backup
```

### PostgreSQL
```bash
# Backup database
pg_dump -U username -d dbname > backup_before_cleanup.sql
```

## Rollback

If you need to restore removed models (not recommended):

1. Restore the backup database
2. Use git to restore the model files:
   ```powershell
   git checkout HEAD~1 -- src/app/models/batch.py
   git checkout HEAD~1 -- src/app/models/process.py
   git checkout HEAD~1 -- src/app/models/results_cache.py
   git checkout HEAD~1 -- src/app/models/__init__.py
   ```

## Post-Cleanup Steps

1. **Re-initialize database** (if starting fresh):
   ```powershell
   .venv\Scripts\python.exe src\init_db.py
   ```

2. **Run tests** to ensure nothing broke:
   ```powershell
   .venv\Scripts\python.exe -m pytest -q -m "not integration and not slow and not analyzer"
   ```

3. **Start the application** and verify it works:
   ```powershell
   .\start.ps1
   ```

## Troubleshooting

### "Table does not exist" errors
This is normal if tables were never created. The drop script handles this gracefully.

### Foreign key constraint errors
The script uses `CASCADE` which should handle foreign keys. If you still get errors:
1. Check if any custom foreign keys reference these tables
2. Drop those referencing tables first
3. Then drop the orphaned tables

### "Table has data" warnings
If tables contain data:
1. Export the data if needed for records
2. Confirm you want to delete it
3. Proceed with dropping

## Safety Features

The drop script includes:
- ✓ Dry-run mode to preview changes
- ✓ Row count display (warn if data present)
- ✓ Confirmation prompt before dropping
- ✓ CASCADE to handle foreign keys
- ✓ Error handling and rollback on failure

## Impact Assessment

After cleanup:
- **Database size**: May decrease depending on row counts
- **Query performance**: Slightly improved (fewer tables to track)
- **Schema clarity**: Much clearer (only used tables remain)
- **Maintenance**: Easier (no dead tables to manage)

---

**Note**: This cleanup is part of the code cleanup performed on 2024-10-14. See `CLEANUP_SUMMARY.md` for full details.
