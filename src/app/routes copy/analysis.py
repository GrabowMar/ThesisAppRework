"""
New Analysis API Routes
======================

Modern API endpoints for the reimplemented analysis system.
Handles tasks, batches, configurations, and results.
"""

import logging
import io  # for in-memory result exports (bytes IO)
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, abort, send_file, render_template
from flask_cors import cross_origin

from ..extensions import db
from ..models import (
    AnalysisTask, BatchAnalysis, AnalyzerConfiguration, AnalysisResult
)
from ..constants import AnalysisStatus, AnalysisType, JobPriority as Priority, JobStatus as BatchStatus
from ..services.task_service import (
    task_service, batch_service, queue_service, AnalysisTaskService, BatchAnalysisService
)
from ..services.analyzer_service import (
    analyzer_config_service, analyzer_manager_service
)
from ..services.batch_service import (
    batch_template_service, batch_validation_service, batch_execution_service
)
from ..services.results_service import (
    results_query_service, results_aggregation_service, results_export_service,
    FilterCriteria, ResultFormat
)


logger = logging.getLogger(__name__)

# Create blueprint
new_analysis_api = Blueprint('analysis', __name__, url_prefix='/analysis')


# Error handlers
@new_analysis_api.errorhandler(400)
def bad_request(error):
    return jsonify({'error': 'Bad request', 'message': str(error)}), 400


@new_analysis_api.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found', 'message': str(error)}), 404


@new_analysis_api.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error', 'message': str(error)}), 500


# ============================================================================
# Dashboard and Overview Endpoints
# ============================================================================

@new_analysis_api.route('/dashboard')
def analysis_dashboard():
    """Render the analysis dashboard page.

    Template: `pages/analysis/dashboard_main.html`
    Layout:   `layouts/dashboard.html`
    Context Keys Provided:
        dashboard_data (dict): summary metrics & recent activity. Keys:
            active_tasks (int)
            completed_tasks (int)
            failed_tasks (int)
            total_analyses (int)
            recent_activity (list[dict])
            system_health (dict)
            queue_status (dict)
    HTMX: Standard GET (no HX-specific branch yet). Future: could return fragment
          when `HX-Request` header present by rendering only the dashboard_content
          block or a dedicated partial.
    Accessibility: Landmark & aria-live regions defined in template.
    """
    # Provide basic dashboard data to avoid template errors
    dashboard_data = {
        'active_tasks': 0,
        'completed_tasks': 0,
        'failed_tasks': 0,
        'total_analyses': 0,
        'recent_activity': [],
        'system_health': {'status': 'healthy'},
        'queue_status': {'pending': 0, 'running': 0}
    }
    
    try:
        # Try to get real data from services if available
        from ..models import AnalysisTask
        active_tasks = AnalysisTask.query.filter_by(status='running').count()
        completed_tasks = AnalysisTask.query.filter_by(status='completed').count()
        failed_tasks = AnalysisTask.query.filter_by(status='failed').count()
        total_analyses = AnalysisTask.query.count()
        
        dashboard_data.update({
            'active_tasks': active_tasks,
            'completed_tasks': completed_tasks,
            'failed_tasks': failed_tasks,
            'total_analyses': total_analyses
        })
    except Exception as e:
        logger.warning(f"Could not load dashboard data: {e}")
    
    return render_template('pages/analysis/dashboard_main.html', dashboard_data=dashboard_data)

# Temporary compatibility alias (legacy templates may still reference 'analysis.dashboard')
@new_analysis_api.route('/legacy-dashboard')
def legacy_dashboard_alias():  # pragma: no cover - thin redirect
    """Redirect legacy dashboard path to canonical endpoint.

    This helps avoid 500 errors while residual references are cleaned up.
    Remove after all templates/tests use analysis.analysis_dashboard.
    """
    from flask import redirect, url_for
    return redirect(url_for('analysis.analysis_dashboard'), code=302)

@new_analysis_api.route('/list')
def analysis_list():
    """Render analysis hub/list page.

    TODO: Implement template `pages/analysis/hub_main.html` (currently placeholder or
    pending migration). Once created, supply context containing analysis task
    filters & pagination data via service layer.
    """
    return render_template('pages/analysis/hub_main.html')

