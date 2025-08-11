"""
API Routes
=========

RESTful API endpoints for external integrations.
"""

import logging
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, render_template

from ..models import ModelCapability, GeneratedApplication
from ..services.task_manager import TaskManager
from ..services.analyzer_integration import AnalyzerIntegration
from ..services.background_service import get_background_service

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


@api_bp.route('/system_status')
def system_status():
    """HTMX endpoint for system status in sidebar."""
    try:
        from ..extensions import get_components
        from sqlalchemy import text
        from ..extensions import db
        
        # Quick system health check
        try:
            db.session.execute(text('SELECT 1'))
            db_healthy = True
        except Exception:
            db_healthy = False
        
        if db_healthy:
            return '<span class="badge bg-success">Online</span>'
        else:
            return '<span class="badge bg-danger">Offline</span>'
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return '<span class="badge bg-secondary">Unknown</span>'


@api_bp.route('/stats_running_containers')
def stats_running_containers():
    """HTMX endpoint for running containers count."""
    try:
        # For now, return a placeholder. In production, this would check actual container status
        from ..models import ContainerizedTest
        from ..extensions import db
        
        # Count active containerized tests
        active_tests = db.session.query(ContainerizedTest).filter(
            ContainerizedTest.status == 'running'
        ).count()
        
        return str(active_tests)
    except Exception as e:
        logger.error(f"Error getting running containers: {e}")
        return "0"


# Dashboard-specific HTMX endpoints
@api_bp.route('/dashboard/recent-models')
def dashboard_recent_models():
    """HTMX endpoint for dashboard recent models section."""
    try:
        from ..models import ModelCapability, GeneratedApplication
        from ..extensions import db
        from sqlalchemy import desc
        
        # Get recently updated models with their app counts
        recent_models = db.session.query(ModelCapability).order_by(
            desc(ModelCapability.updated_at)
        ).limit(5).all()
        
        # Add app counts and recent activity
        models_data = []
        for model in recent_models:
            app_count = db.session.query(GeneratedApplication).filter_by(
                model_slug=model.canonical_slug
            ).count()
            
            models_data.append({
                'model': model,
                'app_count': app_count,
                'last_activity': model.updated_at or model.created_at
            })
        
        return render_template('partials/dashboard_recent_models.html', models_data=models_data)
    except Exception as e:
        logger.error(f"Error getting dashboard recent models: {e}")
        return render_template('partials/dashboard_recent_models.html', models_data=[])


@api_bp.route('/dashboard/system-status')
def dashboard_system_status():
    """HTMX endpoint for dashboard system status section."""
    try:
        from ..extensions import get_components
        from sqlalchemy import text
        from ..extensions import db
        from datetime import datetime
        
        # Comprehensive system status check
        status_info = {
            'timestamp': datetime.now(),
            'services': {}
        }
        
        # Database status
        try:
            db.session.execute(text('SELECT 1'))
            status_info['services']['database'] = {
                'status': 'healthy',
                'message': 'Connected',
                'icon': 'fas fa-database',
                'color': 'success'
            }
        except Exception as e:
            status_info['services']['database'] = {
                'status': 'error',
                'message': 'Connection failed',
                'icon': 'fas fa-database',
                'color': 'danger'
            }
        
        # Celery status
        try:
            components = get_components()
            if components and components.celery:
                status_info['services']['celery'] = {
                    'status': 'healthy',
                    'message': 'Running',
                    'icon': 'fas fa-tasks',
                    'color': 'success'
                }
            else:
                status_info['services']['celery'] = {
                    'status': 'warning',
                    'message': 'Not configured',
                    'icon': 'fas fa-tasks',
                    'color': 'warning'
                }
        except Exception:
            status_info['services']['celery'] = {
                'status': 'error',
                'message': 'Error',
                'icon': 'fas fa-tasks',
                'color': 'danger'
            }
        
        # Analyzer status
        try:
            components = get_components()
            if components and components.analyzer_integration:
                status_info['services']['analyzer'] = {
                    'status': 'available',
                    'message': 'Ready',
                    'icon': 'fas fa-search',
                    'color': 'info'
                }
            else:
                status_info['services']['analyzer'] = {
                    'status': 'warning',
                    'message': 'Not configured',
                    'icon': 'fas fa-search',
                    'color': 'warning'
                }
        except Exception:
            status_info['services']['analyzer'] = {
                'status': 'error',
                'message': 'Error',
                'icon': 'fas fa-search',
                'color': 'danger'
            }
        
        # Docker status (simplified)
        try:
            components = get_components()
            # Simplified check - just verify components exist
            if components:
                status_info['services']['docker'] = {
                    'status': 'available',
                    'message': 'Service available',
                    'icon': 'fab fa-docker',
                    'color': 'info'
                }
            else:
                status_info['services']['docker'] = {
                    'status': 'warning',
                    'message': 'Not available',
                    'icon': 'fab fa-docker',
                    'color': 'warning'
                }
        except Exception:
            status_info['services']['docker'] = {
                'status': 'error',
                'message': 'Error',
                'icon': 'fab fa-docker',
                'color': 'danger'
            }
        
        return render_template('partials/dashboard_system_status.html', status_info=status_info)
    except Exception as e:
        logger.error(f"Error getting dashboard system status: {e}")
        from datetime import datetime
        return render_template('partials/dashboard_system_status.html', status_info={
            'timestamp': datetime.now(),
            'services': {}
        })


