"""Automation Pipeline Jinja Routes
=====================================

Web interface routes for the end-to-end automation system that
orchestrates: Sample Generation → Analysis in a single unified workflow.

Note: Reports stage was removed (Dec 2025) - use Reports module separately.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from flask import Blueprint, current_app, jsonify, render_template, flash, redirect, url_for, request
from flask_login import current_user

from app.services.generation_v2 import get_generation_service


def _get_analyzer_host(service_name: str) -> str:
    """Get the hostname for an analyzer service.
    
    In Docker environment, uses container names for inter-container communication.
    Falls back to localhost for local development.
    
    Args:
        service_name: Name of the analyzer service
        
    Returns:
        Hostname string (e.g., 'static-analyzer' in Docker, 'localhost' locally)
    """
    in_docker = os.environ.get('IN_DOCKER', '').lower() in ('true', '1', 'yes')
    
    if in_docker:
        # Use container names for Docker inter-container communication
        return service_name
    
    # Use environment variable if set, otherwise localhost
    return os.environ.get('ANALYZER_HOST', 'localhost')
from app.models import ModelCapability, GeneratedApplication, AnalysisTask, PipelineSettings, PipelineExecution, PipelineExecutionStatus
from app.constants import AnalysisStatus
from app.extensions import db

automation_bp = Blueprint('automation', __name__, url_prefix='/automation')


def _authenticate_request():
    """
    Authenticate request using either session or Bearer token.
    Returns (user, error_response) tuple.
    """
    # Check for session authentication first
    if current_user.is_authenticated:
        return current_user, None
    
    # Check for Bearer token (for API endpoints)
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]
        try:
            from app.models import User
            user = User.verify_api_token(token)
            if user:
                # Set user for this request context
                from flask_login import login_user
                login_user(user, remember=False)
                return user, None
        except Exception as e:
            current_app.logger.warning(f"Token auth failed: {e}")
    
    return None, None


# Require authentication
@automation_bp.before_request
def require_authentication():
    """Require authentication for all automation endpoints."""
    # Check if this is an API endpoint (should allow token auth)
    is_api_endpoint = request.path.startswith('/automation/api/')
    
    user, _ = _authenticate_request()
    
    if not user and not current_user.is_authenticated:
        if is_api_endpoint:
            return jsonify({
                'success': False,
                'error': 'Authentication required. Use session or Bearer token.'
            }), 401
        else:
            flash('Please log in to access the automation pipeline.', 'info')
            return redirect(url_for('auth.login', next=request.url))


def _get_generation_service():
    """Get generation service instance."""
    return get_generation_service()


def _get_report_service():
    """Get report generation service instance."""
    from app.services.report_service import get_report_service
    return get_report_service()


def _build_status() -> Dict[str, Any]:
    """Build current automation status metrics."""
    try:
        svc = _get_generation_service()
        gen_status = svc.get_generation_status()
        
        # Get analysis task counts
        pending_tasks = AnalysisTask.query.filter_by(status=AnalysisStatus.PENDING).count()
        running_tasks = AnalysisTask.query.filter_by(status=AnalysisStatus.RUNNING).count()
        completed_tasks = AnalysisTask.query.filter(
            AnalysisTask.status.in_([AnalysisStatus.COMPLETED.value, AnalysisStatus.PARTIAL_SUCCESS.value])  # type: ignore[union-attr]
        ).count()
        
        return {
            'generation': {
                'in_flight': gen_status.get('in_flight_count', 0),
                'available_slots': gen_status.get('available_slots', 0),
                'max_concurrent': gen_status.get('max_concurrent', 3),
            },
            'analysis': {
                'pending': pending_tasks,
                'running': running_tasks,
                'completed': completed_tasks,
            },
            'system_healthy': True,
        }
    except Exception as exc:
        current_app.logger.exception("Failed to build automation status", exc_info=exc)
        return {
            'generation': {'in_flight': 0, 'available_slots': 0, 'max_concurrent': 0},
            'analysis': {'pending': 0, 'running': 0, 'completed': 0},
            'system_healthy': False,
        }


def _load_available_models() -> List[Dict[str, Any]]:
    """Load models available for generation."""
    try:
        models = ModelCapability.query.order_by(
            ModelCapability.provider, 
            ModelCapability.model_name
        ).all()
        return [
            {
                'id': m.model_id,
                'slug': m.canonical_slug,
                'name': m.model_name,
                'provider': m.provider,
                'display_name': f"{m.provider}/{m.model_name}",
                'input_price': m.input_price_per_token or 0,
                'output_price': m.output_price_per_token or 0,
            }
            for m in models
        ]
    except Exception as exc:
        current_app.logger.exception("Failed to load models", exc_info=exc)
        return []


def _load_available_templates() -> List[Dict[str, Any]]:
    """Load available generation templates."""
    try:
        svc = _get_generation_service()
        return svc.get_template_catalog()
    except Exception as exc:
        current_app.logger.exception("Failed to load templates", exc_info=exc)
        return []


def _load_existing_apps() -> List[Dict[str, Any]]:
    """Load all existing generated applications."""
    try:
        apps = GeneratedApplication.query.order_by(
            GeneratedApplication.model_slug,
            GeneratedApplication.app_number.desc()
        ).all()
        return [
            {
                'id': app.id,
                'model_slug': app.model_slug,
                'app_number': app.app_number,
                'template_slug': getattr(app, 'template_slug', None),
                'status': getattr(app, 'status', 'unknown'),
                'created_at': app.created_at,
            }
            for app in apps
        ]
    except Exception as exc:
        current_app.logger.exception("Failed to load existing apps", exc_info=exc)
        return []


def _load_user_settings(user_id: int) -> List[Dict[str, Any]]:
    """Load saved pipeline settings for a user."""
    try:
        settings = PipelineSettings.get_user_settings(user_id)
        return [s.to_dict() for s in settings]
    except Exception as exc:
        current_app.logger.exception("Failed to load user settings", exc_info=exc)
        return []


def _load_recent_pipelines(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Load recent pipeline executions for a user."""
    try:
        pipelines = PipelineExecution.get_user_pipelines(user_id, limit=limit)
        return [p.to_dict() for p in pipelines]
    except Exception as exc:
        current_app.logger.exception("Failed to load recent pipelines", exc_info=exc)
        return []


