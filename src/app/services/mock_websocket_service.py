"""
Mock WebSocket Integration Service
Provides WebSocket-like functionality without requiring flask-socketio
for development and testing when real-time features are not available.
"""

from app.utils.logging_config import get_logger
from typing import Dict, Any, Optional, List
import os
from datetime import datetime
from threading import Lock, Thread
import time
import json

logger = get_logger('mock_websocket')

class MockWebSocketService:
    """
    Mock WebSocket service that provides the same interface as the real
    WebSocket service but stores events in memory for testing/development.
    """
    
    def __init__(self):
        self.active_analyses: Dict[str, Dict[str, Any]] = {}
        self.connected_clients: List[str] = []
        self.event_log: List[Dict[str, Any]] = []
        self.analyzer_status = {
            'websocket_connected': True,
            'analyzer_available': True,
            'active_analyses': 0,
            'last_update': None
        }
        
        # Thread safety
        self._lock = Lock()
        
        # Start background monitoring
        self._start_monitoring()
        
        logger.info("Mock WebSocket Service initialized")
    
    def emit(self, event: str, data: Dict[str, Any], room: Optional[str] = None):
        """Mock emit that logs events instead of sending to clients."""
        event_entry = {
            'event': event,
            'data': data,
            'room': room,
            'timestamp': datetime.now().isoformat()
        }
        
        with self._lock:
            self.event_log.append(event_entry)
            # Keep only last 100 events
            if len(self.event_log) > 100:
                self.event_log = self.event_log[-100:]
        
        logger.debug(f"Mock emit: {event} - {json.dumps(data, default=str)[:100]}...")
    
    def start_analysis(self, data: Dict[str, Any]) -> Optional[str]:
        """Start an analysis and return analysis ID."""
        try:
            # Extract analysis parameters
            analysis_type = data.get('analysis_type')
            model_slug = data.get('model_slug')
            app_number = data.get('app_number')
            config = data.get('config', {})
            
            if not all([analysis_type, model_slug, app_number is not None]):
                raise ValueError("Missing required analysis parameters")
            
            # Generate analysis ID
            analysis_id = f"{model_slug}_{app_number}_{analysis_type}_{int(time.time())}"
            
            # Store analysis info
            with self._lock:
                self.active_analyses[analysis_id] = {
                    'id': analysis_id,
                    'type': analysis_type,
                    'model_slug': model_slug,
                    'app_number': app_number,
                    'config': config,
                    'status': 'running',
                    'progress': 0,
                    'start_time': datetime.now().isoformat(),
                    'last_update': datetime.now().isoformat()
                }
                
                self.analyzer_status['active_analyses'] = len(self.active_analyses)
            
            # Emit started event
            self.emit('analysis_started', {
                'analysis_id': analysis_id,
                'status': 'started',
                'timestamp': datetime.now().isoformat()
            })
            
            # Start the simulation
            self._simulate_analysis(analysis_id)
            
            logger.info(f"Started mock analysis: {analysis_id}")
            return analysis_id
            
        except Exception as e:
            logger.error(f"Error starting mock analysis: {e}")
            return None
    
    def cancel_analysis(self, analysis_id: str) -> bool:
        """Cancel an active analysis."""
        try:
            with self._lock:
                if analysis_id in self.active_analyses:
                    self.active_analyses[analysis_id]['status'] = 'cancelled'
                    self.analyzer_status['active_analyses'] = len([
                        a for a in self.active_analyses.values() 
                        if a['status'] == 'running'
                    ])
            
            self.emit('analysis_cancelled', {
                'analysis_id': analysis_id,
                'success': True,
                'timestamp': datetime.now().isoformat()
            })
            
            logger.info(f"Cancelled mock analysis: {analysis_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling mock analysis: {e}")
            return False
    
    def _simulate_analysis(self, analysis_id: str):
        """Simulate analysis progress for demonstration."""
        def run_simulation():
            try:
                # Simulate progress updates
                for progress in range(0, 101, 20):
                    time.sleep(1)  # Faster simulation for testing
                    
                    with self._lock:
                        if analysis_id not in self.active_analyses:
                            break
                        
                        analysis = self.active_analyses[analysis_id]
                        if analysis['status'] != 'running':
                            break
                        
                        analysis['progress'] = progress
                        analysis['last_update'] = datetime.now().isoformat()
                    
                    # Emit progress update
                    self.emit('analysis_progress', {
                        'analysis_id': analysis_id,
                        'progress': progress,
                        'stage': f"Processing step {progress // 20 + 1}",
                        'message': f"Mock analysis {progress}% complete",
                        'timestamp': datetime.now().isoformat()
                    })
                
                # Complete the analysis
                with self._lock:
                    if analysis_id in self.active_analyses:
                        self.active_analyses[analysis_id]['status'] = 'completed'
                        self.active_analyses[analysis_id]['progress'] = 100
                        self.active_analyses[analysis_id]['end_time'] = datetime.now().isoformat()
                        
                        self.analyzer_status['active_analyses'] = len([
                            a for a in self.active_analyses.values() 
                            if a['status'] == 'running'
                        ])
                
                # Emit completion
                self.emit('analysis_completed', {
                    'analysis_id': analysis_id,
                    'result': {
                        'success': True,
                        'summary': 'Mock analysis completed successfully',
                        'metrics': {
                            'total_issues': 3,
                            'critical_issues': 0,
                            'warnings': 3
                        }
                    },
                    'timestamp': datetime.now().isoformat()
                })
                
                logger.info(f"Completed mock analysis: {analysis_id}")
                
            except Exception as e:
                logger.error(f"Error in mock analysis simulation: {e}")
                
                # Emit error
                self.emit('analysis_error', {
                    'analysis_id': analysis_id,
                    'error': {
                        'message': str(e),
                        'type': 'execution_error'
                    },
                    'timestamp': datetime.now().isoformat()
                })
        
        # Run simulation in background thread
        thread = Thread(target=run_simulation, daemon=True)
        thread.start()
    
    def _update_analyzer_status(self):
        """Update analyzer status information."""
        try:
            # Mock status update
            running_analyses = [
                a for a in self.active_analyses.values() 
                if a['status'] == 'running'
            ]
            
            self.analyzer_status.update({
                'websocket_connected': True,
                'analyzer_available': True,
                'active_analyses': len(running_analyses),
                'last_update': datetime.now().isoformat(),
                'services': {
                    'static-analyzer': {'status': 'healthy', 'port': 2001},
                    'dynamic-analyzer': {'status': 'healthy', 'port': 2002},
                    'performance-tester': {'status': 'healthy', 'port': 2003},
                    'ai-analyzer': {'status': 'healthy', 'port': 2004}
                }
            })
            
        except Exception as e:
            logger.error(f"Error updating mock analyzer status: {e}")
    
    def _start_monitoring(self):
        """Start background monitoring of analyzer services."""
        def monitor():
            while True:
                try:
                    time.sleep(30)  # Update every 30 seconds
                    self._update_analyzer_status()
                    
                    # Emit status update
                    self.emit('status_update', {
                        'type': 'analyzer_status',
                        'data': self.analyzer_status
                    })
                    
                    # Emit system health update
                    self.emit('system_health', {
                        'health': {
                            'status': 'healthy',
                            'services': self.analyzer_status.get('services', {})
                        },
                        'timestamp': datetime.now().isoformat()
                    })
                    
                except Exception as e:
                    logger.error(f"Error in mock monitoring loop: {e}")
        
        # Start monitoring thread
        monitor_thread = Thread(target=monitor, daemon=True)
        monitor_thread.start()
        logger.info("Started mock background monitoring")
    
    def broadcast_message(self, event: str, data: Dict[str, Any]):
        """Broadcast message to all connected clients."""
        self.emit(event, data)
    
    def send_to_analysis_room(self, analysis_id: str, event: str, data: Dict[str, Any]):
        """Send message to clients subscribed to specific analysis."""
        self.emit(event, data, room=f"analysis_{analysis_id}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current service status."""
        with self._lock:
            return {
                'connected_clients': len(self.connected_clients),
                'active_analyses': len(self.active_analyses),
                'analyzer_status': self.analyzer_status,
                'service_health': 'healthy',
                'mock_mode': True,
                'service': 'mock_websocket'
            }
    
    def get_active_analyses(self) -> List[Dict[str, Any]]:
        """Get list of active analyses."""
        with self._lock:
            return list(self.active_analyses.values())
    
    def get_event_log(self) -> List[Dict[str, Any]]:
        """Get recent events for debugging."""
        with self._lock:
            return list(self.event_log)

    def clear_event_log(self) -> None:
        """Clear the in-memory event log (useful for smoke/E2E runs)."""
        with self._lock:
            self.event_log.clear()


# Global service instance
_mock_service: Optional[MockWebSocketService] = None

def initialize_mock_websocket_service() -> MockWebSocketService:
    """Initialize the mock WebSocket service."""
    # Enforce strict mode: do not allow mock service when explicitly disabled
    if os.environ.get('WEBSOCKET_STRICT_CELERY', 'false').lower() == 'true':
        raise RuntimeError("WEBSOCKET_STRICT_CELERY=true: Mock WebSocket service is disabled")

    global _mock_service
    _mock_service = MockWebSocketService()
    return _mock_service

def get_mock_websocket_service() -> Optional[MockWebSocketService]:
    """Get the mock WebSocket service instance."""
    return _mock_service

def broadcast_analysis_update(analysis_id: str, event: str, data: Dict[str, Any]):
    """Convenience function to broadcast analysis updates."""
    if _mock_service:
        _mock_service.send_to_analysis_room(analysis_id, event, data)
        _mock_service.broadcast_message(event, {**data, 'analysis_id': analysis_id})

def broadcast_system_update(event: str, data: Dict[str, Any]):
    """Convenience function to broadcast system updates."""
    if _mock_service:
        _mock_service.broadcast_message(event, data)
