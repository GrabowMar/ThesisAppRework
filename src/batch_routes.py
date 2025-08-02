"""
Batch Analysis Routes - Flask Integration
========================================

This module provides Flask route integration for the batch analysis system.
It connects the batch service with the web interface and provides HTMX-compatible
endpoints for real-time updates.

Features:
- RESTful API endpoints for batch job management
- HTMX-compatible partial template rendering
- Real-time progress tracking and updates
- Comprehensive error handling and validation
- Integration with existing Flask application architecture
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import json
import logging
from pathlib import Path

from flask import (
    Blueprint, current_app, flash, jsonify, request, 
    render_template, render_template_string, redirect, url_for
)
from sqlalchemy import and_, desc, func, or_
from sqlalchemy.exc import SQLAlchemyError

# Import existing models and services
try:
    from .extensions import db
    from .models import (
        AnalysisStatus, JobStatus, TaskStatus, AnalysisType,
        GeneratedApplication, ModelCapability, BatchJob, BatchTask, JobPriority
    )
    from .core_services import get_logger
    from .batch_service import BatchService, ToolType, ToolConfiguration
except ImportError:
    # Fallback for direct execution
    import sys
    sys.path.insert(0, '.')
    from extensions import db
    from models import (
        AnalysisStatus, JobStatus, TaskStatus, AnalysisType,
        GeneratedApplication, ModelCapability, BatchJob, BatchTask, JobPriority
    )
    from core_services import get_logger
    from batch_service import BatchService, ToolType, ToolConfiguration

# Initialize logger
logger = get_logger('batch_routes')

# Create batch routes blueprint
batch_routes_bp = Blueprint('batch_routes', __name__, url_prefix='/batch')
batch_api_bp = Blueprint('batch_api', __name__, url_prefix='/api/batch')

# ===========================
# UTILITY FUNCTIONS
# ===========================

def get_batch_service() -> Optional[BatchService]:
    """Get the batch service instance."""
    return current_app.config.get('BATCH_SERVICE')

def handle_batch_error(error: Exception, message: str = "An error occurred") -> Tuple[Dict, int]:
    """Handle batch service errors consistently."""
    logger.error(f"{message}: {str(error)}")
    return {
        'success': False,
        'error': str(error),
        'message': message
    }, 500

def parse_nested_form_data(form_data: Dict) -> Dict:
    """Parse nested form data from HTMX form submission."""
    result = {}
    
    for key, value in form_data.items():
        if key.endswith('[]'):
            # Handle array fields
            clean_key = key[:-2]
            if clean_key not in result:
                result[clean_key] = []
            result[clean_key].append(value)
        elif '[' in key and ']' in key:
            # Handle nested object fields
            main_key, sub_key = key.split('[', 1)
            sub_key = sub_key.rstrip(']')
            if main_key not in result:
                result[main_key] = {}
            result[main_key][sub_key] = value
        else:
            result[key] = value
    
    return result

def validate_job_configuration(config: Dict) -> Tuple[bool, List[str]]:
    """Validate job configuration data."""
    errors = []
    
    # Required fields
    if not config.get('name', '').strip():
        errors.append('Job name is required')
    
    if not config.get('models'):
        errors.append('At least one model must be selected')
    
    if not config.get('analysis_types'):
        errors.append('At least one analysis type must be selected')
    
    # Validate app range
    try:
        start = int(config.get('app_range_start', 1))
        end = int(config.get('app_range_end', 30))
        if start < 1 or end > 30 or start > end:
            errors.append('Invalid app range (must be 1-30)')
    except (ValueError, TypeError):
        errors.append('Invalid app range values')
    
    # Validate priority
    valid_priorities = [p.value for p in JobPriority]
    if config.get('priority', 'normal') not in valid_priorities:
        errors.append('Invalid priority level')
    
    return len(errors) == 0, errors

def get_available_test_files() -> List[Dict[str, Any]]:
    """Get list of available test files in the project."""
    test_files = []
    root_path = Path(current_app.root_path).parent
    
    # Find test files in root directory
    for pattern in ['test_*.py', '*_test.py']:
        for test_file in root_path.glob(pattern):
            if test_file.is_file():
                test_files.append({
                    'name': test_file.name,
                    'path': str(test_file),
                    'relative_path': str(test_file.relative_to(root_path)),
                    'size': test_file.stat().st_size,
                    'modified': datetime.fromtimestamp(test_file.stat().st_mtime),
                    'category': 'root'
                })
    
    # Find test files in tests directory
    tests_dir = root_path / 'tests'
    if tests_dir.exists():
        for test_file in tests_dir.rglob('test_*.py'):
            if test_file.is_file():
                test_files.append({
                    'name': test_file.name,
                    'path': str(test_file),
                    'relative_path': str(test_file.relative_to(root_path)),
                    'size': test_file.stat().st_size,
                    'modified': datetime.fromtimestamp(test_file.stat().st_mtime),
                    'category': 'tests'
                })
    
    # Sort by category then name
    test_files.sort(key=lambda x: (x['category'], x['name']))
    return test_files

def run_test_file(test_file_path: str, test_options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run a specific test file using pytest or unittest."""
    import subprocess
    import sys
    from pathlib import Path
    
    test_options = test_options or {}
    root_path = Path(current_app.root_path).parent
    
    # Validate test file exists
    test_path = Path(test_file_path)
    if not test_path.exists():
        return {
            'success': False,
            'error': f"Test file not found: {test_file_path}",
            'output': '',
            'exit_code': 1
        }
    
    try:
        # Determine test runner
        use_pytest = test_options.get('use_pytest', True)
        
        if use_pytest:
            # Try pytest first
            cmd = [sys.executable, '-m', 'pytest', str(test_path)]
            
            # Add pytest options
            if test_options.get('verbose'):
                cmd.append('-v')
            if test_options.get('capture', 'no') == 'no':
                cmd.append('-s')
            if test_options.get('tb_style'):
                cmd.extend(['--tb', test_options['tb_style']])
            if test_options.get('maxfail'):
                cmd.extend(['--maxfail', str(test_options['maxfail'])])
        else:
            # Fall back to unittest
            cmd = [sys.executable, '-m', 'unittest', str(test_path)]
            if test_options.get('verbose'):
                cmd.append('-v')
        
        # Set working directory
        cwd = root_path
        
        # Run the test
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=test_options.get('timeout', 300)  # 5 minute timeout
        )
        
        return {
            'success': result.returncode == 0,
            'output': result.stdout + result.stderr,
            'exit_code': result.returncode,
            'command': ' '.join(cmd),
            'duration': None  # Could add timing if needed
        }
        
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'error': f"Test execution timed out after {test_options.get('timeout', 300)} seconds",
            'output': '',
            'exit_code': 124
        }
    except Exception as e:
        return {
            'success': False,
            'error': f"Failed to execute test: {str(e)}",
            'output': '',
            'exit_code': 1
        }

