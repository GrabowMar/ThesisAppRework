"""
Common API utilities and response helpers
=========================================

Shared utilities, response builders, validation logic, and common patterns
used across all API route modules.
"""

import psutil
from datetime import datetime, timezone
from flask import request, jsonify, current_app
from werkzeug.exceptions import BadRequest, NotFound, InternalServerError

from app.extensions import db
from app.utils.helpers import create_success_response, create_error_response
from app.utils.errors import build_error_payload


# ============================================================================
# RESPONSE HELPERS
# ============================================================================

def build_pagination_envelope(query, page, per_page):
    """Build pagination envelope for query results."""
    try:
        items = query.paginate(page=page, per_page=per_page, error_out=False)
        total = query.count()
        total_pages = (total + per_page - 1) // per_page

        return items.items if hasattr(items, 'items') else items, {
            'current_page': page,
            'per_page': per_page,
            'total_items': total,
            'total_pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages
        }
    except Exception:
        # Fallback for queries that don't support pagination
        all_items = query.all() if hasattr(query, 'all') else list(query)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        items = all_items[start_idx:end_idx]

        total = len(all_items)
        total_pages = (total + per_page - 1) // per_page

        return items, {
            'current_page': page,
            'per_page': per_page,
            'total_items': total,
            'total_pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages
        }


def create_success_response_with_status(data=None, message="Success", status=200, **kwargs):
    """Create standardized success response with status support."""
    response = create_success_response(data, message)
    return response, status


def create_error_response_with_status(error, status=500, error_type=None, **kwargs):
    """Create standardized error response with status support."""
    response = create_error_response(error, status, error_type)
    return response, status


def api_success(data=None, message="Success", status=200):
    """Shorthand for JSON success response."""
    return jsonify({
        'success': True,
        'message': message,
        'data': data,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }), status


def api_error(message, status=500, error_type=None, details=None):
    """Shorthand for JSON error response."""
    return jsonify(build_error_payload(
        message, 
        status=status, 
        error=error_type or 'APIError',
        details=details or {}
    )), status


def htmx_or_json(html_content, json_data, message="Success"):
    """Return HTML for HTMX requests, JSON for regular API calls."""
    if request.headers.get('HX-Request'):
        return html_content
    return api_success(json_data, message)


# ============================================================================
# VALIDATION HELPERS
# ============================================================================

def require_fields(data, required_fields):
    """Check if required fields are present in data."""
    missing = []
    for field in required_fields:
        if field not in data or data[field] is None:
            missing.append(field)
    return missing


def validate_request_data(required_fields=None, optional_fields=None):
    """Validate request JSON data and return validated data or error response."""
    data = request.get_json(silent=True) or {}
    
    if required_fields:
        missing = require_fields(data, required_fields)
        if missing:
            raise BadRequest(f"Missing required fields: {', '.join(missing)}")
    
    # Filter to only allowed fields if specified
    if optional_fields is not None:
        all_fields = set(required_fields or []) | set(optional_fields or [])
        data = {k: v for k, v in data.items() if k in all_fields}
    
    return data


def get_pagination_params(default_per_page=25, max_per_page=200):
    """Extract and validate pagination parameters from request."""
    page = request.args.get('page', type=int) or 1
    per_page = request.args.get('per_page', type=int) or default_per_page
    
    per_page = max(1, min(per_page, max_per_page))
    page = max(1, page)
    
    return page, per_page


# ============================================================================
# SYSTEM STATUS HELPERS
# ============================================================================

def get_system_status():
    """Get basic system status information."""
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    
    if cpu_percent > 90 or memory.percent > 90:
        status = 'critical'
        status_class = 'status-indicator-animated bg-red'
    elif cpu_percent > 70 or memory.percent > 80:
        status = 'warning'
        status_class = 'status-indicator-animated bg-orange'
    elif cpu_percent > 50 or memory.percent > 70:
        status = 'moderate'
        status_class = 'status-indicator-animated bg-yellow'
    else:
        status = 'healthy'
        status_class = 'status-indicator-animated bg-green'
    
    return {
        'status': status,
        'status_class': status_class,
        'cpu_percent': cpu_percent,
        'memory_percent': memory.percent,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }


