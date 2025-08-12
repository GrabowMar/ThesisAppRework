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


@analysis_bp.route('/security/<int:analysis_id>/results/view')
def security_analysis_results_view(analysis_id):
    """HTML view for security analysis results."""
    try:
        from flask import render_template, flash, redirect, url_for
        from ..models import SecurityAnalysis
        import json
        
        analysis = SecurityAnalysis.query.get(analysis_id)
        if not analysis:
            flash('Security analysis not found', 'error')
            return redirect(url_for('analysis.analysis_hub'))
        
        # Initialize results data
        bandit_results = None
        safety_results = None
        zap_results = None
        pylint_results = None
        eslint_results = None
        
        # Parse individual tool results from results_json
        if hasattr(analysis, 'results_json') and analysis.results_json:
            try:
                all_results = json.loads(analysis.results_json)
                bandit_results = all_results.get('bandit')
                safety_results = all_results.get('safety')
                zap_results = all_results.get('zap')
                pylint_results = all_results.get('pylint')
                eslint_results = all_results.get('eslint')
            except json.JSONDecodeError:
                # If parsing fails, set all to None
                pass
        
        # Get tool configurations
        bandit_config = analysis.get_bandit_config() if hasattr(analysis, 'get_bandit_config') else {}
        safety_config = analysis.get_safety_config() if hasattr(analysis, 'get_safety_config') else {}
        eslint_config = analysis.get_eslint_config() if hasattr(analysis, 'get_eslint_config') else {}
        pylint_config = analysis.get_pylint_config() if hasattr(analysis, 'get_pylint_config') else {}
        zap_config = analysis.get_zap_config() if hasattr(analysis, 'get_zap_config') else {}
        
        # Get analysis metadata
        analysis_metadata = analysis.get_metadata() if hasattr(analysis, 'get_metadata') else {}

        # Calculate summary metrics
        total_vulnerabilities = 0
        critical_high_count = 0
        tools_executed = 0
        
        # Count Bandit vulnerabilities
        if bandit_results and 'results' in bandit_results:
            bandit_count = len(bandit_results['results'])
            total_vulnerabilities += bandit_count
            tools_executed += 1
            # Count high/critical severity in Bandit
            for result in bandit_results['results']:
                if result.get('issue_severity', '').lower() in ['high', 'critical']:
                    critical_high_count += 1
        
        # Count Safety vulnerabilities
        if safety_results and 'vulnerabilities' in safety_results:
            safety_count = len(safety_results['vulnerabilities'])
            total_vulnerabilities += safety_count
            tools_executed += 1
            # Safety vulnerabilities are typically high severity by nature
            critical_high_count += safety_count
        
        # Count OWASP ZAP vulnerabilities
        if zap_results and 'site' in zap_results and zap_results['site']:
            if 'alerts' in zap_results['site'][0]:
                zap_count = len(zap_results['site'][0]['alerts'])
                total_vulnerabilities += zap_count
                tools_executed += 1
                # Count high risk alerts (riskcode 2-3)
                for alert in zap_results['site'][0]['alerts']:
                    if alert.get('riskcode', 0) >= 2:
                        critical_high_count += 1
        
        # Count Pylint issues
        if pylint_results:
            pylint_count = len(pylint_results)
            total_vulnerabilities += pylint_count
            tools_executed += 1
            # Count errors as high severity
            for result in pylint_results:
                if result.get('type', '') == 'error':
                    critical_high_count += 1
        
        # Count ESLint issues
        if eslint_results:
            eslint_count = 0
            for file_result in eslint_results:
                if 'messages' in file_result:
                    eslint_count += len(file_result['messages'])
                    # Count severity 2 (errors) as high severity
                    for message in file_result['messages']:
                        if message.get('severity', 0) == 2:
                            critical_high_count += 1
            total_vulnerabilities += eslint_count
            tools_executed += 1
        
        # Calculate scan duration
        scan_duration = 'N/A'
        if analysis.started_at and analysis.completed_at:
            duration = analysis.completed_at - analysis.started_at
            if duration.total_seconds() < 60:
                scan_duration = f"{int(duration.total_seconds())}s"
            else:
                scan_duration = f"{int(duration.total_seconds() // 60)}m {int(duration.total_seconds() % 60)}s"
        
        # Prepare severity distribution for charts
        severity_distribution = {
            'Critical': 0,
            'High': 0,
            'Medium': 0,
            'Low': 0,
            'Info': 0
        }
        
        tool_distribution = {
            'Bandit': len(bandit_results['results']) if bandit_results and 'results' in bandit_results else 0,
            'Safety': len(safety_results['vulnerabilities']) if safety_results and 'vulnerabilities' in safety_results else 0,
            'OWASP ZAP': len(zap_results['site'][0]['alerts']) if zap_results and 'site' in zap_results and zap_results['site'] and 'alerts' in zap_results['site'][0] else 0,
            'Pylint': len(pylint_results) if pylint_results else 0,
            'ESLint': sum(len(f.get('messages', [])) for f in eslint_results) if eslint_results else 0
        }
        
        # Count severity levels for Bandit
        if bandit_results and 'results' in bandit_results:
            for result in bandit_results['results']:
                severity = result.get('issue_severity', '').title()
                if severity in severity_distribution:
                    severity_distribution[severity] += 1
        
        # Count severity levels for ZAP
        if zap_results and 'site' in zap_results and zap_results['site']:
            if 'alerts' in zap_results['site'][0]:
                for alert in zap_results['site'][0]['alerts']:
                    risk_code = alert.get('riskcode', 0)
                    if risk_code == 3:
                        severity_distribution['High'] += 1
                    elif risk_code == 2:
                        severity_distribution['Medium'] += 1
                    elif risk_code == 1:
                        severity_distribution['Low'] += 1
                    else:
                        severity_distribution['Info'] += 1
        
        return render_template('pages/security_analysis_complete.html',
                             analysis=analysis,
                             bandit_results=bandit_results,
                             safety_results=safety_results,
                             zap_results=zap_results,
                             pylint_results=pylint_results,
                             eslint_results=eslint_results,
                             bandit_config=bandit_config,
                             safety_config=safety_config,
                             eslint_config=eslint_config,
                             pylint_config=pylint_config,
                             zap_config=zap_config,
                             analysis_metadata=analysis_metadata,
                             total_vulnerabilities=total_vulnerabilities,
                             critical_high_count=critical_high_count,
                             tools_executed=tools_executed,
                             scan_duration=scan_duration,
                             severity_distribution=severity_distribution,
                             tool_distribution=tool_distribution)
        
    except Exception as e:
        logger.error(f"Error rendering security analysis results for {analysis_id}: {e}")
        from flask import flash, redirect, url_for
        flash(f'Error loading results: {str(e)}', 'error')
        return redirect(url_for('analysis.analysis_hub'))


