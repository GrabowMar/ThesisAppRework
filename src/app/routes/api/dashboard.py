"""
Dashboard API routes - CONSOLIDATED
====================================

Streamlined endpoints for dashboard overview, statistics, and HTMX fragments.
Reduced from 32 endpoints to 12 by using query parameters.
"""

from flask import Blueprint, current_app, request
import logging
from datetime import datetime, timezone, timedelta

from app.extensions import db
from app.models import (
    ModelCapability, GeneratedApplication, SecurityAnalysis, 
    PerformanceTest
)
from app.services.statistics_service import (
    get_application_statistics, get_model_statistics, get_analysis_statistics,
    get_recent_statistics, get_model_distribution, get_generation_trends,
    get_analysis_summary, export_statistics, get_generation_statistics_by_models
)
from app.services.dashboard_service import (
    build_summary_payload,
    build_system_status_payload,
    get_recent_activity_entries,
    get_recent_applications,
    get_recent_analysis_summary,
)
from .common import api_success, api_error

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard_api', __name__)


# =================================================================
# CORE DASHBOARD ENDPOINTS
# =================================================================

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

        # Active models (those with apps)
        active_models = (
            db.session.query(db.func.count(db.func.distinct(GeneratedApplication.model_id)))
            .scalar()
        )

        return api_success({
            'totals': {
                'applications': total_apps,
                'models': total_models,
                'security_tests': total_security,
                'performance_tests': total_performance,
            },
            'recent': {
                'applications_this_week': recent_apps,
                'active_models': active_models
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error getting dashboard overview: {e}")
        return api_error("Failed to retrieve dashboard overview", details={"reason": str(e)})


@dashboard_bp.route('/summary')
def dashboard_summary():
    """HTMX endpoint - full summary payload."""
    return api_success(build_summary_payload())


# =================================================================
# CONSOLIDATED STATS ENDPOINT (replaces 10 endpoints)
# =================================================================

@dashboard_bp.route('/stats')
def api_dashboard_stats():
    """
    Unified statistics endpoint with query parameter for type.
    
    Query params:
      ?type=full          - Full dashboard stats (default)
      ?type=apps          - Application statistics only
      ?type=models        - Model statistics only
      ?type=analysis      - Analysis statistics only
      ?type=recent        - Recent statistics only
      ?type=sidebar       - Sidebar stats only
      ?type=distribution  - Model distribution
      ?type=trends        - Generation trends
      ?type=summary       - Analysis summary
    """
    stat_type = request.args.get('type', 'full').lower()
    
    try:
        # Route to specific stat type
        if stat_type == 'apps':
            data = get_application_statistics()
            return api_success(data, message="Application statistics fetched")
            
        elif stat_type == 'models':
            data = get_model_statistics()
            return api_success(data, message="Model statistics fetched")
            
        elif stat_type == 'analysis':
            data = get_analysis_statistics()
            return api_success(data, message="Analysis statistics fetched")
            
        elif stat_type == 'recent':
            data = get_recent_statistics()
            return api_success(data, message="Recent statistics fetched")
            
        elif stat_type == 'distribution':
            data = get_model_distribution()
            return api_success(data, message="Model distribution fetched")
            
        elif stat_type == 'trends':
            data = get_generation_trends()
            return api_success(data, message="Generation trends fetched")
            
        elif stat_type == 'summary':
            data = get_analysis_summary()
            return api_success(data, message="Analysis summary fetched")
            
        elif stat_type == 'sidebar':
            # Sidebar stats
            stats = {
                'total_models': db.session.query(ModelCapability).count(),
                'total_apps': db.session.query(GeneratedApplication).count(),
                'security_tests': db.session.query(SecurityAnalysis).count(),
                'performance_tests': db.session.query(PerformanceTest).count()
            }
            return api_success(stats)
            
        else:  # 'full' or default
            # Full dashboard stats (original /stats logic)
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
        current_app.logger.error(f"Error getting stats (type={stat_type}): {e}")
        return api_error(f"Failed to retrieve {stat_type} statistics", details={"reason": str(e)})


@dashboard_bp.route('/stats/export')
def api_export_statistics():
    """Export statistics (kept separate due to different response format)."""
    data = export_statistics()
    return api_success(data, message="Statistics exported")


# =================================================================
# CONSOLIDATED SYSTEM STATUS ENDPOINT (replaces 3 endpoints)
# =================================================================

@dashboard_bp.route('/system-status')
def dashboard_system_status():
    """
    Unified system status endpoint.
    
    Query params:
      ?level=simple          - Simple status (default)
      ?level=comprehensive   - Full comprehensive health check
    """
    level = request.args.get('level', 'simple').lower()
    
    try:
        if level == 'comprehensive':
            # Comprehensive system health (original /system-health-comprehensive logic)
            from app.services.container_management_service import get_docker_manager
            docker_mgr = get_docker_manager()
            
            # Get all container details
            containers_info = []
            for model_slug in ['anthropic_claude-3.7-sonnet', 'openai_gpt-4', 'x-ai_grok-code-fast-1']:
                for app_num in [1, 2, 3]:
                    try:
                        status = docker_mgr.get_container_status(model_slug, app_num)
                        if status:
                            containers_info.append({
                                'model': model_slug,
                                'app': app_num,
                                'status': status.get('status'),
                                'health': status.get('health', 'unknown')
                            })
                    except Exception:
                        pass
            
            # Database health
            db_healthy = True
            try:
                db.session.query(db.func.count(ModelCapability.id)).scalar()
            except Exception:
                db_healthy = False
            
            # Analyzer services health (if available)
            analyzer_healthy = False
            try:
                import requests
                resp = requests.get('http://localhost:2001/health', timeout=2)
                analyzer_healthy = resp.status_code == 200
            except Exception:
                pass
            
            return api_success({
                'database': {
                    'status': 'healthy' if db_healthy else 'unhealthy',
                    'connected': db_healthy
                },
                'containers': {
                    'total': len(containers_info),
                    'running': sum(1 for c in containers_info if c['status'] == 'running'),
                    'details': containers_info
                },
                'analyzer_services': {
                    'status': 'healthy' if analyzer_healthy else 'unavailable',
                    'reachable': analyzer_healthy
                },
                'overall_status': 'healthy' if (db_healthy and analyzer_healthy) else 'degraded'
            })
        else:
            # Simple status (original /system-status logic)
            return api_success(build_system_status_payload())
            
    except Exception as e:
        current_app.logger.error(f"Error getting system status (level={level}): {e}")
        return api_error("Failed to retrieve system status", details={"reason": str(e)})


# =================================================================
# CONSOLIDATED FRAGMENTS ENDPOINT (replaces 6 endpoints)
# =================================================================

@dashboard_bp.route('/fragments/<fragment_name>')
def dashboard_fragment(fragment_name: str):
    """
    Unified HTMX fragments endpoint.
    
    Supported fragments:
      - summary-cards
      - system-status  
      - recent-activity
      - recent-applications
      - recent-analyses
      - stats
      - system-health
    """
    try:
        from app.utils.template_paths import render_template_compat as render_template
        
        if fragment_name == 'summary-cards':
            summary = build_summary_payload()
            return render_template('pages/index/partials/summary_cards.html', summary=summary)
            
        elif fragment_name == 'system-status':
            system_status = build_system_status_payload()
            return render_template('pages/index/partials/system_status.html', system_status=system_status)
            
        elif fragment_name == 'recent-activity':
            activity = get_recent_activity_entries()
            return render_template('pages/index/partials/recent_activity.html', activity=activity)
            
        elif fragment_name == 'recent-applications':
            applications = get_recent_applications()
            return render_template('pages/index/partials/recent_applications.html', applications=applications)
            
        elif fragment_name == 'recent-analyses':
            analyses = get_recent_analysis_summary()
            return render_template('pages/index/partials/recent_analyses.html', analyses=analyses)
            
        elif fragment_name == 'stats':
            stats = {
                'total_models': db.session.query(ModelCapability).count(),
                'total_apps': db.session.query(GeneratedApplication).count(),
                'security_tests': db.session.query(SecurityAnalysis).count(),
                'performance_tests': db.session.query(PerformanceTest).count()
            }
            # Try both possible template locations
            try:
                return render_template('pages/index/partials/stats_inner.html', stats=stats)
            except Exception:
                return render_template('partials/common/_sidebar_stats_inner.html', stats=stats)
                
        elif fragment_name == 'system-health':
            # System health fragment
            health_data = {
                'database': 'healthy',
                'containers': 'checking...',
                'analyzer': 'unknown'
            }
            
            return render_template('pages/index/partials/system_health.html', health=health_data)
            
        else:
            return api_error(f"Unknown fragment: {fragment_name}")
            
    except Exception as e:
        current_app.logger.error(f"Error rendering fragment '{fragment_name}': {e}")
        return api_error("Failed to render fragment", details={"reason": str(e)})


# =================================================================
# SYSTEM MANAGEMENT
# =================================================================

@dashboard_bp.route('/system-stats')
def dashboard_system_stats():
    """Detailed system statistics (kept as-is, used by monitoring)."""
    try:
        # Import monitoring service
        from app.services.system_monitoring_service import get_system_stats
        stats = get_system_stats()
        return api_success(stats)
    except ImportError:
        # Fallback if monitoring service doesn't exist
        return api_success({
            'cpu_percent': 0,
            'memory_percent': 0,
            'disk_usage': 0,
            'message': 'Monitoring service not available'
        })
    except Exception as e:
        current_app.logger.error(f"Error getting system stats: {e}")
        return api_error("Failed to retrieve system stats", details={"reason": str(e)})


@dashboard_bp.route('/tool-registry-summary')
def tool_registry_summary():
    """Tool registry summary (kept as-is)."""
    try:
        from app.services.tool_registry_service import get_tool_registry_service
        registry = get_tool_registry_service()
        
        tools = registry.get_all_tools()
        profiles = registry.get_all_profiles()
        
        # Group tools by category
        by_category = {}
        for tool in tools:
            category = tool.category or 'Other'
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(tool)
        
        return api_success({
            'total_tools': len(tools),
            'total_profiles': len(profiles),
            'categories': {cat: len(tools_list) for cat, tools_list in by_category.items()},
            'tools_by_category': {cat: [t.to_dict() for t in tools_list] for cat, tools_list in by_category.items()},
            'profiles': [p.to_dict() for p in profiles]
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting tool registry summary: {e}")
        return api_error("Failed to retrieve tool registry summary", details={"reason": str(e)})


@dashboard_bp.route('/analyzer-services')
def dashboard_analyzer_services():
    """Analyzer services status (kept as-is)."""
    try:
        import requests
        
        services = {
            'static-analyzer': {'url': 'http://localhost:2001/health', 'status': 'unknown'},
            'dynamic-analyzer': {'url': 'http://localhost:2002/health', 'status': 'unknown'},
            'performance-tester': {'url': 'http://localhost:2003/health', 'status': 'unknown'},
            'ai-analyzer': {'url': 'http://localhost:2004/health', 'status': 'unknown'},
        }
        
        for name, info in services.items():
            try:
                resp = requests.get(info['url'], timeout=2)
                info['status'] = 'healthy' if resp.status_code == 200 else 'unhealthy'
                info['response_code'] = str(resp.status_code)
            except requests.RequestException as e:
                info['status'] = 'unreachable'
                info['error'] = str(e)
        
        all_healthy = all(s['status'] == 'healthy' for s in services.values())
        
        return api_success({
            'services': services,
            'overall_status': 'healthy' if all_healthy else 'degraded',
            'healthy_count': sum(1 for s in services.values() if s['status'] == 'healthy'),
            'total_count': len(services)
        })
        
    except Exception as e:
        current_app.logger.error(f"Error checking analyzer services: {e}")
        return api_error("Failed to check analyzer services", details={"reason": str(e)})


@dashboard_bp.route('/recent_activity')
def recent_activity():
    """Recent activity feed (kept as-is)."""
    try:
        activity = get_recent_activity_entries(limit=20)
        return api_success({'activities': activity})
    except Exception as e:
        current_app.logger.error(f"Error getting recent activity: {e}")
        return api_error("Failed to retrieve recent activity", details={"reason": str(e)})


@dashboard_bp.route('/actions/<string:action_name>', methods=['POST'])
def execute_action(action_name: str):
    """Execute dashboard action (kept as-is)."""  
    try:
        if action_name == 'start_analyzer':
            # Start analyzer services
            import subprocess
            result = subprocess.run(
                ['python', 'analyzer/analyzer_manager.py', 'start'],
                capture_output=True,
                text=True
            )
            return api_success({'output': result.stdout, 'status': 'started'})
            
        elif action_name == 'stop_analyzer':
            # Stop analyzer services
            import subprocess
            result = subprocess.run(
                ['python', 'analyzer/analyzer_manager.py', 'stop'],
                capture_output=True,
                text=True
            )
            return api_success({'output': result.stdout, 'status': 'stopped'})
            
        else:
            return api_error(f"Unknown action: {action_name}")
            
    except Exception as e:
        current_app.logger.error(f"Error executing action '{action_name}': {e}")
        return api_error("Failed to execute action", details={"reason": str(e)})
@dashboard_bp.route('/chart-data')
def dashboard_chart_data():
    """Chart data for dashboard visualizations (kept as-is)."""
    try:
        # Generation trends over time
        days = 30
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        
        # Query apps by day
        daily_apps = db.session.query(
            db.func.date(GeneratedApplication.created_at).label('date'),
            db.func.count(GeneratedApplication.id).label('count')
        ).filter(
            GeneratedApplication.created_at >= start_date
        ).group_by(
            db.func.date(GeneratedApplication.created_at)
        ).all()
        
        # Format for charts
        chart_data = {
            'labels': [str(day[0]) for day in daily_apps],
            'datasets': [{
                'label': 'Applications Generated',
                'data': [day[1] for day in daily_apps]
            }]
        }
        
        return api_success(chart_data)
        
    except Exception as e:
        current_app.logger.error(f"Error getting chart data: {e}")
        return api_error("Failed to retrieve chart data", details={"reason": str(e)})


# =================================================================
# STATISTICS ACTIONS
# =================================================================

@dashboard_bp.route('/statistics/generation/by-models', methods=['POST'])
def api_generation_stats_by_models():
    """Get generation statistics filtered by models."""
    try:
        data = request.get_json() or {}
        model_slugs = data.get('model_slugs', [])
        stats = get_generation_statistics_by_models(model_slugs)
        return api_success(stats, message="Generation statistics by models fetched")
    except Exception as e:
        current_app.logger.error(f"Error getting generation stats by models: {e}")
        return api_error("Failed to retrieve generation statistics", details={"reason": str(e)})


@dashboard_bp.route('/statistics/wipe', methods=['POST'])
def api_wipe_statistics():
    """Wipe all statistics (dangerous operation)."""
    try:
        # This would require admin confirmation
        confirm = request.get_json() or {}
        if not confirm.get('confirmed'):
            return api_error("Operation requires confirmation")
        
        # Delete statistics records (be careful!)
        # This is a placeholder - implement actual wipe logic if needed
        return api_success({'wiped': False, 'message': 'Statistics wipe not implemented'})
        
    except Exception as e:
        current_app.logger.error(f"Error wiping statistics: {e}")
        return api_error("Failed to wipe statistics", details={"reason": str(e)})