def _get_active_pipeline(user_id: int) -> Optional[Dict[str, Any]]:
    """Get the currently active (running) pipeline for a user."""
    try:
        pipeline = PipelineExecution.query.filter_by(
            user_id=user_id,
            status=PipelineExecutionStatus.RUNNING
        ).order_by(PipelineExecution.created_at.desc()).first()
        return pipeline.to_dict() if pipeline else None
    except Exception as exc:
        current_app.logger.exception("Failed to get active pipeline", exc_info=exc)
        return None


@automation_bp.route('/')
def index():
    """Main automation pipeline interface."""
    status = _build_status()
    models = _load_available_models()
    templates = _load_available_templates()
    existing_apps = _load_existing_apps()
    saved_settings = _load_user_settings(current_user.id) if current_user.is_authenticated else []
    recent_pipelines = _load_recent_pipelines(current_user.id, limit=50) if current_user.is_authenticated else []
    active_pipeline = _get_active_pipeline(current_user.id) if current_user.is_authenticated else None
    
    return render_template(
        'pages/automation/automation_main.html',
        status=status,
        models=models,
        templates=templates,
        existing_apps=existing_apps,
        saved_settings=saved_settings,
        recent_pipelines=recent_pipelines,
        active_pipeline=active_pipeline,
        page_title='Automation Pipeline',
        active_page='automation',
    )


# ---------------------------------------------------------------------------
# HTMX partial endpoints for real-time updates
# ---------------------------------------------------------------------------


@automation_bp.route('/fragments/status')
def fragment_status():
    """Return status metrics fragment for HTMX polling."""
    status = _build_status()
    return render_template(
        'pages/automation/partials/_status_metrics.html',
        status=status,
    )


@automation_bp.route('/fragments/pipeline-progress/<pipeline_id>')
def fragment_pipeline_progress(pipeline_id: str):
    """Return pipeline progress fragment for HTMX polling."""
    # Load pipeline state from session or database
    try:
        from flask import session
        pipelines = session.get('automation_pipelines', {})
        pipeline = pipelines.get(pipeline_id, {})
        
        return render_template(
            'pages/automation/partials/_pipeline_progress.html',
            pipeline_id=pipeline_id,
            pipeline=pipeline,
        )
    except Exception as exc:
        current_app.logger.exception(f"Error loading pipeline {pipeline_id}", exc_info=exc)
        return '<div class="alert alert-danger">Error loading pipeline status</div>'


@automation_bp.route('/fragments/tools/<category>')
def fragment_tools(category: str):
    """Return tools list fragment for a specific category via HTMX.
    
    Uses intersect trigger so tools load when the container scrolls into view.
    This fixes the issue where tools don't load on initial page load because
    Step 2 panel is hidden.
    """
    valid_categories = ['static', 'dynamic', 'performance', 'ai']
    if category not in valid_categories:
        return '<div class="p-2 text-danger small"><i class="fas fa-exclamation-triangle me-1"></i>Invalid category</div>', 400
    
    try:
        from app.engines.container_tool_registry import get_container_tool_registry, AnalyzerContainer
        
        registry = get_container_tool_registry()
        all_tools = registry.get_all_tools()
        
        # Map category to container enum
        category_to_container = {
            'static': AnalyzerContainer.STATIC,
            'dynamic': AnalyzerContainer.DYNAMIC,
            'performance': AnalyzerContainer.PERFORMANCE,
            'ai': AnalyzerContainer.AI,
        }
        
        target_container = category_to_container[category]
        category_tools = [
            {
                'name': tool.name,
                'display_name': tool.display_name,
                'description': tool.description,
                'available': tool.available,
            }
            for tool in all_tools.values()
            if tool.container == target_container
        ]
        
        return render_template(
            'pages/automation/partials/_tools_list.html',
            tools=category_tools,
            category=category,
        )
        
    except ImportError as e:
        current_app.logger.warning(f"Container tool registry not available: {e}")
        return '<div class="p-2 text-muted small">Tool registry not available</div>'
        
    except Exception as e:
        current_app.logger.exception(f"Error getting tools for {category}: {e}")
        return f'<div class="p-2 text-danger small"><i class="fas fa-exclamation-triangle me-1"></i>Error loading tools</div>'