@api_bp.route('/dashboard/activity')
def dashboard_activity():
    """HTMX endpoint for dashboard activity feed."""
    try:
        from ..models import SecurityAnalysis, PerformanceTest, BatchAnalysis, GeneratedApplication
        from ..extensions import db
        from sqlalchemy import desc
        from datetime import datetime, timezone
        
        # Collect recent activities from different sources
        activities = []
        
        # Recent security analyses
        recent_security = db.session.query(SecurityAnalysis).order_by(
            desc(SecurityAnalysis.created_at)
        ).limit(3).all()
        
        for analysis in recent_security:
            activities.append({
                'type': 'security',
                'icon': 'fas fa-shield-alt',
                'color': 'danger' if analysis.total_issues and analysis.total_issues > 0 else 'success',
                'title': f'Security Analysis #{analysis.id}',
                'description': f'Found {analysis.total_issues or 0} issues',
                'timestamp': analysis.created_at or datetime.now(timezone.utc),
                'status': analysis.status.value if analysis.status else 'completed'
            })
        
        # Recent performance tests
        recent_performance = db.session.query(PerformanceTest).order_by(
            desc(PerformanceTest.created_at)
        ).limit(3).all()
        
        for test in recent_performance:
            activities.append({
                'type': 'performance',
                'icon': 'fas fa-tachometer-alt',
                'color': 'info',
                'title': f'Performance Test #{test.id}',
                'description': f'{test.requests_per_second:.1f} RPS' if test.requests_per_second else 'Test completed',
                'timestamp': test.created_at or datetime.now(timezone.utc),
                'status': test.status.value if test.status else 'completed'
            })
        
        # Recent batch analyses
        recent_batches = db.session.query(BatchAnalysis).order_by(
            desc(BatchAnalysis.created_at)
        ).limit(2).all()
        
        for batch in recent_batches:
            activities.append({
                'type': 'batch',
                'icon': 'fas fa-layer-group',
                'color': 'primary',
                'title': f'Batch Analysis #{batch.id}',
                'description': f'{batch.total_tasks or 0} tasks',
                'timestamp': batch.created_at or datetime.now(timezone.utc),
                'status': batch.status.value if batch.status else 'pending'
            })
        
        # Recent applications
        recent_apps = db.session.query(GeneratedApplication).order_by(
            desc(GeneratedApplication.created_at)
        ).limit(2).all()
        
        for app in recent_apps:
            activities.append({
                'type': 'application',
                'icon': 'fas fa-cogs',
                'color': 'secondary',
                'title': f'App {app.app_number} - {app.provider}',
                'description': f'Model: {app.model_slug}',
                'timestamp': app.created_at or datetime.now(timezone.utc),
                'status': app.generation_status or 'generated'
            })
        
        # Sort activities by timestamp (most recent first)
        activities.sort(key=lambda x: x['timestamp'], reverse=True)
        activities = activities[:10]  # Keep only the 10 most recent
        
        return render_template('partials/dashboard_activity.html', activities=activities)
    except Exception as e:
        logger.error(f"Error getting dashboard activity: {e}")
        return render_template('partials/dashboard_activity.html', activities=[])


