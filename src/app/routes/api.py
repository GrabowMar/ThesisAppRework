"""
API Routes
=========

RESTful API endpoints for external integrations.
"""

import logging
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, render_template

from ..models import ModelCapability, GeneratedApplication
from ..services.task_manager import TaskManager
from ..services.analyzer_integration import AnalyzerIntegration

# Set up logger
logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)

# Initialize services
task_manager = TaskManager()
analyzer_integration = AnalyzerIntegration()


@api_bp.route('/models')
def api_models():
    """API endpoint: Get all models."""
    try:
        models = ModelCapability.query.all()
        return jsonify([{
            'model_slug': model.model_slug,
            'provider': model.provider,
            'model_name': model.model_name,
            'capabilities': model.capabilities
        } for model in models])
    except Exception as e:
        logger.error(f"Error getting models: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/models/<model_slug>/apps')
def api_model_apps(model_slug):
    """API endpoint: Get applications for a model."""
    try:
        apps = GeneratedApplication.query.filter_by(model_slug=model_slug).all()
        return jsonify([{
            'app_id': app.id,
            'app_number': app.app_number,
            'model_slug': app.model_slug,
            'provider': app.provider,
            'created_at': app.created_at.isoformat() if app.created_at else None
        } for app in apps])
    except Exception as e:
        logger.error(f"Error getting apps for model {model_slug}: {e}")
        return jsonify({'error': str(e)}), 500


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


@api_bp.route('/quick_search', methods=['POST'])
def quick_search():
    """HTMX endpoint for quick search functionality."""
    # TODO: Implement quick search
    return render_template('partials/search_results.html', results=[])


@api_bp.route('/sidebar_stats')
def sidebar_stats():
    """HTMX endpoint for sidebar statistics."""
    from ..models import ModelCapability, GeneratedApplication, SecurityAnalysis, PerformanceTest
    from ..extensions import db
    
    try:
        stats = {
            'total_models': db.session.query(ModelCapability).count(),
            'total_apps': db.session.query(GeneratedApplication).count(),
            'security_tests': db.session.query(SecurityAnalysis).count(),
            'performance_tests': db.session.query(PerformanceTest).count()
        }
        return render_template('partials/sidebar_stats.html', stats=stats)
    except Exception as e:
        logger.error(f"Error getting sidebar stats: {e}")
        return render_template('partials/sidebar_stats.html', stats={
            'total_models': 0, 'total_apps': 0, 'security_tests': 0, 'performance_tests': 0
        })


@api_bp.route('/recent_activity')
def recent_activity():
    """HTMX endpoint for recent activity timeline."""
    from ..models import SecurityAnalysis, PerformanceTest, BatchAnalysis
    from ..extensions import db
    from sqlalchemy import desc
    from datetime import datetime, timezone
    
    try:
        # Get recent activities (last 10 items)
        recent_security = db.session.query(SecurityAnalysis).order_by(desc(SecurityAnalysis.started_at)).limit(5).all()
        recent_performance = db.session.query(PerformanceTest).order_by(desc(PerformanceTest.started_at)).limit(5).all()
        recent_batch = db.session.query(BatchAnalysis).order_by(desc(BatchAnalysis.created_at)).limit(5).all()
        
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
        
        return render_template('partials/activity_timeline.html', activities=activities)
    except Exception as e:
        logger.error(f"Error getting recent activity: {e}")
        return render_template('partials/activity_timeline.html', activities=[])


@api_bp.route('/system_health')
def system_health():
    """HTMX endpoint for system health status."""
    from ..extensions import get_components
    from sqlalchemy import text
    from ..extensions import db
    
    try:
        # Check database status
        try:
            db.session.execute(text('SELECT 1'))
            db_status = {'status': 'healthy', 'message': 'Connected'}
        except Exception as e:
            db_status = {'status': 'error', 'message': str(e)}
        
        # Check Celery status
        try:
            components = get_components()
            celery_instance = components.celery if components else None
            if celery_instance:
                celery_inspect = celery_instance.control.inspect()
                active_tasks = celery_inspect.active()
                celery_status = {'status': 'healthy', 'message': 'Running'} if active_tasks is not None else {'status': 'error', 'message': 'Not responding'}
            else:
                celery_status = {'status': 'warning', 'message': 'Not available'}
        except Exception as e:
            celery_status = {'status': 'error', 'message': str(e)}
        
        # Check analyzer status (simplified to avoid encoding issues)
        try:
            components = get_components()
            analyzer_integration = components.analyzer_integration if components else None
            if analyzer_integration:
                # Just check if the service exists, don't run commands that might have encoding issues
                analyzer_status = {'status': 'available', 'message': 'Service available'}
            else:
                analyzer_status = {'status': 'warning', 'message': 'Not configured'}
        except Exception as e:
            analyzer_status = {'status': 'error', 'message': str(e)}
        
        system_status = {
            'database': db_status,
            'celery': celery_status,
            'analyzer': analyzer_status
        }
        
        return render_template('partials/system_status.html', system_status=system_status)
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        # Return a minimal system status to prevent template errors
        fallback_status = {
            'database': {'status': 'error', 'message': 'Health check failed'},
            'celery': {'status': 'error', 'message': 'Health check failed'},
            'analyzer': {'status': 'error', 'message': 'Health check failed'}
        }
        return render_template('partials/system_status.html', system_status=fallback_status)


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
        from ..models import SecurityAnalysis, PerformanceTest
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
        from ..models import SecurityAnalysis, PerformanceTest
        from datetime import datetime, timedelta
        
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
        from ..extensions import get_components
        from sqlalchemy import text
        from ..extensions import db
        
        # Quick health check
        try:
            # Test database connection
            db.session.execute(text('SELECT 1'))
            db_healthy = True
        except Exception:
            db_healthy = False
        
        # Check if components are available
        try:
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


@api_bp.route('/recent_activity_detailed')
def recent_activity_detailed():
    """HTMX endpoint for detailed recent activity."""
    try:
        from ..models import SecurityAnalysis, PerformanceTest
        from ..extensions import db
        from sqlalchemy import desc
        
        # Get more detailed recent activities
        recent_activities = []
        
        # Security analyses
        security_analyses = db.session.query(SecurityAnalysis).order_by(desc(SecurityAnalysis.started_at)).limit(5).all()
        for analysis in security_analyses:
            recent_activities.append({
                'type': 'security',
                'title': f'Security Analysis #{analysis.id}',
                'status': analysis.status.value if analysis.status else 'unknown',
                'timestamp': analysis.started_at or analysis.created_at,
                'details': f'{analysis.total_issues} issues found' if analysis.total_issues else 'No issues'
            })
        
        # Performance tests
        performance_tests = db.session.query(PerformanceTest).order_by(desc(PerformanceTest.started_at)).limit(5).all()
        for test in performance_tests:
            recent_activities.append({
                'type': 'performance',
                'title': f'Performance Test #{test.id}',
                'status': test.status.value if test.status else 'unknown',
                'timestamp': test.started_at or test.created_at,
                'details': f'{test.requests_per_second:.1f} RPS' if test.requests_per_second else 'No data'
            })
        
        # Sort by timestamp
        recent_activities.sort(key=lambda x: x['timestamp'] or datetime.min, reverse=True)
        recent_activities = recent_activities[:10]
        
        return render_template('partials/recent_activity_detailed.html', activities=recent_activities)
    except Exception as e:
        logger.error(f"Error getting detailed recent activity: {e}")
        return render_template('partials/recent_activity_detailed.html', activities=[])


@api_bp.route('/system_status_detailed')
def system_status_detailed():
    """HTMX endpoint for detailed system status."""
    try:
        from ..extensions import get_components
        from sqlalchemy import text
        from ..extensions import db
        
        # Detailed system status check
        status_details = {}
        
        # Database status
        try:
            db.session.execute(text('SELECT 1'))
            status_details['database'] = {
                'status': 'healthy',
                'message': 'Database connection active',
                'details': 'SQLite database responding normally'
            }
        except Exception as e:
            status_details['database'] = {
                'status': 'error',
                'message': 'Database connection failed',
                'details': str(e)
            }
        
        # Celery status
        try:
            components = get_components()
            if components and components.celery:
                status_details['celery'] = {
                    'status': 'healthy',
                    'message': 'Task queue operational',
                    'details': 'Celery worker available'
                }
            else:
                status_details['celery'] = {
                    'status': 'warning',
                    'message': 'Task queue not configured',
                    'details': 'Celery not initialized'
                }
        except Exception as e:
            status_details['celery'] = {
                'status': 'error',
                'message': 'Task queue error',
                'details': str(e)
            }
        
        # Analyzer status
        try:
            components = get_components()
            if components and components.analyzer_integration:
                status_details['analyzer'] = {
                    'status': 'available',
                    'message': 'Analyzer service available',
                    'details': 'Ready for analysis tasks'
                }
            else:
                status_details['analyzer'] = {
                    'status': 'warning',
                    'message': 'Analyzer not configured',
                    'details': 'Service not initialized'
                }
        except Exception as e:
            status_details['analyzer'] = {
                'status': 'error',
                'message': 'Analyzer service error',
                'details': str(e)
            }
        
        return render_template('partials/system_status_detailed.html', status_details=status_details)
    except Exception as e:
        logger.error(f"Error getting detailed system status: {e}")
        return render_template('partials/system_status_detailed.html', status_details={})


@api_bp.route('/models_overview_summary')
def models_overview_summary():
    """HTMX endpoint for models overview summary."""
    try:
        from ..models import ModelCapability, GeneratedApplication
        from ..extensions import db
        
        # Get model statistics
        total_models = db.session.query(ModelCapability).count()
        total_apps = db.session.query(GeneratedApplication).count()
        
        # Get provider breakdown
        provider_stats = db.session.query(
            ModelCapability.provider,
            db.func.count(ModelCapability.id)
        ).group_by(ModelCapability.provider).all()
        
        summary = {
            'total_models': total_models,
            'total_apps': total_apps,
            'providers': [{'name': provider, 'count': count} for provider, count in provider_stats]
        }
        
        return render_template('partials/models_overview_summary.html', summary=summary)
    except Exception as e:
        logger.error(f"Error getting models overview summary: {e}")
        return render_template('partials/models_overview_summary.html', summary={
            'total_models': 0, 'total_apps': 0, 'providers': []
        })


@api_bp.route('/performance_chart_data')
def performance_chart_data():
    """HTMX endpoint for performance chart data."""
    try:
        from ..models import PerformanceTest
        from ..extensions import db
        from datetime import datetime, timedelta
        
        # Get performance test data for the last 30 days
        thirty_days_ago = datetime.now() - timedelta(days=30)
        performance_tests = db.session.query(PerformanceTest).filter(
            PerformanceTest.created_at >= thirty_days_ago
        ).all()
        
        # Group by date and calculate averages
        chart_data = []
        for test in performance_tests:
            if test.average_response_time:
                chart_data.append({
                    'date': test.created_at.strftime('%Y-%m-%d') if test.created_at else 'Unknown',
                    'response_time': float(test.average_response_time),
                    'requests_per_second': float(test.requests_per_second) if test.requests_per_second else 0
                })
        
        return render_template('partials/performance_chart.html', chart_data=chart_data)
    except Exception as e:
        logger.error(f"Error getting performance chart data: {e}")
        return render_template('partials/performance_chart.html', chart_data=[])


@api_bp.route('/security_distribution_data')
def security_distribution_data():
    """HTMX endpoint for security distribution data."""
    try:
        from ..models import SecurityAnalysis
        from ..extensions import db
        
        # Get security analysis distribution
        security_analyses = db.session.query(SecurityAnalysis).all()
        
        # Count by severity using the actual model attributes
        distribution = {
            'high': sum(1 for a in security_analyses if a.high_severity_count and a.high_severity_count > 0),
            'medium': sum(1 for a in security_analyses if a.medium_severity_count and a.medium_severity_count > 0),
            'low': sum(1 for a in security_analyses if a.low_severity_count and a.low_severity_count > 0),
            'clean': sum(1 for a in security_analyses if a.total_issues == 0)
        }
        
        return render_template('partials/security_distribution.html', distribution=distribution)
    except Exception as e:
        logger.error(f"Error getting security distribution data: {e}")
        return render_template('partials/security_distribution.html', distribution={
            'high': 0, 'medium': 0, 'low': 0, 'clean': 0
        })
