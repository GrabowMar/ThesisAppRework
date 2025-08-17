"""
Statistics API Routes
=====================

API endpoints for statistics and data aggregation.
"""

import logging
from datetime import datetime, timedelta
from flask import render_template
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
