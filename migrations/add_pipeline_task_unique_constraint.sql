-- Migration: Add unique constraint to prevent duplicate analysis tasks per pipeline
-- Created: 2026-01-10
-- Purpose: Prevent race condition duplicates in pipeline analysis task creation

-- Add unique constraint on (pipeline_execution_id, target_model, target_app_number)
-- This ensures each model/app combination can only have ONE analysis task per pipeline

-- First, we need to add a pipeline_execution_id column to analysis_tasks if it doesn't exist
-- (assuming it exists based on the codebase structure)

-- Create unique index to enforce constraint at database level
CREATE UNIQUE INDEX IF NOT EXISTS idx_analysis_task_pipeline_unique
ON analysis_tasks (
    -- We need to extract pipeline_id from custom_options JSON
    -- This requires PostgreSQL JSON operators
    CAST(custom_options->>'pipeline_id' AS TEXT),
    target_model,
    target_app_number
)
WHERE
    custom_options IS NOT NULL
    AND custom_options->>'pipeline_id' IS NOT NULL
    AND custom_options->>'source' = 'automation_pipeline';

-- For SQLite compatibility (if using SQLite), we'd need a different approach:
-- CREATE UNIQUE INDEX IF NOT EXISTS idx_analysis_task_pipeline_unique
-- ON analysis_tasks (
--     json_extract(custom_options, '$.pipeline_id'),
--     target_model,
--     target_app_number
-- )
-- WHERE
--     json_extract(custom_options, '$.pipeline_id') IS NOT NULL
--     AND json_extract(custom_options, '$.source') = 'automation_pipeline';

-- Note: This migration should be reviewed and adjusted based on actual database type
-- Run with: psql -d your_database -f migrations/add_pipeline_task_unique_constraint.sql
