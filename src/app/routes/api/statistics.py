"""
Statistics API Routes
=====================

API endpoints for statistics and data aggregation.
"""

import logging
from datetime import datetime, timedelta
from flask import render_template, request, Response
from sqlalchemy import text, func

from . import api_bp
from ...models import (
    GeneratedApplication, ModelCapability, SecurityAnalysis, PerformanceTest
)
from ...extensions import db
from ..response_utils import json_success, handle_exceptions
from ...services.statistics_service import (
    get_application_statistics,
    get_model_statistics,
    get_analysis_statistics,
    get_recent_statistics,
    get_model_distribution,
    get_generation_trends,
    get_analysis_summary,
    export_statistics
)

# Set up logger
logger = logging.getLogger(__name__)


@api_bp.route('/stats/apps')
@handle_exceptions(logger_override=logger)
def api_stats_apps():
    data = get_application_statistics()
    return json_success(data, message="Application statistics fetched")


@api_bp.route('/stats/models')
@handle_exceptions(logger_override=logger)
def api_stats_models():
    data = get_model_statistics()
    return json_success(data, message="Model statistics fetched")


@api_bp.route('/stats/analysis')
@handle_exceptions(logger_override=logger)
def api_stats_analysis():
    data = get_analysis_statistics()
    return json_success(data, message="Analysis statistics fetched")


@api_bp.route('/stats/recent')
@handle_exceptions(logger_override=logger)
def api_stats_recent():
    data = get_recent_statistics()
    return json_success(data, message="Recent statistics fetched")


@api_bp.route('/models/distribution')
@handle_exceptions(logger_override=logger)
def api_models_distribution():
    data = get_model_distribution()
    return json_success(data, message="Model distribution fetched")


@api_bp.route('/generation/trends')
@handle_exceptions(logger_override=logger)
def api_generation_trends():
    data = get_generation_trends()
    return json_success(data, message="Generation trends fetched")


@api_bp.route('/analysis/summary')
@handle_exceptions(logger_override=logger)
def api_analysis_summary():
    data = get_analysis_summary()
    return json_success(data, message="Analysis summary fetched")


@api_bp.route('/export')
@handle_exceptions(logger_override=logger)
def api_export_statistics():
    data = export_statistics()
    return json_success(data, message="Statistics exported")


# =================================================================
# HTMX STATISTICS ENDPOINTS
# =================================================================

@api_bp.route('/stats_total_models')
def stats_total_models():
    """HTMX endpoint for total models count."""
    try:
        count = ModelCapability.query.count()
        return str(count)
    except Exception as e:
        logger.error(f"Error getting total models: {e}")
        return "0"


@api_bp.route('/stats_models_trend')
def stats_models_trend():
    """HTMX endpoint for models trend."""
    try:
        # Simple trend calculation - could be enhanced
        recent_count = ModelCapability.query.filter(
            ModelCapability.created_at >= datetime.now() - timedelta(days=30)
        ).count() if hasattr(ModelCapability, 'created_at') else 0
        return f"+{recent_count} this month"
    except Exception as e:
        logger.error(f"Error getting models trend: {e}")
        return "No data"


@api_bp.route('/stats_total_apps')
def stats_total_apps():
    """HTMX endpoint for total applications count."""
    try:
        total_apps = GeneratedApplication.query.count()
        return str(total_apps)
    except Exception as e:
        logger.error(f"Error getting total apps: {e}")
        return "0"


@api_bp.route('/stats_security_tests')
def stats_security_tests():
    """HTMX endpoint for security tests count."""
    try:
        security_tests = SecurityAnalysis.query.count()
        return str(security_tests)
    except Exception as e:
        logger.error(f"Error getting security tests count: {e}")
        return "0"


@api_bp.route('/stats_performance_tests')
def stats_performance_tests():
    """HTMX endpoint for performance tests count."""
    try:
        performance_tests = PerformanceTest.query.count()
        return str(performance_tests)
    except Exception as e:
        logger.error(f"Error getting performance tests count: {e}")
        return "0"


@api_bp.route('/stats_container_status')
def stats_container_status():
    """HTMX endpoint for container status summary."""
    try:
        # Simple status check without complex dependencies
        # In a production environment, this would query actual container status
        return "Checking containers..."
    except Exception as e:
        logger.error(f"Error getting container status: {e}")
        return "Status unknown"


@api_bp.route('/stats_completed_analyses')
def stats_completed_analyses():
    """HTMX endpoint for completed analyses count."""
    try:
        # Count completed security and performance analyses
        security_count = SecurityAnalysis.query.count()
        performance_count = PerformanceTest.query.count()
        total = security_count + performance_count
        return str(total)
    except Exception as e:
        logger.error(f"Error getting completed analyses: {e}")
        return "0"