# ===========================
# MAIN PAGE ROUTES
# ===========================

@batch_routes_bp.route('/')
def batch_dashboard():
    """Main batch analysis dashboard."""
    try:
        batch_service = get_batch_service()
        if not batch_service:
            flash('Batch service is not available', 'error')
            return redirect(url_for('main.dashboard'))
        
        # Get basic statistics for initial load
        stats = batch_service.get_stats()
        
        return render_template('pages/batch_analysis.html', 
                             page_title='Batch Analysis',
                             stats=stats)
        
    except Exception as e:
        logger.error(f"Error loading batch dashboard: {str(e)}")
        flash('Error loading batch analysis dashboard', 'error')
        return redirect(url_for('main.dashboard'))

@batch_routes_bp.route('/jobs/<job_id>')
def job_details(job_id: str):
    """Job details page."""
    try:
        batch_service = get_batch_service()
        if not batch_service:
            flash('Batch service is not available', 'error')
            return redirect(url_for('batch_routes.batch_dashboard'))
        
        job = batch_service.get_job(job_id)
        if not job:
            flash('Job not found', 'error')
            return redirect(url_for('batch_routes.batch_dashboard'))
        
        # Get job tasks
        tasks = BatchTask.query.filter_by(job_id=job_id).order_by(
            BatchTask.priority, BatchTask.created_at
        ).all()
        
        return render_template('pages/batch_job_details.html',
                             job=job,
                             tasks=tasks,
                             page_title=f'Job: {job.name}')
        
    except Exception as e:
        logger.error(f"Error loading job details: {str(e)}")
        flash('Error loading job details', 'error')
        return redirect(url_for('batch_routes.batch_dashboard'))

