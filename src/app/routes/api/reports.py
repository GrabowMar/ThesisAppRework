"""
Reports API Routes (v2)
=======================

Simplified API for report generation and retrieval.
Reports store JSON data directly in database - no file I/O.
"""
import logging
from flask import Blueprint, request, jsonify
from flask_login import current_user, login_user

from ...extensions import db
from ...models import User
from ...services.report_service import get_report_service

logger = logging.getLogger(__name__)

reports_bp = Blueprint('reports_api', __name__, url_prefix='/reports')


def _authenticate_request():
    """Authenticate via session or Bearer token."""
    if current_user.is_authenticated:
        return current_user, None
    
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]
        try:
            user = User.verify_api_token(token)
            if user:
                login_user(user, remember=False)
                return user, None
        except Exception as e:
            logger.warning(f"Token auth failed: {e}")
    
    return None, None


@reports_bp.before_request
def require_authentication():
    """Require authentication for all endpoints."""
    user, _ = _authenticate_request()
    if not user and not current_user.is_authenticated:
        return jsonify({
            'success': False,
            'error': 'Authentication required',
            'message': 'Please log in or provide a Bearer token'
        }), 401


@reports_bp.route('/generate', methods=['POST'])
def generate_report():
    """
    Generate a new report.
    
    Request body:
    {
        "report_type": "model_analysis|template_comparison|tool_analysis|generation_analytics|comprehensive",
        "config": {
            // For model_analysis:
            "model_slug": "openai_gpt-4",
            "date_range": {"start": "2025-01-01", "end": "2025-12-31"}
            
            // For template_comparison:
            "template_slug": "crud_todo_list",
            "filter_models": ["model1", "model2"]
            
            // For tool_analysis:
            "tool_name": "bandit",  // optional
            "filter_model": "openai_gpt-4",  // optional
            "filter_app": 1  // optional
        },
        "title": "Custom title",  // optional
        "description": "Description",  // optional
        "filter_mode": "all|exclude_dynamic_perf|only_dynamic_perf"  // optional, default: all
    }
    """
    try:
        from ...constants import ReportFilterMode
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Request body required'}), 400
        
        report_type = data.get('report_type')
        config = data.get('config', {})
        
        if not report_type:
            return jsonify({'success': False, 'error': 'report_type required'}), 400
        
        # Map old 'app_analysis' to new 'template_comparison' for backwards compat
        if report_type == 'app_analysis':
            report_type = 'template_comparison'
        
        valid_types = ['model_analysis', 'template_comparison', 'tool_analysis', 'generation_analytics', 'comprehensive']
        if report_type not in valid_types:
            return jsonify({
                'success': False,
                'error': f'report_type must be one of: {", ".join(valid_types)}'
            }), 400
        
        # Validate required config
        if report_type == 'model_analysis' and not config.get('model_slug'):
            return jsonify({'success': False, 'error': 'model_slug required'}), 400
        if report_type == 'template_comparison' and not config.get('template_slug'):
            return jsonify({'success': False, 'error': 'template_slug required'}), 400
        # generation_analytics and comprehensive have no required config
        
        # Parse filter_mode
        filter_mode_str = data.get('filter_mode', 'all')
        try:
            filter_mode = ReportFilterMode(filter_mode_str)
        except ValueError:
            return jsonify({
                'success': False,
                'error': f'filter_mode must be one of: all, exclude_dynamic_perf, only_dynamic_perf'
            }), 400
        
        service = get_report_service()
        user_id = current_user.id if current_user.is_authenticated else None
        
        report = service.generate_report(
            report_type=report_type,
            config=config,
            title=data.get('title'),
            description=data.get('description'),
            user_id=user_id,
            expires_in_days=data.get('expires_in_days', 30),
            filter_mode=filter_mode
        )
        
        return jsonify({
            'success': True,
            'report': report.to_dict(),
            'message': 'Report generated successfully'
        }), 201
        
    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error generating report: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@reports_bp.route('/<report_id>', methods=['GET'])
