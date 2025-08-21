"""
WebSocket API Routes
Provides REST endpoints for WebSocket service interaction and testing
"""

from flask import Blueprint, request, jsonify
from app.extensions import get_websocket_service
import logging
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)

# Create blueprint
websocket_api = Blueprint('websocket_api', __name__, url_prefix='/api/websocket')

@websocket_api.route('/status', methods=['GET'])
def get_websocket_status():
    """Get WebSocket service status."""
    try:
        from flask import current_app
        websocket_service = get_websocket_service()
        if not websocket_service:
            return jsonify({
                'error': 'WebSocket service not available',
                'status': 'unavailable'
            }), 503
        
        status = websocket_service.get_status()
        # Derive active_service reliably from status payload
        active_service = 'unknown'
        if isinstance(status, dict):
            active_service = status.get('service') or ('mock_websocket' if status.get('mock_mode') else 'unknown')
        return jsonify({
            'status': 'success',
            'data': status,
            'active_service': active_service,
            'strict': bool(current_app.config.get('WEBSOCKET_STRICT_CELERY', False)),
            'preference': current_app.config.get('WEBSOCKET_SERVICE_PREFERENCE', 'auto')
        })
        
    except Exception as e:
        logger.error(f"Error getting WebSocket status: {e}")
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

@websocket_api.route('/analyses', methods=['GET'])
def get_active_analyses():
    """Get list of active analyses."""
    try:
        websocket_service = get_websocket_service()
        if not websocket_service:
            return jsonify({
                'error': 'WebSocket service not available',
                'analyses': []
            }), 503
        
        analyses = websocket_service.get_active_analyses()
        return jsonify({
            'status': 'success',
            'analyses': analyses
        })
        
    except Exception as e:
        logger.error(f"Error getting active analyses: {e}")
        return jsonify({
            'error': str(e),
            'analyses': []
        }), 500

@websocket_api.route('/analysis/start', methods=['POST'])
def start_analysis():
    """Start a new analysis via WebSocket service."""
    try:
        websocket_service = get_websocket_service()
        if not websocket_service:
            return jsonify({
                'error': 'WebSocket service not available'
            }), 503
        
        data = request.get_json()
        if not data:
            return jsonify({
                'error': 'Request data required'
            }), 400
        
        # Validate required fields
        required_fields = ['analysis_type', 'model_slug', 'app_number']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return jsonify({
                'error': f'Missing required fields: {", ".join(missing_fields)}'
            }), 400
        
        # Start analysis
        if hasattr(websocket_service, 'start_analysis'):
            analysis_id = websocket_service.start_analysis(data)
        else:
            # Fallback for mock service
            analysis_id = websocket_service.start_analysis(data)
        
        if analysis_id:
            return jsonify({
                'status': 'success',
                'analysis_id': analysis_id,
                'message': 'Analysis started successfully'
            })
        else:
            return jsonify({
                'error': 'Failed to start analysis',
                'details': 'WebSocket backend unavailable or task enqueue failed'
            }), 503
        
    except Exception as e:
        logger.error(f"Error starting analysis: {e}")
        # Map infrastructure connectivity issues to 503 (service unavailable)
        msg = str(e).lower()
        if any(tok in msg for tok in [
            'redis', 'connection refused', 'econnrefused', '10061', '111', 'timeout', 'timed out', 'connect', 'refused'
        ]):
            return jsonify({'error': 'WebSocket backend unavailable', 'details': str(e)}), 503
        return jsonify({'error': str(e)}), 500

@websocket_api.route('/analysis/<analysis_id>/cancel', methods=['POST'])
def cancel_analysis(analysis_id):
    """Cancel a running analysis."""
    try:
        websocket_service = get_websocket_service()
        if not websocket_service:
            return jsonify({
                'error': 'WebSocket service not available'
            }), 503
        
        success = websocket_service.cancel_analysis(analysis_id)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': f'Analysis {analysis_id} cancelled'
            })
        else:
            return jsonify({
                'error': f'Failed to cancel analysis {analysis_id}'
            }), 500
        
    except Exception as e:
        logger.error(f"Error cancelling analysis: {e}")
        return jsonify({
            'error': str(e)
        }), 500

@websocket_api.route('/events', methods=['GET'])
def get_events():
    """Get recent WebSocket events (for mock service debugging)."""
    try:
        websocket_service = get_websocket_service()
        if not websocket_service:
            return jsonify({
                'error': 'WebSocket service not available',
                'events': []
            }), 503
        
        # Check if this is the mock service
        if hasattr(websocket_service, 'get_event_log'):
            events = websocket_service.get_event_log()
            return jsonify({
                'status': 'success',
                'events': events
            })
        else:
            return jsonify({
                'status': 'success',
                'message': 'Real-time service active - events not logged',
                'events': []
            })
        
    except Exception as e:
        logger.error(f"Error getting events: {e}")
        return jsonify({
            'error': str(e),
            'events': []
        }), 500

