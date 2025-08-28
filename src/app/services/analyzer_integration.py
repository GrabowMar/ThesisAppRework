"""
Analyzer Integration Layer
=========================

Integration layer for communicating with containerized analyzer services.
Handles WebSocket connections, task execution, and result processing.
"""

from app.utils.logging_config import get_logger
import asyncio
import json
import uuid
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timezone
from enum import Enum
import websockets
from websockets.exceptions import ConnectionClosed, InvalidStatusCode

from ..extensions import db
# Temporarily commented out due to missing models
# from ..models import (
#     Any,  # AnalysisTask AnalysisResult, AnalysisStatus, AnalysisType
# )


logger = get_logger('analyzer_integration')


class AnalyzerServiceType(Enum):
    """Types of analyzer services."""
    SECURITY = "security"
    STATIC = "static"
    DYNAMIC = "dynamic"
    PERFORMANCE = "performance"
    AI_REVIEW = "ai_review"


class ConnectionManager:
    """Manages WebSocket connections to analyzer services."""
    
    def __init__(self):
        self.connections: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.service_urls = {
            AnalyzerServiceType.SECURITY: "ws://localhost:2001",
            AnalyzerServiceType.STATIC: "ws://localhost:2001",
            AnalyzerServiceType.DYNAMIC: "ws://localhost:2002", 
            AnalyzerServiceType.PERFORMANCE: "ws://localhost:2003",
            AnalyzerServiceType.AI_REVIEW: "ws://localhost:2004"
        }
        self.connection_timeouts = {
            'connect': 10,  # seconds
            'analysis': 1800,  # 30 minutes
            'heartbeat': 30  # seconds
        }
    
    async def get_connection(self, service_type: AnalyzerServiceType) -> Optional[websockets.WebSocketServerProtocol]:
        """Get or create WebSocket connection to analyzer service."""
        service_key = service_type.value
        
        # Check if existing connection is still valid
        if service_key in self.connections:
            connection = self.connections[service_key]
            if not connection.closed:
                try:
                    # Test connection with ping
                    await asyncio.wait_for(connection.ping(), timeout=5)
                    return connection
                except Exception as e:
                    logger.debug(f"Connection test failed for {service_key}: {e}")
                    # Remove invalid connection
                    del self.connections[service_key]
        
        # Create new connection
        return await self._create_connection(service_type)
    
    async def _create_connection(self, service_type: AnalyzerServiceType) -> Optional[websockets.WebSocketServerProtocol]:
        """Create new WebSocket connection."""
        service_key = service_type.value
        service_url = self.service_urls[service_type]
        
        try:
            logger.info(f"Connecting to {service_key} analyzer at {service_url}")
            
            connection = await asyncio.wait_for(
                websockets.connect(
                    service_url,
                    ping_interval=self.connection_timeouts['heartbeat'],
                    ping_timeout=10,
                    close_timeout=10
                ),
                timeout=self.connection_timeouts['connect']
            )
            
            self.connections[service_key] = connection
            logger.info(f"Connected to {service_key} analyzer")
            
            return connection
            
        except asyncio.TimeoutError:
            logger.error(f"Timeout connecting to {service_key} analyzer")
            return None
        except (ConnectionError, InvalidStatusCode) as e:
            logger.error(f"Failed to connect to {service_key} analyzer: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error connecting to {service_key}: {e}")
            return None
    
    async def close_connection(self, service_type: AnalyzerServiceType):
        """Close connection to analyzer service."""
        service_key = service_type.value
        if service_key in self.connections:
            connection = self.connections[service_key]
            try:
                await connection.close()
            except Exception as e:
                logger.debug(f"Error closing connection to {service_key}: {e}")
            finally:
                del self.connections[service_key]
    
    async def close_all_connections(self):
        """Close all analyzer connections."""
        for service_type in AnalyzerServiceType:
            await self.close_connection(service_type)


