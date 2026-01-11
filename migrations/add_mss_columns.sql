-- Database Migration: Add MSS (Model Selection Score) Columns
-- Date: 2026-01-10
-- Description: Adds Chapter 4 MSS-specific columns to model_benchmark_cache table

-- Chapter 4 MSS Benchmarks
ALTER TABLE model_benchmark_cache ADD COLUMN IF NOT EXISTS bfcl_score FLOAT;
ALTER TABLE model_benchmark_cache ADD COLUMN IF NOT EXISTS webdev_elo FLOAT;
ALTER TABLE model_benchmark_cache ADD COLUMN IF NOT EXISTS arc_agi_score FLOAT;
ALTER TABLE model_benchmark_cache ADD COLUMN IF NOT EXISTS simplebench_score FLOAT;
ALTER TABLE model_benchmark_cache ADD COLUMN IF NOT EXISTS canaicode_score FLOAT;
ALTER TABLE model_benchmark_cache ADD COLUMN IF NOT EXISTS seal_coding_score FLOAT;
ALTER TABLE model_benchmark_cache ADD COLUMN IF NOT EXISTS gpqa_score FLOAT;

-- MSS Component Scores
ALTER TABLE model_benchmark_cache ADD COLUMN IF NOT EXISTS adoption_score FLOAT;
ALTER TABLE model_benchmark_cache ADD COLUMN IF NOT EXISTS benchmark_score FLOAT;
ALTER TABLE model_benchmark_cache ADD COLUMN IF NOT EXISTS cost_efficiency_score FLOAT;
ALTER TABLE model_benchmark_cache ADD COLUMN IF NOT EXISTS accessibility_score FLOAT;
ALTER TABLE model_benchmark_cache ADD COLUMN IF NOT EXISTS mss FLOAT;

-- Adoption Metrics
ALTER TABLE model_benchmark_cache ADD COLUMN IF NOT EXISTS openrouter_programming_rank INTEGER;
ALTER TABLE model_benchmark_cache ADD COLUMN IF NOT EXISTS openrouter_overall_rank INTEGER;
ALTER TABLE model_benchmark_cache ADD COLUMN IF NOT EXISTS openrouter_market_share FLOAT;

-- Accessibility Metrics
ALTER TABLE model_benchmark_cache ADD COLUMN IF NOT EXISTS license_type VARCHAR(50);
ALTER TABLE model_benchmark_cache ADD COLUMN IF NOT EXISTS api_stability VARCHAR(20);
ALTER TABLE model_benchmark_cache ADD COLUMN IF NOT EXISTS documentation_quality VARCHAR(20);

-- Data Freshness Tracking
ALTER TABLE model_benchmark_cache ADD COLUMN IF NOT EXISTS adoption_data_updated_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE model_benchmark_cache ADD COLUMN IF NOT EXISTS accessibility_data_updated_at TIMESTAMP WITH TIME ZONE;

-- Add indexes for commonly queried columns
CREATE INDEX IF NOT EXISTS idx_mss ON model_benchmark_cache(mss DESC);
CREATE INDEX IF NOT EXISTS idx_adoption_score ON model_benchmark_cache(adoption_score DESC);
CREATE INDEX IF NOT EXISTS idx_benchmark_score ON model_benchmark_cache(benchmark_score DESC);
CREATE INDEX IF NOT EXISTS idx_openrouter_programming_rank ON model_benchmark_cache(openrouter_programming_rank ASC);

-- Add comments for documentation
COMMENT ON COLUMN model_benchmark_cache.bfcl_score IS 'Berkeley Function Calling Leaderboard score (0-100)';
COMMENT ON COLUMN model_benchmark_cache.webdev_elo IS 'WebDev Arena Elo score';
COMMENT ON COLUMN model_benchmark_cache.arc_agi_score IS 'ARC-AGI pass rate (0-100)';
COMMENT ON COLUMN model_benchmark_cache.simplebench_score IS 'SimpleBench accuracy (0-100)';
COMMENT ON COLUMN model_benchmark_cache.canaicode_score IS 'CanAiCode pass rate (0-100)';
COMMENT ON COLUMN model_benchmark_cache.seal_coding_score IS 'SEAL Showdown coding Bradley-Terry score';
COMMENT ON COLUMN model_benchmark_cache.gpqa_score IS 'GPQA accuracy (0-100)';
COMMENT ON COLUMN model_benchmark_cache.adoption_score IS 'MSS adoption component (0-1, 35% weight)';
COMMENT ON COLUMN model_benchmark_cache.benchmark_score IS 'MSS benchmark component (0-1, 30% weight)';
COMMENT ON COLUMN model_benchmark_cache.cost_efficiency_score IS 'MSS cost efficiency component (0-1, 20% weight)';
COMMENT ON COLUMN model_benchmark_cache.accessibility_score IS 'MSS accessibility component (0-1, 15% weight)';
COMMENT ON COLUMN model_benchmark_cache.mss IS 'Model Selection Score (Chapter 4 composite score)';
COMMENT ON COLUMN model_benchmark_cache.openrouter_programming_rank IS 'Rank in OpenRouter programming category';
COMMENT ON COLUMN model_benchmark_cache.openrouter_overall_rank IS 'Overall rank in OpenRouter leaderboard';
COMMENT ON COLUMN model_benchmark_cache.openrouter_market_share IS 'Market share percentage from OpenRouter';
COMMENT ON COLUMN model_benchmark_cache.license_type IS 'Model license type (apache, mit, llama, commercial, etc.)';
COMMENT ON COLUMN model_benchmark_cache.api_stability IS 'API stability rating (stable, beta, experimental, deprecated)';
COMMENT ON COLUMN model_benchmark_cache.documentation_quality IS 'Documentation quality rating (comprehensive, basic, minimal, none)';

-- Migration complete
