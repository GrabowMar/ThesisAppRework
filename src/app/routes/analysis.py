"""
Analysis Routes
==============

Routes for managing analysis operations and results.
"""

import logging
import time
from functools import wraps

from flask import Blueprint, request, jsonify, render_template

from ..services.task_manager import TaskManager
from ..models import GeneratedApplication

# Set up logger
logger = logging.getLogger(__name__)

analysis_bp = Blueprint('analysis', __name__, url_prefix='/analysis')

# ---------------------------------------------------------------------------
# Lightweight in-process rate limiting (best-effort; not for multi-instance)
# ---------------------------------------------------------------------------
_last_call_registry = {}

def rate_limited(min_interval: float = 5.0):
    """Decorator to throttle high-frequency HTMX polling endpoints.

    Uses (route, remote_addr) key in an in-memory dictionary. If calls arrive
    sooner than min_interval seconds, returns a 429 with a tiny partial that
    HTMX will swap in (but visually minimal) instead of hitting the DB again.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                from flask import request, make_response
                key = (fn.__name__, request.remote_addr or 'anon')
                now = time.time()
                last = _last_call_registry.get(key, 0)
                if now - last < min_interval:
                    # Too soon; short-circuit with 429
                    resp = make_response('<div class="d-none" data-rate="limited"></div>', 429)
                    resp.headers['Retry-After'] = str(int(min_interval))
                    return resp
                _last_call_registry[key] = now
            except Exception:  # pragma: no cover - safety net
                pass
            return fn(*args, **kwargs)
        return wrapper
    return decorator

# Initialize services
task_manager = TaskManager()


@analysis_bp.route('/')
def analysis_hub():
    """Unified analysis hub served through dynamic single_page shell.

    Former template: pages/analysis.html (now removed in favor of partials).
    """
    try:
        # Provide initial context so that included partials render without relying
        # on the first HTMX refresh (prevents StrictUndefined errors on first load)
        from datetime import datetime, timedelta
        from sqlalchemy import desc
        from ..models import SecurityAnalysis, PerformanceTest, ZAPAnalysis, OpenRouterAnalysis

        # Aggregate headline stats (mirrors /analysis/api/stats endpoint)
        stats = {
            'total_security': SecurityAnalysis.query.count(),
            'total_performance': PerformanceTest.query.count(),
            'total_zap': ZAPAnalysis.query.count(),
            'total_ai': OpenRouterAnalysis.query.count()
        }

        # Weekly trend snapshot (mirrors /analysis/api/trends endpoint)
        week_ago = datetime.utcnow() - timedelta(days=7)
        trends = {
            'security_this_week': SecurityAnalysis.query.filter(SecurityAnalysis.created_at >= week_ago).count(),
            'performance_this_week': PerformanceTest.query.filter(PerformanceTest.created_at >= week_ago).count()
        }

        # Recent lists used by their respective partials (they self-refresh via HTMX)
        recent_security = SecurityAnalysis.query.order_by(desc(SecurityAnalysis.created_at)).limit(5).all()
        recent_performance = PerformanceTest.query.order_by(desc(PerformanceTest.created_at)).limit(5).all()

        return render_template(
            'pages/analysis.html',
            stats=stats,
            trends=trends,
            recent_security=recent_security,
            recent_performance=recent_performance
        )
    except Exception as e:  # pragma: no cover - defensive catch
        logger.error(f"Error loading analysis hub: {e}")
        return render_template(
            'single_page.html',
            page_title='Error',
            main_partial='partials/common/error.html',
            error=str(e)
        ), 500

@analysis_bp.get('/api/stats')
def htmx_analysis_stats():
    """HTMX endpoint for refreshing stats cards."""
    try:
        from ..models import SecurityAnalysis, PerformanceTest, ZAPAnalysis, OpenRouterAnalysis
        stats = {
            'total_security': SecurityAnalysis.query.count(),
            'total_performance': PerformanceTest.query.count(),
            'total_zap': ZAPAnalysis.query.count(),
            'total_ai': OpenRouterAnalysis.query.count()
        }
        return render_template('partials/analysis/stats_cards.html', stats=stats)
    except Exception as e:
        logger.error(f"HTMX stats error: {e}")
        return render_template('partials/common/error.html', error='Failed to load stats'), 500

@analysis_bp.get('/api/trends')
def htmx_analysis_trends():
    """HTMX endpoint for refreshing trends card."""
    try:
        from ..models import SecurityAnalysis, PerformanceTest
        from datetime import datetime, timedelta
        week_ago = datetime.utcnow() - timedelta(days=7)
        trends = {
            'security_this_week': SecurityAnalysis.query.filter(SecurityAnalysis.created_at >= week_ago).count(),
            'performance_this_week': PerformanceTest.query.filter(PerformanceTest.created_at >= week_ago).count()
        }
        return render_template('partials/analysis/trends.html', trends=trends)
    except Exception as e:
        logger.error(f"HTMX trends error: {e}")
        return render_template('partials/common/error.html', error='Failed to load trends'), 500

@analysis_bp.get('/api/recent/security')
@rate_limited(2.5)
def htmx_recent_security():
    """HTMX endpoint for recent security analyses list."""
    try:
        from ..models import SecurityAnalysis
        from sqlalchemy import desc
        recent_security = SecurityAnalysis.query.order_by(desc(SecurityAnalysis.created_at)).limit(5).all()
        return render_template('partials/analysis/recent_security.html', recent_security=recent_security)
    except Exception as e:
        logger.error(f"HTMX recent security error: {e}")
        return render_template('partials/common/error.html', error='Failed to load security list'), 500

@analysis_bp.get('/api/recent/performance')
@rate_limited(2.5)
def htmx_recent_performance():
    """HTMX endpoint for recent performance tests list."""
    try:
        from ..models import PerformanceTest
        from sqlalchemy import desc
        recent_performance = PerformanceTest.query.order_by(desc(PerformanceTest.created_at)).limit(5).all()
        return render_template('partials/analysis/recent_performance.html', recent_performance=recent_performance)
    except Exception as e:
        logger.error(f"HTMX recent performance error: {e}")
        return render_template('partials/common/error.html', error='Failed to load performance list'), 500


@analysis_bp.route('/security/start', methods=['POST'])
def start_security_analysis():
    """Start security analysis for an application."""
    try:
        data = request.get_json(silent=True) or {}
        app_id = data.get('app_id')
        if not app_id:
            return jsonify({'error': 'Application ID required'}), 400

        app = GeneratedApplication.query.get_or_404(app_id)

        # Raw config flags (persisted as options)
        config = {
            'bandit_enabled': data.get('bandit_enabled', True),
            'safety_enabled': data.get('safety_enabled', True),
            'pylint_enabled': data.get('pylint_enabled', True),
            'eslint_enabled': data.get('eslint_enabled', True),
            'npm_audit_enabled': data.get('npm_audit_enabled', True),
            'snyk_enabled': data.get('snyk_enabled', False),
        }

        # Derive list of enabled tools for TaskManager API
        tool_key_map = {
            'bandit_enabled': 'bandit',
            'safety_enabled': 'safety',
            'pylint_enabled': 'pylint',
            'eslint_enabled': 'eslint',
            'npm_audit_enabled': 'npm_audit',
            'snyk_enabled': 'snyk'
        }
        tools = [tool_key_map[k] for k, v in config.items() if v and k in tool_key_map]

        # Start analysis task (returns task id string)
        task_id = task_manager.start_security_analysis(
            app.model_slug,
            app.app_number,
            tools=tools,
            options=config
        )

        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': 'Security analysis started'
        })
        
    except Exception as e:
        logger.error(f"Error starting security analysis: {e}")
        return jsonify({'error': str(e)}), 500


@analysis_bp.route('/performance/start', methods=['POST'])
def start_performance_test():
    """Start performance test for an application."""
    try:
        data = request.get_json(silent=True) or {}
        app_id = data.get('app_id')
        if not app_id:
            return jsonify({'error': 'Application ID required'}), 400

        app = GeneratedApplication.query.get_or_404(app_id)

        # Test configuration
        test_config = {
            'test_type': data.get('test_type', 'load'),
            'users': data.get('users', 10),
            'spawn_rate': data.get('spawn_rate', 1.0),
            'duration': data.get('duration', 60)
        }

        # Start performance test (returns task id)
        task_id = task_manager.start_performance_test(
            app.model_slug,
            app.app_number,
            test_config
        )

        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': 'Performance test started'
        })
        
    except Exception as e:
        logger.error(f"Error starting performance test: {e}")
        return jsonify({'error': str(e)}), 500


@analysis_bp.route('/dynamic/start', methods=['POST'])
def start_dynamic_analysis():
    """Start dynamic (ZAP-like) analysis for an application."""
    try:
        data = request.get_json(silent=True) or {}

        # Support both app_id JSON payload and form-based model/app selection
        app_id = data.get('app_id')
        model_slug = data.get('model_slug')
        app_number = data.get('app_number')

        app = None
        if app_id:
            app = GeneratedApplication.query.get_or_404(app_id)
        else:
            if not model_slug or not app_number:
                return jsonify({'error': 'model_slug and app_number are required'}), 400
            try:
                app_number_int = int(app_number)
            except (TypeError, ValueError):
                return jsonify({'error': 'app_number must be an integer'}), 400
            app = GeneratedApplication.query.filter_by(model_slug=model_slug, app_number=app_number_int).first()
            if not app:
                return jsonify({'error': 'Application not found for given model/app'}), 404

        # Dynamic analysis configuration
        dynamic_options = {
            'target_url': data.get('target_url'),
            'scan_type': data.get('scan_type', 'baseline'),
            'timeout': data.get('timeout', 30),
            'include_paths': data.get('include_paths', []),
            'exclude_paths': data.get('exclude_paths', []),
        }

        # Start dynamic analysis task
        task_id = task_manager.start_dynamic_analysis(
            app.model_slug,
            app.app_number,
            options=dynamic_options
        )

        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': 'Dynamic analysis started'
        })

    except Exception as e:
        logger.error(f"Error starting dynamic analysis: {e}")
        return jsonify({'error': str(e)}), 500


@analysis_bp.route('/batch/start', methods=['POST'])
def start_batch_analysis():
    """Start batch analysis job."""
    try:
        data = request.get_json(silent=True) or {}
        analysis_types = data.get('analysis_types', [])
        models = data.get('model_filter', [])
        apps = data.get('app_filter', [])
        priority = data.get('priority', 'normal')

        if not analysis_types:
            return jsonify({'error': 'At least one analysis type required'}), 400

        options = {
            'priority': priority
        }

        # Start batch analysis (returns task id)
        task_id = task_manager.start_batch_analysis(
            models=models,
            apps=apps,
            analysis_types=analysis_types,
            options=options
        )

        return jsonify({
            'success': True,
            'task_id': task_id,
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


@analysis_bp.route('/dynamic_test_form')
def dynamic_test_form():
    """HTMX endpoint for dynamic (ZAP) test form."""
    from ..models import ModelCapability
    try:
        models = ModelCapability.query.all()
        return render_template('partials/testing/dynamic_test_form.html', models=models)
    except Exception as e:
        logger.error(f"Error loading dynamic test form: {e}")
        return render_template('partials/common/error.html', 
                             error=f"Error loading dynamic test form: {str(e)}")


@analysis_bp.route('/security/run', methods=['POST'])
def run_security_test():
    """Run security test (alias for start_security_analysis)."""
    return start_security_analysis()


@analysis_bp.route('/performance/run', methods=['POST'])
def run_performance_test():
    """Run performance test (alias for start_performance_test)."""
    return start_performance_test()


@analysis_bp.route('/dynamic/run', methods=['POST'])
def run_dynamic_test():
    """Run dynamic test (alias for start_dynamic_analysis)."""
    return start_dynamic_analysis()


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
        
        return render_template(
            'single_page.html',
            page_title='Security Analysis Complete',
            page_icon='fa-shield-alt',
            page_subtitle=f"Analysis #{analysis.id}",
            main_partial='partials/analysis/security_complete.html',
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
            tool_distribution=tool_distribution
        )
        
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

        return render_template(
            'single_page.html',
            page_title='Security Analysis (Complete View)',
            page_icon='fa-search',
            page_subtitle=f"Analysis #{analysis.id}",
            main_partial='partials/analysis/security_complete.html',
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
            analysis_metadata=analysis_metadata
        )
        
    except Exception as e:
        logger.error(f"Error rendering complete security analysis for {analysis_id}: {e}")
        from flask import flash, redirect, url_for
        flash(f'Error loading complete analysis: {str(e)}', 'error')
        return redirect(url_for('analysis.analysis_hub'))


# ============================================================================
# Combined recent activity endpoint (single poll instead of two)
# ============================================================================
@analysis_bp.get('/api/recent/combined')
@rate_limited(2.5)
def htmx_recent_combined():
    """Return a combined partial containing both recent security & performance.

    This reduces client polling overhead by consolidating two requests into one.
    """
    try:
        from ..models import SecurityAnalysis, PerformanceTest
        from sqlalchemy import desc
        security_items = SecurityAnalysis.query.order_by(desc(SecurityAnalysis.created_at)).limit(5).all()
        performance_items = PerformanceTest.query.order_by(desc(PerformanceTest.created_at)).limit(5).all()
        return render_template('partials/analysis/recent_combined.html',
                               recent_security=security_items,
                               recent_performance=performance_items)
    except Exception as e:  # pragma: no cover - defensive
        logger.error(f"HTMX recent combined error: {e}")
        return render_template('partials/common/error.html', error='Failed to load recent activity'), 500
