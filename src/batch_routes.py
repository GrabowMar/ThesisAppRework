"""
Enhanced Batch Dashboard Routes
===============================

Complete API and web routes for the batch analysis dashboard.
Provides comprehensive endpoints for job management, monitoring, and reporting.

Features:
- RESTful API for job management
- Real-time progress tracking
- WebSocket support for live updates
- Comprehensive filtering and pagination
- Export functionality
- Worker management
- System monitoring
"""

import json
import logging
from datetime import datetime, timedelta
from io import BytesIO
from typing import Any, Dict, List, Optional

from flask import (
    Blueprint, current_app, jsonify, request, render_template,
    send_file, Response, stream_template, make_response
)

# Import database and models
try:
    # Try relative imports
    from .extensions import db
    from .models import (
        BatchJob, BatchTask, BatchWorker, GeneratedApplication,
        JobStatus, TaskStatus, JobPriority, AnalysisType
    )
    from .batch_service import get_batch_manager, BatchConfiguration
    DATABASE_AVAILABLE = True
except ImportError:
    try:
        # Try absolute imports
        from extensions import db
        from models import (
            BatchJob, BatchTask, BatchWorker, GeneratedApplication,
            JobStatus, TaskStatus, JobPriority, AnalysisType
        )
        from batch_service import get_batch_manager, BatchConfiguration
        DATABASE_AVAILABLE = True
    except ImportError:
        DATABASE_AVAILABLE = False
        # Create dummy classes for development
        class BatchJob: pass
        class BatchTask: pass
        class BatchWorker: pass
        class GeneratedApplication: pass
        class JobStatus: pass
        class TaskStatus: pass
        class JobPriority: pass
        class AnalysisType: pass
        def get_batch_manager(): return None
        class BatchConfiguration: pass

# Initialize logger
logger = logging.getLogger(__name__)

# Create blueprint
batch_bp = Blueprint('batch', __name__, url_prefix='/batch')
batch_api_bp = Blueprint('batch_api', __name__, url_prefix='/api/batch')


# ===========================
# UTILITY FUNCTIONS
# ===========================

