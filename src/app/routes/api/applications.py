"""
Applications API Routes
=======================

API endpoints for application management and CRUD operations.
"""

import logging
from flask import request
from app.utils.template_paths import render_template_compat as render_template

from ..response_utils import (
    json_success, json_error, handle_exceptions,
    build_pagination_envelope, require_fields
)

from . import api_bp
from ...models import GeneratedApplication
from ...extensions import db
from ...constants import AnalysisStatus  # noqa: F401 (may be referenced indirectly or kept for future use)
from ...services import application_service as app_service
from ...services.service_locator import ServiceLocator
from ...utils.helpers import get_app_directory
from pathlib import Path
import json
import requests
from flask import Response

# Set up logger
logger = logging.getLogger(__name__)


@api_bp.route('/applications')
@handle_exceptions(logger_override=logger)
def api_list_applications():
    """API endpoint: Get applications (standardized envelope)."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status')
    app_type = request.args.get('type')

    query = app_service.list_applications(status=status, app_type=app_type)

    items, meta = build_pagination_envelope(query, page, per_page)
    return json_success(
        [app.to_dict() for app in items],
        message="Applications fetched",
        pagination=meta
    )


@api_bp.route('/applications', methods=['POST'])
@handle_exceptions(logger_override=logger)
def api_create_application():
    """API endpoint: Create application (standardized envelope)."""
    data = request.get_json() or {}
    missing = require_fields(data, ['model_slug', 'app_number', 'app_type', 'provider'])
    if missing:
        return json_error(f"Missing required fields: {', '.join(missing)}", status=400, error_type="ValidationError")

    try:
        created = app_service.create_application(data)
        return json_success(created, message="Application created", status=201)
    except app_service.ValidationError as ve:
        return json_error(str(ve), status=400, error_type='ValidationError')


@api_bp.route('/applications/<int:app_id>')
@handle_exceptions(logger_override=logger)
def api_get_application(app_id):
    """API endpoint: Get specific application (standardized)."""
    try:
        return json_success(app_service.get_application(app_id))
    except app_service.NotFoundError:
        return json_error('Application not found', status=404, error_type='NotFound')


@api_bp.route('/applications/<int:app_id>', methods=['PUT'])
@handle_exceptions(logger_override=logger)
def api_update_application(app_id):
    """API endpoint: Update application (standardized)."""
    data = request.get_json() or {}
    try:
        updated = app_service.update_application(app_id, data)
        return json_success(updated, message="Application updated")
    except app_service.NotFoundError:
        return json_error('Application not found', status=404, error_type='NotFound')


@api_bp.route('/applications/<int:app_id>', methods=['DELETE'])
@handle_exceptions(logger_override=logger)
def api_delete_application(app_id):
    """API endpoint: Delete application (standardized)."""
    try:
        app_service.delete_application(app_id)
        return json_success(message='Application deleted successfully')
    except app_service.NotFoundError:
        return json_error('Application not found', status=404, error_type='NotFound')


@api_bp.route('/applications/types')
@handle_exceptions(logger_override=logger)
def api_get_application_types():
    """API endpoint: Get available application types (standardized)."""
    types = (
        db.session.query(GeneratedApplication.app_type)
        .distinct()
        .filter(GeneratedApplication.app_type.isnot(None))
        .all()
    )
    type_list = [t[0] for t in types]
    common_types = [
        'web_app', 'api', 'microservice', 'dashboard',
        'e_commerce', 'blog', 'cms', 'social_media'
    ]
    for common_type in common_types:
        if common_type not in type_list:
            type_list.append(common_type)
    return json_success({'types': sorted(type_list)}, message='Application types fetched')


@api_bp.route('/applications/<int:app_id>/code')
@handle_exceptions(logger_override=logger)
def api_get_application_code(app_id):
    """API endpoint: Get application code/metadata (standardized)."""
    from app.extensions import get_session
    with get_session() as _s:
        app = _s.get(GeneratedApplication, app_id)
    if not app:
        return json_error('Application not found', status=404, error_type='NotFound')
    return json_success({
        'model_slug': app.model_slug,
        'app_number': app.app_number,
        'metadata': app.get_metadata(),
        'has_backend': app.has_backend,
        'has_frontend': app.has_frontend,
        'has_docker_compose': app.has_docker_compose,
        'backend_framework': app.backend_framework,
        'frontend_framework': app.frontend_framework
    }, message='Application code fetched')


@api_bp.route('/applications/<int:app_id>/status', methods=['PATCH'])
@handle_exceptions(logger_override=logger)
def api_update_application_status(app_id):
    """API endpoint: Update application status (standardized)."""
    from app.extensions import get_session
    with get_session() as _s:
        app = _s.get(GeneratedApplication, app_id)
    if not app:
        return json_error('Application not found', status=404, error_type='NotFound')
    data = request.get_json() or {}
    if 'generation_status' not in data and 'container_status' not in data:
        return json_error('generation_status or container_status is required', status=400, error_type='ValidationError')
    if 'generation_status' in data:
        app.generation_status = data['generation_status']
    if 'container_status' in data:
        valid_container_statuses = ['running', 'stopped', 'error', 'pending', 'building']
        if data['container_status'] not in valid_container_statuses:
            return json_error(f"Invalid container status. Must be one of: {valid_container_statuses}", status=400, error_type='ValidationError')
        app.container_status = data['container_status']
    db.session.commit()
    return json_success({
        'generation_status': str(app.generation_status) if app.generation_status else None,
        'container_status': app.container_status
    }, message='Application status updated')


# =================================================================
# APPLICATION CONTAINER MANAGEMENT
# =================================================================

@api_bp.route('/apps/grid')
def api_apps_grid():
    """API endpoint for applications grid view."""
    try:
        # Get query parameters
        search = request.args.get('search', '')
        model = request.args.get('model', '')
        status = request.args.get('status', '')
    # app_type placeholder for future filtering (currently unused)
        view = request.args.get('view', 'grid')
        page = request.args.get('page', 1, type=int)
        per_page = 12

        # Build query
        query = GeneratedApplication.query

        if search:
            query = query.filter(
                GeneratedApplication.model_slug.contains(search)
            )

        if model:
            query = query.filter(GeneratedApplication.model_slug == model)

        if status:
            query = query.filter(GeneratedApplication.generation_status == status)

        # Paginate
        apps = query.order_by(
            GeneratedApplication.created_at.desc()
        ).paginate(
            page=page, per_page=per_page, error_out=False
        )

        # Return appropriate template based on view
        # Use consolidated namespaced partials (apps_grid namespace)
        # Legacy root-level partials (partials/apps_list.html, partials/apps_grid.html)
        # are being deprecated in favor of the structured namespace.
        if view == 'list':
            return render_template('partials/apps_grid/apps_list.html', apps=apps.items if hasattr(apps, 'items') else apps)
        else:
            return render_template('partials/apps_grid/apps_grid.html', apps=apps.items if hasattr(apps, 'items') else apps)
    except Exception as e:
        logger.error(f"Error getting apps grid: {e}")
        return f'<div class="alert alert-danger">Error loading applications: {str(e)}</div>'


@api_bp.route('/applications/<int:app_id>/start', methods=['POST'])
def api_application_start(app_id):
    """API endpoint to start an application container (service-backed)."""
    try:
        result = app_service.start_application(app_id)
        return json_success(result, message=f'Application {app_id} started successfully')
    except app_service.NotFoundError:
        return json_error(f'Application {app_id} not found', status=404, error_type='NotFound')


@api_bp.route('/applications/<int:app_id>/stop', methods=['POST'])
def api_application_stop(app_id):
    """API endpoint to stop an application container (service-backed)."""
    try:
        result = app_service.stop_application(app_id)
        return json_success(result, message=f'Application {app_id} stopped successfully')
    except app_service.NotFoundError:
        return json_error(f'Application {app_id} not found', status=404, error_type='NotFound')


@api_bp.route('/applications/<int:app_id>/restart', methods=['POST'])
def api_application_restart(app_id):
    """API endpoint to restart an application container (service-backed)."""
    try:
        result = app_service.restart_application(app_id)
        return json_success(result, message=f'Application {app_id} restarted successfully')
    except app_service.NotFoundError:
        return json_error(f'Application {app_id} not found', status=404, error_type='NotFound')


# ================================================================
# BULK APPLICATION OPERATIONS (used by Applications index page)
# ================================================================

@api_bp.route('/applications/bulk/start', methods=['POST'])
def api_applications_bulk_start():
    """Start multiple applications by ID.

    Payload: { "app_ids": [1,2,3] }
    Returns: { success, started_count, errors }
    """
    try:
        data = request.get_json(silent=True) or {}
        ids = data.get('app_ids') or []
        if not isinstance(ids, list) or not ids:
            return json_error('app_ids must be a non-empty array', status=400, error_type='ValidationError')
        started = 0
        errors = []
        for app_id in ids:
            try:
                res = app_service.start_application(int(app_id))
                if res.get('success'):
                    started += 1
                else:
                    errors.append({'app_id': app_id, 'error': res})
            except Exception as e:  # noqa: BLE001
                errors.append({'app_id': app_id, 'error': str(e)})
        return json_success({'started_count': started, 'errors': errors}, message='Bulk start triggered')
    except Exception as e:  # noqa: BLE001
        logger.error(f"Bulk start error: {e}")
        return json_error(str(e), status=500, error_type='InternalError')


@api_bp.route('/applications/bulk/stop', methods=['POST'])
def api_applications_bulk_stop():
    """Stop multiple applications by ID.

    Payload: { "app_ids": [1,2,3] }
    Returns: { success, stopped_count, errors }
    """
    try:
        data = request.get_json(silent=True) or {}
        ids = data.get('app_ids') or []
        if not isinstance(ids, list) or not ids:
            return json_error('app_ids must be a non-empty array', status=400, error_type='ValidationError')
        stopped = 0
        errors = []
        for app_id in ids:
            try:
                res = app_service.stop_application(int(app_id))
                if res.get('success'):
                    stopped += 1
                else:
                    errors.append({'app_id': app_id, 'error': res})
            except Exception as e:  # noqa: BLE001
                errors.append({'app_id': app_id, 'error': str(e)})
        return json_success({'stopped_count': stopped, 'errors': errors}, message='Bulk stop triggered')
    except Exception as e:  # noqa: BLE001
        logger.error(f"Bulk stop error: {e}")
        return json_error(str(e), status=500, error_type='InternalError')


@api_bp.route('/applications/bulk/delete', methods=['POST'])
def api_applications_bulk_delete():
    """Delete multiple applications by ID.

    Payload: { "app_ids": [1,2,3] }
    Returns: { success, deleted_count, errors }
    """
    try:
        data = request.get_json(silent=True) or {}
        ids = data.get('app_ids') or []
        if not isinstance(ids, list) or not ids:
            return json_error('app_ids must be a non-empty array', status=400, error_type='ValidationError')
        deleted = 0
        errors = []
        for app_id in ids:
            try:
                app_service.delete_application(int(app_id))
                deleted += 1
            except app_service.NotFoundError:
                errors.append({'app_id': app_id, 'error': 'Not found'})
            except Exception as e:  # noqa: BLE001
                errors.append({'app_id': app_id, 'error': str(e)})
        return json_success({'deleted_count': deleted, 'errors': errors}, message='Bulk delete completed')
    except Exception as e:  # noqa: BLE001
        logger.error(f"Bulk delete error: {e}")
        return json_error(str(e), status=500, error_type='InternalError')


@api_bp.route('/applications/bulk/download')
def api_applications_bulk_download():
    """Download bundle for selected applications.

    Currently returns a JSON message placeholder to avoid 404 in UI.
    Consider implementing a ZIP stream of app metadata and logs.
    """
    try:
        ids_param = request.args.get('app_ids', '')
        ids = [int(x) for x in ids_param.split(',') if x.strip().isdigit()]
        if not ids:
            return json_error('app_ids query param required', status=400, error_type='ValidationError')
        # Placeholder response to keep UI functional; implement ZIP streaming later
        return json_success({'app_ids': ids}, message='Download packaging not implemented yet')
    except Exception as e:  # noqa: BLE001
        logger.error(f"Bulk download error: {e}")
        return json_error(str(e), status=500, error_type='InternalError')


@api_bp.route('/applications/<int:app_id>/details')
@handle_exceptions(logger_override=logger)
def api_application_details(app_id):
    """API endpoint to get application details (standardized)."""
    from app.extensions import get_session
    with get_session() as _s:
        app = _s.get(GeneratedApplication, app_id)
    if not app:
        return json_error(f'Application {app_id} not found', status=404, error_type='NotFound')
    return json_success({
        'id': app.id,
        'app_number': app.app_number,
        'model_slug': app.model_slug,
        'provider': app.provider,
        'container_status': app.container_status,
        'frontend_url': app.frontend_url,
        'backend_url': app.backend_url,
        'description': app.description,
        'backend_framework': app.backend_framework,
        'frontend_framework': app.frontend_framework,
        'created_at': app.created_at.isoformat() if app.created_at else None
    }, message='Application details fetched')


@api_bp.route('/applications/export')
def api_applications_export():
    """Placeholder endpoint for exporting applications list.

    In a future iteration this can stream a CSV/XLSX. For now, return a small HTML page
    indicating export is not yet implemented to avoid broken link.
    """
    try:
        return render_template('partials/common/info.html',
                               title='Export not implemented',
                               message='Export will be available in a future update.')
    except Exception:
        return json_success({'message': 'Export not implemented yet'})


@api_bp.route('/applications/cleanup', methods=['POST'])
def api_applications_cleanup():
    """Placeholder cleanup endpoint to keep UI action functional.

    Performs a no-op and returns success; real cleanup logic can be implemented
    in application_service later.
    """
    try:
        # Potentially call a service to prune unused rows/files in the future
        return json_success({'removed_count': 0}, message='Cleanup completed (no-op)')
    except Exception as e:  # noqa: BLE001
        logger.error(f"Cleanup error: {e}")
        return json_error(str(e), status=500, error_type='InternalError')


@api_bp.route('/applications/<int:app_id>/logs')
def api_application_logs_modal(app_id):
    """API endpoint to get application logs modal."""
    try:
        from app.extensions import get_session
        with get_session() as _s:
            app = _s.get(GeneratedApplication, app_id)
        if not app:
            return f'<div class="alert alert-warning">Application {app_id} not found</div>', 404
        
        # Mock logs for now - in production, this would read actual log files
        logs = [
            {'timestamp': '2025-01-11 03:35:00', 'level': 'INFO', 'message': f'Application {app_id} initialized'},
            {'timestamp': '2025-01-11 03:35:01', 'level': 'INFO', 'message': f'Model: {app.model_slug}'},
            {'timestamp': '2025-01-11 03:35:02', 'level': 'INFO', 'message': f'Provider: {app.provider}'},
            {'timestamp': '2025-01-11 03:35:03', 'level': 'INFO', 'message': 'Container started successfully'},
            {'timestamp': '2025-01-11 03:35:04', 'level': 'INFO', 'message': 'Application ready for analysis'}
        ]
        
        return render_template('partials/application_logs_modal.html', app=app, logs=logs)
    except Exception as e:
        logger.error(f"Error loading application logs modal: {e}")
        return f'<div class="alert alert-danger">Error loading logs: {str(e)}</div>', 500


@api_bp.route('/app/<model_slug>/<int:app_num>/logs')
def api_application_logs_modal_by_slug(model_slug, app_num):
    """API endpoint to get application logs modal by model slug and app number."""
    try:
        app = GeneratedApplication.query.filter_by(model_slug=model_slug, app_number=app_num).first()
        if not app:
            return f'<div class="alert alert-warning">Application {model_slug}/app{app_num} not found</div>', 404

        # Try real Docker logs via DockerManager
        docker = ServiceLocator.get_docker_manager()
        backend_logs = "Docker manager unavailable"
        frontend_logs = "Docker manager unavailable"
        backend_port = None
        frontend_port = None
        try:
            if docker is not None:  # type: ignore[truthy-bool]
                backend_logs = docker.get_container_logs(model_slug, app_num, 'backend', tail=200)  # type: ignore[attr-defined]
                frontend_logs = docker.get_container_logs(model_slug, app_num, 'frontend', tail=200)  # type: ignore[attr-defined]
        except Exception as log_err:  # noqa: BLE001
            logger.warning(f"Failed to fetch docker logs for {model_slug}/app{app_num}: {log_err}")

        # Resolve ports from database if available
        try:
            from ...models import PortConfiguration  # local import to avoid circulars
            pc = db.session.query(PortConfiguration).filter_by(model=model_slug, app_num=app_num).first()
            if pc:
                backend_port = pc.backend_port
                frontend_port = pc.frontend_port
        except Exception as e:
            logger.debug(f"Port lookup failed for {model_slug}/app{app_num}: {e}")

        # If ports still unknown, try to read misc/port_config.json directly
        if backend_port is None or frontend_port is None:
            try:
                # project root: src/app/routes/api -> src -> project
                proj_root = Path(__file__).resolve().parents[4]
                port_file = proj_root / 'misc' / 'port_config.json'
                if port_file.exists():
                    entries = json.loads(port_file.read_text(encoding='utf-8'))
                    for entry in entries:
                        if (entry.get('model_name') == model_slug and int(entry.get('app_number')) == int(app_num)):
                            backend_port = backend_port or int(entry.get('backend_port'))
                            frontend_port = frontend_port or int(entry.get('frontend_port'))
                            break
            except Exception as _json_port_err:
                logger.debug(f"JSON port config lookup failed: {_json_port_err}")

        # Fallback to filesystem logs under misc/models/<slug>/appN/_logs
        try:
            proj_root = Path(__file__).resolve().parents[4]
            app_dir = proj_root / 'misc' / 'models' / model_slug / f'app{app_num}'
            logs_dir = app_dir / '_logs'
            if logs_dir.exists():
                backend_log_path = None
                frontend_log_path = None
                # common names
                for name in ['backend.log', 'api.log', 'server.log']:
                    p = logs_dir / name
                    if p.exists():
                        backend_log_path = p
                        break
                for name in ['frontend.log', 'web.log', 'ui.log']:
                    p = logs_dir / name
                    if p.exists():
                        frontend_log_path = p
                        break
                try:
                    if backend_log_path:
                        backend_logs = backend_log_path.read_text(encoding='utf-8', errors='replace')[-10000:]
                except Exception:
                    pass
                try:
                    if frontend_log_path:
                        frontend_logs = frontend_log_path.read_text(encoding='utf-8', errors='replace')[-10000:]
                except Exception:
                    pass
        except Exception as _fs_err:
            logger.debug(f"Filesystem logs fallback failed: {_fs_err}")

        # Render rich modal with split backend/frontend panes
        return render_template(
            'partials/app_logs_modal.html',
            model_slug=model_slug,
            app_num=app_num,
            backend_logs=backend_logs or 'No backend logs available',
            frontend_logs=frontend_logs or 'No frontend logs available',
            backend_port=backend_port,
            frontend_port=frontend_port
        )
    except Exception as e:
        logger.error(f"Error loading application logs modal by slug for {model_slug}/app{app_num}: {e}")
        return f'<div class="alert alert-danger">Error loading logs: {str(e)}</div>', 500


@api_bp.route('/logs/application/<int:app_id>')
def api_application_logs(app_id):
    """API endpoint for application logs."""
    try:
        from app.extensions import get_session
        with get_session() as _s:
            app = _s.get(GeneratedApplication, app_id)
        if not app:
            return f'<div class="alert alert-warning">Application {app_id} not found</div>', 404
        
        # Mock logs for now - in production, this would read actual log files
        logs = [
            {'timestamp': '2025-08-11 03:35:00', 'level': 'INFO', 'message': f'Application {app_id} initialized'},
            {'timestamp': '2025-08-11 03:35:01', 'level': 'INFO', 'message': f'Model: {app.model_slug}'},
            {'timestamp': '2025-08-11 03:35:02', 'level': 'INFO', 'message': f'Provider: {app.provider}'},
            {'timestamp': '2025-08-11 03:35:03', 'level': 'INFO', 'message': 'Application ready for analysis'}
        ]
        
        return render_template('partials/application_logs.html', app=app, logs=logs)
    except Exception as e:
        logger.error(f"Error loading application logs: {e}")
        return f'<div class="alert alert-danger">Error loading logs: {str(e)}</div>', 500


# =================================================================
# MODEL-BASED APPLICATION ACTIONS (for frontend compatibility)
# =================================================================

@api_bp.route('/app/<model_slug>/<int:app_num>/start', methods=['POST'])
def start_app_by_model(model_slug, app_num):
    """Start application by model slug and app number."""
    try:
        # Leverage generic application start
        app = GeneratedApplication.query.filter_by(model_slug=model_slug, app_number=app_num).first()
        if not app:
            return json_error(f'Application {model_slug}/{app_num} not found', status=404, error_type='NotFound')
        docker = ServiceLocator.get_docker_manager()
        result = None
        if docker is not None:  # type: ignore[truthy-bool]
            # Attempt to start containers via docker-compose
            result = docker.start_containers(model_slug, app_num)  # type: ignore[attr-defined]
            if result.get('success'):
                app.container_status = 'running'
                db.session.commit()
        else:
            # Fallback to status-only if docker unavailable
            result = app_service.start_application(app.id)
        return json_success(result, message=f'Started {model_slug} app {app_num}')
    except Exception as e:  # noqa: BLE001 broad for last-resort logging
        logger.error(f"Error starting app {model_slug}/{app_num}: {e}")
        return json_error(str(e), status=500, error_type='InternalError')


@api_bp.route('/app/<model_slug>/<int:app_num>/stop', methods=['POST'])
def stop_app_by_model(model_slug, app_num):
    """Stop application by model slug and app number."""
    try:
        app = GeneratedApplication.query.filter_by(model_slug=model_slug, app_number=app_num).first()
        if not app:
            return json_error(f'Application {model_slug}/{app_num} not found', status=404, error_type='NotFound')
        docker = ServiceLocator.get_docker_manager()
        if docker is not None:  # type: ignore[truthy-bool]
            result = docker.stop_containers(model_slug, app_num)  # type: ignore[attr-defined]
            if result.get('success'):
                app.container_status = 'stopped'
                db.session.commit()
        else:
            result = app_service.stop_application(app.id)
        return json_success(result, message=f'Stopped {model_slug} app {app_num}')
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error stopping app {model_slug}/{app_num}: {e}")
        return json_error(str(e), status=500, error_type='InternalError')


@api_bp.route('/app/<model_slug>/<int:app_num>/restart', methods=['POST'])
def restart_app_by_model(model_slug, app_num):
    """Restart application by model slug and app number."""
    try:
        app = GeneratedApplication.query.filter_by(model_slug=model_slug, app_number=app_num).first()
        if not app:
            return json_error(f'Application {model_slug}/{app_num} not found', status=404, error_type='NotFound')
        docker = ServiceLocator.get_docker_manager()
        if docker is not None:  # type: ignore[truthy-bool]
            result = docker.restart_containers(model_slug, app_num)  # type: ignore[attr-defined]
            if result.get('success'):
                app.container_status = 'running'
                db.session.commit()
        else:
            result = app_service.restart_application(app.id)
        return json_success(result, message=f'Restarted {model_slug} app {app_num}')
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error restarting app {model_slug}/{app_num}: {e}")
        return json_error(str(e), status=500, error_type='InternalError')


@api_bp.route('/app/<model_slug>/<int:app_num>/build', methods=['POST'])
def build_app_by_model(model_slug, app_num):
    """Build containers for application by model slug and app number using DockerManager."""
    try:
        # Verify app exists (optional: create placeholder if directory exists)
        app = GeneratedApplication.query.filter_by(model_slug=model_slug, app_number=app_num).first()
        docker = ServiceLocator.get_docker_manager()
        if docker is None:
            return json_error('Docker manager unavailable', status=503, error_type='ServiceUnavailable')

        # Ensure compose file exists before attempting build
        app_dir = get_app_directory(model_slug, app_num, base_path=Path(__file__).resolve().parents[4] / 'misc' / 'models')
        compose_path = app_dir / 'docker-compose.yml'
        if not compose_path.exists():
            return json_error(f'docker-compose.yml not found for {model_slug}/app{app_num}', status=404, error_type='NotFound')

        result = docker.build_containers(model_slug, app_num, no_cache=True)  # type: ignore[attr-defined]

        # Update DB status to 'stopped' after a successful build (not running yet)
        if app and result.get('success'):
            app.container_status = 'stopped'
            db.session.commit()

        message = 'Build started' if result.get('success') else 'Build failed'
        return json_success(result, message=message)
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error building app {model_slug}/{app_num}: {e}")
        return json_error(str(e), status=500, error_type='InternalError')


@api_bp.route('/model/<model_slug>/containers/start', methods=['POST'])
def start_model_containers(model_slug):
    """Start all containers for a model."""
    try:
        result = app_service.start_model_containers(model_slug)
        if result['affected'] == 0:
            return json_error(f'No applications found for model {model_slug}', status=404, error_type='NotFound')
        return json_success(result, message=f"Started {result['started']} containers for {model_slug}")
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error starting containers for model {model_slug}: {e}")
        return json_error(str(e), status=500, error_type='InternalError')


@api_bp.route('/model/<model_slug>/containers/stop', methods=['POST'])
def stop_model_containers(model_slug):
    """Stop all containers for a model."""
    try:
        result = app_service.stop_model_containers(model_slug)
        if result['affected'] == 0:
            return json_error(f'No applications found for model {model_slug}', status=404, error_type='NotFound')
        return json_success(result, message=f"Stopped {result['stopped']} containers for {model_slug}")
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error stopping containers for model {model_slug}: {e}")
        return json_error(str(e), status=500, error_type='InternalError')


@api_bp.route('/model/<model_slug>/containers/build', methods=['POST'])
def build_model_containers(model_slug):
    """Build all containers (docker images) for a model's applications that have docker-compose.yml."""
    try:
        apps = db.session.query(GeneratedApplication).filter_by(model_slug=model_slug).all()
        if not apps:
            return json_error(f'No applications found for model {model_slug}', status=404, error_type='NotFound')

        docker = ServiceLocator.get_docker_manager()
        if docker is None:  # type: ignore[truthy-bool]
            return json_error('Docker manager unavailable', status=503, error_type='ServiceUnavailable')

        built = 0
        skipped = 0
        errors = 0
        base_models_path = Path(__file__).resolve().parents[4] / 'misc' / 'models'

        for app in apps:
            app_dir = get_app_directory(model_slug, app.app_number, base_path=base_models_path)
            compose_path = app_dir / 'docker-compose.yml'
            if not compose_path.exists():
                skipped += 1
                continue
            try:
                result = docker.build_containers(model_slug, app.app_number, no_cache=False)  # type: ignore[attr-defined]
                if result.get('success'):
                    built += 1
                else:
                    errors += 1
            except Exception:
                errors += 1

        return json_success({'built': built, 'skipped': skipped, 'errors': errors}, message=f'Build triggered for {model_slug}')
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error building containers for model {model_slug}: {e}")
        return json_error(str(e), status=500, error_type='InternalError')


