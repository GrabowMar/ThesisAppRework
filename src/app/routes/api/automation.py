"""Automation Pipeline API
==========================

Programmable API for the end-to-end automation pipeline.
Provides endpoints to start pipelines, inspect status, and manage
saved pipeline settings.
"""

from __future__ import annotations

import logging
import os
import sys
import time
import zipfile
import json
import shutil
from pathlib import Path
from datetime import datetime

from flask import Blueprint, current_app, request, send_file
from flask_login import current_user
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import AnalysisTask, PipelineExecution, PipelineExecutionStatus, PipelineSettings
from app.routes.api.common import api_error, api_success

logger = logging.getLogger(__name__)

automation_api_bp = Blueprint('automation_api', __name__, url_prefix='/automation')


def _get_analyzer_host(service_name: str) -> str:
    """Get the hostname for an analyzer service."""
    in_docker = os.environ.get('IN_DOCKER', '').lower() in ('true', '1', 'yes')
    if in_docker:
        return service_name
    return os.environ.get('ANALYZER_HOST', 'localhost')


# ---------------------------------------------------------------------------
# Pipeline orchestration
# ---------------------------------------------------------------------------


@automation_api_bp.route('/pipelines', methods=['POST'])
def api_start_pipeline():
    """Start a new automation pipeline."""
    try:
        data = request.get_json() or {}
        config = data.get('config', {})
        name = data.get('name', '')

        if not config:
            return api_error('config is required', 400)

        # Validate configuration
        gen_config = config.get('generation', {})
        generation_mode = gen_config.get('mode', 'generate')

        if generation_mode == 'existing':
            if not gen_config.get('existingApps'):
                return api_error('Please select at least one existing app', 400)
        else:
            if not gen_config.get('models') or not gen_config.get('templates'):
                return api_error('Generation requires at least one model and one template', 400)

        # If analysis is enabled and tools not specified, default to all available tools
        analysis_config = config.get('analysis', {})
        if analysis_config.get('enabled', True) and not analysis_config.get('tools'):
            try:
                from app.engines.container_tool_registry import get_container_tool_registry

                registry = get_container_tool_registry()
                all_tools = registry.get_all_tools()
                analysis_config['tools'] = [t.name for t in all_tools.values() if t.available]
                config['analysis'] = analysis_config
            except Exception:
                # If tool registry fails, keep tools empty to avoid blocking pipeline start
                pass

        pipeline = PipelineExecution(
            user_id=current_user.id,
            config=config,
            name=name or None,
        )
        db.session.add(pipeline)

        pipeline.start()
        db.session.commit()

        return api_success(
            data={
                'pipeline_id': pipeline.pipeline_id,
                'pipeline': pipeline.to_dict(),
            },
            message=f"Pipeline started with {pipeline.progress.get('generation', {}).get('total', 0)} generation jobs",
            status=201,
        )

    except Exception as exc:
        db.session.rollback()
        logger.exception("Error starting pipeline")
        return api_error(str(exc), 500)


@automation_api_bp.route('/pipelines/<pipeline_id>', methods=['GET'])
def api_pipeline_status(pipeline_id: str):
    """Get pipeline status by ID."""
    try:
        pipeline = PipelineExecution.get_by_id(pipeline_id, user_id=current_user.id)

        if not pipeline:
            return api_error('Pipeline not found', 404, error_type='NotFound')

        return api_success(data=pipeline.to_dict())

    except Exception as exc:
        logger.exception("Error getting pipeline status")
        return api_error(str(exc), 500)


@automation_api_bp.route('/pipelines/<pipeline_id>/details', methods=['GET'])
def api_pipeline_detailed_status(pipeline_id: str):
    """Get detailed pipeline status including analysis task details."""
    try:
        pipeline = PipelineExecution.get_by_id(pipeline_id, user_id=current_user.id)

        if not pipeline:
            return api_error('Pipeline not found', 404, error_type='NotFound')

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
                        'success': True,
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

                    status_lower = task_data['status'].lower()
                    if status_lower in ('completed', 'partial_success'):
                        task_summary['completed'] += 1
                    elif status_lower == 'running':
                        task_summary['running'] += 1
                    elif status_lower in ('failed', 'cancelled'):
                        task_summary['failed'] += 1
                    else:
                        task_summary['pending'] += 1

            for tid in task_ids:
                if tid.startswith('skipped') or tid.startswith('error:'):
                    analysis_tasks.append({
                        'task_id': tid,
                        'task_name': tid,
                        'status': 'skipped' if tid.startswith('skipped') else 'failed',
                        'error_message': tid.replace('error:', '').replace('skipped:', ''),
                    })
                    task_summary['failed'] += 1

        # Get activity events (newest first, limited to 50 for UI)
        events = progress.get('events', [])
        recent_events = events[-50:] if len(events) > 50 else events
        # Reverse to show newest first in UI
        recent_events = list(reversed(recent_events))

        response_data = {
            **base_data,
            'generation_jobs': generation_jobs,
            'analysis_tasks': analysis_tasks,
            'all_tasks': all_tasks,
            'task_summary': task_summary,
            'events': recent_events,
        }

        return api_success(data=response_data)

    except Exception as exc:
        logger.exception("Error getting detailed pipeline status")
        return api_error(str(exc), 500)


