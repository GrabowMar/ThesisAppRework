"""Statistics Service Layer
=========================

Provides aggregation logic for application, model, and analysis statistics.
Extracted from verbose route implementations to enable reuse and testing.

Design Notes:
- Each public function returns plain dictionaries (JSON-ready)
- No Flask request context assumptions
- Expensive queries gathered here for potential future caching

Future Enhancements:
- Add caching (Redis) for heavy aggregation (distribution, trends)
- Parameterize time windows
- Support pagination for large ranking sets
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
from sqlalchemy import func, desc

from ..extensions import db
from ..models import GeneratedApplication, ModelCapability, SecurityAnalysis, PerformanceTest

# ---------------------------------------------------------------------------
# Core Aggregations
# ---------------------------------------------------------------------------

def get_application_statistics() -> Dict[str, Any]:
    total = db.session.query(func.count(GeneratedApplication.id)).scalar() or 0

    by_status_rows = (
        db.session.query(
            GeneratedApplication.generation_status,
            func.count(GeneratedApplication.id)
        ).group_by(GeneratedApplication.generation_status).all()
    )
    by_status = [
        {"status": str(status) if status is not None else None, "count": count}
        for status, count in by_status_rows
    ]

    by_type_rows = (
        db.session.query(
            GeneratedApplication.app_type,
            func.count(GeneratedApplication.id)
        ).group_by(GeneratedApplication.app_type).all()
    )
    by_type = [
        {"type": app_type, "count": count} for app_type, count in by_type_rows
    ]

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    recent_count = (
        db.session.query(func.count(GeneratedApplication.id))
        .filter(GeneratedApplication.created_at >= week_ago)
        .scalar() or 0
    )

    return {
        "total": total,
        "by_status": by_status,
        "by_type": by_type,
        "recent_count": recent_count,
    }

def get_model_statistics() -> Dict[str, Any]:
    total = db.session.query(func.count(ModelCapability.id)).scalar() or 0

    provider_rows = (
        db.session.query(
            ModelCapability.provider,
            func.count(ModelCapability.id)
        ).group_by(ModelCapability.provider).all()
    )
    by_provider = [
        {"provider": provider, "count": count} for provider, count in provider_rows
    ]

    # Map to actual boolean capability columns present on ModelCapability
    capability_fields = {
        'function_calling': 'supports_function_calling',
        'vision': 'supports_vision',
        'streaming': 'supports_streaming',
        'json_mode': 'supports_json_mode',
    }
    by_capability = {}
    for label, attr in capability_fields.items():
        column_attr = getattr(ModelCapability, attr)
        count = db.session.query(func.count(ModelCapability.id)).filter(column_attr.is_(True)).scalar() or 0
        by_capability[label] = count

    return {
        "total": total,
        "by_provider": by_provider,
        "by_capability": by_capability,
    }

def get_analysis_statistics() -> Dict[str, Any]:
    security_total = db.session.query(func.count(SecurityAnalysis.id)).scalar() or 0
    security_completed = (
        db.session.query(func.count(SecurityAnalysis.id))
        .filter(SecurityAnalysis.status == 'completed')
        .scalar() or 0
    )

    perf_total = db.session.query(func.count(PerformanceTest.id)).scalar() or 0
    perf_completed = (
        db.session.query(func.count(PerformanceTest.id))
        .filter(PerformanceTest.status == 'completed')
        .scalar() or 0
    )

    def rate(total: int, completed: int) -> float:
        return round((completed / total * 100), 2) if total > 0 else 0.0

    return {
        "security": {
            "total": security_total,
            "completed": security_completed,
            "success_rate": rate(security_total, security_completed)
        },
        "performance": {
            "total": perf_total,
            "completed": perf_completed,
            "success_rate": rate(perf_total, perf_completed)
        }
    }

def get_recent_statistics() -> Dict[str, Any]:
    day_ago = datetime.now(timezone.utc) - timedelta(days=1)
    recent_apps = db.session.query(func.count(GeneratedApplication.id)).filter(GeneratedApplication.created_at >= day_ago).scalar() or 0
    recent_security = db.session.query(func.count(SecurityAnalysis.id)).filter(SecurityAnalysis.created_at >= day_ago).scalar() or 0
    recent_perf = db.session.query(func.count(PerformanceTest.id)).filter(PerformanceTest.created_at >= day_ago).scalar() or 0

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    popular_models_rows = (
        db.session.query(
            GeneratedApplication.model_slug,
            func.count(GeneratedApplication.id).label('usage_count')
        ).filter(GeneratedApplication.created_at >= week_ago)
         .group_by(GeneratedApplication.model_slug)
         .order_by(desc('usage_count'))
         .limit(5)
         .all()
    )
    popular_models = [
        {"model_slug": slug, "usage_count": count}
        for slug, count in popular_models_rows
    ]

    return {
        "last_24h": {
            "applications": recent_apps,
            "security_analyses": recent_security,
            "performance_tests": recent_perf,
        },
        "popular_models": popular_models,
    }

def get_model_distribution() -> Dict[str, Any]:
    provider_rows = db.session.query(
        ModelCapability.provider,
        func.count(ModelCapability.id)
    ).group_by(ModelCapability.provider).all()

    capabilities = {
        'function_calling': db.session.query(ModelCapability).filter(ModelCapability.supports_function_calling).count(),
        'vision': db.session.query(ModelCapability).filter(ModelCapability.supports_vision).count(),
        'streaming': db.session.query(ModelCapability).filter(ModelCapability.supports_streaming).count(),
        'json_mode': db.session.query(ModelCapability).filter(ModelCapability.supports_json_mode).count(),
    }

    free_models = db.session.query(ModelCapability).filter(ModelCapability.is_free).count()
    paid_models = db.session.query(ModelCapability).filter(~ModelCapability.is_free).count()

    return {
        'providers': [{"provider": p, "count": c} for p, c in provider_rows],
        'capabilities': capabilities,
        'cost_distribution': {"free": free_models, "paid": paid_models},
    }

def get_generation_trends(days: int = 30) -> Dict[str, Any]:
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days)
    daily_data: List[Dict[str, Any]] = []
    current = start_date
    while current <= end_date:
        count = db.session.query(func.count(GeneratedApplication.id)).filter(
            func.date(GeneratedApplication.created_at) == current
        ).scalar() or 0
        daily_data.append({"date": current.isoformat(), "applications": count})
        current += timedelta(days=1)
    return {
        "daily_trends": daily_data,
        "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
    }

def get_analysis_summary() -> Dict[str, Any]:
    security_count = db.session.query(func.count(SecurityAnalysis.id)).scalar() or 0
    performance_count = db.session.query(func.count(PerformanceTest.id)).scalar() or 0
    security_success = db.session.query(func.count(SecurityAnalysis.id)).filter(SecurityAnalysis.status == 'completed').scalar() or 0
    performance_success = db.session.query(func.count(PerformanceTest.id)).filter(PerformanceTest.status == 'completed').scalar() or 0

    def rate(success: int, total: int) -> float:
        return (success / total * 100) if total > 0 else 0.0

    return {
        'security_analyses': {
            'total': security_count,
            'successful': security_success,
            'success_rate': rate(security_success, security_count),
        },
        'performance_tests': {
            'total': performance_count,
            'successful': performance_success,
            'success_rate': rate(performance_success, performance_count),
        },
        'total_analyses': security_count + performance_count,
    }

def export_statistics(days: int = 30) -> Dict[str, Any]:
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    return {
        'export_info': {
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'period_start': start_date.isoformat(),
            'period_end': datetime.now(timezone.utc).isoformat(),
        },
        'models': {
            'total': db.session.query(func.count(ModelCapability.id)).scalar() or 0,
            'by_provider': dict(db.session.query(ModelCapability.provider, func.count(ModelCapability.id)).group_by(ModelCapability.provider).all()),
        },
        'applications': {
            'total': db.session.query(func.count(GeneratedApplication.id)).scalar() or 0,
            'recent': db.session.query(func.count(GeneratedApplication.id)).filter(GeneratedApplication.created_at >= start_date).scalar() or 0,
        },
        'analyses': {
            'security': db.session.query(func.count(SecurityAnalysis.id)).scalar() or 0,
            'performance': db.session.query(func.count(PerformanceTest.id)).scalar() or 0,
        },
    }


def get_generation_statistics_by_models(model_slugs: List[str]) -> Dict[str, Any]:
    """Get generation statistics for specific models."""
    from ..models import AnalysisStatus
    
    stats = []
    for model_slug in model_slugs:
        # Total runs for this model
        total_runs = db.session.query(func.count(GeneratedApplication.id)).filter(
            GeneratedApplication.model_slug == model_slug
        ).scalar() or 0
        
        # Successful runs (completed status)
        successful_runs = db.session.query(func.count(GeneratedApplication.id)).filter(
            GeneratedApplication.model_slug == model_slug,
            GeneratedApplication.generation_status == AnalysisStatus.COMPLETED
        ).scalar() or 0
        
        # Get metadata for token and cost calculations
        apps = db.session.query(GeneratedApplication).filter(
            GeneratedApplication.model_slug == model_slug
        ).all()
        
        total_tokens = 0
        total_cost = 0.0
        
        for app in apps:
            metadata = app.get_metadata()
            if metadata:
                # Try to extract token usage and cost from metadata
                total_tokens += metadata.get('total_tokens', 0) or metadata.get('tokens', 0) or 0
                total_cost += float(metadata.get('cost', 0) or metadata.get('total_cost', 0) or 0)
        
        stats.append({
            'model_slug': model_slug,
            'total_runs': total_runs,
            'successful_runs': successful_runs,
            'total_tokens': total_tokens,
            'total_cost': total_cost
        })
    
    return {'stats': stats}


__all__ = [
    'get_application_statistics', 'get_model_statistics', 'get_analysis_statistics', 'get_recent_statistics',
    'get_model_distribution', 'get_generation_trends', 'get_analysis_summary', 'export_statistics',
    'get_generation_statistics_by_models'
]
