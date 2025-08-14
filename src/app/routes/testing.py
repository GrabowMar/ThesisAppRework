"""
Testing Routes
=============

Routes for managing testing operations and configurations.
"""

import logging
import json
from datetime import datetime, timedelta
from flask import Blueprint, render_template, flash, request, jsonify

# Set up logger
logger = logging.getLogger(__name__)

testing_bp = Blueprint('testing', __name__, url_prefix='/testing')


@testing_bp.route('/')
def testing_center():
    """Testing center main page."""
    try:
        from ..models import (
            SecurityAnalysis, PerformanceTest, ZAPAnalysis,
            OpenRouterAnalysis, BatchAnalysis, ContainerizedTest
        )
        from sqlalchemy import desc
        from datetime import datetime, timedelta
        
        # Get testing statistics
        stats = {
            'total_security_tests': SecurityAnalysis.query.count(),
            'total_performance_tests': PerformanceTest.query.count(),
            'total_zap_scans': ZAPAnalysis.query.count(),
            'total_ai_analyses': OpenRouterAnalysis.query.count(),
            'total_batch_operations': BatchAnalysis.query.count(),
            'total_container_tests': ContainerizedTest.query.count()
        }
        
        # Get active tests
        from ..constants import JobStatus, ContainerState
        active_tests = {
            'security': SecurityAnalysis.query.filter_by(status=JobStatus.RUNNING).count(),
            'performance': PerformanceTest.query.filter_by(status=JobStatus.RUNNING).count(),
            'batch': BatchAnalysis.query.filter_by(status=JobStatus.RUNNING).count(),
            'containers': ContainerizedTest.query.filter_by(status=ContainerState.RUNNING).count()
        }
        
        # Get recent test results
        recent_security = SecurityAnalysis.query.order_by(
            desc(SecurityAnalysis.created_at)
        ).limit(5).all()
        
        recent_performance = PerformanceTest.query.order_by(
            desc(PerformanceTest.created_at)
        ).limit(5).all()
        
        # Get weekly trends
        week_ago = datetime.utcnow() - timedelta(days=7)
        weekly_trends = {
            'security_tests': SecurityAnalysis.query.filter(
                SecurityAnalysis.created_at >= week_ago
            ).count(),
            'performance_tests': PerformanceTest.query.filter(
                PerformanceTest.created_at >= week_ago
            ).count(),
            'zap_scans': ZAPAnalysis.query.filter(
                ZAPAnalysis.created_at >= week_ago
            ).count()
        }
        
        # Get test success rates
        success_rates = {}
        
        # Security test success rate
        total_security = SecurityAnalysis.query.count()
        failed_security = SecurityAnalysis.query.filter_by(status=JobStatus.FAILED).count()
        success_rates['security'] = (
            ((total_security - failed_security) / total_security * 100)
            if total_security > 0 else 0
        )
        
        # Performance test success rate
        total_performance = PerformanceTest.query.count()
        failed_performance = PerformanceTest.query.filter_by(status=JobStatus.FAILED).count()
        success_rates['performance'] = (
            ((total_performance - failed_performance) / total_performance * 100)
            if total_performance > 0 else 0
        )
        
        return render_template(
            'pages/testing.html',
            stats=stats,
            active_tests=active_tests,
            recent_security=recent_security,
            recent_performance=recent_performance,
            weekly_trends=weekly_trends,
            success_rates=success_rates
        )
    except Exception as e:
        logger.error(f"Error loading testing center: {e}")
        return render_template(
            'single_page.html',
            page_title='Error',
            page_icon='fa-triangle-exclamation',
            page_subtitle='Testing Center Error',
            main_partial='partials/common/error.html',
            error_code=500,
            error_title='Testing Center Error',
            error_message=str(e)
        )