@batch_routes_bp.route('/tests')
def test_dashboard():
    """Test runner dashboard."""
    try:
        # Get available test files
        test_files = get_available_test_files()
        
        # Get recent test results from database 
        # Use description field to identify test runs
        recent_runs = db.session.query(BatchJob).filter(
            BatchJob.description.like('%test%')
        ).order_by(desc(BatchJob.created_at)).limit(10).all()
        
        return render_template('pages/batch_test_dashboard.html',
                             test_files=test_files,
                             recent_runs=recent_runs,
                             page_title='Test Runner Dashboard')
        
    except Exception as e:
        logger.error(f"Error loading test dashboard: {str(e)}")
        flash('Error loading test dashboard', 'error')
        return redirect(url_for('batch_routes.batch_dashboard'))

# ===========================
# API ROUTES - Statistics
# ===========================

@batch_api_bp.route('/stats')
def get_batch_stats():
    """Get batch analysis statistics."""
    try:
        batch_service = get_batch_service()
        if not batch_service:
            return jsonify({'error': 'Batch service not available'}), 503
        
        stats = batch_service.get_stats()
        
        # Add additional metrics
        total_tasks = db.session.query(func.count(BatchTask.id)).scalar() or 0
        active_workers = db.session.query(func.count(BatchTask.id)).filter(
            BatchTask.status == TaskStatus.RUNNING
        ).scalar() or 0
        
        # Calculate queue size (pending + running)
        queue_size = db.session.query(func.count(BatchJob.id)).filter(
            or_(BatchJob.status == JobStatus.PENDING, BatchJob.status == JobStatus.RUNNING)
        ).scalar() or 0
        
        enhanced_stats = {
            **stats,
            'total_tasks': total_tasks,
            'active_workers': active_workers,
            'queue_size': queue_size,
            'system_load': min(100, (active_workers / 4) * 100) if active_workers else 0
        }
        
        # Render as partial if HTMX request
        if request.headers.get('HX-Request'):
            return render_template('partials/batch_stats.html', stats=enhanced_stats)
        
        return jsonify(enhanced_stats)
        
    except Exception as e:
        return handle_batch_error(e, "Failed to get batch statistics")

@batch_api_bp.route('/system-status')
def get_system_status():
    """Get batch system status and health."""
    try:
        batch_service = get_batch_service()
        if not batch_service:
            return jsonify({'error': 'Batch service not available'}), 503
        
        # System health metrics
        health_data = {
            'service_status': 'healthy',
            'database_status': 'healthy',
            'worker_status': 'active',
            'last_job_completion': None,
            'average_job_duration': None,
            'success_rate': 0,
            'error_rate': 0
        }
        
        # Get recent job statistics
        recent_jobs = BatchJob.query.filter(
            BatchJob.created_at >= datetime.utcnow() - timedelta(hours=24)
        ).all()
        
        if recent_jobs:
            completed_jobs = [j for j in recent_jobs if j.status == JobStatus.COMPLETED]
            failed_jobs = [j for j in recent_jobs if j.status == JobStatus.FAILED]
            
            total_recent = len(recent_jobs)
            health_data['success_rate'] = round((len(completed_jobs) / total_recent) * 100, 1)
            health_data['error_rate'] = round((len(failed_jobs) / total_recent) * 100, 1)
            
            if completed_jobs:
                durations = [j.duration.total_seconds() for j in completed_jobs if j.duration]
                if durations:
                    health_data['average_job_duration'] = round(sum(durations) / len(durations), 1)
                
                latest_completion = max(completed_jobs, key=lambda x: x.completed_at or datetime.min)
                health_data['last_job_completion'] = latest_completion.completed_at.isoformat()
        
        # System resource usage (mock data - replace with actual monitoring)
        resource_data = {
            'cpu_usage': 25.5,
            'memory_usage': 45.2,
            'disk_usage': 60.1,
            'network_io': 15.8
        }
        
        if request.headers.get('HX-Request'):
            return render_template('partials/batch_system_status.html',
                                 health=health_data,
                                 resources=resource_data)
        
        return jsonify({
            'health': health_data,
            'resources': resource_data
        })
        
    except Exception as e:
        return handle_batch_error(e, "Failed to get system status")

# ===========================
# API ROUTES - Job Management
# ===========================