@api_bp.route('/stats_analysis_trend')
def stats_analysis_trend():
    """HTMX endpoint for analysis trend."""
    try:
        # Count recent analyses
        recent_security = SecurityAnalysis.query.filter(
            SecurityAnalysis.created_at >= datetime.now() - timedelta(days=7)
        ).count() if hasattr(SecurityAnalysis, 'created_at') else 0
        
        recent_performance = PerformanceTest.query.filter(
            PerformanceTest.created_at >= datetime.now() - timedelta(days=7)
        ).count() if hasattr(PerformanceTest, 'created_at') else 0
        
        total_recent = recent_security + recent_performance
        return f"+{total_recent} this week"
    except Exception as e:
        logger.error(f"Error getting analysis trend: {e}")
        return "No data"


@api_bp.route('/stats_system_health')
def stats_system_health():
    """HTMX endpoint for system health indicator."""
    try:
        # Quick health check
        try:
            # Test database connection
            db.session.execute(text('SELECT 1'))
            db_healthy = True
        except Exception:
            db_healthy = False
        
        # Check if components are available
        try:
            from ...extensions import get_components
            components = get_components()
            services_available = components is not None
        except Exception:
            services_available = False
        
        # Determine overall health
        if db_healthy and services_available:
            return '<span class="badge bg-success">Healthy</span>'
        elif db_healthy:
            return '<span class="badge bg-warning">Partial</span>'
        else:
            return '<span class="badge bg-danger">Unhealthy</span>'
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        return '<span class="badge bg-secondary">Unknown</span>'


@api_bp.route('/stats_uptime')
def stats_uptime():
    """HTMX endpoint for system uptime."""
    try:
        # Simple uptime calculation based on application start
        # In production, this could track actual application start time
        
        # For now, return a simple uptime message
        # In production, you'd track actual start time
        uptime_days = 1  # Placeholder
        return f"{uptime_days} day(s)"
    except Exception as e:
        logger.error(f"Error getting uptime: {e}")
        return "Unknown"


@api_bp.route('/stats_running_containers')
def stats_running_containers():
    """HTMX endpoint for running containers count."""
    try:
        # For now, return a placeholder. In production, this would check actual container status
        from ...models import ContainerizedTest
        
        # Count active containerized tests
        active_tests = db.session.query(ContainerizedTest).filter(
            ContainerizedTest.status == 'running'
        ).count()
        
        return str(active_tests)
    except Exception as e:
        logger.error(f"Error getting running containers: {e}")
        return "0"


# =================================================================
# TEMPLATE-BASED STATISTICS ENDPOINTS  
# =================================================================

@api_bp.route('/statistics/top-models')
def statistics_top_models_table():
    """Render a simple table with top performing models for the stats overview page."""
    try:
        # Top by number of generated applications
        top = db.session.query(
            GeneratedApplication.model_slug.label('model_slug'),
            func.count(GeneratedApplication.id).label('app_count')
        ).group_by(GeneratedApplication.model_slug).order_by(func.count(GeneratedApplication.id).desc()).limit(10).all()

        # Map to display fields
        from ...models import ModelCapability
        slug_to_meta = {m.canonical_slug: m for m in db.session.query(ModelCapability).all()}
        rows = []
        for row in top:
            meta = slug_to_meta.get(row.model_slug)
            rows.append({
                'model_slug': row.model_slug,
                'model_name': getattr(meta, 'model_name', row.model_slug),
                'provider': getattr(meta, 'provider', 'unknown'),
                'app_count': int(row.app_count or 0)
            })

        return render_template('partials/statistics/top_models_table.html', top_models=rows)
    except Exception as e:
        logger.error(f"Error rendering statistics top models table: {e}")
        return render_template('partials/statistics/top_models_table.html', top_models=[])