@testing_bp.route('/security')
def security_testing():
    """Security testing configuration page."""
    try:
        from ..models import SecurityAnalysis, GeneratedApplication
        from sqlalchemy import desc

        # Get available applications for testing
        applications = GeneratedApplication.query.order_by(
            desc(GeneratedApplication.created_at)
        ).limit(20).all()

        # Get recent security analyses
        recent_analyses = SecurityAnalysis.query.order_by(
            desc(SecurityAnalysis.created_at)
        ).limit(10).all()

        return render_template(
            'single_page.html',
            page_title='Security Testing',
            page_icon='fa-shield-halved',
            page_subtitle='Configure and review security analyses',
            main_partial='partials/testing/platform_overview.html',  # reuse platform overview for now
            applications=applications,
            security_analyses=recent_analyses
        )
    except Exception as e:
        logger.error(f"Error loading security testing: {e}")
        flash('Error loading security testing page', 'error')
        return render_template(
            'single_page.html',
            page_title='Error',
            page_icon='fa-triangle-exclamation',
            page_subtitle='Security Testing Error',
            main_partial='partials/common/error.html',
            error_code=500,
            error_title='Security Testing Error',
            error_message=str(e),
            python_version='N/A',
            flask_version='N/A',
            debug_mode=False,
            environment='N/A'
        )


@testing_bp.route('/performance')
def performance_testing():
    """Performance testing configuration page."""
    try:
        from ..models import PerformanceTest, GeneratedApplication
        from sqlalchemy import desc

        # Get available applications for testing
        applications = GeneratedApplication.query.order_by(
            desc(GeneratedApplication.created_at)
        ).limit(20).all()

        # Get recent performance tests
        recent_tests = PerformanceTest.query.order_by(
            desc(PerformanceTest.created_at)
        ).limit(10).all()

        return render_template(
            'single_page.html',
            page_title='Performance Testing',
            page_icon='fa-gauge-high',
            page_subtitle='Configure and review performance tests',
            main_partial='partials/testing/platform_overview.html',  # reuse overview partial
            applications=applications,
            recent_tests=recent_tests
        )
    except Exception as e:
        logger.error(f"Error loading performance testing: {e}")
        flash('Error loading performance testing page', 'error')
        return render_template(
            'single_page.html',
            page_title='Error',
            page_icon='fa-triangle-exclamation',
            page_subtitle='Performance Testing Error',
            main_partial='partials/common/error.html',
            error_code=500,
            error_title='Performance Testing Error',
            error_message=str(e),
            python_version='N/A',
            flask_version='N/A',
            debug_mode=False,
            environment='N/A'
        )


@testing_bp.route('/batch')
def batch_testing():
    """Batch testing operations page."""
    try:
        from ..models import BatchAnalysis
        from sqlalchemy import desc

        # Get batch operations
        recent_batches = BatchAnalysis.query.order_by(
            desc(BatchAnalysis.created_at)
        ).limit(20).all()

        # Get active batches
        from ..constants import JobStatus
        active_batches = BatchAnalysis.query.filter(
            BatchAnalysis.status.in_([JobStatus.RUNNING, JobStatus.PENDING])
        ).all()

        # Calculate stats for the template
        stats = {
            'total_batches': BatchAnalysis.query.count(),
            'completed_batches': BatchAnalysis.query.filter(
                BatchAnalysis.status == JobStatus.COMPLETED
            ).count(),
            'failed_batches': BatchAnalysis.query.filter(
                BatchAnalysis.status == JobStatus.FAILED
            ).count(),
            'active_batches': len(active_batches)
        }

        return render_template(
            'single_page.html',
            page_title='Batch Testing',
            page_icon='fa-layer-group',
            page_subtitle='Manage batch analysis operations',
            main_partial='partials/testing/platform_overview.html',  # reuse overview
            recent_batches=recent_batches,
            active_batches=active_batches,
            stats=stats
        )
    except Exception as e:
        logger.error(f"Error loading batch testing: {e}")
        flash('Error loading batch testing page', 'error')
        return render_template(
            'single_page.html',
            page_title='Error',
            page_icon='fa-triangle-exclamation',
            page_subtitle='Batch Testing Error',
            main_partial='partials/common/error.html',
            error_code=500,
            error_title='Batch Testing Error',
            error_message=str(e)
        )


