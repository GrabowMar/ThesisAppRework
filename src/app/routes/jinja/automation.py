"""Automation Pipeline Jinja Routes
=====================================

Web interface routes for the end-to-end automation system that
orchestrates: Sample Generation → Analysis → Report Generation
in a single unified workflow.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from flask import Blueprint, current_app, jsonify, render_template, flash, redirect, url_for, request, make_response
from flask_login import current_user

from app.services.generation import get_generation_service
from app.services.service_locator import ServiceLocator
from app.models import ModelCapability, GeneratedApplication, AnalysisTask, PipelineSettings
from app.constants import AnalysisStatus
from app.extensions import db

automation_bp = Blueprint('automation', __name__, url_prefix='/automation')


# Require authentication
@automation_bp.before_request
def require_authentication():
    """Require authentication for all automation endpoints."""
    if not current_user.is_authenticated:
        flash('Please log in to access the automation pipeline.', 'info')
        return redirect(url_for('auth.login', next=request.url))


def _get_generation_service():
    """Get generation service instance."""
    return get_generation_service()


def _get_report_service():
    """Get report generation service instance."""
    from app.services.report_generation_service import ReportGenerationService
    service_locator = ServiceLocator()
    service = service_locator.get_report_service()
    if service is None:
        # Initialize a new instance if not available via locator
        from flask import current_app
        service = ReportGenerationService(current_app)
    return service


def _build_status() -> Dict[str, Any]:
    """Build current automation status metrics."""
    try:
        svc = _get_generation_service()
        gen_status = svc.get_generation_status()
        
        # Get analysis task counts
        pending_tasks = AnalysisTask.query.filter_by(status=AnalysisStatus.PENDING).count()
        running_tasks = AnalysisTask.query.filter_by(status=AnalysisStatus.RUNNING).count()
        completed_tasks = AnalysisTask.query.filter(
            AnalysisTask.status.in_([AnalysisStatus.COMPLETED.value, AnalysisStatus.PARTIAL_SUCCESS.value])
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


@automation_bp.route('/')
def index():
    """Main automation pipeline interface."""
    status = _build_status()
    models = _load_available_models()
    templates = _load_available_templates()
    existing_apps = _load_existing_apps()
    saved_settings = _load_user_settings(current_user.id) if current_user.is_authenticated else []
    
    return render_template(
        'pages/automation/automation_main.html',
        status=status,
        models=models,
        templates=templates,
        existing_apps=existing_apps,
        saved_settings=saved_settings,
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


@automation_bp.route('/fragments/stage/<stage_name>')
def fragment_stage(stage_name: str):
    """Return stage configuration fragment."""
    valid_stages = ['generation', 'analysis', 'reports']
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
    elif stage_name == 'reports':
        context['report_types'] = ['app_analysis', 'model_comparison', 'tool_effectiveness']
        context['report_formats'] = ['html', 'json']
    
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
                "models": ["openai_gpt-4", ...],
                "templates": ["crud_todo_list", ...],
                "options": {...}
            },
            "analysis": {
                "enabled": true,
                "profile": "comprehensive",
                "tools": [...],
                "options": {...}
            },
            "reports": {
                "enabled": true,
                "types": ["app_analysis"],
                "format": "html",
                "options": {...}
            }
        }
    }
    """
    try:
        data = request.get_json() or {}
        config = data.get('config', {})
        
        # Validate configuration
        gen_config = config.get('generation', {})
        if not gen_config.get('models') or not gen_config.get('templates'):
            return jsonify({
                'success': False,
                'error': 'Generation requires at least one model and one template'
            }), 400
        
        # Generate pipeline ID
        import uuid
        pipeline_id = f"pipeline_{uuid.uuid4().hex[:12]}"
        
        # Calculate total jobs
        models = gen_config.get('models', [])
        templates = gen_config.get('templates', [])
        total_generation_jobs = len(models) * len(templates)
        
        analysis_enabled = config.get('analysis', {}).get('enabled', True)
        reports_enabled = config.get('reports', {}).get('enabled', True)
        
        # Initialize pipeline state
        pipeline_state = {
            'id': pipeline_id,
            'status': 'running',
            'stage': 'generation',
            'config': config,
            'created_at': datetime.utcnow().isoformat(),
            'progress': {
                'generation': {
                    'total': total_generation_jobs,
                    'completed': 0,
                    'failed': 0,
                    'status': 'pending',
                    'results': [],
                },
                'analysis': {
                    'total': total_generation_jobs if analysis_enabled else 0,
                    'completed': 0,
                    'failed': 0,
                    'status': 'pending' if analysis_enabled else 'skipped',
                    'task_ids': [],
                },
                'reports': {
                    'total': 1 if reports_enabled else 0,
                    'completed': 0,
                    'failed': 0,
                    'status': 'pending' if reports_enabled else 'skipped',
                    'report_ids': [],
                },
            },
        }
        
        # Store pipeline state in session
        from flask import session
        if 'automation_pipelines' not in session:
            session['automation_pipelines'] = {}
        session['automation_pipelines'][pipeline_id] = pipeline_state
        session.modified = True
        
        current_app.logger.info(f"Started automation pipeline {pipeline_id} with {total_generation_jobs} generation jobs")
        
        return jsonify({
            'success': True,
            'pipeline_id': pipeline_id,
            'message': f'Pipeline started with {total_generation_jobs} generation jobs',
            'data': pipeline_state,
        }), 201
        
    except Exception as e:
        current_app.logger.exception(f"Error starting pipeline: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@automation_bp.route('/api/pipeline/<pipeline_id>/status', methods=['GET'])
def api_pipeline_status(pipeline_id: str):
    """Get pipeline status."""
    try:
        from flask import session
        pipelines = session.get('automation_pipelines', {})
        pipeline = pipelines.get(pipeline_id)
        
        if not pipeline:
            return jsonify({
                'success': False,
                'error': 'Pipeline not found',
            }), 404
        
        return jsonify({
            'success': True,
            'data': pipeline,
        })
        
    except Exception as e:
        current_app.logger.exception(f"Error getting pipeline status: {e}")
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
        elif stage == 'reports':
            result = _execute_reports_job(pipeline_id, pipeline, config)
        
        # Update session
        session['automation_pipelines'][pipeline_id] = pipeline
        session.modified = True
        
        return jsonify(result)
        
    except Exception as e:
        current_app.logger.exception(f"Error executing stage: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


def _execute_generation_job(pipeline_id: str, pipeline: Dict, config: Dict, job_index: int) -> Dict:
    """Execute a single generation job."""
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
    """Execute a single analysis job for a generated app."""
    analysis_config = config.get('analysis', {})
    
    if not analysis_config.get('enabled', True):
        return {'success': True, 'message': 'Analysis skipped'}
    
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
            pipeline['stage'] = 'reports'
        return {'success': True, 'message': 'Skipped - generation failed'}
    
    model_slug = gen_result.get('model_slug')
    app_number = gen_result.get('app_number')
    
    if not model_slug or not app_number:
        return {'success': False, 'error': 'Missing model_slug or app_number'}
    
    try:
        from app.services.task_service import AnalysisTaskService
        from app.engines.container_tool_registry import get_container_tool_registry
        
        # Get tools
        profile = analysis_config.get('profile', 'security')
        tools = analysis_config.get('tools', [])
        
        if not tools:
            # Default tools based on profile
            registry = get_container_tool_registry()
            all_tools = registry.get_all_tools()
            tools = [t.name for t in all_tools.values() if t.available]
        
        # Create analysis task
        task = AnalysisTaskService.create_task(
            model_slug=model_slug,
            app_number=app_number,
            tools=tools,
            priority='normal',
            custom_options={
                'source': 'automation_pipeline',
                'pipeline_id': pipeline_id,
            },
        )
        
        # Update progress
        progress = pipeline['progress']['analysis']
        progress['completed'] += 1
        progress['task_ids'].append(task.task_id)
        progress['status'] = 'running'
        
        if progress['completed'] + progress['failed'] >= progress['total']:
            progress['status'] = 'completed'
            pipeline['stage'] = 'reports'
        
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
            pipeline['stage'] = 'reports'
        
        return {'success': False, 'error': str(e)}


def _execute_reports_job(pipeline_id: str, pipeline: Dict, config: Dict) -> Dict:
    """Execute report generation job."""
    reports_config = config.get('reports', {})
    
    if not reports_config.get('enabled', True):
        return {'success': True, 'message': 'Reports skipped'}
    
    try:
        report_service = _get_report_service()
        
        report_types = reports_config.get('types', ['app_analysis'])
        report_format = reports_config.get('format', 'html')
        
        # Get app numbers from generation results
        gen_results = pipeline['progress']['generation'].get('results', [])
        successful_apps = [
            r for r in gen_results 
            if r.get('success') and r.get('app_number')
        ]
        
        if not successful_apps:
            return {'success': False, 'error': 'No successful generations to report on'}
        
        created_reports = []
        
        for report_type in report_types:
            # Create report config based on type
            if report_type == 'app_analysis':
                # Generate report for each app
                for app_result in successful_apps:
                    report_config = {
                        'model_slug': app_result.get('model_slug'),
                        'app_number': app_result.get('app_number'),
                    }
                    
                    report = report_service.generate_report(
                        report_type=report_type,
                        format=report_format,
                        config=report_config,
                        title=f"Automation Report - {app_result.get('model_slug')} App {app_result.get('app_number')}",
                        user_id=current_user.id if current_user.is_authenticated else None,
                    )
                    created_reports.append(report.report_id)
            else:
                # Model comparison or tool effectiveness
                report_config = {
                    'filter_models': list(set(r.get('model_slug') for r in successful_apps)),
                    'filter_apps': list(set(r.get('app_number') for r in successful_apps)),
                }
                
                report = report_service.generate_report(
                    report_type=report_type,
                    format=report_format,
                    config=report_config,
                    title=f"Automation {report_type.replace('_', ' ').title()}",
                    user_id=current_user.id if current_user.is_authenticated else None,
                )
                created_reports.append(report.report_id)
        
        # Update progress
        progress = pipeline['progress']['reports']
        progress['completed'] = 1
        progress['report_ids'] = created_reports
        progress['status'] = 'completed'
        
        pipeline['status'] = 'completed'
        pipeline['stage'] = 'done'
        
        return {
            'success': True,
            'message': f'Generated {len(created_reports)} reports',
            'data': {'report_ids': created_reports},
        }
        
    except Exception as e:
        progress = pipeline['progress']['reports']
        progress['failed'] = 1
        progress['status'] = 'failed'
        
        pipeline['status'] = 'failed'
        
        return {'success': False, 'error': str(e)}


@automation_bp.route('/api/pipeline/<pipeline_id>/cancel', methods=['POST'])
def api_cancel_pipeline(pipeline_id: str):
    """Cancel a running pipeline."""
    try:
        from flask import session
        pipelines = session.get('automation_pipelines', {})
        pipeline = pipelines.get(pipeline_id)
        
        if not pipeline:
            return jsonify({'success': False, 'error': 'Pipeline not found'}), 404
        
        pipeline['status'] = 'cancelled'
        session.modified = True
        
        # Cancel any pending analysis tasks
        task_ids = pipeline.get('progress', {}).get('analysis', {}).get('task_ids', [])
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
        current_app.logger.exception(f"Error cancelling pipeline: {e}")
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
