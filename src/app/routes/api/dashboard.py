"""
Dashboard API Routes
====================

API endpoints for dashboard data and visualizations.
"""

import logging
from flask import jsonify
from app.utils.template_paths import render_template_compat as render_template
from flask import Response
import psutil
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, desc, text

from . import api_bp
from ...models import (
    GeneratedApplication, SecurityAnalysis, PerformanceTest, ModelCapability,
    BatchAnalysis, ContainerizedTest
)
from ...extensions import db
from ...constants import JobStatus, ContainerState

# Set up logger
logger = logging.getLogger(__name__)


@api_bp.route('/dashboard/overview')
def api_dashboard_overview():
    """API endpoint: Get dashboard overview data."""
    try:
        # Total counts
        total_apps = db.session.query(func.count(GeneratedApplication.id)).scalar()
        total_models = db.session.query(func.count(ModelCapability.id)).scalar()
        total_security = db.session.query(func.count(SecurityAnalysis.id)).scalar()
        total_performance = db.session.query(func.count(PerformanceTest.id)).scalar()

        # Recent activity (last 7 days)
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        recent_apps = (
            db.session.query(func.count(GeneratedApplication.id))
            .filter(GeneratedApplication.created_at >= week_ago)
            .scalar()
        )

        # Active applications
        active_apps = (
            db.session.query(func.count(GeneratedApplication.id))
            .filter(GeneratedApplication.container_status == 'running')
            .scalar()
        )

        # Success rates
        completed_security = (
            db.session.query(func.count(SecurityAnalysis.id))
            .filter(SecurityAnalysis.status == 'completed')
            .scalar()
        )
        security_rate = (completed_security / total_security * 100) if total_security > 0 else 0

        completed_performance = (
            db.session.query(func.count(PerformanceTest.id))
            .filter(PerformanceTest.status == 'completed')
            .scalar()
        )
        performance_rate = (completed_performance / total_performance * 100) if total_performance > 0 else 0

        return jsonify({
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
        logger.error(f"Error getting dashboard overview: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/dashboard/activity')
def api_dashboard_activity():
    """API endpoint: Get recent activity for dashboard."""
    try:
        # Last 30 days of application creation
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        
        daily_apps = (
            db.session.query(
                func.date(GeneratedApplication.created_at).label('date'),
                func.count(GeneratedApplication.id).label('count')
            )
            .filter(GeneratedApplication.created_at >= thirty_days_ago)
            .group_by(func.date(GeneratedApplication.created_at))
            .order_by('date')
            .all()
        )
        
        # Recent applications with details
        recent_apps = (
            GeneratedApplication.query
            .filter(GeneratedApplication.created_at >= thirty_days_ago)
            .order_by(desc(GeneratedApplication.created_at))
            .limit(10)
            .all()
        )
        
        # Analysis activity
        recent_security = (
            SecurityAnalysis.query
            .filter(SecurityAnalysis.created_at >= thirty_days_ago)
            .order_by(desc(SecurityAnalysis.created_at))
            .limit(5)
            .all()
        )
        
        recent_performance = (
            PerformanceTest.query
            .filter(PerformanceTest.created_at >= thirty_days_ago)
            .order_by(desc(PerformanceTest.created_at))
            .limit(5)
            .all()
        )
        
        return jsonify({
            'daily_activity': [
                {
                    'date': str(date),
                    'applications': count
                }
                for date, count in daily_apps
            ],
            'recent_applications': [app.to_dict() for app in recent_apps],
            'recent_security': [analysis.to_dict() for analysis in recent_security],
            'recent_performance': [test.to_dict() for test in recent_performance]
        })
        
    except Exception as e:
        logger.error(f"Error getting dashboard activity: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/dashboard/activity-timeline')
def dashboard_activity_timeline():
    """Render activity timeline HTML for dashboard."""
    try:
        # Build recent activities list
        activities = []

        recent_apps = (
            GeneratedApplication.query
            .order_by(desc(GeneratedApplication.created_at))
            .limit(5)
            .all()
        )
        for app in recent_apps:
            activities.append({
                'type': 'success',
                'title': 'New App Generated',
                'description': f'{app.model_slug} - App #{app.app_number}',
                'timestamp': app.created_at,
                'source': 'Generator',
                'status': 'completed'
            })

        recent_security = (
            SecurityAnalysis.query
            .join(GeneratedApplication)
            .order_by(desc(SecurityAnalysis.created_at))
            .limit(3)
            .all()
        )
        for analysis in recent_security:
            try:
                activities.append({
                    'type': 'info',
                    'title': 'Security Analysis',
                    'description': f'{analysis.application.model_slug} - App #{analysis.application.app_number}',
                    'timestamp': analysis.created_at,
                    'source': 'Security',
                    'status': analysis.status.value if hasattr(analysis.status, 'value') else str(analysis.status)
                })
            except AttributeError as e:
                logger.warning(f"Skipping security analysis due to missing application: {e}")
                continue

        # Normalize any legacy keys to 'timestamp' to satisfy template expectations
        for item in activities:
            if 'timestamp' not in item and 'created_at' in item:
                item['timestamp'] = item['created_at']
        activities.sort(key=lambda x: x.get('timestamp') or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        activities = activities[:8]
        return render_template('components/dashboard/activity-timeline.html', activities=activities)
    except Exception as e:
        logger.error(f"Error rendering activity timeline: {e}")
        return '<div class="text-center py-3"><p class="text-muted">Unable to load activity</p></div>'


@api_bp.route('/dashboard/charts')
def api_dashboard_charts():
    """API endpoint: Get chart data for dashboard."""
    try:
        # Application status distribution
        status_data = (
            db.session.query(
                GeneratedApplication.generation_status,
                func.count(GeneratedApplication.id).label('count')
            )
            .group_by(GeneratedApplication.generation_status)
            .all()
        )

        # Application type distribution
        type_data = (
            db.session.query(
                GeneratedApplication.app_type,
                func.count(GeneratedApplication.id).label('count')
            )
            .group_by(GeneratedApplication.app_type)
            .all()
        )

        # Model usage distribution
        model_usage = (
            db.session.query(
                GeneratedApplication.model_slug,
                func.count(GeneratedApplication.id).label('usage_count')
            )
            .group_by(GeneratedApplication.model_slug)
            .order_by(desc('usage_count'))
            .limit(10)
            .all()
        )

        # Analysis success rates over time (last 12 weeks)
        twelve_weeks_ago = datetime.now(timezone.utc) - timedelta(weeks=12)

        weekly_security = (
            db.session.query(
                func.date_trunc('week', SecurityAnalysis.created_at).label('week'),
                func.count(SecurityAnalysis.id).label('total'),
                func.sum(func.case([(SecurityAnalysis.status == 'completed', 1)], else_=0)).label('completed')
            )
            .filter(SecurityAnalysis.created_at >= twelve_weeks_ago)
            .group_by('week')
            .order_by('week')
            .all()
        )

        return jsonify({
            'status_distribution': [
                {'status': str(status), 'count': count}
                for status, count in status_data
            ],
            'type_distribution': [
                {'type': app_type, 'count': count}
                for app_type, count in type_data
            ],
            'model_usage': [
                {'model': model, 'usage': usage}
                for model, usage in model_usage
            ],
            'weekly_success_rates': [
                {
                    'week': str(week),
                    'total': total,
                    'completed': completed,
                    'success_rate': round((completed / total * 100) if total > 0 else 0, 2)
                }
                for week, total, completed in weekly_security
            ]
        })

    except Exception as e:
        logger.error(f"Error getting dashboard charts: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/dashboard/health')
def api_dashboard_health():
    """API endpoint: Get system health metrics for dashboard."""
    try:
        # Check for failed applications in last 24 hours
        day_ago = datetime.now(timezone.utc) - timedelta(days=1)

        failed_apps = (
            db.session.query(func.count(GeneratedApplication.id))
            .filter(
                GeneratedApplication.generation_status == 'failed',
                GeneratedApplication.updated_at >= day_ago
            )
            .scalar()
        )

        # Check for stuck analyses (created more than 1 hour ago but still pending)
        hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)

        stuck_security = (
            db.session.query(func.count(SecurityAnalysis.id))
            .filter(
                SecurityAnalysis.status == 'pending',
                SecurityAnalysis.created_at <= hour_ago
            )
            .scalar()
        )

        stuck_performance = (
            db.session.query(func.count(PerformanceTest.id))
            .filter(
                PerformanceTest.status == 'pending',
                PerformanceTest.created_at <= hour_ago
            )
            .scalar()
        )

        # Calculate overall health score
        health_issues = failed_apps + stuck_security + stuck_performance
        health_score = max(0, 100 - (health_issues * 10))  # Deduct 10 points per issue

        # Determine health status
        if health_score >= 90:
            health_status = 'excellent'
        elif health_score >= 70:
            health_status = 'good'
        elif health_score >= 50:
            health_status = 'warning'
        else:
            health_status = 'critical'

        return jsonify({
            'health_score': health_score,
            'health_status': health_status,
            'issues': {
                'failed_applications': failed_apps,
                'stuck_security_analyses': stuck_security,
                'stuck_performance_tests': stuck_performance
            },
            'last_updated': datetime.now(timezone.utc).isoformat()
        })

    except Exception as e:
        logger.error(f"Error getting dashboard health: {e}")
        return jsonify({'error': str(e)}), 500


# =================================================================
# HTMX DASHBOARD ENDPOINTS
# =================================================================

@api_bp.route('/sidebar_stats')
def sidebar_stats():
    """HTMX endpoint for sidebar statistics."""
    try:
        stats = {
            'total_models': db.session.query(ModelCapability).count(),
            'total_apps': db.session.query(GeneratedApplication).count(),
            'security_tests': db.session.query(SecurityAnalysis).count(),
            'performance_tests': db.session.query(PerformanceTest).count()
        }
        # Return only the inner fragment so outer wrapper doesn't duplicate on hx swaps
        return render_template('partials/common/_sidebar_stats_inner.html', stats=stats)
    except Exception as e:
        logger.error(f"Error getting sidebar stats: {e}")
        return render_template('partials/common/_sidebar_stats_inner.html', stats={
            'total_models': 0, 'total_apps': 0, 'security_tests': 0, 'performance_tests': 0
        })


@api_bp.route('/dashboard/stats-fragment')
def dashboard_stats_fragment():
    """HTMX endpoint returning dashboard stats inner fragment HTML."""
    try:
        stats = {
            'total_models': db.session.query(ModelCapability).count(),
            'total_apps': db.session.query(GeneratedApplication).count(),
            'security_tests': db.session.query(SecurityAnalysis).count(),
            'performance_tests': db.session.query(PerformanceTest).count(),
        }
        return render_template('partials/dashboard/_dashboard_stats_inner.html', stats=stats)
    except Exception as e:
        logger.error(f"Error rendering dashboard stats fragment: {e}")
        return render_template('partials/dashboard/_dashboard_stats_inner.html', stats={
            'total_models': 0,
            'total_apps': 0,
            'security_tests': 0,
            'performance_tests': 0,
            'recent_activity': []
        })


# Aliases expected by templates/JS
@api_bp.route('/dashboard/chart-data')
def api_dashboard_chart_data_alias():
    """Alias that returns same payload as /dashboard/charts for template JS fetch."""
    return api_dashboard_charts()


@api_bp.route('/dashboard/stats-update')
def api_dashboard_stats_update_alias():
    """Alias that returns stats fragment HTML for periodic refresh."""
    return dashboard_stats_fragment()


@api_bp.route('/dashboard/refresh')
def api_dashboard_refresh():
    """Lightweight refresh endpoint for HTMX. Returns an empty 204 or small message."""
    try:
        # Could assemble a composite partial; for now, let client panels refresh independently
        return Response(status=204)
    except Exception:
        return Response('', status=204)


@api_bp.route('/recent_activity')
def recent_activity():
    """HTMX endpoint for recent activity timeline."""
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
        
        if not activities:
            # Return fallback content that tests expect when no activity is available
            return '<div class="text-center py-3"><p class="text-muted">Unable to load activity</p></div>'
        return render_template('components/dashboard/activity-timeline.html', activities=activities)
    except Exception as e:
        logger.error(f"Error getting recent activity: {e}")
        return render_template('components/dashboard/activity-timeline.html', activities=[])


@api_bp.route('/recent_activity_detailed')
def recent_activity_detailed():
    """HTMX endpoint for detailed recent activity."""
    try:
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


@api_bp.route('/activity/clear', methods=['POST'])
def activity_clear():
    """Clear recent activity.

    Activities on this platform are derived from database records (apps/tests),
    so we don't delete history. This endpoint responds success for UX and
    clients can refresh the panel.
    """
    try:
        return jsonify({'success': True, 'message': 'Activity cleared (no-op)'}), 200
    except Exception as e:
        logger.error(f"Error clearing activity: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/activity/export')
def activity_export():
    """Export recent activity as CSV for download."""
    try:
        # Build the same activities list as recent_activity, but fetch more rows
        recent_security = db.session.query(SecurityAnalysis).order_by(desc(SecurityAnalysis.started_at)).limit(50).all()
        recent_performance = db.session.query(PerformanceTest).order_by(desc(PerformanceTest.started_at)).limit(50).all()
        recent_batch = db.session.query(BatchAnalysis).order_by(desc(BatchAnalysis.created_at)).limit(50).all()

        rows = ["type,description,timestamp,status"]

        def fmt_ts(ts):
            try:
                return ts.isoformat()
            except Exception:
                return ''

        for a in recent_security:
            if a.started_at:
                status = a.status.value if getattr(a, 'status', None) and hasattr(a.status, 'value') else str(getattr(a, 'status', 'unknown'))
                rows.append(f"security,Security analysis completed,{fmt_ts(a.started_at)},{status}")

        for t in recent_performance:
            if t.started_at:
                status = t.status.value if getattr(t, 'status', None) and hasattr(t.status, 'value') else str(getattr(t, 'status', 'unknown'))
                rows.append(f"performance,Performance test completed,{fmt_ts(t.started_at)},{status}")

        for b in recent_batch:
            if b.created_at:
                status = b.status.value if getattr(b, 'status', None) and hasattr(b.status, 'value') else str(getattr(b, 'status', 'unknown'))
                rows.append(f"batch,Batch analysis #{b.id},{fmt_ts(b.created_at)},{status}")
        
        csv_data = "\n".join(rows)

        filename = f"activity_log_{datetime.now(timezone.utc).date().isoformat()}.csv"
        return Response(
            csv_data,
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename={filename}'
            }
        )
    except Exception as e:
        logger.error(f"Error exporting activity: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/models_overview_summary')
def models_overview_summary():
    """HTMX endpoint for models overview summary."""
    try:
        # Get model statistics
        total_models = db.session.query(ModelCapability).count()
        total_apps = db.session.query(GeneratedApplication).count()
        
        # Get provider breakdown
        provider_stats = db.session.query(
            ModelCapability.provider,
            func.count(ModelCapability.id)
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
        # Get performance test data for the last 30 days
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
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


@api_bp.route('/dashboard/recent-models')
def dashboard_recent_models():
    """HTMX endpoint for dashboard recent models section."""
    try:
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


@api_bp.route('/realtime/dashboard')
def realtime_dashboard():
    """HTMX endpoint for real-time dashboard updates."""
    try:
        from ...services.background_service import get_background_service
        
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


@api_bp.route('/dashboard/docker-status')
def dashboard_docker_status():
    """HTMX endpoint for Docker infrastructure status."""
    try:
        import subprocess
        
        docker_info = {
            'timestamp': datetime.now(),
            'docker_available': False,
            'compose_available': False,
            'engine_running': False,
            'version': 'N/A',
            'total_containers': 0,
            'total_images': 0,
            'running_containers': 0,
            'stopped_containers': 0,
            'error_containers': 0,
            'created_containers': 0,
            'resource_usage': {},
            'recent_containers': [],
            'last_check': datetime.now(timezone.utc)
        }
        
        try:
            # Check if Docker is available
            result = subprocess.run(['docker', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                docker_info['docker_available'] = True
                docker_info['version'] = result.stdout.strip()
                
                # Check if Docker engine is running
                result = subprocess.run(['docker', 'info'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    docker_info['engine_running'] = True
                    
                    # Get container counts
                    try:
                        result = subprocess.run(['docker', 'ps', '-a', '--format', '{{.Status}}'], 
                                              capture_output=True, text=True, timeout=10)
                        if result.returncode == 0:
                            statuses = result.stdout.strip().split('\n') if result.stdout.strip() else []
                            docker_info['total_containers'] = len(statuses)
                            
                            for status in statuses:
                                if status.startswith('Up'):
                                    docker_info['running_containers'] += 1
                                elif status.startswith('Exited'):
                                    docker_info['stopped_containers'] += 1
                                elif 'error' in status.lower() or 'failed' in status.lower():
                                    docker_info['error_containers'] += 1
                                elif status.startswith('Created'):
                                    docker_info['created_containers'] += 1
                    except Exception:
                        pass
                    
                    # Get image count
                    try:
                        result = subprocess.run(['docker', 'images', '-q'], 
                                              capture_output=True, text=True, timeout=10)
                        if result.returncode == 0:
                            images = result.stdout.strip().split('\n') if result.stdout.strip() else []
                            docker_info['total_images'] = len(images)
                    except Exception:
                        pass
                        
        except subprocess.TimeoutExpired:
            docker_info['docker_available'] = False
        except FileNotFoundError:
            docker_info['docker_available'] = False
        except Exception as e:
            logger.error(f"Docker status check error: {e}")
            docker_info['docker_available'] = False

        # Return only inner fragment to avoid duplicating wrapper on HTMX swaps
        return render_template('partials/dashboard/_docker_status_inner.html', docker_status=docker_info)
    except Exception as e:
        logger.error(f"Error getting Docker status: {e}")
        return (
            '<div class="text-center py-3">'
            '<div class="empty-state">'
            '<i class="fab fa-docker fa-2x text-muted mb-2"></i>'
            '<div class="text-muted">Docker status unavailable</div>'
            '</div>'
            '</div>'
        )


@api_bp.route('/dashboard/system-health-fragment')
def dashboard_system_health_fragment():
    """HTMX endpoint returning system health inner fragment HTML."""
    try:
        # Database health check
        db_healthy = True
        try:
            from sqlalchemy import text
            db.session.execute(text('SELECT 1'))
        except Exception:
            db_healthy = False

        # Celery/analyzer status (best-effort without hard dependency)
        celery_status = {'status': 'warning', 'message': 'Unknown'}
        analyzer_status = {'status': 'warning', 'message': 'Unknown'}
        try:
            from ...extensions import get_components
            components = get_components()
            if components and getattr(components, 'celery', None):
                celery_status = {'status': 'healthy', 'message': 'Configured'}
            if components and getattr(components, 'analyzer_integration', None):
                analyzer_status = {'status': 'available', 'message': 'Service available'}
        except Exception:
            # Keep defaults
            pass

        # System resource metrics
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory_percent = psutil.virtual_memory().percent
            disk_percent = psutil.disk_usage('/').percent
        except Exception:
            cpu_percent = None
            memory_percent = None
            disk_percent = None

        # Determine overall status
        issues = 0
        if not db_healthy:
            issues += 1
        if cpu_percent is not None and cpu_percent > 85:
            issues += 1
        if memory_percent is not None and memory_percent > 85:
            issues += 1
        if disk_percent is not None and disk_percent > 90:
            issues += 1

        if issues == 0:
            overall = 'healthy'
        elif issues <= 2:
            overall = 'warning'
        else:
            overall = 'critical'

        system_health = {
            'overall_status': overall,
            'components': [
                {'name': 'Database', 'description': 'Primary DB connection', 'status': 'healthy' if db_healthy else 'error', 'message': ''},
                {'name': 'Celery', 'description': 'Background worker', 'status': celery_status.get('status', 'warning'), 'message': celery_status.get('message', '')},
                {'name': 'Analyzer', 'description': 'Analyzer integration', 'status': analyzer_status.get('status', 'warning'), 'message': analyzer_status.get('message', '')},
            ],
            'resources': {
                'cpu_usage': cpu_percent,
                'memory_usage': memory_percent,
                'disk_usage': disk_percent,
            },
            # Provide a datetime object so templates can call strftime safely
            'last_check': datetime.now(timezone.utc)
        }

        return render_template('partials/dashboard/_system_health_inner.html', system_health=system_health)
    except Exception as e:
        logger.error(f"Error rendering system health fragment: {e}")
        # Minimal fallback to avoid template errors
        return render_template('partials/dashboard/_system_health_inner.html', system_health=None)


@api_bp.route('/dashboard/analyzer-services')
def dashboard_analyzer_services():
    """HTMX endpoint returning analyzer services panel content.

    Renders the analyzer services list using 'partials/dashboard/analyzer_services.html'.
    Falls back to an empty list when analyzer integration is unavailable.
    """
    try:
        analyzer_services = []

        # Try to fetch status via the analyzer integration if available
        try:
            from ...extensions import get_components
            components = get_components()
            analyzer_integration = getattr(components, 'analyzer_integration', None) if components else None
            if analyzer_integration:
                status_info = analyzer_integration.get_services_status()
                services = status_info.get('services', {}) if isinstance(status_info, dict) else {}

                # Normalize services mapping into list of dicts expected by template
                for name, info in services.items():
                    analyzer_services.append({
                        'name': name,
                        'display_name': info.get('display_name') or name.replace('-', ' ').title(),
                        'description': info.get('description') or 'Analyzer microservice',
                        'status': info.get('status') or 'unknown',
                        'port': info.get('port'),
                        'uptime': info.get('uptime') or info.get('uptime_human'),
                        'health_status': info.get('health') or info.get('health_status') or 'Unknown',
                        'error_message': info.get('error') or info.get('error_message')
                    })
        except Exception as inner_err:  # keep dashboard resilient
            logger.warning(f"Analyzer integration unavailable: {inner_err}")

        return render_template('partials/dashboard/analyzer_services.html', analyzer_services=analyzer_services)
    except Exception as e:
        logger.error(f"Error rendering analyzer services: {e}")
        return render_template('partials/dashboard/analyzer_services.html', analyzer_services=[])
    

# Alias route expected by templates: /api/dashboard/services -> same as analyzer-services
@api_bp.route('/dashboard/services')
def dashboard_services_alias():
    """Alias for analyzer services to match template expectations."""
    return dashboard_analyzer_services()


@api_bp.route('/dashboard/top-models')
def dashboard_top_models():
    """HTMX endpoint rendering a compact Top Models panel for the dashboard.

    Ranks models by number of generated applications and shows a simple list.
    """
    try:
        # Get top models by app count
        top = (
            db.session.query(
                GeneratedApplication.model_slug.label('model_slug'),
                func.count(GeneratedApplication.id).label('app_count')
            )
            .group_by(GeneratedApplication.model_slug)
            .order_by(desc('app_count'))
            .limit(10)
            .all()
        )

        # Fetch names/providers for slugs
        slug_to_meta = {m.canonical_slug: m for m in db.session.query(ModelCapability).all()}
        models = []
        for row in top:
            meta = slug_to_meta.get(row.model_slug)
            models.append({
                'model_slug': row.model_slug,
                'model_name': getattr(meta, 'model_name', row.model_slug),
                'provider': getattr(meta, 'provider', 'unknown'),
                'app_count': int(row.app_count or 0),
                # Placeholder success rate until a real metric is available
                'success_rate': 0
            })

        return render_template('partials/dashboard/top_models.html', top_models=models)
    except Exception as e:
        logger.error(f"Error rendering top models panel: {e}")
        return render_template('partials/dashboard/top_models.html', top_models=[])
