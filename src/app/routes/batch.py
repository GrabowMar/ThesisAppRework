"""
Batch Testing Routes
===================

Flask routes for managing batch analysis operations with analyzer integration.
Provides endpoints for creating, monitoring, and managing bulk analysis jobs.
"""

import logging
import uuid
from datetime import datetime

from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from sqlalchemy import desc

from ..extensions import db
from ..models import (
    BatchAnalysis, GeneratedApplication, SecurityAnalysis, 
    PerformanceTest, ZAPAnalysis, OpenRouterAnalysis, ModelCapability
)
from ..constants import JobStatus, JobPriority, AnalysisStatus
from ..services.service_locator import ServiceLocator

# Configure logging
logger = logging.getLogger(__name__)

# Create blueprint
batch_bp = Blueprint('batch', __name__, url_prefix='/batch')


@batch_bp.route('/')
def batch_overview():
    """Main batch testing dashboard."""
    try:
        # Get batch job statistics
        total_batches = db.session.query(BatchAnalysis).count()
        active_batches = db.session.query(BatchAnalysis).filter(
            BatchAnalysis.status.in_([JobStatus.PENDING, JobStatus.RUNNING])
        ).count()
        completed_batches = db.session.query(BatchAnalysis).filter(
            BatchAnalysis.status == JobStatus.COMPLETED
        ).count()
        failed_batches = db.session.query(BatchAnalysis).filter(
            BatchAnalysis.status == JobStatus.FAILED
        ).count()
        
        # Get recent batch jobs
        recent_batches = db.session.query(BatchAnalysis).order_by(
            desc(BatchAnalysis.created_at)
        ).limit(10).all()
        
        # Get analyzer service status
        analyzer_service = ServiceLocator.get_analyzer_service()
        analyzer_status = {}
        if analyzer_service:
            try:
                analyzer_status = {'services': []}  # Placeholder
            except Exception as e:
                logger.error(f"Error getting analyzer status: {e}")
                analyzer_status = {'services': []}
        
        # Get available models for filtering
        available_models = db.session.query(
            ModelCapability.canonical_slug,
            ModelCapability.provider,
            ModelCapability.model_name
        ).distinct().all()
        
        # Calculate statistics
        stats = {
            'total_batches': total_batches,
            'active_batches': active_batches,
            'completed_batches': completed_batches,
            'failed_batches': failed_batches,
            'success_rate': (completed_batches / max(total_batches, 1)) * 100,
            'analyzer_services': len(analyzer_status.get('services', [])),
            'healthy_services': len([
                s for s in analyzer_status.get('services', [])
                if s.get('status') == 'healthy'
            ])
        }
        
        return render_template(
            'pages/batch.html',
            stats=stats,
            recent_batches=recent_batches,
            analyzer_status=analyzer_status,
            available_models=available_models
        )
    
    except Exception as e:
        logger.error(f"Error loading batch overview: {e}")
        flash(f"Error loading batch overview: {str(e)}", 'error')
        return render_template(
            'single_page.html',
            page_title='Batch Overview Error',
            main_partial='partials/common/error.html',
            error=str(e)
        )


