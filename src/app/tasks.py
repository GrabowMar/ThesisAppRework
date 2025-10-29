"""
Celery Integration for AI Research Platform
==========================================

Celery application factory and task definitions for orchestrating
containerized analyzer services through analyzer integration.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import os
import json as _json

from celery import Celery
from celery.signals import task_prerun, task_postrun, worker_ready
from threading import Lock
from celery import group

# Import logging
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

# Import ServiceLocator
from app.services.service_locator import ServiceLocator

# Import engine registry (best-effort)
try:  # pragma: no cover - import guard
    from app.services.analysis_engines import get_engine
except Exception:  # pragma: no cover
    get_engine = None  # type: ignore
# Import configuration
from config.celery_config import (
    BROKER_URL, CELERY_RESULT_BACKEND, CELERY_TASK_SERIALIZER, 
    CELERY_RESULT_SERIALIZER, CELERY_ACCEPT_CONTENT, CELERY_TIMEZONE,
    CELERY_ENABLE_UTC, CELERY_ROUTES, CELERY_QUEUES,
    CELERY_WORKER_PREFETCH_MULTIPLIER, CELERY_WORKER_MAX_TASKS_PER_CHILD,
    CELERY_TASK_TRACK_STARTED, CELERY_TASK_TIME_LIMIT, CELERY_TASK_SOFT_TIME_LIMIT,
    CELERY_TASK_ACKS_LATE, CELERY_WORKER_SEND_TASK_EVENTS, CELERY_RESULT_EXPIRES,
    CELERY_SEND_EVENTS, CELERY_TASK_REJECT_ON_WORKER_LOST, CELERY_TASK_DEFAULT_RETRY_DELAY,
    CELERY_TASK_MAX_RETRIES, CELERYBEAT_SCHEDULE
)
from app.config.config_manager import get_config

# ---------------------------------------------------------------------------
# Model Disable Gating
# ---------------------------------------------------------------------------
# Allow operators to disable ALL analysis tasks for specific model slugs via
# environment variable: DISABLED_ANALYSIS_MODELS="model_a,model_b"
# This provides a quick mitigation for noisy / resource-heavy automatic
# "sanity checks" on a model (e.g., anthropic_claude-3.7-sonnet) without
# needing to identify and refactor their upstream trigger immediately.

_disabled_env = os.getenv('DISABLED_ANALYSIS_MODELS', '')
DISABLED_ANALYSIS_MODELS = {
    m.strip() for m in _disabled_env.split(',') if m.strip()
}

# Emit a concise banner at import time so workers clearly show gating state
try:  # pragma: no cover - logging side effect
    if DISABLED_ANALYSIS_MODELS:
        logger.info(
            "Disabled analysis models: %s",
            ", ".join(sorted(DISABLED_ANALYSIS_MODELS))
        )
    else:
        logger.info("No disabled analysis models configured")
except Exception:
    pass

def _is_model_disabled(model_slug: str) -> bool:
    return model_slug in DISABLED_ANALYSIS_MODELS

def create_celery_app(app_name: str = 'ai_research_platform') -> Celery:
    """Create and configure Celery application."""
    
    celery = Celery(app_name)
    
    # Update configuration
    celery.conf.update(
        broker_url=BROKER_URL,
        result_backend=CELERY_RESULT_BACKEND,
        task_serializer=CELERY_TASK_SERIALIZER,
        result_serializer=CELERY_RESULT_SERIALIZER,
        accept_content=CELERY_ACCEPT_CONTENT,
        timezone=CELERY_TIMEZONE,
        enable_utc=CELERY_ENABLE_UTC,
        task_routes=CELERY_ROUTES,
        task_queues=CELERY_QUEUES,
        worker_prefetch_multiplier=CELERY_WORKER_PREFETCH_MULTIPLIER,
        worker_max_tasks_per_child=CELERY_WORKER_MAX_TASKS_PER_CHILD,
        task_track_started=CELERY_TASK_TRACK_STARTED,
        task_time_limit=CELERY_TASK_TIME_LIMIT,
        task_soft_time_limit=CELERY_TASK_SOFT_TIME_LIMIT,
        task_acks_late=CELERY_TASK_ACKS_LATE,
        worker_send_task_events=CELERY_WORKER_SEND_TASK_EVENTS,
        result_expires=CELERY_RESULT_EXPIRES,
        send_events=CELERY_SEND_EVENTS,
        task_reject_on_worker_lost=CELERY_TASK_REJECT_ON_WORKER_LOST,
        task_default_retry_delay=CELERY_TASK_DEFAULT_RETRY_DELAY,
        task_max_retries=CELERY_TASK_MAX_RETRIES,
        beat_schedule=CELERYBEAT_SCHEDULE,
    )
    
    return celery

# Create Celery instance
celery = create_celery_app()

# Expose analyzer integration accessor for tests to monkeypatch.
try:  # pragma: no cover - if integration available
    from app.services.analyzer_integration import get_analyzer_integration as _real_get_analyzer_integration  # type: ignore
    def get_analyzer_integration():  # type: ignore
        return _real_get_analyzer_integration()
except Exception:  # pragma: no cover - fallback placeholder
    def get_analyzer_integration():  # type: ignore
        raise RuntimeError("analyzer integration not available")

"""
Ensure all Celery tasks execute within a Flask application context.