def get_uptime_info():
    """Get system uptime information."""
    boot_time = psutil.boot_time()
    uptime_seconds = datetime.now(timezone.utc).timestamp() - boot_time

    uptime_days = int(uptime_seconds // 86400)
    uptime_hours = int((uptime_seconds % 86400) // 3600)
    uptime_minutes = int((uptime_seconds % 3600) // 60)

    # Format for display
    if uptime_days > 0:
        uptime_str = f"{uptime_days}d {uptime_hours}h"
    elif uptime_hours > 0:
        uptime_str = f"{uptime_hours}h {uptime_minutes}m"
    else:
        uptime_str = f"{uptime_minutes}m"

    return {
        'uptime_seconds': int(uptime_seconds),
        'uptime_formatted': uptime_str,
        'days': uptime_days,
        'hours': uptime_hours,
        'minutes': uptime_minutes
    }


def get_database_health():
    """Check database connection health."""
    try:
        db.session.execute(db.text('SELECT 1'))
        db.session.commit()
        return True, None
    except Exception as e:
        return False, str(e)


def get_active_tasks_count():
    """Get count of active tasks across all analysis types."""
    try:
        from app.models import SecurityAnalysis, PerformanceTest, BatchAnalysis

        active_security = SecurityAnalysis.query.filter(
            SecurityAnalysis.status.in_(['pending', 'running'])
        ).count()

        active_performance = PerformanceTest.query.filter(
            PerformanceTest.status.in_(['pending', 'running'])
        ).count()

        active_batch = BatchAnalysis.query.filter(
            BatchAnalysis.status.in_(['pending', 'running'])
        ).count()

        return {
            'total_active': active_security + active_performance + active_batch,
            'security': active_security,
            'performance': active_performance,
            'batch': active_batch
        }
    except Exception as e:
        current_app.logger.error(f"Error getting active tasks count: {e}")
        return {'total_active': 0, 'security': 0, 'performance': 0, 'batch': 0}


# ============================================================================
# HTML FRAGMENT HELPERS
# ============================================================================

def render_status_indicator(status_info):
    """Render status indicator HTML fragment."""
    status_text = {
        'healthy': 'OK',
        'moderate': 'OK',
        'warning': 'Warning',
        'critical': 'Critical'
    }.get(status_info['status'], 'Unknown')
    
    return f'''
    <span class="d-flex align-items-center" aria-live="polite">
        <span class="{status_info['status_class']} me-2" 
              style="width:20px;height:20px;border-radius:50%;display:inline-block;" 
              aria-hidden="true"></span>
        <small class="text-muted">{status_text}</small>
    </span>
    '''


def render_tasks_indicator(tasks_info):
    """Render tasks count indicator HTML fragment."""
    total = tasks_info['total_active']
    badge_class = 'text-blue' if total > 0 else 'text-muted'
    
    return f'''
    <svg xmlns="http://www.w3.org/2000/svg" class="icon icon-tabler icon-tabler-list-check me-1" 
         width="16" height="16" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" 
         fill="none" stroke-linecap="round" stroke-linejoin="round">
        <path stroke="none" d="M0 0h24v24H0z" fill="none"/>
        <path d="M3.5 5.5l1.5 1.5l2.5 -2.5"/>
        <path d="M3.5 11.5l1.5 1.5l2.5 -2.5"/>
        <path d="M3.5 17.5l1.5 1.5l2.5 -2.5"/>
        <path d="M11 6l9 0"/>
        <path d="M11 12l9 0"/>
        <path d="M11 18l9 0"/>
    </svg>
    <small class="{badge_class}">{total}</small>
    '''


def render_uptime_indicator(uptime_info):
    """Render uptime indicator HTML fragment."""
    return f'''
    <svg xmlns="http://www.w3.org/2000/svg" class="icon icon-tabler icon-tabler-clock me-1" 
         width="16" height="16" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" 
         fill="none" stroke-linecap="round" stroke-linejoin="round">
        <path stroke="none" d="M0 0h24v24H0z" fill="none"/>
        <path d="M12 12m-9 0a9 9 0 1 0 18 0a9 9 0 1 0 -18 0"/>
        <path d="M12 7l0 5 3 3"/>
    </svg>
    <small class="text-muted">{uptime_info['uptime_formatted']}</small>
    '''


# ============================================================================
# EXCEPTION HELPERS
# ============================================================================

def handle_api_exception(exc):
    """Centralized API exception handler."""
    current_app.logger.exception("API Exception occurred")
    
    if isinstance(exc, BadRequest):
        return api_error(str(exc), status=400, error_type='BadRequest')
    elif isinstance(exc, NotFound):
        return api_error(str(exc), status=404, error_type='NotFound')
    elif isinstance(exc, InternalServerError):
        return api_error("Internal server error", status=500, error_type='InternalServerError')
    else:
        return api_error("Unexpected error occurred", status=500, error_type=exc.__class__.__name__)


# ============================================================================
# ADMIN AUTHENTICATION
# ============================================================================

def require_admin_token():
    """Check for admin token in request headers or query params."""
    from flask import abort
    import os
    
    token = request.headers.get('X-Admin-Token') or request.args.get('admin_token')
    expected = current_app.config.get('DASHBOARD_ADMIN_TOKEN') or os.environ.get('DASHBOARD_ADMIN_TOKEN')
    if expected and token != expected:
        abort(401)


# ============================================================================
# BULK OPERATIONS HELPERS
# ============================================================================

def parse_bulk_items(form_field='items'):
    """Parse bulk operation items from form data."""
    raw_items = request.form.getlist(form_field)
    if not raw_items:
        raise BadRequest('No items selected')
    
    parsed_items = []
    for item in raw_items:
        try:
            if ':' in item:
                model_slug, app_number_s = item.split(':', 1)
                app_number = int(app_number_s)
                parsed_items.append((model_slug, app_number))
            else:
                parsed_items.append((item, None))
        except ValueError:
            raise BadRequest(f'Invalid item format: {item}')
    
    return parsed_items