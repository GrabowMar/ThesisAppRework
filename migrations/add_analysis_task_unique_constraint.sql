-- Migration: Add unique constraint to prevent duplicate analysis tasks
-- This constraint ensures only one task per (target_model, target_app_number, batch_id) combination
-- Date: 2026-01-11
-- 
-- NOTE: This migration has already been applied via scripts/migrate_analysis_task_constraint.py
-- This SQL file is kept for documentation purposes.

-- SQLite doesn't support adding constraints to existing tables directly,
-- so we need to recreate the table with the constraint

-- Step 1: Create new table with constraint
CREATE TABLE IF NOT EXISTS analysis_tasks_new (
    id INTEGER NOT NULL,
    task_id VARCHAR(100) NOT NULL,
    parent_task_id VARCHAR(100),
    is_main_task BOOLEAN,
    service_name VARCHAR(100),
    analyzer_config_id INTEGER NOT NULL,
    status VARCHAR(15),
    priority VARCHAR(6),
    target_model VARCHAR(200) NOT NULL,
    target_app_number INTEGER NOT NULL,
    target_path VARCHAR(500),
    task_name VARCHAR(200),
    description TEXT,
    task_metadata TEXT,
    progress_percentage FLOAT,
    current_step VARCHAR(200),
    total_steps INTEGER,
    completed_steps INTEGER,
    batch_id VARCHAR(100),
    assigned_worker VARCHAR(100),
    execution_context TEXT,
    result_summary TEXT,
    issues_found INTEGER,
    severity_breakdown TEXT,
    estimated_duration INTEGER,
    actual_duration FLOAT,
    queue_time FLOAT,
    error_message TEXT,
    retry_count INTEGER,
    max_retries INTEGER,
    created_at DATETIME NOT NULL,
    updated_at DATETIME,
    started_at DATETIME,
    completed_at DATETIME,
    PRIMARY KEY (id),
    UNIQUE (target_model, target_app_number, batch_id)
);

-- Step 2: Copy data from old table (ignoring duplicates)
INSERT OR IGNORE INTO analysis_tasks_new 
SELECT * FROM analysis_tasks;

-- Step 3: Drop old table
DROP TABLE IF EXISTS analysis_tasks;

-- Step 4: Rename new table
ALTER TABLE analysis_tasks_new RENAME TO analysis_tasks;

-- Step 5: Recreate indexes
CREATE INDEX IF NOT EXISTS ix_analysis_tasks_task_id ON analysis_tasks (task_id);
CREATE INDEX IF NOT EXISTS ix_analysis_tasks_status ON analysis_tasks (status);
CREATE INDEX IF NOT EXISTS ix_analysis_tasks_batch_id ON analysis_tasks (batch_id);
CREATE INDEX IF NOT EXISTS ix_analysis_tasks_parent_task_id ON analysis_tasks (parent_task_id);
CREATE INDEX IF NOT EXISTS ix_analysis_tasks_target_model ON analysis_tasks (target_model);
