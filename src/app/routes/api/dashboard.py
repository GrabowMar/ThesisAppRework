"""
Dashboard API routes
====================

Endpoints for dashboard overview, statistics, and HTMX fragments.
"""

from flask import Blueprint, current_app
from datetime import datetime, timezone, timedelta

from app.extensions import db
from app.models import (
    ModelCapability, GeneratedApplication, SecurityAnalysis, 
    PerformanceTest, BatchAnalysis
)
from app.services.statistics_service import (
    get_application_statistics, get_model_statistics, get_analysis_statistics,
    get_recent_statistics, get_model_distribution, get_generation_trends,
    get_analysis_summary, export_statistics
)
from .common import api_success, api_error


dashboard_bp = Blueprint('dashboard_api', __name__)


@dashboard_bp.route('/overview')
def api_dashboard_overview():
    """Get dashboard overview data."""
    try:
        # Total counts
        total_apps = db.session.query(db.func.count(GeneratedApplication.id)).scalar()
        total_models = db.session.query(db.func.count(ModelCapability.id)).scalar()
        total_security = db.session.query(db.func.count(SecurityAnalysis.id)).scalar()
        total_performance = db.session.query(db.func.count(PerformanceTest.id)).scalar()

        # Recent activity (last 7 days)
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        recent_apps = (
            db.session.query(db.func.count(GeneratedApplication.id))
            .filter(GeneratedApplication.created_at >= week_ago)
            .scalar()
        )

        # Active applications
        active_apps = (
            db.session.query(db.func.count(GeneratedApplication.id))
            .filter(GeneratedApplication.container_status == 'running')
            .scalar()
        )

        # Success rates
        completed_security = (
            db.session.query(db.func.count(SecurityAnalysis.id))
            .filter(SecurityAnalysis.status == 'completed')
            .scalar()
        )
        security_rate = (completed_security / total_security * 100) if total_security > 0 else 0

        completed_performance = (
            db.session.query(db.func.count(PerformanceTest.id))
            .filter(PerformanceTest.status == 'completed')
            .scalar()
        )
        performance_rate = (completed_performance / total_performance * 100) if total_performance > 0 else 0

        return api_success({
            'totals': {
                'applications': total_apps,
                'models': total_models,
                'security_analyses': total_security,
                'performance_tests': total_performance
            },
            'activity': {
                'recent_applications': recent_apps,
                'active_applications': active_apps
            },
            'success_rates': {
                'security': round(security_rate, 2),
                'performance': round(performance_rate, 2)
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error getting dashboard overview: {e}")
        return api_error("Failed to retrieve dashboard overview", details={"reason": str(e)})


@dashboard_bp.route('/stats')
def api_dashboard_stats():
    """Enhanced dashboard statistics."""
    try:
        # Basic counts
        models_count = ModelCapability.query.count()
        apps_count = GeneratedApplication.query.count()
        security_count = SecurityAnalysis.query.count()
        performance_count = PerformanceTest.query.count()

        # Provider breakdown
        provider_stats = db.session.query(
            ModelCapability.provider,
            db.func.count(ModelCapability.id).label('count')
        ).group_by(ModelCapability.provider).all()

        # Application framework breakdown
        framework_stats = db.session.query(
            GeneratedApplication.backend_framework,
            db.func.count(GeneratedApplication.id).label('count')
        ).group_by(GeneratedApplication.backend_framework).all()

        # Recent activity
        recent_models = ModelCapability.query.order_by(
            ModelCapability.created_at.desc()
        ).limit(5).all()

        recent_apps = GeneratedApplication.query.order_by(
            GeneratedApplication.created_at.desc()
        ).limit(5).all()

        return api_success({
            'counts': {
                'models': models_count,
                'applications': apps_count,
                'security_tests': security_count,
                'performance_tests': performance_count
            },
            'providers': [{'name': p[0], 'count': p[1]} for p in provider_stats],
            'frameworks': [{'name': f[0] or 'Unknown', 'count': f[1]} for f in framework_stats],
            'recent_models': [m.to_dict() for m in recent_models],
            'recent_apps': [a.to_dict() for a in recent_apps],
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

    except Exception as e:
        current_app.logger.error(f"Error getting dashboard stats: {e}")
        return api_error("Failed to retrieve dashboard stats", details={"reason": str(e)})


@dashboard_bp.route('/sidebar_stats')
def sidebar_stats():
    """HTMX endpoint for sidebar statistics."""
    try:
        from app.utils.template_paths import render_template_compat as render_template
        stats = {
            'total_models': db.session.query(ModelCapability).count(),
            'total_apps': db.session.query(GeneratedApplication).count(),
            'security_tests': db.session.query(SecurityAnalysis).count(),
            'performance_tests': db.session.query(PerformanceTest).count()
        }
        return render_template('partials/common/_sidebar_stats_inner.html', stats=stats)
    except Exception as e:
        current_app.logger.error(f"Error getting sidebar stats: {e}")
        from app.utils.template_paths import render_template_compat as render_template
        return render_template('partials/common/_sidebar_stats_inner.html', stats={
            'total_models': 0, 'total_apps': 0, 'security_tests': 0, 'performance_tests': 0
        })


@dashboard_bp.route('/stats-fragment')
def dashboard_stats_fragment():
    """HTMX endpoint returning dashboard stats inner fragment HTML."""
    try:
        stats = {
            'total_models': db.session.query(ModelCapability).count(),
            'total_apps': db.session.query(GeneratedApplication).count(),
            'security_tests': db.session.query(SecurityAnalysis).count(),
            'performance_tests': db.session.query(PerformanceTest).count(),
        }
        # Return inline HTML fragment (removed external template dependency)
        return (
            '<div class="row g-3">'
            f'<div class="col-6 col-md-3"><div class="card text-center stat-card"><div class="card-body py-3">'
            f'<div class="h4 mb-0">{stats["total_models"]}</div><div class="text-muted small">Models</div>'
            '</div></div></div>'
            f'<div class="col-6 col-md-3"><div class="card text-center stat-card"><div class="card-body py-3">'
            f'<div class="h4 mb-0">{stats["total_apps"]}</div><div class="text-muted small">Apps</div>'
            '</div></div></div>'
            f'<div class="col-6 col-md-3"><div class="card text-center stat-card"><div class="card-body py-3">'
            f'<div class="h4 mb-0">{stats["security_tests"]}</div><div class="text-muted small">Security</div>'
            '</div></div></div>'
            f'<div class="col-6 col-md-3"><div class="card text-center stat-card"><div class="card-body py-3">'
            f'<div class="h4 mb-0">{stats["performance_tests"]}</div><div class="text-muted small">Perf</div>'
            '</div></div></div>'
            '</div>'
        )
    except Exception as e:
        current_app.logger.error(f"Error rendering dashboard stats fragment: {e}")
        return (
            '<div class="row g-3">'
            '<div class="col-12 text-muted small">Stats unavailable</div>'
            '</div>'
        )


@dashboard_bp.route('/system-health-fragment')
def dashboard_system_health_fragment():
    """Return small system health fragment."""
    try:
        from app.utils.template_paths import render_template_compat as render_template
        health = {
            'status': 'healthy',
            'uptime_minutes': 0,
            'active_tasks': 0,
        }
        return render_template('pages/system/partials/_system_health_inner.html', health=health)
    except Exception as e:
        current_app.logger.error(f"Error rendering system health: {e}")
        return '<div class="text-muted small">Health unavailable</div>'


@dashboard_bp.route('/analyzer-services')
def dashboard_analyzer_services():
    """Return analyzer services status cards."""
    try:
        services = [
            {'name': 'Security', 'status': 'healthy', 'version': '1.0'},
            {'name': 'Performance', 'status': 'healthy', 'version': '1.0'},
        ]
        cards = []
        for svc in services:
            cards.append(
                '<div class="col-md-3">'
                '<div class="card h-100 service-card">'
                '<div class="card-body py-2 px-3">'
                '<div class="d-flex justify-content-between align-items-center">'
                f'<strong class="small">{svc["name"]}</strong>'
                f'<span class="badge bg-{"success" if svc["status"]=="healthy" else "secondary"}">{svc["status"]}</span>'
                '</div>'
                f'<div class="small text-muted">v{svc.get("version") or "1.0"}</div>'
                '</div>'
                '</div>'
                '</div>'
            )
        return '<div class="row g-2">' + ''.join(cards) + '</div>'
    except Exception:
        current_app.logger.error("Analyzer services fragment failed", exc_info=True)
        return '<div class="text-muted small">Analyzer services unavailable</div>'


@dashboard_bp.route('/recent_activity')
def recent_activity():
    """HTMX endpoint for recent activity timeline."""
    try:
        from app.utils.template_paths import render_template_compat as render_template
        # Get recent activities (last 10 items)
        recent_security = db.session.query(SecurityAnalysis).order_by(db.desc(SecurityAnalysis.started_at)).limit(5).all()
        recent_performance = db.session.query(PerformanceTest).order_by(db.desc(PerformanceTest.started_at)).limit(5).all()
        recent_batch = db.session.query(BatchAnalysis).order_by(db.desc(BatchAnalysis.created_at)).limit(5).all()

        activities = []

        # Add security activities
        for analysis in recent_security:
            if analysis.started_at:
                activities.append({
                    'type': 'security',
                    'description': 'Security analysis completed',
                    'timestamp': analysis.started_at,
                    'status': analysis.status.value if analysis.status else 'unknown'
                })

        # Add performance activities
        for test in recent_performance:
            if test.started_at:
                activities.append({
                    'type': 'performance',
                    'description': 'Performance test completed',
                    'timestamp': test.started_at,
                    'status': test.status.value if test.status else 'unknown'
                })

        # Add batch activities
        for batch in recent_batch:
            if batch.created_at:
                activities.append({
                    'type': 'batch',
                    'description': f'Batch analysis #{batch.id}',
                    'timestamp': batch.created_at,
                    'status': batch.status.value if batch.status else 'unknown'
                })

        # Sort by timestamp
        activities.sort(key=lambda x: x['timestamp'] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        activities = activities[:10]  # Keep only the 10 most recent

        if not activities:
            return '<div class="text-center py-3"><p class="text-muted">Unable to load activity</p></div>'
        return render_template('components/dashboard/activity-timeline.html', activities=activities)
    except Exception as e:
        current_app.logger.error(f"Error getting recent activity: {e}")
        from app.utils.template_paths import render_template_compat as render_template
        return render_template('components/dashboard/activity-timeline.html', activities=[])


# =================================================================
# STATISTICS API ROUTES (moved from main api.py)
# =================================================================

@dashboard_bp.route('/stats/apps')
def api_stats_apps():
    data = get_application_statistics()
    return api_success(data, message="Application statistics fetched")


@dashboard_bp.route('/stats/models')
def api_stats_models():
    data = get_model_statistics()
    return api_success(data, message="Model statistics fetched")


@dashboard_bp.route('/stats/analysis')
def api_stats_analysis():
    data = get_analysis_statistics()
    return api_success(data, message="Analysis statistics fetched")


@dashboard_bp.route('/stats/recent')
def api_stats_recent():
    data = get_recent_statistics()
    return api_success(data, message="Recent statistics fetched")


@dashboard_bp.route('/models/distribution')
def api_models_distribution():
    data = get_model_distribution()
    return api_success(data, message="Model distribution fetched")


@dashboard_bp.route('/generation/trends')
def api_generation_trends():
    data = get_generation_trends()
    return api_success(data, message="Generation trends fetched")


@dashboard_bp.route('/analysis/summary')
def api_analysis_summary():
    data = get_analysis_summary()
    return api_success(data, message="Analysis summary fetched")


@dashboard_bp.route('/export')
def api_export_statistics():
    data = export_statistics()
    return api_success(data, message="Statistics exported")