@api_bp.route('/model/<model_slug>/containers/restart', methods=['POST'])
def restart_model_containers(model_slug):
    """Restart all containers for a model (best-effort)."""
    try:
        apps = db.session.query(GeneratedApplication).filter_by(model_slug=model_slug).all()
        if not apps:
            return json_error(f'No applications found for model {model_slug}', status=404, error_type='NotFound')

        docker = ServiceLocator.get_docker_manager()
        restarted = 0
        errors = 0
        for app in apps:
            try:
                if docker is not None:  # type: ignore[truthy-bool]
                    result = docker.restart_containers(model_slug, app.app_number)  # type: ignore[attr-defined]
                    if result.get('success'):
                        app.container_status = 'running'
                        restarted += 1
                    else:
                        errors += 1
                else:
                    # Fallback via service
                    res = app_service.restart_application(app.id)
                    if res.get('success'):
                        restarted += 1
                    else:
                        errors += 1
            except Exception:
                errors += 1
        db.session.commit()
        return json_success({'restarted': restarted, 'errors': errors}, message=f'Restarted containers for {model_slug}')
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error restarting containers for model {model_slug}: {e}")
        return json_error(str(e), status=500, error_type='InternalError')


@api_bp.route('/model/<model_slug>/containers/sync-status', methods=['POST'])
def sync_model_status(model_slug):
    """Return HTML fragment with up-to-date app cards for a model (used by htmx)."""
    try:
        from ...models import ModelCapability, PortConfiguration
        model = ModelCapability.query.filter_by(canonical_slug=model_slug).first_or_404()
        apps = db.session.query(GeneratedApplication).filter_by(model_slug=model_slug).all()
        ports_by_app = {pc.app_num: {'backend': pc.backend_port, 'frontend': pc.frontend_port}
                        for pc in db.session.query(PortConfiguration).filter_by(model=model_slug).all()}

        # Build the object the mini-fragment expects
        app_list = []
        for i in range(1, 31):
            app = next((a for a in apps if a.app_number == i), None)
            app_list.append({
                'app_number': i,
                'status': app.container_status if app else 'not_created',
                'app_type': app.app_type if app else 'unknown',
                'ports': ports_by_app.get(i),
                'exists': bool(app),
                'has_docker_compose': app.has_docker_compose if app else False
            })
        return render_template('partials/apps_grid/model_apps_inline.html', model=model, apps=app_list)
    except Exception as e:
        logger.error(f"Error syncing model status for {model_slug}: {e}")
        return f'<div class="alert alert-danger">Error loading status: {str(e)}</div>', 500


