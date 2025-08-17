"""
WebSocket API Routes
Provides REST endpoints for WebSocket service interaction and testing
"""

from flask import Blueprint, request, jsonify
from app.extensions import get_websocket_service
import logging

logger = logging.getLogger(__name__)

# Create blueprint
websocket_api = Blueprint('websocket_api', __name__, url_prefix='/api/websocket')

@websocket_api.route('/status', methods=['GET'])
def get_websocket_status():
    """Get WebSocket service status."""
    try:
        websocket_service = get_websocket_service()
        if not websocket_service:
            return jsonify({
                'error': 'WebSocket service not available',
                'status': 'unavailable'
            }), 503
        
        status = websocket_service.get_status()
        return jsonify({
            'status': 'success',
            'data': status
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
                'error': 'Failed to start analysis'
            }), 500
        
    except Exception as e:
        logger.error(f"Error starting analysis: {e}")
        return jsonify({
            'error': str(e)
        }), 500

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

@websocket_api.route('/test', methods=['POST'])
def test_websocket():
    """Test WebSocket functionality with a sample analysis."""
    try:
        websocket_service = get_websocket_service()
        if not websocket_service:
            return jsonify({
                'error': 'WebSocket service not available'
            }), 503
        
        # Create test analysis data
        test_data = {
            'analysis_type': 'security',
            'model_slug': 'test_model',
            'app_number': 1,
            'config': {
                'tools': ['static_analysis'],
                'severity': 'medium'
            }
        }
        
        analysis_id = websocket_service.start_analysis(test_data)
        
        if analysis_id:
            return jsonify({
                'status': 'success',
                'analysis_id': analysis_id,
                'message': 'Test analysis started - check WebSocket events for progress'
            })
        else:
            return jsonify({
                'error': 'Failed to start test analysis'
            }), 500
        
    except Exception as e:
        logger.error(f"Error in WebSocket test: {e}")
        return jsonify({
            'error': str(e)
        }), 500