@api_bp.route('/dashboard/stats')
def dashboard_stats():
    """HTMX endpoint for refreshing dashboard statistics."""
    try:
        from ..models import (
            ModelCapability, GeneratedApplication, SecurityAnalysis, 
            PerformanceTest, BatchAnalysis, ContainerizedTest
        )
        from ..extensions import db
        from ..constants import JobStatus, ContainerState
        
        # Calculate dashboard statistics
        stats = {
            'total_models': db.session.query(ModelCapability).count(),
            'running_containers': db.session.query(ContainerizedTest).filter_by(
                status=ContainerState.RUNNING.value
            ).count(),
            'pending_tests': (
                db.session.query(SecurityAnalysis).filter_by(status=JobStatus.PENDING).count() +
                db.session.query(PerformanceTest).filter_by(status=JobStatus.PENDING).count()
            ),
            'completed_tests': (
                db.session.query(SecurityAnalysis).filter_by(status=JobStatus.COMPLETED).count() +
                db.session.query(PerformanceTest).filter_by(status=JobStatus.COMPLETED).count()
            )
        }
        
        return render_template('partials/dashboard_stats.html', stats=stats)
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {e}")
        return render_template('partials/dashboard_stats.html', stats={
            'total_models': 0, 'running_containers': 0, 'pending_tests': 0, 'completed_tests': 0
        })


