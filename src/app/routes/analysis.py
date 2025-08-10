"""
Analysis Routes
==============

Routes for managing analysis operations and results.
"""

import logging

from flask import Blueprint, request, jsonify, render_template

from ..services.task_manager import TaskManager
from ..models import GeneratedApplication

# Set up logger
logger = logging.getLogger(__name__)

analysis_bp = Blueprint('analysis', __name__)

# Initialize services
task_manager = TaskManager()


@analysis_bp.route('/security/start', methods=['POST'])
def start_security_analysis():
    """Start security analysis for an application."""
    try:
        app_id = request.json.get('app_id')
        if not app_id:
            return jsonify({'error': 'Application ID required'}), 400
        
        app = GeneratedApplication.query.get_or_404(app_id)
        
        # Configuration options
        config = {
            'bandit_enabled': request.json.get('bandit_enabled', True),
            'safety_enabled': request.json.get('safety_enabled', True),
            'pylint_enabled': request.json.get('pylint_enabled', True),
            'eslint_enabled': request.json.get('eslint_enabled', True),
            'npm_audit_enabled': request.json.get('npm_audit_enabled', True),
            'snyk_enabled': request.json.get('snyk_enabled', False),
        }
        
        # Start analysis task
        task_result = task_manager.start_security_analysis(
            app.model_slug,
            app.app_number,
            config
        )
        
        return jsonify({
            'success': True,
            'task_id': task_result.id,
            'message': 'Security analysis started'
        })
        
    except Exception as e:
        logger.error(f"Error starting security analysis: {e}")
        return jsonify({'error': str(e)}), 500


@analysis_bp.route('/performance/start', methods=['POST'])
def start_performance_test():
    """Start performance test for an application."""
    try:
        app_id = request.json.get('app_id')
        if not app_id:
            return jsonify({'error': 'Application ID required'}), 400
        
        app = GeneratedApplication.query.get_or_404(app_id)
        
        # Test configuration
        config = {
            'test_type': request.json.get('test_type', 'load'),
            'users': request.json.get('users', 10),
            'spawn_rate': request.json.get('spawn_rate', 1.0),
            'duration': request.json.get('duration', 60)
        }
        
        # Start performance test
        task_result = task_manager.start_performance_test(
            app.model_slug,
            app.app_number,
            config
        )
        
        return jsonify({
            'success': True,
            'task_id': task_result.id,
            'message': 'Performance test started'
        })
        
    except Exception as e:
        logger.error(f"Error starting performance test: {e}")
        return jsonify({'error': str(e)}), 500


@analysis_bp.route('/batch/start', methods=['POST'])
def start_batch_analysis():
    """Start batch analysis job."""
    try:
        config = {
            'analysis_types': request.json.get('analysis_types', []),
            'model_filter': request.json.get('model_filter', []),
            'app_filter': request.json.get('app_filter', []),
            'priority': request.json.get('priority', 'normal')
        }
        
        if not config['analysis_types']:
            return jsonify({'error': 'At least one analysis type required'}), 400
        
        # Start batch analysis
        task_result = task_manager.start_batch_analysis(config)
        
        return jsonify({
            'success': True,
            'task_id': task_result.id,
            'message': 'Batch analysis started'
        })
        
    except Exception as e:
        logger.error(f"Error starting batch analysis: {e}")
        return jsonify({'error': str(e)}), 500


@analysis_bp.route('/security_test_form')
def security_test_form():
    """HTMX endpoint for security test form."""
    from ..models import ModelCapability
    
    try:
        models = ModelCapability.query.all()
        return render_template('partials/security_test_form.html', models=models)
    except Exception as e:
        logger.error(f"Error loading security test form: {e}")
        return f'<div class="alert alert-danger">Error loading security test form: {str(e)}</div>'


@analysis_bp.route('/performance_test_form')
def performance_test_form():
    """HTMX endpoint for performance test form."""
    return render_template('partials/performance_test_form.html')


@analysis_bp.route('/security/run', methods=['POST'])
def run_security_test():
    """Run security test (alias for start_security_analysis)."""
    return start_security_analysis()


@analysis_bp.route('/performance/run', methods=['POST'])
def run_performance_test():
    """Run performance test (alias for start_performance_test)."""
    return start_performance_test()


@analysis_bp.route('/get_model_apps')
def get_model_apps():
    """HTMX endpoint to get applications for a model."""
    from ..models import GeneratedApplication
    from flask import request
    
    model_slug = request.args.get('model_slug')
    if not model_slug:
        return '<select class="form-select" name="app_number" disabled><option value="">Choose a model first...</option></select>'
    
    try:
        apps = GeneratedApplication.query.filter_by(model_slug=model_slug).all()
        
        # Generate select options
        options = ['<select class="form-select" name="app_number" required>']
        options.append('<option value="">Choose an application...</option>')
        
        for app in apps:
            options.append(f'<option value="{app.app_number}">App {app.app_number}</option>')
        
        options.append('</select>')
        
        return ''.join(options)
    except Exception as e:
        logger.error(f"Error getting apps for model {model_slug}: {e}")
        return '<select class="form-select" name="app_number" disabled><option value="">Error loading apps</option></select>'
