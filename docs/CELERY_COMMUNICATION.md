# Celery Communication in the Analysis Platform

This document describes how Celery orchestrates asynchronous, container-backed analysis in the platform: the request → service → task → analyzer → persistence → UI path, with concrete contracts and operational guidance.

## Overview

- UI (HTMX) submits analysis requests → Service layer creates DB records and enqueues Celery tasks → Tasks call analyzer services (Dockerized) → Results are persisted → UI renders results pages.
- Applies to security/static tools, dynamic (OWASP ZAP-like) scans, performance tests, and batch jobs.

## Key Components

- Flask routes
  - `src/app/routes/analysis.py`: HTMX endpoints for forms and results pages.
  - `src/app/routes/api/analysis.py`: JSON API endpoints.
- Service layer
  - `src/app/services/analysis_service.py`: CRUD-lite, state transitions, enqueue logic.
  - `src/app/services/task_manager.py`: convenience wrapper for enqueue (legacy compatibility).
- Celery tasks
  - `src/app/tasks.py`: `run_security_analysis`, `dynamic_analysis_task`, `performance_test_task`, `batch_analysis_task`, etc.
- Analyzer integration
  - `src/app/services/analyzer_integration.py`: bridges to `analyzer/analyzer_manager.py` (container orchestration), returns normalized JSON.
- Models
  - `src/app/models.py`: `SecurityAnalysis`, `ZAPAnalysis`, `PerformanceTest`; JSON fields for flexible results/metadata.
- UI Partials
  - `src/templates/partials/analysis/*` for HTMX forms and results views (testing namespace removed)

## End-to-End Flow

1. UI submits form (HTMX)
   - Security: POST `/analysis/security/start`
   - Dynamic: POST `/analysis/dynamic/start`
2. Service layer
   - Create DB record (flags, configs, target, metadata)
   - Start: set `status=RUNNING`, `started_at`, enqueue Celery task
3. Celery worker runs task
   - Ensures analyzer services are up
   - Calls analyzer integration; receives structured JSON
   - Persists results, counts, and timestamps
4. UI renders results page
   - Security: `/analysis/security/<id>/results/view`
   - Dynamic: `/analysis/dynamic/<id>`

## Contracts

### Dynamic (ZAP) Analysis

- Create (service input):
  - `application_id: int` (required)
  - `target_url: str` (optional; can be inferred)
  - `scan_type: "baseline" | "active"` (default: `baseline`)
  - `include_paths: List[str]` (optional)
  - `exclude_paths: List[str]` (optional)
  - `timeout_minutes: int` (optional; default 10)
- Start (service input):
  - `analysis_id: int`, `enqueue: bool=True`
- Celery payload (service → task):
  - `analysis_id: int`
  - `batch_job_id: Optional[str]`
  - `timeout: int` (seconds, from `timeout_minutes`)
- Persisted (`ZAPAnalysis`):
  - Scalars: `status`, `target_url`, `scan_type`, timestamps
  - JSON: `zap_report_json` (full report), `metadata_json` (include/exclude/timeout, duration, last_error)
  - Counts: `high_risk_alerts`, `medium_risk_alerts`, `low_risk_alerts`, `informational_alerts`

### Security (Comprehensive Static/Dependency)

- Create (service input):
  - `application_id: int` (required)
  - `analysis_name`, `description`
  - Tool flags: `bandit_enabled`, `safety_enabled`, `pylint_enabled`, `eslint_enabled`, `npm_audit_enabled`, `snyk_enabled`, `zap_enabled`, `semgrep_enabled`
  - Configs (JSON): `bandit_config`, `safety_config`, `eslint_config`, `pylint_config`, `zap_config`, `global_config`
  - Filters: `include_patterns`, `exclude_patterns`
  - Controls: `severity_threshold`, `max_issues_per_tool`, `timeout_minutes`
- Start (service input):
  - `analysis_id: int`, `enqueue: bool=True`
- Celery payload:
  - Only `analysis_id`; task loads analysis options from DB
- Persisted (`SecurityAnalysis`):
  - JSON: `results_json` (per-tool nested results), `metadata_json` (run info)
  - Summary: totals, severity counts, tools run/failed, duration

## State & Lifecycle

- States: `PENDING → RUNNING → COMPLETED | FAILED`
- Service transitions on start; tasks finalize status and `completed_at`.
- Duration is derived from timestamps and stored (security) or placed in metadata (dynamic).

## Error Handling & Retry

- Dynamic task retries transient errors (timeout/connection issues) with `self.retry(countdown=60, max_retries=3)`.
- On hard failure, tasks record `last_error` in metadata and mark as `FAILED`.
- Batch task updates aggregate progress for each subtask completion/failure.

## Progress/Status Reporting

- Tasks call progress hooks; task IDs are returned at enqueue time.
- Minimal HTMX partial (`partials/analysis/create/start_result.html`) shows the task ID and links to results.
- Optional: poll an API endpoint or integrate with websocket status events.

## Analyzer Integration

- Wrapper around CLI-driven container orchestration (`analyzer/analyzer_manager.py`).
- Ensures analyzer services start, executes requested analysis, returns normalized JSON.
- Tasks are responsible for mapping summaries and persisting key counts.

## Operational Notes

- Prereqs: Redis running (for Celery), Docker for analyzer containers.
- Timezones: prefer timezone-aware UTC (`datetime.now(timezone.utc)`) for new code.
- Security: sanitize/validate inputs; restrict targets to known apps/ports.
- Scaling: configure Celery workers/queues based on throughput; containers can run in parallel.

## Quick References

- Start security analysis (HTMX): `POST /analysis/security/start`
- Start dynamic analysis (HTMX): `POST /analysis/dynamic/start`
- Security results page: `/analysis/security/<id>/results/view`
- Dynamic results page: `/analysis/dynamic/<id>`

## File Map

- Routes: `src/app/routes/analysis.py`, `src/app/routes/api/analysis.py`
- Services: `src/app/services/analysis_service.py`, `src/app/services/task_manager.py`, `src/app/services/analyzer_integration.py`
- Tasks: `src/app/tasks.py`
- Models: `src/app/models.py`
- Templates: `src/templates/partials/analysis/*`