@batch_api_bp.route('/jobs', methods=['GET'])
def get_jobs():
    """Get batch jobs with optional filtering."""
    try:
        batch_service = get_batch_service()
        if not batch_service:
            return jsonify({'error': 'Batch service not available'}), 503
        
        # Parse query parameters
        status_filter = request.args.get('status', '').split(',') if request.args.get('status') else None
        limit = min(int(request.args.get('limit', 50)), 100)
        offset = int(request.args.get('offset', 0))
        page = int(request.args.get('page', 1))
        
        # Calculate offset from page
        if page > 1:
            offset = (page - 1) * limit
        
        # Build query
        query = BatchJob.query
        
        if status_filter:
            status_objects = []
            for status_str in status_filter:
                try:
                    status_objects.append(JobStatus(status_str.strip()))
                except ValueError:
                    continue
            if status_objects:
                query = query.filter(BatchJob.status.in_(status_objects))
        
        # Apply ordering and pagination
        total_count = query.count()
        jobs = query.order_by(desc(BatchJob.created_at)).offset(offset).limit(limit).all()
        
        # Calculate pagination info
        total_pages = (total_count + limit - 1) // limit
        
        # Format jobs for display
        formatted_jobs = []
        for job in jobs:
            job_dict = job.to_dict()
            job_dict['created_at_formatted'] = job.created_at.strftime('%Y-%m-%d %H:%M') if job.created_at else 'Unknown'
            job_dict['duration_formatted'] = str(job.duration).split('.')[0] if job.duration else None
            formatted_jobs.append(job_dict)
        
        # Render as partial if HTMX request
        if request.headers.get('HX-Request'):
            return render_template('partials/batch_jobs_table.html',
                                 jobs=formatted_jobs,
                                 page=page,
                                 limit=limit,
                                 total_pages=total_pages,
                                 total_count=total_count)
        
        return jsonify({
            'jobs': formatted_jobs,
            'pagination': {
                'page': page,
                'limit': limit,
                'total_pages': total_pages,
                'total_count': total_count
            }
        })
        
    except Exception as e:
        return handle_batch_error(e, "Failed to get jobs")

@batch_api_bp.route('/jobs', methods=['POST'])
def create_job():
    """Create a new batch job."""
    try:
        batch_service = get_batch_service()
        if not batch_service:
            return jsonify({'error': 'Batch service not available'}), 503
        
        # Parse form data
        if request.is_json:
            config_data = request.get_json()
        else:
            # Parse form data (from HTMX form submission)
            config_data = {}
            form_data = request.form.to_dict(flat=False)
            
            # Basic fields
            config_data['name'] = request.form.get('job_name', '').strip()
            config_data['description'] = request.form.get('job_description', '').strip()
            config_data['priority'] = request.form.get('job_priority', 'normal')
            
            # Model selection
            config_data['models'] = form_data.get('models', [])
            
            # App range
            try:
                config_data['app_range_start'] = int(request.form.get('app_range_start', 1))
                config_data['app_range_end'] = int(request.form.get('app_range_end', 30))
            except (ValueError, TypeError):
                config_data['app_range_start'] = 1
                config_data['app_range_end'] = 30
            
            # Analysis types
            config_data['analysis_types'] = form_data.get('analysis_types', [])
            
            # Tool configurations
            tools_config = {}
            for tool_type in ['bandit', 'safety', 'semgrep', 'eslint', 'locust']:
                enabled = request.form.get(f'tool_{tool_type}_enabled') == 'on'
                timeout = int(request.form.get(f'tool_{tool_type}_timeout', 300))
                tools_config[tool_type] = {
                    'enabled': enabled,
                    'timeout': timeout
                }
            config_data['tools'] = tools_config
            
            # Advanced options
            config_data['parallel_workers'] = int(request.form.get('parallel_workers', 4))
            config_data['retry_attempts'] = int(request.form.get('retry_attempts', 2))
            config_data['save_detailed_logs'] = request.form.get('save_detailed_logs') == 'on'
            config_data['email_notifications'] = request.form.get('email_notifications') == 'on'
        
        # Validate configuration
        is_valid, errors = validate_job_configuration(config_data)
        if not is_valid:
            if request.headers.get('HX-Request'):
                return render_template_string('''
                    <div class="alert alert-danger">
                        <h6>Validation Errors:</h6>
                        <ul class="mb-0">
                        {% for error in errors %}
                            <li>{{ error }}</li>
                        {% endfor %}
                        </ul>
                    </div>
                ''', errors=errors)
            
            return jsonify({'error': 'Validation failed', 'details': errors}), 400
        
        # Create the job
        job = batch_service.create_job(config_data)
        
        # Auto-start if requested
        auto_start = request.form.get('auto_start', 'true').lower() == 'true'
        if auto_start:
            batch_service.start_job(job.id)
        
        # Return success response
        if request.headers.get('HX-Request'):
            return render_template_string('''
                <div class="alert alert-success">
                    <i class="fas fa-check-circle"></i>
                    <strong>Job created successfully!</strong><br>
                    Job ID: <code>{{ job.id }}</code><br>
                    Status: <span class="badge badge-{{ 'success' if auto_started else 'warning' }}">
                        {{ 'Started' if auto_started else 'Created' }}
                    </span>
                </div>
            ''', job=job, auto_started=auto_start)
        
        return jsonify({
            'success': True,
            'job_id': job.id,
            'message': f"Job created {'and started' if auto_start else ''} successfully"
        })
        
    except Exception as e:
        return handle_batch_error(e, "Failed to create job")

