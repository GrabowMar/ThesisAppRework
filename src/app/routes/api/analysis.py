"""
Analysis API Routes
==================

API endpoints for analysis operations and results.
"""

import logging
from flask import jsonify, request, render_template

from . import api_bp
from ...models import (
    SecurityAnalysis, PerformanceTest, BatchAnalysis, 
    ContainerizedTest, GeneratedApplication
)
from ...extensions import db

# Set up logger
logger = logging.getLogger(__name__)


@api_bp.route('/analysis/security')
def api_list_security_analyses():
    """API endpoint: Get security analyses."""
    try:
        analyses = SecurityAnalysis.query.all()
        return jsonify([analysis.to_dict() for analysis in analyses])
    except Exception as e:
        logger.error(f"Error getting security analyses: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/analysis/security', methods=['POST'])
def api_create_security_analysis():
    """API endpoint: Create security analysis."""
    try:
        data = request.get_json()
        app_id = data.get('application_id')
        
        if not app_id:
            return jsonify({'error': 'application_id is required'}), 400
            
        # Check if application exists
        app = GeneratedApplication.query.get(app_id)
        if not app:
            return jsonify({'error': 'Application not found'}), 404
            
        # Create new security analysis
        analysis = SecurityAnalysis()
        analysis.application_id = app_id
        analysis.bandit_enabled = data.get('bandit_enabled', True)
        analysis.safety_enabled = data.get('safety_enabled', True)
        
        db.session.add(analysis)
        db.session.commit()
        
        return jsonify(analysis.to_dict()), 201
        
    except Exception as e:
        logger.error(f"Error creating security analysis: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/analysis/performance') 
def api_list_performance_tests():
    """API endpoint: Get performance tests."""
    try:
        tests = PerformanceTest.query.all()
        return jsonify([test.to_dict() for test in tests])
    except Exception as e:
        logger.error(f"Error getting performance tests: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/analysis/performance', methods=['POST'])
def api_create_performance_test():
    """API endpoint: Create performance test."""
    try:
        data = request.get_json()
        app_id = data.get('application_id')
        
        if not app_id:
            return jsonify({'error': 'application_id is required'}), 400
            
        # Check if application exists
        app = GeneratedApplication.query.get(app_id)
        if not app:
            return jsonify({'error': 'Application not found'}), 404
            
        # Create new performance test
        test = PerformanceTest()
        test.application_id = app_id
        test.test_type = data.get('test_type', 'load')
        test.users = data.get('users', 10)
        test.test_duration = data.get('test_duration', 60)
        
        db.session.add(test)
        db.session.commit()
        
        return jsonify(test.to_dict()), 201
        
    except Exception as e:
        logger.error(f"Error creating performance test: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/analysis/batch')
def api_analysis_batch():
    """API endpoint: Get batch analyses."""
    try:
        batches = BatchAnalysis.query.all()
        return jsonify([batch.to_dict() for batch in batches])
    except Exception as e:
        logger.error(f"Error getting batch analyses: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/analysis/containerized')
def api_analysis_containerized():
    """API endpoint: Get containerized tests."""
    try:
        tests = ContainerizedTest.query.all()
        return jsonify([test.to_dict() for test in tests])
    except Exception as e:
        logger.error(f"Error getting containerized tests: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/batch', methods=['POST'])
def api_create_batch():
    """API endpoint: Create batch analysis."""
    try:
        data = request.get_json()
        
        # Create new batch analysis
        import uuid
        batch = BatchAnalysis()
        batch.batch_id = str(uuid.uuid4())
        batch.total_tasks = data.get('total_tasks', 0)
        
        if 'analysis_types' in data:
            batch.set_analysis_types(data['analysis_types'])
        
        db.session.add(batch)
        db.session.commit()
        
        return jsonify(batch.to_dict()), 201
        
    except Exception as e:
        logger.error(f"Error creating batch analysis: {e}")
        return jsonify({'error': str(e)}), 400


@api_bp.route('/batch/<batch_id>/status')
def api_batch_status(batch_id):
    """API endpoint: Get batch status."""
    try:
        batch = BatchAnalysis.query.filter_by(batch_id=batch_id).first()
        if not batch:
            return jsonify({'error': 'Batch not found'}), 404
        return jsonify(batch.to_dict())
    except Exception as e:
        logger.error(f"Error getting batch status: {e}")
        return jsonify({'error': str(e)}), 500


# =================================================================
# ANALYSIS ORCHESTRATION AND CONFIGURATION
# =================================================================

@api_bp.route('/analysis/configure/<int:app_id>')
def api_analysis_configure_modal(app_id):
    """API endpoint to get analysis configuration modal."""
    try:
        app = GeneratedApplication.query.get(app_id)
        if not app:
            return f'<div class="alert alert-warning">Application {app_id} not found</div>', 404
        
        return render_template('partials/analysis_configure_modal.html', app=app)
    except Exception as e:
        logger.error(f"Error loading analysis configuration modal: {e}")
        return f'<div class="alert alert-danger">Error loading analysis configuration: {str(e)}</div>', 500


@api_bp.route('/analysis/start/<int:app_id>', methods=['POST'])
def api_analysis_start(app_id):
    """API endpoint to start comprehensive analysis for an application."""
    try:
        from ...services.background_service import get_background_service
        
        app = GeneratedApplication.query.get(app_id)
        if not app:
            return jsonify({'error': f'Application {app_id} not found'}), 404
        
        # Start comprehensive analysis (all types)
        service = get_background_service()
        if service:
            task_id = f"comprehensive_analysis_{app_id}"
            task = service.create_task(
                task_id=task_id,
                task_type="comprehensive_analysis",
                message=f"Starting comprehensive analysis for application {app_id}"
            )
            service.start_task(task_id)
            
            return jsonify({
                'success': True,
                'message': 'Comprehensive analysis started',
                'task_id': task_id
            })
        else:
            return jsonify({'error': 'Background service not available'}), 503
            
    except Exception as e:
        logger.error(f"Error starting analysis for app {app_id}: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/analysis/security/<int:app_id>', methods=['POST'])
def api_analysis_security(app_id):
    """API endpoint to start security analysis for an application."""
    try:
        from ...constants import AnalysisStatus
        from datetime import datetime, timezone
        
        app = GeneratedApplication.query.get(app_id)
        if not app:
            return jsonify({'error': f'Application {app_id} not found'}), 404
        
        # Create security analysis record
        analysis = SecurityAnalysis(
            application_id=app_id,
            status=AnalysisStatus.PENDING,
            created_at=datetime.now(timezone.utc)
        )
        
        db.session.add(analysis)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Security analysis started',
            'analysis_id': analysis.id
        })
            
    except Exception as e:
        logger.error(f"Error starting security analysis for app {app_id}: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/analysis/performance/<int:app_id>', methods=['POST'])
def api_analysis_performance(app_id):
    """API endpoint to start performance analysis for an application."""
    try:
        from ...constants import AnalysisStatus
        from datetime import datetime, timezone
        
        app = GeneratedApplication.query.get(app_id)
        if not app:
            return jsonify({'error': f'Application {app_id} not found'}), 404
        
        # Create performance test record
        test = PerformanceTest(
            application_id=app_id,
            status=AnalysisStatus.PENDING,
            created_at=datetime.now(timezone.utc)
        )
        
        db.session.add(test)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Performance test started',
            'test_id': test.id
        })
            
    except Exception as e:
        logger.error(f"Error starting performance test for app {app_id}: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/batch/active')
def api_batch_active():
    """API endpoint for active batch analyses (HTMX)."""
    try:
        from ...constants import JobStatus
        
        active_batches = db.session.query(BatchAnalysis).filter(
            BatchAnalysis.status.in_([JobStatus.RUNNING, JobStatus.PENDING])
        ).order_by(BatchAnalysis.created_at.desc()).all()
        
        return render_template('partials/active_batches.html', active_batches=active_batches)
    except Exception as e:
        logger.error(f"Error loading active batches: {e}")
        return f'<div class="alert alert-danger">Error loading active batches: {str(e)}</div>'


@api_bp.route('/batch/create', methods=['POST'])
def api_batch_create():
    """API endpoint to create a new batch analysis."""
    try:
        from ...services.background_service import get_background_service
        from ...constants import JobStatus
        import uuid
        
        # Get request data
        data = request.get_json() or {}
        
        # Create batch analysis record
        batch_id_uuid = str(uuid.uuid4())
        batch = BatchAnalysis(
            batch_id=batch_id_uuid,
            status=JobStatus.PENDING,
            total_tasks=data.get('total_tasks', 0),
            completed_tasks=0,
            failed_tasks=0
        )
        
        db.session.add(batch)
        db.session.commit()
        
        # Create background task
        service = get_background_service()
        task = service.create_task(
            task_id=f"batch_{batch_id_uuid}",
            task_type="batch_analysis",
            message=f"Starting batch analysis with {data.get('total_tasks', 0)} tasks"
        )
        
        return jsonify({
            'success': True,
            'batch_id': batch_id_uuid,
            'task_id': task.task_id
        })
    except Exception as e:
        logger.error(f"Error creating batch: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/batch/<batch_id>/start', methods=['POST'])
def api_batch_start(batch_id):
    """API endpoint to start a batch analysis."""
    try:
        from ...services.background_service import get_background_service
        from ...constants import JobStatus
        from datetime import datetime, timezone
        
        # Update batch status
        batch = db.session.query(BatchAnalysis).filter_by(batch_id=batch_id).first()
        if not batch:
            return jsonify({'error': 'Batch not found'}), 404
        
        batch.status = JobStatus.RUNNING
        batch.started_at = datetime.now(timezone.utc)
        db.session.commit()
        
        # Start background task
        service = get_background_service()
        task_id = f"batch_{batch_id}"
        service.start_task(task_id)
        
        return jsonify({'success': True, 'status': 'started'})
    except Exception as e:
        logger.error(f"Error starting batch {batch_id}: {e}")
        return jsonify({'error': str(e)}), 500