@api_bp.route('/statistics/chart-data')
def statistics_chart_data():
    """Return chart data payload for statistics overview page.

    Query param 'range' can be 7d, 30d, 90d. Returns structure expected by views/statistics/overview.html.
    """
    try:
        from datetime import datetime, timedelta
        rng = (request.args.get('range') or '30d').lower()  # type: ignore[name-defined]
        days = 30
        if rng.endswith('d') and rng[:-1].isdigit():
            days = max(7, min(365, int(rng[:-1])))
        start = datetime.utcnow() - timedelta(days=days)

        # Build simple time buckets (daily) for security/performance counts
        # For portability across DBs, do Python-side aggregation
        security = db.session.query(SecurityAnalysis).filter(SecurityAnalysis.created_at >= start).all()
        performance = db.session.query(PerformanceTest).filter(PerformanceTest.created_at >= start).all()

        # Prepare labels (dates) and counts
        from collections import defaultdict
        def daterange(s, e):
            cur = s.date()
            while cur <= e.date():
                yield cur
                cur += timedelta(days=1)

        sec_counts = defaultdict(int)
        for a in security:
            if a.created_at:
                sec_counts[a.created_at.date()] += 1
        perf_counts = defaultdict(int)
        for t in performance:
            if t.created_at:
                perf_counts[t.created_at.date()] += 1

        labels = [d.isoformat() for d in daterange(start, datetime.utcnow())]
        activity = {
            'labels': labels,
            'datasets': [
                {'label': 'Security Analyses', 'data': [sec_counts.get(datetime.fromisoformat(ld).date(), 0) for ld in labels]},
                {'label': 'Performance Tests', 'data': [perf_counts.get(datetime.fromisoformat(ld).date(), 0) for ld in labels]},
                {'label': 'Dynamic Analyses', 'data': [0 for _ in labels]},
            ]
        }

        # Model performance: top models success rate placeholder + avg runtime
        top = (
            db.session.query(
                GeneratedApplication.model_slug,
                func.count(GeneratedApplication.id).label('cnt')
            )
            .group_by(GeneratedApplication.model_slug)
            .order_by(func.count(GeneratedApplication.id).desc())
            .limit(8)
            .all()
        )
        model_labels = [row.model_slug for row in top]
        success_rates = [80 for _ in top]  # placeholder
        avg_runtimes = [2.5 for _ in top]  # minutes placeholder
        model_performance = {
            'labels': model_labels,
            'successRates': success_rates,
            'avgRuntimes': avg_runtimes,
        }

        # Analysis type distribution
        analysis_types = [
            db.session.query(SecurityAnalysis).count(),
            db.session.query(PerformanceTest).count(),
            0,
            0,
        ]

        # Success trends placeholder
        success_trends = {
            'labels': labels,
            'datasets': [
                {'label': 'Model A', 'data': [70 for _ in labels], 'borderColor': 'rgb(54,162,235)'},
                {'label': 'Model B', 'data': [65 for _ in labels], 'borderColor': 'rgb(255,99,132)'}
            ]
        }

        return json_success({
            'activity': activity,
            'modelPerformance': model_performance,
            'analysisTypes': analysis_types,
            'successTrends': success_trends,
        })
    except Exception as e:
        logger.error(f"Error building statistics chart data: {e}")
        return json_success({'activity': {'labels': [], 'datasets': []}, 'modelPerformance': {'labels': [], 'successRates': [], 'avgRuntimes': []}, 'analysisTypes': [0,0,0,0], 'successTrends': {'labels': [], 'datasets': []}})


