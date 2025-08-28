"""Analysis Service Layer
=========================

Encapsulates business logic for security analyses and performance tests,
providing a thin, testable abstraction for route handlers.

Phase 1 Scope:
- CRUD-lite + start operations for SecurityAnalysis & PerformanceTest
- Comprehensive security analysis creation convenience
- Recent activity helper
- Results retrieval

Design Principles:
- Return plain dicts (JSON-serializable) for route layer
- Raise domain-specific exceptions for error cases
- Keep orchestration (e.g., Celery task dispatch) narrowly wrapped so it can be mocked in tests

Future Enhancements:
- Batch operations & composite orchestrations
- Caching heavy aggregate queries
- Pydantic validation schemas
- Repository abstraction
"""
from __future__ import annotations

from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from ..extensions import db
from ..models import SecurityAnalysis, PerformanceTest, GeneratedApplication, ZAPAnalysis
from ..constants import AnalysisStatus
from .analysis_engines import get_engine

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class AnalysisServiceError(Exception):
    """Base service error."""

class NotFoundError(AnalysisServiceError):
    """Raised when an entity is not found."""

class ValidationError(AnalysisServiceError):
    """Raised when input validation fails."""

class InvalidStateError(AnalysisServiceError):
    """Raised when an operation is not valid for current state."""

class TaskEnqueueError(AnalysisServiceError):
    """Raised when background task dispatch fails."""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SECURITY_CREATE_REQUIRED = ["application_id"]
PERF_CREATE_REQUIRED = ["application_id", "test_type"]

DEFAULT_SECURITY_FLAGS = {
    "bandit_enabled": True,
    "safety_enabled": True,
    "pylint_enabled": True,
    "eslint_enabled": True,
    "npm_audit_enabled": True,
    "snyk_enabled": False,
    "zap_enabled": False,
    "semgrep_enabled": False,
}

# ---------------------------------------------------------------------------
# Dynamic/ZAP Analysis Operations
# ---------------------------------------------------------------------------