We do this in two layers for robustness:
1) Override celery.Task.__call__ to push app context for all tasks defined
   against this Celery instance.
2) Additionally, register task_prerun/task_postrun signal hooks that push/pop
   app context by task_id. This covers edge cases where a running worker was
   started before the Task subclass override was applied or is using a different
   Celery instance.
"""
_worker_flask_app = None
_task_ctx_lock: Lock = Lock()
_task_ctx_map = {}  # task_id -> app_context_object
_task_ctx_managed_by_override = set()  # task_ids currently managed by _ContextTask


# ----- datetime utilities ----------------------------------------------------
def _seconds_between(end_dt: Optional[datetime], start_dt: Optional[datetime]) -> Optional[float]:
    """Return seconds between two datetimes, normalizing to UTC and handling
    naive vs aware datetimes safely. Returns None if either is missing.
    """
    if not end_dt or not start_dt:
        return None
    def to_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    try:
        # Import here (inside try) so NameError doesn't occur if module import fails earlier
        e = to_utc(end_dt)
        s = to_utc(start_dt)
        return (e - s).total_seconds()
    except Exception:
        # Last-resort fallback via timestamps
        try:
            e_ts = (end_dt.replace(tzinfo=timezone.utc)).timestamp()
            s_ts = (start_dt.replace(tzinfo=timezone.utc)).timestamp()
            return e_ts - s_ts
        except Exception:
            return None

def _ensure_worker_app():
    global _worker_flask_app
    if _worker_flask_app is None:
        try:
            from app.factory import create_app as _create_flask_app
            _worker_flask_app = _create_flask_app('worker')
        except Exception as _err:  # pragma: no cover - safety
            logger.warning(f"Could not create worker Flask app: {_err}")
            _worker_flask_app = None
    return _worker_flask_app

def _push_app_context_for_task(task_id: str):
    app = _ensure_worker_app()
    if app is None:
        return
    try:
        ctx = app.app_context()
        ctx.push()
        with _task_ctx_lock:
            _task_ctx_map[task_id] = ctx
    except Exception as e:  # pragma: no cover
        logger.warning(f"Failed to push app context for task {task_id}: {e}")

def _pop_app_context_for_task(task_id: str):
    try:
        with _task_ctx_lock:
            ctx = _task_ctx_map.pop(task_id, None)
        if ctx is not None:
            try:
                ctx.pop()
            except Exception:
                pass
    except Exception as e:  # pragma: no cover
        logger.warning(f"Failed to pop app context for task {task_id}: {e}")

# Layer 1: Task subclass override
try:
    class _ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):  # type: ignore[override]
            # Use task id if available for consistent push/pop
            task_id = getattr(self.request, 'id', None)
            if task_id:
                _push_app_context_for_task(task_id)
                # Mark as managed so signal hooks can avoid double push/pop
                try:
                    with _task_ctx_lock:
                        _task_ctx_managed_by_override.add(task_id)
                except Exception:
                    pass
                try:
                    return self.run(*args, **kwargs)
                finally:
                    _pop_app_context_for_task(task_id)
                    try:
                        with _task_ctx_lock:
                            _task_ctx_managed_by_override.discard(task_id)
                    except Exception:
                        pass
            # Fallback: push once for the duration of this call
            app = _ensure_worker_app()
            if app is None:
                return self.run(*args, **kwargs)
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = _ContextTask
except Exception as _ctx_err:  # pragma: no cover - best effort safety
    logger.warning(f"Could not set Celery ContextTask: {_ctx_err}")

def _run_engine(engine_name: str, model_slug: str, app_number: int, **kwargs):
    """Helper to invoke an analysis engine and return payload dict.

    Falls back to descriptive error dict if engine registry unavailable.
    """
    if not get_engine:
        return {'status': 'error', 'error': 'engine_registry_unavailable'}
    try:
        engine = get_engine(engine_name)
        result = engine.run(model_slug, app_number, **kwargs)
        return result.to_dict()
    except Exception as e:  # pragma: no cover - defensive
        return {'status': 'error', 'error': str(e)}

def update_task_progress(current: int, total: int, status: Optional[str] = None, metadata: Optional[Dict] = None):
    """Update task progress for monitoring."""
    # Simplified version to avoid type checking issues
    # In a real implementation, this would update Celery task state
    logger.debug(f"Task progress: {current}/{total} ({int((current/total)*100) if total > 0 else 0}%) - {status or 'running'}")

# =============================================================================
# ANALYZER ORCHESTRATION TASKS
# =============================================================================

@celery.task(bind=True, name='app.tasks.execute_analysis')
def execute_analysis(self, model_slug: str, app_number: int, 
                     tools: List[str], 
                     options: Optional[Dict] = None):
    """
    Universal Celery task to execute any analysis by specifying a list of tools.
    This replaces all previous type-specific analysis tasks.
    
    Args:
        model_slug: The model identifier.
        app_number: The application number.
        tools: A list of tool names to be executed.
        options: Additional options for the analysis.
    """
    
    if _is_model_disabled(model_slug):
        return {
            'model_slug': model_slug,
            'app_number': app_number,
            'analysis_type': 'custom',
            'status': 'skipped',
            'reason': 'model_disabled',
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

    opts = options or {}
    
    try:
        update_task_progress(0, 100, f"Initializing analysis with tools: {', '.join(tools)}")

        if opts.get('force_engine_exception'):
            raise RuntimeError(str(opts.get('force_engine_exception')))
        
        if 'force_engine_result' in opts:
            result = opts['force_engine_result']
        else:
            # The 'universal' engine is now the only one
            result = _run_engine(
                'universal', model_slug, app_number, 
                tools=tools, options=opts
            )

        update_task_progress(80, 100, "Processing results")
        status = result.get('status', 'completed') if isinstance(result, dict) else 'completed'

        final_result = {
            'model_slug': model_slug,
            'app_number': app_number,
            'task_name': 'custom',  # Set to a generic value
            'tools': tools,
            'result': result,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'status': status,
            'analysis_id': opts.get('analysis_id')
        }

        update_task_progress(100, 100, "Analysis completed")
        return final_result

    except Exception as e:
        error_msg = f"Analysis failed for tools {tools}: {str(e)}"
        update_task_progress(0, 100, f"Error: {error_msg}")
        
        transient = any(msg in str(e).lower() for msg in ["timeout", "connection refused", "temporary", "unavailable"])
        if transient and getattr(self, 'request', None) and self.request.retries < 3:
            raise self.retry(exc=e, countdown=60, max_retries=3)
        raise

# =============================================================================
# PARALLEL SUBTASK EXECUTION
# =============================================================================

@celery.task(bind=True, name='app.tasks.run_analyzer_subtask', time_limit=900, soft_time_limit=840)
def run_analyzer_subtask(self, subtask_id: int, model_slug: str, app_number: int, tool_names: List[str], service_name: str) -> Dict:
    """Execute a subtask for a specific analyzer service with a 15-minute timeout."""
    from app.extensions import db, get_session
    from app.models import AnalysisTask
    from app.constants import AnalysisStatus
    
    try:
        with get_session() as session:
            subtask = session.get(AnalysisTask, subtask_id)
            if subtask:
                subtask.status = AnalysisStatus.RUNNING
                subtask.started_at = datetime.now(timezone.utc)
                session.commit()
        
        # The engine name is now ignored, but we pass it for compatibility.
        result = _run_engine(service_name, model_slug, app_number, tools=tool_names, persist=True)
        
        with get_session() as session:
            subtask = session.get(AnalysisTask, subtask_id)
            if subtask:
                subtask.status = AnalysisStatus.COMPLETED
                subtask.completed_at = datetime.now(timezone.utc)
                subtask.progress_percentage = 100.0
                if subtask.started_at and subtask.completed_at:
                    subtask.actual_duration = _seconds_between(subtask.completed_at, subtask.started_at)
                subtask.set_result_summary(result)
                session.commit()
        
        return {'status': 'completed', 'subtask_id': subtask_id, 'service': service_name, 'result': result}
    
    except Exception as e:
        try:
            with get_session() as session:
                subtask = session.get(AnalysisTask, subtask_id)
                if subtask:
                    subtask.status = AnalysisStatus.FAILED
                    subtask.completed_at = datetime.now(timezone.utc)
                    subtask.error_message = str(e)
                    session.commit()
        except Exception:
            pass
        raise

@celery.task(bind=True, name='app.tasks.aggregate_subtask_results')
def aggregate_subtask_results(self, subtask_results: List[Dict], main_task_id: str) -> Dict:
    """Aggregate results from parallel subtasks into unified payload."""
    from app.extensions import db, get_session
    from app.models import AnalysisTask, GeneratedApplication
    from app.constants import AnalysisStatus
    from app.services.unified_result_service import UnifiedResultService
    
    try:
        # Collect all results
        all_results: Dict[str, Dict[str, Any]] = {}
        combined_tools: Dict[str, Dict[str, Any]] = {}
        all_findings: List[Dict[str, Any]] = []
        tools_used: List[str] = []
        tools_successful: List[str] = []
        tools_failed: List[str] = []
        aggregated_severity: Dict[str, int] = {}
        total_findings_accum = 0
        summary_status = 'completed'

        for subtask_result in subtask_results:
            if subtask_result.get('status') != 'completed':
                continue

            service = subtask_result.get('service') or 'unknown-service'
            result = subtask_result.get('result', {})
            if not isinstance(result, dict):
                continue

            payload = result.get('payload') if isinstance(result.get('payload'), dict) else None
            all_results[service] = result

            result_status = str(result.get('status', '')).lower()
            if result_status and result_status not in ('completed', 'success', 'ok'):
                summary_status = 'failed'
            if payload and payload.get('success') is False:
                summary_status = 'failed'

            # Gather tool result dictionaries from both top-level and payload shapes
            candidate_tool_maps: List[Dict[str, Any]] = []
            direct_tools = result.get('tool_results')
            if isinstance(direct_tools, dict):
                candidate_tool_maps.append(direct_tools)
            if payload and isinstance(payload.get('tool_results'), dict):
                candidate_tool_maps.append(payload['tool_results'])

            service_tool_issue_sum = 0
            service_severity: Dict[str, int] = {}
            severity_from_tools = False

            for tool_map in candidate_tool_maps:
                for tool_name, tool_data in tool_map.items():
                    if not isinstance(tool_name, str):
                        continue

                    existing = combined_tools.get(tool_name)
                    if isinstance(existing, dict) and isinstance(tool_data, dict):
                        merged = existing.copy()
                        for key, value in tool_data.items():
                            if key not in merged or merged[key] in (None, '', [], {}):
                                merged[key] = value
                        combined_tools[tool_name] = merged
                    else:
                        combined_tools[tool_name] = tool_data

                    if tool_name not in tools_used:
                        tools_used.append(tool_name)

                    if isinstance(tool_data, dict):
                        issues_val = tool_data.get('total_issues')
                        if isinstance(issues_val, int) and issues_val > 0:
                            service_tool_issue_sum += issues_val

                        severity_map = tool_data.get('severity_breakdown')
                        if isinstance(severity_map, dict) and severity_map:
                            severity_from_tools = True
                            for severity, count in severity_map.items():
                                try:
                                    service_severity[severity] = service_severity.get(severity, 0) + int(count)
                                except (TypeError, ValueError):
                                    continue

                        status_val = str(tool_data.get('status', '')).lower()
                        if status_val in ('success', 'completed', 'ok'):
                            if tool_name not in tools_successful:
                                tools_successful.append(tool_name)
                        elif status_val:
                            if tool_name not in tools_failed:
                                tools_failed.append(tool_name)

            # Incorporate requested/used tool hints when analyzer skipped execution
            candidate_tool_lists: List[List[Any]] = []
            for key in ('tools_used', 'tools_requested', 'requested_tools'):
                value = result.get(key)
                if isinstance(value, list):
                    candidate_tool_lists.append(value)
            if payload:
                for key in ('tools_used', 'tools_requested', 'requested_tools'):
                    value = payload.get(key)
                    if isinstance(value, list):
                        candidate_tool_lists.append(value)
            for tool_list in candidate_tool_lists:
                for tool_name in tool_list:
                    if isinstance(tool_name, str) and tool_name not in tools_used:
                        tools_used.append(tool_name)

            # Aggregate findings from any structure we can find
            findings_sources = []
            if isinstance(result.get('findings'), list):
                findings_sources.append(result['findings'])
            if payload and isinstance(payload.get('findings'), list):
                findings_sources.append(payload['findings'])
            for findings in findings_sources:
                for finding in findings:
                    if isinstance(finding, dict):
                        all_findings.append(finding)

            # Merge summary information for totals/severity
            summary_candidates: List[Dict[str, Any]] = []
            if isinstance(result.get('summary'), dict):
                summary_candidates.append(result['summary'])
            if payload and isinstance(payload.get('summary'), dict):
                summary_candidates.append(payload['summary'])

            service_total_findings = service_tool_issue_sum
            for summary in summary_candidates:
                total_from_summary = summary.get('total_findings')
                if isinstance(total_from_summary, int):
                    service_total_findings = max(service_total_findings, total_from_summary)

                if not severity_from_tools:
                    severity_map = summary.get('severity_breakdown')
                    if isinstance(severity_map, dict):
                        for severity, count in severity_map.items():
                            try:
                                service_severity[severity] = service_severity.get(severity, 0) + int(count)
                            except (TypeError, ValueError):
                                continue

            total_findings_accum += service_total_findings
            for severity, count in service_severity.items():
                aggregated_severity[severity] = aggregated_severity.get(severity, 0) + count

        if not tools_used and combined_tools:
            tools_used = list(combined_tools.keys())

        # De-duplicate tool lists while preserving discovery order
        tools_used = list(dict.fromkeys(tools_used))
        tools_successful = [t for t in tools_successful if t in combined_tools]
        tools_failed = [t for t in tools_failed if t in combined_tools]

        total_findings_value = max(total_findings_accum, len(all_findings))
        success_flag = summary_status in ('completed', 'success', 'ok')

        # Build unified payload
        unified_payload = {
            'task': {'task_id': main_task_id},
            'summary': {
                'total_findings': total_findings_value,
                'services_executed': len(all_results),
                'tools_executed': len(combined_tools),
                'tools_successful': len(tools_successful),
                'tools_failed': len(tools_failed),
                'status': summary_status
            },
            'services': all_results,
            'tool_results': combined_tools,
            'tools': combined_tools,
            'tools_used': tools_used,
            'tools_requested': tools_used,
            'tools_successful': len(tools_successful),
            'tools_failed': len(tools_failed),
            'tools_successful_names': tools_successful,
            'tools_failed_names': tools_failed,
            'findings': all_findings,
            'metadata': {
                'unified_analysis': True,
                'generated_at': datetime.now(timezone.utc).isoformat(),
                'services_included': list(all_results.keys())
            },
            'success': success_flag
        }

        if aggregated_severity:
            unified_payload['summary']['severity_breakdown'] = aggregated_severity
        unified_payload['summary']['success'] = success_flag

        # Build condensed raw outputs block so downstream consumers can access artifacts quickly
        raw_outputs: Dict[str, Dict[str, Any]] = {}
        for tool_name, tool_meta in combined_tools.items():
            if not isinstance(tool_name, str) or not isinstance(tool_meta, dict):
                continue
            artifact: Dict[str, Any] = {}
            for key in ('raw_output', 'stdout', 'stderr', 'command_line', 'exit_code', 'error'):
                value = tool_meta.get(key)
                if value not in (None, '', [], {}):
                    artifact[key] = value
            raw_details = tool_meta.get('raw_details')
            if isinstance(raw_details, dict) and raw_details:
                artifact.setdefault('raw_details', raw_details)
            if artifact:
                raw_outputs[tool_name] = artifact
        if raw_outputs:
            unified_payload['raw_outputs'] = raw_outputs
        
        # Persist unified results to database
        with get_session() as session:
            main_task = session.query(AnalysisTask).filter_by(task_id=main_task_id).first()
            if main_task:
                main_task.status = AnalysisStatus.COMPLETED
                main_task.completed_at = datetime.now(timezone.utc)
                main_task.progress_percentage = 100.0
                if main_task.started_at and main_task.completed_at:
                    main_task.actual_duration = _seconds_between(main_task.completed_at, main_task.started_at)
                main_task.set_result_summary(unified_payload)
                session.commit()
        
        # Persist to unified result service (database + disk file writes)
        try:
            result_service = UnifiedResultService()
            # Get model_slug and app_number from task
            with get_session() as session:
                task = session.query(AnalysisTask).filter_by(task_id=main_task_id).first()
                if task and task.target_model and task.target_app_number:
                    result_service.store_analysis_results(
                        task_id=main_task_id,
                        payload=unified_payload,
                        model_slug=task.target_model,
                        app_number=task.target_app_number
                    )
        except Exception as e:
            logger.warning(f"Failed to persist unified results: {e}")
        
        return unified_payload
    
    except Exception as e:
        logger.error(f"Failed to aggregate subtask results: {e}")
        # Mark main task as failed
        try:
            with get_session() as session:
                main_task = session.query(AnalysisTask).filter_by(task_id=main_task_id).first()
                if main_task:
                    main_task.status = AnalysisStatus.FAILED
                    main_task.completed_at = datetime.now(timezone.utc)
                    main_task.error_message = str(e)
                    session.commit()
        except Exception:
            pass
        raise



# =============================================================================
# CONTAINER MANAGEMENT TASKS
# =============================================================================
# Container management externalized to analyzer_manager.py CLI and DockerManager service

# =============================================================================
# MONITORING TASKS
# =============================================================================

# Health checking and monitoring now handled by HealthService and analyzer_manager.py

@celery.task(name='app.tasks.cleanup_expired_results')
def cleanup_expired_results():
    """Clean up expired analysis results and temporary files."""
    
    try:
        # This would clean up old results from database and filesystem
        # For now, just return a placeholder result
        return {
            'cleanup': {'files_cleaned': 0, 'results_cleaned': 0},
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'status': 'completed'
        }
        
    except Exception as e:
        return {
            'status': 'failed',
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

# =============================================================================
# CELERY SIGNALS
# =============================================================================

@task_prerun.connect
def task_prerun_handler(task_id, task, *args, **kwargs):
    """Handle task pre-execution setup."""
    logger.info(f"Starting task {task.name} with ID {task_id}")
    try:
        # Belt-and-suspenders app context push, but skip if our Task override is handling it
        with _task_ctx_lock:
            managed = task_id in _task_ctx_managed_by_override
        if not managed:
            _push_app_context_for_task(task_id)
    except Exception as e:  # pragma: no cover
        logger.warning(f"task_prerun app context push failed for {task_id}: {e}")

@task_postrun.connect
def task_postrun_handler(task_id, task, retval, state, *args, **kwargs):
    """Handle task post-execution cleanup."""
    logger.info(f"Completed task {task.name} with ID {task_id}, state: {state}")
    try:
        with _task_ctx_lock:
            managed = task_id in _task_ctx_managed_by_override
        if not managed:
            _pop_app_context_for_task(task_id)
    except Exception as e:  # pragma: no cover
        logger.warning(f"task_postrun app context pop failed for {task_id}: {e}")

@worker_ready.connect
def worker_ready_handler(sender, **kwargs):
    """Handle worker ready event."""
    logger.info(f"Celery worker {sender} is ready and connected to analyzer infrastructure")


if __name__ == '__main__':
    logger.info("Celery tasks module loaded successfully")
    logger.info(f"Available tasks: {list(celery.tasks.keys())}")