def get_report(report_id: str):
    """
    Get report by ID.
    
    Query params:
        - include_data: If 'true', include full report data
    """
    try:
        service = get_report_service()
        report = service.get_report(report_id)
        
        if not report:
            return jsonify({'success': False, 'error': 'Report not found'}), 404
        
        include_data = request.args.get('include_data', 'false').lower() == 'true'
        
        return jsonify({
            'success': True,
            'report': report.to_dict(include_data=include_data)
        })
        
    except Exception as e:
        logger.error(f"Error getting report: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@reports_bp.route('/<report_id>/data', methods=['GET'])
def get_report_data(report_id: str):
    """Get full report data for client-side rendering."""
    try:
        service = get_report_service()
        report = service.get_report(report_id)
        
        if not report:
            return jsonify({'success': False, 'error': 'Report not found'}), 404
        
        if report.status != 'completed':
            return jsonify({
                'success': False,
                'error': f'Report not ready (status: {report.status})',
                'status': report.status,
                'progress': report.progress_percent
            }), 400
        
        data = report.get_report_data()
        if not data:
            return jsonify({'success': False, 'error': 'No data available'}), 404
        
        return jsonify({
            'success': True,
            'report_id': report_id,
            'report_type': report.report_type,
            'title': report.title,
            'data': data
        })
        
    except Exception as e:
        logger.error(f"Error getting report data: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@reports_bp.route('', methods=['GET'])
def list_reports():
    """
    List reports with optional filtering.
    
    Query params:
        - report_type: Filter by type
        - status: Filter by status
        - limit: Max results (default 50)
        - offset: Pagination offset
    """
    try:
        service = get_report_service()
        
        report_type = request.args.get('report_type')
        status = request.args.get('status')
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        user_id = current_user.id if current_user.is_authenticated else None
        
        reports = service.list_reports(
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
        service = get_report_service()
        report = service.get_report(report_id)
        
        if not report:
            return jsonify({'success': False, 'error': 'Report not found'}), 404
        
        # Check ownership
        if current_user.is_authenticated and report.created_by:
            if report.created_by != current_user.id and not getattr(current_user, 'is_admin', False):
                return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
        service.delete_report(report_id)
        
        return jsonify({
            'success': True,
            'message': 'Report deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"Error deleting report: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@reports_bp.route('/<report_id>/regenerate', methods=['POST'])
def regenerate_report(report_id: str):
    """
    Regenerate an existing report with fresh data.
    
    Useful when underlying analysis data has changed since the report
    was originally generated.
    """
    try:
        service = get_report_service()
        report = service.get_report(report_id)
        
        if not report:
            return jsonify({'success': False, 'error': 'Report not found'}), 404
        
        # Check ownership
        if current_user.is_authenticated and report.created_by:
            if report.created_by != current_user.id and not getattr(current_user, 'is_admin', False):
                return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
        # Regenerate the report
        regenerated = service.regenerate_report(report_id)
        
        if not regenerated:
            return jsonify({
                'success': False, 
                'error': 'Failed to regenerate report'
            }), 500
        
        return jsonify({
            'success': True,
            'report': regenerated.to_dict(include_data=True),
            'message': 'Report regenerated successfully'
        })
        
    except Exception as e:
        logger.error(f"Error regenerating report: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@reports_bp.route('/cleanup', methods=['POST'])
def cleanup_expired():
    """Clean up expired reports (admin only)."""
    try:
        if not current_user.is_authenticated or not getattr(current_user, 'is_admin', False):
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        
        service = get_report_service()
        count = service.cleanup_expired_reports()
        
        return jsonify({
            'success': True,
            'message': f'Cleaned up {count} expired reports'
        })
        
    except Exception as e:
        logger.error(f"Error cleaning up reports: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


# =============================================================================
# Data endpoints for report generation UI
# =============================================================================

@reports_bp.route('/options', methods=['GET'])
def get_report_options():
    """
    Get options for report generation form.
    
    Returns available models, templates, and tools for dropdown population.
    """
    try:
        from ...models import ModelCapability, GeneratedApplication
        from ...engines.container_tool_registry import get_container_tool_registry
        from ...services.generation_v2 import get_generation_service
        from ...utils.slug_utils import normalize_model_slug
        
        # Get all unique model slugs from generated apps (most reliable source)
        app_model_slugs = db.session.query(
            GeneratedApplication.model_slug
        ).distinct().all()
        app_model_slugs = [row[0] for row in app_model_slugs if row[0]]
        
        # Build models data - prioritize from apps, enrich with ModelCapability where available
        models_data = []
        seen_slugs = set()
        
        for slug in app_model_slugs:
            if slug in seen_slugs:
                continue
            seen_slugs.add(slug)
            
            # Try to find matching capability for display name
            normalized = normalize_model_slug(slug)
            capability = ModelCapability.query.filter(
                (ModelCapability.canonical_slug == slug) | 
                (ModelCapability.canonical_slug == normalized)
            ).first()
            
            if capability:
                models_data.append({
                    'slug': slug,
                    'name': capability.model_name or slug,
                    'provider': capability.provider or slug.split('_')[0] if '_' in slug else 'unknown'
                })
            else:
                # Parse from slug
                parts = slug.split('_', 1)
                provider = parts[0] if parts else 'unknown'
                model_name = parts[1] if len(parts) > 1 else slug
                models_data.append({
                    'slug': slug,
                    'name': model_name.replace('-', ' ').title(),
                    'provider': provider
                })
        
        # Sort by provider then name
        models_data.sort(key=lambda m: (m['provider'], m['name']))
        
        # Get apps grouped by model
        apps = GeneratedApplication.query.order_by(
            GeneratedApplication.model_slug,
            GeneratedApplication.app_number
        ).all()
        
        apps_by_model = {}
        for app in apps:
            if app.model_slug not in apps_by_model:
                apps_by_model[app.model_slug] = []
            apps_by_model[app.model_slug].append({
                'app_number': app.app_number,
                'template_slug': app.template_slug,
                'app_type': app.app_type
            })
        
        # Get tools
        tool_registry = get_container_tool_registry()
        all_tools = tool_registry.get_all_tools()
        tools_data = [{
            'name': tool.name,
            'display_name': tool.display_name,
            'container': tool.container.value if hasattr(tool.container, 'value') else str(tool.container),
            'available': tool.available
        } for tool in all_tools.values()]
        tools_data.sort(key=lambda t: (t['container'], t['display_name']))
        
        # Get templates
        gen_service = get_generation_service()
        templates_catalog = gen_service.get_template_catalog()
        templates_data = [{
            'slug': t.get('slug'),
            'name': t.get('name'),
            'category': t.get('category', 'general')
        } for t in templates_catalog if t.get('slug') and t.get('name')]
        templates_data.sort(key=lambda t: (t['category'], t['name']))
        
        return jsonify({
            'success': True,
            'models': models_data,
            'apps_by_model': apps_by_model,
            'tools': tools_data,
            'templates': templates_data
        })
        
    except Exception as e:
        logger.error(f"Error getting report options: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Internal server error'}), 500