@automation_api_bp.route('/pipelines/<pipeline_id>/cancel', methods=['POST'])
def api_cancel_pipeline(pipeline_id: str):
    """Cancel a running pipeline."""
    try:
        pipeline = PipelineExecution.get_by_id(pipeline_id, user_id=current_user.id)

        if not pipeline:
            return api_error('Pipeline not found', 404, error_type='NotFound')

        pipeline.cancel()
        db.session.commit()

        task_ids = pipeline.progress.get('analysis', {}).get('task_ids', [])
        for task_id in task_ids:
            try:
                from app.services.task_service import AnalysisTaskService

                AnalysisTaskService.cancel_task(task_id)
            except Exception:
                continue

        return api_success(message='Pipeline cancelled')

    except Exception as exc:
        db.session.rollback()
        logger.exception("Error cancelling pipeline")
        return api_error(str(exc), 500)


@automation_api_bp.route('/pipelines', methods=['GET'])
def api_list_pipelines():
    """List pipelines for the current user."""
    try:
        limit = request.args.get('limit', 20, type=int)
        pipelines = PipelineExecution.get_user_pipelines(current_user.id, limit=limit)
        return api_success(data=[p.to_dict() for p in pipelines])
    except Exception as exc:
        logger.exception("Error listing pipelines")
        return api_error(str(exc), 500)


@automation_api_bp.route('/pipelines/active', methods=['GET'])
def api_get_active_pipeline():
    """Get currently active pipeline for the user."""
    try:
        pipeline = PipelineExecution.query.filter_by(
            user_id=current_user.id,
            status=PipelineExecutionStatus.RUNNING,
        ).order_by(PipelineExecution.created_at.desc()).first()

        if not pipeline:
            return api_success(data=None, message='No active pipeline')

        return api_success(data=pipeline.to_dict())

    except Exception as exc:
        logger.exception("Error getting active pipeline")
        return api_error(str(exc), 500)


# ---------------------------------------------------------------------------
# Pipeline settings
# ---------------------------------------------------------------------------


@automation_api_bp.route('/settings', methods=['GET'])
def api_list_settings():
    """List saved pipeline settings for the current user."""
    try:
        settings = PipelineSettings.get_user_settings(current_user.id)
        return api_success(data=[s.to_dict() for s in settings])
    except Exception as exc:
        logger.exception("Error listing settings")
        return api_error(str(exc), 500)


@automation_api_bp.route('/settings', methods=['POST'])
def api_create_settings():
    """Create new pipeline settings."""
    try:
        data = request.get_json() or {}

        name = data.get('name', '').strip()
        if not name:
            return api_error('Name is required', 400)

        description = data.get('description', '').strip() or None
        config = data.get('config', {})
        is_default = data.get('is_default', False)

        settings = PipelineSettings(
            user_id=current_user.id,
            name=name,
            config=config,
            description=description,
        )

        db.session.add(settings)
        db.session.commit()

        if is_default:
            settings.set_as_default()

        return api_success(data=settings.to_dict(), message='Settings saved successfully', status=201)

    except Exception as exc:
        db.session.rollback()
        logger.exception("Error creating settings")
        return api_error(str(exc), 500)


@automation_api_bp.route('/settings/<int:settings_id>', methods=['GET'])
def api_get_settings(settings_id: int):
    """Get pipeline settings by ID."""
    try:
        settings = PipelineSettings.get_by_id(settings_id, current_user.id)

        if not settings:
            return api_error('Settings not found', 404, error_type='NotFound')

        return api_success(data=settings.to_dict())

    except Exception as exc:
        logger.exception("Error getting settings")
        return api_error(str(exc), 500)