@testing_bp.route('/results')
def testing_results():
    """Testing results and analytics page."""
    try:
        from ..models import SecurityAnalysis, PerformanceTest
        from sqlalchemy import desc
        from datetime import datetime

        # Get results by status
        results_stats = {
            'security': {
                'total': SecurityAnalysis.query.count(),
                'completed': SecurityAnalysis.query.filter_by(status='completed').count(),
                'failed': SecurityAnalysis.query.filter_by(status='failed').count(),
                'running': SecurityAnalysis.query.filter_by(status='running').count()
            },
            'performance': {
                'total': PerformanceTest.query.count(),
                'completed': PerformanceTest.query.filter_by(status='completed').count(),
                'failed': PerformanceTest.query.filter_by(status='failed').count(),
                'running': PerformanceTest.query.filter_by(status='running').count()
            }
        }

        # Get recent results
        recent_results = []

        # Security results
        security_results = SecurityAnalysis.query.order_by(
            desc(SecurityAnalysis.created_at)
        ).limit(10).all()

        for result in security_results:
            recent_results.append({
                'type': 'Security',
                'id': result.id,
                'status': result.status,
                'created_at': result.created_at,
                'issues': result.total_issues or 0
            })

        # Performance results
        performance_results = PerformanceTest.query.order_by(
            desc(PerformanceTest.created_at)
        ).limit(10).all()

        for result in performance_results:
            recent_results.append({
                'type': 'Performance',
                'id': result.id,
                'status': result.status,
                'created_at': result.created_at,
                'rps': result.requests_per_second or 0
            })

        # Sort by created_at
        recent_results.sort(key=lambda x: x['created_at'] or datetime.min, reverse=True)
        recent_results = recent_results[:15]

        return render_template(
            'single_page.html',
            page_title='Testing Results',
            page_icon='fa-chart-bar',
            page_subtitle='Recent testing outcomes and statistics',
            main_partial='partials/testing/platform_overview.html',  # reuse overview until dedicated partial added
            results_stats=results_stats,
            recent_results=recent_results
        )
    except Exception as e:
        logger.error(f"Error loading testing results: {e}")
        flash('Error loading testing results page', 'error')
        return render_template(
            'single_page.html',
            page_title='Error',
            page_icon='fa-triangle-exclamation',
            page_subtitle='Testing Results Error',
            main_partial='partials/common/error.html',
            error_code=500,
            error_title='Testing Results Error',
            error_message=str(e)
        )


# Enhanced Testing API Endpoints

