"""
Main Routes
==========

Core application routes including dashboard and basic pages.
"""

import logging
import subprocess
from datetime import datetime, timezone

from flask import Blueprint, render_template, flash, current_app, jsonify, redirect, url_for

from ..models import (
    ModelCapability, GeneratedApplication,
    SecurityAnalysis, PerformanceTest,
    BatchAnalysis, ContainerizedTest
)
from ..extensions import db
from ..constants import JobStatus, ContainerState
from ..services.data_initialization import data_init_service

# Set up logger
logger = logging.getLogger(__name__)

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def dashboard():
    """Main dashboard page."""
    try:
        # Get overview statistics
        stats = {
            'total_models': ModelCapability.query.count(),
            'total_applications': GeneratedApplication.query.count(),
            'total_security_analyses': SecurityAnalysis.query.count(),
            'total_performance_tests': PerformanceTest.query.count(),
            'active_containers': ContainerizedTest.query.filter_by(
                status=ContainerState.RUNNING.value
            ).count()
        }
        
        # Get recent activities
        recent_apps = GeneratedApplication.query.order_by(
            GeneratedApplication.created_at.desc()
        ).limit(5).all()
        
        recent_analyses = SecurityAnalysis.query.order_by(
            SecurityAnalysis.created_at.desc()
        ).limit(5).all()
        
        # Get running batch jobs
        running_batches = BatchAnalysis.query.filter_by(
            status=JobStatus.RUNNING
        ).all()
        
        # Use new dashboard template structure
        return render_template(
            'views/dashboard/index.html',
            stats=stats,
            recent_apps=recent_apps,
            recent_analyses=recent_analyses,
            running_batches=running_batches
        )
    except Exception as e:
        logger.error(f"Error loading dashboard: {e}")
        flash('Error loading dashboard', 'error')
        # Use the proper error template structure
        return render_template(
            'partials/common/error.html',
            error=str(e),
            page_title='Dashboard Error'
        ), 500


@main_bp.route('/about')
def about():
    """About page with project information."""
    return render_template('views/about.html')


# =================================================================
# SPA PARTIAL ROUTES
# These routes return inner content to be injected into the SPA shell
# at layouts/single-page.html#spa-content
# =================================================================

@main_bp.route('/spa/dashboard')
def spa_dashboard():
    """SPA: Dashboard inner content."""
    try:
        # Reuse the main dashboard view content
        return render_template('spa/dashboard_content.html')
    except Exception as e:
        logger.error(f"Error loading SPA dashboard: {e}")
        return render_template('partials/common/error.html', error=str(e)), 500


@main_bp.route('/spa/analysis')
def spa_analysis():
    """SPA: Analysis hub inner content."""
    try:
        return render_template('spa/analysis_content.html')
    except Exception as e:
        logger.error(f"Error loading SPA analysis: {e}")
        return render_template('partials/common/error.html', error=str(e)), 500


@main_bp.route('/spa/models')
def spa_models():
    """SPA: Models overview inner content."""
    try:
        return render_template('spa/models_content.html')
    except Exception as e:
        logger.error(f"Error loading SPA models: {e}")
        return render_template('partials/common/error.html', error=str(e)), 500


@main_bp.route('/spa/applications')
def spa_applications():
    """SPA: Applications overview inner content."""
    try:
        return render_template('spa/applications_content.html')
    except Exception as e:
        logger.error(f"Error loading SPA applications: {e}")
        return render_template('partials/common/error.html', error=str(e)), 500


@main_bp.route('/system-status')
def system_status():
    """System status / runtime health page (wrapper template)."""
    try:
        # Light-weight stats for status panel (reuse subset of dashboard)
        stats = {
            'models': ModelCapability.query.count(),
            'applications': GeneratedApplication.query.count(),
            'security_scans': SecurityAnalysis.query.count(),
            'performance_tests': PerformanceTest.query.count()
        }
        return render_template('views/system/status.html', stats=stats)
    except Exception as e:
        logger.error(f"Error loading system status: {e}")
        flash('Error loading system status', 'error')
        return render_template(
            'partials/common/error.html',
            error=str(e),
            page_title='System Status Error'
        ), 500


@main_bp.route('/test-platform')
def testing():
    """Legacy testing platform route -> redirect to Analysis Hub."""
    try:
        flash('Testing has moved to Analysis Hub.', 'info')
        return redirect(url_for('analysis.analysis_hub'))
    except Exception as e:
        logger.error(f"Error redirecting testing page: {e}")
        flash('Error loading testing page', 'error')
        return render_template(
            'partials/common/error.html',
            error=str(e),
            page_title='Testing Page Error'
        ), 500