@automation_api_bp.route('/settings/<int:settings_id>', methods=['PUT'])
def api_update_settings(settings_id: int):
    """Update existing pipeline settings."""
    try:
        settings = PipelineSettings.get_by_id(settings_id, current_user.id)

        if not settings:
            return api_error('Settings not found', 404, error_type='NotFound')

        data = request.get_json() or {}

        if 'name' in data:
            settings.name = data['name'].strip()
        if 'description' in data:
            settings.description = data['description'].strip() or None
        if 'config' in data:
            settings.update_config(data['config'])

        db.session.commit()

        return api_success(data=settings.to_dict(), message='Settings updated successfully')

    except Exception as exc:
        db.session.rollback()
        logger.exception("Error updating settings")
        return api_error(str(exc), 500)


@automation_api_bp.route('/settings/<int:settings_id>', methods=['DELETE'])
def api_delete_settings(settings_id: int):
    """Delete pipeline settings."""
    try:
        settings = PipelineSettings.get_by_id(settings_id, current_user.id)

        if not settings:
            return api_error('Settings not found', 404, error_type='NotFound')

        settings.delete()

        return api_success(message='Settings deleted successfully')

    except Exception as exc:
        db.session.rollback()
        logger.exception("Error deleting settings")
        return api_error(str(exc), 500)


@automation_api_bp.route('/settings/<int:settings_id>/default', methods=['POST'])
def api_set_default_settings(settings_id: int):
    """Set pipeline settings as default."""
    try:
        settings = PipelineSettings.get_by_id(settings_id, current_user.id)

        if not settings:
            return api_error('Settings not found', 404, error_type='NotFound')

        settings.set_as_default()

        return api_success(message='Settings set as default')

    except Exception as exc:
        db.session.rollback()
        logger.exception("Error setting default settings")
        return api_error(str(exc), 500)


# ---------------------------------------------------------------------------
# Tools and analyzer containers
# ---------------------------------------------------------------------------


@automation_api_bp.route('/tools', methods=['GET'])
def api_get_tools():
    """Get available analysis tools grouped by category."""
    try:
        from app.engines.container_tool_registry import AnalyzerContainer, get_container_tool_registry

        registry = get_container_tool_registry()
        all_tools = registry.get_all_tools()

        container_to_category = {
            AnalyzerContainer.STATIC: 'static',
            AnalyzerContainer.DYNAMIC: 'dynamic',
            AnalyzerContainer.PERFORMANCE: 'performance',
            AnalyzerContainer.AI: 'ai',
        }

        tools_by_category = {
            'static': [],
            'dynamic': [],
            'performance': [],
            'ai': [],
        }

        for tool in all_tools.values():
            category = container_to_category.get(tool.container, 'static')
            tools_by_category[category].append({
                'name': tool.name,
                'display_name': tool.display_name,
                'description': tool.description,
                'available': tool.available,
                'category': category,
            })

        return api_success(data=tools_by_category)

    except ImportError as exc:
        logger.warning("Container tool registry not available: %s", exc)
        return api_success(
            data={'static': [], 'dynamic': [], 'performance': [], 'ai': []},
            message='Tool registry not available',
        )

    except Exception as exc:
        logger.exception("Error getting tools")
        return api_error(str(exc), 500)


@automation_api_bp.route('/capacity', methods=['GET'])
def api_get_capacity():
    """Get analysis concurrency capacity based on available replicas."""
    try:
        total_capacity = 0
        breakdown = {}
        
        # Check environment variables for replica URLs
        # Format: ws://host:port,ws://host2:port2,...
        env_vars = {
            'static': 'STATIC_ANALYZER_URLS', 
            'dynamic': 'DYNAMIC_ANALYZER_URLS',
            'performance': 'PERF_TESTER_URLS',
            'ai': 'AI_ANALYZER_URLS'
        }
        
        for key, env_var in env_vars.items():
            val = os.environ.get(env_var, '')
            if val:
                urls = [u for u in val.split(',') if u.strip()]
                count = len(urls)
            else:
                # Default to 1 if not specified (assuming standard single container)
                count = 1
            
            breakdown[key] = count
            total_capacity += count
            
        # Minimal sanity check
        if total_capacity < 1:
            total_capacity = 1

        return api_success(data={
            'total': total_capacity, 
            'breakdown': breakdown,
            'recommended_max': total_capacity  # Simple heuristic
        })

    except Exception as exc:
        logger.exception("Error calculating capacity")
        return api_error(str(exc), 500)


