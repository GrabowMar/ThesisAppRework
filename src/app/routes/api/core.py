"""
Core API routes
===============

Basic health, status, and core application endpoints.
"""

from flask import Blueprint, jsonify, current_app
from datetime import datetime, timezone

from app.models import ModelCapability, GeneratedApplication, SecurityAnalysis, PerformanceTest, BatchAnalysis, ContainerizedTest
from app.constants import ContainerState
from app.services.data_initialization import data_init_service
from .common import api_success, api_error, get_database_health


core_bp = Blueprint('core_api', __name__)


@core_bp.route('/')
def api_overview():
    """API overview endpoint."""
    return api_success({
        'version': '1.0',
        'endpoints': {
            'models': '/api/models',
            'applications': '/api/applications',
            'statistics': '/api/statistics',
            'system': '/api/system',
            'analysis': '/api/analysis'
        }
    }, message='Thesis Research App API')


@core_bp.route('/health')
def api_health():
    """API health check endpoint."""
    db_healthy, db_error = get_database_health()
    
    if not db_healthy:
        return api_error(f"Database health check failed: {db_error}", status=503)
    
    return api_success({
        'status': 'healthy',
        'database': 'connected',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'version': '1.0'
    })


@core_bp.route('/stats')
def api_stats():
    """Basic API statistics endpoint."""
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
        return api_success(stats)
    except Exception as e:
        current_app.logger.error(f"Error getting API stats: {e}")
        return api_error("Failed to retrieve statistics", details={"reason": str(e)})


@core_bp.route('/data/initialize', methods=['POST'])
def api_initialize_data():
    """Initialize database with data from JSON files."""
    try:
        results = data_init_service.initialize_all_data()
        return jsonify(results)
    except Exception as e:
        current_app.logger.error(f"Error initializing data: {e}")
        return api_error("Failed to initialize data", details={"reason": str(e)})


@core_bp.route('/data/status')
def api_data_status():
    """Get data initialization status."""
    try:
        status = data_init_service.get_initialization_status()
        return jsonify(status)
    except Exception as e:
        current_app.logger.error(f"Error getting data status: {e}")
        return api_error("Failed to retrieve data status", details={"reason": str(e)})


@core_bp.route('/data/reload', methods=['POST'])
def api_reload_core_data():
    """Reload core JSON files."""
    try:
        results = data_init_service.reload_core_files()
        status_code = 200 if results.get('success', True) and not results.get('errors') else 207
        return jsonify(results), status_code
    except Exception as e:
        current_app.logger.error(f"Error reloading core data: {e}")
        return api_error("Failed to reload core data", details={"reason": str(e)})