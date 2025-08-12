"""
Applications API Routes
=======================

API endpoints for application management and CRUD operations.
"""

import logging
from flask import jsonify, request, render_template

from . import api_bp
from ...models import GeneratedApplication
from ...extensions import db
from ...constants import AnalysisStatus

# Set up logger
logger = logging.getLogger(__name__)


@api_bp.route('/applications')
def api_list_applications():
    """API endpoint: Get applications."""
    try:
        # Get query parameters for pagination and filtering
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status')
        app_type = request.args.get('type')
        
        # Build query
        query = GeneratedApplication.query
        
        if status:
            query = query.filter(GeneratedApplication.generation_status == status)
        if app_type:
            query = query.filter(GeneratedApplication.app_type == app_type)
        
        # Order by creation date (newest first)
        query = query.order_by(GeneratedApplication.created_at.desc())
        
        # Paginate results
        paginated = query.paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        return jsonify({
            'applications': [app.to_dict() for app in paginated.items],
            'pagination': {
                'page': paginated.page,
                'pages': paginated.pages,
                'per_page': paginated.per_page,
                'total': paginated.total,
                'has_next': paginated.has_next,
                'has_prev': paginated.has_prev
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting applications: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/applications', methods=['POST'])
def api_create_application():
    """API endpoint: Create application."""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['model_slug', 'app_number', 'app_type', 'provider']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Create new application
        app = GeneratedApplication()
        app.model_slug = data['model_slug']
        app.app_number = data['app_number']
        app.app_type = data['app_type']
        app.provider = data['provider']
        app.generation_status = data.get('generation_status', AnalysisStatus.PENDING)
        
        # Set optional fields that exist in the model
        if 'has_backend' in data:
            app.has_backend = data['has_backend']
        if 'has_frontend' in data:
            app.has_frontend = data['has_frontend']
        if 'has_docker_compose' in data:
            app.has_docker_compose = data['has_docker_compose']
        if 'backend_framework' in data:
            app.backend_framework = data['backend_framework']
        if 'frontend_framework' in data:
            app.frontend_framework = data['frontend_framework']
        if 'container_status' in data:
            app.container_status = data['container_status']
        
        db.session.add(app)
        db.session.commit()
        
        return jsonify(app.to_dict()), 201
        
    except Exception as e:
        logger.error(f"Error creating application: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/applications/<int:app_id>')
def api_get_application(app_id):
    """API endpoint: Get specific application."""
    try:
        app = GeneratedApplication.query.get(app_id)
        if not app:
            return jsonify({'error': 'Application not found'}), 404
        return jsonify(app.to_dict())
    except Exception as e:
        logger.error(f"Error getting application {app_id}: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/applications/<int:app_id>', methods=['PUT'])
def api_update_application(app_id):
    """API endpoint: Update application."""
    try:
        app = GeneratedApplication.query.get(app_id)
        if not app:
            return jsonify({'error': 'Application not found'}), 404
        
        data = request.get_json()
        
        # Update allowed fields
        updatable_fields = [
            'model_slug', 'app_number', 'app_type', 'provider', 'generation_status',
            'has_backend', 'has_frontend', 'has_docker_compose', 
            'backend_framework', 'frontend_framework', 'container_status'
        ]
        
        for field in updatable_fields:
            if field in data:
                setattr(app, field, data[field])
        
        # Handle metadata updates separately
        if 'metadata' in data:
            app.set_metadata(data['metadata'])
        
        db.session.commit()
        return jsonify(app.to_dict())
        
    except Exception as e:
        logger.error(f"Error updating application {app_id}: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/applications/<int:app_id>', methods=['DELETE'])
def api_delete_application(app_id):
    """API endpoint: Delete application."""
    try:
        app = GeneratedApplication.query.get(app_id)
        if not app:
            return jsonify({'error': 'Application not found'}), 404
        
        db.session.delete(app)
        db.session.commit()
        
        return jsonify({'message': 'Application deleted successfully'})
        
    except Exception as e:
        logger.error(f"Error deleting application {app_id}: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/applications/types')
def api_get_application_types():
    """API endpoint: Get available application types."""
    try:
        # Get distinct application types from the database
        types = (
            db.session.query(GeneratedApplication.app_type)
            .distinct()
            .filter(GeneratedApplication.app_type.isnot(None))
            .all()
        )
        
        type_list = [t[0] for t in types]
        
        # Add common application types if not already present
        common_types = [
            'web_app', 'api', 'microservice', 'dashboard', 
            'e_commerce', 'blog', 'cms', 'social_media'
        ]
        
        for common_type in common_types:
            if common_type not in type_list:
                type_list.append(common_type)
        
        return jsonify({
            'types': sorted(type_list)
        })
        
    except Exception as e:
        logger.error(f"Error getting application types: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/applications/<int:app_id>/code')
def api_get_application_code(app_id):
    """API endpoint: Get application code/metadata."""
    try:
        app = GeneratedApplication.query.get(app_id)
        if not app:
            return jsonify({'error': 'Application not found'}), 404
        
        return jsonify({
            'model_slug': app.model_slug,
            'app_number': app.app_number,
            'metadata': app.get_metadata(),
            'has_backend': app.has_backend,
            'has_frontend': app.has_frontend,
            'has_docker_compose': app.has_docker_compose,
            'backend_framework': app.backend_framework,
            'frontend_framework': app.frontend_framework
        })
        
    except Exception as e:
        logger.error(f"Error getting application code for {app_id}: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/applications/<int:app_id>/status', methods=['PATCH'])
def api_update_application_status(app_id):
    """API endpoint: Update application status."""
    try:
        app = GeneratedApplication.query.get(app_id)
        if not app:
            return jsonify({'error': 'Application not found'}), 404
        
        data = request.get_json()
        if 'generation_status' not in data and 'container_status' not in data:
            return jsonify({'error': 'generation_status or container_status is required'}), 400
        
        # Update generation status
        if 'generation_status' in data:
            app.generation_status = data['generation_status']
        
        # Update container status
        if 'container_status' in data:
            valid_container_statuses = ['running', 'stopped', 'error', 'pending', 'building']
            if data['container_status'] not in valid_container_statuses:
                return jsonify({'error': f'Invalid container status. Must be one of: {valid_container_statuses}'}), 400
            app.container_status = data['container_status']
        
        db.session.commit()
        
        return jsonify({
            'generation_status': str(app.generation_status) if app.generation_status else None,
            'container_status': app.container_status
        })
        
    except Exception as e:
        logger.error(f"Error updating application status for {app_id}: {e}")
        return jsonify({'error': str(e)}), 500


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
        app_type = request.args.get('type', '')
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
        if view == 'list':
            return render_template('partials/apps_list.html', apps=apps)
        else:
            return render_template('partials/apps_grid.html', apps=apps)
    except Exception as e:
        logger.error(f"Error getting apps grid: {e}")
        return f'<div class="alert alert-danger">Error loading applications: {str(e)}</div>'


@api_bp.route('/applications/<int:app_id>/start', methods=['POST'])
def api_application_start(app_id):
    """API endpoint to start an application container."""
    try:
        app = GeneratedApplication.query.get(app_id)
        if not app:
            return jsonify({'error': f'Application {app_id} not found'}), 404
        
        # Update container status
        app.container_status = 'running'
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Application {app_id} started successfully'
        })
            
    except Exception as e:
        logger.error(f"Error starting application {app_id}: {e}")
        return jsonify({'error': str(e), 'success': False}), 500


@api_bp.route('/applications/<int:app_id>/stop', methods=['POST'])
def api_application_stop(app_id):
    """API endpoint to stop an application container."""
    try:
        app = GeneratedApplication.query.get(app_id)
        if not app:
            return jsonify({'error': f'Application {app_id} not found'}), 404
        
        # Update container status
        app.container_status = 'stopped'
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Application {app_id} stopped successfully'
        })
            
    except Exception as e:
        logger.error(f"Error stopping application {app_id}: {e}")
        return jsonify({'error': str(e), 'success': False}), 500


@api_bp.route('/applications/<int:app_id>/restart', methods=['POST'])
def api_application_restart(app_id):
    """API endpoint to restart an application container."""
    try:
        app = GeneratedApplication.query.get(app_id)
        if not app:
            return jsonify({'error': f'Application {app_id} not found'}), 404
        
        # Update container status (simulate restart)
        app.container_status = 'running'
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Application {app_id} restarted successfully'
        })
            
    except Exception as e:
        logger.error(f"Error restarting application {app_id}: {e}")
        return jsonify({'error': str(e), 'success': False}), 500


@api_bp.route('/applications/<int:app_id>/details')
def api_application_details(app_id):
    """API endpoint to get application details."""
    try:
        app = GeneratedApplication.query.get(app_id)
        if not app:
            return jsonify({'error': f'Application {app_id} not found'}), 404
        
        return jsonify({
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
        })
            
    except Exception as e:
        logger.error(f"Error getting application {app_id} details: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/applications/<int:app_id>/logs')
def api_application_logs_modal(app_id):
    """API endpoint to get application logs modal."""
    try:
        app = GeneratedApplication.query.get(app_id)
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


@api_bp.route('/logs/application/<int:app_id>')
def api_application_logs(app_id):
    """API endpoint for application logs."""
    try:
        app = GeneratedApplication.query.get(app_id)
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
