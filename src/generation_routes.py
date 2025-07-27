"""
Generation Content Routes
========================

Flask routes for viewing and managing generated content from combined.py output.
"""

import logging
from flask import Blueprint, render_template, jsonify, request, abort, Response
from pathlib import Path
from generation_lookup_service import GenerationLookupService

# Create blueprint
generation_bp = Blueprint('generation', __name__, url_prefix='/generation')
logger = logging.getLogger(__name__)

# Initialize lookup service
try:
    lookup_service = GenerationLookupService()
except Exception as e:
    logger.error(f"Failed to initialize GenerationLookupService: {e}")
    lookup_service = None


@generation_bp.route('/')
def index():
    """Main generation content page"""
    try:
        if not lookup_service:
            return render_template('generation/error.html', 
                                 error="Generation lookup service not available")
        
        # Get list of generation runs
        runs = lookup_service.list_generation_runs()
        
        return render_template('generation/index.html', 
                             generation_runs=runs,
                             total_runs=len(runs))
    
    except Exception as e:
        logger.error(f"Error in generation index: {e}")
        return render_template('generation/error.html', 
                             error=f"Failed to load generation runs: {e}")


@generation_bp.route('/run/<timestamp>')
def view_run(timestamp: str):
    """View details of a specific generation run"""
    try:
        if not lookup_service:
            abort(503, "Generation lookup service not available")
        
        # Get generation details
        details = lookup_service.get_generation_details(timestamp)
        if not details:
            abort(404, "Generation run not found")
        
        # Get performance summary
        performance = lookup_service.get_model_performance_summary(timestamp)
        
        return render_template('generation/run_details.html',
                             timestamp=timestamp,
                             details=details,
                             performance=performance)
    
    except Exception as e:
        logger.error(f"Error viewing generation run {timestamp}: {e}")
        abort(500, f"Error loading generation run: {e}")


@generation_bp.route('/model/<timestamp>/<path:model>/<int:app_num>')
def view_model_app(timestamp: str, model: str, app_num: int):
    """View details of a specific model-app combination"""
    try:
        if not lookup_service:
            abort(503, "Generation lookup service not available")
        
        # Get model app details
        details = lookup_service.get_model_app_details(timestamp, model, app_num)
        if not details:
            abort(404, "Model-app combination not found")
        
        return render_template('generation/model_app_details.html',
                             timestamp=timestamp,
                             model=model,
                             app_num=app_num,
                             details=details)
    
    except Exception as e:
        logger.error(f"Error viewing model app {model}/{app_num}: {e}")
        abort(500, f"Error loading model app details: {e}")


@generation_bp.route('/file/<path:file_path>')
def view_file(file_path: str):
    """View content of a generated file"""
    try:
        if not lookup_service:
            abort(503, "Generation lookup service not available")
        
        # Get file content
        content = lookup_service.get_file_content(file_path)
        if content is None:
            abort(404, "File not found")
        
        # Determine if it's a markdown file
        is_markdown = file_path.endswith('.md')
        
        # Get file extension for syntax highlighting
        file_ext = Path(file_path).suffix.lower()
        
        return render_template('generation/file_viewer.html',
                             file_path=file_path,
                             content=content,
                             is_markdown=is_markdown,
                             file_extension=file_ext)
    
    except Exception as e:
        logger.error(f"Error viewing file {file_path}: {e}")
        abort(500, f"Error loading file: {e}")


@generation_bp.route('/api/runs')
def api_list_runs():
    """API endpoint to list generation runs"""
    try:
        if not lookup_service:
            return jsonify({"error": "Service not available"}), 503
        
        runs = lookup_service.list_generation_runs()
        return jsonify({
            "runs": [
                {
                    "timestamp": run.timestamp,
                    "filename": run.filename,
                    "models_count": run.models_count,
                    "apps_count": run.apps_count,
                    "total_successful": run.total_successful,
                    "total_failed": run.total_failed,
                    "generation_time": run.generation_time,
                    "fastest_model": run.fastest_model,
                    "slowest_model": run.slowest_model
                }
                for run in runs
            ]
        })
    
    except Exception as e:
        logger.error(f"Error in API list runs: {e}")
        return jsonify({"error": str(e)}), 500


@generation_bp.route('/api/run/<timestamp>')
def api_get_run(timestamp: str):
    """API endpoint to get generation run details"""
    try:
        if not lookup_service:
            return jsonify({"error": "Service not available"}), 503
        
        details = lookup_service.get_generation_details(timestamp)
        if not details:
            return jsonify({"error": "Run not found"}), 404
        
        return jsonify(details)
    
    except Exception as e:
        logger.error(f"Error in API get run: {e}")
        return jsonify({"error": str(e)}), 500


@generation_bp.route('/api/search')
def api_search():
    """API endpoint to search generations"""
    try:
        if not lookup_service:
            return jsonify({"error": "Service not available"}), 503
        
        # Get query parameters
        model_filter = request.args.get('model')
        app_filter = request.args.get('app', type=int)
        success_only = request.args.get('success_only', 'false').lower() == 'true'
        
        results = lookup_service.search_generations(
            model_filter=model_filter,
            app_filter=app_filter,
            success_only=success_only
        )
        
        return jsonify({
            "results": [
                {
                    "timestamp": timestamp,
                    "model": model,
                    "app_num": app_num,
                    "success": success
                }
                for timestamp, model, app_num, success in results
            ]
        })
    
    except Exception as e:
        logger.error(f"Error in API search: {e}")
        return jsonify({"error": str(e)}), 500


@generation_bp.route('/api/file/<path:file_path>')
def api_get_file(file_path: str):
    """API endpoint to get file content"""
    try:
        if not lookup_service:
            return jsonify({"error": "Service not available"}), 503
        
        content = lookup_service.get_file_content(file_path)
        if content is None:
            return jsonify({"error": "File not found"}), 404
        
        return Response(content, mimetype='text/plain')
    
    except Exception as e:
        logger.error(f"Error in API get file: {e}")
        return jsonify({"error": str(e)}), 500


@generation_bp.route('/api/stats')
def api_get_stats():
    """API endpoint to get overall generation statistics"""
    try:
        if not lookup_service:
            return jsonify({"error": "Service not available"}), 503
        
        runs = lookup_service.list_generation_runs()
        
        # Calculate overall statistics
        total_runs = len(runs)
        total_models = sum(run.models_count for run in runs)
        total_apps = sum(run.apps_count for run in runs)
        total_successful = sum(run.total_successful for run in runs)
        total_failed = sum(run.total_failed for run in runs)
        
        avg_generation_time = sum(run.generation_time for run in runs) / max(total_runs, 1)
        
        return jsonify({
            "total_runs": total_runs,
            "total_models": total_models,
            "total_apps": total_apps,
            "total_successful": total_successful,
            "total_failed": total_failed,
            "success_rate": total_successful / max(total_successful + total_failed, 1) * 100,
            "avg_generation_time": avg_generation_time,
            "latest_run": runs[0].timestamp if runs else None
        })
    
    except Exception as e:
        logger.error(f"Error in API get stats: {e}")
        return jsonify({"error": str(e)}), 500


# Error handlers for this blueprint
@generation_bp.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return render_template('generation/error.html', 
                         error="The requested resource was not found"), 404


@generation_bp.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return render_template('generation/error.html', 
                         error="An internal server error occurred"), 500


@generation_bp.errorhandler(503)
def service_unavailable(error):
    """Handle 503 errors"""
    return render_template('generation/error.html', 
                         error="Generation lookup service is currently unavailable"), 503