@batch_api_bp.route('/jobs/<job_id>', methods=['GET'])
def get_job_details(job_id: str):
    """Get detailed information about a specific job."""
    try:
        batch_service = get_batch_service()
        if not batch_service:
            return jsonify({'error': 'Batch service not available'}), 503
        
        job = batch_service.get_job(job_id)
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        # Get job tasks with details
        tasks = BatchTask.query.filter_by(job_id=job_id).order_by(
            BatchTask.priority, BatchTask.created_at
        ).all()
        
        # Format task data
        formatted_tasks = []
        for task in tasks:
            task_dict = task.to_dict()
            task_dict['duration'] = None
            if task.started_at and task.completed_at:
                duration = task.completed_at - task.started_at
                task_dict['duration'] = str(duration).split('.')[0]
            formatted_tasks.append(task_dict)
        
        job_data = job.to_dict()
        job_data['tasks'] = formatted_tasks
        job_data['task_summary'] = {
            'total': len(formatted_tasks),
            'completed': len([t for t in formatted_tasks if t['status'] == 'completed']),
            'failed': len([t for t in formatted_tasks if t['status'] == 'failed']),
            'running': len([t for t in formatted_tasks if t['status'] == 'running']),
            'pending': len([t for t in formatted_tasks if t['status'] == 'pending'])
        }
        
        if request.headers.get('HX-Request'):
            return render_template('partials/batch_job_details.html', job=job_data)
        
        return jsonify(job_data)
        
    except Exception as e:
        return handle_batch_error(e, "Failed to get job details")

@batch_api_bp.route('/jobs/<job_id>/start', methods=['POST'])
def start_job(job_id: str):
    """Start a batch job."""
    try:
        batch_service = get_batch_service()
        if not batch_service:
            return jsonify({'error': 'Batch service not available'}), 503
        
        success = batch_service.start_job(job_id)
        if success:
            return jsonify({'success': True, 'message': 'Job started successfully'})
        else:
            return jsonify({'error': 'Failed to start job'}), 400
        
    except Exception as e:
        return handle_batch_error(e, "Failed to start job")

@batch_api_bp.route('/jobs/<job_id>/stop', methods=['POST'])
def stop_job(job_id: str):
    """Stop a running batch job."""
    try:
        batch_service = get_batch_service()
        if not batch_service:
            return jsonify({'error': 'Batch service not available'}), 503
        
        success = batch_service.stop_job(job_id)
        if success:
            return jsonify({'success': True, 'message': 'Job stopped successfully'})
        else:
            return jsonify({'error': 'Failed to stop job'}), 400
        
    except Exception as e:
        return handle_batch_error(e, "Failed to stop job")

@batch_api_bp.route('/jobs/<job_id>', methods=['DELETE'])
def delete_job(job_id: str):
    """Delete a batch job."""
    try:
        batch_service = get_batch_service()
        if not batch_service:
            return jsonify({'error': 'Batch service not available'}), 503
        
        success = batch_service.delete_job(job_id)
        if success:
            return jsonify({'success': True, 'message': 'Job deleted successfully'})
        else:
            return jsonify({'error': 'Failed to delete job'}), 400
        
    except Exception as e:
        return handle_batch_error(e, "Failed to delete job")

# ===========================
# API ROUTES - Models and Configuration
# ===========================