@websocket_api.route('/events/clear', methods=['POST', 'GET'])
def clear_events():
    """Clear the in-memory event log for the active websocket service."""
    try:
        websocket_service = get_websocket_service()
        if not websocket_service:
            return jsonify({'error': 'WebSocket service not available'}), 503

        if hasattr(websocket_service, 'clear_event_log'):
            websocket_service.clear_event_log()  # type: ignore[attr-defined]
            return jsonify({'status': 'success', 'message': 'Event log cleared'})
        return jsonify({'status': 'noop', 'message': 'Active service does not keep an in-memory event log'})
    except Exception as e:
        logger.error(f"Error clearing events: {e}")
        return jsonify({'error': str(e)}), 500

@websocket_api.route('/broadcast', methods=['POST'])
def broadcast_message():
    """Broadcast a test message (for development/testing)."""
    try:
        websocket_service = get_websocket_service()
        if not websocket_service:
            return jsonify({
                'error': 'WebSocket service not available'
            }), 503
        
        data = request.get_json()
        if not data or 'event' not in data or 'message' not in data:
            return jsonify({
                'error': 'Event and message fields required'
            }), 400
        
        event = data['event']
        message = data['message']
        additional_data = data.get('data', {})
        
        # Broadcast the message
        websocket_service.broadcast_message(event, {
            'message': message,
            'timestamp': data.get('timestamp'),
            **additional_data
        })
        
        return jsonify({
            'status': 'success',
            'message': f'Broadcast sent: {event}'
        })
        
    except Exception as e:
        logger.error(f"Error broadcasting message: {e}")
        return jsonify({
            'error': str(e)
        }), 500

def _find_models_root() -> Optional[Path]:
    """Locate repo's misc/models directory by walking up parents."""
    try:
        for parent in Path(__file__).resolve().parents:
            candidate = parent / 'misc' / 'models'
            if candidate.exists() and candidate.is_dir():
                return candidate
    except Exception:
        pass
    return None

def _pick_available_model_slug(preferred: Optional[List[str]] = None) -> Optional[str]:
    root = _find_models_root()
    if not root:
        return None
    def has_app1(p: Path) -> bool:
        return (p / 'app1').exists()
    # Preferred list first
    if preferred:
        for slug in preferred:
            cp = root / slug
            if cp.exists() and cp.is_dir() and has_app1(cp):
                return slug
    # Fallback: first directory with app1
    for entry in sorted(root.iterdir()):
        try:
            if entry.is_dir() and has_app1(entry):
                return entry.name
        except Exception:
            continue
    return None

@websocket_api.route('/test', methods=['POST'])
def test_websocket():
    """Test WebSocket functionality with a sample analysis."""
    try:
        websocket_service = get_websocket_service()
        if not websocket_service:
            return jsonify({
                'error': 'WebSocket service not available'
            }), 503
        
        # Prefer explicit model/app from request over auto-pick
        payload = request.get_json(silent=True) or {}
        # Allow form-encoded and query params as well
        if not payload:
            payload = request.form.to_dict() if request.form else {}
        model_slug = payload.get('model_slug') or request.args.get('model_slug')
        app_number_val = payload.get('app_number') or request.args.get('app_number')
        app_number: int
        try:
            app_number = int(app_number_val) if app_number_val is not None else 1
        except (TypeError, ValueError):
            return jsonify({'error': 'app_number must be an integer'}), 400

        # If no explicit slug provided, fall back to a discoverable one
        if not model_slug:
            model_slug = _pick_available_model_slug(preferred=['anthropic_claude-3.7-sonnet', 'openai_gpt_4', 'openai_gpt-4.1']) or 'anthropic_claude-3.7-sonnet'

        # Build test payload honoring selected slug/app
        test_data = {
            'analysis_type': payload.get('analysis_type', 'security'),
            'model_slug': model_slug,
            'app_number': app_number,
            'config': payload.get('config') or {
                'tools': ['static_analysis'],
                'severity': 'medium'
            }
        }
        
        analysis_id = websocket_service.start_analysis(test_data)
        
        if analysis_id:
            return jsonify({
                'status': 'success',
                'analysis_id': analysis_id,
                'message': 'Test analysis started - check WebSocket events for progress',
                'model_slug': model_slug,
                'app_number': app_number
            })
        else:
            return jsonify({
                'error': 'Failed to start test analysis',
                'details': 'WebSocket backend unavailable or task enqueue failed'
            }), 503
        
    except Exception as e:
        logger.error(f"Error in WebSocket test: {e}")
        # Map infrastructure connectivity issues to 503 (service unavailable)
        msg = str(e).lower()
        if any(tok in msg for tok in [
            'redis', 'connection refused', 'econnrefused', '10061', '111', 'timeout', 'timed out', 'connect', 'refused'
        ]):
            return jsonify({'error': 'WebSocket backend unavailable', 'details': str(e)}), 503
        return jsonify({'error': str(e)}), 500
