"""
Dynamic Analysis Service - OWASP ZAP Security Scanner
Performs dynamic application security testing using OWASP ZAP.
"""

import asyncio
import json
import logging
import os
import subprocess
import tempfile
import websockets
from pathlib import Path
from typing import Dict, List, Any, Optional
import shutil
from dataclasses import asdict
from datetime import datetime
import uuid
import time
import requests

# Add parent directory to path for shared imports
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from shared.protocol import (
    WebSocketMessage, MessageType, PerformanceTestRequest, 
    AnalysisResult, ProgressUpdate, AnalysisStatus, AnalysisType,
    AnalysisIssue, SeverityLevel, create_request_from_dict
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DynamicAnalyzer:
    """OWASP ZAP-based dynamic security analysis."""
    
    def __init__(self):
        self.zap_path = os.getenv('ZAP_PATH', '/opt/zaproxy')
        self.zap_port = 8080
        self.zap_process = None
        
    async def analyze(self, request: PerformanceTestRequest, websocket) -> AnalysisResult:
        """
        Perform dynamic security analysis using OWASP ZAP.
        """
        analysis_id = str(uuid.uuid4())
        started_at = datetime.utcnow()
        
        logger.info(f"Starting dynamic analysis for {request.target_url}")
        
        # Send initial progress
        await self._send_progress(websocket, analysis_id, "Initializing ZAP scanner", 0.0)
        
        issues = []
        
        try:
            # Start ZAP daemon
            await self._send_progress(websocket, analysis_id, "Starting ZAP daemon", 0.1)
            await self._start_zap_daemon()
            
            # Wait for ZAP to be ready
            await self._send_progress(websocket, analysis_id, "Waiting for ZAP to be ready", 0.2)
            await self._wait_for_zap_ready()
            
            # Configure ZAP
            await self._send_progress(websocket, analysis_id, "Configuring ZAP scanner", 0.3)
            await self._configure_zap(request)
            
            # Spider the application
            await self._send_progress(websocket, analysis_id, "Spidering application", 0.4)
            spider_id = await self._start_spider(request.target_url)
            await self._wait_for_spider_completion(spider_id, websocket, analysis_id)
            
            # Run active scan
            await self._send_progress(websocket, analysis_id, "Running active security scan", 0.7)
            scan_id = await self._start_active_scan(request.target_url)
            await self._wait_for_scan_completion(scan_id, websocket, analysis_id)
            
            # Get results
            await self._send_progress(websocket, analysis_id, "Collecting results", 0.9)
            issues = await self._get_scan_results()
            
            # Generate summary
            summary = self._generate_summary(issues)
            
            # Final progress
            await self._send_progress(websocket, analysis_id, "Analysis complete", 1.0)
            
            return AnalysisResult(
                analysis_id=analysis_id,
                status=AnalysisStatus.COMPLETED,
                analysis_type=request.analysis_type,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                duration=(datetime.utcnow() - started_at).total_seconds(),
                issues=issues,
                summary=summary,
                metadata={
                    'analyzer': 'dynamic-analyzer',
                    'target_url': request.target_url,
                    'zap_version': await self._get_zap_version()
                }
            )
                
        except Exception as e:
            logger.error(f"Analysis failed: {str(e)}")
            await self._send_progress(websocket, analysis_id, f"Analysis failed: {str(e)}", 1.0)
            
            return AnalysisResult(
                analysis_id=analysis_id,
                status=AnalysisStatus.FAILED,
                analysis_type=request.analysis_type,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                duration=(datetime.utcnow() - started_at).total_seconds(),
                issues=[],
                summary={},
                metadata={'analyzer': 'dynamic-analyzer'},
                error_message=str(e)
            )
        finally:
            # Always stop ZAP daemon
            await self._stop_zap_daemon()
    
    async def _start_zap_daemon(self):
        """Start ZAP daemon in headless mode."""
        try:
            zap_script = Path(self.zap_path) / "zap.sh"
            
            cmd = [
                str(zap_script),
                "-daemon",
                "-port", str(self.zap_port),
                "-config", "api.addrs.addr.name=.*",
                "-config", "api.addrs.addr.regex=true",
                "-config", "api.key=changeme"
            ]
            
            # Start ZAP process
            self.zap_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid
            )
            
            logger.info(f"Started ZAP daemon with PID: {self.zap_process.pid}")
            
        except Exception as e:
            logger.error(f"Failed to start ZAP daemon: {str(e)}")
            raise
    
    async def _wait_for_zap_ready(self, timeout: int = 60):
        """Wait for ZAP to be ready to accept API calls."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                response = requests.get(
                    f"http://localhost:{self.zap_port}/JSON/core/view/version/",
                    params={"apikey": "changeme"},
                    timeout=5
                )
                
                if response.status_code == 200:
                    logger.info("ZAP is ready")
                    return
                    
            except requests.exceptions.RequestException:
                pass
            
            await asyncio.sleep(2)
        
        raise Exception("ZAP failed to start within timeout period")
    
    async def _configure_zap(self, request: PerformanceTestRequest):
        """Configure ZAP scanner settings."""
        try:
            # Set attack mode
            requests.get(
                f"http://localhost:{self.zap_port}/JSON/core/action/setMode/",
                params={"apikey": "changeme", "mode": "attack"}
            )
            
            # Configure spider settings
            requests.get(
                f"http://localhost:{self.zap_port}/JSON/spider/action/setOptionMaxDepth/",
                params={"apikey": "changeme", "Integer": "5"}
            )
            
            # Configure active scan settings based on test scenario
            if request.test_scenario == "thorough":
                # Enable all scan rules for thorough testing
                requests.get(
                    f"http://localhost:{self.zap_port}/JSON/ascan/action/setOptionAttackPolicy/",
                    params={"apikey": "changeme", "String": "Default Policy"}
                )
            else:
                # Use faster scan for basic testing
                requests.get(
                    f"http://localhost:{self.zap_port}/JSON/ascan/action/setOptionAttackPolicy/",
                    params={"apikey": "changeme", "String": "Quick"}
                )
                
        except Exception as e:
            logger.warning(f"Failed to configure ZAP: {str(e)}")
    
    async def _start_spider(self, target_url: str) -> str:
        """Start spidering the target application."""
        try:
            response = requests.get(
                f"http://localhost:{self.zap_port}/JSON/spider/action/scan/",
                params={
                    "apikey": "changeme",
                    "url": target_url,
                    "maxChildren": "10",
                    "recurse": "true",
                    "contextName": "",
                    "subtreeOnly": "false"
                }
            )
            
            result = response.json()
            spider_id = result.get('scan')
            
            logger.info(f"Started spider with ID: {spider_id}")
            return spider_id
            
        except Exception as e:
            logger.error(f"Failed to start spider: {str(e)}")
            raise
    
    async def _wait_for_spider_completion(self, spider_id: str, websocket, analysis_id: str):
        """Wait for spider to complete and send progress updates."""
        while True:
            try:
                response = requests.get(
                    f"http://localhost:{self.zap_port}/JSON/spider/view/status/",
                    params={"apikey": "changeme", "scanId": spider_id}
                )
                
                result = response.json()
                progress = int(result.get('status', 0))
                
                # Send progress update (spider is 40-60% of total progress)
                total_progress = 0.4 + (progress / 100.0) * 0.2
                await self._send_progress(
                    websocket, analysis_id, 
                    f"Spidering progress: {progress}%", 
                    total_progress
                )
                
                if progress >= 100:
                    logger.info("Spider completed")
                    break
                    
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"Error checking spider status: {str(e)}")
                break
    
    async def _start_active_scan(self, target_url: str) -> str:
        """Start active security scan."""
        try:
            response = requests.get(
                f"http://localhost:{self.zap_port}/JSON/ascan/action/scan/",
                params={
                    "apikey": "changeme",
                    "url": target_url,
                    "recurse": "true",
                    "inScopeOnly": "false",
                    "scanPolicyName": "",
                    "method": "",
                    "postData": "",
                    "contextId": ""
                }
            )
            
            result = response.json()
            scan_id = result.get('scan')
            
            logger.info(f"Started active scan with ID: {scan_id}")
            return scan_id
            
        except Exception as e:
            logger.error(f"Failed to start active scan: {str(e)}")
            raise
    
    async def _wait_for_scan_completion(self, scan_id: str, websocket, analysis_id: str):
        """Wait for active scan to complete and send progress updates."""
        while True:
            try:
                response = requests.get(
                    f"http://localhost:{self.zap_port}/JSON/ascan/view/status/",
                    params={"apikey": "changeme", "scanId": scan_id}
                )
                
                result = response.json()
                progress = int(result.get('status', 0))
                
                # Send progress update (active scan is 70-90% of total progress)
                total_progress = 0.7 + (progress / 100.0) * 0.2
                await self._send_progress(
                    websocket, analysis_id, 
                    f"Active scan progress: {progress}%", 
                    total_progress
                )
                
                if progress >= 100:
                    logger.info("Active scan completed")
                    break
                    
                await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"Error checking scan status: {str(e)}")
                break
    
    async def _get_scan_results(self) -> List[AnalysisIssue]:
        """Get scan results from ZAP."""
        issues = []
        
        try:
            # Get alerts
            response = requests.get(
                f"http://localhost:{self.zap_port}/JSON/core/view/alerts/",
                params={"apikey": "changeme", "baseurl": "", "start": "", "count": ""}
            )
            
            result = response.json()
            alerts = result.get('alerts', [])
            
            # Convert ZAP alerts to AnalysisIssue objects
            for alert in alerts:
                severity_map = {
                    'High': SeverityLevel.HIGH,
                    'Medium': SeverityLevel.MEDIUM,
                    'Low': SeverityLevel.LOW,
                    'Informational': SeverityLevel.INFO
                }
                
                issue = AnalysisIssue(
                    tool='zap',
                    severity=severity_map.get(alert.get('risk', 'Low'), SeverityLevel.LOW),
                    confidence=alert.get('confidence', 'Medium'),
                    file_path=alert.get('url', ''),
                    message=alert.get('name', ''),
                    description=alert.get('description', ''),
                    rule_id=alert.get('pluginId', ''),
                    fix_suggestion=alert.get('solution', ''),
                    code_snippet=alert.get('evidence', '')
                )
                
                issues.append(issue)
                
        except Exception as e:
            logger.error(f"Failed to get scan results: {str(e)}")
        
        return issues
    
    async def _get_zap_version(self) -> str:
        """Get ZAP version."""
        try:
            response = requests.get(
                f"http://localhost:{self.zap_port}/JSON/core/view/version/",
                params={"apikey": "changeme"}
            )
            
            result = response.json()
            return result.get('version', 'unknown')
            
        except Exception:
            return 'unknown'
    
    async def _stop_zap_daemon(self):
        """Stop ZAP daemon."""
        try:
            if self.zap_process:
                # Try graceful shutdown first
                requests.get(
                    f"http://localhost:{self.zap_port}/JSON/core/action/shutdown/",
                    params={"apikey": "changeme"},
                    timeout=5
                )
                
                # Wait a bit for graceful shutdown
                await asyncio.sleep(5)
                
                # Force kill if still running
                if self.zap_process.poll() is None:
                    os.killpg(os.getpgid(self.zap_process.pid), 9)
                
                logger.info("ZAP daemon stopped")
                
        except Exception as e:
            logger.warning(f"Error stopping ZAP daemon: {str(e)}")
    
    def _generate_summary(self, issues: List[AnalysisIssue]) -> Dict[str, Any]:
        """Generate analysis summary."""
        summary = {
            'total_issues': len(issues),
            'by_severity': {},
            'by_type': {},
            'top_issues': []
        }
        
        # Count by severity
        for issue in issues:
            severity = issue.severity.value
            summary['by_severity'][severity] = summary['by_severity'].get(severity, 0) + 1
            
            # Count by vulnerability type (based on rule_id)
            rule_id = issue.rule_id
            summary['by_type'][rule_id] = summary['by_type'].get(rule_id, 0) + 1
        
        # Get top issues (by severity)
        severity_order = {
            SeverityLevel.CRITICAL: 5,
            SeverityLevel.HIGH: 4,
            SeverityLevel.MEDIUM: 3,
            SeverityLevel.LOW: 2,
            SeverityLevel.INFO: 1
        }
        
        sorted_issues = sorted(
            issues,
            key=lambda x: severity_order.get(x.severity, 0),
            reverse=True
        )
        
        summary['top_issues'] = [issue.to_dict() for issue in sorted_issues[:10]]
        
        return summary
    
    async def _send_progress(self, websocket, analysis_id: str, message: str, progress: float):
        """Send progress update to client."""
        try:
            progress_update = ProgressUpdate(
                analysis_id=analysis_id,
                stage="scanning",
                progress=progress,
                message=message
            )
            
            ws_message = WebSocketMessage(
                type=MessageType.PROGRESS_UPDATE,
                data=progress_update.to_dict()
            )
            
            await websocket.send(ws_message.to_json())
        except Exception as e:
            logger.error(f"Failed to send progress: {str(e)}")


async def handle_client(websocket, path):
    """Handle incoming WebSocket connections."""
    analyzer = DynamicAnalyzer()
    logger.info(f"New client connected: {websocket.remote_address}")
    
    try:
        async for message in websocket:
            try:
                # Parse incoming message
                ws_message = WebSocketMessage.from_json(message)
                
                if ws_message.type == MessageType.ANALYSIS_REQUEST:
                    # Parse analysis request
                    request = create_request_from_dict(ws_message.data)
                    
                    # Only handle performance test requests (which include dynamic security testing)
                    if isinstance(request, PerformanceTestRequest):
                        # Perform analysis
                        result = await analyzer.analyze(request, websocket)
                        
                        # Send result back
                        response = WebSocketMessage(
                            type=MessageType.ANALYSIS_RESULT,
                            data=result.to_dict(),
                            correlation_id=ws_message.id
                        )
                        
                        await websocket.send(response.to_json())
                    else:
                        # Not a supported request type
                        error_msg = WebSocketMessage(
                            type=MessageType.ERROR,
                            data={
                                'code': 'UNSUPPORTED_REQUEST',
                                'message': 'This service only handles dynamic security analysis requests'
                            },
                            correlation_id=ws_message.id
                        )
                        await websocket.send(error_msg.to_json())
                
                elif ws_message.type == MessageType.HEARTBEAT:
                    # Respond to heartbeat
                    response = WebSocketMessage(
                        type=MessageType.HEARTBEAT,
                        data={'status': 'healthy', 'service': 'dynamic-analyzer'}
                    )
                    await websocket.send(response.to_json())
                    
            except json.JSONDecodeError:
                logger.error("Received invalid JSON message")
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")
                
    except websockets.exceptions.ConnectionClosed:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")


def main():
    """Start the dynamic analyzer service."""
    host = os.getenv('WEBSOCKET_HOST', '0.0.0.0')
    port = int(os.getenv('WEBSOCKET_PORT', 8002))
    
    logger.info(f"Starting Dynamic Analyzer service on {host}:{port}")
    
    start_server = websockets.serve(handle_client, host, port)
    
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()


if __name__ == "__main__":
    main()