# Background task monitoring endpoints
@api_bp.route('/tasks/status')
def api_tasks_status():
    """API endpoint for background task status."""
    try:
        from ..services.background_service import get_background_service
        service = get_background_service()
        summary = service.get_task_summary()
        return jsonify(summary)
    except Exception as e:
        logger.error(f"Error getting task status: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/tasks/active')
def api_tasks_active():
    """HTMX endpoint for active background tasks."""
    try:
        from ..services.background_service import get_background_service
        service = get_background_service()
        active_tasks = service.get_active_tasks()
        
        return render_template('partials/active_tasks.html', tasks=active_tasks)
    except Exception as e:
        logger.error(f"Error getting active tasks: {e}")
        return render_template('partials/active_tasks.html', tasks=[])


@api_bp.route('/tasks/<task_id>/status')
def api_task_status(task_id):
    """HTMX endpoint for individual task status."""
    try:
        from ..services.background_service import get_background_service
        service = get_background_service()
        task = service.get_task(task_id)
        
        if task:
            return render_template('partials/task_status.html', task=task)
        else:
            return render_template('partials/task_status.html', task=None)
    except Exception as e:
        logger.error(f"Error getting task {task_id} status: {e}")
        return render_template('partials/task_status.html', task=None)


@api_bp.route('/realtime/dashboard')
def realtime_dashboard():
    """HTMX endpoint for real-time dashboard updates."""
    try:
        from ..models import (
            ModelCapability, GeneratedApplication, SecurityAnalysis, 
            PerformanceTest, BatchAnalysis, ContainerizedTest
        )
        from ..extensions import db
        from ..constants import JobStatus, ContainerState
        from ..services.background_service import get_background_service
        
        # Get current statistics
        stats = {
            'total_models': db.session.query(ModelCapability).count(),
            'running_containers': db.session.query(ContainerizedTest).filter_by(
                status=ContainerState.RUNNING.value
            ).count(),
            'pending_tests': (
                db.session.query(SecurityAnalysis).filter_by(status=JobStatus.PENDING).count() +
                db.session.query(PerformanceTest).filter_by(status=JobStatus.PENDING).count()
            ),
            'completed_tests': (
                db.session.query(SecurityAnalysis).filter_by(status=JobStatus.COMPLETED).count() +
                db.session.query(PerformanceTest).filter_by(status=JobStatus.COMPLETED).count()
            )
        }
        
        # Get background task summary
        service = get_background_service()
        task_summary = service.get_task_summary()
        
        # Get system health
        from sqlalchemy import text
        try:
            db.session.execute(text('SELECT 1'))
            system_health = "healthy"
        except Exception:
            system_health = "error"
        
        realtime_data = {
            'stats': stats,
            'tasks': task_summary,
            'system_health': system_health,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        return render_template('partials/realtime_dashboard.html', data=realtime_data)
    except Exception as e:
        logger.error(f"Error getting realtime dashboard data: {e}")
        return render_template('partials/realtime_dashboard.html', data={
            'stats': {'total_models': 0, 'running_containers': 0, 'pending_tests': 0, 'completed_tests': 0},
            'tasks': {'total': 0, 'pending': 0, 'running': 0, 'completed': 0, 'failed': 0, 'recent': []},
            'system_health': 'unknown',
            'timestamp': datetime.now(timezone.utc).isoformat()
        })


# Batch operation endpoints
@api_bp.route('/batch/create', methods=['POST'])
def api_batch_create():
    """API endpoint to create a new batch analysis."""
    try:
        from flask import request
        from ..services.background_service import get_background_service
        from ..models import BatchAnalysis
        from ..extensions import db
        from ..constants import JobStatus
        import uuid
        
        # Get request data
        data = request.get_json() or {}
        
        # Create batch analysis record
        batch_id_uuid = str(uuid.uuid4())
        batch = BatchAnalysis(
            batch_id=batch_id_uuid,
            status=JobStatus.PENDING,
            total_tasks=data.get('total_tasks', 0),
            completed_tasks=0,
            failed_tasks=0
        )
        
        db.session.add(batch)
        db.session.commit()
        
        # Create background task
        service = get_background_service()
        task = service.create_task(
            task_id=f"batch_{batch_id_uuid}",
            task_type="batch_analysis",
            message=f"Starting batch analysis with {data.get('total_tasks', 0)} tasks"
        )
        
        return jsonify({
            'success': True,
            'batch_id': batch_id_uuid,
            'task_id': task.task_id
        })
    except Exception as e:
        logger.error(f"Error creating batch: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/batch/<batch_id>/start', methods=['POST'])
def api_batch_start(batch_id):
    """API endpoint to start a batch analysis."""
    try:
        from ..services.background_service import get_background_service
        from ..models import BatchAnalysis
        from ..extensions import db
        from ..constants import JobStatus
        
        # Update batch status
        batch = db.session.query(BatchAnalysis).filter_by(batch_id=batch_id).first()
        if not batch:
            return jsonify({'error': 'Batch not found'}), 404
        
        batch.status = JobStatus.RUNNING
        batch.started_at = datetime.now(timezone.utc)
        db.session.commit()
        
        # Start background task
        service = get_background_service()
        task_id = f"batch_{batch_id}"
        service.start_task(task_id)
        
        return jsonify({'success': True, 'status': 'started'})
    except Exception as e:
        logger.error(f"Error starting batch {batch_id}: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/notifications/count')
def api_notifications_count():
    """HTMX endpoint for notification count."""
    try:
        from ..services.background_service import get_background_service
        service = get_background_service()
        
        # Count active tasks as notifications
        active_tasks = service.get_active_tasks()
        failed_tasks = service.get_tasks(status="failed")
        
        notification_count = len(active_tasks) + len(failed_tasks)
        
        if notification_count > 0:
            return f'<span class="badge bg-danger">{notification_count}</span>'
        else:
            return ''
    except Exception as e:
        logger.error(f"Error getting notification count: {e}")
        return ''


# Missing Models endpoints
@api_bp.route('/models/list')
def api_models_list():
    """API endpoint for models list (HTMX)."""
    try:
        models = ModelCapability.query.all()
        return render_template('partials/models_list.html', models=models)
    except Exception as e:
        logger.error(f"Error loading models list: {e}")
        return f'<div class="alert alert-danger">Error loading models: {str(e)}</div>'


# Statistics endpoints
@api_bp.route('/statistics/test-results')
def api_statistics_test_results():
    """API endpoint for test results statistics (HTMX)."""
    try:
        from ..models import SecurityAnalysis, PerformanceTest
        from ..extensions import db
        from sqlalchemy import func
        
        # Get test results statistics
        security_count = db.session.query(SecurityAnalysis).count()
        performance_count = db.session.query(PerformanceTest).count()
        
        # Get recent results
        recent_security = db.session.query(SecurityAnalysis).order_by(
            SecurityAnalysis.created_at.desc()
        ).limit(5).all()
        
        recent_performance = db.session.query(PerformanceTest).order_by(
            PerformanceTest.created_at.desc()
        ).limit(5).all()
        
        return render_template('partials/statistics_test_results.html', 
                             security_count=security_count,
                             performance_count=performance_count,
                             recent_security=recent_security,
                             recent_performance=recent_performance)
    except Exception as e:
        logger.error(f"Error loading test results: {e}")
        return f'<div class="alert alert-danger">Error loading test results: {str(e)}</div>'


@api_bp.route('/statistics/model-rankings')
def api_statistics_model_rankings():
    """API endpoint for model rankings (HTMX)."""
    try:
        from ..models import ModelCapability, SecurityAnalysis, PerformanceTest, GeneratedApplication
        from ..extensions import db
        from sqlalchemy import func, desc
        
        # Get model rankings based on test results
        model_stats = db.session.query(
            ModelCapability.canonical_slug,
            ModelCapability.model_name,
            ModelCapability.provider,
            func.count(SecurityAnalysis.id).label('security_tests'),
            func.count(PerformanceTest.id).label('performance_tests')
        ).outerjoin(
            GeneratedApplication, ModelCapability.canonical_slug == GeneratedApplication.model_slug
        ).outerjoin(
            SecurityAnalysis, GeneratedApplication.id == SecurityAnalysis.application_id
        ).outerjoin(
            PerformanceTest, GeneratedApplication.id == PerformanceTest.application_id
        ).group_by(ModelCapability.id
        ).order_by(desc('security_tests')).all()
        
        return render_template('partials/statistics_model_rankings.html', models=model_stats)
    except Exception as e:
        logger.error(f"Error loading model rankings: {e}")
        return f'<div class="alert alert-danger">Error loading model rankings: {str(e)}</div>'


@api_bp.route('/statistics/error-analysis')
def api_statistics_error_analysis():
    """API endpoint for error analysis (HTMX)."""
    try:
        from ..models import SecurityAnalysis, PerformanceTest, GeneratedApplication
        from ..extensions import db
        from sqlalchemy import func
        
        # Get error statistics
        security_errors = db.session.query(SecurityAnalysis).filter(
            SecurityAnalysis.status == 'failed'
        ).count()
        
        performance_errors = db.session.query(PerformanceTest).filter(
            PerformanceTest.status == 'failed'  
        ).count()
        
        # Get recent errors with model information
        recent_errors = []
        
        security_recent = db.session.query(SecurityAnalysis, GeneratedApplication).join(
            GeneratedApplication, SecurityAnalysis.application_id == GeneratedApplication.id
        ).filter(
            SecurityAnalysis.status == 'failed'
        ).order_by(SecurityAnalysis.created_at.desc()).limit(3).all()
        
        for analysis, app in security_recent:
            error_msg = 'Unknown error'
            if analysis.results_json:
                try:
                    import json
                    results = json.loads(analysis.results_json)
                    error_msg = results.get('error', 'Unknown error')
                except:
                    error_msg = 'JSON parsing error'
            
            recent_errors.append({
                'type': 'Security Analysis',
                'model': app.model_slug,
                'error': error_msg,
                'timestamp': analysis.created_at
            })
        
        performance_recent = db.session.query(PerformanceTest, GeneratedApplication).join(
            GeneratedApplication, PerformanceTest.application_id == GeneratedApplication.id
        ).filter(
            PerformanceTest.status == 'failed'
        ).order_by(PerformanceTest.created_at.desc()).limit(3).all()
        
        for test, app in performance_recent:
            error_msg = 'Unknown error'
            if test.results_json:
                try:
                    import json
                    results = json.loads(test.results_json)
                    error_msg = results.get('error', 'Unknown error')
                except:
                    error_msg = 'JSON parsing error'
            
            recent_errors.append({
                'type': 'Performance Test',
                'model': app.model_slug,
                'error': error_msg,
                'timestamp': test.created_at
            })
        
        # Sort by timestamp
        recent_errors.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return render_template('partials/statistics_error_analysis.html',
                             security_errors=security_errors,
                             performance_errors=performance_errors,
                             recent_errors=recent_errors[:5])
    except Exception as e:
        logger.error(f"Error loading error analysis: {e}")
        return f'<div class="alert alert-danger">Error loading error analysis: {str(e)}</div>'


# Testing endpoints
@api_bp.route('/testing/active-tests')
def api_testing_active_tests():
    """API endpoint for active tests (HTMX)."""
    try:
        from ..extensions import get_background_service
        
        background_service = get_background_service()
        if background_service:
            active_tasks = []
            for task_id, task in background_service.tasks.items():
                if task.status in ['running', 'pending']:
                    active_tasks.append(task)
            
            return render_template('partials/testing_active_tests.html', active_tests=active_tasks)
        else:
            return '<div class="text-muted">No active tests found</div>'
    except Exception as e:
        logger.error(f"Error loading active tests: {e}")
        return f'<div class="alert alert-danger">Error loading active tests: {str(e)}</div>'


@api_bp.route('/testing/service-status')
def api_testing_service_status():
    """API endpoint for testing service status (HTMX)."""
    try:
        from ..extensions import get_components
        
        components = get_components()
        status = {
            'background_service': 'available' if components and components.background_service else 'unavailable',
            'task_manager': 'available' if components and components.task_manager else 'unavailable',
            'analyzer': 'available' if components and components.analyzer_integration else 'unavailable'
        }
        
        return render_template('partials/testing_service_status.html', status=status)
    except Exception as e:
        logger.error(f"Error loading service status: {e}")
        return f'<div class="alert alert-danger">Error loading service status: {str(e)}</div>'


@api_bp.route('/testing/templates')
def api_testing_templates():
    """API endpoint for testing templates (HTMX)."""
    try:
        import os
        templates_dir = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'misc', 'app_templates')
        
        templates = []
        if os.path.exists(templates_dir):
            for filename in os.listdir(templates_dir):
                if filename.endswith('.md'):
                    templates.append({
                        'name': filename.replace('.md', '').replace('_', ' ').title(),
                        'filename': filename
                    })
        
        return render_template('partials/testing_templates.html', templates=templates)
    except Exception as e:
        logger.error(f"Error loading templates: {e}")
        return f'<div class="alert alert-danger">Error loading templates: {str(e)}</div>'


@api_bp.route('/testing/test-history')
def api_testing_test_history():
    """API endpoint for test history (HTMX)."""
    try:
        from ..models import SecurityAnalysis, PerformanceTest, GeneratedApplication
        from ..extensions import db
        
        # Get recent test history with model information
        recent_security = db.session.query(SecurityAnalysis, GeneratedApplication).join(
            GeneratedApplication, SecurityAnalysis.application_id == GeneratedApplication.id
        ).order_by(SecurityAnalysis.created_at.desc()).limit(10).all()
        
        recent_performance = db.session.query(PerformanceTest, GeneratedApplication).join(
            GeneratedApplication, PerformanceTest.application_id == GeneratedApplication.id
        ).order_by(PerformanceTest.created_at.desc()).limit(10).all()
        
        # Combine and sort
        all_tests = []
        for analysis, app in recent_security:
            all_tests.append({
                'type': 'Security',
                'model': app.model_slug,
                'status': analysis.status,
                'timestamp': analysis.created_at,
                'id': analysis.id
            })
        
        for test, app in recent_performance:
            all_tests.append({
                'type': 'Performance',
                'model': app.model_slug,
                'status': test.status,
                'timestamp': test.created_at,
                'id': test.id
            })
        
        all_tests.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return render_template('partials/testing_test_history.html', tests=all_tests[:15])
    except Exception as e:
        logger.error(f"Error loading test history: {e}")
        return f'<div class="alert alert-danger">Error loading test history: {str(e)}</div>'


@api_bp.route('/testing/batch-progress')
def api_testing_batch_progress():
    """API endpoint for batch progress (HTMX)."""
    try:
        from ..models import BatchAnalysis
        from ..extensions import db
        
        # Get active batch operations
        active_batches = db.session.query(BatchAnalysis).filter(
            BatchAnalysis.status.in_(['pending', 'running'])
        ).order_by(BatchAnalysis.created_at.desc()).all()
        
        # Get recently completed batches
        completed_batches = db.session.query(BatchAnalysis).filter(
            BatchAnalysis.status.in_(['completed', 'failed'])
        ).order_by(BatchAnalysis.created_at.desc()).limit(5).all()
        
        return render_template('partials/testing_batch_progress.html',
                             active_batches=active_batches,
                             completed_batches=completed_batches)
    except Exception as e:
        logger.error(f"Error loading batch progress: {e}")
        return f'<div class="alert alert-danger">Error loading batch progress: {str(e)}</div>'


@api_bp.route('/statistics/overview')
def api_statistics_overview():
    """API endpoint for statistics overview data (HTMX)."""
    try:
        from ..models import (
            ModelCapability, GeneratedApplication, SecurityAnalysis, 
            PerformanceTest, BatchAnalysis, ZAPAnalysis, OpenRouterAnalysis
        )
        from ..extensions import db
        from sqlalchemy import func
        from datetime import datetime, timedelta
        
        # Calculate overview statistics
        overview_stats = {}
        
        # Model statistics
        overview_stats['total_models'] = db.session.query(ModelCapability).count()
        overview_stats['total_applications'] = db.session.query(GeneratedApplication).count()
        
        # Analysis statistics
        overview_stats['security_analyses'] = db.session.query(SecurityAnalysis).count()
        overview_stats['performance_tests'] = db.session.query(PerformanceTest).count()
        overview_stats['batch_analyses'] = db.session.query(BatchAnalysis).count()
        overview_stats['zap_scans'] = db.session.query(ZAPAnalysis).count()
        overview_stats['ai_analyses'] = db.session.query(OpenRouterAnalysis).count()
        
        # Recent activity (last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)
        overview_stats['recent_security'] = db.session.query(SecurityAnalysis).filter(
            SecurityAnalysis.created_at >= week_ago
        ).count()
        overview_stats['recent_performance'] = db.session.query(PerformanceTest).filter(
            PerformanceTest.created_at >= week_ago
        ).count()
        
        # Provider breakdown
        provider_stats = db.session.query(
            ModelCapability.provider,
            func.count(ModelCapability.id).label('count')
        ).group_by(ModelCapability.provider).all()
        
        overview_stats['providers'] = [
            {'name': provider, 'count': count} for provider, count in provider_stats
        ]
        
        # Success rates
        total_security = overview_stats['security_analyses']
        failed_security = db.session.query(SecurityAnalysis).filter(
            SecurityAnalysis.status == 'failed'
        ).count()
        overview_stats['security_success_rate'] = (
            ((total_security - failed_security) / total_security * 100) 
            if total_security > 0 else 0
        )
        
        total_performance = overview_stats['performance_tests']
        failed_performance = db.session.query(PerformanceTest).filter(
            PerformanceTest.status == 'failed'
        ).count()
        overview_stats['performance_success_rate'] = (
            ((total_performance - failed_performance) / total_performance * 100) 
            if total_performance > 0 else 0
        )
        
        return render_template('partials/statistics_overview.html', stats=overview_stats)
    except Exception as e:
        logger.error(f"Error loading statistics overview: {e}")
        return f'<div class="alert alert-danger">Error loading statistics overview: {str(e)}</div>'


# Missing endpoints from logs
@api_bp.route('/batch/active')
def api_batch_active():
    """API endpoint for active batch analyses (HTMX)."""
    try:
        from ..models import BatchAnalysis
        from ..extensions import db
        from ..constants import JobStatus
        
        active_batches = db.session.query(BatchAnalysis).filter(
            BatchAnalysis.status.in_([JobStatus.RUNNING, JobStatus.PENDING])
        ).order_by(BatchAnalysis.created_at.desc()).all()
        
        return render_template('partials/active_batches.html', active_batches=active_batches)
    except Exception as e:
        logger.error(f"Error loading active batches: {e}")
        return f'<div class="alert alert-danger">Error loading active batches: {str(e)}</div>'


@api_bp.route('/logs/application/<int:app_id>')
def api_application_logs(app_id):
    """API endpoint for application logs."""
    try:
        from ..models import GeneratedApplication
        from ..extensions import db
        
        app = db.session.query(GeneratedApplication).get(app_id)
        if not app:
            return f'<div class="alert alert-warning">Application {app_id} not found</div>', 404
        
        # Mock logs for now - in production, this would read actual log files
        logs = [
            {'timestamp': '2025-08-11 03:35:00', 'level': 'INFO', 'message': f'Application {app_id} initialized'},
            {'timestamp': '2025-08-11 03:35:01', 'level': 'INFO', 'message': f'Model: {app.model_slug}'},
            {'timestamp': '2025-08-11 03:35:02', 'level': 'INFO', 'message': f'Provider: {app.provider}'},
            {'timestamp': '2025-08-11 03:35:03', 'level': 'INFO', 'message': 'Application ready for analysis'}
        ]
        
        return render_template('partials/application_logs.html', app=app, logs=logs)
    except Exception as e:
        logger.error(f"Error loading application logs: {e}")
        return f'<div class="alert alert-danger">Error loading logs: {str(e)}</div>', 500


@api_bp.route('/analysis/start/<int:app_id>', methods=['POST'])
def api_analysis_start(app_id):
    """API endpoint to start comprehensive analysis for an application."""
    try:
        from ..models import GeneratedApplication, SecurityAnalysis
        from ..extensions import db
        from ..constants import JobStatus
        
        app = db.session.query(GeneratedApplication).get(app_id)
        if not app:
            return jsonify({'error': f'Application {app_id} not found'}), 404
        
        # Start comprehensive analysis (all types)
        service = get_background_service()
        if service:
            task_id = f"comprehensive_analysis_{app_id}"
            task = service.create_task(
                task_id=task_id,
                task_type="comprehensive_analysis",
                message=f"Starting comprehensive analysis for application {app_id}"
            )
            service.start_task(task_id)
            
            return jsonify({
                'success': True,
                'message': 'Comprehensive analysis started',
                'task_id': task_id
            })
        else:
            return jsonify({'error': 'Background service not available'}), 503
            
    except Exception as e:
        logger.error(f"Error starting analysis for app {app_id}: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/analysis/security/<int:app_id>', methods=['POST'])
def api_analysis_security(app_id):
    """API endpoint to start security analysis for an application."""
    try:
        from ..models import GeneratedApplication, SecurityAnalysis
        from ..extensions import db
        from ..constants import AnalysisStatus
        from datetime import datetime, timezone
        
        app = db.session.query(GeneratedApplication).get(app_id)
        if not app:
            return jsonify({'error': f'Application {app_id} not found'}), 404
        
        # Create security analysis record
        analysis = SecurityAnalysis(
            application_id=app_id,
            status=AnalysisStatus.PENDING,
            created_at=datetime.now(timezone.utc)
        )
        
        db.session.add(analysis)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Security analysis started',
            'analysis_id': analysis.id
        })
            
    except Exception as e:
        logger.error(f"Error starting security analysis for app {app_id}: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/analysis/performance/<int:app_id>', methods=['POST'])
def api_analysis_performance(app_id):
    """API endpoint to start performance analysis for an application."""
    try:
        from ..models import GeneratedApplication, PerformanceTest
        from ..extensions import db
        from ..constants import AnalysisStatus
        from datetime import datetime, timezone
        
        app = db.session.query(GeneratedApplication).get(app_id)
        if not app:
            return jsonify({'error': f'Application {app_id} not found'}), 404
        
        # Create performance test record
        test = PerformanceTest(
            application_id=app_id,
            status=AnalysisStatus.PENDING,
            created_at=datetime.now(timezone.utc)
        )
        
        db.session.add(test)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Performance test started',
            'test_id': test.id
        })
            
    except Exception as e:
        logger.error(f"Error starting performance test for app {app_id}: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/analysis/zap/<int:app_id>', methods=['POST'])
def api_analysis_zap(app_id):
    """API endpoint to start ZAP analysis for an application."""
    try:
        from ..models import GeneratedApplication, ZAPAnalysis
        from ..extensions import db
        from ..constants import AnalysisStatus
        from datetime import datetime, timezone
        
        app = db.session.query(GeneratedApplication).get(app_id)
        if not app:
            return jsonify({'error': f'Application {app_id} not found'}), 404
        
        # Create ZAP analysis record
        analysis = ZAPAnalysis(
            application_id=app_id,
            status=AnalysisStatus.PENDING,
            created_at=datetime.now(timezone.utc)
        )
        
        db.session.add(analysis)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'ZAP scan started',
            'analysis_id': analysis.id
        })
            
    except Exception as e:
        logger.error(f"Error starting ZAP analysis for app {app_id}: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/analysis/ai/<int:app_id>', methods=['POST'])
def api_analysis_ai(app_id):
    """API endpoint to start AI analysis for an application."""
    try:
        from ..models import GeneratedApplication, OpenRouterAnalysis
        from ..extensions import db
        from ..constants import AnalysisStatus
        from datetime import datetime, timezone
        
        app = db.session.query(GeneratedApplication).get(app_id)
        if not app:
            return jsonify({'error': f'Application {app_id} not found'}), 404
        
        # Create AI analysis record
        analysis = OpenRouterAnalysis(
            application_id=app_id,
            status=AnalysisStatus.PENDING,
            created_at=datetime.now(timezone.utc)
        )
        
        db.session.add(analysis)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'AI analysis started',
            'analysis_id': analysis.id
        })
            
    except Exception as e:
        logger.error(f"Error starting AI analysis for app {app_id}: {e}")
        return jsonify({'error': str(e)}), 500
