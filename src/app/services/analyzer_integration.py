"""
Analyzer Integration Layer
=========================

Integration layer for communicating with containerized analyzer services.
Handles WebSocket connections, task execution, and result processing.
"""

from app.utils.logging_config import get_logger
from app.config.config_manager import get_config
from app.services.service_locator import ServiceLocator
import asyncio
from copy import deepcopy
import json
import uuid
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timezone
from enum import Enum
import websockets
from websockets.exceptions import ConnectionClosed

from ..extensions import db
from ..models import AnalysisResult
from ..constants import AnalysisType


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
        self.connections: Dict[str, Any] = {}
        config = get_config()
        self.service_urls = {
            AnalyzerServiceType.SECURITY: config.get_analyzer_service_url('static'),  # Security uses static service
            AnalyzerServiceType.STATIC: config.get_analyzer_service_url('static'),
            AnalyzerServiceType.DYNAMIC: config.get_analyzer_service_url('dynamic'), 
            AnalyzerServiceType.PERFORMANCE: config.get_analyzer_service_url('performance'),
            AnalyzerServiceType.AI_REVIEW: config.get_analyzer_service_url('ai')
        }
        self.connection_timeouts = {
            'connect': 10,  # seconds
            'analysis': 1800,  # 30 minutes
            'heartbeat': 30  # seconds
        }
    
    async def get_connection(self, service_type: AnalyzerServiceType) -> Optional[Any]:
        """Get or create WebSocket connection to analyzer service."""
        service_key = service_type.value
        
        # Check if existing connection is still valid
        if service_key in self.connections:
            connection = self.connections[service_key]
            # Defensive check for 'closed' attribute
            if hasattr(connection, 'closed') and not connection.closed:
                try:
                    # Test connection with ping
                    await asyncio.wait_for(connection.ping(), timeout=5)
                    return connection
                except Exception as e:
                    logger.debug(f"Connection test failed for {service_key}: {e}")
                    # Remove invalid connection
                    del self.connections[service_key]
            else:
                # If 'closed' attribute is missing or connection is closed, remove it
                logger.debug(f"Removing stale or invalid connection for {service_key}")
                del self.connections[service_key]
        
        # Create new connection
        return await self._create_connection(service_type)
    
    async def _create_connection(self, service_type: AnalyzerServiceType) -> Optional[Any]:
        """Create new WebSocket connection."""
        service_key = service_type.value
        service_url = self.service_urls[service_type]
        
        try:
            logger.info(f"Connecting to {service_key} analyzer at {service_url}")
            
            # Disable keepalive pings to prevent timeouts while services perform
            # long-running blocking subprocess work. We rely on higher-level
            # request timeouts and error handling instead.
            connection = await asyncio.wait_for(
                websockets.connect(
                    service_url,
                    ping_interval=None,
                    ping_timeout=None,
                    close_timeout=20
                ),
                timeout=self.connection_timeouts['connect']
            )
            
            self.connections[service_key] = connection
            logger.info(f"Connected to {service_key} analyzer")
            
            return connection
            
        except asyncio.TimeoutError:
            logger.error(f"Timeout connecting to {service_key} analyzer")
            return None
        except ConnectionError as e:
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

            # Decide success using tolerant schema match (some services use 'success')
            def _is_success(res: dict) -> bool:
                try:
                    status = str(res.get('status', '')).lower()
                    if status in ('completed', 'success', 'ok'):
                        return True
                    # Look into nested analysis summary
                    analysis = res.get('analysis') if isinstance(res.get('analysis'), dict) else None
                    if analysis:
                        summary = analysis.get('summary') if isinstance(analysis.get('summary'), dict) else None
                        if summary and str(summary.get('analysis_status', '')).lower() in ('completed', 'success'):
                            return True
                    return False
                except Exception:
                    return False

            # Process results
            if _is_success(result):
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
        """Map analysis type to service type.

        Supports both plain string analysis types ("security", "static", "dynamic", "performance", "ai")
        and any enum values present in AnalysisType. Avoids referencing missing enum members.
        """
        at = (analysis_type or '').lower()
        # Base string mapping
        mapping: Dict[str, AnalyzerServiceType] = {
            'security': AnalyzerServiceType.SECURITY,
            'static': AnalyzerServiceType.STATIC,
            'dynamic': AnalyzerServiceType.DYNAMIC,
            'performance': AnalyzerServiceType.PERFORMANCE,
            'ai': AnalyzerServiceType.AI_REVIEW,
            'ai_review': AnalyzerServiceType.AI_REVIEW,
        }
        # Dynamically augment from AnalysisType enum if members exist
        try:
            enum_pairs = [
                ('SECURITY', AnalyzerServiceType.SECURITY),
                ('STATIC', AnalyzerServiceType.STATIC),
                ('DYNAMIC', AnalyzerServiceType.DYNAMIC),
                ('PERFORMANCE', AnalyzerServiceType.PERFORMANCE),
                ('AI_REVIEW', AnalyzerServiceType.AI_REVIEW),
            ]
            for name, svc in enum_pairs:
                member = getattr(AnalysisType, name, None)
                if member is not None:
                    try:
                        key = str(member.value).lower()
                        mapping[key] = svc
                    except Exception:
                        pass
        except Exception:
            pass
        return mapping.get(at) or mapping.get(analysis_type)
    
    def _prepare_analysis_request(self, task: Any) -> Dict[str, Any]:  # AnalysisTask
        """Prepare analysis request for analyzer service."""
        config = get_config()
        
        # Get task configuration if available
        task_config = getattr(task, 'config', {}) or {}
        
        # Fallback: Try to get config from task metadata (custom_options)
        if not task_config.get('tools_config') and hasattr(task, 'get_metadata'):
            metadata = task.get_metadata()
            custom_options = metadata.get('custom_options', {})
            # Check for tool_config (from UI) or tools_config (standard)
            tools_config = custom_options.get('tool_config') or custom_options.get('tools_config')
            if tools_config:
                # Ensure task_config is a dict we can modify
                if not isinstance(task_config, dict):
                    task_config = {}
                task_config['tools_config'] = tools_config
        
        request = {
            'request_id': str(uuid.uuid4()),
            'task_id': task.task_id,
            'action': f'run_{task.analysis_type}',
            'target': {
                'model_slug': task.target_model,
                'app_number': task.target_app_number,
                'source_path': config.get_source_path(task.target_model, task.target_app_number)
            },
            'config': {
                'tools_config': task_config.get('tools_config', {}),
                'execution_config': task_config.get('execution_config', {}),
                'output_config': task_config.get('output_config', {})
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
        connection: Any,
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
            
            try:
                while True:
                    message = await asyncio.wait_for(connection.recv(), timeout=timeout)
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
            except asyncio.TimeoutError:
                logger.error(f"Message timeout for task {task.task_id}")
                result = None
            
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
            stage = data.get('stage') or data.get('phase') or ''

            # Heuristic mapping of stages to tool names
            stage_tool_map = {
                'scanning_python': ['bandit', 'pylint', 'mypy'],
                'python_analysis': ['bandit', 'pylint', 'mypy'],
                'scanning_js': ['eslint', 'tsc'],
                'scanning_css': ['stylelint'],
            }

            # Resolve explicitly selected tools (names) from task metadata if available
            selected_tool_names: set[str] | None = None
            try:
                meta = task.get_metadata() if hasattr(task, 'get_metadata') else {}
                cand = meta.get('selected_tools')
                if not isinstance(cand, list) and isinstance(meta.get('custom_options'), dict):
                    cand = meta.get('custom_options', {}).get('selected_tools')
                if isinstance(cand, list):
                    if all(isinstance(x, str) for x in cand):
                        selected_tool_names = {x.lower() for x in cand}
                    elif all(isinstance(x, int) for x in cand):
                        try:
                            # Resolve IDs -> names via container tool registry
                            from app.engines.container_tool_registry import get_container_tool_registry
                            registry = get_container_tool_registry()
                            all_tools = registry.get_all_tools()
                            
                            # Create mapping from ID to tool name (ID based on enumeration order)
                            id_to_name = {}
                            for idx, (tool_name, tool) in enumerate(all_tools.items()):
                                id_to_name[idx + 1] = tool_name
                            
                            names: list[str] = []
                            for tid in cand:
                                tool_name = id_to_name.get(tid)
                                if tool_name:
                                    names.append(tool_name)
                            
                            selected_tool_names = {n.lower() for n in names} if names else None
                        except Exception:
                            selected_tool_names = None
            except Exception:
                selected_tool_names = None

            # Initialize per-task emitted tools cache in metadata (non-persistent ephemeral via object attr)
            if not hasattr(task, '_emitted_tool_started'):
                setattr(task, '_emitted_tool_started', set())
            emitted: set = getattr(task, '_emitted_tool_started')  # type: ignore

            from app.realtime.task_events import emit_task_event  # local import to avoid circular
            # For each stage, emit tool.started once per tool to allow UI to show pending vs running
            if stage in stage_tool_map:
                for tool_name in stage_tool_map[stage]:
                    # Honor explicit selection: if selected_tool_names provided, only emit for those tools
                    if selected_tool_names is not None and tool_name.lower() not in selected_tool_names:
                        continue
                    key = f"{tool_name}"
                    if key not in emitted:
                        emit_task_event(
                            "task.tool.started",
                            {
                                "task_id": task.task_id,
                                "tool": tool_name,
                                "stage": stage,
                                "progress_percentage": percentage,
                            },
                        )
                        emitted.add(key)
            
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
        """Process successful analysis result and preserve raw outputs."""
        try:
            # Extract result data from multiple possible shapes
            analysis_data = {}
            if isinstance(result.get('analysis'), dict):
                analysis_data = result.get('analysis')  # canonical analyzer shape
            elif isinstance(result.get('data'), dict):
                analysis_data = result.get('data')
            elif isinstance(result.get('results'), dict):
                # Wrap results under analysis key for consistency
                analysis_data = {'results': result.get('results')}

            findings = result.get('findings', [])
            metrics = result.get('metrics', {})
            
            # PRESERVE RAW TOOL OUTPUTS: Extract and store raw outputs from analyzer response
            raw_outputs = self._extract_raw_outputs_from_result(result, analysis_data or {})
            if raw_outputs:
                if analysis_data is None:
                    analysis_data = {}
                analysis_data['raw_outputs'] = raw_outputs
            
            # Construct unified payload
            payload = analysis_data or {}
            
            # Ensure critical sections exist
            if 'findings' not in payload and findings:
                payload['findings'] = findings
            if 'summary' not in payload and 'summary' in result:
                payload['summary'] = result['summary']
            if 'services' not in payload and 'services' in result:
                payload['services'] = result['services']
                
            # Store via UnifiedResultService
            try:
                unified_service = ServiceLocator.get_unified_result_service()
                unified_service.store_analysis_results(
                    task_id=task.task_id,
                    payload=payload,
                    model_slug=task.target_model,
                    app_number=task.target_app_number
                )
                logger.info(f"Stored results via UnifiedResultService for task {task.task_id}")
            except Exception as e:
                logger.error(f"Failed to store results via UnifiedResultService: {e}")
                raise

            # Update task status (UnifiedResultService doesn't set COMPLETED status)
            from app.constants import AnalysisStatus
            task.status = AnalysisStatus.COMPLETED
            
            # Store metrics if present (UnifiedResultService might not handle this specific metadata field)
            if metrics:
                metadata = task.get_metadata()
                metadata['metrics'] = metrics
                task.set_metadata(metadata)

            # Persist a normalized copy of the analyzer result into task metadata
            try:
                meta = task.get_metadata()
                # Avoid clobbering if already set by previous retry
                meta['analysis'] = analysis_data
                # Add raw transport-level envelope (non-sensitive)
                meta['result_envelope'] = {
                    'type': result.get('type'),
                    'service': result.get('service'),
                    'status': result.get('status'),
                    'timestamp': result.get('timestamp'),
                }
                task.set_metadata(meta)
            except Exception:
                pass
            
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
    
    # _extract_sarif_findings removed - functionality moved to UnifiedResultService
    
    # _store_sarif_export removed - functionality moved to UnifiedResultService
    
    # _store_findings removed - functionality moved to UnifiedResultService
    
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

    # Subprocess bridge methods for engine compatibility
    def run_security_analysis(self, model_slug: str, app_number: int, tools: Optional[List[str]] = None, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run security analysis via subprocess bridge to analyzer_manager.py."""
        return self._run_analyzer_subprocess('security', model_slug, app_number, tools=tools, options=options)
    
    def run_ai_analysis(self, model_slug: str, app_number: int, tools: Optional[List[str]] = None, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run AI analysis via subprocess bridge to analyzer_manager.py."""
        return self._run_analyzer_subprocess('ai', model_slug, app_number, tools=tools, options=options)
    
    def run_performance_test(self, model_slug: str, app_number: int, test_config: Optional[Dict[str, Any]] = None, tools: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run performance test via subprocess bridge to analyzer_manager.py.

        tools: Optional list of tool names to gate which performance tools run (e.g., ["aiohttp", "ab"]).
        """
        return self._run_analyzer_subprocess('performance', model_slug, app_number, config=test_config, tools=tools)
    
    def run_static_analysis(self, model_slug: str, app_number: int, tools: Optional[List[str]] = None, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run static analysis via subprocess bridge to analyzer_manager.py."""
        return self._run_analyzer_subprocess('static', model_slug, app_number, tools=tools, options=options)
    
    def run_dynamic_analysis(self, model_slug: str, app_number: int, options: Optional[Dict[str, Any]] = None, tools: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run dynamic analysis via subprocess bridge to analyzer_manager.py.

        tools: Optional list of tool names to gate which dynamic tools run (e.g., ["curl", "nmap", "zap"]).
        """
        return self._run_analyzer_subprocess('dynamic', model_slug, app_number, options=options, tools=tools)
    
    def _transform_analyzer_output_to_task_format(self, analyzer_output: Dict[str, Any], requested_tools: List[str]) -> Dict[str, Any]:
        """Transform analyzer output into the format expected by task_execution_service.
        
        Converts the nested analyzer JSON structure into a flat tool_results format.
        """
        
        # Extract the analysis section from the analyzer output
        analysis = analyzer_output.get('results', {}).get('analysis', {})
        if not analysis:
            # Fallback to look for analysis at top level
            analysis = analyzer_output.get('analysis', {})
        
        # For performance/dynamic analyzers, use results directly if no analysis section
        if not analysis and 'results' in analyzer_output:
            analysis = analyzer_output['results']
        
        tool_results = {}
        tools_requested = requested_tools or []

        def _ensure_tool_requested(name: Any) -> None:
            if isinstance(name, str) and name not in tools_requested:
                tools_requested.append(name)

        def _merge_tool_run_details(entry: Dict[str, Any], run_data: Dict[str, Any]) -> None:
            if not isinstance(run_data, dict):
                return

            duration_hint = run_data.get('duration_seconds') or run_data.get('duration')
            if duration_hint and not entry.get('duration_seconds'):
                try:
                    entry['duration_seconds'] = float(duration_hint)
                except (TypeError, ValueError):
                    entry['duration_seconds'] = duration_hint

            if 'executed' not in entry and 'executed' in run_data:
                entry['executed'] = run_data['executed']

            if 'status' not in entry and 'status' in run_data:
                entry['status'] = run_data['status']

            if 'command_line' not in entry and run_data.get('command'):
                entry['command_line'] = run_data.get('command')

            exit_code = run_data.get('exit_code')
            if exit_code is None:
                exit_code = run_data.get('returncode')
            if exit_code is not None and 'exit_code' not in entry:
                entry['exit_code'] = exit_code

            if 'error' not in entry and run_data.get('error'):
                entry['error'] = run_data['error']

            if 'raw_output' in entry and entry['raw_output']:
                return

            raw_output = run_data.get('raw_output') or run_data.get('stdout')
            if not raw_output and isinstance(run_data.get('commands'), list):
                chunks: List[str] = []
                for idx, cmd_data in enumerate(run_data['commands']):
                    if not isinstance(cmd_data, dict):
                        continue
                    cmd_parts = cmd_data.get('cmd')
                    if isinstance(cmd_parts, list):
                        cmd_text = ' '.join(str(part) for part in cmd_parts)
                    else:
                        cmd_text = str(cmd_parts) if cmd_parts else ''
                    lines: List[str] = []
                    if cmd_text:
                        lines.append(f"$ {cmd_text}")
                    if cmd_data.get('exit_code') is not None:
                        lines.append(f"exit_code: {cmd_data['exit_code']}")
                    stdout = (cmd_data.get('stdout') or '').strip()
                    if stdout:
                        lines.append('stdout:')
                        lines.append(stdout)
                    stderr = (cmd_data.get('stderr') or '').strip()
                    if stderr:
                        lines.append('stderr:')
                        lines.append(stderr)
                    if lines:
                        chunks.append('\n'.join(lines))
                if chunks:
                    raw_output = '\n\n'.join(chunks)

            if raw_output:
                entry['raw_output'] = raw_output

        def _merge_tool_entry(target: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
            if not updates:
                return target

            if not target:
                target.update(updates)
                return target

            for key, value in updates.items():
                if value is None:
                    continue

                if key == 'issues' and isinstance(value, list):
                    existing = target.get('issues')
                    if isinstance(existing, list):
                        existing.extend(value)
                        target['issues'] = existing
                        target['total_issues'] = len(existing)
                    else:
                        target['issues'] = list(value)
                        target['total_issues'] = len(value)
                    continue

                if key == 'severity_breakdown' and isinstance(value, dict):
                    existing_sb = target.get('severity_breakdown')
                    if isinstance(existing_sb, dict):
                        merged = existing_sb.copy()
                        for sev, count in value.items():
                            try:
                                merged[sev] = merged.get(sev, 0) + int(count)
                            except (TypeError, ValueError):
                                merged[sev] = merged.get(sev, 0)
                        target['severity_breakdown'] = merged
                    else:
                        target['severity_breakdown'] = value
                    continue

                if key == 'raw_details' and isinstance(value, dict):
                    existing_raw = target.get('raw_details')
                    if isinstance(existing_raw, dict):
                        merged_raw = existing_raw.copy()
                        merged_raw.update(value)
                        target['raw_details'] = merged_raw
                    else:
                        target['raw_details'] = value
                    continue

                if key in ('raw_output', 'stdout', 'stderr', 'command_line', 'error', 'message', 'summary'):
                    if not target.get(key) and value not in ('', [], {}):
                        target[key] = value
                    continue

                if key in ('status', 'executed'):
                    target[key] = value
                    continue

                if key == 'total_issues':
                    if target.get('total_issues') is None:
                        target['total_issues'] = value
                    continue

                if key == 'duration_seconds':
                    if target.get('duration_seconds') is None:
                        target['duration_seconds'] = value
                    continue

                if key == 'exit_code':
                    if target.get('exit_code') is None:
                        target['exit_code'] = value
                    continue

                if key == 'metrics' and isinstance(value, dict):
                    if not isinstance(target.get('metrics'), dict):
                        target['metrics'] = value
                    continue

                if key == 'config_used' and value:
                    if not target.get('config_used'):
                        target['config_used'] = value
                    continue

                if key == 'recommendations' and value:
                    if not target.get('recommendations'):
                        target['recommendations'] = value
                    continue

                target.setdefault(key, value)
            return target

        def _build_tool_entry(tool_name: str, tool_data: Any, *, run_details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
            entry: Dict[str, Any] = {}
            data = tool_data if isinstance(tool_data, dict) else {}

            status = str(data.get('status', 'unknown'))
            entry['status'] = status

            executed = data.get('executed')
            if executed is None:
                executed = status not in ('not_available', 'skipped', 'error', 'failed', 'unknown')
            entry['executed'] = bool(executed)

            duration = data.get('duration_seconds')
            if duration is None:
                duration = data.get('duration')
            if duration is not None:
                try:
                    entry['duration_seconds'] = float(duration)
                except (TypeError, ValueError):
                    entry['duration_seconds'] = duration

            total_issues = data.get('total_issues')
            issues_collection = data.get('issues')
            if issues_collection is None and isinstance(data.get('results'), list):
                issues_collection = data.get('results')

            if isinstance(issues_collection, list) and issues_collection:
                entry['issues'] = issues_collection
                if total_issues is None:
                    total_issues = len(issues_collection)

            if isinstance(total_issues, int):
                entry['total_issues'] = total_issues

            severity_breakdown = data.get('severity_breakdown')
            if isinstance(severity_breakdown, dict) and severity_breakdown:
                entry['severity_breakdown'] = severity_breakdown

            metrics = data.get('metrics')
            if isinstance(metrics, dict) and metrics:
                entry['metrics'] = metrics

            config_used = data.get('config_used')
            if config_used:
                entry['config_used'] = config_used

            recommendations = data.get('recommendations') or data.get('references') or data.get('fixes')
            if recommendations:
                entry['recommendations'] = recommendations

            for field in ('raw_output', 'stdout', 'stderr', 'command_line', 'error', 'message', 'summary'):
                value = data.get(field)
                if value not in (None, '', [], {}):
                    entry[field] = value

            exit_code = data.get('exit_code')
            if exit_code is None:
                exit_code = data.get('returncode')
            if exit_code is not None:
                entry['exit_code'] = exit_code

            if run_details:
                _merge_tool_run_details(entry, run_details)

            if data:
                entry['raw_details'] = deepcopy(data)

            return entry
        
        # Calculate analysis duration (fallback to reasonable estimate)
        analysis_duration = 1.0  # Default fallback
        if 'metadata' in analyzer_output:
            timestamp_str = analyzer_output['metadata'].get('timestamp', '')
            if timestamp_str:
                try:
                    # Calculate duration from timestamp to now
                    from datetime import datetime
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    duration_delta = datetime.now() - timestamp.replace(tzinfo=None)
                    analysis_duration = max(0.1, duration_delta.total_seconds())
                except Exception:
                    pass
        
        # Surface dynamic/performance summary maps when available
        if isinstance(analysis, dict):
            if isinstance(analysis.get('tools_used'), list):
                for tool_name in analysis['tools_used']:
                    _ensure_tool_requested(tool_name)

            results_section = analysis.get('results') if isinstance(analysis.get('results'), dict) else {}
            tool_runs_section = {}
            if isinstance(results_section, dict):
                candidate_runs = results_section.get('tool_runs')
                if isinstance(candidate_runs, dict):
                    tool_runs_section = candidate_runs

            summary_section = analysis.get('tool_results')
            if isinstance(summary_section, dict):
                for tool_name, tool_data in summary_section.items():
                    if not isinstance(tool_name, str) or not isinstance(tool_data, dict):
                        continue

                    _ensure_tool_requested(tool_name)

                    run_details = tool_runs_section.get(tool_name)
                    entry = _build_tool_entry(tool_name, tool_data, run_details=run_details)

                    if tool_name in tool_results:
                        _merge_tool_entry(tool_results[tool_name], entry)
                    else:
                        tool_results[tool_name] = entry

        # Extract tool results from the analysis structure
        if isinstance(analysis, dict) and 'results' in analysis:
            results = analysis['results']
            
            # Handle Python tools (like bandit)
            if 'python' in results and isinstance(results['python'], dict):
                for tool_name, tool_data in results['python'].items():
                    if tool_name == 'tool_status':
                        continue  # Skip meta information
                    
                    if isinstance(tool_data, dict):
                        run_details = tool_runs_section.get(tool_name)
                        entry = _build_tool_entry(tool_name, tool_data, run_details=run_details)

                        if 'duration_seconds' not in entry or entry.get('duration_seconds') in (None, 0):
                            num_tools = len([t for t in results.get('python', {}).keys() if t != 'tool_status'])
                            tool_duration = analysis_duration / max(1, num_tools)
                            entry['duration_seconds'] = round(tool_duration, 2)

                        if 'total_issues' not in entry:
                            total_issues = tool_data.get('total_issues')
                            if total_issues is None and isinstance(tool_data.get('issues'), list):
                                total_issues = len(tool_data['issues'])
                            if total_issues is not None:
                                entry['total_issues'] = total_issues

                        if tool_name in tool_results:
                            _merge_tool_entry(tool_results[tool_name], entry)
                        else:
                            tool_results[tool_name] = entry

                        if tool_name not in tools_requested:
                            tools_requested.append(tool_name)
            
            # Handle other language tools if present
            for lang in ['javascript', 'css', 'html']:
                if lang in results and isinstance(results[lang], dict):
                    for tool_name, tool_data in results[lang].items():
                        if isinstance(tool_data, dict) and 'status' in tool_data:
                            entry = _build_tool_entry(tool_name, tool_data)

                            if 'duration_seconds' not in entry or entry.get('duration_seconds') in (None, 0):
                                entry['duration_seconds'] = round(analysis_duration / max(1, len(tools_requested) or 1), 2)

                            if 'total_issues' not in entry and tool_data.get('total_issues') is not None:
                                entry['total_issues'] = tool_data.get('total_issues')

                            if tool_name in tool_results:
                                _merge_tool_entry(tool_results[tool_name], entry)
                            else:
                                tool_results[tool_name] = entry
            
            # Handle AI analyzer tools (requirements-scanner, etc.)
            if 'tools_used' in analysis and 'requirement_checks' in results:
                # AI analyzer has a different structure - extract tool results from analysis data
                ai_tools = analysis.get('tools_used', [])
                requirements_data = results.get('requirement_checks', [])
                summary_data = results.get('summary', {})
                
                for tool_name in ai_tools:
                    if tool_name in ['requirements-scanner', 'requirements-analyzer', 'ai-requirements']:
                        # Calculate issues from requirements that were not met
                        total_requirements = summary_data.get('total_requirements', 0)
                        requirements_met = summary_data.get('requirements_met', 0)
                        issues_found = total_requirements - requirements_met
                        
                        # Build raw output from requirement checks
                        raw_output_lines = ["AI Requirements Analysis Results", "=" * 40]
                        raw_output_lines.append(f"Total Requirements: {total_requirements}")
                        raw_output_lines.append(f"Requirements Met: {requirements_met}")
                        raw_output_lines.append(f"Requirements Not Met: {issues_found}")
                        raw_output_lines.append(f"Compliance: {summary_data.get('compliance_percentage', 0):.1f}%")
                        raw_output_lines.append("")
                        
                        for req_check in requirements_data:
                            result = req_check.get('result', {})
                            requirement = req_check.get('requirement', 'Unknown requirement')
                            met = result.get('met', False)
                            confidence = result.get('confidence', 'UNKNOWN')
                            explanation = result.get('explanation', 'No explanation provided')
                            
                            status_icon = "✓" if met else "✗"
                            raw_output_lines.append(f"{status_icon} [{confidence}] {requirement}")
                            if explanation:
                                raw_output_lines.append(f"    {explanation}")
                            raw_output_lines.append("")
                        
                        raw_output = "\n".join(raw_output_lines)
                        
                        entry = {
                            'status': 'success',
                            'duration_seconds': round(analysis_duration, 2),
                            'total_issues': issues_found,
                            'executed': True,
                            'raw_output': raw_output,
                            'command_line': f'ai-analyzer analyze {analysis.get("model_slug", "")} {analysis.get("app_number", "")}',
                            'exit_code': 0,
                            'raw_details': {
                                'requirements_summary': summary_data,
                                'requirement_checks': requirements_data
                            }
                        }

                        if tool_name in tool_results:
                            _merge_tool_entry(tool_results[tool_name], entry)
                        else:
                            tool_results[tool_name] = entry
                        
                        # Add tool to requested list if not already there
                        if tool_name not in tools_requested:
                            tools_requested.append(tool_name)
        
        # Handle performance analyzer results (structure: results.results.{url}.{tool})
        elif isinstance(analyzer_output.get('results', {}).get('results'), dict):
            # This is likely a performance or dynamic analyzer
            url_results = analyzer_output['results']['results']
            
            for url, url_data in url_results.items():
                if isinstance(url_data, dict):
                    for tool_name, tool_data in url_data.items():
                        # Skip non-tool entries like 'connectivity'
                        if tool_name in ['connectivity']:
                            continue
                            
                        if isinstance(tool_data, dict) and tool_name in tools_requested:
                            # Extract performance tool results
                            status = tool_data.get('status', 'unknown')
                            
                            # Calculate issues based on failures
                            total_issues = 0
                            if 'failures' in tool_data:
                                total_issues = tool_data.get('failures', 0)
                            elif 'errors' in tool_data:
                                total_issues = len(tool_data.get('errors', []))
                            
                            # Build raw output for performance tools
                            raw_output_lines = [f"{tool_name.upper()} Performance Test Results", "=" * 50]
                            raw_output_lines.append(f"URL: {url}")
                            raw_output_lines.append(f"Status: {status}")
                            
                            if 'requests' in tool_data:
                                raw_output_lines.append(f"Total Requests: {tool_data.get('requests', 0)}")
                            if 'failures' in tool_data:
                                raw_output_lines.append(f"Failures: {tool_data.get('failures', 0)}")
                            if 'avg_response_time' in tool_data:
                                raw_output_lines.append(f"Average Response Time: {tool_data.get('avg_response_time', 0):.2f}ms")
                            if 'requests_per_second' in tool_data:
                                raw_output_lines.append(f"Requests/Second: {tool_data.get('requests_per_second', 0):.2f}")
                            
                            # Add configuration if available
                            if 'configuration' in tool_data:
                                config = tool_data['configuration']
                                raw_output_lines.append("\nConfiguration:")
                                for key, value in config.items():
                                    raw_output_lines.append(f"  {key}: {value}")
                            
                            raw_output = "\n".join(raw_output_lines)
                            
                            entry = {
                                'status': 'success' if status == 'success' else 'error',
                                'duration_seconds': round(analysis_duration, 2),
                                'total_issues': total_issues,
                                'executed': True,
                                'raw_output': raw_output,
                                'command_line': f'{tool_name} --target {url}',
                                'exit_code': 0 if status == 'success' else 1,
                                'raw_details': {
                                    'target_url': url,
                                    'tool_output': tool_data
                                }
                            }

                            if tool_name in tool_results:
                                _merge_tool_entry(tool_results[tool_name], entry)
                            else:
                                tool_results[tool_name] = entry
        
        # Handle dynamic analyzer results (structure may vary)
        elif isinstance(analyzer_output.get('results', {}), dict):
            results_data = analyzer_output.get('results', {})
            
            # Check for tools_used and scan results pattern
            if 'tools_used' in results_data and not any(k in results_data for k in ['python', 'requirement_checks']):
                tools_used = results_data.get('tools_used', [])
                
                for tool_name in tools_used:
                    if tool_name in tools_requested:
                        # Look for scan results or similar data
                        scan_results = []
                        vulnerabilities_found = 0
                        
                        # Check various possible result locations
                        for key, value in results_data.items():
                            if isinstance(value, dict) and 'vulnerabilities' in str(value).lower():
                                if isinstance(value, dict) and 'count' in value:
                                    vulnerabilities_found += value.get('count', 0)
                                elif isinstance(value, list):
                                    vulnerabilities_found += len(value)
                                    scan_results.extend(value)
                        
                        # Build raw output for dynamic tools
                        raw_output_lines = [f"{tool_name.upper()} Dynamic Analysis Results", "=" * 50]
                        
                        if 'target_urls' in results_data:
                            raw_output_lines.append(f"Target URLs: {', '.join(results_data['target_urls'])}")
                        
                        raw_output_lines.append(f"Vulnerabilities Found: {vulnerabilities_found}")
                        
                        if scan_results:
                            raw_output_lines.append("\nDetailed Results:")
                            for result in scan_results[:10]:  # Limit to first 10 results
                                raw_output_lines.append(f"  - {str(result)}")
                            if len(scan_results) > 10:
                                raw_output_lines.append(f"  ... and {len(scan_results) - 10} more")
                        
                        raw_output = "\n".join(raw_output_lines)
                        
                        entry = {
                            'status': 'success',
                            'duration_seconds': round(analysis_duration, 2),
                            'total_issues': vulnerabilities_found,
                            'executed': True,
                            'raw_output': raw_output,
                            'command_line': f'{tool_name} --dynamic-scan',
                            'exit_code': 0,
                            'raw_details': {
                                'scan_results': scan_results,
                                'vulnerabilities_found': vulnerabilities_found,
                                'target_urls': results_data.get('target_urls')
                            }
                        }

                        if tool_name in tool_results:
                            _merge_tool_entry(tool_results[tool_name], entry)
                        else:
                            tool_results[tool_name] = entry
        
        # Deduplicate requested tools while preserving order
        tools_requested = list(dict.fromkeys(tools_requested))

        # Ensure all requested tools have results (create placeholder for missing ones)
        for tool_name in tools_requested:
            if tool_name not in tool_results:
                reason = f'Tool {tool_name} was not executed by analyzer'
                tool_results[tool_name] = {
                    'status': 'not_available',
                    'duration_seconds': 0.0,
                    'total_issues': 0,
                    'executed': False,
                    'error': reason,
                    'not_executed_reason': 'analyzer_did_not_return_result',
                    'requested': True,
                    'issues': [],
                    'severity_breakdown': {},
                    'raw_details': {
                        'status': 'not_available',
                        'reason': reason,
                        'requested': True
                    }
                }
        
        # Build the transformed response
        transformed = {
            'status': 'completed',
            'tools_requested': tools_requested,
            'tool_results': tool_results,
            'analysis_duration': analysis_duration,
            'original_analyzer_output': analyzer_output  # Preserve original for debugging
        }
        
        return transformed

    def _run_analyzer_subprocess(self, analysis_type: str, model_slug: str, app_number: int, **kwargs) -> Dict[str, Any]:
        """Run analyzer_manager.py via subprocess with proper UTF-8 handling."""
        import subprocess
        import os
        import json
        import sys
        
        logger.info(
            "[ANALYZER-SUBPROCESS] Starting subprocess: type=%s, model=%s, app=%s, tools=%s",
            analysis_type, model_slug, app_number, kwargs.get('tools')
        )
        
        try:
            # Build command - use absolute path to Python executable
            analyzer_dir = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'analyzer')
            
            # Get the same Python executable that's running the worker
            python_exe = sys.executable
            
            cmd = [
                python_exe, 'analyzer_manager.py', 'analyze',
                model_slug, str(app_number), analysis_type
            ]
            
            # Add tools if specified
            if 'tools' in kwargs and kwargs['tools']:
                cmd.extend(['--tools'] + kwargs['tools'])
            
            logger.info(
                "[ANALYZER-SUBPROCESS] Command: %s (cwd=%s)",
                ' '.join(cmd), analyzer_dir
            )
            logger.debug(
                "[ANALYZER-SUBPROCESS] Python executable: %s",
                python_exe
            )
            
            # Set up environment with UTF-8 encoding and JSON mode
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            env['PYTHONUNBUFFERED'] = '1'  # Disable output buffering
            env['ANALYZER_JSON'] = '1'  # Enable JSON output mode
            
            # Run with proper UTF-8 encoding
            logger.debug("[ANALYZER-SUBPROCESS] Executing subprocess.run (timeout=1800s)...")
            result = subprocess.run(
                cmd,
                cwd=analyzer_dir,
                capture_output=True,
                text=True,
                encoding='utf-8',
                env=env,
                timeout=1800  # 30 minute timeout
            )
            
            logger.info(
                "[ANALYZER-SUBPROCESS] Process completed: returncode=%s, stdout_len=%s, stderr_len=%s",
                result.returncode, len(result.stdout or ''), len(result.stderr or '')
            )
            
            if analysis_type == 'ai':
                try:
                    logger.info(
                        "AI subprocess completed rc=%s stdout_bytes=%s stderr_bytes=%s", 
                        result.returncode, len(result.stdout or ''), len(result.stderr or '')
                    )
                    if result.stdout:
                        logger.debug("AI subprocess raw stdout (first 500 chars): %s", (result.stdout[:500]))
                    if result.stderr:
                        logger.debug("AI subprocess stderr (first 300 chars): %s", (result.stderr[:300]))
                except Exception:
                    pass

            if result.returncode != 0:
                logger.error(
                    "[ANALYZER-SUBPROCESS] FAILED: returncode=%s, stderr=%s",
                    result.returncode, result.stderr[:500] if result.stderr else "No stderr"
                )
                return {
                    'status': 'error',
                    'error': f"Analyzer process failed: {result.stderr}",
                    'stdout': result.stdout,
                    'stderr': result.stderr
                }
            
            # Parse JSON output (with defensive recovery for noisy stdout)
            try:
                parsed_stdout = json.loads(result.stdout)
                logger.info("Analyzer subprocess completed successfully (type=%s tools=%s)", analysis_type, kwargs.get('tools'))
            except json.JSONDecodeError as e:
                trimmed = (result.stdout or '').lstrip()
                fallback_output = None
                if trimmed:
                    brace_idx = trimmed.find('{')
                    bracket_idx = trimmed.find('[')
                    candidates = [idx for idx in (brace_idx, bracket_idx) if idx != -1]
                    if candidates:
                        start = min(candidates)
                        try:
                            fallback_output = json.loads(trimmed[start:])
                            logger.warning(
                                "Recovered analyzer JSON by trimming %s leading chars (type=%s)",
                                start, analysis_type
                            )
                        except json.JSONDecodeError:
                            fallback_output = None
                if fallback_output is None:
                    logger.error(f"Failed to parse analyzer output as JSON: {e}")
                    return {
                        'status': 'error',
                        'error': f"Failed to parse JSON output: {e}",
                        'stdout': result.stdout,
                        'stderr': result.stderr
                    }
                parsed_stdout = fallback_output

            # Transform analyzer output into task execution service format
            transformed_output = self._transform_analyzer_output_to_task_format(parsed_stdout, kwargs.get('tools', []))
            if analysis_type == 'ai':
                try:
                    logger.debug(
                        "AI transformed output keys=%s tool_results=%s", 
                        list(transformed_output.keys()), 
                        list(transformed_output.get('tool_results', {}).keys())
                    )
                except Exception:
                    pass
            return transformed_output
                
        except subprocess.TimeoutExpired:
            logger.error("Analyzer subprocess timed out")
            return {
                'status': 'error',
                'error': 'Analysis timed out after 30 minutes'
            }
        except Exception as e:
            logger.error(f"Analyzer subprocess error: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }

    def _extract_raw_outputs_from_result(self, result: Dict[str, Any], analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract raw tool outputs from analyzer result for preservation."""
        raw_outputs = {}
        
        try:
            # Look for raw outputs in multiple possible locations
            candidates = [
                result,
                analysis_data,
                result.get('data', {}),
                result.get('analysis', {}),
                analysis_data.get('results', {}),
                analysis_data.get('tool_results', {}),
            ]
            
            for candidate in candidates:
                if not isinstance(candidate, dict):
                    continue
                    
                # Look for tool_results or similar structures
                for key in ['tool_results', 'tool_outputs', 'tools', 'results']:
                    tool_data = candidate.get(key)
                    if isinstance(tool_data, dict):
                        for tool_name, tool_result in tool_data.items():
                            if isinstance(tool_result, dict):
                                # Extract any raw output fields
                                output_info = {}
                                
                                # Look for various output field names
                                for field in ['raw_output', 'output', 'stdout', 'stderr', 'response', 'result']:
                                    if field in tool_result and tool_result[field]:
                                        output_info[field] = tool_result[field]
                                
                                # Also capture command and execution info
                                for field in ['command_line', 'command', 'cmd', 'exit_code', 'returncode', 'duration', 'error']:
                                    if field in tool_result:
                                        output_info[field] = tool_result[field]
                                
                                if output_info:
                                    raw_outputs[tool_name] = output_info
                
                # Also check for direct tool names as keys (legacy format)
                common_tools = ['bandit', 'pylint', 'eslint', 'safety', 'semgrep', 'mypy', 'jshint', 'vulture',
                               'zap', 'curl', 'nmap', 'locust', 'ab', 'aiohttp', 'requirements-scanner', 'flake8']
                
                for tool_name in common_tools:
                    if tool_name in candidate:
                        tool_data = candidate[tool_name]
                        if isinstance(tool_data, dict):
                            output_info = {}
                            for field in ['raw_output', 'output', 'stdout', 'stderr', 'response', 'result', 
                                        'command_line', 'command', 'exit_code', 'error']:
                                if field in tool_data and tool_data[field] is not None:
                                    output_info[field] = tool_data[field]
                            
                            if output_info and tool_name not in raw_outputs:
                                raw_outputs[tool_name] = output_info
                                
        except Exception as e:
            logger.warning(f"Error extracting raw outputs: {e}")
            
        return raw_outputs


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
                'type': 'health_check'
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
                        'available_tools': response.get('available_tools', []),
                        'last_check': datetime.now(timezone.utc).isoformat()
                    }
                else:
                    health_data = {
                        'status': 'unhealthy',
                        'error': response.get('error', 'Unknown error'),
                        'available_tools': response.get('available_tools', []),
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


# ---- Convenience helpers for synchronous contexts -------------------------
def get_available_toolsets(timeout_seconds: float = 3.0) -> Dict[str, list]:
    """Best-effort snapshot of available tools per analyzer service.

    Attempts a quick health check of all analyzer services to retrieve their
    reported 'available_tools' lists. Uses a short timeout to avoid blocking
    request handlers; falls back to cached values when available.

    Returns a mapping like:
      { 'static-analyzer': ['bandit', 'pylint', ...], 'dynamic-analyzer': [...], ... }
    """
    try:
        # Use cached values first
        cached = health_monitor.get_cached_health_status() or {}

        # Prepare async call with reduced connect timeout
        # Temporarily lower connect timeout for a snappier check
        original_timeout = analysis_executor.connection_manager.connection_timeouts.get('connect', 10)  # type: ignore[attr-defined]
        analysis_executor.connection_manager.connection_timeouts['connect'] = 2  # type: ignore[attr-defined]
        try:
            async def _check_all():
                return await health_monitor.check_all_services()

            # Run with overall timeout cap
            results: Dict[str, Dict[str, Any]] = asyncio.run(asyncio.wait_for(_check_all(), timeout=timeout_seconds))  # type: ignore[arg-type]
        except Exception:
            # Fall back to cached if async fails or times out
            results = cached
        finally:
            # Restore original connect timeout
            analysis_executor.connection_manager.connection_timeouts['connect'] = original_timeout  # type: ignore[attr-defined]

        # Build simple mapping from analyzer responses
        mapping: Dict[str, list] = {}
        for key, data in (results or {}).items():
            # Normalize keys to service names used elsewhere
            # AnalyzerServiceType values are: 'security', 'static', 'dynamic', 'performance', 'ai_review'
            service_map = {
                'static': 'static-analyzer',
                'security': 'static-analyzer',  # security maps to static analyzer
                'dynamic': 'dynamic-analyzer',
                'performance': 'performance-tester',
                'ai_review': 'ai-analyzer',
            }
            svc = service_map.get(key, key)
            tools = []
            try:
                tools = list((data or {}).get('available_tools', []) or [])
            except Exception:
                tools = []
            # Merge (prefer non-empty)
            if svc in mapping:
                if not mapping[svc] and tools:
                    mapping[svc] = tools
            else:
                mapping[svc] = tools

        # Fallback: if a service is healthy but provided no tool list, infer from Container Tool Registry
        try:
            from app.engines.container_tool_registry import get_container_tool_registry
            registry = get_container_tool_registry()
            all_tools = registry.get_all_tools()
            
            # Build a quick group of enabled tools by service (container)
            by_service: Dict[str, list] = {}
            for tool_name, tool in all_tools.items():
                if tool.available:  # Only include available tools
                    container_name = tool.container.value
                    if container_name not in by_service:
                        by_service[container_name] = []
                    by_service[container_name].append(tool_name)

            # Known service keys to check
            known_svcs = ['static-analyzer', 'dynamic-analyzer', 'performance-tester', 'ai-analyzer']
            # Reverse-map analyzer result keys for health check lookup
            reverse_map = {
                'static-analyzer': 'static',
                'dynamic-analyzer': 'dynamic',
                'performance-tester': 'performance',
                'ai-analyzer': 'ai_review',
            }
            for svc in known_svcs:
                # If mapping missing or empty AND corresponding analyzer status was healthy, infer names from registry
                if (svc not in mapping) or (not mapping.get(svc)):
                    analyzer_key = reverse_map.get(svc, svc)
                    svc_status = (results or {}).get(analyzer_key, {}) or {}
                    if str(svc_status.get('status')).lower() == 'healthy':
                        inferred = by_service.get(svc) or []
                        if inferred:
                            mapping[svc] = inferred
        except Exception:
            # Best-effort fallback only; ignore errors
            pass

        return mapping
    except Exception:
        return {}


# Initialize global instances
connection_manager = ConnectionManager()
analysis_executor = AnalysisExecutor(connection_manager)
health_monitor = AnalyzerHealthMonitor(connection_manager)


def get_analyzer_integration():
    """Get the analyzer integration instance."""
    return analysis_executor