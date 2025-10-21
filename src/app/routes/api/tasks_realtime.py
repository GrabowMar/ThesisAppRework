"""REST fallback endpoints for realtime task events."""
from flask import Blueprint, request, jsonify
from flask_login import current_user

from app.realtime.task_events import get_recent_events
from app.services.task_service import queue_service

tasks_rt_bp = Blueprint('tasks_realtime', __name__, url_prefix='/api/tasks')

# Require authentication for all tasks API routes
@tasks_rt_bp.before_request
def require_authentication():
    """Require authentication for all tasks API endpoints."""
    if not current_user.is_authenticated:
        return jsonify({
            'error': 'Authentication required',
            'message': 'Please log in to access this endpoint',
            'login_url': '/auth/login'
        }), 401


@tasks_rt_bp.get('/events')
def get_events():
    since = request.args.get('since')
    events = get_recent_events()
    if since:
        # Return only events newer than 'since'
        events = [e for e in events if e.get('timestamp') and e['timestamp'] > since]
    return jsonify({
        'events': events
    })


@tasks_rt_bp.get('/queue-status')
def queue_status():
    try:
        status = queue_service.get_queue_status()
        return jsonify(status)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
