"""
Celery Integration for AI Research Platform
==========================================

Celery application factory and task definitions for orchestrating
containerized analyzer services through analyzer integration.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional
import os
import json as _json

from celery import Celery
from celery.signals import task_prerun, task_postrun, worker_ready
from threading import Lock

# Import engine registry & batch service (best-effort)
try:  # pragma: no cover - import guard
    from app.services.analysis_engines import get_engine
except Exception:  # pragma: no cover
    get_engine = None  # type: ignore

try:  # pragma: no cover
    from app.services.batch_service import batch_service  # type: ignore
except Exception:  # pragma: no cover
    batch_service = None  # type: ignore

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
        print(
            "[tasks] Disabled analysis models:",
            ", ".join(sorted(DISABLED_ANALYSIS_MODELS))
        )
    else:
        print("[tasks] No disabled analysis models configured")
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
            print(f"Warning: Could not create worker Flask app: {_err}")
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
        print(f"Warning: Failed to push app context for task {task_id}: {e}")

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
        print(f"Warning: Failed to pop app context for task {task_id}: {e}")

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
    print(f"Warning: Could not set Celery ContextTask: {_ctx_err}")

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
    print(f"Task progress: {current}/{total} ({int((current/total)*100) if total > 0 else 0}%) - {status or 'running'}")

def update_batch_progress(batch_job_id: Optional[str], task_completed: bool = False, 
                         task_failed: bool = False, result: Optional[Dict] = None):
    """Update batch job progress."""
    if batch_service and batch_job_id:
        try:
            batch_service.update_task_progress(
                batch_job_id, task_completed, task_failed, result
            )
        except Exception as e:
            print(f"Failed to update batch progress: {e}")

# =============================================================================
# ANALYZER ORCHESTRATION TASKS
# =============================================================================

@celery.task(bind=True, name='app.tasks.security_analysis_task')
def security_analysis_task(self, model_slug: str, app_number: int, 
                          tools: Optional[List[str]] = None, options: Optional[Dict] = None):
    """
    Run security analysis on a specific model application.
    
    Args:
        model_slug: Model identifier (e.g., 'openai_gpt-4')
        app_number: Application number (1-30)
        tools: List of security tools to run
        options: Additional analysis options
    """
    
    # Early exit if model globally disabled
    if _is_model_disabled(model_slug):
        return {
            'model_slug': model_slug,
            'app_number': app_number,
            'analysis_type': 'security',
            'status': 'skipped',
            'reason': 'model_disabled',
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

    batch_job_id = options.get('batch_job_id') if options else None
    analysis_id = options.get('analysis_id') if options else None

    # Import here to avoid circular import at module load
    from app.extensions import get_session
    from app.models import SecurityAnalysis
    from app.constants import AnalysisStatus

    try:
        # Engines are stateless; no container start step now
        update_task_progress(0, 100, "Initializing security analysis")

        # Fetch analysis record (if provided) and mark RUNNING
        if analysis_id:
            with get_session() as session:
                analysis = session.query(SecurityAnalysis).get(analysis_id)
                if analysis:
                    analysis.status = AnalysisStatus.RUNNING
                    analysis.started_at = datetime.now(timezone.utc)
                    session.commit()

        # Default tools if not specified
        if not tools:
            tools = ['bandit', 'safety', 'pylint']

        update_task_progress(10, 100, "Preparing engine")
        update_task_progress(20, 100, "Running security analysis")

        # Run the analysis via engine
        result = _run_engine('security', model_slug, app_number, tools=tools, options=options)

        update_task_progress(80, 100, "Processing results")
        status = result.get('status', 'completed')

        # Persist results
        if analysis_id:
            with get_session() as session:
                analysis = session.query(SecurityAnalysis).get(analysis_id)
                if analysis:
                    analysis.status = AnalysisStatus.COMPLETED if status == 'completed' else AnalysisStatus.FAILED
                    analysis.completed_at = datetime.now(timezone.utc)
                    if analysis.started_at:
                        # Ensure both datetimes are timezone-aware (UTC)
                        def ensure_aware(dt):
                            if dt is None:
                                return None
                            if dt.tzinfo is None:
                                return dt.replace(tzinfo=timezone.utc)
                            return dt
                        started = ensure_aware(analysis.started_at)
                        completed = ensure_aware(analysis.completed_at)
                        if started and completed:
                            analysis.analysis_duration = (completed - started).total_seconds()
                    # Store raw result JSON
                    try:
                        analysis.results_json = _json.dumps(result)
                    except Exception:
                        analysis.results_json = _json.dumps({'raw_result': str(result)})

                    # Update summary counts if present
                    summary = result.get('summary') if isinstance(result, dict) else {}
                    if not isinstance(summary, dict):
                        summary = {}
                    # Some analyzers may return counts at top-level
                    analysis.total_issues = (summary.get('total_issues') if isinstance(summary, dict) else 0) or (result.get('total_issues') if isinstance(result, dict) else 0) or 0
                    analysis.critical_severity_count = (summary.get('critical') if isinstance(summary, dict) else 0) or (result.get('critical_count') if isinstance(result, dict) else 0) or 0
                    analysis.high_severity_count = (summary.get('high') if isinstance(summary, dict) else 0) or (result.get('high_count') if isinstance(result, dict) else 0) or 0
                    analysis.medium_severity_count = (summary.get('medium') if isinstance(summary, dict) else 0) or (result.get('medium_count') if isinstance(result, dict) else 0) or 0
                    analysis.low_severity_count = (summary.get('low') if isinstance(summary, dict) else 0) or (result.get('low_count') if isinstance(result, dict) else 0) or 0
                    # Track tools run
                    if isinstance(tools, list):
                        analysis.tools_run_count = len(tools)
                    session.commit()

        # Prepare final return payload
        final_result = {
            'model_slug': model_slug,
            'app_number': app_number,
            'analysis_type': 'security',
            'tools': tools,
            'result': result,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'status': status,
            'analysis_id': analysis_id
        }

        update_batch_progress(batch_job_id, task_completed=True, result=final_result)
        update_task_progress(100, 100, "Analysis completed")
        return final_result

    except Exception as e:
        error_msg = f"Security analysis failed: {str(e)}"
        update_task_progress(0, 100, f"Error: {error_msg}")

        # Mark analysis failed immediately (avoid leaving RUNNING) before retry
        if analysis_id:
            try:
                with get_session() as session:
                    analysis = session.query(SecurityAnalysis).get(analysis_id)
                    if analysis:
                        analysis.status = AnalysisStatus.FAILED
                        analysis.completed_at = datetime.now(timezone.utc)
                        if analysis.started_at:
                            # Ensure both datetimes are timezone-aware (UTC)
                            def ensure_aware(dt):
                                if dt is None:
                                    return None
                                if dt.tzinfo is None:
                                    return dt.replace(tzinfo=timezone.utc)
                                return dt
                            started = ensure_aware(analysis.started_at)
                            completed = ensure_aware(analysis.completed_at)
                            if started and completed:
                                analysis.analysis_duration = (completed - started).total_seconds()
                        # Append error metadata
                        meta = analysis.get_metadata() if hasattr(analysis, 'get_metadata') else {}
                        meta['last_error'] = str(e)
                        if hasattr(analysis, 'set_metadata'):
                            analysis.set_metadata(meta)
                        session.commit()
            except Exception as meta_e:
                print(f"Failed to record failure metadata: {meta_e}")

        update_batch_progress(batch_job_id, task_failed=True)

        # Decide whether to retry: only retry transient infrastructure errors
        transient = any(msg in str(e).lower() for msg in ["timeout", "connection refused", "temporary", "unavailable"])
        if transient and getattr(self, 'request', None) and self.request.retries < 3:
            raise self.retry(exc=e, countdown=60, max_retries=3)
        # Non-transient: raise without retry so status stays FAILED
        raise


@celery.task(bind=True, name='app.tasks.run_security_analysis')
def run_security_analysis(self, analysis_id: int):
    """Lookup SecurityAnalysis and dispatch security_analysis_task.

    Returns the Celery async result id for traceability.
    """
    try:
        # Import here to avoid circular dependencies
        from app.extensions import get_session
        from app.models import SecurityAnalysis as _Sec, GeneratedApplication as _GA

        with get_session() as session:
            analysis = session.query(_Sec).get(analysis_id)
            if not analysis:
                raise ValueError(f"SecurityAnalysis {analysis_id} not found")
            app = session.query(_GA).get(analysis.application_id)
            if not app:
                raise ValueError("Associated application not found")

            # Build tools list from flags on the analysis record
            tools: List[str] = []
            if getattr(analysis, 'bandit_enabled', False):
                tools.append('bandit')
            if getattr(analysis, 'safety_enabled', False):
                tools.append('safety')
            if getattr(analysis, 'pylint_enabled', False):
                tools.append('pylint')
            if getattr(analysis, 'eslint_enabled', False):
                tools.append('eslint')
            if getattr(analysis, 'npm_audit_enabled', False):
                tools.append('npm_audit')
            if getattr(analysis, 'semgrep_enabled', False):
                tools.append('semgrep')
            # ZAP treated as part of dynamic; include only if your analyzer supports it inline
            if getattr(analysis, 'zap_enabled', False):
                tools.append('zap')

            options: Dict[str, Optional[object]] = {
                'analysis_id': analysis_id,
                'batch_job_id': None,
            }

            # Dispatch underlying task
            async_result = security_analysis_task.delay(app.model_slug, app.app_number, tools, options)  # type: ignore[call-arg]
            return {'task_id': getattr(async_result, 'id', None), 'analysis_id': analysis_id}
    except Exception as e:
        # Surface a clear error; the caller will mark FAILED appropriately
        raise e

@celery.task(bind=True, name='app.tasks.performance_test_task')
def performance_test_task(self, model_slug: str, app_number: int, 
                         test_config: Optional[Dict] = None):
    """
    Run performance testing on a specific model application.
    
    Args:
        model_slug: Model identifier
        app_number: Application number
        test_config: Performance test configuration
    """
    
    if _is_model_disabled(model_slug):
        return {
            'model_slug': model_slug,
            'app_number': app_number,
            'analysis_type': 'performance',
            'status': 'skipped',
            'reason': 'model_disabled',
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

    batch_job_id = test_config.get('batch_job_id') if test_config else None
    
    try:
        # Engines are stateless; no container start step now
        update_task_progress(0, 100, "Initializing performance testing")

        # Default configuration
        config = test_config or {
            'users': 10,
            'spawn_rate': 2,
            'duration': 300,
            'host': f'http://localhost:800{app_number}'
        }

        update_task_progress(10, 100, "Preparing engine")
        update_task_progress(20, 100, "Running performance tests")

        # Run performance test via engine
        result = _run_engine('performance', model_slug, app_number, test_config=config)

        update_task_progress(80, 100, "Processing performance results")
        
        final_result = {
            'model_slug': model_slug,
            'app_number': app_number,
            'analysis_type': 'performance',
            'config': config,
            'result': result,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'status': result.get('status', 'completed')
        }
        
        # Update batch progress if this is part of a batch
        update_batch_progress(batch_job_id, task_completed=True, result=final_result)
        
        update_task_progress(100, 100, "Performance testing completed")
        
        return final_result
        
    except Exception as e:
        error_msg = f"Performance testing failed: {str(e)}"
        update_task_progress(0, 100, f"Error: {error_msg}")
        
        # Update batch progress for failed task
        update_batch_progress(batch_job_id, task_failed=True)
        
        raise self.retry(exc=e, countdown=60, max_retries=3)

@celery.task(bind=True, name='app.tasks.static_analysis_task')
def static_analysis_task(self, model_slug: str, app_number: int,
                        tools: Optional[List[str]] = None, options: Optional[Dict] = None):
    """
    Run static code analysis on a specific model application.
    
    Args:
        model_slug: Model identifier
        app_number: Application number
        tools: List of static analysis tools
        options: Additional analysis options
    """
    
    if _is_model_disabled(model_slug):
        return {
            'model_slug': model_slug,
            'app_number': app_number,
            'analysis_type': 'static',
            'status': 'skipped',
            'reason': 'model_disabled',
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

    batch_job_id = options.get('batch_job_id') if options else None
    
    try:
        # Engines are stateless; no container start step now
        update_task_progress(0, 100, "Initializing static analysis")

        # Default tools
        if not tools:
            tools = ['pylint', 'flake8']

        update_task_progress(10, 100, "Preparing engine")
        update_task_progress(20, 100, "Running static analysis")

        # Run static analysis via engine
        result = _run_engine('static', model_slug, app_number, tools=tools, options=options)

        update_task_progress(80, 100, "Processing static analysis results")
        
        final_result = {
            'model_slug': model_slug,
            'app_number': app_number,
            'analysis_type': 'static',
            'tools': tools,
            'result': result,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'status': result.get('status', 'completed')
        }
        
        # Update batch progress if this is part of a batch
        update_batch_progress(batch_job_id, task_completed=True, result=final_result)
        
        update_task_progress(100, 100, "Static analysis completed")
        
        return final_result
        
    except Exception as e:
        error_msg = f"Static analysis failed: {str(e)}"
        update_task_progress(0, 100, f"Error: {error_msg}")
        
        # Update batch progress for failed task
        update_batch_progress(batch_job_id, task_failed=True)
        
        raise self.retry(exc=e, countdown=60, max_retries=3)

@celery.task(bind=True, name='app.tasks.dynamic_analysis_task')
def dynamic_analysis_task(self, model_slug: str, app_number: int, options: Optional[Dict] = None):
    """
    Run dynamic (ZAP-like) security analysis on a specific model application.
    
    Args:
        model_slug: Model identifier
        app_number: Application number
        options: Additional options (e.g., target URLs, timeouts)
    """
    if _is_model_disabled(model_slug):
        return {
            'model_slug': model_slug,
            'app_number': app_number,
            'analysis_type': 'dynamic',
            'status': 'skipped',
            'reason': 'model_disabled',
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

    batch_job_id = options.get('batch_job_id') if options else None
    analysis_id = options.get('analysis_id') if options else None

    # Import here to avoid circular import at module load
    from app.extensions import get_session
    from app.models import ZAPAnalysis
    from app.constants import AnalysisStatus

    try:
        # Engines are stateless; no container start step now
        update_task_progress(0, 100, "Initializing dynamic analysis")

        # Mark RUNNING if an analysis record is provided
        if analysis_id:
            with get_session() as session:
                analysis = session.query(ZAPAnalysis).get(analysis_id)
                if analysis:
                    analysis.status = AnalysisStatus.RUNNING
                    analysis.started_at = datetime.now(timezone.utc)
                    session.commit()

        update_task_progress(10, 100, "Preparing engine")
        update_task_progress(20, 100, "Running dynamic analysis")

        # Run dynamic analysis via engine
        result = _run_engine('dynamic', model_slug, app_number, options=options)

        update_task_progress(80, 100, "Processing dynamic analysis results")
        status = result.get('status', 'completed')

        # Persist results if analysis record provided
        if analysis_id:
            with get_session() as session:
                analysis = session.query(ZAPAnalysis).get(analysis_id)
                if analysis:
                    analysis.status = AnalysisStatus.COMPLETED if status == 'completed' else AnalysisStatus.FAILED
                    analysis.completed_at = datetime.now(timezone.utc)
                    analysis_duration = None
                    if analysis.started_at:
                        # Ensure both datetimes are timezone-aware (UTC)
                        def ensure_aware(dt):
                            if dt is None:
                                return None
                            if dt.tzinfo is None:
                                return dt.replace(tzinfo=timezone.utc)
                            return dt
                        started = ensure_aware(analysis.started_at)
                        completed = ensure_aware(analysis.completed_at)
                        if started and completed:
                            analysis_duration = (completed - started).total_seconds()
                        # Not stored explicitly in ZAPAnalysis; include in metadata if available
                        if analysis_duration is not None:
                            meta = analysis.get_metadata()
                            meta['analysis_duration'] = analysis_duration
                            analysis.set_metadata(meta)
                    # Store raw result JSON
                    try:
                        analysis.set_zap_report(result)
                    except Exception:
                        analysis.set_zap_report({'raw_result': str(result)})

                    # Attempt to map summary counts if present
                    summary = result.get('summary') if isinstance(result, dict) else {}
                    if not isinstance(summary, dict):
                        summary = {}
                    analysis.high_risk_alerts = (summary.get('high') if isinstance(summary, dict) else 0) or (summary.get('high_risk_alerts') if isinstance(summary, dict) else 0) or 0
                    analysis.medium_risk_alerts = (summary.get('medium') if isinstance(summary, dict) else 0) or (summary.get('medium_risk_alerts') if isinstance(summary, dict) else 0) or 0
                    analysis.low_risk_alerts = (summary.get('low') if isinstance(summary, dict) else 0) or (summary.get('low_risk_alerts') if isinstance(summary, dict) else 0) or 0
                    analysis.informational_alerts = (summary.get('informational') if isinstance(summary, dict) else 0) or (summary.get('info') if isinstance(summary, dict) else 0) or 0
                    session.commit()

        final_result = {
            'model_slug': model_slug,
            'app_number': app_number,
            'analysis_type': 'dynamic',
            'result': result,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'status': status,
            'analysis_id': analysis_id
        }

        update_batch_progress(batch_job_id, task_completed=True, result=final_result)
        update_task_progress(100, 100, "Dynamic analysis completed")
        return final_result

    except Exception as e:
        error_msg = f"Dynamic analysis failed: {str(e)}"
        update_task_progress(0, 100, f"Error: {error_msg}")

        # Mark analysis failed before retry
        if analysis_id:
            try:
                with get_session() as session:
                    analysis = session.query(ZAPAnalysis).get(analysis_id)
                    if analysis:
                        analysis.status = AnalysisStatus.FAILED
                        analysis.completed_at = datetime.now(timezone.utc)
                        meta = analysis.get_metadata()
                        meta['last_error'] = str(e)
                        analysis.set_metadata(meta)
                        session.commit()
            except Exception as meta_e:
                print(f"Failed to record failure metadata: {meta_e}")

        update_batch_progress(batch_job_id, task_failed=True)

        # Retry only for transient errors
        transient = any(msg in str(e).lower() for msg in ["timeout", "connection refused", "temporary", "unavailable"]) 
        if transient and getattr(self, 'request', None) and self.request.retries < 3:
            raise self.retry(exc=e, countdown=60, max_retries=3)
        raise

@celery.task(bind=True, name='app.tasks.ai_analysis_task')
def ai_analysis_task(self, model_slug: str, app_number: int,
                    analysis_types: Optional[List[str]] = None, options: Optional[Dict] = None):
    """
    Run AI-powered code analysis on a specific model application.
    
    Args:
        model_slug: Model identifier
        app_number: Application number
        analysis_types: Types of AI analysis to perform
        options: Additional analysis options
    """
    
    # Deprecated placeholder – composite AI engine not yet implemented
    return {
        'status': 'deprecated',
        'message': 'ai_analysis_task deprecated pending composite AI engine implementation',
        'model_slug': model_slug,
        'app_number': app_number,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }

@celery.task(bind=True, name='app.tasks.batch_analysis_task')
def batch_analysis_task(self, models: List[str], apps: List[int],
                       analysis_types: List[str], options: Optional[Dict] = None):
    """
    Run batch analysis across multiple models and applications.
    
    Args:
        models: List of model slugs
        apps: List of application numbers
        analysis_types: Types of analysis to perform
        options: Additional options
    """
    
    return {
        'status': 'deprecated',
        'message': 'batch_analysis_task deprecated – use individual engine tasks or future orchestrator',
        'models': models,
        'apps': apps,
        'analysis_types': analysis_types,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }

# =============================================================================
# CONTAINER MANAGEMENT TASKS
# =============================================================================

@celery.task(bind=True, name='app.tasks.container_management_task')
def container_management_task(self, action: str, service: Optional[str] = None):
    """
    Manage analyzer container operations.
    
    Args:
        action: Action to perform (start, stop, restart, status)
        service: Specific service name (optional)
    """
    
    return {
        'status': 'deprecated',
        'message': f'container_management_task action {action} deprecated – externalized to infra tooling',
        'action': action,
        'service': service,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }

# =============================================================================
# MONITORING TASKS
# =============================================================================

@celery.task(name='app.tasks.health_check_analyzers')
def health_check_analyzers():
    """Periodic health check of analyzer services."""
    
    return {
        'status': 'deprecated',
        'message': 'Analyzer service health check deprecated with engine refactor',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }

@celery.task(name='app.tasks.monitor_analyzer_containers')
def monitor_analyzer_containers():
    """Monitor analyzer container resources and performance."""
    
    return {
        'status': 'deprecated',
        'message': 'Container monitoring deprecated with engine refactor',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }

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
    print(f"Starting task {task.name} with ID {task_id}")
    try:
        # Belt-and-suspenders app context push, but skip if our Task override is handling it
        with _task_ctx_lock:
            managed = task_id in _task_ctx_managed_by_override
        if not managed:
            _push_app_context_for_task(task_id)
    except Exception as e:  # pragma: no cover
        print(f"Warning: task_prerun app context push failed for {task_id}: {e}")

@task_postrun.connect
def task_postrun_handler(task_id, task, retval, state, *args, **kwargs):
    """Handle task post-execution cleanup."""
    print(f"Completed task {task.name} with ID {task_id}, state: {state}")
    try:
        with _task_ctx_lock:
            managed = task_id in _task_ctx_managed_by_override
        if not managed:
            _pop_app_context_for_task(task_id)
    except Exception as e:  # pragma: no cover
        print(f"Warning: task_postrun app context pop failed for {task_id}: {e}")

@worker_ready.connect
def worker_ready_handler(sender, **kwargs):
    """Handle worker ready event."""
    print(f"Celery worker {sender} is ready and connected to analyzer infrastructure")


@celery.task(bind=True, name='app.tasks.run_enhanced_analysis')
def run_enhanced_analysis(self, model_slug: str, app_number: int, config: Dict) -> Dict:
    """
    Run enhanced analysis with custom configuration.
    
    This task orchestrates multiple analyzer services with enhanced configuration
    options for comprehensive testing.
    
    Args:
        model_slug: The model identifier (e.g., 'anthropic_claude-3.5-sonnet')
        app_number: The application number to analyze
        config: Enhanced configuration dict with tool-specific settings
        
    Returns:
        Dict containing analysis results and metadata
    """
    task_id = self.request.id
    print(f"Starting enhanced analysis task {task_id} for {model_slug} app {app_number}")
    
    try:
        # Placeholder composite orchestration – deprecated
        results = {}
        
        # Update task progress
        self.update_state(state='PROGRESS', meta={'stage': 'starting', 'progress': 0})
        
        # Deprecated – no-op sections retained for backward compatibility
        if config.get('static'):
            self.update_state(state='PROGRESS', meta={'stage': 'static_analysis', 'progress': 20})
            results['static_analysis'] = {'status': 'deprecated'}
        if config.get('performance'):
            self.update_state(state='PROGRESS', meta={'stage': 'performance_testing', 'progress': 50})
            results['performance_testing'] = {'status': 'deprecated'}
        if config.get('ai'):
            self.update_state(state='PROGRESS', meta={'stage': 'ai_analysis', 'progress': 80})
            results['ai_analysis'] = {'status': 'deprecated'}
        
        # Compile final results
        self.update_state(state='PROGRESS', meta={'stage': 'finalizing', 'progress': 95})
        
        # Calculate overall scores and summary
        overall_results = {
            'status': 'completed',
            'task_id': task_id,
            'model_slug': model_slug,
            'app_number': app_number,
            'config_used': config,
            'analysis_results': results,
            'completed_at': datetime.now(timezone.utc).isoformat(),
            'summary': _generate_enhanced_summary(results)
        }
        
        # Save results to database
        _save_enhanced_results(overall_results)
        
        print(f"Enhanced analysis task {task_id} completed successfully")
        return overall_results
        
    except Exception as e:
        print(f"Enhanced analysis task {task_id} failed: {e}")
        error_result = {
            'status': 'error',
            'error': str(e),
            'task_id': task_id,
            'model_slug': model_slug,
            'app_number': app_number,
            'failed_at': datetime.now(timezone.utc).isoformat()
        }
        
        # Try to save error to database
        try:
            _save_enhanced_results(error_result)
        except Exception as save_error:
            print(f"Failed to save error results: {save_error}")
        
        # Re-raise for Celery to handle
        raise self.retry(exc=e, countdown=60, max_retries=3)


def _generate_enhanced_summary(results: Dict) -> Dict:
    """Generate summary from enhanced analysis results."""
    summary = {
        'total_analyses': 0,
        'successful_analyses': 0,
        'failed_analyses': 0,
        'overall_score': 0,
        'issues_found': 0,
        'recommendations': []
    }
    
    scores = []
    
    for analysis_type, result in results.items():
        summary['total_analyses'] += 1
        
        if result.get('status') == 'success':
            summary['successful_analyses'] += 1
            
            # Extract scores based on analysis type
            if analysis_type == 'static_analysis':
                if 'bandit' in result and result['bandit'].get('total_issues'):
                    summary['issues_found'] += result['bandit']['total_issues']
                if 'pylint' in result and result['pylint'].get('score'):
                    scores.append(result['pylint']['score'])
                    
            elif analysis_type == 'performance_testing':
                if 'apache_bench' in result and result['apache_bench'].get('requests_per_second'):
                    # Convert RPS to a 0-100 score (normalize based on expected performance)
                    rps = result['apache_bench']['requests_per_second']
                    score = min(100, (rps / 100) * 100)  # 100 RPS = 100% score
                    scores.append(score)
                    
            elif analysis_type == 'ai_analysis':
                if result.get('quality_score'):
                    scores.append(result['quality_score'])
        else:
            summary['failed_analyses'] += 1
    
    # Calculate overall score
    if scores:
        summary['overall_score'] = sum(scores) / len(scores)
    
    # Generate recommendations based on results
    if summary['issues_found'] > 10:
        summary['recommendations'].append('High number of security issues detected - review critical vulnerabilities')
    
    if summary['overall_score'] < 60:
        summary['recommendations'].append('Overall score is below acceptable threshold - consider code improvements')
    
    if summary['failed_analyses'] > 0:
        summary['recommendations'].append('Some analyses failed - check analyzer configuration and connectivity')
    
    return summary


def _save_enhanced_results(results: Dict) -> None:
    """Save enhanced analysis results to database."""
    try:
        from app.extensions import db
        import app.models as _models

        EnhancedAnalysisModel = getattr(_models, 'EnhancedAnalysis', None)
        if EnhancedAnalysisModel is None:
            print("EnhancedAnalysis model not available; skipping DB save")
            return

        # Create enhanced analysis record
        analysis = EnhancedAnalysisModel(
            task_id=results.get('task_id'),
            model_slug=results.get('model_slug'),
            app_number=results.get('app_number'),
            status=results.get('status'),
            config_json=results.get('config_used', {}),
            results_json=results.get('analysis_results', {}),
            summary_json=results.get('summary', {}),
            overall_score=(results.get('summary') or {}).get('overall_score'),
            created_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc) if results.get('status') == 'completed' else None
        )

        db.session.add(analysis)
        db.session.commit()

        print(f"Saved enhanced analysis results for task {results.get('task_id')}")

    except Exception as e:
        print(f"Failed to save enhanced analysis results: {e}")
        # Don't re-raise - this is not critical for task completion


if __name__ == '__main__':
    print("Celery tasks module loaded successfully")
    print(f"Available tasks: {list(celery.tasks.keys())}")