@analysis_bp.route('/security/<int:analysis_id>/results/complete')
def security_analysis_complete_view(analysis_id):
    """Complete HTML view for security analysis with all configurations and metadata."""
    try:
        from flask import render_template, flash, redirect, url_for
        from ..models import SecurityAnalysis
        import json
        
        analysis = SecurityAnalysis.query.get(analysis_id)
        if not analysis:
            flash('Security analysis not found', 'error')
            return redirect(url_for('analysis.analysis_hub'))
        
        # Initialize results data
        bandit_results = None
        safety_results = None
        zap_results = None
        pylint_results = None
        eslint_results = None
        
        # Parse individual tool results from results_json
        if hasattr(analysis, 'results_json') and analysis.results_json:
            try:
                all_results = json.loads(analysis.results_json)
                bandit_results = all_results.get('bandit')
                safety_results = all_results.get('safety')
                zap_results = all_results.get('zap')
                pylint_results = all_results.get('pylint')
                eslint_results = all_results.get('eslint')
            except json.JSONDecodeError:
                # If parsing fails, set all to None
                pass
        
        # Get tool configurations - these are the detailed configs
        bandit_config = analysis.get_bandit_config() if hasattr(analysis, 'get_bandit_config') else {}
        safety_config = analysis.get_safety_config() if hasattr(analysis, 'get_safety_config') else {}
        eslint_config = analysis.get_eslint_config() if hasattr(analysis, 'get_eslint_config') else {}
        pylint_config = analysis.get_pylint_config() if hasattr(analysis, 'get_pylint_config') else {}
        zap_config = analysis.get_zap_config() if hasattr(analysis, 'get_zap_config') else {}
        
        # Get analysis metadata
        analysis_metadata = analysis.get_metadata() if hasattr(analysis, 'get_metadata') else {}

        return render_template('pages/security_analysis_complete.html',
                             analysis=analysis,
                             bandit_results=bandit_results,
                             safety_results=safety_results,
                             zap_results=zap_results,
                             pylint_results=pylint_results,
                             eslint_results=eslint_results,
                             bandit_config=bandit_config,
                             safety_config=safety_config,
                             eslint_config=eslint_config,
                             pylint_config=pylint_config,
                             zap_config=zap_config,
                             analysis_metadata=analysis_metadata)
        
    except Exception as e:
        logger.error(f"Error rendering complete security analysis for {analysis_id}: {e}")
        from flask import flash, redirect, url_for
        flash(f'Error loading complete analysis: {str(e)}', 'error')
        return redirect(url_for('analysis.analysis_hub'))
