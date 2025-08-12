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

analysis_bp = Blueprint('analysis', __name__, url_prefix='/analysis')

# Initialize services
task_manager = TaskManager()


@analysis_bp.route('/')
def analysis_hub():
    """Analysis hub main page."""
    try:
        from ..models import SecurityAnalysis, PerformanceTest, ZAPAnalysis, OpenRouterAnalysis
        from ..extensions import db
        from sqlalchemy import desc, func
        
        # Get analysis statistics
        stats = {
            'total_security': SecurityAnalysis.query.count(),
            'total_performance': PerformanceTest.query.count(),
            'total_zap': ZAPAnalysis.query.count(),
            'total_ai': OpenRouterAnalysis.query.count()
        }
        
        # Get recent analyses
        recent_security = SecurityAnalysis.query.order_by(
            desc(SecurityAnalysis.created_at)
        ).limit(5).all()
        
        recent_performance = PerformanceTest.query.order_by(
            desc(PerformanceTest.created_at)
        ).limit(5).all()
        
        # Get analysis trends
        from datetime import datetime, timedelta
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        trends = {
            'security_this_week': SecurityAnalysis.query.filter(
                SecurityAnalysis.created_at >= week_ago
            ).count(),
            'performance_this_week': PerformanceTest.query.filter(
                PerformanceTest.created_at >= week_ago
            ).count()
        }
        
        return render_template(
            'pages/analysis_hub.html',
            stats=stats,
            recent_security=recent_security,
            recent_performance=recent_performance,
            trends=trends
        )
    except Exception as e:
        logger.error(f"Error loading analysis hub: {e}")
        return render_template('pages/error.html',
                             error_code=500,
                             error_title='Analysis Hub Error',
                             error_message=str(e))


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
        return render_template('partials/testing/security_test_form.html', models=models)
    except Exception as e:
        logger.error(f"Error loading security test form: {e}")
        return render_template('partials/common/error.html', 
                             error=f"Error loading security test form: {str(e)}")


@analysis_bp.route('/performance_test_form')
def performance_test_form():
    """HTMX endpoint for performance test form."""
    return render_template('partials/testing/performance_test_form.html')


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
    apps = []
    
    if model_slug:
        try:
            apps = GeneratedApplication.query.filter_by(model_slug=model_slug).all()
        except Exception as e:
            logger.error(f"Error getting apps for model {model_slug}: {e}")
    
    return render_template('partials/common/model_apps_select.html', 
                         apps=apps, 
                         model_slug=model_slug)