def list_dynamic_analyses(*, application_id: Optional[int] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    query = ZAPAnalysis.query
    if application_id is not None:
        query = query.filter_by(application_id=application_id)
    query = query.order_by(ZAPAnalysis.created_at.desc())
    if limit:
        query = query.limit(limit)
    return [a.to_dict() for a in query.all()]

def create_dynamic_analysis(data: Dict[str, Any]) -> Dict[str, Any]:
    # Target URL can be empty (will be inferred from port mapping if not provided)
    required = ["application_id"]
    missing = [f for f in required if f not in data]
    if missing:
        raise ValidationError(f"Missing required fields: {', '.join(missing)}")

    app = db.session.get(GeneratedApplication, data["application_id"])
    if not app:
        raise ValidationError("Referenced application does not exist")

    analysis = ZAPAnalysis()
    analysis.application_id = data["application_id"]
    analysis.target_url = data.get("target_url", "") or ""
    analysis.scan_type = data.get("scan_type", "baseline")

    # Persist auxiliary options into metadata for traceability
    meta = analysis.get_metadata()
    if "include_paths" in data:
        meta["include_paths"] = data["include_paths"]
    if "exclude_paths" in data:
        meta["exclude_paths"] = data["exclude_paths"]
    if "timeout_minutes" in data:
        meta["timeout_minutes"] = data["timeout_minutes"]
    analysis.set_metadata(meta)

    db.session.add(analysis)
    db.session.commit()
    return analysis.to_dict()

def start_dynamic_analysis(analysis_id: int, *, enqueue: bool = True) -> Dict[str, Any]:
    analysis = db.session.get(ZAPAnalysis, analysis_id)
    if not analysis:
        raise NotFoundError("Dynamic analysis not found")
    if analysis.status not in {AnalysisStatus.PENDING, AnalysisStatus.FAILED}:
        raise InvalidStateError(f"Cannot start analysis in state {analysis.status}")

    analysis.status = AnalysisStatus.RUNNING
    analysis.started_at = datetime.now(timezone.utc)
    db.session.commit()

    task_id = None
    if enqueue:
        try:
            from ..tasks import dynamic_analysis_task  # type: ignore[attr-defined]
            payload = {
                'analysis_id': analysis_id,
                'batch_job_id': None,
                # Use configured timeout from metadata if present (minutes -> seconds)
                'timeout': int((analysis.get_metadata().get('timeout_minutes') or 10) * 60),
            }
            app = db.session.get(GeneratedApplication, analysis.application_id)
            model_slug = app.model_slug if app else ""
            app_number = app.app_number if app else 0
            celery_result = dynamic_analysis_task.delay(model_slug, app_number, payload)  # type: ignore[call-arg]
            task_id = getattr(celery_result, 'id', None)
        except Exception as e:  # noqa: BLE001
            raise TaskEnqueueError(f"Failed to enqueue dynamic analysis task: {e}")

    return {"analysis_id": analysis_id, "status": analysis.status, "task_id": task_id}

def get_dynamic_results(analysis_id: int) -> Dict[str, Any]:
    analysis = db.session.get(ZAPAnalysis, analysis_id)
    if not analysis:
        raise NotFoundError("Dynamic analysis not found")
    return analysis.to_dict()

# ---------------------------------------------------------------------------
# Security Analysis Operations
# ---------------------------------------------------------------------------

def list_security_analyses(*, application_id: Optional[int] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    query = SecurityAnalysis.query
    if application_id is not None:
        query = query.filter_by(application_id=application_id)
    query = query.order_by(SecurityAnalysis.created_at.desc())
    if limit:
        query = query.limit(limit)
    return [a.to_dict() for a in query.all()]

def get_security_analysis(analysis_id: int) -> Dict[str, Any]:
    analysis = db.session.get(SecurityAnalysis, analysis_id)
    if not analysis:
        raise NotFoundError("Security analysis not found")
    return analysis.to_dict()

def create_security_analysis(data: Dict[str, Any]) -> Dict[str, Any]:
    missing = [f for f in SECURITY_CREATE_REQUIRED if f not in data]
    if missing:
        raise ValidationError(f"Missing required fields: {', '.join(missing)}")

    app = db.session.get(GeneratedApplication, data["application_id"])
    if not app:
        raise ValidationError("Referenced application does not exist")

    analysis = SecurityAnalysis()
    analysis.application_id = data["application_id"]
    analysis.analysis_name = data.get("analysis_name", "Security Analysis")
    analysis.description = data.get("description")

    # Flags (default first then override)
    for flag, default in DEFAULT_SECURITY_FLAGS.items():
        setattr(analysis, flag, data.get(flag, default))

    db.session.add(analysis)
    db.session.commit()
    return analysis.to_dict()

def update_security_analysis(analysis_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    analysis = db.session.get(SecurityAnalysis, analysis_id)
    if not analysis:
        raise NotFoundError("Security analysis not found")

    mutable_fields = [
        "analysis_name", "description", "severity_threshold", "max_issues_per_tool",
        "timeout_minutes", "bandit_enabled", "safety_enabled", "pylint_enabled",
        "eslint_enabled", "npm_audit_enabled", "snyk_enabled", "zap_enabled", "semgrep_enabled"
    ]
    for field in mutable_fields:
        if field in data:
            setattr(analysis, field, data[field])

    # Pattern lists
    if "exclude_patterns" in data:
        analysis.set_exclude_patterns(data["exclude_patterns"])
    if "include_patterns" in data:
        analysis.set_include_patterns(data["include_patterns"])

    # Tool-specific configuration dicts
    # Allow clients to pass JSON objects named *_config to override defaults
    if "bandit_config" in data and isinstance(data["bandit_config"], dict):
        analysis.set_bandit_config(data["bandit_config"])
    if "safety_config" in data and isinstance(data["safety_config"], dict):
        analysis.set_safety_config(data["safety_config"])
    if "eslint_config" in data and isinstance(data["eslint_config"], dict):
        analysis.set_eslint_config(data["eslint_config"])
    if "pylint_config" in data and isinstance(data["pylint_config"], dict):
        analysis.set_pylint_config(data["pylint_config"])
    if "zap_config" in data and isinstance(data["zap_config"], dict):
        analysis.set_zap_config(data["zap_config"])
    if "semgrep_config" in data and isinstance(data["semgrep_config"], dict):
        # Not yet modeled separately, but we can store in metadata/global for now
        meta = analysis.get_metadata()
        meta["semgrep_config"] = data["semgrep_config"]
        analysis.set_metadata(meta)
    if "global_config" in data and isinstance(data["global_config"], dict):
        analysis.set_global_config(data["global_config"])

    db.session.commit()
    return analysis.to_dict()

def start_security_analysis(analysis_id: int, *, enqueue: bool = True, use_engine: bool = False) -> Dict[str, Any]:
    analysis = db.session.get(SecurityAnalysis, analysis_id)
    if not analysis:
        raise NotFoundError("Security analysis not found")
    if analysis.status not in {AnalysisStatus.PENDING, AnalysisStatus.FAILED}:
        raise InvalidStateError(f"Cannot start analysis in state {analysis.status}")

    analysis.status = AnalysisStatus.RUNNING
    analysis.started_at = datetime.now(timezone.utc)
    db.session.commit()

    task_id = None
    if enqueue and not use_engine:
        # Legacy celery dispatch path retained for compatibility
        try:
            from ..tasks import run_security_analysis  # type: ignore
            celery_result = run_security_analysis.delay(analysis_id)  # type: ignore[attr-defined]
            task_id = getattr(celery_result, 'id', None)
        except Exception as e:  # noqa: BLE001
            raise TaskEnqueueError(f"Failed to enqueue security analysis task: {e}")
    elif use_engine:
        # Immediate engine invocation (synchronous) for simplified flows / tests
        app = db.session.get(GeneratedApplication, analysis.application_id)
        if app:
            engine = get_engine('security')
            engine_result = engine.run(app.model_slug, app.app_number)
            # Optionally persist quick result metadata (tools run count) if provided
            payload = engine_result.payload or {}
            meta = analysis.get_metadata()
            meta['engine_invocation'] = True
            if 'tools' in payload:
                meta['engine_tools'] = payload['tools']
            analysis.set_metadata(meta)
            db.session.commit()

    return {"analysis_id": analysis_id, "status": analysis.status, "task_id": task_id, "engine": 'security' if use_engine else None}

def create_comprehensive_security_analysis(application_id: int, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = payload or {}
    payload["application_id"] = application_id
    # Force-enable all tools for comprehensive scan
    for flag in DEFAULT_SECURITY_FLAGS.keys():
        payload.setdefault(flag, True)
    payload.setdefault("analysis_name", "Comprehensive Security Analysis")
    return create_security_analysis(payload)

def start_comprehensive_analysis(application_id: int) -> Dict[str, Any]:
    # Create (if not existing pending) then start comprehensive scan
    existing = SecurityAnalysis.query.filter_by(application_id=application_id, analysis_name="Comprehensive Security Analysis").order_by(SecurityAnalysis.created_at.desc()).first()
    if existing and existing.status in {AnalysisStatus.PENDING, AnalysisStatus.FAILED}:
        target_id = existing.id
    else:
        created = create_comprehensive_security_analysis(application_id, {})
        target_id = created["id"]
    return start_security_analysis(target_id)

def get_analysis_results(analysis_id: int) -> Dict[str, Any]:
    analysis = db.session.get(SecurityAnalysis, analysis_id)
    if not analysis:
        raise NotFoundError("Security analysis not found")
    return {
        "id": analysis.id,
    "status": analysis.status,
        "results": analysis.get_results(),
        "summary": {
            "total_issues": analysis.total_issues,
            "critical": analysis.critical_severity_count,
            "high": analysis.high_severity_count,
            "medium": analysis.medium_severity_count,
            "low": analysis.low_severity_count,
            "tools_run": analysis.tools_run_count,
            "tools_failed": analysis.tools_failed_count,
            "duration": analysis.analysis_duration,
        }
    }

# ---------------------------------------------------------------------------
# Performance Test Operations
# ---------------------------------------------------------------------------

def list_performance_tests(*, application_id: Optional[int] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    query = PerformanceTest.query
    if application_id is not None:
        query = query.filter_by(application_id=application_id)
    query = query.order_by(PerformanceTest.created_at.desc())
    if limit:
        query = query.limit(limit)
    return [t.to_dict() for t in query.all()]

def get_performance_test(test_id: int) -> Dict[str, Any]:
    test = db.session.get(PerformanceTest, test_id)
    if not test:
        raise NotFoundError("Performance test not found")
    return test.to_dict()

def create_performance_test(data: Dict[str, Any]) -> Dict[str, Any]:
    missing = [f for f in PERF_CREATE_REQUIRED if f not in data]
    if missing:
        raise ValidationError(f"Missing required fields: {', '.join(missing)}")

    app = db.session.get(GeneratedApplication, data["application_id"])
    if not app:
        raise ValidationError("Referenced application does not exist")

    test = PerformanceTest()
    test.application_id = data["application_id"]
    test.test_type = data.get("test_type", "load")
    test.users = data.get("users", 10)
    test.spawn_rate = data.get("spawn_rate", 1.0)
    test.test_duration = data.get("test_duration", 60)

    db.session.add(test)
    db.session.commit()
    return test.to_dict()

def start_performance_test(test_id: int, *, use_engine: bool = False) -> Dict[str, Any]:
    test = db.session.get(PerformanceTest, test_id)
    if not test:
        raise NotFoundError("Performance test not found")
    if test.status not in {AnalysisStatus.PENDING, AnalysisStatus.FAILED}:
        raise InvalidStateError(f"Cannot start test in state {test.status}")

    test.status = AnalysisStatus.RUNNING
    test.started_at = datetime.now(timezone.utc)
    db.session.commit()

    engine_payload = None
    if use_engine:
        app = db.session.get(GeneratedApplication, test.application_id)
        if app:
            engine = get_engine('performance')
            engine_result = engine.run(app.model_slug, app.app_number, test_config={
                'users': test.users,
                'duration': test.test_duration,
            })
            engine_payload = engine_result.payload
            meta = test.get_metadata() if hasattr(test, 'get_metadata') else {}
            if isinstance(meta, dict):
                meta['engine_invocation'] = True
                test.set_metadata(meta) if hasattr(test, 'set_metadata') else None  # type: ignore[attr-defined]
            db.session.commit()

    return {"test_id": test_id, "status": test.status, "engine": 'performance' if use_engine else None, "engine_payload": engine_payload}

# ---------------------------------------------------------------------------
# Activity Helpers
# ---------------------------------------------------------------------------

def get_recent_activity(limit: int = 5) -> Dict[str, Any]:
    security = SecurityAnalysis.query.order_by(SecurityAnalysis.created_at.desc()).limit(limit).all()
    perf = PerformanceTest.query.order_by(PerformanceTest.created_at.desc()).limit(limit).all()
    return {
        "security": [a.to_dict() for a in security],
        "performance": [t.to_dict() for t in perf]
    }

__all__ = [
    'AnalysisServiceError', 'NotFoundError', 'ValidationError', 'InvalidStateError', 'TaskEnqueueError',
    'list_security_analyses', 'get_security_analysis', 'create_security_analysis', 'update_security_analysis',
    'start_security_analysis', 'create_comprehensive_security_analysis', 'start_comprehensive_analysis', 'get_analysis_results',
    'list_performance_tests', 'get_performance_test', 'create_performance_test', 'start_performance_test',
    'get_recent_activity',
    'list_dynamic_analyses', 'create_dynamic_analysis', 'start_dynamic_analysis', 'get_dynamic_results'
]
