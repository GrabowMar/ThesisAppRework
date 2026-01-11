"""
Dashboard Service
=================

Service layer for aggregating dashboard metrics, system health status, and recent activity.

This module provides functions to build dashboard payloads including:
- Summary statistics with temporal deltas (24h, 7d)
- System component health checks (database, Redis, Celery, analyzers)
- Recent activity feeds across multiple analysis types
- Application and analysis summaries

The service performs lightweight health checks with configurable timeouts to avoid
blocking the dashboard UI on slow or unavailable components.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import socket

from sqlalchemy import func
from flask import current_app

from app.extensions import db
from app.models import (
    AnalysisStatus,
    BatchAnalysis,
    GeneratedApplication,
    ModelCapability,
    PerformanceTest,
    SecurityAnalysis,
)


@dataclass
class ComponentStatus:
    key: str
    label: str
    status: str
    message: str
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "status": self.status,
            "message": self.message,
            "details": self.details or {},
        }


def build_summary_payload() -> Dict[str, Any]:
    """Return aggregate counts and recent deltas for dashboard metrics."""
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)

    def _count(query) -> int:
        value = query.scalar()
        return int(value or 0)

    totals = {
        "models": _count(db.session.query(func.count(ModelCapability.id))),
        "applications": _count(db.session.query(func.count(GeneratedApplication.id))),
        "security": _count(db.session.query(func.count(SecurityAnalysis.id))),
        "performance": _count(db.session.query(func.count(PerformanceTest.id))),
    }

    last_24h = {
        "applications": _count(
            db.session.query(func.count(GeneratedApplication.id))
            .filter(GeneratedApplication.created_at >= day_ago)
        ),
        "security": _count(
            db.session.query(func.count(SecurityAnalysis.id))
            .filter(SecurityAnalysis.created_at >= day_ago)
        ),
        "performance": _count(
            db.session.query(func.count(PerformanceTest.id))
            .filter(PerformanceTest.created_at >= day_ago)
        ),
    }

    last_7d = {
        "applications": _count(
            db.session.query(func.count(GeneratedApplication.id))
            .filter(GeneratedApplication.created_at >= week_ago)
        ),
        "security": _count(
            db.session.query(func.count(SecurityAnalysis.id))
            .filter(SecurityAnalysis.created_at >= week_ago)
        ),
        "performance": _count(
            db.session.query(func.count(PerformanceTest.id))
            .filter(PerformanceTest.created_at >= week_ago)
        ),
    }

    return {
        "generated_at": now.isoformat(),
        "totals": totals,
        "recent": {
            "last_24h": last_24h,
            "last_7d": last_7d,
        },
    }


def build_system_status_payload() -> Dict[str, Any]:
    """Return a lightweight health snapshot for core services."""
    statuses: List[ComponentStatus] = []

    statuses.append(_database_status())
    statuses.append(_redis_status())
    statuses.append(_celery_status())
    statuses.extend(_analyzer_statuses())

    # Determine overall health – degraded if any component is degraded/unhealthy
    severity_order = {"error": 3, "unhealthy": 3, "degraded": 2, "warning": 1, "healthy": 0, "unknown": 1, "not_configured": 0}
    worst = max((severity_order.get(c.status, 1) for c in statuses), default=0)
    overall = "healthy"
    if worst >= 3:
        overall = "unhealthy"
    elif worst == 2:
        overall = "degraded"
    elif worst == 1:
        overall = "warning"

    return {
        "overall": overall,
        "components": [c.to_dict() for c in statuses],
    }


def get_recent_activity_entries(limit: int = 8) -> List[Dict[str, Any]]:
    """Return a merged list of recent analyses and batch events."""
    now = datetime.now(timezone.utc)

    def _normalize_status(status: Any) -> str:
        if isinstance(status, AnalysisStatus):
            return status.value
        if isinstance(status, str):
            return status
        try:
            return status.name  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - defensive
            return "unknown"

    entries: List[Dict[str, Any]] = []

    security_items = (
        db.session.query(SecurityAnalysis)
        .order_by(SecurityAnalysis.created_at.desc())
        .limit(limit)
        .all()
    )
    for analysis in security_items:
        timestamp = analysis.completed_at or analysis.started_at or analysis.created_at or now
        entries.append({
            "type": "security",
            "title": analysis.analysis_name or "Security Analysis",
            "status": _normalize_status(getattr(analysis, "status", None)),
            "timestamp": timestamp,
            "meta": {
                "issues": getattr(analysis, "total_issues", None),
                "application_id": analysis.application_id,
            },
        })

    performance_items = (
        db.session.query(PerformanceTest)
        .order_by(PerformanceTest.created_at.desc())
        .limit(limit)
        .all()
    )
    for test in performance_items:
        timestamp = test.completed_at or test.started_at or test.created_at or now
        entries.append({
            "type": "performance",
            "title": f"Performance test #{test.id}",
            "status": _normalize_status(getattr(test, "status", None)),
            "timestamp": timestamp,
            "meta": {
                "rps": getattr(test, "requests_per_second", None),
                "error_rate": getattr(test, "error_rate", None),
                "application_id": test.application_id,
            },
        })

    batch_items = (
        db.session.query(BatchAnalysis)
        .order_by(BatchAnalysis.created_at.desc())
        .limit(limit)
        .all()
    )
    for batch in batch_items:
        timestamp = batch.completed_at or batch.created_at or now
        entries.append({
            "type": "batch",
            "title": f"Batch #{batch.id}",
            "status": _normalize_status(getattr(batch, "status", None)),
            "timestamp": timestamp,
            "meta": {
                "items": getattr(batch, "total_jobs", None),
            },
        })

    entries.sort(key=lambda item: item["timestamp"] or now, reverse=True)
    return entries[:limit]


def get_recent_applications(limit: int = 6) -> List[Dict[str, Any]]:
    rows = (
        db.session.query(GeneratedApplication)
        .order_by(GeneratedApplication.created_at.desc())
        .limit(limit)
        .all()
    )
    result: List[Dict[str, Any]] = []
    for app_obj in rows:
        result.append({
            "id": app_obj.id,
            "model_slug": app_obj.model_slug,
            "app_number": app_obj.app_number,
            "app_type": app_obj.app_type,
            "framework": app_obj.backend_framework or "Unknown",
            "created_at": app_obj.created_at,
            "status": getattr(app_obj, "container_status", None) or "unknown",
        })
    return result


def get_recent_analysis_summary(limit: int = 5) -> List[Dict[str, Any]]:
    security = (
        db.session.query(SecurityAnalysis)
        .order_by(SecurityAnalysis.created_at.desc())
        .limit(limit)
        .all()
    )
    performance = (
        db.session.query(PerformanceTest)
        .order_by(PerformanceTest.created_at.desc())
        .limit(limit)
        .all()
    )

    def _make_entry(obj: Any, category: str) -> Dict[str, Any]:
        status = getattr(obj, "status", None)
        if isinstance(status, AnalysisStatus):
            status_value = status.value
        elif isinstance(status, str):
            status_value = status
        else:
            status_value = getattr(status, "name", "unknown")
        return {
            "id": obj.id,
            "category": category,
            "application_id": obj.application_id,
            "status": status_value,
            "created_at": getattr(obj, "created_at", None),
            "completed_at": getattr(obj, "completed_at", None),
        }

    combined = [_make_entry(item, "security") for item in security]
    combined.extend(_make_entry(item, "performance") for item in performance)
    combined.sort(key=lambda entry: entry.get("completed_at") or entry.get("created_at") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return combined[:limit]


def _database_status() -> ComponentStatus:
    try:
        db.session.execute(db.text("SELECT 1"))
        return ComponentStatus(
            key="database",
            label="Database",
            status="healthy",
            message="Connected",
        )
    except Exception as exc:  # pragma: no cover - defensive
        return ComponentStatus(
            key="database",
            label="Database",
            status="unhealthy",
            message=f"Error: {exc}",
        )


def _redis_status() -> ComponentStatus:
    redis_url = (
        current_app.config.get("REDIS_URL")
        or current_app.config.get("CELERY_BROKER_URL")
        or current_app.config.get("CELERY_RESULT_BACKEND")
    )
    if not redis_url:
        return ComponentStatus(
            key="redis",
            label="Redis",
            status="not_configured",
            message="Redis URL not configured",
        )

    try:
        import redis  # type: ignore

        client: Any = redis.Redis.from_url(
            redis_url,
            socket_connect_timeout=1.5,
            socket_timeout=1.5,
        )
        client.ping()
        return ComponentStatus(
            key="redis",
            label="Redis",
            status="healthy",
            message="Responding",
        )
    except Exception as exc:  # pragma: no cover - best effort
        return ComponentStatus(
            key="redis",
            label="Redis",
            status="degraded",
            message=f"Ping failed: {exc}",
        )


def _celery_status() -> ComponentStatus:
    """Check Celery worker status by pinging the broker."""
    import os
    
    # Check if Celery is enabled
    use_celery = os.environ.get("USE_CELERY_ANALYSIS", "false").lower() == "true"
    if not use_celery:
        return ComponentStatus(
            key="celery",
            label="Celery",
            status="not_configured",
            message="Celery disabled (USE_CELERY_ANALYSIS=false)",
        )
    
    # Get broker URL
    broker_url = (
        os.environ.get("CELERY_BROKER_URL")
        or current_app.config.get("CELERY_BROKER_URL")
    )
    if not broker_url:
        return ComponentStatus(
            key="celery",
            label="Celery",
            status="not_configured",
            message="CELERY_BROKER_URL not configured",
        )
    
    try:
        # Try to connect to broker and check for workers
        from celery import Celery
        celery_app = Celery(broker=broker_url)
        
        try:
            # Quick ping with short timeout
            inspect = celery_app.control.inspect(timeout=2.0)
            stats = inspect.stats() if inspect else None
        except Exception:
            stats = None
        
        if stats:
            return ComponentStatus(
                key="celery",
                label="Celery",
                status="healthy",
                message=f"{len(stats)} worker(s) online",
            )
        return ComponentStatus(
            key="celery",
            label="Celery",
            status="degraded",
            message="No workers responding",
        )
    except ImportError:
        return ComponentStatus(
            key="celery",
            label="Celery",
            status="warning",
            message="Celery package not installed",
        )
    except Exception as exc:  # pragma: no cover - defensive
        return ComponentStatus(
            key="celery",
            label="Celery",
            status="warning",
            message=f"Check failed: {exc}",
        )


def _analyzer_statuses() -> List[ComponentStatus]:
    """Check analyzer service connectivity.
    
    In Docker environments, each analyzer runs in its own container with its own hostname.
    The service key (e.g., 'static-analyzer') matches the Docker service name.
    """
    services = [
        {"key": "static-analyzer", "label": "Static Analyzer", "port": 2001},
        {"key": "dynamic-analyzer", "label": "Dynamic Analyzer", "port": 2002},
        {"key": "performance-tester", "label": "Performance Tester", "port": 2003},
        {"key": "ai-analyzer", "label": "AI Analyzer", "port": 2004},
    ]
    timeout = float(current_app.config.get("DASHBOARD_ANALYZER_TIMEOUT", 2.0))
    
    import os
    # Check if we're in Docker by looking for common Docker environment indicators
    in_docker = (
        os.path.exists("/.dockerenv") 
        or os.environ.get("DOCKER_CONTAINER") == "true"
        or os.environ.get("IN_DOCKER") == "true"
    )
    
    # In Docker, use the service name as the host (Docker DNS resolution)
    # For local dev, use ANALYZER_HOST env var or fallback to localhost
    default_host = os.environ.get("ANALYZER_HOST") or current_app.config.get("DASHBOARD_ANALYZER_HOST", "127.0.0.1")

    results: List[ComponentStatus] = []
    for svc in services:
        port = svc["port"]
        label = svc["label"]
        service_key = svc["key"]
        
        # In Docker, use the service name as host; otherwise use default_host
        if in_docker:
            host = service_key  # e.g., "static-analyzer"
        else:
            host = default_host
        
        try:
            with socket.create_connection((host, port), timeout=timeout):
                results.append(
                    ComponentStatus(
                        key=service_key,
                        label=label,
                        status="healthy",
                        message=f"Port {port} reachable",
                    )
                )
        except OSError as e:
            results.append(
                ComponentStatus(
                    key=service_key,
                    label=label,
                    status="warning",
                    message=f"No response ({host}:{port})",
                )
            )
    return results