@api_bp.route('/statistics/export/<fmt>')
def statistics_export(fmt: str):
    """Export statistics in basic formats (csv/excel/pdf placeholder)."""
    try:
        fmt = (fmt or '').lower()
        # Simple CSV export of model usage
        rows = ["model_slug,applications"]
        usage = (
            db.session.query(
                GeneratedApplication.model_slug,
                func.count(GeneratedApplication.id).label('cnt')
            )
            .group_by(GeneratedApplication.model_slug)
            .order_by(func.count(GeneratedApplication.id).desc())
            .all()
        )
        for row in usage:
            rows.append(f"{row.model_slug},{int(row.cnt or 0)}")
        csv_data = "\n".join(rows)

        filename = f"statistics_export_{fmt}_{datetime.now().date().isoformat()}.csv"
        return Response(csv_data, mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename={filename}'})
    except Exception as e:
        logger.error(f"Error exporting statistics: {e}")
        return Response('model_slug,applications\n', mimetype='text/csv')


@api_bp.route('/statistics/refresh')
def statistics_refresh():
    """No-op refresh endpoint for HTMX triggers on statistics page."""
    return Response(status=204)


@api_bp.route('/statistics/insights')
def statistics_insights():
    """Return a simple HTML list of recent insights for the statistics page."""
    try:
        # Build a simple list from recent activity stats
        recent_models = db.session.query(ModelCapability).order_by(ModelCapability.created_at.desc()).limit(5).all() if hasattr(ModelCapability, 'created_at') else []
        items = []
        for m in recent_models:
            items.append(f"<li class='list-group-item'><i class='fas fa-robot text-primary me-2'></i><strong>{m.model_name}</strong> by {m.provider}</li>")
        if not items:
            items = ["<li class='list-group-item text-muted'>No recent insights available</li>"]
        return "<ul class='list-group list-group-flush'>" + "".join(items) + "</ul>"
    except Exception as e:
        logger.error(f"Error building insights: {e}")
        return "<div class='text-muted'>No insights available</div>"


@api_bp.route('/statistics/summary')
def statistics_summary_html():
    """Return a compact HTML summary grid for the statistics page."""
    try:
        total_models = db.session.query(ModelCapability).count()
        total_apps = db.session.query(GeneratedApplication).count()
        total_security = db.session.query(SecurityAnalysis).count()
        total_performance = db.session.query(PerformanceTest).count()

        html = f"""
        <div class='col-md-3 mb-3'>
            <div class='card border-0 shadow-sm'>
                <div class='card-body'>
                    <div class='d-flex align-items-center'>
                        <i class='fas fa-robot text-primary me-2'></i>
                        <div>
                            <div class='fw-bold'>{total_models}</div>
                            <div class='text-muted small'>Models</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <div class='col-md-3 mb-3'>
            <div class='card border-0 shadow-sm'>
                <div class='card-body'>
                    <div class='d-flex align-items-center'>
                        <i class='fas fa-code text-warning me-2'></i>
                        <div>
                            <div class='fw-bold'>{total_apps}</div>
                            <div class='text-muted small'>Applications</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <div class='col-md-3 mb-3'>
            <div class='card border-0 shadow-sm'>
                <div class='card-body'>
                    <div class='d-flex align-items-center'>
                        <i class='fas fa-shield-alt text-info me-2'></i>
                        <div>
                            <div class='fw-bold'>{total_security}</div>
                            <div class='text-muted small'>Security Analyses</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <div class='col-md-3 mb-3'>
            <div class='card border-0 shadow-sm'>
                <div class='card-body'>
                    <div class='d-flex align-items-center'>
                        <i class='fas fa-tachometer-alt text-success me-2'></i>
                        <div>
                            <div class='fw-bold'>{total_performance}</div>
                            <div class='text-muted small'>Performance Tests</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        """
        return html
    except Exception as e:
        logger.error(f"Error building statistics summary: {e}")
        return "<div class='text-muted'>Summary unavailable</div>"

@api_bp.route('/statistics/test-results')
def statistics_test_results():
    """Render test results statistics template."""
    try:
        # Aggregate test results data
        security_results = db.session.query(SecurityAnalysis).order_by(
            SecurityAnalysis.created_at.desc()
        ).limit(10).all()
        
        performance_results = db.session.query(PerformanceTest).order_by(
            PerformanceTest.created_at.desc()
        ).limit(10).all()
        
        return render_template('statistics/test_results.html', 
                             security_results=security_results,
                             performance_results=performance_results)
    except Exception as e:
        logger.error(f"Error rendering test results statistics: {e}")
        return f"<div class='alert alert-danger'>Error loading test results: {str(e)}</div>"


@api_bp.route('/statistics/model-rankings')
def statistics_model_rankings():
    """Render model rankings statistics template."""
    try:
        # Get model performance rankings based on application success rates
        model_rankings = db.session.query(
            ModelCapability.model_name,
            ModelCapability.provider,
            func.count(SecurityAnalysis.id).label('security_tests_count'),
            func.count(PerformanceTest.id).label('performance_tests_count'),
            func.avg(SecurityAnalysis.total_issues).label('avg_security_issues'),
            func.avg(PerformanceTest.requests_per_second).label('avg_rps'),
            func.avg(PerformanceTest.average_response_time).label('avg_response_time')
        ).outerjoin(GeneratedApplication, GeneratedApplication.model_slug == ModelCapability.canonical_slug)\
         .outerjoin(SecurityAnalysis, SecurityAnalysis.application_id == GeneratedApplication.id)\
         .outerjoin(PerformanceTest, PerformanceTest.application_id == GeneratedApplication.id)\
         .group_by(ModelCapability.id, ModelCapability.model_name, ModelCapability.provider)\
         .order_by(func.count(GeneratedApplication.id).desc()).all()
        
        return render_template('statistics/model_rankings.html',
                             model_rankings=model_rankings)
    except Exception as e:
        logger.error(f"Error rendering model rankings: {e}")
        return f"<div class='alert alert-danger'>Error loading model rankings: {str(e)}</div>"


@api_bp.route('/statistics/error-analysis')
def statistics_error_analysis():
    """Render error analysis statistics template."""
    try:
        # Aggregate error data from various sources
        error_summary = {
            'database_errors': 0,  # Could track from logs
            'application_errors': 0,
            'analysis_failures': 0,
            'container_failures': 0
        }
        
        # Get recent failed analyses
        failed_security = db.session.query(SecurityAnalysis).filter(
            SecurityAnalysis.status == 'failed'
        ).order_by(SecurityAnalysis.created_at.desc()).limit(5).all()
        
        failed_performance = db.session.query(PerformanceTest).filter(
            PerformanceTest.status == 'failed'
        ).order_by(PerformanceTest.created_at.desc()).limit(5).all()
        
        return render_template('statistics/error_analysis.html',
                             error_summary=error_summary,
                             failed_security=failed_security,
                             failed_performance=failed_performance)
    except Exception as e:
        logger.error(f"Error rendering error analysis: {e}")
        return f"<div class='alert alert-danger'>Error loading error analysis: {str(e)}</div>"