@automation_api_bp.route('/analyzer/status', methods=['GET'])
def api_analyzer_status():
    """Get status of analyzer containers."""
    try:
        project_root = Path(current_app.root_path).parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        from analyzer.analyzer_manager import AnalyzerManager

        manager = AnalyzerManager()

        containers = manager.get_container_status()

        ports = {}
        for service_name, service_info in manager.services.items():
            ports[service_name] = {
                'port': service_info.port,
                'accessible': manager.check_port_accessibility(_get_analyzer_host(service_name), service_info.port),
            }

        all_running = all(
            c.get('state') == 'running'
            for c in containers.values()
        ) if containers else False

        all_ports_accessible = all(p.get('accessible', False) for p in ports.values())

        return api_success(data={
            'containers': containers,
            'ports': ports,
            'all_running': all_running,
            'all_ports_accessible': all_ports_accessible,
            'overall_healthy': all_running and all_ports_accessible,
        })

    except Exception as exc:
        logger.exception("Error getting analyzer status")
        return api_error(str(exc), 500)


@automation_api_bp.route('/analyzer/start', methods=['POST'])
def api_analyzer_start():
    """Start analyzer containers."""
    try:
        project_root = Path(current_app.root_path).parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        from analyzer.analyzer_manager import AnalyzerManager

        data = request.get_json() or {}
        wait_for_health = data.get('wait_for_health', True)

        manager = AnalyzerManager()

        success = manager.start_services()
        if not success:
            return api_error('Failed to start analyzer containers', 500)

        if wait_for_health:
            max_wait = 60
            start_time = time.time()
            all_accessible = False

            while time.time() - start_time < max_wait:
                all_accessible = True
                for service_name, service_info in manager.services.items():
                    if not manager.check_port_accessibility(_get_analyzer_host(service_name), service_info.port):
                        all_accessible = False
                        break

                if all_accessible:
                    break

                time.sleep(2)

            if not all_accessible:
                logger.warning("Not all analyzer ports accessible after waiting")

        containers = manager.get_container_status()
        ports = {}
        for service_name, service_info in manager.services.items():
            ports[service_name] = {
                'port': service_info.port,
                'accessible': manager.check_port_accessibility(_get_analyzer_host(service_name), service_info.port),
            }

        all_running = all(
            c.get('state') == 'running'
            for c in containers.values()
        ) if containers else False

        all_ports_accessible = all(p.get('accessible', False) for p in ports.values())

        return api_success(
            data={
                'containers': containers,
                'ports': ports,
                'all_running': all_running,
                'all_ports_accessible': all_ports_accessible,
                'overall_healthy': all_running and all_ports_accessible,
            },
            message='Analyzer containers started',
        )

    except Exception as exc:
        logger.exception("Error starting analyzer containers")
        return api_error(str(exc), 500)


@automation_api_bp.route('/analyzer/health', methods=['GET'])
def api_analyzer_health():
    """Perform health checks on analyzer containers."""
    try:
        project_root = Path(current_app.root_path).parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        from analyzer.analyzer_manager import AnalyzerManager
        import asyncio

        manager = AnalyzerManager()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            health_results = loop.run_until_complete(manager.check_all_services_health())
        finally:
            loop.close()

        overall_healthy = all(
            h.get('status') == 'healthy'
            for h in health_results.values()
        ) if health_results else False

        return api_success(data={
            'health': health_results,
            'overall_healthy': overall_healthy,
        })

    except Exception as exc:
        logger.exception("Error checking analyzer health")
        return api_error(str(exc), 500)


# ---------------------------------------------------------------------------
# Results Import/Export
# ---------------------------------------------------------------------------