def validate_job_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate job creation data."""
    errors = {}
    
    if not data.get('name'):
        errors['name'] = 'Job name is required'
    elif len(data['name']) > 200:
        errors['name'] = 'Job name must be 200 characters or less'
    
    if not data.get('analysis_types'):
        errors['analysis_types'] = 'At least one analysis type is required'
    else:
        valid_types = [t.value for t in AnalysisType]
        invalid_types = [t for t in data['analysis_types'] if t not in valid_types]
        if invalid_types:
            errors['analysis_types'] = f'Invalid analysis types: {invalid_types}'
    
    if not data.get('models'):
        errors['models'] = 'At least one model is required'
    
    app_range = data.get('app_range', '1-5')
    if not app_range:
        errors['app_range'] = 'App range is required'
    
    priority = data.get('priority', 'normal')
    if priority not in [p.value for p in JobPriority]:
        errors['priority'] = f'Invalid priority: {priority}'
    
    return errors


def parse_filters(request_args) -> Dict[str, Any]:
    """Parse filtering parameters from request."""
    filters = {}
    
    # Status filter
    if 'status' in request_args and request_args['status']:
        try:
            filters['status'] = JobStatus(request_args['status'])
        except ValueError:
            pass
    
    # Priority filter
    if 'priority' in request_args and request_args['priority']:
        try:
            filters['priority'] = JobPriority(request_args['priority'])
        except ValueError:
            pass
    
    # Analysis type filter
    if 'analysis_type' in request_args and request_args['analysis_type']:
        filters['analysis_type'] = request_args['analysis_type']
    
    # Date range filter
    if 'created_after' in request_args:
        try:
            filters['created_after'] = datetime.fromisoformat(
                request_args['created_after'].replace('Z', '+00:00')
            )
        except ValueError:
            pass
    
    if 'created_before' in request_args:
        try:
            filters['created_before'] = datetime.fromisoformat(
                request_args['created_before'].replace('Z', '+00:00')
            )
        except ValueError:
            pass
    
    # Search filter
    if 'search' in request_args and request_args['search']:
        filters['search'] = request_args['search']
    
    return filters


def apply_job_filters(query, filters: Dict[str, Any]):
    """Apply filters to a job query."""
    if 'status' in filters:
        query = query.filter(BatchJob.status == filters['status'])
    
    if 'priority' in filters:
        query = query.filter(BatchJob.priority == filters['priority'])
    
    if 'analysis_type' in filters:
        # Filter by analysis type (JSON field)
        query = query.filter(
            BatchJob.analysis_types_json.contains(f'"{filters["analysis_type"]}"')
        )
    
    if 'created_after' in filters:
        query = query.filter(BatchJob.created_at >= filters['created_after'])
    
    if 'created_before' in filters:
        query = query.filter(BatchJob.created_at <= filters['created_before'])
    
    if 'search' in filters:
        search_term = f"%{filters['search']}%"
        query = query.filter(
            db.or_(
                BatchJob.name.ilike(search_term),
                BatchJob.description.ilike(search_term)
            )
        )
    
    return query


def format_duration(seconds: Optional[float]) -> str:
    """Format duration in seconds to human-readable string."""
    if not seconds:
        return "N/A"
    
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        return f"{seconds/3600:.1f}h"


def calculate_eta(job: BatchJob) -> Optional[str]:
    """Calculate estimated time to completion for a job."""
    if job.status not in [JobStatus.RUNNING, JobStatus.QUEUED]:
        return None
    
    if job.completed_tasks == 0:
        return "Calculating..."
    
    # Calculate average task duration
    completed_tasks = db.session.query(BatchTask).filter(
        BatchTask.job_id == job.id,
        BatchTask.status == TaskStatus.COMPLETED,
        BatchTask.actual_duration_seconds.isnot(None)
    ).all()
    
    if not completed_tasks:
        return "Calculating..."
    
    avg_duration = sum(t.actual_duration_seconds for t in completed_tasks) / len(completed_tasks)
    remaining_tasks = job.total_tasks - job.completed_tasks - job.failed_tasks
    
    eta_seconds = remaining_tasks * avg_duration
    return format_duration(eta_seconds)


# ===========================
# WEB ROUTES (Dashboard UI)
# ===========================

@batch_bp.route('/')
def dashboard():
    """Main batch dashboard page."""
    if not DATABASE_AVAILABLE:
        return render_template('batch/error.html', 
                             error="Database not available"), 500
    
    # Get summary statistics
    try:
        batch_manager = get_batch_manager()
        stats = batch_manager.get_system_statistics()
        
        return render_template('batch/dashboard.html', 
                             stats=stats,
                             analysis_types=[t.value for t in AnalysisType],
                             job_priorities=[p.value for p in JobPriority])
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        return render_template('batch/error.html', 
                             error=f"Failed to load dashboard: {e}"), 500


@batch_bp.route('/jobs')
def jobs_list():
    """Jobs list page with advanced filtering."""
    if not DATABASE_AVAILABLE:
        return render_template('batch/error.html', 
                             error="Database not available"), 500
    
    try:
        # Parse filters and pagination
        filters = parse_filters(request.args)
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 25))
        
        # Build query
        query = db.session.query(BatchJob)
        query = apply_job_filters(query, filters)
        
        # Order by creation date (newest first)
        query = query.order_by(BatchJob.created_at.desc())
        
        # Paginate
        pagination = query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        jobs = pagination.items
        
        # Add calculated fields
        for job in jobs:
            job.eta = calculate_eta(job)
            job.duration_formatted = format_duration(job.actual_duration_seconds)
        
        return render_template('batch/jobs_list.html',
                             jobs=jobs,
                             pagination=pagination,
                             filters=filters,
                             analysis_types=[t.value for t in AnalysisType],
                             job_priorities=[p.value for p in JobPriority],
                             job_statuses=[s.value for s in JobStatus])
    
    except Exception as e:
        logger.error(f"Jobs list error: {e}")
        return render_template('batch/error.html', 
                             error=f"Failed to load jobs: {e}"), 500


@batch_bp.route('/jobs/<job_id>')
def job_details(job_id: str):
    """Detailed job view page."""
    if not DATABASE_AVAILABLE:
        return render_template('batch/error.html', 
                             error="Database not available"), 500
    
    try:
        job = db.session.query(BatchJob).filter_by(id=job_id).first()
        if not job:
            return render_template('batch/error.html', 
                                 error="Job not found"), 404
        
        # Get tasks with pagination
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        
        tasks_query = db.session.query(BatchTask).filter_by(job_id=job_id)
        tasks_pagination = tasks_query.order_by(
            BatchTask.created_at.desc()
        ).paginate(page=page, per_page=per_page, error_out=False)
        
        # Calculate additional metrics
        job.eta = calculate_eta(job)
        job.duration_formatted = format_duration(job.actual_duration_seconds)
        
        # Task statistics
        task_stats = {}
        for status in TaskStatus:
            count = db.session.query(BatchTask).filter(
                BatchTask.job_id == job_id,
                BatchTask.status == status
            ).count()
            task_stats[status.value] = count
        
        return render_template('batch/job_details.html',
                             job=job,
                             tasks=tasks_pagination.items,
                             tasks_pagination=tasks_pagination,
                             task_stats=task_stats)
    
    except Exception as e:
        logger.error(f"Job details error: {e}")
        return render_template('batch/error.html', 
                             error=f"Failed to load job details: {e}"), 500


@batch_bp.route('/create')
def create_job_form():
    """Job creation form page."""
    try:
        # Get available models
        models = db.session.query(GeneratedApplication.model_slug).distinct().all()
        model_slugs = [m[0] for m in models]
        
        return render_template('batch/create_job.html',
                             analysis_types=[t.value for t in AnalysisType],
                             job_priorities=[p.value for p in JobPriority],
                             available_models=model_slugs)
    
    except Exception as e:
        logger.error(f"Create job form error: {e}")
        return render_template('batch/error.html', 
                             error=f"Failed to load create form: {e}"), 500


@batch_bp.route('/workers')
def workers_list():
    """Workers monitoring page."""
    if not DATABASE_AVAILABLE:
        return render_template('batch/error.html', 
                             error="Database not available"), 500
    
    try:
        # Get all workers
        workers = db.session.query(BatchWorker).order_by(
            BatchWorker.last_heartbeat.desc()
        ).all()
        
        # Get worker pool statistics
        batch_manager = get_batch_manager()
        worker_stats = batch_manager.worker_pool.get_worker_stats()
        
        return render_template('batch/workers.html',
                             workers=workers,
                             worker_stats=worker_stats)
    
    except Exception as e:
        logger.error(f"Workers list error: {e}")
        return render_template('batch/error.html', 
                             error=f"Failed to load workers: {e}"), 500


@batch_bp.route('/analytics')
def analytics():
    """Batch analytics and reporting page."""
    if not DATABASE_AVAILABLE:
        return render_template('batch/error.html', 
                             error="Database not available"), 500
    
    try:
        # Get analytics data
        batch_manager = get_batch_manager()
        system_stats = batch_manager.get_system_statistics()
        
        # Job completion trends (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_jobs = db.session.query(BatchJob).filter(
            BatchJob.created_at >= thirty_days_ago
        ).all()
        
        # Analysis type distribution
        analysis_type_stats = {}
        for job in recent_jobs:
            for analysis_type in job.get_analysis_types():
                analysis_type_stats[analysis_type] = analysis_type_stats.get(analysis_type, 0) + 1
        
        # Model analysis distribution
        model_stats = {}
        for job in recent_jobs:
            for model in job.get_models():
                model_stats[model] = model_stats.get(model, 0) + 1
        
        analytics_data = {
            'system_stats': system_stats,
            'recent_jobs_count': len(recent_jobs),
            'analysis_type_distribution': analysis_type_stats,
            'model_distribution': model_stats,
            'job_completion_trend': _calculate_completion_trend(recent_jobs)
        }
        
        return render_template('batch/analytics.html',
                             analytics=analytics_data)
    
    except Exception as e:
        logger.error(f"Analytics error: {e}")
        return render_template('batch/error.html', 
                             error=f"Failed to load analytics: {e}"), 500


def _calculate_completion_trend(jobs: List[BatchJob]) -> List[Dict[str, Any]]:
    """Calculate job completion trend data."""
    trend_data = {}
    
    for job in jobs:
        if job.completed_at:
            date_key = job.completed_at.strftime('%Y-%m-%d')
            if date_key not in trend_data:
                trend_data[date_key] = {'completed': 0, 'failed': 0}
            
            if job.status == JobStatus.COMPLETED:
                trend_data[date_key]['completed'] += 1
            elif job.status == JobStatus.FAILED:
                trend_data[date_key]['failed'] += 1
    
    # Convert to list format for charts
    return [
        {
            'date': date,
            'completed': data['completed'],
            'failed': data['failed']
        }
        for date, data in sorted(trend_data.items())
    ]


# ===========================
# API ROUTES
# ===========================

@batch_api_bp.route('/jobs', methods=['GET'])
def api_list_jobs():
    """API endpoint to list jobs with filtering and pagination."""
    if not DATABASE_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 500
    
    try:
        # Parse parameters
        filters = parse_filters(request.args)
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 25)), 100)  # Max 100 per page
        
        # Build query
        query = db.session.query(BatchJob)
        query = apply_job_filters(query, filters)
        
        # Order by priority and creation date
        query = query.order_by(
            BatchJob.priority.desc(),
            BatchJob.created_at.desc()
        )
        
        # Paginate
        pagination = query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        jobs_data = []
        for job in pagination.items:
            job_dict = job.to_dict()
            job_dict['eta'] = calculate_eta(job)
            job_dict['duration_formatted'] = format_duration(job.actual_duration_seconds)
            jobs_data.append(job_dict)
        
        return jsonify({
            'jobs': jobs_data,
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev
            },
            'filters_applied': filters
        })
    
    except Exception as e:
        logger.error(f"API list jobs error: {e}")
        return jsonify({'error': str(e)}), 500


@batch_api_bp.route('/jobs', methods=['POST'])
def api_create_job():
    """API endpoint to create a new batch job."""
    if not DATABASE_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 500
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate data
        errors = validate_job_data(data)
        if errors:
            return jsonify({'error': 'Validation failed', 'details': errors}), 400
        
        # Create job
        batch_manager = get_batch_manager()
        job_id = batch_manager.create_job(
            name=data['name'],
            description=data.get('description', ''),
            analysis_types=data['analysis_types'],
            models=data['models'],
            app_range=data.get('app_range', '1-5'),
            priority=data.get('priority', 'normal'),
            auto_start=data.get('auto_start', True),
            options=data.get('options', {})
        )
        
        return jsonify({
            'job_id': job_id,
            'message': 'Job created successfully'
        }), 201
    
    except Exception as e:
        logger.error(f"API create job error: {e}")
        return jsonify({'error': str(e)}), 500


@batch_api_bp.route('/jobs/<job_id>', methods=['GET'])
def api_get_job(job_id: str):
    """API endpoint to get job details."""
    if not DATABASE_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 500
    
    try:
        batch_manager = get_batch_manager()
        job_status = batch_manager.get_job_status(job_id)
        
        if not job_status:
            return jsonify({'error': 'Job not found'}), 404
        
        return jsonify(job_status)
    
    except Exception as e:
        logger.error(f"API get job error: {e}")
        return jsonify({'error': str(e)}), 500


@batch_api_bp.route('/jobs/<job_id>/start', methods=['POST'])
def api_start_job(job_id: str):
    """API endpoint to start a job."""
    if not DATABASE_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 500
    
    try:
        batch_manager = get_batch_manager()
        success = batch_manager.start_job(job_id)
        
        if success:
            return jsonify({'message': 'Job started successfully'})
        else:
            return jsonify({'error': 'Failed to start job'}), 400
    
    except Exception as e:
        logger.error(f"API start job error: {e}")
        return jsonify({'error': str(e)}), 500


@batch_api_bp.route('/jobs/<job_id>/cancel', methods=['POST'])
def api_cancel_job(job_id: str):
    """API endpoint to cancel a job."""
    if not DATABASE_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 500
    
    try:
        batch_manager = get_batch_manager()
        success = batch_manager.cancel_job(job_id)
        
        if success:
            return jsonify({'message': 'Job cancelled successfully'})
        else:
            return jsonify({'error': 'Failed to cancel job'}), 400
    
    except Exception as e:
        logger.error(f"API cancel job error: {e}")
        return jsonify({'error': str(e)}), 500


@batch_api_bp.route('/jobs/<job_id>', methods=['DELETE'])
def api_delete_job(job_id: str):
    """API endpoint to delete a job."""
    if not DATABASE_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 500
    
    try:
        job = db.session.query(BatchJob).filter_by(id=job_id).first()
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        # Can only delete completed, failed, or cancelled jobs
        if job.status in [JobStatus.RUNNING, JobStatus.QUEUED]:
            return jsonify({'error': 'Cannot delete running or queued jobs'}), 400
        
        # Delete associated tasks first (cascade should handle this)
        db.session.delete(job)
        db.session.commit()
        
        return jsonify({'message': 'Job deleted successfully'})
    
    except Exception as e:
        logger.error(f"API delete job error: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@batch_api_bp.route('/jobs/<job_id>/tasks', methods=['GET'])
def api_get_job_tasks(job_id: str):
    """API endpoint to get job tasks."""
    if not DATABASE_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 500
    
    try:
        # Check if job exists
        job = db.session.query(BatchJob).filter_by(id=job_id).first()
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        # Parse parameters
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 50)), 200)
        status_filter = request.args.get('status')
        
        # Build tasks query
        query = db.session.query(BatchTask).filter_by(job_id=job_id)
        
        if status_filter:
            try:
                status_enum = TaskStatus(status_filter)
                query = query.filter(BatchTask.status == status_enum)
            except ValueError:
                pass
        
        # Order by creation date
        query = query.order_by(BatchTask.created_at.desc())
        
        # Paginate
        pagination = query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        tasks_data = [task.to_dict() for task in pagination.items]
        
        return jsonify({
            'tasks': tasks_data,
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev
            }
        })
    
    except Exception as e:
        logger.error(f"API get job tasks error: {e}")
        return jsonify({'error': str(e)}), 500


@batch_api_bp.route('/jobs/<job_id>/progress', methods=['GET'])
def api_get_job_progress(job_id: str):
    """API endpoint to get real-time job progress."""
    if not DATABASE_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 500
    
    try:
        batch_manager = get_batch_manager()
        progress = batch_manager.progress_tracker.get_job_progress(job_id)
        
        # Also get latest job data from database
        job = db.session.query(BatchJob).filter_by(id=job_id).first()
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        job_data = job.to_dict()
        job_data['eta'] = calculate_eta(job)
        
        return jsonify({
            'job': job_data,
            'real_time_progress': progress
        })
    
    except Exception as e:
        logger.error(f"API get job progress error: {e}")
        return jsonify({'error': str(e)}), 500


@batch_api_bp.route('/jobs/bulk-action', methods=['POST'])
def api_bulk_job_action():
    """API endpoint for bulk job actions."""
    if not DATABASE_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 500
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        job_ids = data.get('job_ids', [])
        action = data.get('action')
        
        if not job_ids:
            return jsonify({'error': 'No job IDs provided'}), 400
        
        if action not in ['cancel', 'delete', 'restart']:
            return jsonify({'error': 'Invalid action'}), 400
        
        batch_manager = get_batch_manager()
        results = {'success': [], 'failed': []}
        
        for job_id in job_ids:
            try:
                if action == 'cancel':
                    success = batch_manager.cancel_job(job_id)
                elif action == 'delete':
                    job = db.session.query(BatchJob).filter_by(id=job_id).first()
                    if job and job.status not in [JobStatus.RUNNING, JobStatus.QUEUED]:
                        db.session.delete(job)
                        success = True
                    else:
                        success = False
                elif action == 'restart':
                    # Implementation for restart would go here
                    success = False
                
                if success:
                    results['success'].append(job_id)
                else:
                    results['failed'].append(job_id)
            
            except Exception as e:
                logger.error(f"Bulk action failed for job {job_id}: {e}")
                results['failed'].append(job_id)
        
        if action == 'delete':
            db.session.commit()
        
        return jsonify({
            'message': f'Bulk {action} completed',
            'results': results
        })
    
    except Exception as e:
        logger.error(f"Bulk action error: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@batch_api_bp.route('/statistics', methods=['GET'])
def api_get_statistics():
    """API endpoint to get system statistics."""
    if not DATABASE_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 500
    
    try:
        batch_manager = get_batch_manager()
        stats = batch_manager.get_system_statistics()
        return jsonify(stats)
    
    except Exception as e:
        logger.error(f"API statistics error: {e}")
        return jsonify({'error': str(e)}), 500


@batch_api_bp.route('/workers', methods=['GET'])
def api_get_workers():
    """API endpoint to get worker information."""
    if not DATABASE_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 500
    
    try:
        workers = db.session.query(BatchWorker).all()
        workers_data = [worker.to_dict() for worker in workers]
        
        batch_manager = get_batch_manager()
        pool_stats = batch_manager.worker_pool.get_worker_stats()
        
        return jsonify({
            'workers': workers_data,
            'pool_statistics': pool_stats
        })
    
    except Exception as e:
        logger.error(f"API get workers error: {e}")
        return jsonify({'error': str(e)}), 500


@batch_api_bp.route('/export/jobs', methods=['GET'])
def api_export_jobs():
    """API endpoint to export jobs data."""
    if not DATABASE_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 500
    
    try:
        # Parse filters
        filters = parse_filters(request.args)
        export_format = request.args.get('format', 'json')
        
        # Build query
        query = db.session.query(BatchJob)
        query = apply_job_filters(query, filters)
        query = query.order_by(BatchJob.created_at.desc())
        
        jobs = query.all()
        
        if export_format == 'csv':
            return _export_jobs_csv(jobs)
        else:
            # JSON export
            jobs_data = [job.to_dict() for job in jobs]
            
            response = make_response(jsonify(jobs_data))
            response.headers['Content-Disposition'] = 'attachment; filename=batch_jobs.json'
            return response
    
    except Exception as e:
        logger.error(f"Export jobs error: {e}")
        return jsonify({'error': str(e)}), 500


def _export_jobs_csv(jobs: List[BatchJob]) -> Response:
    """Export jobs to CSV format."""
    import csv
    from io import StringIO
    
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'ID', 'Name', 'Description', 'Status', 'Priority',
        'Total Tasks', 'Completed Tasks', 'Failed Tasks',
        'Progress %', 'Created At', 'Started At', 'Completed At',
        'Duration (seconds)', 'Analysis Types', 'Models'
    ])
    
    # Write data
    for job in jobs:
        writer.writerow([
            job.id,
            job.name,
            job.description or '',
            job.status.value if job.status else '',
            job.priority.value if job.priority else '',
            job.total_tasks,
            job.completed_tasks,
            job.failed_tasks,
            job.get_progress_percentage(),
            job.created_at.isoformat() if job.created_at else '',
            job.started_at.isoformat() if job.started_at else '',
            job.completed_at.isoformat() if job.completed_at else '',
            job.actual_duration_seconds or '',
            ', '.join(job.get_analysis_types()),
            ', '.join(job.get_models())
        ])
    
    output.seek(0)
    
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=batch_jobs.csv'
    
    return response


# ===========================
# ERROR HANDLERS
# ===========================

@batch_bp.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Resource not found'}), 404
    return render_template('batch/error.html', error="Page not found"), 404


@batch_bp.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal error: {error}")
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Internal server error'}), 500
    return render_template('batch/error.html', error="Internal server error"), 500


# ===========================
# TEMPLATE FILTERS
# ===========================

@batch_bp.app_template_filter('format_duration')
def template_format_duration(seconds):
    """Template filter to format duration."""
    return format_duration(seconds)


@batch_bp.app_template_filter('format_datetime')
def template_format_datetime(dt):
    """Template filter to format datetime."""
    if not dt:
        return "N/A"
    return dt.strftime('%Y-%m-%d %H:%M:%S')


@batch_bp.app_template_filter('format_progress')
def template_format_progress(percentage):
    """Template filter to format progress percentage."""
    if percentage is None:
        return "0%"
    return f"{percentage:.1f}%"


# Register blueprints function
def register_batch_blueprints(app):
    """Register batch blueprints with the Flask app."""
    app.register_blueprint(batch_bp)
    app.register_blueprint(batch_api_bp)
    
    logger.info("Batch blueprints registered")


# Export for use in main app
__all__ = ['batch_bp', 'batch_api_bp', 'register_batch_blueprints']
