"""
WebSocket Integration Service
============================

Enhanced WebSocket integration for real-time analyzer communication
and dashboard updates. Provides seamless connection to analyzer services
with progress updates, status monitoring, and error handling.
"""

import asyncio
import logging
import threading
from typing import Any, Dict, Optional, Callable
from datetime import datetime, timezone
from pathlib import Path

from ..extensions import socketio
from .analyzer_integration import get_analyzer_integration

# Import analyzer protocol if available
try:
    import sys
    analyzer_path = Path(__file__).parent.parent.parent.parent / 'analyzer'
    sys.path.insert(0, str(analyzer_path))
    
    from shared.client import AnalyzerClient
    from shared.protocol import (
        AnalysisRequest, SecurityAnalysisRequest, PerformanceTestRequest,
        AnalysisType, MessageType
    )
    ANALYZER_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Analyzer protocol not available: {e}")
    ANALYZER_AVAILABLE = False

logger = logging.getLogger(__name__)


class WebSocketIntegration:
    """Enhanced WebSocket integration for real-time analyzer communication."""
    
    def __init__(self):
        self.analyzer_client: Optional[AnalyzerClient] = None
        self.connected = False
        self.connection_thread = None
        self.active_analyses: Dict[str, Dict] = {}
        self.progress_callbacks: Dict[str, Callable] = {}
        self.analyzer_integration = get_analyzer_integration()
        
        # Default analyzer gateway URI
        self.gateway_uri = "ws://localhost:8765"
        
        # SocketIO event handlers
        self._register_socketio_handlers()
    
    def _register_socketio_handlers(self):
        """Register SocketIO event handlers for client communication."""
        
        @socketio.on('connect')
        def handle_connect():
            logger.info(f"Client connected: {id}")
            socketio.emit('connection_status', {
                'connected': True,
                'analyzer_available': ANALYZER_AVAILABLE,
                'analyzer_connected': self.connected
            })
        
        @socketio.on('disconnect')
        def handle_disconnect():
            logger.info("Client disconnected")
        
        @socketio.on('request_analyzer_status')
        def handle_status_request():
            """Handle client request for analyzer status."""
            status = self.get_analyzer_status()
            socketio.emit('analyzer_status', status)
        
        @socketio.on('start_analysis')
        def handle_start_analysis(data):
            """Handle client request to start analysis."""
            try:
                analysis_id = self.start_analysis_async(data)
                socketio.emit('analysis_started', {
                    'analysis_id': analysis_id,
                    'status': 'started'
                })
            except Exception as e:
                logger.error(f"Failed to start analysis: {e}")
                socketio.emit('analysis_error', {
                    'error': str(e),
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })
        
        @socketio.on('cancel_analysis')
        def handle_cancel_analysis(data):
            """Handle client request to cancel analysis."""
            analysis_id = data.get('analysis_id')
            if analysis_id:
                success = self.cancel_analysis(analysis_id)
                socketio.emit('analysis_cancelled', {
                    'analysis_id': analysis_id,
                    'success': success
                })
    
    async def connect_to_analyzer(self) -> bool:
        """Connect to the analyzer WebSocket gateway."""
        if not ANALYZER_AVAILABLE:
            logger.warning("Analyzer protocol not available")
            return False
        
        try:
            self.analyzer_client = AnalyzerClient(self.gateway_uri)
            
            # Register progress handler
            self.analyzer_client.register_handler(
                MessageType.PROGRESS_UPDATE,
                self._handle_progress_update
            )
            
            # Register result handler
            self.analyzer_client.register_handler(
                MessageType.ANALYSIS_RESULT,
                self._handle_analysis_result
            )
            
            # Register error handler
            self.analyzer_client.register_handler(
                MessageType.ERROR,
                self._handle_error
            )
            
            success = await self.analyzer_client.connect()
            
            if success:
                self.connected = True
                logger.info("Connected to analyzer gateway")
                
                # Notify clients
                socketio.emit('analyzer_connected', {
                    'connected': True,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to connect to analyzer: {e}")
            self.connected = False
            return False
    
    async def disconnect_from_analyzer(self):
        """Disconnect from the analyzer WebSocket gateway."""
        if self.analyzer_client:
            await self.analyzer_client.disconnect()
            self.analyzer_client = None
        
        self.connected = False
        
        # Notify clients
        socketio.emit('analyzer_disconnected', {
            'connected': False,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    
    def start_connection_thread(self):
        """Start the WebSocket connection in a separate thread."""
        if self.connection_thread and self.connection_thread.is_alive():
            return
        
        def run_connection():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.connect_to_analyzer())
                # Keep the connection alive
                loop.run_until_complete(self._keep_alive())
            except Exception as e:
                logger.error(f"Connection thread error: {e}")
            finally:
                loop.close()
        
        self.connection_thread = threading.Thread(target=run_connection, daemon=True)
        self.connection_thread.start()
    
    async def _keep_alive(self):
        """Keep the WebSocket connection alive."""
        while self.connected and self.analyzer_client:
            try:
                await asyncio.sleep(30)  # Send heartbeat every 30 seconds
                if self.analyzer_client:
                    # Could implement heartbeat here if needed
                    pass
            except Exception as e:
                logger.error(f"Keep-alive error: {e}")
                break
    
    async def _handle_progress_update(self, message):
        """Handle progress update from analyzer."""
        try:
            data = message.data
            analysis_id = data.get('analysis_id')
            
            if analysis_id:
                # Update active analysis tracking
                if analysis_id in self.active_analyses:
                    self.active_analyses[analysis_id].update(data)
                
                # Emit to connected clients
                socketio.emit('analysis_progress', {
                    'analysis_id': analysis_id,
                    'progress': data.get('progress', 0),
                    'stage': data.get('stage', ''),
                    'message': data.get('message', ''),
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })
                
                # Call registered callback if exists
                if analysis_id in self.progress_callbacks:
                    try:
                        self.progress_callbacks[analysis_id](data)
                    except Exception as e:
                        logger.error(f"Progress callback error: {e}")
        
        except Exception as e:
            logger.error(f"Error handling progress update: {e}")
    
    async def _handle_analysis_result(self, message):
        """Handle analysis result from analyzer."""
        try:
            data = message.data
            analysis_id = data.get('analysis_id')
            
            if analysis_id:
                # Update active analysis tracking
                if analysis_id in self.active_analyses:
                    self.active_analyses[analysis_id]['status'] = 'completed'
                    self.active_analyses[analysis_id]['result'] = data
                
                # Emit to connected clients
                socketio.emit('analysis_completed', {
                    'analysis_id': analysis_id,
                    'result': data,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })
                
                # Clean up tracking
                self.active_analyses.pop(analysis_id, None)
                self.progress_callbacks.pop(analysis_id, None)
        
        except Exception as e:
            logger.error(f"Error handling analysis result: {e}")
    
    async def _handle_error(self, message):
        """Handle error message from analyzer."""
        try:
            data = message.data
            correlation_id = message.correlation_id
            
            # Update active analysis if applicable
            if correlation_id and correlation_id in self.active_analyses:
                self.active_analyses[correlation_id]['status'] = 'failed'
                self.active_analyses[correlation_id]['error'] = data
            
            # Emit to connected clients
            socketio.emit('analysis_error', {
                'analysis_id': correlation_id,
                'error': data,
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
            
            # Clean up tracking
            if correlation_id:
                self.active_analyses.pop(correlation_id, None)
                self.progress_callbacks.pop(correlation_id, None)
        
        except Exception as e:
            logger.error(f"Error handling error message: {e}")
    
    def start_analysis_async(self, analysis_data: Dict[str, Any]) -> str:
        """
        Start analysis asynchronously through WebSocket.
        
        Args:
            analysis_data: Analysis configuration
            
        Returns:
            Analysis ID
        """
        if not ANALYZER_AVAILABLE:
            # Fallback to direct analyzer integration
            return self._start_analysis_fallback(analysis_data)
        
        if not self.connected:
            # Try to connect first
            self.start_connection_thread()
            # For now, fallback to direct integration
            return self._start_analysis_fallback(analysis_data)
        
        try:
            # Create appropriate request based on analysis type
            request = self._create_analysis_request(analysis_data)
            analysis_id = f"analysis_{datetime.now().timestamp()}"
            
            # Track analysis
            self.active_analyses[analysis_id] = {
                'status': 'queued',
                'started_at': datetime.now(timezone.utc),
                'request': analysis_data
            }
            
            # Start analysis in background
            def run_analysis():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self._submit_analysis(request, analysis_id))
                except Exception as e:
                    logger.error(f"Analysis submission error: {e}")
                finally:
                    loop.close()
            
            thread = threading.Thread(target=run_analysis, daemon=True)
            thread.start()
            
            return analysis_id
        
        except Exception as e:
            logger.error(f"Failed to start async analysis: {e}")
            # Fallback to direct integration
            return self._start_analysis_fallback(analysis_data)
    
    def _start_analysis_fallback(self, analysis_data: Dict[str, Any]) -> str:
        """Fallback to direct analyzer integration."""
        analysis_type = analysis_data.get('type', 'security')
        model_slug = str(analysis_data.get('model_slug', ''))
        app_number = int(analysis_data.get('app_number', 1))
        
        analysis_id = f"fallback_{analysis_type}_{datetime.now().timestamp()}"
        
        # Use the existing analyzer integration
        try:
            if analysis_type == 'security':
                result = self.analyzer_integration.run_security_analysis(
                    model_slug, app_number,
                    tools=analysis_data.get('tools'),
                    options=analysis_data.get('options')
                )
            elif analysis_type == 'performance':
                result = self.analyzer_integration.run_performance_test(
                    model_slug, app_number,
                    test_config=analysis_data.get('config')
                )
            elif analysis_type == 'static':
                result = self.analyzer_integration.run_static_analysis(
                    model_slug, app_number,
                    tools=analysis_data.get('tools'),
                    options=analysis_data.get('options')
                )
            elif analysis_type == 'ai':
                result = self.analyzer_integration.run_ai_analysis(
                    model_slug, app_number,
                    analysis_types=analysis_data.get('analysis_types'),
                    options=analysis_data.get('options')
                )
            else:
                raise ValueError(f"Unknown analysis type: {analysis_type}")
            
            # Emit completion event
            socketio.emit('analysis_completed', {
                'analysis_id': analysis_id,
                'result': result,
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
            
        except Exception as e:
            logger.error(f"Fallback analysis failed: {e}")
            socketio.emit('analysis_error', {
                'analysis_id': analysis_id,
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
        
        return analysis_id
    
    def _create_analysis_request(self, analysis_data: Dict[str, Any]) -> AnalysisRequest:
        """Create appropriate analysis request object."""
        analysis_type_map = {
            'security': AnalysisType.SECURITY_PYTHON,
            'performance': AnalysisType.PERFORMANCE_LOAD,
            'static': AnalysisType.CODE_QUALITY_PYTHON,
            'ai': AnalysisType.AI_CODE_REVIEW
        }
        
        base_params = {
            'model': analysis_data.get('model_slug', ''),
            'app_number': analysis_data.get('app_number', 1),
            'analysis_type': analysis_type_map.get(analysis_data.get('type'), AnalysisType.SECURITY_PYTHON),
            'source_path': analysis_data.get('source_path', ''),
            'options': analysis_data.get('options', {}),
            'timeout': analysis_data.get('timeout', 300),
            'priority': analysis_data.get('priority', 1)
        }
        
        analysis_type = analysis_data.get('type', 'security')
        
        if analysis_type == 'security':
            return SecurityAnalysisRequest(
                **base_params,
                tools=analysis_data.get('tools', ['bandit', 'safety']),
                scan_depth=analysis_data.get('scan_depth', 'standard'),
                include_tests=analysis_data.get('include_tests', False),
                exclude_patterns=analysis_data.get('exclude_patterns', [])
            )
        elif analysis_type == 'performance':
            return PerformanceTestRequest(
                **base_params,
                target_url=analysis_data.get('target_url', ''),
                users=analysis_data.get('users', 10),
                spawn_rate=analysis_data.get('spawn_rate', 2),
                duration=analysis_data.get('duration', 60),
                test_scenario=analysis_data.get('test_scenario', 'basic_load')
            )
        else:
            return AnalysisRequest(**base_params)
    
    async def _submit_analysis(self, request: AnalysisRequest, analysis_id: str):
        """Submit analysis request to analyzer."""
        try:
            if self.analyzer_client:
                result = await self.analyzer_client.request_analysis(request, timeout=request.timeout)
                
                # Handle result
                if result.type == MessageType.ANALYSIS_RESULT:
                    await self._handle_analysis_result(result)
                elif result.type == MessageType.ERROR:
                    await self._handle_error(result)
            
        except Exception as e:
            logger.error(f"Failed to submit analysis: {e}")
            # Create error message
            socketio.emit('analysis_error', {
                'analysis_id': analysis_id,
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
    
    def cancel_analysis(self, analysis_id: str) -> bool:
        """Cancel running analysis."""
        try:
            if analysis_id in self.active_analyses:
                # Update status
                self.active_analyses[analysis_id]['status'] = 'cancelled'
                
                # If connected to analyzer, send cancel request
                if self.connected and self.analyzer_client:
                    def cancel_async():
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            loop.run_until_complete(
                                self.analyzer_client.cancel_analysis(analysis_id)
                            )
                        except Exception as e:
                            logger.error(f"Cancel request error: {e}")
                        finally:
                            loop.close()
                    
                    thread = threading.Thread(target=cancel_async, daemon=True)
                    thread.start()
                
                # Clean up tracking
                self.active_analyses.pop(analysis_id, None)
                self.progress_callbacks.pop(analysis_id, None)
                
                return True
            
            return False
        
        except Exception as e:
            logger.error(f"Failed to cancel analysis: {e}")
            return False
    
    def get_analyzer_status(self) -> Dict[str, Any]:
        """Get comprehensive analyzer status."""
        try:
            # Get basic status from analyzer integration
            base_status = self.analyzer_integration.get_services_status()
            
            # Enhance with WebSocket status
            enhanced_status = {
                'websocket_connected': self.connected,
                'analyzer_available': ANALYZER_AVAILABLE,
                'active_analyses': len(self.active_analyses),
                'analyses': list(self.active_analyses.keys()),
                'base_status': base_status,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            return enhanced_status
        
        except Exception as e:
            logger.error(f"Failed to get analyzer status: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    def get_active_analyses(self) -> Dict[str, Dict]:
        """Get currently active analyses."""
        return self.active_analyses.copy()
    
    def register_progress_callback(self, analysis_id: str, callback: Callable):
        """Register callback for analysis progress updates."""
        self.progress_callbacks[analysis_id] = callback


# Global WebSocket integration instance
_websocket_integration = None

def get_websocket_integration() -> WebSocketIntegration:
    """Get the global WebSocket integration instance."""
    global _websocket_integration
    if _websocket_integration is None:
        _websocket_integration = WebSocketIntegration()
    return _websocket_integration


def emit_status_update(status_type: str, data: Dict[str, Any]):
    """Emit status update to connected clients."""
    socketio.emit('status_update', {
        'type': status_type,
        'data': data,
        'timestamp': datetime.now(timezone.utc).isoformat()
    })


def emit_test_update(test_id: str, status: str, progress: float = None, message: str = None):
    """Emit test status update to connected clients."""
    update_data = {
        'test_id': test_id,
        'status': status,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    
    if progress is not None:
        update_data['progress'] = progress
    
    if message:
        update_data['message'] = message
    
    socketio.emit('test_update', update_data)


def emit_system_health(health_data: Dict[str, Any]):
    """Emit system health update to connected clients."""
    socketio.emit('system_health', {
        'health': health_data,
        'timestamp': datetime.now(timezone.utc).isoformat()
    })