@automation_api_bp.route('/results/export', methods=['POST'])
def api_export_results():
    """Export results and generated apps to a ZIP file.

    Request body (optional filters):
    {
        "models": ["model_slug1", "model_slug2"],  // Optional: specific models
        "pipeline_id": "pipeline_xxx",              // Optional: specific pipeline
        "include_metadata": true,                   // Include export metadata (default: true)
        "include_apps": true,                       // Include generated app source code (default: true)
        "include_results": true                     // Include analysis results (default: true)
    }
    """
    try:
        data = request.get_json() or {}
        models_filter = data.get('models', [])
        pipeline_id = data.get('pipeline_id')
        include_metadata = data.get('include_metadata', True)
        include_apps = data.get('include_apps', True)
        include_results = data.get('include_results', True)

        # Get directories
        project_root = Path(current_app.root_path).parent.parent
        results_dir = project_root / 'results'
        apps_dir = project_root / 'generated' / 'apps'

        # Create temporary ZIP file
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        zip_filename = f'thesis_export_{timestamp}.zip'
        zip_path = project_root / zip_filename

        exported_results_count = 0
        exported_apps_count = 0
        exported_files = []

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Export analysis results
            if include_results and results_dir.exists():
                for model_dir in results_dir.iterdir():
                    if not model_dir.is_dir():
                        continue

                    model_slug = model_dir.name

                    # Apply model filter if specified
                    if models_filter and model_slug not in models_filter:
                        continue

                    # Iterate through app directories
                    for app_dir in model_dir.iterdir():
                        if not app_dir.is_dir():
                            continue

                        # Iterate through task directories
                        for task_dir in app_dir.iterdir():
                            if not task_dir.is_dir():
                                continue

                            # Add all files in task directory
                            for file_path in task_dir.rglob('*'):
                                if file_path.is_file():
                                    # Calculate relative path for ZIP structure
                                    rel_path = file_path.relative_to(results_dir)
                                    zipf.write(file_path, arcname=f'results/{rel_path}')
                                    exported_results_count += 1

                                    if include_metadata:
                                        exported_files.append(f'results/{rel_path}')

            # Export generated apps source code
            if include_apps and apps_dir.exists():
                for model_dir in apps_dir.iterdir():
                    if not model_dir.is_dir():
                        continue

                    model_slug = model_dir.name

                    # Apply model filter if specified
                    if models_filter and model_slug not in models_filter:
                        continue

                    # Iterate through app directories
                    for app_dir in model_dir.iterdir():
                        if not app_dir.is_dir():
                            continue

                        # Add all files in app directory
                        for file_path in app_dir.rglob('*'):
                            if file_path.is_file():
                                # Skip certain directories to reduce size
                                skip_dirs = {'node_modules', '.venv', 'venv', '__pycache__', '.git',
                                           '.mypy_cache', '.pytest_cache', 'dist', 'build', '.eggs'}
                                if any(skip_dir in file_path.parts for skip_dir in skip_dirs):
                                    continue

                                # Calculate relative path for ZIP structure
                                rel_path = file_path.relative_to(apps_dir)
                                zipf.write(file_path, arcname=f'generated/apps/{rel_path}')
                                exported_apps_count += 1

                                if include_metadata:
                                    exported_files.append(f'generated/apps/{rel_path}')

            # Add metadata file
            if include_metadata:
                metadata = {
                    'export_timestamp': datetime.utcnow().isoformat(),
                    'export_user_id': current_user.id,
                    'export_version': '1.0',
                    'filters': {
                        'models': models_filter,
                        'pipeline_id': pipeline_id,
                    },
                    'options': {
                        'include_apps': include_apps,
                        'include_results': include_results,
                    },
                    'statistics': {
                        'total_files': exported_results_count + exported_apps_count,
                        'results_files': exported_results_count,
                        'apps_files': exported_apps_count,
                    },
                    'exported_files': exported_files[:100] if len(exported_files) > 100 else exported_files,  # Limit to first 100 for size
                }
                zipf.writestr('export_metadata.json', json.dumps(metadata, indent=2))

        # Send file and clean up
        response = send_file(
            zip_path,
            as_attachment=True,
            download_name=zip_filename,
            mimetype='application/zip',
        )
        
        # Clean up temporary ZIP file after response is sent
        @response.call_on_close
        def cleanup():
            try:
                if zip_path.exists():
                    zip_path.unlink()
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup export file {zip_path}: {cleanup_error}")
        
        return response

    except Exception as exc:
        logger.exception("Error exporting results")
        # Clean up ZIP file if it exists
        if 'zip_path' in locals() and zip_path.exists():
            zip_path.unlink()
        return api_error(str(exc), 500)