@automation_bp.route('/fragments/stage/<stage_name>')
def fragment_stage(stage_name: str):
    """Return stage configuration fragment."""
    valid_stages = ['generation', 'analysis']  # Reports stage removed Dec 2025
    if stage_name not in valid_stages:
        return '<div class="alert alert-danger">Invalid stage</div>', 400
    
    context = {}
    
    if stage_name == 'generation':
        context['models'] = _load_available_models()
        context['templates'] = _load_available_templates()
        context['existing_apps'] = _load_existing_apps()
        context['saved_settings'] = _load_user_settings(current_user.id) if current_user.is_authenticated else []
    elif stage_name == 'analysis':
        # Load tool registry
        try:
            from app.engines.container_tool_registry import get_container_tool_registry
            registry = get_container_tool_registry()
            context['tools'] = list(registry.get_all_tools().values())
        except Exception:
            context['tools'] = []
    
    return render_template(
        f'pages/automation/partials/_stage_{stage_name}.html',
        **context,
    )


# ---------------------------------------------------------------------------
# API endpoints for pipeline orchestration
# ---------------------------------------------------------------------------


@automation_bp.route('/api/pipeline/start', methods=['POST'])
def api_start_pipeline():
    """
    Start a new automation pipeline.
    
    Request body:
    {
        "config": {
            "generation": {
                "mode": "generate" | "existing",
                "models": ["openai_gpt-4", ...],      // For generate mode
                "templates": ["crud_todo_list", ...], // For generate mode
                "existingApps": [{"model": "...", "app": 1}, ...],  // For existing mode
                "options": {...}
            },
            "analysis": {
                "enabled": true,
                "profile": "comprehensive",
                "tools": [...],
                "parallel": true,
                "maxConcurrentTasks": 2,
                "autoStartContainers": true,
                "options": {...}
            }
        },
        "name": "Optional pipeline name"
    }
    """
    try:
        data = request.get_json() or {}
        config = data.get('config', {})
        name = data.get('name', '')
        
        # Validate configuration
        gen_config = config.get('generation', {})
        generation_mode = gen_config.get('mode', 'generate')
        
        if generation_mode == 'existing':
            # Existing apps mode - need at least one app selected
            if not gen_config.get('existingApps'):
                return jsonify({
                    'success': False,
                    'error': 'Please select at least one existing app'
                }), 400
        else:
            # Generate mode - need models and templates
            if not gen_config.get('models') or not gen_config.get('templates'):
                return jsonify({
                    'success': False,
                    'error': 'Generation requires at least one model and one template'
                }), 400
        
        # Create pipeline execution in database
        pipeline = PipelineExecution(
            user_id=current_user.id,
            config=config,
            name=name or None,
        )
        db.session.add(pipeline)
        
        # Start the pipeline
        pipeline.start()
        db.session.commit()
        
        current_app.logger.info(
            f"Started automation pipeline {pipeline.pipeline_id} with "
            f"{pipeline.progress['generation']['total']} generation jobs"
        )
        
        return jsonify({
            'success': True,
            'pipeline_id': pipeline.pipeline_id,
            'message': f"Pipeline started with {pipeline.progress['generation']['total']} generation jobs",
            'data': pipeline.to_dict(),
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error starting pipeline: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@automation_bp.route('/api/pipeline/<pipeline_id>/status', methods=['GET'])
def api_pipeline_status(pipeline_id: str):
    """Get pipeline status from database."""
    try:
        # Get pipeline from database (no debug logging - this endpoint is polled frequently)
        pipeline = PipelineExecution.get_by_id(pipeline_id, user_id=current_user.id)
        
        if not pipeline:
            return jsonify({
                'success': False,
                'error': 'Pipeline not found',
            }), 404
        
        return jsonify({
            'success': True,
            'data': pipeline.to_dict(),
        })
        
    except Exception as e:
        current_app.logger.exception(f"Error getting pipeline status: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@automation_bp.route('/api/pipeline/<pipeline_id>/detailed-status', methods=['GET'])
def api_pipeline_detailed_status(pipeline_id: str):
    """
    Get detailed pipeline status including individual task statuses.
    
    Returns:
        - Pipeline basic info (id, status, progress)
        - Generation jobs with status
        - Analysis tasks with detailed status from DB
        - Task summary (completed, running, failed counts)
    """
    try:
        # AnalysisTask already imported at module level from app.models
        # AnalysisStatus already imported at module level from app.constants
        
        # Get pipeline from database
        pipeline = PipelineExecution.get_by_id(pipeline_id, user_id=current_user.id)
        
        if not pipeline:
            return jsonify({
                'success': False,
                'error': 'Pipeline not found',
            }), 404
        
        # Get base pipeline data
        base_data = pipeline.to_dict()
        progress = pipeline.progress
        config = pipeline.config
        
        # Build generation jobs list from progress results
        gen_results = progress.get('generation', {}).get('results', [])
        generation_jobs = []
        for idx, result in enumerate(gen_results):
            generation_jobs.append({
                'index': idx,
                'model_slug': result.get('model_slug'),
                'template_slug': result.get('template_slug'),
                'app_number': result.get('app_number') or result.get('app_num'),
                'success': result.get('success', False),
                'error': result.get('error'),
            })
        
        # If using existing apps mode, build from config
        gen_config = config.get('generation', {})
        if gen_config.get('mode') == 'existing':
            existing_apps = gen_config.get('existingApps', [])
            generation_jobs = []
            for idx, app_ref in enumerate(existing_apps):
                if isinstance(app_ref, dict):
                    generation_jobs.append({
                        'index': idx,
                        'model_slug': app_ref.get('model'),
                        'app_number': app_ref.get('app'),
                        'success': True,  # Existing apps always "generated"
                    })
                else:
                    parts = app_ref.rsplit(':', 1)
                    generation_jobs.append({
                        'index': idx,
                        'model_slug': parts[0] if len(parts) > 0 else app_ref,
                        'app_number': int(parts[1]) if len(parts) > 1 else None,
                        'success': True,
                    })
        
        # Get analysis tasks from database
        analysis_progress = progress.get('analysis', {})
        task_ids = analysis_progress.get('task_ids', [])
        
        analysis_tasks = []
        all_tasks = []
        task_summary = {'completed': 0, 'running': 0, 'failed': 0, 'pending': 0}
        
        if task_ids:
            # Filter out error/skipped markers and get real tasks
            real_task_ids = [tid for tid in task_ids if not tid.startswith('skipped') and not tid.startswith('error:')]
            
            if real_task_ids:
                tasks = AnalysisTask.query.filter(AnalysisTask.task_id.in_(real_task_ids)).all()
                
                for task in tasks:
                    task_data = {
                        'task_id': task.task_id,
                        'task_name': task.task_name or task.task_id[:16],
                        'target_model': task.target_model,
                        'target_app_number': task.target_app_number,
                        'status': task.status.value if hasattr(task.status, 'value') else str(task.status),
                        'progress_percentage': task.progress_percentage or 0,
                        'service_name': task.service_name,
                        'error_message': task.error_message,
                        'created_at': task.created_at.isoformat() if task.created_at else None,
                        'started_at': task.started_at.isoformat() if task.started_at else None,
                        'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                        'actual_duration': task.actual_duration,
                    }
                    analysis_tasks.append(task_data)
                    all_tasks.append(task_data)
                    
                    # Count by status
                    status_lower = task_data['status'].lower()
                    if status_lower == 'completed' or status_lower == 'partial_success':
                        task_summary['completed'] += 1
                    elif status_lower == 'running':
                        task_summary['running'] += 1
                    elif status_lower in ('failed', 'cancelled'):
                        task_summary['failed'] += 1
                    else:
                        task_summary['pending'] += 1
            
            # Add skipped/error markers
            for tid in task_ids:
                if tid.startswith('skipped') or tid.startswith('error:'):
                    analysis_tasks.append({
                        'task_id': tid,
                        'task_name': tid,
                        'status': 'skipped' if tid.startswith('skipped') else 'failed',
                        'error_message': tid.replace('error:', '').replace('skipped:', ''),
                    })
                    task_summary['failed'] += 1
        
        # Build response
        response_data = {
            **base_data,
            'generation_jobs': generation_jobs,
            'analysis_tasks': analysis_tasks,
            'all_tasks': all_tasks,
            'task_summary': task_summary,
        }
        
        return jsonify({
            'success': True,
            'data': response_data,
        })
        
    except Exception as e:
        current_app.logger.exception(f"Error getting detailed pipeline status: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@automation_bp.route('/api/pipeline/<pipeline_id>/execute-stage', methods=['POST'])
def api_execute_stage(pipeline_id: str):
    """
    Execute the next stage in the pipeline.
    
    Request body:
    {
        "stage": "generation|analysis|reports",
        "job_index": 0  // For generation/analysis, which job to execute
    }
    """
    try:
        from flask import session
        data = request.get_json() or {}
        stage = data.get('stage', 'generation')
        job_index = data.get('job_index', 0)
        
        pipelines = session.get('automation_pipelines', {})
        pipeline = pipelines.get(pipeline_id)
        
        if not pipeline:
            return jsonify({'success': False, 'error': 'Pipeline not found'}), 404
        
        config = pipeline.get('config', {})
        progress = pipeline.get('progress', {})
        
        result = {'success': True, 'message': 'Stage executed'}
        
        if stage == 'generation':
            result = _execute_generation_job(pipeline_id, pipeline, config, job_index)
        elif stage == 'analysis':
            result = _execute_analysis_job(pipeline_id, pipeline, config, job_index)
        # Reports stage removed - reports are now generated separately via Reports module
        
        # Update session
        session['automation_pipelines'][pipeline_id] = pipeline
        session.modified = True
        
        return jsonify(result)
        
    except Exception as e:
        current_app.logger.exception(f"Error executing stage: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


def _execute_generation_job(pipeline_id: str, pipeline: Dict, config: Dict, job_index: int) -> Dict:
    """Execute a single generation job within the pipeline.

    Generates one model-template combination based on the job index.
    Automatically determines the next available app number and creates
    the application using the generation service.

    Args:
        pipeline_id: Unique identifier for the pipeline execution
        pipeline: Pipeline state dict containing progress tracking
        config: Pipeline configuration with generation settings
        job_index: Job number to execute (determines model/template pair)

    Returns:
        Dict with success status, message, and generation result data
    """
    gen_config = config.get('generation', {})
    models = gen_config.get('models', [])
    templates = gen_config.get('templates', [])
    
    if not models or not templates:
        return {'success': False, 'error': 'No models or templates configured'}
    
    # Calculate which model/template combo this job is
    num_templates = len(templates)
    model_idx = job_index // num_templates
    template_idx = job_index % num_templates
    
    if model_idx >= len(models):
        return {'success': False, 'error': 'Job index out of range'}
    
    model_slug = models[model_idx]
    template_slug = templates[template_idx]
    
    try:
        svc = _get_generation_service()
        
        # Generate application
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Get next app number for this model
            from app.models import GeneratedApplication
            max_app = GeneratedApplication.query.filter_by(
                model_slug=model_slug
            ).order_by(
                GeneratedApplication.app_number.desc()
            ).first()
            app_num = (max_app.app_number + 1) if max_app else 1
            
            gen_result = loop.run_until_complete(
                svc.generate_full_app(
                    model_slug=model_slug,
                    app_num=app_num,
                    template_slug=template_slug,
                )
            )
        finally:
            loop.close()
        
        # Update progress
        progress = pipeline['progress']['generation']
        progress['completed'] += 1
        progress['results'].append({
            'model_slug': model_slug,
            'template_slug': template_slug,
            'app_number': gen_result.get('app_number'),
            'success': gen_result.get('success', True),
        })
        progress['status'] = 'running'
        
        if progress['completed'] + progress['failed'] >= progress['total']:
            progress['status'] = 'completed'
            pipeline['stage'] = 'analysis'
        
        return {
            'success': True,
            'message': f'Generated {model_slug} with {template_slug}',
            'data': gen_result,
        }
        
    except Exception as e:
        progress = pipeline['progress']['generation']
        progress['failed'] += 1
        progress['results'].append({
            'model_slug': model_slug,
            'template_slug': template_slug,
            'success': False,
            'error': str(e),
        })
        
        if progress['completed'] + progress['failed'] >= progress['total']:
            progress['status'] = 'completed'
            pipeline['stage'] = 'analysis'
        
        return {'success': False, 'error': str(e)}


def _execute_analysis_job(pipeline_id: str, pipeline: Dict, config: Dict, job_index: int) -> Dict:
    """Execute a single analysis job for a generated app.

    Analyzes a previously generated application using the configured analyzers.
    Automatically starts analyzer containers if configured to do so on the first job.
    Skips analysis for applications that failed to generate.

    Args:
        pipeline_id: Unique identifier for the pipeline execution
        pipeline: Pipeline state dict containing generation results and progress
        config: Pipeline configuration with analysis settings
        job_index: Job number to execute (corresponds to generation result index)

    Returns:
        Dict with success status, message, and analysis task information
    """
    analysis_config = config.get('analysis', {})
    
    if not analysis_config.get('enabled', True):
        return {'success': True, 'message': 'Analysis skipped'}
    
    # Check if we need to auto-start containers (only on first analysis job)
    analysis_options = analysis_config.get('options', {})
    if job_index == 0 and analysis_options.get('autoStartContainers', False):
        container_check_result = _ensure_analyzer_containers_running()
        if not container_check_result.get('success'):
            return {
                'success': False,
                'error': f"Container startup failed: {container_check_result.get('error', 'Unknown error')}. Analysis aborted."
            }
    
    # Get the generated app from generation results
    gen_results = pipeline['progress']['generation'].get('results', [])
    
    if job_index >= len(gen_results):
        return {'success': False, 'error': 'Job index out of range'}
    
    gen_result = gen_results[job_index]
    
    if not gen_result.get('success'):
        # Skip analysis for failed generations
        progress = pipeline['progress']['analysis']
        progress['failed'] += 1
        if progress['completed'] + progress['failed'] >= progress['total']:
            progress['status'] = 'completed'
            pipeline['stage'] = 'done'
            pipeline['status'] = 'completed'
        return {'success': True, 'message': 'Skipped - generation failed'}
    
    model_slug = gen_result.get('model_slug')
    app_number = gen_result.get('app_number')
    
    if not model_slug or not app_number:
        return {'success': False, 'error': 'Missing model_slug or app_number'}
    
    try:
        from app.services.task_service import AnalysisTaskService
        from app.engines.container_tool_registry import get_container_tool_registry
        
        # Get tools
        profile = analysis_config.get('profile', 'comprehensive')
        tools = analysis_config.get('tools', [])
        
        if not tools:
            # Default tools based on profile
            registry = get_container_tool_registry()
            all_tools = registry.get_all_tools()
            tools = [t.name for t in all_tools.values() if t.available]
        
        # Build container management options for the task
        container_management = {}
        if analysis_options.get('autoStartContainers', False):
            container_management = {
                'start_before_analysis': True,
                'build_if_missing': True,
                'stop_after_analysis': analysis_options.get('stopAfterAnalysis', True),  # Default to cleanup
            }
        
        # Create analysis task
        task = AnalysisTaskService.create_task(
            model_slug=model_slug,
            app_number=app_number,
            tools=tools,
            priority='normal',
            custom_options={
                'source': 'automation_pipeline',
                'pipeline_id': pipeline_id,
                'container_management': container_management,
            },
        )
        
        # Update progress
        progress = pipeline['progress']['analysis']
        progress['completed'] += 1
        progress['task_ids'].append(task.task_id)
        progress['status'] = 'running'
        
        if progress['completed'] + progress['failed'] >= progress['total']:
            progress['status'] = 'completed'
            pipeline['stage'] = 'done'
            pipeline['status'] = 'completed'
        
        return {
            'success': True,
            'message': f'Created analysis task {task.task_id}',
            'data': {'task_id': task.task_id},
        }
        
    except Exception as e:
        progress = pipeline['progress']['analysis']
        progress['failed'] += 1
        
        if progress['completed'] + progress['failed'] >= progress['total']:
            progress['status'] = 'completed'
            pipeline['stage'] = 'done'
            pipeline['status'] = 'completed'
        
        return {'success': False, 'error': str(e)}


def _ensure_analyzer_containers_running() -> Dict[str, Any]:
    """
    Check if analyzer containers are running and healthy.
    If not running, attempt to start them.
    
    Returns:
        Dict with 'success' (bool) and 'error' (str) if failed
    """
    import sys
    import time
    from pathlib import Path
    from flask import current_app
    
    try:
        # Add project root to path (src/app -> src -> project_root)
        project_root = Path(current_app.root_path).parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        
        from analyzer.analyzer_manager import AnalyzerManager
        
        manager = AnalyzerManager()
        
        # Check current status
        containers = manager.get_container_status()
        
        all_running = all(
            c.get('state') == 'running' 
            for c in containers.values()
        ) if containers else False
        
        # Check port accessibility
        all_ports_accessible = all(
            manager.check_port_accessibility(_get_analyzer_host(service_name), service_info.port)
            for service_name, service_info in manager.services.items()
        )
        
        # If already healthy, return success
        if all_running and all_ports_accessible:
            current_app.logger.info("[CONTAINER] Analyzer containers already running and healthy")
            return {'success': True, 'message': 'Containers already running'}
        
        # Need to start containers
        current_app.logger.info("[CONTAINER] Starting analyzer containers...")
        
        success = manager.start_services()
        
        if not success:
            return {
                'success': False,
                'error': 'Failed to start analyzer containers'
            }
        
        # Wait for containers to become healthy (max 90 seconds)
        max_wait = 90
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            # Check port accessibility
            all_accessible = all(
                manager.check_port_accessibility(_get_analyzer_host(service_name), service_info.port)
                for service_name, service_info in manager.services.items()
            )
            
            if all_accessible:
                current_app.logger.info("[CONTAINER] All analyzer containers are healthy")
                return {'success': True, 'message': 'Containers started successfully'}
            
            time.sleep(3)
        
        # Timeout - check final status
        final_containers = manager.get_container_status()
        running_count = sum(1 for c in final_containers.values() if c.get('state') == 'running')
        
        if running_count >= len(manager.services):
            # All running but ports not accessible - might just need more time
            current_app.logger.warning("[CONTAINER] Containers running but ports may not be fully accessible yet")
            return {'success': True, 'message': 'Containers started (ports warming up)'}
        
        return {
            'success': False,
            'error': f'Timeout waiting for containers to become healthy. {running_count}/{len(manager.services)} running.'
        }
        
    except Exception as e:
        current_app.logger.exception(f"[CONTAINER] Error managing containers: {e}")
        return {'success': False, 'error': str(e)}


@automation_bp.route('/api/pipeline/<pipeline_id>/cancel', methods=['POST'])
def api_cancel_pipeline(pipeline_id: str):
    """Cancel a running pipeline."""
    try:
        # Get pipeline from database
        pipeline = PipelineExecution.get_by_id(pipeline_id, user_id=current_user.id)
        
        if not pipeline:
            return jsonify({'success': False, 'error': 'Pipeline not found'}), 404
        
        # Cancel the pipeline
        pipeline.cancel()
        db.session.commit()
        
        # Cancel any pending analysis tasks associated with this pipeline
        task_ids = pipeline.progress.get('analysis', {}).get('task_ids', [])
        for task_id in task_ids:
            try:
                from app.services.task_service import AnalysisTaskService
                AnalysisTaskService.cancel_task(task_id)
            except Exception:
                pass
        
        return jsonify({
            'success': True,
            'message': 'Pipeline cancelled',
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error cancelling pipeline: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ---------------------------------------------------------------------------
# Pipeline History API endpoints
# ---------------------------------------------------------------------------


@automation_bp.route('/api/pipelines', methods=['GET'])
def api_list_pipelines():
    """List all pipelines for the current user."""
    try:
        limit = request.args.get('limit', 20, type=int)
        pipelines = PipelineExecution.get_user_pipelines(current_user.id, limit=limit)
        return jsonify({
            'success': True,
            'data': [p.to_dict() for p in pipelines],
        })
    except Exception as e:
        current_app.logger.exception(f"Error listing pipelines: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@automation_bp.route('/api/pipelines/active', methods=['GET'])
def api_get_active_pipeline():
    """Get the currently active (running) pipeline for the user."""
    try:
        pipeline = PipelineExecution.query.filter_by(
            user_id=current_user.id,
            status=PipelineExecutionStatus.RUNNING
        ).order_by(PipelineExecution.created_at.desc()).first()
        
        if not pipeline:
            return jsonify({
                'success': True,
                'data': None,
                'message': 'No active pipeline',
            })
        
        return jsonify({
            'success': True,
            'data': pipeline.to_dict(),
        })
    except Exception as e:
        current_app.logger.exception(f"Error getting active pipeline: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ---------------------------------------------------------------------------
# Pipeline Settings API endpoints
# ---------------------------------------------------------------------------


@automation_bp.route('/api/settings', methods=['GET'])
def api_list_settings():
    """List all saved pipeline settings for the current user."""
    try:
        settings = PipelineSettings.get_user_settings(current_user.id)
        return jsonify({
            'success': True,
            'data': [s.to_dict() for s in settings],
        })
    except Exception as e:
        current_app.logger.exception(f"Error listing settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@automation_bp.route('/api/settings', methods=['POST'])
def api_create_settings():
    """Create new pipeline settings."""
    try:
        data = request.get_json() or {}
        
        name = data.get('name', '').strip()
        if not name:
            return jsonify({'success': False, 'error': 'Name is required'}), 400
        
        description = data.get('description', '').strip() or None
        config = data.get('config', {})
        is_default = data.get('is_default', False)
        
        # Create the settings
        settings = PipelineSettings(
            user_id=current_user.id,
            name=name,
            config=config,
            description=description,
        )
        
        db.session.add(settings)
        db.session.commit()
        
        # Set as default if requested
        if is_default:
            settings.set_as_default()
        
        return jsonify({
            'success': True,
            'data': settings.to_dict(),
            'message': 'Settings saved successfully',
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error creating settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@automation_bp.route('/api/settings/<int:settings_id>', methods=['GET'])
def api_get_settings(settings_id: int):
    """Get a specific pipeline settings by ID."""
    try:
        settings = PipelineSettings.get_by_id(settings_id, current_user.id)
        
        if not settings:
            return jsonify({'success': False, 'error': 'Settings not found'}), 404
        
        return jsonify({
            'success': True,
            'data': settings.to_dict(),
        })
        
    except Exception as e:
        current_app.logger.exception(f"Error getting settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@automation_bp.route('/api/settings/<int:settings_id>', methods=['PUT'])
def api_update_settings(settings_id: int):
    """Update existing pipeline settings."""
    try:
        settings = PipelineSettings.get_by_id(settings_id, current_user.id)
        
        if not settings:
            return jsonify({'success': False, 'error': 'Settings not found'}), 404
        
        data = request.get_json() or {}
        
        if 'name' in data:
            settings.name = data['name'].strip()
        if 'description' in data:
            settings.description = data['description'].strip() or None
        if 'config' in data:
            settings.update_config(data['config'])
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'data': settings.to_dict(),
            'message': 'Settings updated successfully',
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error updating settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@automation_bp.route('/api/settings/<int:settings_id>', methods=['DELETE'])
def api_delete_settings(settings_id: int):
    """Delete pipeline settings."""
    try:
        settings = PipelineSettings.get_by_id(settings_id, current_user.id)
        
        if not settings:
            return jsonify({'success': False, 'error': 'Settings not found'}), 404
        
        settings.delete()
        
        return jsonify({
            'success': True,
            'message': 'Settings deleted successfully',
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error deleting settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@automation_bp.route('/api/settings/<int:settings_id>/default', methods=['POST'])
def api_set_default_settings(settings_id: int):
    """Set pipeline settings as default."""
    try:
        settings = PipelineSettings.get_by_id(settings_id, current_user.id)
        
        if not settings:
            return jsonify({'success': False, 'error': 'Settings not found'}), 404
        
        settings.set_as_default()
        
        return jsonify({
            'success': True,
            'message': 'Settings set as default',
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error setting default: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@automation_bp.route('/api/tools', methods=['GET'])
def api_get_tools():
    """
    Get available analysis tools grouped by category.
    
    Returns:
    {
        "success": true,
        "tools": {
            "static": [...],
            "dynamic": [...],
            "performance": [...],
            "ai": [...]
        }
    }
    """
    try:
        from app.engines.container_tool_registry import get_container_tool_registry, AnalyzerContainer
        
        registry = get_container_tool_registry()
        all_tools = registry.get_all_tools()
        
        # Map container enum to category name
        container_to_category = {
            AnalyzerContainer.STATIC: 'static',
            AnalyzerContainer.DYNAMIC: 'dynamic',
            AnalyzerContainer.PERFORMANCE: 'performance',
            AnalyzerContainer.AI: 'ai',
        }
        
        # Group tools by category
        tools_by_category = {
            'static': [],
            'dynamic': [],
            'performance': [],
            'ai': [],
        }
        
        for tool in all_tools.values():
            category = container_to_category.get(tool.container, 'static')
            tool_data = {
                'name': tool.name,
                'display_name': tool.display_name,
                'description': tool.description,
                'available': tool.available,
                'category': category,
            }
            tools_by_category[category].append(tool_data)
        
        return jsonify({
            'success': True,
            'tools': tools_by_category,
        })
        
    except ImportError as e:
        current_app.logger.warning(f"Container tool registry not available: {e}")
        # Return empty tools if registry not available
        return jsonify({
            'success': True,
            'tools': {
                'static': [],
                'dynamic': [],
                'performance': [],
                'ai': [],
            },
            'message': 'Tool registry not available',
        })
        
    except Exception as e:
        current_app.logger.exception(f"Error getting tools: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500

# ---------------------------------------------------------------------------
# Analyzer Container Management API
# ---------------------------------------------------------------------------


@automation_bp.route('/api/analyzer/status', methods=['GET'])
def api_analyzer_status():
    """
    Get status of all analyzer containers.
    
    Returns:
    {
        "success": true,
        "status": {
            "containers": {...},
            "ports": {...},
            "health": {...},
            "overall_healthy": bool,
            "all_running": bool
        }
    }
    """
    try:
        import sys
        from pathlib import Path
        
        # Add project root to path (src/app -> src -> project_root)
        project_root = Path(current_app.root_path).parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        
        from analyzer.analyzer_manager import AnalyzerManager
        
        manager = AnalyzerManager()
        
        # Get container status
        containers = manager.get_container_status()
        
        # Check port accessibility
        ports = {}
        for service_name, service_info in manager.services.items():
            ports[service_name] = {
                'port': service_info.port,
                'accessible': manager.check_port_accessibility(_get_analyzer_host(service_name), service_info.port)
            }
        
        # Calculate overall status
        all_running = all(
            c.get('state') == 'running' 
            for c in containers.values()
        ) if containers else False
        
        all_ports_accessible = all(p.get('accessible', False) for p in ports.values())
        
        return jsonify({
            'success': True,
            'status': {
                'containers': containers,
                'ports': ports,
                'all_running': all_running,
                'all_ports_accessible': all_ports_accessible,
                'overall_healthy': all_running and all_ports_accessible,
            }
        })
        
    except Exception as e:
        current_app.logger.exception(f"Error getting analyzer status: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@automation_bp.route('/api/analyzer/start', methods=['POST'])
def api_analyzer_start():
    """
    Start all analyzer containers.
    
    Request body (optional):
    {
        "wait_for_health": true  // Wait for health checks to pass
    }
    
    Returns:
    {
        "success": true,
        "message": "Analyzer containers started",
        "status": {...}
    }
    """
    try:
        import sys
        from pathlib import Path
        
        # Add project root to path (src/app -> src -> project_root)
        project_root = Path(current_app.root_path).parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        
        from analyzer.analyzer_manager import AnalyzerManager
        import time
        
        data = request.get_json() or {}
        wait_for_health = data.get('wait_for_health', True)
        
        manager = AnalyzerManager()
        
        current_app.logger.info("Starting analyzer containers...")
        
        # Start services
        success = manager.start_services()
        
        if not success:
            return jsonify({
                'success': False,
                'error': 'Failed to start analyzer containers'
            }), 500
        
        # Wait for health if requested
        if wait_for_health:
            max_wait = 60  # Maximum 60 seconds to wait
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                # Check if all ports are accessible
                all_accessible = True
                for service_name, service_info in manager.services.items():
                    if not manager.check_port_accessibility(_get_analyzer_host(service_name), service_info.port):
                        all_accessible = False
                        break
                
                if all_accessible:
                    break
                
                time.sleep(2)
            
            if not all_accessible:
                current_app.logger.warning("Not all analyzer ports accessible after waiting")
        
        # Get final status
        containers = manager.get_container_status()
        ports = {}
        for service_name, service_info in manager.services.items():
            ports[service_name] = {
                'port': service_info.port,
                'accessible': manager.check_port_accessibility(_get_analyzer_host(service_name), service_info.port)
            }
        
        all_running = all(
            c.get('state') == 'running' 
            for c in containers.values()
        ) if containers else False
        
        all_ports_accessible = all(p.get('accessible', False) for p in ports.values())
        
        return jsonify({
            'success': True,
            'message': 'Analyzer containers started',
            'status': {
                'containers': containers,
                'ports': ports,
                'all_running': all_running,
                'all_ports_accessible': all_ports_accessible,
                'overall_healthy': all_running and all_ports_accessible,
            }
        })
        
    except Exception as e:
        current_app.logger.exception(f"Error starting analyzer containers: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@automation_bp.route('/api/analyzer/health', methods=['GET'])
def api_analyzer_health():
    """
    Perform health checks on all analyzer containers.
    
    Returns:
    {
        "success": true,
        "health": {
            "static-analyzer": {"status": "healthy", ...},
            ...
        },
        "overall_healthy": bool
    }
    """
    try:
        import sys
        from pathlib import Path
        
        # Add project root to path (src/app -> src -> project_root)
        project_root = Path(current_app.root_path).parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        
        from analyzer.analyzer_manager import AnalyzerManager
        import asyncio
        
        manager = AnalyzerManager()
        
        # Run health checks
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            health_results = loop.run_until_complete(manager.check_all_services_health())
        finally:
            loop.close()
        
        # Determine overall health
        overall_healthy = all(
            h.get('status') == 'healthy' 
            for h in health_results.values()
        ) if health_results else False
        
        return jsonify({
            'success': True,
            'health': health_results,
            'overall_healthy': overall_healthy,
        })
        
    except Exception as e:
        current_app.logger.exception(f"Error checking analyzer health: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500