@batch_api_bp.route('/models/list')
def get_models_list():
    """Get list of available models for job creation."""
    try:
        # Get available models from database
        models = ModelCapability.query.filter_by(is_available=True).order_by(
            ModelCapability.provider, ModelCapability.model_name
        ).all()
        
        # Group by provider
        models_by_provider = {}
        for model in models:
            provider = model.provider
            if provider not in models_by_provider:
                models_by_provider[provider] = []
            
            models_by_provider[provider].append({
                'id': model.canonical_slug,
                'name': model.model_name,
                'slug': model.canonical_slug,
                'is_free': model.is_free,
                'context_window': model.context_window
            })
        
        if request.headers.get('HX-Request'):
            return render_template('partials/batch_model_selection.html',
                                 models_by_provider=models_by_provider)
        
        return jsonify(models_by_provider)
        
    except Exception as e:
        return handle_batch_error(e, "Failed to get models list")

@batch_api_bp.route('/cleanup', methods=['POST'])
def cleanup_old_jobs():
    """Clean up old completed and failed jobs."""
    try:
        batch_service = get_batch_service()
        if not batch_service:
            return jsonify({'error': 'Batch service not available'}), 503
        
        # Delete jobs older than 30 days
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        old_jobs = BatchJob.query.filter(
            and_(
                BatchJob.completed_at < cutoff_date,
                or_(
                    BatchJob.status == JobStatus.COMPLETED,
                    BatchJob.status == JobStatus.FAILED,
                    BatchJob.status == JobStatus.CANCELLED
                )
            )
        ).all()
        
        deleted_count = 0
        for job in old_jobs:
            if batch_service.delete_job(job.id):
                deleted_count += 1
        
        return jsonify({
            'success': True,
            'message': f'Deleted {deleted_count} old jobs'
        })
        
    except Exception as e:
        return handle_batch_error(e, "Failed to cleanup old jobs")

# ===========================
# API ROUTES - Test Runner
# ===========================

@batch_api_bp.route('/tests/files')
def get_test_files():
    """Get list of available test files."""
    try:
        test_files = get_available_test_files()
        
        # Render as partial if HTMX request
        if request.headers.get('HX-Request'):
            return render_template('partials/test_files_list.html', test_files=test_files)
        
        return jsonify({'success': True, 'data': test_files})
        
    except Exception as e:
        return handle_batch_error(e, "Failed to get test files")

@batch_api_bp.route('/tests/run', methods=['POST'])
def run_test():
    """Run a specific test file."""
    try:
        data = request.get_json() or request.form.to_dict()
        
        test_file = data.get('test_file')
        if not test_file:
            return jsonify({'error': 'Test file is required'}), 400
        
        # Parse test options
        test_options = {
            'use_pytest': data.get('use_pytest', True),
            'verbose': data.get('verbose', False),
            'capture': data.get('capture', 'no'),
            'tb_style': data.get('tb_style', 'short'),
            'maxfail': data.get('maxfail'),
            'timeout': int(data.get('timeout', 300))
        }
        
        # Create a batch job for the test run
        batch_service = get_batch_service()
        if batch_service:
            job_config = {
                'name': f"Test: {Path(test_file).name}",
                'description': f"Running test file: {test_file}",
                'priority': 'normal',
                'test_file': test_file,
                'test_options': test_options
            }
            
            job_id = batch_service.create_test_job(job_config)
            
            return jsonify({
                'success': True,
                'job_id': job_id,
                'message': f'Test job created: {job_id}'
            })
        else:
            # Run test directly if no batch service
            result = run_test_file(test_file, test_options)
            
            if request.headers.get('HX-Request'):
                return render_template('partials/test_result.html', 
                                     result=result, 
                                     test_file=test_file)
            
            return jsonify({'success': result['success'], 'data': result})
        
    except Exception as e:
        return handle_batch_error(e, "Failed to run test")

@batch_api_bp.route('/tests/run-multiple', methods=['POST'])
def run_multiple_tests():
    """Run multiple test files."""
    try:
        data = request.get_json() or request.form.to_dict()
        
        test_files = data.get('test_files', [])
        if isinstance(test_files, str):
            test_files = [test_files]
        
        if not test_files:
            return jsonify({'error': 'At least one test file is required'}), 400
        
        # Parse test options
        test_options = {
            'use_pytest': data.get('use_pytest', True),
            'verbose': data.get('verbose', False),
            'capture': data.get('capture', 'no'),
            'tb_style': data.get('tb_style', 'short'),
            'maxfail': data.get('maxfail'),
            'timeout': int(data.get('timeout', 300))
        }
        
        batch_service = get_batch_service()
        if batch_service:
            # Create batch job for multiple tests
            job_config = {
                'name': f"Test Suite ({len(test_files)} files)",
                'description': f"Running {len(test_files)} test files",
                'priority': data.get('priority', 'normal'),
                'test_files': test_files,
                'test_options': test_options
            }
            
            job_id = batch_service.create_test_suite_job(job_config)
            
            return jsonify({
                'success': True,
                'job_id': job_id,
                'message': f'Test suite job created: {job_id}'
            })
        else:
            # Run tests sequentially if no batch service
            results = []
            for test_file in test_files:
                result = run_test_file(test_file, test_options)
                results.append({
                    'test_file': test_file,
                    'result': result
                })
            
            if request.headers.get('HX-Request'):
                return render_template('partials/test_results_multiple.html', 
                                     results=results)
            
            return jsonify({'success': True, 'data': results})
        
    except Exception as e:
        return handle_batch_error(e, "Failed to run multiple tests")