class AnalysisExecutor:
    """Executes analysis tasks on analyzer services."""
    
    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager
        self.active_analyses: Dict[str, Dict[str, Any]] = {}
    
    async def execute_analysis(
        self,
        task: Any,  # AnalysisTask
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Execute analysis task on appropriate analyzer service."""
        try:
            # Determine service type
            service_type = self._get_service_type(task.analysis_type)
            if not service_type:
                raise ValueError(f"Unknown analysis type: {task.analysis_type}")
            
            logger.info(f"Executing {task.analysis_type} analysis for task {task.task_id}")
            
            # Mark task as started
            task.mark_started()
            db.session.commit()
            
            # Register active analysis
            self.active_analyses[task.task_id] = {
                'task': task,
                'service_type': service_type,
                'started_at': datetime.now(timezone.utc),
                'progress_callback': progress_callback
            }
            
            # Get connection
            connection = await self.connection_manager.get_connection(service_type)
            if not connection:
                raise ConnectionError(f"Could not connect to {service_type.value} analyzer")
            
            # Prepare analysis request
            request = self._prepare_analysis_request(task)
            
            # Send request and handle response
            result = await self._send_analysis_request(connection, request, task, progress_callback)
            
            # Process results
            if result['status'] == 'completed':
                await self._process_successful_result(task, result)
            else:
                await self._process_failed_result(task, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Analysis execution failed for task {task.task_id}: {e}")
            await self._process_failed_result(task, {'error': str(e), 'status': 'failed'})
            raise
        finally:
            # Clean up
            if task.task_id in self.active_analyses:
                del self.active_analyses[task.task_id]
    
    def _get_service_type(self, analysis_type: str) -> Optional[AnalyzerServiceType]:
        """Map analysis type to service type."""
        mapping = {
            AnalysisType.SECURITY.value: AnalyzerServiceType.SECURITY,
            AnalysisType.STATIC.value: AnalyzerServiceType.STATIC,
            AnalysisType.DYNAMIC.value: AnalyzerServiceType.DYNAMIC,
            AnalysisType.PERFORMANCE.value: AnalyzerServiceType.PERFORMANCE,
            AnalysisType.AI_REVIEW.value: AnalyzerServiceType.AI_REVIEW
        }
        return mapping.get(analysis_type)
    
    def _prepare_analysis_request(self, task: Any) -> Dict[str, Any]:  # AnalysisTask
        """Prepare analysis request for analyzer service."""
        config = task.get_config()
        
        request = {
            'request_id': str(uuid.uuid4()),
            'task_id': task.task_id,
            'action': f'run_{task.analysis_type}',
            'target': {
                'model_slug': task.model_slug,
                'app_number': task.app_number,
                'source_path': f'/app/sources/{task.model_slug}/app{task.app_number}'
            },
            'config': {
                'tools_config': config.get('tools_config', {}),
                'execution_config': config.get('execution_config', {}),
                'output_config': config.get('output_config', {})
            },
            'options': {
                'timeout': task.estimated_duration or 600,
                'priority': task.priority,
                'return_detailed_results': True
            },
            'metadata': {
                'created_at': task.created_at.isoformat() if task.created_at else None,
                'started_at': datetime.now(timezone.utc).isoformat()
            }
        }
        
        return request
    
    async def _send_analysis_request(
        self,
        connection: websockets.WebSocketServerProtocol,
        request: Dict[str, Any],
        task: Any,  # AnalysisTask
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Send analysis request and handle response."""
        try:
            # Send request
            await connection.send(json.dumps(request))
            logger.debug(f"Sent analysis request for task {task.task_id}")
            
            # Handle response messages
            result = None
            timeout = request['options']['timeout']
            
            async for message in asyncio.wait_for(connection, timeout=timeout):
                try:
                    data = json.loads(message)
                    message_type = data.get('type', 'unknown')
                    
                    if message_type == 'progress':
                        await self._handle_progress_message(data, task, progress_callback)
                    elif message_type == 'result':
                        result = data
                        break
                    elif message_type == 'error':
                        result = data
                        break
                    elif message_type == 'log':
                        await self._handle_log_message(data, task)
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON message from analyzer: {e}")
                    continue
            
            if result is None:
                raise TimeoutError("No result received from analyzer")
            
            return result
            
        except asyncio.TimeoutError:
            logger.error(f"Analysis timeout for task {task.task_id}")
            return {
                'status': 'failed',
                'error': 'Analysis timeout',
                'error_type': 'timeout'
            }
        except ConnectionClosed:
            logger.error(f"Connection closed during analysis for task {task.task_id}")
            return {
                'status': 'failed',
                'error': 'Connection lost during analysis',
                'error_type': 'connection_error'
            }
    
    async def _handle_progress_message(
        self,
        data: Dict[str, Any],
        task: Any,  # AnalysisTask
        progress_callback: Optional[Callable] = None
    ):
        """Handle progress update from analyzer."""
        try:
            percentage = data.get('percentage', 0)
            message = data.get('message', '')
            
            # Update task progress
            task.update_progress(percentage, message)
            db.session.commit()
            
            # Call progress callback
            if progress_callback:
                await progress_callback(task.task_id, percentage, message)
            
            logger.debug(f"Task {task.task_id} progress: {percentage}% - {message}")
            
        except Exception as e:
            logger.error(f"Error handling progress message: {e}")
    
    async def _handle_log_message(self, data: Dict[str, Any], task: Any):
        """Handle log message from analyzer."""
        try:
            log_level = data.get('level', 'info')
            log_message = data.get('message', '')
            timestamp = data.get('timestamp', datetime.now(timezone.utc).isoformat())
            
            # Append to task logs
            current_logs = task.logs or ""
            new_log = f"[{timestamp}] {log_level.upper()}: {log_message}\n"
            task.logs = current_logs + new_log
            
            # Limit log size (keep last 10KB)
            if len(task.logs) > 10240:
                task.logs = task.logs[-10240:]
            
            db.session.commit()
            
        except Exception as e:
            logger.error(f"Error handling log message: {e}")
    
    async def _process_successful_result(self, task: Any, result: Dict[str, Any]):
        """Process successful analysis result."""
        try:
            # Extract result data
            analysis_data = result.get('data', {})
            findings = result.get('findings', [])
            metrics = result.get('metrics', {})
            
            # Update task with results
            task.mark_completed(analysis_data)
            
            # Store detailed findings
            if findings:
                await self._store_findings(task, findings)
            
            # Store metrics
            if metrics:
                metadata = task.get_metadata()
                metadata['metrics'] = metrics
                task.set_metadata(metadata)
            
            db.session.commit()
            logger.info(f"Successfully processed results for task {task.task_id}")
            
        except Exception as e:
            logger.error(f"Error processing successful result for task {task.task_id}: {e}")
            # Mark as failed if we can't process the results
            task.mark_failed(f"Result processing error: {str(e)}")
            db.session.commit()
    
    async def _process_failed_result(self, task: Any, result: Dict[str, Any]):
        """Process failed analysis result."""
        try:
            error_message = result.get('error', 'Unknown error')
            error_type = result.get('error_type', 'unknown')
            
            # Update task status
            task.mark_failed(error_message)
            
            # Store error details in metadata
            metadata = task.get_metadata()
            metadata['error_details'] = {
                'error_type': error_type,
                'error_message': error_message,
                'failed_at': datetime.now(timezone.utc).isoformat()
            }
            task.set_metadata(metadata)
            
            db.session.commit()
            logger.warning(f"Analysis failed for task {task.task_id}: {error_message}")
            
        except Exception as e:
            logger.error(f"Error processing failed result for task {task.task_id}: {e}")
    
    async def _store_findings(self, task: Any, findings: List[Dict[str, Any]]):
        """Store detailed analysis findings."""
        try:
            for finding_data in findings:
                finding = AnalysisResult(
                    task_id=task.id,
                    result_type=finding_data.get('type', 'finding'),
                    severity=finding_data.get('severity', 'low'),
                    category=finding_data.get('category', 'general'),
                    title=finding_data.get('title', ''),
                    description=finding_data.get('description', ''),
                    file_path=finding_data.get('file_path'),
                    line_number=finding_data.get('line_number'),
                    code_snippet=finding_data.get('code_snippet'),
                    score=finding_data.get('score'),
                    confidence=finding_data.get('confidence'),
                    impact=finding_data.get('impact'),
                    recommendation=finding_data.get('recommendation'),
                    tool_name=finding_data.get('tool_name'),
                    rule_id=finding_data.get('rule_id')
                )
                
                # Store additional details
                if 'details' in finding_data:
                    finding.set_details(finding_data['details'])
                
                if 'external_references' in finding_data:
                    finding.set_external_references(finding_data['external_references'])
                
                db.session.add(finding)
            
            logger.debug(f"Stored {len(findings)} findings for task {task.task_id}")
            
        except Exception as e:
            logger.error(f"Error storing findings for task {task.task_id}: {e}")
            raise
    
    async def cancel_analysis(self, task_id: str) -> bool:
        """Cancel running analysis."""
        try:
            if task_id not in self.active_analyses:
                return False
            
            analysis_info = self.active_analyses[task_id]
            service_type = analysis_info['service_type']
            
            # Get connection
            connection = await self.connection_manager.get_connection(service_type)
            if connection:
                # Send cancel request
                cancel_request = {
                    'request_id': str(uuid.uuid4()),
                    'action': 'cancel_analysis',
                    'task_id': task_id
                }
                
                await connection.send(json.dumps(cancel_request))
                logger.info(f"Sent cancel request for task {task_id}")
            
            # Clean up
            del self.active_analyses[task_id]
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling analysis for task {task_id}: {e}")
            return False


class AnalyzerHealthMonitor:
    """Monitors health of analyzer services."""
    
    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager
        self.health_status: Dict[str, Dict[str, Any]] = {}
    
    async def check_service_health(self, service_type: AnalyzerServiceType) -> Dict[str, Any]:
        """Check health of specific analyzer service."""
        try:
            connection = await self.connection_manager.get_connection(service_type)
            if not connection:
                return {
                    'status': 'unhealthy',
                    'error': 'Cannot connect to service',
                    'last_check': datetime.now(timezone.utc).isoformat()
                }
            
            # Send health check request
            health_request = {
                'request_id': str(uuid.uuid4()),
                'action': 'health_check'
            }
            
            await connection.send(json.dumps(health_request))
            
            # Wait for response with timeout
            try:
                response_message = await asyncio.wait_for(connection.recv(), timeout=10)
                response = json.loads(response_message)
                
                if response.get('status') == 'healthy':
                    health_data = {
                        'status': 'healthy',
                        'version': response.get('version', 'unknown'),
                        'uptime': response.get('uptime', 0),
                        'resource_usage': response.get('resource_usage', {}),
                        'last_check': datetime.now(timezone.utc).isoformat()
                    }
                else:
                    health_data = {
                        'status': 'unhealthy',
                        'error': response.get('error', 'Unknown error'),
                        'last_check': datetime.now(timezone.utc).isoformat()
                    }
                
                self.health_status[service_type.value] = health_data
                return health_data
                
            except asyncio.TimeoutError:
                return {
                    'status': 'unhealthy',
                    'error': 'Health check timeout',
                    'last_check': datetime.now(timezone.utc).isoformat()
                }
            
        except Exception as e:
            logger.error(f"Health check failed for {service_type.value}: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'last_check': datetime.now(timezone.utc).isoformat()
            }
    
    async def check_all_services(self) -> Dict[str, Dict[str, Any]]:
        """Check health of all analyzer services."""
        health_results = {}
        
        for service_type in AnalyzerServiceType:
            health_results[service_type.value] = await self.check_service_health(service_type)
        
        return health_results
    
    def get_cached_health_status(self) -> Dict[str, Dict[str, Any]]:
        """Get cached health status."""
        return self.health_status.copy()


# Initialize global instances
connection_manager = ConnectionManager()
analysis_executor = AnalysisExecutor(connection_manager)
health_monitor = AnalyzerHealthMonitor(connection_manager)


def get_analyzer_integration():
    """Get the analyzer integration instance."""
    return analysis_executor