@testing_bp.route('/api/run-with-config', methods=['POST'])
def run_test_with_config():
    """Run test with enhanced configuration."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        config = data.get('config', {})
        model_slug = data.get('model_slug')
        app_number = data.get('app_number')
        
        if not model_slug or not app_number:
            return jsonify({
                'success': False, 
                'error': 'Model slug and app number required'
            }), 400
        
        # Import the analyzer configuration
        import sys
        import os
        analyzer_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'analyzer')
        if analyzer_path not in sys.path:
            sys.path.append(analyzer_path)
        
        from analyzer_config import AnalyzerConfig
        
        # Validate configuration
        analyzer_config = AnalyzerConfig()
        validation_result = analyzer_config.validate_full_config(config)
        
        if not validation_result['valid']:
            return jsonify({
                'success': False,
                'error': 'Invalid configuration',
                'validation_errors': validation_result['errors']
            }), 400
        
        # Start enhanced analysis task
        from ..tasks import run_enhanced_analysis
        task = run_enhanced_analysis.delay(model_slug, app_number, config)
        
        return jsonify({
            'success': True,
            'task_id': task.id,
            'message': 'Enhanced analysis started successfully'
        })
        
    except Exception as e:
        logger.error(f"Error starting enhanced test: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@testing_bp.route('/api/results/enhanced')
def get_enhanced_results():
    """Get enhanced results with filtering and pagination."""
    try:
        from ..models import SecurityAnalysis, PerformanceTest, OpenRouterAnalysis
        from sqlalchemy import desc, or_, and_
        
        # Get query parameters
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 25))
        model_filter = request.args.get('model', '')
        analysis_type_filter = request.args.get('analysisType', '')
        date_filter = request.args.get('dateRange', 'all')
        status_filter = request.args.get('status', '')
        search_filter = request.args.get('search', '')
        
        # Base queries for different analysis types
        results = []
        
        # Security analyses
        security_query = SecurityAnalysis.query
        if model_filter:
            security_query = security_query.filter(
                SecurityAnalysis.model_slug.contains(model_filter)
            )
        if status_filter:
            security_query = security_query.filter_by(status=status_filter)
        if search_filter:
            security_query = security_query.filter(
                or_(
                    SecurityAnalysis.model_slug.contains(search_filter),
                    SecurityAnalysis.results_json.contains(search_filter)
                )
            )
        
        # Apply date filter
        if date_filter != 'all':
            from datetime import datetime, timedelta
            now = datetime.utcnow()
            if date_filter == 'today':
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif date_filter == 'week':
                start_date = now - timedelta(days=7)
            elif date_filter == 'month':
                start_date = now - timedelta(days=30)
            
            security_query = security_query.filter(SecurityAnalysis.created_at >= start_date)
        
        # Get security results
        if not analysis_type_filter or analysis_type_filter == 'security':
            for analysis in security_query.order_by(desc(SecurityAnalysis.created_at)).all():
                results.append({
                    'id': analysis.id,
                    'model_slug': analysis.model_slug,
                    'app_number': analysis.app_number,
                    'analysis_type': 'security',
                    'status': analysis.status,
                    'score': analysis.security_score,
                    'duration': (
                        (analysis.completed_at - analysis.created_at).total_seconds()
                        if analysis.completed_at and analysis.created_at else None
                    ),
                    'started_at': analysis.created_at.isoformat() if analysis.created_at else None,
                    'completed_at': analysis.completed_at.isoformat() if analysis.completed_at else None,
                    'files_analyzed': analysis.total_issues
                })
        
        # Performance tests
        perf_query = PerformanceTest.query
        if model_filter:
            perf_query = perf_query.filter(
                PerformanceTest.model_slug.contains(model_filter)
            )
        if status_filter:
            perf_query = perf_query.filter_by(status=status_filter)
        if search_filter:
            perf_query = perf_query.filter(
                PerformanceTest.model_slug.contains(search_filter)
            )
        
        if date_filter != 'all':
            perf_query = perf_query.filter(PerformanceTest.created_at >= start_date)
        
        # Get performance results
        if not analysis_type_filter or analysis_type_filter == 'performance':
            for test in perf_query.order_by(desc(PerformanceTest.created_at)).all():
                results.append({
                    'id': test.id,
                    'model_slug': test.model_slug,
                    'app_number': test.app_number,
                    'analysis_type': 'performance',
                    'status': test.status,
                    'score': int(test.requests_per_second) if test.requests_per_second else None,
                    'duration': (
                        (test.completed_at - test.created_at).total_seconds()
                        if test.completed_at and test.created_at else None
                    ),
                    'started_at': test.created_at.isoformat() if test.created_at else None,
                    'completed_at': test.completed_at.isoformat() if test.completed_at else None,
                    'files_analyzed': test.total_requests
                })
        
        # AI analyses
        ai_query = OpenRouterAnalysis.query
        if model_filter:
            ai_query = ai_query.filter(
                OpenRouterAnalysis.model_slug.contains(model_filter)
            )
        if status_filter:
            ai_query = ai_query.filter_by(status=status_filter)
        if search_filter:
            ai_query = ai_query.filter(
                or_(
                    OpenRouterAnalysis.model_slug.contains(search_filter),
                    OpenRouterAnalysis.results_json.contains(search_filter)
                )
            )
        
        if date_filter != 'all':
            ai_query = ai_query.filter(OpenRouterAnalysis.created_at >= start_date)
        
        # Get AI analysis results
        if not analysis_type_filter or analysis_type_filter == 'ai_analysis':
            for analysis in ai_query.order_by(desc(OpenRouterAnalysis.created_at)).all():
                results.append({
                    'id': analysis.id,
                    'model_slug': analysis.model_slug,
                    'app_number': analysis.app_number,
                    'analysis_type': 'ai_analysis',
                    'status': analysis.status,
                    'score': analysis.quality_score,
                    'duration': (
                        (analysis.completed_at - analysis.created_at).total_seconds()
                        if analysis.completed_at and analysis.created_at else None
                    ),
                    'started_at': analysis.created_at.isoformat() if analysis.created_at else None,
                    'completed_at': analysis.completed_at.isoformat() if analysis.completed_at else None,
                    'files_analyzed': None
                })
        
        # Sort results by started_at
        results.sort(key=lambda x: x['started_at'] or '', reverse=True)
        
        # Paginate
        total = len(results)
        start = (page - 1) * page_size
        end = start + page_size
        paginated_results = results[start:end]
        
        return jsonify({
            'success': True,
            'results': paginated_results,
            'pagination': {
                'current_page': page,
                'per_page': page_size,
                'total': total,
                'total_pages': (total + page_size - 1) // page_size
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting enhanced results: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@testing_bp.route('/api/results/<int:result_id>/detail')
def get_result_detail(result_id):
    """Get detailed information for a specific result."""
    try:
        from ..models import SecurityAnalysis, PerformanceTest, OpenRouterAnalysis
        
        # Try to find the result in different tables
        result = None
        result_type = None
        
        # Check security analyses
        security_result = SecurityAnalysis.query.get(result_id)
        if security_result:
            result = security_result
            result_type = 'security'
        
        # Check performance tests
        if not result:
            perf_result = PerformanceTest.query.get(result_id)
            if perf_result:
                result = perf_result
                result_type = 'performance'
        
        # Check AI analyses
        if not result:
            ai_result = OpenRouterAnalysis.query.get(result_id)
            if ai_result:
                result = ai_result
                result_type = 'ai_analysis'
        
        if not result:
            return jsonify({'success': False, 'error': 'Result not found'}), 404
        
        # Format detailed result data
        detailed_result = {
            'id': result.id,
            'model_slug': result.model_slug,
            'app_number': result.app_number,
            'analysis_type': result_type,
            'status': result.status,
            'created_at': result.created_at.isoformat() if result.created_at else None,
            'completed_at': result.completed_at.isoformat() if result.completed_at else None,
            'duration': (
                (result.completed_at - result.created_at).total_seconds()
                if result.completed_at and result.created_at else None
            ),
            'config': getattr(result, 'config_json', {}) or {},
            'results': getattr(result, 'results_json', {}) or {},
            'version': getattr(result, 'version', None),
            'service': getattr(result, 'service_name', None),
            'task_id': getattr(result, 'task_id', None)
        }
        
        # Add type-specific fields
        if result_type == 'security':
            detailed_result.update({
                'score': result.security_score,
                'total_issues': result.total_issues,
                'high_severity_issues': result.high_severity_issues,
                'medium_severity_issues': result.medium_severity_issues,
                'low_severity_issues': result.low_severity_issues
            })
        elif result_type == 'performance':
            detailed_result.update({
                'score': int(result.requests_per_second) if result.requests_per_second else None,
                'requests_per_second': result.requests_per_second,
                'mean_response_time': result.mean_response_time,
                'total_requests': result.total_requests,
                'failed_requests': result.failed_requests
            })
        elif result_type == 'ai_analysis':
            detailed_result.update({
                'score': result.quality_score,
                'model_used': result.model_used,
                'tokens_used': result.tokens_used,
                'cost': result.cost
            })
        
        return jsonify({
            'success': True,
            'result': detailed_result
        })
        
    except Exception as e:
        logger.error(f"Error getting result detail: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@testing_bp.route('/api/results/<int:result_id>/download')
def download_result(result_id):
    """Download result data as JSON."""
    try:
        from flask import Response
        import json
        
        # Get the detailed result
        response = get_result_detail(result_id)
        if response[1] != 200:
            return response
        
        result_data = response[0].get_json()['result']
        
        # Create JSON response
        json_data = json.dumps(result_data, indent=2, default=str)
        
        return Response(
            json_data,
            mimetype='application/json',
            headers={
                'Content-Disposition': f'attachment; filename=test_result_{result_id}.json'
            }
        )
        
    except Exception as e:
        logger.error(f"Error downloading result: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@testing_bp.route('/api/results/export')
def export_results():
    """Export multiple results as JSON."""
    try:
        from flask import Response
        import json
        
        result_ids = request.args.getlist('ids')
        if not result_ids:
            return jsonify({'success': False, 'error': 'No result IDs provided'}), 400
        
        exported_results = []
        
        for result_id in result_ids:
            try:
                response = get_result_detail(int(result_id))
                if response[1] == 200:
                    result_data = response[0].get_json()['result']
                    exported_results.append(result_data)
            except (ValueError, Exception) as e:
                logger.warning(f"Skipping invalid result ID {result_id}: {e}")
                continue
        
        if not exported_results:
            return jsonify({'success': False, 'error': 'No valid results found'}), 404
        
        # Create export data
        export_data = {
            'export_timestamp': datetime.utcnow().isoformat(),
            'total_results': len(exported_results),
            'results': exported_results
        }
        
        json_data = json.dumps(export_data, indent=2, default=str)
        
        return Response(
            json_data,
            mimetype='application/json',
            headers={
                'Content-Disposition': f'attachment; filename=test_results_export_{len(exported_results)}_items.json'
            }
        )
        
    except Exception as e:
        logger.error(f"Error exporting results: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# @testing_bp.route('/enhanced-config')
# def enhanced_config():
#     """Enhanced testing configuration page with models and apps loaded.
#     
#     NOTE: This route is commented out as configuration should be dynamically 
#     created before tests based on the selected model, not directly accessed.
#     The configuration functionality is now integrated into the test workflow.
#     """
#     try:
#         from ..models import ModelCapability, GeneratedApplication
#         from sqlalchemy import desc
# 
#         # Load all available models
#         models = ModelCapability.query.order_by(ModelCapability.model_name).all()
#         
#         # Load recent applications for quick access
#         recent_applications = GeneratedApplication.query.order_by(
#             desc(GeneratedApplication.created_at)
#         ).limit(50).all()
#         
#         # Group applications by model for easier access
#         apps_by_model = {}
#         for app in recent_applications:
#             if app.model_slug not in apps_by_model:
#                 apps_by_model[app.model_slug] = []
#             apps_by_model[app.model_slug].append(app)
# 
#         return render_template(
#             'single_page.html',
#             page_title='Enhanced Testing Configuration',
#             page_icon='fa-cogs',
#             page_subtitle='Advanced analyzer configuration with database integration',
#             main_partial='partials/testing/enhanced_config.html',
#             models=models,
#             recent_applications=recent_applications,
#             apps_by_model=apps_by_model
#         )
#     except Exception as e:
#         logger.error(f"Error loading enhanced config: {e}")
#         flash('Error loading enhanced configuration page', 'error')
#         return render_template(
#             'single_page.html',
#             page_title='Error',
#             page_icon='fa-triangle-exclamation',
#             page_subtitle='Enhanced Config Error',
#             main_partial='partials/common/error.html',
#             error_code=500,
#             error_title='Enhanced Config Error',
#             error_message=str(e)
#         )