@batch_bp.route('/create', methods=['GET', 'POST'])
def create_batch():
    """Create a new batch analysis job."""
    if request.method == 'GET':
        # Get available models and analysis types
        available_models = db.session.query(
            ModelCapability.canonical_slug,
            ModelCapability.provider,
            ModelCapability.model_name
        ).distinct().all()
        
        analysis_types = [
            {'id': 'security', 'name': 'Security Analysis', 'description': 'Static security scanning'},
            {'id': 'performance', 'name': 'Performance Testing', 'description': 'Load and stress testing'},
            {'id': 'zap', 'name': 'ZAP Security Scan', 'description': 'Dynamic security scanning'},
            {'id': 'ai_analysis', 'name': 'AI Code Analysis', 'description': 'AI-powered code review'}
        ]
        
        return render_template(
            'single_page.html',
            page_title='Create Batch',
            page_icon='fas fa-plus-circle',
            main_partial='partials/batch/create.html',
            available_models=available_models,
            analysis_types=analysis_types
        )
    
    try:
        # Parse form data
        batch_name = request.form.get('batch_name', f'Batch_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
        description = request.form.get('description', '')
        priority = JobPriority(request.form.get('priority', 'normal'))
        
        # Analysis configuration
        analysis_types = request.form.getlist('analysis_types')
        model_filter = request.form.getlist('model_filter')
        app_range_start = int(request.form.get('app_range_start', 1))
        app_range_end = int(request.form.get('app_range_end', 30))
        
        # Validation
        if not analysis_types:
            flash('At least one analysis type must be selected', 'error')
            return redirect(url_for('batch.create_batch'))
        
        if not model_filter:
            flash('At least one model must be selected', 'error')
            return redirect(url_for('batch.create_batch'))
        
        # Create app filter range
        app_filter = list(range(app_range_start, app_range_end + 1))
        
        # Generate batch ID
        batch_id = str(uuid.uuid4())[:8]
        
        # Calculate total tasks
        total_tasks = len(model_filter) * len(app_filter) * len(analysis_types)
        
        # Create batch analysis record
        batch_analysis = BatchAnalysis()
        batch_analysis.batch_id = batch_id
        batch_analysis.status = JobStatus.PENDING
        batch_analysis.total_tasks = total_tasks
        batch_analysis.completed_tasks = 0
        batch_analysis.failed_tasks = 0
        batch_analysis.progress_percentage = 0.0
        
        # Set filters and config
        batch_analysis.set_analysis_types(analysis_types)
        batch_analysis.set_model_filter(model_filter)
        batch_analysis.set_app_filter(app_filter)
        
        # Set configuration
        config = {
            'batch_name': batch_name,
            'description': description,
            'priority': priority.value,
            'analysis_types': analysis_types,
            'model_filter': model_filter,
            'app_filter': app_filter,
            'app_range': {'start': app_range_start, 'end': app_range_end},
            'options': {
                'timeout': int(request.form.get('timeout', 300)),
                'parallel_jobs': int(request.form.get('parallel_jobs', 3)),
                'retry_failed': request.form.get('retry_failed') == 'on',
                'continue_on_error': request.form.get('continue_on_error') == 'on'
            }
        }
        batch_analysis.set_config(config)
        
        # Save to database
        db.session.add(batch_analysis)
        db.session.commit()
        
        # Start batch processing (async)
        from ..services.batch_service import batch_service
        success = batch_service.start_job(batch_id)
        if success:
            flash(f'Batch analysis "{batch_name}" started successfully', 'success')
        else:
            flash(f'Failed to start batch analysis "{batch_name}"', 'error')
        
        return redirect(url_for('batch.batch_detail', batch_id=batch_id))
    
    except Exception as e:
        logger.error(f"Error creating batch: {e}")
        flash(f"Error creating batch: {str(e)}", 'error')
        return redirect(url_for('batch.create_batch'))


@batch_bp.route('/<batch_id>')
def batch_detail(batch_id: str):
    """Show detailed view of a specific batch analysis."""
    try:
        batch = db.session.query(BatchAnalysis).filter_by(batch_id=batch_id).first()
        if not batch:
            flash('Batch analysis not found', 'error')
            return redirect(url_for('batch.batch_overview'))
        
        # Get related analysis results
        analysis_results = []
        
        # Get security analyses for this batch's models/apps
        model_filter = batch.get_model_filter()
        app_filter = batch.get_app_filter()
        
        if model_filter and app_filter:
            # Get applications matching the batch criteria
            apps = db.session.query(GeneratedApplication).filter(
                GeneratedApplication.model_slug.in_(model_filter),
                GeneratedApplication.app_number.in_(app_filter)
            ).all()
            
            for app in apps:
                # Get all analysis types for this app
                if 'security' in batch.get_analysis_types():
                    security_analyses = db.session.query(SecurityAnalysis).filter_by(
                        application_id=app.id
                    ).all()
                    analysis_results.extend([{
                        'type': 'security',
                        'app': app,
                        'analysis': analysis
                    } for analysis in security_analyses])
                
                if 'performance' in batch.get_analysis_types():
                    performance_tests = db.session.query(PerformanceTest).filter_by(
                        application_id=app.id
                    ).all()
                    analysis_results.extend([{
                        'type': 'performance',
                        'app': app,
                        'analysis': analysis
                    } for analysis in performance_tests])
                
                if 'zap' in batch.get_analysis_types():
                    zap_analyses = db.session.query(ZAPAnalysis).filter_by(
                        application_id=app.id
                    ).all()
                    analysis_results.extend([{
                        'type': 'zap',
                        'app': app,
                        'analysis': analysis
                    } for analysis in zap_analyses])
                
                if 'ai_analysis' in batch.get_analysis_types():
                    ai_analyses = db.session.query(OpenRouterAnalysis).filter_by(
                        application_id=app.id
                    ).all()
                    analysis_results.extend([{
                        'type': 'ai_analysis',
                        'app': app,
                        'analysis': analysis
                    } for analysis in ai_analyses])
        
        # Calculate detailed statistics
        completed_count = len([r for r in analysis_results if r['analysis'].status == AnalysisStatus.COMPLETED])
        failed_count = len([r for r in analysis_results if r['analysis'].status == AnalysisStatus.FAILED])
        running_count = len([r for r in analysis_results if r['analysis'].status == AnalysisStatus.RUNNING])
        
        detailed_stats = {
            'total_analyses': len(analysis_results),
            'completed': completed_count,
            'failed': failed_count,
            'running': running_count,
            'pending': len(analysis_results) - completed_count - failed_count - running_count,
            'success_rate': (completed_count / max(len(analysis_results), 1)) * 100
        }
        
        return render_template(
            'single_page.html',
            page_title='Batch Detail',
            page_icon='fa-layer-group',
            page_subtitle=f"Batch {batch.batch_id}",
            main_partial='partials/batch/detail.html',
            batch=batch,
            analysis_results=analysis_results,
            detailed_stats=detailed_stats
        )
    
    except Exception as e:
        logger.error(f"Error loading batch detail: {e}")
        flash(f"Error loading batch detail: {str(e)}", 'error')
        return redirect(url_for('batch.batch_overview'))


@batch_bp.route('/api/status/<batch_id>')
def api_batch_status(batch_id: str):
    """API endpoint to get batch status."""
    try:
        batch = db.session.query(BatchAnalysis).filter_by(batch_id=batch_id).first()
        if not batch:
            return jsonify({'error': 'Batch not found'}), 404
        
        return jsonify(batch.to_dict())
    
    except Exception as e:
        logger.error(f"Error getting batch status: {e}")
        return jsonify({'error': str(e)}), 500


@batch_bp.route('/api/start/<batch_id>', methods=['POST'])
def api_start_batch(batch_id: str):
    """API endpoint to start a batch analysis."""
    try:
        batch = db.session.query(BatchAnalysis).filter_by(batch_id=batch_id).first()
        if not batch:
            return jsonify({'error': 'Batch not found'}), 404
        
        if batch.status != JobStatus.PENDING:
            return jsonify({'error': 'Batch is not in pending state'}), 400
        
        from ..services.batch_service import batch_service
        success = batch_service.start_job(batch.batch_id)
        if success:
            return jsonify({'success': True, 'message': 'Batch started successfully'})
        else:
            return jsonify({'error': 'Failed to start batch'}), 500
    
    except Exception as e:
        logger.error(f"Error starting batch: {e}")
        return jsonify({'error': str(e)}), 500


@batch_bp.route('/api/stop/<batch_id>', methods=['POST'])
def api_stop_batch(batch_id: str):
    """API endpoint to stop a batch analysis."""
    try:
        batch = db.session.query(BatchAnalysis).filter_by(batch_id=batch_id).first()
        if not batch:
            return jsonify({'error': 'Batch not found'}), 404
        
        if batch.status not in [JobStatus.RUNNING, JobStatus.PENDING]:
            return jsonify({'error': 'Batch is not running or pending'}), 400
        
        from ..services.batch_service import batch_service
        success = batch_service.cancel_job(batch.batch_id)
        if success:
            return jsonify({'success': True, 'message': 'Batch stopped successfully'})
        else:
            return jsonify({'error': 'Failed to stop batch'}), 500
    
    except Exception as e:
        logger.error(f"Error stopping batch: {e}")
        return jsonify({'error': str(e)}), 500


@batch_bp.route('/api/delete/<batch_id>', methods=['DELETE'])
def api_delete_batch(batch_id: str):
    """API endpoint to delete a batch analysis."""
    try:
        batch = db.session.query(BatchAnalysis).filter_by(batch_id=batch_id).first()
        if not batch:
            return jsonify({'error': 'Batch not found'}), 404
        
        if batch.status == JobStatus.RUNNING:
            return jsonify({'error': 'Cannot delete running batch'}), 400
        
        # Delete the batch
        db.session.delete(batch)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Batch deleted successfully'})
    
    except Exception as e:
        logger.error(f"Error deleting batch: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@batch_bp.route('/api/list')
def api_list_batches():
    """API endpoint to list all batch analyses."""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        status_filter = request.args.get('status')
        
        query = db.session.query(BatchAnalysis)
        
        if status_filter:
            try:
                status_enum = JobStatus(status_filter)
                query = query.filter(BatchAnalysis.status == status_enum)
            except ValueError:
                pass  # Invalid status, ignore filter
        
        # Get paginated results
        offset = (page - 1) * per_page
        batches_list = query.order_by(desc(BatchAnalysis.created_at)).offset(offset).limit(per_page).all()
        total_count = query.count()
        
        return jsonify({
            'batches': [batch.to_dict() for batch in batches_list],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total_count,
                'pages': (total_count + per_page - 1) // per_page,
                'has_next': offset + per_page < total_count,
                'has_prev': page > 1
            }
        })
    
    except Exception as e:
        logger.error(f"Error listing batches: {e}")
        return jsonify({'error': str(e)}), 500


@batch_bp.route('/api/infrastructure/status')
def api_infrastructure_status():
    """API endpoint to get analyzer infrastructure status."""
    try:
        # Return mock status for now
        status = {
            'services': [
                {'name': 'security-analyzer', 'status': 'healthy', 'service_type': 'security'},
                {'name': 'performance-tester', 'status': 'healthy', 'service_type': 'performance'},
                {'name': 'zap-scanner', 'status': 'healthy', 'service_type': 'zap'},
                {'name': 'ai-analyzer', 'status': 'healthy', 'service_type': 'ai'}
            ],
            'overall_status': 'healthy'
        }
        return jsonify(status)
    
    except Exception as e:
        logger.error(f"Error getting infrastructure status: {e}")
        return jsonify({'error': str(e)}), 500


@batch_bp.route('/api/infrastructure/start', methods=['POST'])
def api_start_infrastructure():
    """API endpoint to start analyzer infrastructure."""
    try:
        # Mock success response
        return jsonify({'success': True, 'message': 'Infrastructure started successfully'})
    
    except Exception as e:
        logger.error(f"Error starting infrastructure: {e}")
        return jsonify({'error': str(e)}), 500


@batch_bp.route('/api/infrastructure/stop', methods=['POST'])
def api_stop_infrastructure():
    """API endpoint to stop analyzer infrastructure."""
    try:
        # Mock success response
        return jsonify({'success': True, 'message': 'Infrastructure stopped successfully'})
    
    except Exception as e:
        logger.error(f"Error stopping infrastructure: {e}")
        return jsonify({'error': str(e)}), 500


@batch_bp.route('/list')
def batch_list():
    """HTMX endpoint for batch list."""
    try:
        status_filter = request.args.get('status')
        
        query = BatchAnalysis.query
        if status_filter:
            query = query.filter_by(status=status_filter)
        
        batches = query.order_by(
            BatchAnalysis.created_at.desc()
        ).limit(10).all()
        
        return render_template('partials/testing/batch_list.html', batches=batches)
    except Exception as e:
        logger.error(f"Error loading batch list: {e}")
        return render_template('partials/common/error.html', 
                             error=f"Error loading batch list: {str(e)}")


@batch_bp.route('/form')
def batch_form():
    """HTMX endpoint for batch form."""
    try:
        models = ModelCapability.query.all()
        return render_template('partials/testing/batch_form.html', models=models)
    except Exception as e:
        logger.error(f"Error loading batch form: {e}")
        return render_template('partials/common/error.html', 
                             error=f"Error loading batch form: {str(e)}")


# Import logger
logger = logging.getLogger(__name__)
