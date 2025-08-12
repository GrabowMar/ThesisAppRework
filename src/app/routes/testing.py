"""
Testing Routes
=============

Routes for managing testing operations and configurations.
"""

import logging
from flask import Blueprint, render_template, request, flash

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
        from ..extensions import db
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
            'pages/testing_center.html',
            stats=stats,
            active_tests=active_tests,
            recent_security=recent_security,
            recent_performance=recent_performance,
            weekly_trends=weekly_trends,
            success_rates=success_rates
        )
    except Exception as e:
        logger.error(f"Error loading testing center: {e}")
        return render_template('pages/error.html',
                             error_code=500,
                             error_title='Testing Center Error',
                             error_message=str(e))


@testing_bp.route('/security')
def security_testing():
    """Security testing configuration page."""
    try:
        from ..models import SecurityAnalysis, GeneratedApplication
        from ..extensions import db
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
            'pages/security_testing.html',
            applications=applications,
            security_analyses=recent_analyses
        )
    except Exception as e:
        logger.error(f"Error loading security testing: {e}")
        flash('Error loading security testing page', 'error')
        return render_template('pages/error.html',
                             error_code=500,
                             error_title='Security Testing Error',
                             error_message=str(e),
                             python_version='N/A',
                             flask_version='N/A',
                             debug_mode=False,
                             environment='N/A')


@testing_bp.route('/performance')
def performance_testing():
    """Performance testing configuration page."""
    try:
        from ..models import PerformanceTest, GeneratedApplication
        from ..extensions import db
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
            'pages/performance_testing.html',
            applications=applications,
            recent_tests=recent_tests
        )
    except Exception as e:
        logger.error(f"Error loading performance testing: {e}")
        flash('Error loading performance testing page', 'error')
        return render_template('pages/error.html',
                             error_code=500,
                             error_title='Performance Testing Error',
                             error_message=str(e),
                             python_version='N/A',
                             flask_version='N/A',
                             debug_mode=False,
                             environment='N/A')


@testing_bp.route('/batch')
def batch_testing():
    """Batch testing operations page."""
    try:
        from ..models import BatchAnalysis
        from ..extensions import db
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
            'pages/batch_testing.html',
            recent_batches=recent_batches,
            active_batches=active_batches,
            stats=stats
        )
    except Exception as e:
        logger.error(f"Error loading batch testing: {e}")
        flash('Error loading batch testing page', 'error')
        return render_template('pages/error.html',
                             error_code=500,
                             error_title='Batch Testing Error',
                             error_message=str(e))


@testing_bp.route('/results')
def testing_results():
    """Testing results and analytics page."""
    try:
        from ..models import SecurityAnalysis, PerformanceTest, ZAPAnalysis
        from ..extensions import db
        from sqlalchemy import func, desc
        from datetime import datetime, timedelta
        
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
            'pages/testing_results.html',
            results_stats=results_stats,
            recent_results=recent_results
        )
    except Exception as e:
        logger.error(f"Error loading testing results: {e}")
        flash('Error loading testing results page', 'error')
        return render_template('pages/error.html',
                             error_code=500,
                             error_title='Testing Results Error',
                             error_message=str(e))
