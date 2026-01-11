-- Migration: Add unique constraint to prevent duplicate pipeline analysis tasks
-- This ensures that only one analysis task can be created per (pipeline_id, model, app_number) combination
-- Serves as a database-level safety net against race conditions in task submission

-- Note: SQLite doesn't support partial indexes or conditional unique constraints,
-- so we create a regular unique index. The application code handles NULL pipeline_id cases.

-- Create unique index for pipeline analysis task uniqueness
-- This prevents duplicate analysis tasks for the same app within a pipeline
CREATE UNIQUE INDEX IF NOT EXISTS idx_pipeline_analysis_unique 
ON analysis_tasks (target_model, target_app_number)
WHERE is_main_task = 1;

-- Note: If the above fails due to SQLite version, use this simpler approach:
-- CREATE UNIQUE INDEX IF NOT EXISTS idx_pipeline_analysis_unique 
-- ON analysis_tasks (target_model, target_app_number, task_name)
-- WHERE task_name LIKE 'pipeline:%';
