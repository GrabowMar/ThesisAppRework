"""
API Routes for Report Generation

Handles report creation, retrieval, and download operations.
"""
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, send_file, current_app, g
from flask_login import current_user, login_user
from pathlib import Path

from ...extensions import db
from ...models import Report, User
from ...services.service_locator import ServiceLocator
from ...services.service_base import NotFoundError, ValidationError, ServiceError

logger = logging.getLogger(__name__)

# Create blueprint (prefix is just '/reports' since it's nested under api_bp which adds '/api')
reports_bp = Blueprint('reports_api', __name__, url_prefix='/reports')


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
            user = User.verify_api_token(token)
            if user:
                # Set user for this request context
                login_user(user, remember=False)
                return user, None
        except Exception as e:
            logger.warning(f"Token auth failed: {e}")
    
    return None, None


# Require authentication for all report API routes
@reports_bp.before_request
def require_authentication():
    """Require authentication for all report API endpoints."""
    user, _ = _authenticate_request()
    
    if not user and not current_user.is_authenticated:
        return jsonify({
            'error': 'Authentication required',
            'message': 'Please log in or provide a Bearer token',
            'login_url': '/auth/login'
        }), 401


@reports_bp.route('/generate', methods=['POST'])
def generate_report():
    """
    Generate a new report.
    
    Request body:
    {
        "report_type": "model_analysis|app_analysis|tool_analysis",
        "format": "html|json",
        "config": {
            // For model_analysis:
            "model_slug": "openai_gpt-4",
            "date_range": {"start": "2025-01-01", "end": "2025-12-31"}  // optional
            
            // For app_analysis:
            "app_number": 1,
            "filter_models": ["model1", "model2"],  // optional
            "date_range": {"start": "2025-01-01", "end": "2025-12-31"}  // optional
            
            // For tool_analysis:
            "tool_name": "bandit",  // optional (omit for all tools)
            "filter_model": "openai_gpt-4",  // optional
            "filter_app": 1,  // optional
            "date_range": {"start": "2025-01-01", "end": "2025-12-31"}  // optional
        },
        "title": "Custom Report Title",     // optional
        "description": "Report description",// optional
        "expires_in_days": 30               // optional, default 30
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Request body required'}), 400
        
        # Validate required fields
        report_type = data.get('report_type')
        format_type = data.get('format', 'html')
        config = data.get('config', {})
        
        if not report_type:
            return jsonify({'success': False, 'error': 'report_type required'}), 400
        
        valid_types = ['model_analysis', 'app_analysis', 'tool_analysis']
        if report_type not in valid_types:
            return jsonify({'success': False, 'error': f'report_type must be one of: {", ".join(valid_types)}'}), 400
        
        valid_formats = ['html', 'json']
        if format_type not in valid_formats:
            return jsonify({'success': False, 'error': f'format must be one of: {", ".join(valid_formats)}'}), 400
        
        # Validate config based on report type
        if report_type == 'model_analysis':
            if not config.get('model_slug'):
                return jsonify({'success': False, 'error': 'model_slug required for model_analysis'}), 400
        elif report_type == 'app_analysis':
            if config.get('app_number') is None:
                return jsonify({'success': False, 'error': 'app_number required for app_analysis'}), 400
        # tool_analysis is flexible - no required fields
        
        # Get service
        service_locator = ServiceLocator()
        report_service = service_locator.get_report_service()
        
        # Get current user
        user_id = current_user.id if current_user.is_authenticated else None
        
        # Generate report
        report = report_service.generate_report(
            report_type=report_type,
            format=format_type,
            config=config,
            title=data.get('title'),
            description=data.get('description'),
            user_id=user_id,
            expires_in_days=data.get('expires_in_days', 30)
        )
        
        return jsonify({
            'success': True,
            'report': report.to_dict(),
            'message': 'Report generated successfully'
        }), 201
        
    except ValidationError as e:
        logger.warning(f"Validation error generating report: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400
    
    except ServiceError as e:
        logger.error(f"Service error generating report: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    
    except Exception as e:
        logger.error(f"Error generating report: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@reports_bp.route('/<report_id>', methods=['GET'])
def get_report(report_id: str):
    """Get report details by ID."""
    try:
        service_locator = ServiceLocator()
        report_service = service_locator.get_report_service()
        
        report = report_service.get_report(report_id)
        
        if not report:
            return jsonify({'success': False, 'error': 'Report not found'}), 404
        
        return jsonify({
            'success': True,
            'report': report.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error getting report {report_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@reports_bp.route('/<report_id>/download', methods=['GET'])
def download_report(report_id: str):
    """
    Download report file.
    
    Query params:
        - inline: Set to 'true' to view in browser instead of download
    """
    try:
        service_locator = ServiceLocator()
        report_service = service_locator.get_report_service()
        
        report = report_service.get_report(report_id)
        
        if not report:
            return jsonify({'success': False, 'error': 'Report not found'}), 404
        
        if report.status != 'completed':
            return jsonify({
                'success': False,
                'error': f'Report not ready (status: {report.status})'
            }), 400
        
        if not report.file_path:
            return jsonify({'success': False, 'error': 'Report file not found'}), 404
        
        # Get absolute file path
        file_path = report_service.reports_dir / report.file_path
        
        if not file_path.exists():
            return jsonify({'success': False, 'error': 'Report file does not exist'}), 404
        
        # Determine if inline or attachment
        inline = request.args.get('inline', 'false').lower() == 'true'
        
        # Get MIME type
        mime_type = _get_mime_type(report.format)
        
        return send_file(
            file_path,
            mimetype=mime_type,
            as_attachment=not inline,
            download_name=file_path.name
        )
        
    except Exception as e:
        logger.error(f"Error downloading report {report_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@reports_bp.route('', methods=['GET'])
def list_reports():
    """
    List reports with optional filtering.
    
    Query params:
        - report_type: Filter by report type
        - status: Filter by status
        - limit: Max results (default 50)
        - offset: Pagination offset (default 0)
    """
    try:
        service_locator = ServiceLocator()
        report_service = service_locator.get_report_service()
        
        # Get query params
        report_type = request.args.get('report_type')
        status = request.args.get('status')
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        
        # Get current user
        user_id = current_user.id if current_user.is_authenticated else None
        
        # List reports
        reports = report_service.list_reports(
            report_type=report_type,
            status=status,
            user_id=user_id,
            limit=limit,
            offset=offset
        )
        
        return jsonify({
            'success': True,
            'reports': [r.to_dict() for r in reports],
            'count': len(reports),
            'limit': limit,
            'offset': offset
        })
        
    except Exception as e:
        logger.error(f"Error listing reports: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@reports_bp.route('/<report_id>', methods=['DELETE'])
def delete_report(report_id: str):
    """Delete a report."""
    try:
        service_locator = ServiceLocator()
        report_service = service_locator.get_report_service()
        
        # Check if report exists
        report = report_service.get_report(report_id)
        if not report:
            return jsonify({'success': False, 'error': 'Report not found'}), 404
        
        # Check ownership (if user is authenticated)
        if current_user.is_authenticated and report.created_by and report.created_by != current_user.id:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
        # Delete report
        delete_file = request.args.get('delete_file', 'true').lower() == 'true'
        report_service.delete_report(report_id, delete_file=delete_file)
        
        return jsonify({
            'success': True,
            'message': 'Report deleted successfully'
        })
        
    except NotFoundError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    
    except Exception as e:
        logger.error(f"Error deleting report {report_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@reports_bp.route('/cleanup', methods=['POST'])
def cleanup_expired_reports():
    """Clean up expired reports (admin only)."""
    try:
        # Check if user is admin
        if not current_user.is_authenticated or not current_user.is_admin:
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        
        service_locator = ServiceLocator()
        report_service = service_locator.get_report_service()
        
        count = report_service.cleanup_expired_reports()
        
        return jsonify({
            'success': True,
            'message': f'Cleaned up {count} expired reports'
        })
        
    except Exception as e:
        logger.error(f"Error cleaning up expired reports: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


# Helper functions
def _get_mime_type(format_type: str) -> str:
    """Get MIME type for report format."""
    mime_types = {
        'pdf': 'application/pdf',
        'html': 'text/html',
        'excel': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'json': 'application/json'
    }
    return mime_types.get(format_type, 'application/octet-stream')