@main_bp.route('/models_overview')
def models_overview():
    """Redirect to models overview page."""
    from flask import redirect, url_for
    return redirect(url_for('models.models_overview'))


@main_bp.route('/api/stats')
def api_stats():
    """API endpoint for dashboard statistics."""
    try:
        stats = {
            'models': ModelCapability.query.count(),
            'applications': GeneratedApplication.query.count(),
            'security_analyses': SecurityAnalysis.query.count(),
            'performance_tests': PerformanceTest.query.count(),
            'batch_jobs': BatchAnalysis.query.count(),
            'active_containers': ContainerizedTest.query.filter_by(
                status=ContainerState.RUNNING.value
            ).count()
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting API stats: {e}")
        return {'error': str(e)}, 500


@main_bp.route('/api/data/initialize', methods=['POST'])
def api_initialize_data():
    """API endpoint to initialize database with data from JSON files."""
    try:
        results = data_init_service.initialize_all_data()
        return jsonify(results)
    except Exception as e:
        logger.error(f"Error initializing data: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/api/data/status')
def api_data_status():
    """API endpoint to get data initialization status."""
    try:
        status = data_init_service.get_initialization_status()
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error getting data status: {e}")
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/data/reload', methods=['POST'])
def api_reload_core_data():
    """API endpoint to reload core JSON files (capabilities, summary, ports)."""
    try:
        results = data_init_service.reload_core_files()
        status_code = 200 if results.get('success', True) and not results.get('errors') else 207
        return jsonify(results), status_code
    except Exception as e:
        logger.error(f"Error reloading core data: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/api/system/health')
def api_system_health():
    """API endpoint for system health status."""
    try:
        from ..services.service_locator import ServiceLocator

        # Check Docker status
        docker_manager = ServiceLocator.get_docker_manager()
        docker_status = {
            'available': False,
            'containers_running': 0,
            'error': None,
        }

        try:
            client = getattr(docker_manager, 'client', None)
            if client:
                containers = client.containers.list()
                docker_status['available'] = True
                docker_status['containers_running'] = len(containers)
        except Exception as e:
            docker_status['error'] = str(e)

        # Check analyzer services (placeholder values)
        analyzer_status = {
            'security': {'status': 'unknown', 'port': 2001},
            'performance': {'status': 'unknown', 'port': 2002},
            'dynamic': {'status': 'unknown', 'port': 2003},
            'ai': {'status': 'unknown', 'port': 2004},
        }

        # Check database connection
        db_status = {'available': True, 'error': None}
        try:
            from sqlalchemy import text
            db.session.execute(text('SELECT 1'))
        except Exception as e:
            db_status['available'] = False
            db_status['error'] = str(e)

        return jsonify({
            'docker': docker_status,
            'analyzers': analyzer_status,
            'database': db_status,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/dashboard/stats')
def api_dashboard_stats():
    """Enhanced API endpoint for dashboard statistics."""
    try:
        # Basic counts
        models_count = ModelCapability.query.count()
        apps_count = GeneratedApplication.query.count()
        security_count = SecurityAnalysis.query.count()
        performance_count = PerformanceTest.query.count()
        
        # Provider breakdown
        from sqlalchemy import func
        provider_stats = db.session.query(
            ModelCapability.provider,
            func.count(ModelCapability.id).label('count')
        ).group_by(ModelCapability.provider).all()
        
        # Application framework breakdown
        framework_stats = db.session.query(
            GeneratedApplication.backend_framework,
            func.count(GeneratedApplication.id).label('count')
        ).group_by(GeneratedApplication.backend_framework).all()
        
        # Recent activity
        recent_models = ModelCapability.query.order_by(
            ModelCapability.created_at.desc()
        ).limit(5).all()
        
        recent_apps = GeneratedApplication.query.order_by(
            GeneratedApplication.created_at.desc()
        ).limit(5).all()
        
        return jsonify({
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
        logger.error(f"Error getting dashboard stats: {e}")
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/analyzer/start', methods=['POST'])
def start_analyzer_services():
    """Start analyzer services via Docker"""
    try:
        # Simple docker check and analyzer service startup
        result = subprocess.run(['docker', 'ps'], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            # Docker is available, try to start analyzer services
            # This is a simplified implementation
            return jsonify({
                'success': True,
                'message': 'Docker is available. Analyzer services can be started via the analyzer_manager.py script.',
                'note': 'Please run: cd analyzer && python analyzer_manager.py start'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Docker not available'
            }), 500
                
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'error': 'Docker command timed out'
        }), 500
    except FileNotFoundError:
        return jsonify({
            'success': False,
            'error': 'Docker not found. Please install Docker.'
        }), 500
    except Exception as e:
        current_app.logger.error(f"Error starting analyzer services: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
