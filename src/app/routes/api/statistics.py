"""
Statistics API Routes
=====================

API endpoints for statistics and data aggregation.
"""

import logging
from datetime import datetime, timedelta
from flask import jsonify, render_template
from sqlalchemy import func, desc, text

from . import api_bp
from ...models import (
    GeneratedApplication, ModelCapability, SecurityAnalysis, 
    PerformanceTest
)
from ...extensions import db

# Set up logger
logger = logging.getLogger(__name__)


@api_bp.route('/stats/apps')
def api_stats_apps():
    """API endpoint: Get application statistics."""
    try:
        total_apps = db.session.query(func.count(GeneratedApplication.id)).scalar()
        
        # Apps by status  
        app_stats = (
            db.session.query(
                GeneratedApplication.generation_status,
                func.count(GeneratedApplication.id).label('count')
            )
            .group_by(GeneratedApplication.generation_status)
            .all()
        )
        
        # Apps by type
        type_stats = (
            db.session.query(
                GeneratedApplication.app_type,
                func.count(GeneratedApplication.id).label('count')
            )
            .group_by(GeneratedApplication.app_type)
            .all()
        )
        
        # Recent apps (last 7 days)
        from datetime import datetime, timedelta
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_count = (
            db.session.query(func.count(GeneratedApplication.id))
            .filter(GeneratedApplication.created_at >= week_ago)
            .scalar()
        )
        
        return jsonify({
            'total': total_apps,
            'by_status': [{'status': str(s), 'count': c} for s, c in app_stats],
            'by_type': [{'type': t, 'count': c} for t, c in type_stats],
            'recent_count': recent_count
        })
        
    except Exception as e:
        logger.error(f"Error getting app statistics: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/stats/models')
def api_stats_models():
    """API endpoint: Get model statistics."""
    try:
        total_models = db.session.query(func.count(ModelCapability.id)).scalar()
        
        # Models by provider
        provider_stats = (
            db.session.query(
                ModelCapability.provider,
                func.count(ModelCapability.id).label('count')
            )
            .group_by(ModelCapability.provider)
            .all()
        )
        
        # Models by capability
        capability_stats = {}
        capabilities = ['code_generation', 'code_review', 'analysis', 'testing']
        
        for cap in capabilities:
            count = (
                db.session.query(func.count(ModelCapability.id))
                .filter(getattr(ModelCapability, cap))
                .scalar()
            )
            capability_stats[cap] = count
        
        return jsonify({
            'total': total_models,
            'by_provider': [{'provider': p, 'count': c} for p, c in provider_stats],
            'by_capability': capability_stats
        })
        
    except Exception as e:
        logger.error(f"Error getting model statistics: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/stats/analysis')
def api_stats_analysis():
    """API endpoint: Get analysis statistics."""
    try:
        # Security analysis stats
        security_total = db.session.query(func.count(SecurityAnalysis.id)).scalar()
        security_completed = (
            db.session.query(func.count(SecurityAnalysis.id))
            .filter(SecurityAnalysis.status == 'completed')
            .scalar()
        )
        
        # Performance test stats
        perf_total = db.session.query(func.count(PerformanceTest.id)).scalar()
        perf_completed = (
            db.session.query(func.count(PerformanceTest.id))
            .filter(PerformanceTest.status == 'completed')
            .scalar()
        )
        
        # Analysis success rates
        security_rate = (security_completed / security_total * 100) if security_total > 0 else 0
        perf_rate = (perf_completed / perf_total * 100) if perf_total > 0 else 0
        
        return jsonify({
            'security': {
                'total': security_total,
                'completed': security_completed,
                'success_rate': round(security_rate, 2)
            },
            'performance': {
                'total': perf_total,
                'completed': perf_completed,
                'success_rate': round(perf_rate, 2)
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting analysis statistics: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/stats/recent')
def api_stats_recent():
    """API endpoint: Get recent activity statistics."""
    try:
        from datetime import datetime, timedelta
        
        # Last 24 hours
        day_ago = datetime.utcnow() - timedelta(days=1)
        
        recent_apps = (
            db.session.query(func.count(GeneratedApplication.id))
            .filter(GeneratedApplication.created_at >= day_ago)
            .scalar()
        )
        
        recent_security = (
            db.session.query(func.count(SecurityAnalysis.id))
            .filter(SecurityAnalysis.created_at >= day_ago)
            .scalar()
        )
        
        recent_performance = (
            db.session.query(func.count(PerformanceTest.id))
            .filter(PerformanceTest.created_at >= day_ago)
            .scalar()
        )
        
        # Most used models (last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)
        popular_models = (
            db.session.query(
                GeneratedApplication.model_slug,
                func.count(GeneratedApplication.id).label('usage_count')
            )
            .filter(GeneratedApplication.created_at >= week_ago)
            .group_by(GeneratedApplication.model_slug)
            .order_by(desc('usage_count'))
            .limit(5)
            .all()
        )
        
        return jsonify({
            'last_24h': {
                'applications': recent_apps,
                'security_analyses': recent_security,
                'performance_tests': recent_performance
            },
            'popular_models': [
                {'model_slug': m, 'usage_count': c} 
                for m, c in popular_models
            ]
        })
        
    except Exception as e:
        logger.error(f"Error getting recent statistics: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/models/distribution')
def api_models_distribution():
    """API endpoint for model distribution statistics."""
    try:
        # Provider distribution
        provider_dist = db.session.query(
            ModelCapability.provider,
            func.count(ModelCapability.id).label('count')
        ).group_by(ModelCapability.provider).all()
        
        # Capability distribution
        capability_stats = {
            'function_calling': db.session.query(ModelCapability).filter(
                ModelCapability.supports_function_calling
            ).count(),
            'vision': db.session.query(ModelCapability).filter(
                ModelCapability.supports_vision
            ).count(),
            'streaming': db.session.query(ModelCapability).filter(
                ModelCapability.supports_streaming
            ).count(),
            'json_mode': db.session.query(ModelCapability).filter(
                ModelCapability.supports_json_mode
            ).count()
        }
        
        # Cost distribution
        free_models = db.session.query(ModelCapability).filter(
            ModelCapability.is_free
        ).count()
        
        paid_models = db.session.query(ModelCapability).filter(
            ~ModelCapability.is_free
        ).count()
        
        return jsonify({
            'providers': [{'provider': p, 'count': c} for p, c in provider_dist],
            'capabilities': capability_stats,
            'cost_distribution': {
                'free': free_models,
                'paid': paid_models
            }
        })
    
    except Exception as e:
        logger.error(f"Error getting model distribution: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/generation/trends')
def api_generation_trends():
    """API endpoint for generation trend statistics."""
    try:
        from datetime import datetime, timedelta
        
        # Get trends for last 30 days
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
        
        # Daily generation counts
        daily_data = []
        current_date = start_date.date()
        
        while current_date <= end_date.date():
            next_date = current_date + timedelta(days=1)
            
            count = db.session.query(func.count(GeneratedApplication.id)).filter(
                func.date(GeneratedApplication.created_at) == current_date
            ).scalar()
            
            daily_data.append({
                'date': current_date.isoformat(),
                'applications': count or 0
            })
            
            current_date = next_date
        
        return jsonify({
            'daily_trends': daily_data,
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            }
        })
    
    except Exception as e:
        logger.error(f"Error getting generation trends: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/analysis/summary')
def api_analysis_summary():
    """API endpoint for analysis summary statistics."""
    try:
        # Get analysis counts by type
        security_count = db.session.query(func.count(SecurityAnalysis.id)).scalar()
        performance_count = db.session.query(func.count(PerformanceTest.id)).scalar()
        
        # Get success rates
        security_success = db.session.query(func.count(SecurityAnalysis.id)).filter(
            SecurityAnalysis.status == 'completed'
        ).scalar()
        
        performance_success = db.session.query(func.count(PerformanceTest.id)).filter(
            PerformanceTest.status == 'completed'
        ).scalar()
        
        return jsonify({
            'security_analyses': {
                'total': security_count,
                'successful': security_success,
                'success_rate': (security_success / security_count * 100) if security_count > 0 else 0
            },
            'performance_tests': {
                'total': performance_count,
                'successful': performance_success,
                'success_rate': (performance_success / performance_count * 100) if performance_count > 0 else 0
            },
            'total_analyses': security_count + performance_count
        })
    
    except Exception as e:
        logger.error(f"Error getting analysis summary: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/export')
def api_export_statistics():
    """API endpoint to export statistics data."""
    try:
        from datetime import datetime, timedelta
        
        # Get export timeframe (last 30 days by default)
        start_date = datetime.utcnow() - timedelta(days=30)
        
        # Export data
        export_data = {
            'export_info': {
                'generated_at': datetime.utcnow().isoformat(),
                'period_start': start_date.isoformat(),
                'period_end': datetime.utcnow().isoformat()
            },
            'models': {
                'total': db.session.query(func.count(ModelCapability.id)).scalar(),
                'by_provider': dict(db.session.query(
                    ModelCapability.provider,
                    func.count(ModelCapability.id)
                ).group_by(ModelCapability.provider).all())
            },
            'applications': {
                'total': db.session.query(func.count(GeneratedApplication.id)).scalar(),
                'recent': db.session.query(func.count(GeneratedApplication.id)).filter(
                    GeneratedApplication.created_at >= start_date
                ).scalar()
            },
            'analyses': {
                'security': db.session.query(func.count(SecurityAnalysis.id)).scalar(),
                'performance': db.session.query(func.count(PerformanceTest.id)).scalar()
            }
        }
        
        return jsonify(export_data)
        
    except Exception as e:
        logger.error(f"Error exporting statistics: {e}")
        return jsonify({'error': str(e)}), 500


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
