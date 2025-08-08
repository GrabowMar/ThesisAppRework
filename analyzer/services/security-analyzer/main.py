"""
Security Analyzer Service
========================

WebSocket-based security analysis service using modern tools like Bandit, Safety, and PyLint.
Provides real-time progress updates and comprehensive security analysis.
"""
import asyncio
import logging
import os
import time
import json
from pathlib import Path
from typing import Dict, List
import websockets
from dataclasses import asdict

import sys
sys.path.append('/app')

from shared.protocol import (
    WebSocketMessage, MessageType, ServiceType, AnalysisType, SeverityLevel,
    AnalysisStatus, SecurityAnalysisRequest, SecurityAnalysisResult, AnalysisIssue,
    ServiceRegistration, create_progress_update_message, create_result_message,
    create_error_message, create_heartbeat_message
)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SecurityAnalyzer:
    """Security analysis service using multiple tools."""
    
    def __init__(self, gateway_uri: str = "ws://gateway:8765", service_id: str = "security-analyzer-1"):
        self.gateway_uri = gateway_uri
        self.service_id = service_id
        self.websocket = None
        self.connected = False
        self.running = False
        self.active_analyses: Dict[str, asyncio.Task] = {}
        
        # Tool configurations
        self.tools_config = {
            'bandit': {
                'command': ['bandit', '-r', '-f', 'json'],
                'extensions': ['.py'],
                'description': 'Python security linter'
            },
            'safety': {
                'command': ['safety', 'check', '--json'],
                'files': ['requirements.txt', 'Pipfile', 'pyproject.toml'],
                'description': 'Python dependency vulnerability scanner'
            },
            'pylint': {
                'command': ['pylint', '--output-format=json'],
                'extensions': ['.py'],
                'description': 'Python code quality and security checker'
            }
        }
    
    async def start(self):
        """Start the security analyzer service."""
        logger.info(f"Starting security analyzer service: {self.service_id}")
        
        while not self.connected:
            try:
                await self.connect_to_gateway()
                await self.register_service()
                self.running = True
                
                # Start background tasks
                asyncio.create_task(self.listen_for_messages())
                asyncio.create_task(self.send_heartbeats())
                
                logger.info("Security analyzer service started successfully")
                
                # Keep service running
                while self.running:
                    await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error starting service: {e}")
                await asyncio.sleep(5)  # Retry after 5 seconds
    
    async def stop(self):
        """Stop the security analyzer service."""
        logger.info("Stopping security analyzer service")
        self.running = False
        
        # Cancel active analyses
        for analysis_id, task in self.active_analyses.items():
            if not task.done():
                task.cancel()
                logger.info(f"Cancelled analysis: {analysis_id}")
        
        if self.websocket:
            await self.websocket.close()
        
        logger.info("Security analyzer service stopped")
    
    async def connect_to_gateway(self):
        """Connect to the WebSocket gateway."""
        try:
            self.websocket = await websockets.connect(
                self.gateway_uri,
                ping_interval=30,
                ping_timeout=10
            )
            self.connected = True
            logger.info(f"Connected to gateway at {self.gateway_uri}")
            
        except Exception as e:
            logger.error(f"Failed to connect to gateway: {e}")
            self.connected = False
            raise
    
    async def register_service(self):
        """Register service with the gateway."""
        registration = ServiceRegistration(
            service_type=ServiceType.SECURITY_ANALYZER,
            service_id=self.service_id,
            version="1.0.0",
            capabilities=[
                "security_python",
                "dependency_scan",
                "code_quality"
            ]
        )
        
        message = WebSocketMessage(
            type=MessageType.SERVICE_REGISTER,
            data=asdict(registration)
        )
        
        await self.websocket.send(message.to_json())
        logger.info(f"Registered service: {self.service_id}")
    
    async def listen_for_messages(self):
        """Listen for messages from the gateway."""
        try:
            async for message_data in self.websocket:
                try:
                    message = WebSocketMessage.from_json(message_data)
                    await self.handle_message(message)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info("Gateway connection closed")
            self.connected = False
        except Exception as e:
            logger.error(f"Error in message listener: {e}")
            self.connected = False
    
    async def handle_message(self, message: WebSocketMessage):
        """Handle incoming messages."""
        if message.type == MessageType.ANALYSIS_REQUEST:
            await self.handle_analysis_request(message)
        elif message.type == MessageType.CANCEL_REQUEST:
            await self.handle_cancel_request(message)
        elif message.type == MessageType.HEARTBEAT:
            # Gateway heartbeat - update our status
            pass
        else:
            logger.debug(f"Unhandled message type: {message.type}")
    
    async def handle_analysis_request(self, message: WebSocketMessage):
        """Handle security analysis request."""
        try:
            request_data = message.data.get('request', message.data)
            request = SecurityAnalysisRequest(
                model=request_data['model'],
                app_number=request_data['app_number'],
                analysis_type=AnalysisType(request_data['analysis_type']),
                source_path=request_data['source_path'],
                options=request_data.get('options', {}),
                timeout=request_data.get('timeout', 300),
                priority=request_data.get('priority', 1),
                tools=request_data.get('tools', ['bandit', 'safety']),
                scan_depth=request_data.get('scan_depth', 'standard'),
                include_tests=request_data.get('include_tests', False),
                exclude_patterns=request_data.get('exclude_patterns', [])
            )
            
            # Start analysis task
            analysis_id = message.correlation_id or message.id
            task = asyncio.create_task(
                self.perform_analysis(request, analysis_id, message.client_id)
            )
            self.active_analyses[analysis_id] = task
            
            logger.info(f"Started security analysis: {analysis_id}")
            
        except Exception as e:
            logger.error(f"Error handling analysis request: {e}")
            error_msg = create_error_message(
                "ANALYSIS_ERROR",
                f"Failed to start analysis: {e}",
                correlation_id=message.correlation_id or message.id,
                client_id=message.client_id
            )
            await self.websocket.send(error_msg.to_json())
    
    async def handle_cancel_request(self, message: WebSocketMessage):
        """Handle analysis cancellation."""
        analysis_id = message.data.get('analysis_id')
        if analysis_id in self.active_analyses:
            task = self.active_analyses[analysis_id]
            if not task.done():
                task.cancel()
                logger.info(f"Cancelled analysis: {analysis_id}")
    
    async def perform_analysis(self, request: SecurityAnalysisRequest, analysis_id: str, client_id: str):
        """Perform security analysis."""
        start_time = time.time()
        issues = []
        
        try:
            # Send initial progress update
            await self.send_progress_update(
                analysis_id, client_id, "initializing", 0.0, "Starting security analysis"
            )
            
            # Resolve source path
            source_path = Path("/app/sources") / request.source_path
            if not source_path.exists():
                raise FileNotFoundError(f"Source path not found: {source_path}")
            
            # Run selected tools
            total_tools = len(request.tools)
            for i, tool in enumerate(request.tools):
                if tool in self.tools_config:
                    await self.send_progress_update(
                        analysis_id, client_id, f"running_{tool}", 
                        (i / total_tools), f"Running {tool} analysis"
                    )
                    
                    tool_issues = await self.run_security_tool(tool, source_path, request)
                    issues.extend(tool_issues)
                else:
                    logger.warning(f"Unknown security tool: {tool}")
            
            # Finalize results
            await self.send_progress_update(
                analysis_id, client_id, "finalizing", 0.9, "Generating report"
            )
            
            # Create result
            result = SecurityAnalysisResult(
                analysis_id=analysis_id,
                status=AnalysisStatus.COMPLETED,
                analysis_type=request.analysis_type,
                started_at=start_time,
                completed_at=time.time(),
                duration=time.time() - start_time,
                issues=issues,
                tools_used=request.tools,
                total_issues=len(issues),
                critical_count=len([i for i in issues if i.severity == SeverityLevel.CRITICAL]),
                high_count=len([i for i in issues if i.severity == SeverityLevel.HIGH]),
                medium_count=len([i for i in issues if i.severity == SeverityLevel.MEDIUM]),
                low_count=len([i for i in issues if i.severity == SeverityLevel.LOW]),
                vulnerability_types=self.categorize_vulnerabilities(issues),
                summary={
                    'scan_depth': request.scan_depth,
                    'files_scanned': await self.count_files(source_path, request),
                    'tools_used': request.tools
                }
            )
            
            # Send final progress
            await self.send_progress_update(
                analysis_id, client_id, "completed", 1.0, 
                f"Analysis completed: {len(issues)} issues found"
            )
            
            # Send result
            result_msg = create_result_message(result, client_id)
            await self.websocket.send(result_msg.to_json())
            
            logger.info(f"Completed security analysis: {analysis_id} ({len(issues)} issues)")
            
        except asyncio.CancelledError:
            logger.info(f"Analysis cancelled: {analysis_id}")
            # Send cancellation result
            result = SecurityAnalysisResult(
                analysis_id=analysis_id,
                status=AnalysisStatus.CANCELLED,
                analysis_type=request.analysis_type,
                started_at=start_time,
                completed_at=time.time(),
                duration=time.time() - start_time,
                error_message="Analysis was cancelled"
            )
            result_msg = create_result_message(result, client_id)
            await self.websocket.send(result_msg.to_json())
            
        except Exception as e:
            logger.error(f"Analysis failed: {analysis_id} - {e}")
            # Send error result
            result = SecurityAnalysisResult(
                analysis_id=analysis_id,
                status=AnalysisStatus.FAILED,
                analysis_type=request.analysis_type,
                started_at=start_time,
                completed_at=time.time(),
                duration=time.time() - start_time,
                error_message=str(e)
            )
            result_msg = create_result_message(result, client_id)
            await self.websocket.send(result_msg.to_json())
            
        finally:
            # Clean up
            self.active_analyses.pop(analysis_id, None)
    
    async def run_security_tool(
        self, 
        tool: str, 
        source_path: Path, 
        request: SecurityAnalysisRequest
    ) -> List[AnalysisIssue]:
        """Run a specific security tool and parse results."""
        tool_config = self.tools_config[tool]
        issues = []
        
        try:
            if tool == 'bandit':
                issues = await self.run_bandit(source_path, request)
            elif tool == 'safety':
                issues = await self.run_safety(source_path, request)
            elif tool == 'pylint':
                issues = await self.run_pylint(source_path, request)
            
        except Exception as e:
            logger.error(f"Error running {tool}: {e}")
            # Create an error issue
            issues.append(AnalysisIssue(
                tool=tool,
                severity=SeverityLevel.HIGH,
                confidence="high",
                file_path=str(source_path),
                message=f"Tool execution failed: {e}",
                description=f"Failed to run {tool_config['description']}"
            ))
        
        return issues
    
    async def run_bandit(self, source_path: Path, request: SecurityAnalysisRequest) -> List[AnalysisIssue]:
        """Run Bandit security analysis."""
        issues = []
        
        # Find Python files
        python_files = list(source_path.rglob("*.py"))
        if not python_files:
            return issues
        
        try:
            cmd = ['bandit', '-r', '-f', 'json', str(source_path)]
            
            # Add exclusions if specified
            if request.exclude_patterns:
                for pattern in request.exclude_patterns:
                    cmd.extend(['--exclude', pattern])
            
            # Skip tests if not included
            if not request.include_tests:
                cmd.extend(['--skip', 'B101'])  # Skip assert_used test
            
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode in [0, 1]:  # 0 = no issues, 1 = issues found
                output = json.loads(stdout.decode())
                
                for issue in output.get('results', []):
                    issues.append(AnalysisIssue(
                        tool='bandit',
                        severity=self.map_bandit_severity(issue.get('issue_severity', 'LOW')),
                        confidence=issue.get('issue_confidence', 'UNDEFINED').lower(),
                        file_path=issue.get('filename', ''),
                        line_number=issue.get('line_number'),
                        message=issue.get('issue_text', ''),
                        description=issue.get('issue_text', ''),
                        rule_id=issue.get('test_id', ''),
                        code_snippet=issue.get('code', '')
                    ))
            
        except Exception as e:
            logger.error(f"Bandit execution failed: {e}")
        
        return issues
    
    async def run_safety(self, source_path: Path, request: SecurityAnalysisRequest) -> List[AnalysisIssue]:
        """Run Safety dependency vulnerability check."""
        issues = []
        
        # Look for dependency files
        dep_files = []
        for filename in ['requirements.txt', 'Pipfile', 'pyproject.toml']:
            dep_file = source_path / filename
            if dep_file.exists():
                dep_files.append(dep_file)
        
        if not dep_files:
            return issues
        
        try:
            for dep_file in dep_files:
                cmd = ['safety', 'check', '--json', '-r', str(dep_file)]
                
                result = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await result.communicate()
                
                if result.returncode in [0, 64]:  # 0 = no vulnerabilities, 64 = vulnerabilities found
                    try:
                        vulnerabilities = json.loads(stdout.decode())
                        
                        for vuln in vulnerabilities:
                            issues.append(AnalysisIssue(
                                tool='safety',
                                severity=SeverityLevel.HIGH,  # All safety issues are high severity
                                confidence='high',
                                file_path=str(dep_file),
                                message=f"Vulnerable dependency: {vuln.get('package_name', 'unknown')}",
                                description=vuln.get('advisory', ''),
                                rule_id=vuln.get('id', ''),
                                fix_suggestion=f"Update to version {vuln.get('analyzed_version', 'latest')}"
                            ))
                    except json.JSONDecodeError:
                        # Safety sometimes returns non-JSON output
                        if stdout:
                            issues.append(AnalysisIssue(
                                tool='safety',
                                severity=SeverityLevel.MEDIUM,
                                confidence='medium',
                                file_path=str(dep_file),
                                message="Dependency vulnerability check completed",
                                description=stdout.decode()
                            ))
                
        except Exception as e:
            logger.error(f"Safety execution failed: {e}")
        
        return issues
    
    async def run_pylint(self, source_path: Path, request: SecurityAnalysisRequest) -> List[AnalysisIssue]:
        """Run PyLint code quality and security analysis."""
        issues = []
        
        # Find Python files
        python_files = list(source_path.rglob("*.py"))
        if not python_files:
            return issues
        
        try:
            cmd = ['pylint', '--output-format=json', '--disable=C,R', '--enable=W,E']
            cmd.extend([str(f) for f in python_files[:10]])  # Limit to 10 files for performance
            
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if stdout:
                try:
                    pylint_issues = json.loads(stdout.decode())
                    
                    for issue in pylint_issues:
                        issues.append(AnalysisIssue(
                            tool='pylint',
                            severity=self.map_pylint_severity(issue.get('type', 'warning')),
                            confidence='medium',
                            file_path=issue.get('path', ''),
                            line_number=issue.get('line'),
                            column=issue.get('column'),
                            message=issue.get('message', ''),
                            description=issue.get('message', ''),
                            rule_id=issue.get('symbol', '')
                        ))
                except json.JSONDecodeError:
                    pass  # PyLint sometimes has JSON parsing issues
                
        except Exception as e:
            logger.error(f"PyLint execution failed: {e}")
        
        return issues
    
    def map_bandit_severity(self, bandit_severity: str) -> SeverityLevel:
        """Map Bandit severity to our severity levels."""
        mapping = {
            'LOW': SeverityLevel.LOW,
            'MEDIUM': SeverityLevel.MEDIUM,
            'HIGH': SeverityLevel.HIGH,
            'CRITICAL': SeverityLevel.CRITICAL
        }
        return mapping.get(bandit_severity.upper(), SeverityLevel.MEDIUM)
    
    def map_pylint_severity(self, pylint_type: str) -> SeverityLevel:
        """Map PyLint message type to our severity levels."""
        mapping = {
            'error': SeverityLevel.HIGH,
            'warning': SeverityLevel.MEDIUM,
            'refactor': SeverityLevel.LOW,
            'convention': SeverityLevel.LOW
        }
        return mapping.get(pylint_type.lower(), SeverityLevel.MEDIUM)
    
    def categorize_vulnerabilities(self, issues: List[AnalysisIssue]) -> Dict[str, int]:
        """Categorize vulnerabilities by type."""
        categories = {}
        
        for issue in issues:
            if issue.rule_id:
                category = issue.rule_id.split('_')[0] if '_' in issue.rule_id else issue.rule_id
                categories[category] = categories.get(category, 0) + 1
        
        return categories
    
    async def count_files(self, source_path: Path, request: SecurityAnalysisRequest) -> int:
        """Count files that would be analyzed."""
        count = 0
        for ext in ['.py', '.js', '.ts']:
            count += len(list(source_path.rglob(f"*{ext}")))
        return count
    
    async def send_progress_update(
        self, 
        analysis_id: str, 
        client_id: str, 
        stage: str, 
        progress: float, 
        message: str
    ):
        """Send progress update to client."""
        try:
            progress_msg = create_progress_update_message(
                analysis_id, stage, progress, message, client_id
            )
            await self.websocket.send(progress_msg.to_json())
        except Exception as e:
            logger.error(f"Failed to send progress update: {e}")
    
    async def send_heartbeats(self):
        """Send periodic heartbeats to gateway."""
        while self.running and self.connected:
            try:
                heartbeat = create_heartbeat_message(
                    service_id=self.service_id,
                    status="healthy",
                    uptime=time.time(),
                    active_analyses=len(self.active_analyses),
                    queue_size=0
                )
                await self.websocket.send(heartbeat.to_json())
                await asyncio.sleep(30)  # Send every 30 seconds
                
            except Exception as e:
                logger.error(f"Failed to send heartbeat: {e}")
                await asyncio.sleep(30)


async def main():
    """Main entry point for the security analyzer service."""
    import signal
    
    service = SecurityAnalyzer(
        gateway_uri=os.getenv('GATEWAY_URI', 'ws://gateway:8765'),
        service_id=os.getenv('SERVICE_ID', 'security-analyzer-1')
    )
    
    # Handle shutdown signals
    def signal_handler():
        logger.info("Received shutdown signal")
        asyncio.create_task(service.stop())
    
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, lambda s, f: signal_handler())
    if hasattr(signal, 'SIGINT'):
        signal.signal(signal.SIGINT, lambda s, f: signal_handler())
    
    try:
        await service.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())