@new_analysis_api.route('/')
def analysis_index():
    """Alias of /analysis/list during migration.

    Consider redirecting (302) to canonical path after all links updated.
    """
    return render_template('pages/analysis/hub_main.html')

@new_analysis_api.route('/dashboard-data')
def get_dashboard_data():
    """Get comprehensive dashboard data."""
    try:
        dashboard_data = results_aggregation_service.get_dashboard_summary()
        queue_status = queue_service.get_queue_status()
        system_overview = analyzer_manager_service.get_system_overview()
        
        return jsonify({
            'dashboard_data': dashboard_data,
            'queue_status': queue_status,
            'system_overview': system_overview,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        logger.error(f"Failed to get dashboard data: {e}")
        return jsonify({'error': str(e)}), 500


@new_analysis_api.route('/chart-data')
def get_chart_data():
    """Get chart data for dashboard."""
    try:
        period = request.args.get('period', 'day')
        days = {'day': 1, 'week': 7, 'month': 30}.get(period, 7)
        
        trend_data = results_aggregation_service.get_trend_analysis(
            metric='task_count',
            period='daily',
            days=days
        )
        
        return jsonify(trend_data)
    except Exception as e:
        logger.error(f"Failed to get chart data: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Task Management Endpoints
# ============================================================================

@new_analysis_api.route('/tasks', methods=['GET'])
def list_tasks():
    """List analysis tasks with filtering and pagination."""
    try:
        # Parse query parameters
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        status = request.args.get('status')
        analysis_type = request.args.get('analysis_type')
        model_slug = request.args.get('model_slug')
        batch_id = request.args.get('batch_id')
    # NOTE: future filter parameter (search) captured but unused currently.
    # search = request.args.get('search')  # reserved for future filtering
        
        # Build filters
        filters = FilterCriteria()
        if status:
            filters.status = [status]
        if analysis_type:
            filters.analysis_type = [analysis_type]
        if model_slug:
            filters.model_slug = [model_slug]
        if batch_id:
            filters.batch_id = int(batch_id)
        
        # Get tasks
        tasks, total = results_query_service.list_results(
            filters=filters,
            limit=size,
            offset=(page - 1) * size
        )
        
        # Get statistics
        stats = AnalysisTaskService.get_task_statistics()
        
        return jsonify({
            'tasks': tasks,
            'pagination': {
                'current_page': page,
                'page_size': size,
                'total_items': total,
                'total_pages': (total + size - 1) // size
            },
            'stats': stats
        })
    except Exception as e:
        logger.error(f"Failed to list tasks: {e}")
        return jsonify({'error': str(e)}), 500


@new_analysis_api.route('/tasks', methods=['POST'])
def create_task():
    """Create a new analysis task."""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['model_slug', 'app_number', 'analysis_type']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return jsonify({'error': f'Missing required fields: {missing_fields}'}), 400
        
        # Create task
        task = AnalysisTaskService.create_task(
            model_slug=data['model_slug'],
            app_number=data['app_number'],
            analysis_type=data['analysis_type'],
            config_id=data.get('config_id'),
            priority=data.get('priority', 'normal'),
            custom_options=data.get('custom_options')
        )
        
        return jsonify(task.to_dict()), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to create task: {e}")
        return jsonify({'error': str(e)}), 500


@new_analysis_api.route('/tasks/<task_id>')
def get_task(task_id):
    """Get detailed task information."""
    try:
        task_data = results_query_service.get_task_results(task_id, include_detailed_results=True)
        if not task_data:
            abort(404)
        
        return jsonify(task_data)
    except Exception as e:
        logger.error(f"Failed to get task {task_id}: {e}")
        return jsonify({'error': str(e)}), 500


@new_analysis_api.route('/tasks/<task_id>/cancel', methods=['POST'])
def cancel_task(task_id):
    """Cancel a running task."""
    try:
        task = AnalysisTaskService.cancel_task(task_id)
        if not task:
            abort(404)
        
        return jsonify({'message': 'Task cancelled successfully', 'task': task.to_dict()})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to cancel task {task_id}: {e}")
        return jsonify({'error': str(e)}), 500


@new_analysis_api.route('/tasks/<task_id>/results/download')
def download_task_results(task_id):
    """Download task results in specified format."""
    try:
        format_type = request.args.get('format', 'json')
        
        if format_type not in ['json', 'csv', 'html']:
            return jsonify({'error': 'Invalid format'}), 400
        
        content, filename, mimetype = results_export_service.export_task_results(
            task_id=task_id,
            format=ResultFormat(format_type),
            include_detailed=True
        )
        
        return send_file(
            io.BytesIO(content),
            as_attachment=True,
            download_name=filename,
            mimetype=mimetype
        )
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to download results for task {task_id}: {e}")
        return jsonify({'error': str(e)}), 500


@new_analysis_api.route('/tasks/export')
def export_tasks():
    """Export multiple tasks."""
    try:
        format_type = request.args.get('format', 'json')
        task_ids = request.args.getlist('task_ids')
        
        if not task_ids:
            return jsonify({'error': 'No task IDs provided'}), 400
        
        content, filename, mimetype = results_export_service.export_multiple_results(
            task_ids=task_ids,
            format=ResultFormat(format_type)
        )
        
        return send_file(
            io.BytesIO(content),
            as_attachment=True,
            download_name=filename,
            mimetype=mimetype
        )
    except Exception as e:
        logger.error(f"Failed to export tasks: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Batch Analysis Endpoints
# ============================================================================

@new_analysis_api.route('/batches', methods=['GET'])
def list_batches():
    """List batch analyses with filtering and pagination."""
    try:
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        status = request.args.get('status')
        
        batches = BatchAnalysisService.list_batches(
            status=status,
            limit=size,
            offset=(page - 1) * size
        )
        
        stats = BatchAnalysisService.get_batch_statistics()
        
        total = BatchAnalysis.query.count()
        
        return jsonify({
            'batches': [batch.to_dict() for batch in batches],
            'pagination': {
                'current_page': page,
                'page_size': size,
                'total_items': total,
                'total_pages': (total + size - 1) // size
            },
            'stats': stats
        })
    except Exception as e:
        logger.error(f"Failed to list batches: {e}")
        return jsonify({'error': str(e)}), 500


@new_analysis_api.route('/batches', methods=['POST'])
def create_batch():
    """Create a new batch analysis."""
    try:
        data = request.get_json()
        
        # Validate batch configuration
        is_valid, errors = batch_validation_service.validate_batch_config(
            name=data.get('name', ''),
            analysis_types=data.get('analysis_types', []),
            target_models=data.get('target_models', []),
            target_apps=data.get('target_apps', []),
            config=data.get('config', {})
        )
        
        if not is_valid:
            return jsonify({'error': 'Validation failed', 'details': errors}), 400
        
        # Create batch
        batch = BatchAnalysisService.create_batch(
            name=data['name'],
            description=data.get('description', ''),
            analysis_types=data['analysis_types'],
            target_models=data['target_models'],
            target_apps=data['target_apps'],
            priority=data.get('priority', 'normal'),
            config=data.get('config', {})
        )
        
        # Optionally start immediately
        if data.get('start_immediately', False):
            batch_execution_service.execute_batch(batch.batch_id, async_execution=True)
        
        return jsonify(batch.to_dict()), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to create batch: {e}")
        return jsonify({'error': str(e)}), 500


@new_analysis_api.route('/batches/<batch_id>')
def get_batch(batch_id):
    """Get detailed batch information."""
    try:
        batch_data = results_query_service.get_batch_results(batch_id, include_task_details=True)
        if not batch_data:
            abort(404)
        
        return jsonify(batch_data)
    except Exception as e:
        logger.error(f"Failed to get batch {batch_id}: {e}")
        return jsonify({'error': str(e)}), 500


@new_analysis_api.route('/batches/<batch_id>/start', methods=['POST'])
def start_batch(batch_id):
    """Start a batch analysis."""
    try:
        result = batch_execution_service.execute_batch(batch_id, async_execution=True)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to start batch {batch_id}: {e}")
        return jsonify({'error': str(e)}), 500


@new_analysis_api.route('/batches/<batch_id>/cancel', methods=['POST'])
def cancel_batch(batch_id):
    """Cancel a running batch."""
    try:
        result = batch_execution_service.cancel_batch_execution(batch_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to cancel batch {batch_id}: {e}")
        return jsonify({'error': str(e)}), 500


@new_analysis_api.route('/batch-templates')
def get_batch_templates():
    """Get available batch analysis templates."""
    try:
        templates = batch_template_service.get_default_templates()
        return jsonify([{
            'name': t.name,
            'description': t.description,
            'analysis_types': t.analysis_types,
            'default_config': t.default_config,
            'estimated_time_per_app': t.estimated_time_per_app
        } for t in templates])
    except Exception as e:
        logger.error(f"Failed to get batch templates: {e}")
        return jsonify({'error': str(e)}), 500


@new_analysis_api.route('/batch-estimate', methods=['POST'])
def estimate_batch():
    """Estimate batch execution time and resources."""
    try:
        data = request.get_json()
        
        estimate = batch_validation_service.estimate_batch_execution(
            analysis_types=data.get('analysis_types', []),
            target_models=data.get('target_models', []),
            target_apps=data.get('target_apps', []),
            config=data.get('config', {})
        )
        
        return jsonify(estimate)
    except Exception as e:
        logger.error(f"Failed to estimate batch: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Configuration Management Endpoints
# ============================================================================

@new_analysis_api.route('/configurations')
def list_configurations():
    """List analyzer configurations."""
    try:
        analyzer_type = request.args.get('analyzer_type')
        active_only = request.args.get('active_only', 'true').lower() == 'true'
        
        configs = analyzer_config_service.list_configurations(
            analyzer_type=analyzer_type,
            active_only=active_only
        )
        
        return jsonify([config.to_dict() for config in configs])
    except Exception as e:
        logger.error(f"Failed to list configurations: {e}")
        return jsonify({'error': str(e)}), 500


@new_analysis_api.route('/configurations', methods=['POST'])
def create_configuration():
    """Create a new analyzer configuration."""
    try:
        data = request.get_json()
        
        config = analyzer_config_service.create_configuration(
            name=data['name'],
            analyzer_type=data['analyzer_type'],
            description=data.get('description'),
            tools_config=data.get('tools_config'),
            execution_config=data.get('execution_config'),
            output_config=data.get('output_config'),
            is_default=data.get('is_default', False)
        )
        
        return jsonify(config.to_dict()), 201
    except Exception as e:
        logger.error(f"Failed to create configuration: {e}")
        return jsonify({'error': str(e)}), 500


@new_analysis_api.route('/configurations/<config_id>')
def get_configuration(config_id):
    """Get analyzer configuration details."""
    try:
        config = analyzer_config_service.get_configuration(config_id)
        if not config:
            abort(404)
        
        return jsonify(config.to_dict())
    except Exception as e:
        logger.error(f"Failed to get configuration {config_id}: {e}")
        return jsonify({'error': str(e)}), 500


@new_analysis_api.route('/configurations/<config_id>', methods=['PUT'])
def update_configuration(config_id):
    """Update analyzer configuration."""
    try:
        data = request.get_json()
        
        config = analyzer_config_service.update_configuration(config_id, **data)
        if not config:
            abort(404)
        
        return jsonify(config.to_dict())
    except Exception as e:
        logger.error(f"Failed to update configuration {config_id}: {e}")
        return jsonify({'error': str(e)}), 500


@new_analysis_api.route('/configurations/<config_id>', methods=['DELETE'])
def delete_configuration(config_id):
    """Delete analyzer configuration."""
    try:
        success = analyzer_config_service.delete_configuration(config_id)
        if not success:
            abort(404)
        
        return jsonify({'message': 'Configuration deleted successfully'})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to delete configuration {config_id}: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# System Status and Health Endpoints
# ============================================================================

@new_analysis_api.route('/system-status')
def get_system_status():
    """Get system status and health information."""
    try:
        system_overview = analyzer_manager_service.get_system_overview()
        queue_status = queue_service.get_queue_status()
        
        return jsonify({
            'system_overview': system_overview,
            'queue_status': queue_status,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        logger.error(f"Failed to get system status: {e}")
        return jsonify({'error': str(e)}), 500


@new_analysis_api.route('/queue-status')
def get_queue_status():
    """Get current queue status."""
    try:
        status = queue_service.get_queue_status()
        return jsonify(status)
    except Exception as e:
        logger.error(f"Failed to get queue status: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Results and Analytics Endpoints
# ============================================================================

@new_analysis_api.route('/results/search')
def search_results():
    """Search analysis results by content."""
    try:
        search_term = request.args.get('q', '')
        limit = int(request.args.get('limit', 50))
        
        if not search_term:
            return jsonify({'error': 'Search term is required'}), 400
        
        results = results_query_service.search_results(
            search_term=search_term,
            limit=limit
        )
        
        return jsonify({'results': results, 'search_term': search_term})
    except Exception as e:
        logger.error(f"Failed to search results: {e}")
        return jsonify({'error': str(e)}), 500


@new_analysis_api.route('/analytics/trends')
def get_trends():
    """Get trend analysis data."""
    try:
        metric = request.args.get('metric', 'task_count')
        period = request.args.get('period', 'daily')
        days = int(request.args.get('days', 30))
        
        trends = results_aggregation_service.get_trend_analysis(
            metric=metric,
            period=period,
            days=days
        )
        
        return jsonify(trends)
    except Exception as e:
        logger.error(f"Failed to get trends: {e}")
        return jsonify({'error': str(e)}), 500


@new_analysis_api.route('/analytics/comparison')
def get_comparison():
    """Get comparative analysis data."""
    try:
        comparison_type = request.args.get('type', 'model_performance')
        limit = int(request.args.get('limit', 10))
        
        comparison = results_aggregation_service.get_comparison_analysis(
            comparison_type=comparison_type,
            limit=limit
        )
        
        return jsonify(comparison)
    except Exception as e:
        logger.error(f"Failed to get comparison: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Utility Endpoints
# ============================================================================

@new_analysis_api.route('/available-models')
def get_available_models():
    """Get list of available models for analysis."""
    try:
        # This would integrate with the actual model discovery system
        # For now, return mock data
        models = [
            'anthropic_claude-3.7-sonnet',
            'openai_gpt-4',
            'google_gemini-pro',
            'meta_llama-2-70b',
            'mistral_7b-instruct'
        ]
        return jsonify(models)
    except Exception as e:
        logger.error(f"Failed to get available models: {e}")
        return jsonify({'error': str(e)}), 500


@new_analysis_api.route('/filter-options')
def get_filter_options():
    """Get available filter options for UI components."""
    try:
        # Get unique values from database
        models = db.session.query(AnalysisTask.model_slug).distinct().all()
        analysis_types = db.session.query(AnalysisTask.analysis_type).distinct().all()
        
        return jsonify({
            'models': [model[0] for model in models],
            'analysis_types': [at[0] for at in analysis_types],
            'statuses': ['pending', 'queued', 'running', 'completed', 'failed', 'cancelled'],
            'priorities': ['low', 'normal', 'high', 'critical']
        })
    except Exception as e:
        logger.error(f"Failed to get filter options: {e}")
        return jsonify({'error': str(e)}), 500


@new_analysis_api.route('/health')
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'version': '2.0.0'
    })


# ============================================================================
# WebSocket Support (if needed)
# ============================================================================

@new_analysis_api.route('/ws-events')
@cross_origin()
def get_ws_events():
    """Get recent WebSocket events for real-time updates."""
    try:
        # This would integrate with the WebSocket event system
        # For now, return recent activity
        recent_tasks = AnalysisTaskService.get_recent_tasks(limit=10)
        recent_batches = BatchAnalysisService.list_batches(limit=5)
        
        events = []
        
        # Add task events
        for task in recent_tasks:
            events.append({
                'type': 'task_update',
                'timestamp': task.created_at.isoformat() if task.created_at else None,
                'data': task.to_dict()
            })
        
        # Add batch events
        for batch in recent_batches:
            events.append({
                'type': 'batch_update',
                'timestamp': batch.created_at.isoformat() if batch.created_at else None,
                'data': batch.to_dict()
            })
        
        # Sort by timestamp
        events.sort(key=lambda x: x['timestamp'] or '', reverse=True)
        
        return jsonify({'events': events[:20]})  # Return latest 20 events
    except Exception as e:
        logger.error(f"Failed to get WS events: {e}")
        return jsonify({'error': str(e)}), 500