@automation_api_bp.route('/results/import', methods=['POST'])
def api_import_results():
    """Import results and generated apps from a ZIP file.

    Form data:
    - file: ZIP file containing results and/or apps
    - overwrite: "true" to overwrite existing results (default: false)
    - backup: "true" to backup existing data before import (default: true)
    """
    try:
        # Check if file is present
        if 'file' not in request.files:
            return api_error('No file provided', 400)

        file = request.files['file']
        if file.filename == '':
            return api_error('No file selected', 400)

        if not file.filename.endswith('.zip'):
            return api_error('File must be a ZIP archive', 400)

        overwrite = request.form.get('overwrite', 'false').lower() == 'true'
        backup = request.form.get('backup', 'true').lower() == 'true'

        # Get directories
        project_root = Path(current_app.root_path).parent.parent
        results_dir = project_root / 'results'
        apps_dir = project_root / 'generated' / 'apps'

        # Backup existing data if requested
        backup_paths = []
        if backup:
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')

            if results_dir.exists():
                backup_filename = f'results_backup_before_import_{timestamp}.tar.gz'
                backup_path = project_root / backup_filename
                logger.info(f"Creating results backup at {backup_path}")
                shutil.make_archive(
                    str(backup_path).replace('.tar.gz', ''),
                    'gztar',
                    root_dir=results_dir.parent,
                    base_dir=results_dir.name,
                )
                backup_paths.append(str(backup_path))

            if apps_dir.exists():
                backup_filename = f'apps_backup_before_import_{timestamp}.tar.gz'
                backup_path = project_root / backup_filename
                logger.info(f"Creating apps backup at {backup_path}")
                shutil.make_archive(
                    str(backup_path).replace('.tar.gz', ''),
                    'gztar',
                    root_dir=apps_dir.parent,
                    base_dir=apps_dir.name,
                )
                backup_paths.append(str(backup_path))

        # Save uploaded file temporarily
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        temp_zip = project_root / f'temp_import_{timestamp}.zip'
        file.save(temp_zip)

        imported_results_count = 0
        imported_apps_count = 0
        skipped_count = 0
        conflicts = []

        try:
            # Extract ZIP file
            with zipfile.ZipFile(temp_zip, 'r') as zipf:
                # Validate ZIP structure
                namelist = zipf.namelist()

                # Check for metadata file
                metadata = None
                if 'export_metadata.json' in namelist:
                    with zipf.open('export_metadata.json') as meta_file:
                        metadata = json.loads(meta_file.read())

                # Extract files
                for zip_info in zipf.infolist():
                    if zip_info.is_dir():
                        continue

                    # Skip metadata file
                    if zip_info.filename == 'export_metadata.json':
                        continue

                    # Determine target based on path prefix
                    target_path = None
                    is_result = False
                    is_app = False

                    if zip_info.filename.startswith('results/'):
                        rel_path = Path(zip_info.filename).relative_to('results')
                        target_path = results_dir / rel_path
                        is_result = True
                    elif zip_info.filename.startswith('generated/apps/'):
                        rel_path = Path(zip_info.filename).relative_to('generated/apps')
                        target_path = apps_dir / rel_path
                        is_app = True
                    else:
                        # Unknown file, skip
                        continue

                    # Check for conflicts
                    if target_path.exists() and not overwrite:
                        skipped_count += 1
                        conflicts.append(zip_info.filename)
                        continue

                    # Create parent directories
                    target_path.parent.mkdir(parents=True, exist_ok=True)

                    # Extract file
                    with zipf.open(zip_info) as source, open(target_path, 'wb') as target:
                        shutil.copyfileobj(source, target)

                    if is_result:
                        imported_results_count += 1
                    elif is_app:
                        imported_apps_count += 1

        finally:
            # Clean up temporary file
            temp_zip.unlink()

        imported_count = imported_results_count + imported_apps_count
        message = f'Imported {imported_count} files ({imported_results_count} results, {imported_apps_count} apps)'
        if skipped_count > 0:
            message += f', skipped {skipped_count} existing files'

        return api_success(
            data={
                'imported': imported_count,
                'imported_results': imported_results_count,
                'imported_apps': imported_apps_count,
                'skipped': skipped_count,
                'conflicts': conflicts[:10] if conflicts else [],  # Show first 10 conflicts
                'total_conflicts': len(conflicts),
                'metadata': metadata,
                'backup_paths': backup_paths,
            },
            message=message,
        )

    except Exception as exc:
        logger.exception("Error importing results")
        # Clean up temporary file if it exists
        if 'temp_zip' in locals() and temp_zip.exists():
            temp_zip.unlink()
        return api_error(str(exc), 500)