@batch_api_bp.route('/tests/discover')
def discover_tests():
    """Discover and analyze test files."""
    try:
        test_files = get_available_test_files()
        
        # Analyze test files for more detailed information
        for test_file in test_files:
            try:
                # Read file and count test functions
                with open(test_file['path'], 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Count test functions
                import re
                test_functions = len(re.findall(r'def test_\w+\(', content))
                test_classes = len(re.findall(r'class Test\w+\(', content))
                
                test_file['test_functions'] = test_functions
                test_file['test_classes'] = test_classes
                test_file['estimated_duration'] = test_functions * 2  # Rough estimate
                
            except Exception as e:
                logger.warning(f"Could not analyze test file {test_file['path']}: {e}")
                test_file['test_functions'] = 0
                test_file['test_classes'] = 0
                test_file['estimated_duration'] = 0
        
        return jsonify({'success': True, 'data': test_files})
        
    except Exception as e:
        return handle_batch_error(e, "Failed to discover tests")

# ===========================
# PARTIAL TEMPLATES
# ===========================

def create_partial_templates():
    """Create partial template files for HTMX responses."""
    
    # Batch system status partial
    system_status_template = '''
<div class="row">
    <div class="col-lg-3 col-md-6 mb-3">
        <div class="card bg-{{ 'success' if health.service_status == 'healthy' else 'danger' }} text-white">
            <div class="card-body text-center">
                <h5>Service Status</h5>
                <h3>{{ health.service_status|title }}</h3>
            </div>
        </div>
    </div>
    
    <div class="col-lg-3 col-md-6 mb-3">
        <div class="card bg-info text-white">
            <div class="card-body text-center">
                <h5>Success Rate</h5>
                <h3>{{ health.success_rate }}%</h3>
            </div>
        </div>
    </div>
    
    <div class="col-lg-3 col-md-6 mb-3">
        <div class="card bg-primary text-white">
            <div class="card-body text-center">
                <h5>CPU Usage</h5>
                <h3>{{ resources.cpu_usage }}%</h3>
            </div>
        </div>
    </div>
    
    <div class="col-lg-3 col-md-6 mb-3">
        <div class="card bg-secondary text-white">
            <div class="card-body text-center">
                <h5>Memory Usage</h5>
                <h3>{{ resources.memory_usage }}%</h3>
            </div>
        </div>
    </div>
</div>

<div class="row mt-4">
    <div class="col-12">
        <div class="card">
            <div class="card-header">
                <h5 class="mb-0">System Health Details</h5>
            </div>
            <div class="card-body">
                <div class="row">
                    <div class="col-md-6">
                        <p><strong>Last Job Completion:</strong> 
                           {{ health.last_job_completion or 'No recent completions' }}</p>
                        <p><strong>Average Job Duration:</strong> 
                           {{ health.average_job_duration + ' seconds' if health.average_job_duration else 'N/A' }}</p>
                    </div>
                    <div class="col-md-6">
                        <p><strong>Error Rate:</strong> {{ health.error_rate }}%</p>
                        <p><strong>Worker Status:</strong> {{ health.worker_status|title }}</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
'''
    
    # Model selection partial
    model_selection_template = '''
{% for provider, models in models_by_provider.items() %}
<div class="provider-group mb-3">
    <h6 class="text-muted text-uppercase">{{ provider }}</h6>
    {% for model in models %}
    <div class="custom-control custom-checkbox mb-1">
        <input type="checkbox" class="custom-control-input" 
               id="model_{{ model.slug|replace('-', '_') }}" 
               name="models" value="{{ model.slug }}">
        <label class="custom-control-label" for="model_{{ model.slug|replace('-', '_') }}">
            {{ model.name }}
            {% if model.is_free %}
                <span class="badge badge-success badge-sm">Free</span>
            {% endif %}
        </label>
    </div>
    {% endfor %}
</div>
{% endfor %}
'''
    
    # Job details partial
    job_details_template = '''
<div class="row">
    <div class="col-md-8">
        <h6>Job Information</h6>
        <table class="table table-sm">
            <tr><td><strong>Name:</strong></td><td>{{ job.name }}</td></tr>
            <tr><td><strong>Status:</strong></td><td>
                <span class="badge badge-{{ 'success' if job.status == 'completed' else 'warning' if job.status == 'running' else 'danger' if job.status == 'failed' else 'secondary' }}">
                    {{ job.status|title }}
                </span>
            </td></tr>
            <tr><td><strong>Priority:</strong></td><td>{{ job.priority|title }}</td></tr>
            <tr><td><strong>Progress:</strong></td><td>{{ job.progress_percent }}% ({{ job.completed_tasks }}/{{ job.total_tasks }})</td></tr>
            <tr><td><strong>Created:</strong></td><td>{{ job.created_at }}</td></tr>
            {% if job.duration %}
            <tr><td><strong>Duration:</strong></td><td>{{ job.duration }}</td></tr>
            {% endif %}
        </table>
    </div>
    
    <div class="col-md-4">
        <h6>Task Summary</h6>
        <div class="progress mb-2" style="height: 25px;">
            <div class="progress-bar bg-success" style="width: {{ (job.task_summary.completed / job.task_summary.total * 100) if job.task_summary.total > 0 else 0 }}%">
                {{ job.task_summary.completed }} Completed
            </div>
            <div class="progress-bar bg-danger" style="width: {{ (job.task_summary.failed / job.task_summary.total * 100) if job.task_summary.total > 0 else 0 }}%">
                {{ job.task_summary.failed }} Failed
            </div>
        </div>
        <small class="text-muted">
            {{ job.task_summary.running }} running, {{ job.task_summary.pending }} pending
        </small>
    </div>
</div>

{% if job.description %}
<div class="mt-3">
    <h6>Description</h6>
    <p>{{ job.description }}</p>
</div>
{% endif %}

{% if job.tasks %}
<div class="mt-4">
    <h6>Tasks ({{ job.tasks|length }})</h6>
    <div class="table-responsive" style="max-height: 400px;">
        <table class="table table-sm table-striped">
            <thead class="thead-dark">
                <tr>
                    <th>Model</th>
                    <th>App</th>
                    <th>Type</th>
                    <th>Tool</th>
                    <th>Status</th>
                    <th>Duration</th>
                </tr>
            </thead>
            <tbody>
                {% for task in job.tasks %}
                <tr>
                    <td>{{ task.model_name }}</td>
                    <td>{{ task.app_number }}</td>
                    <td>{{ task.analysis_type }}</td>
                    <td>{{ task.tool_type or 'N/A' }}</td>
                    <td>
                        <span class="badge badge-{{ 'success' if task.status == 'completed' else 'warning' if task.status == 'running' else 'danger' if task.status == 'failed' else 'secondary' }}">
                            {{ task.status|title }}
                        </span>
                    </td>
                    <td>{{ task.duration or 'N/A' }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>
{% endif %}
'''
    
    # Write partial templates to files
    templates_dir = Path('src/templates/partials')
    templates_dir.mkdir(exist_ok=True)
    
    (templates_dir / 'batch_system_status.html').write_text(system_status_template)
    (templates_dir / 'batch_model_selection.html').write_text(model_selection_template)
    (templates_dir / 'batch_job_details.html').write_text(job_details_template)

# ===========================
# BLUEPRINT REGISTRATION
# ===========================

def register_batch_routes(app):
    """Register batch routes with the Flask app."""
    try:
        # Create partial templates
        create_partial_templates()
        
        # Register blueprints
        app.register_blueprint(batch_routes_bp)
        app.register_blueprint(batch_api_bp)
        
        logger.info("Batch routes registered successfully")
        
    except Exception as e:
        logger.error(f"Failed to register batch routes: {str(e)}")
        raise

if __name__ == "__main__":
    # Demo/test code
    print("Batch Routes Module - Ready for Integration")
    print("Features:")
    print("  ✓ RESTful API endpoints")
    print("  ✓ HTMX-compatible responses")
    print("  ✓ Real-time progress tracking")
    print("  ✓ Comprehensive error handling")
    print("  ✓ Flask integration ready")