# -----------------------------------------------------------------
# Simple GET proxy to frontend root (basic, non-streaming)
# -----------------------------------------------------------------
@api_bp.route('/app/<model_slug>/<int:app_num>/proxy/frontend')
def proxy_frontend_root(model_slug, app_num):
    """Basic GET proxy that fetches the frontend root from the server's bound port.

    Security: Minimal; this only proxies the root ('/') and returns the content-type
    provided by the proxied response. Do not expand this to arbitrary proxying without
    adding authentication and access controls.
    """
    try:
        # 1) Try DB lookup for port
        try:
            from ...models import PortConfiguration
            pc = db.session.query(PortConfiguration).filter_by(model=model_slug, app_num=app_num).first()
            port = pc.frontend_port if pc else None
        except Exception:
            port = None

        # 2) Fallback to misc/port_config.json
        if not port:
            try:
                proj_root = Path(__file__).resolve().parents[4]
                port_file = proj_root / 'misc' / 'port_config.json'
                if port_file.exists():
                    entries = json.loads(port_file.read_text(encoding='utf-8'))
                    for entry in entries:
                        if entry.get('model_name') == model_slug and int(entry.get('app_number')) == int(app_num):
                            port = int(entry.get('frontend_port'))
                            break
            except Exception:
                port = None

        if not port:
            return json_error('Frontend port not available', status=404, error_type='NotFound')

        url = f'http://localhost:{port}/'
        resp = requests.get(url, timeout=10)
        content_type = resp.headers.get('Content-Type', 'text/html; charset=utf-8')
        return Response(resp.content, status=resp.status_code, content_type=content_type)
    except Exception as e:
        logger.error(f"Proxy error for {model_slug}/app{app_num}: {e}")
        return json_error(str(e), status=500, error_type='InternalError')
