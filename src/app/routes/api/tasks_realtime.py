"""REST fallback endpoints for realtime task events."""
from flask import Blueprint, request, jsonify

from app.realtime.task_events import get_recent_events
from app.services.task_service import queue_service

tasks_rt_bp = Blueprint('tasks_realtime', __name__, url_prefix='/api/tasks')


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
