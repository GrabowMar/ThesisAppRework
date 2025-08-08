"""
Performance Testing Service - Locust Load Testing
Performs load testing and performance analysis using Locust.
"""

import asyncio
import json
import logging
import os
import subprocess
import tempfile
import websockets
from pathlib import Path
from typing import Dict, List, Any
import time
from dataclasses import asdict
from datetime import datetime
import uuid
import threading
import requests
from io import StringIO
import csv

# Add parent directory to path for shared imports
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from shared.protocol import (
    WebSocketMessage, MessageType, PerformanceTestRequest, 
    AnalysisResult, ProgressUpdate, AnalysisStatus,
    AnalysisIssue, SeverityLevel, create_request_from_dict,
    PerformanceTestResult
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PerformanceTester:
    """Locust-based performance testing analyzer."""
    
    def __init__(self):
        self.locust_process = None
        self.test_scenarios = {
            'basic_load': self._create_basic_load_scenario,
            'stress_test': self._create_stress_test_scenario,
            'spike_test': self._create_spike_test_scenario,
            'endurance_test': self._create_endurance_test_scenario
        }
        
    async def analyze(self, request: PerformanceTestRequest, websocket) -> AnalysisResult:
        """
        Perform performance testing using Locust.
        """
        analysis_id = str(uuid.uuid4())
        started_at = datetime.utcnow()
        
        logger.info(f"Starting performance test for {request.target_url}")
        
        # Send initial progress
        await self._send_progress(websocket, analysis_id, "Initializing performance test", 0.0)
        
        issues = []
        
        try:
            # Create test scenario
            await self._send_progress(websocket, analysis_id, "Creating test scenario", 0.1)
            scenario_file = await self._create_test_scenario(request)
            
            # Start Locust test
            await self._send_progress(websocket, analysis_id, "Starting load test", 0.2)
            stats_file = await self._start_locust_test(request, scenario_file)
            
            # Monitor test progress
            await self._send_progress(websocket, analysis_id, "Running load test", 0.3)
            await self._monitor_test_progress(request, websocket, analysis_id)
            
            # Collect results
            await self._send_progress(websocket, analysis_id, "Collecting results", 0.9)
            test_results = await self._collect_results(stats_file)
            
            # Analyze performance issues
            issues = self._analyze_performance_issues(test_results)
            
            # Generate summary
            summary = self._generate_summary(test_results, issues)
            
            # Final progress
            await self._send_progress(websocket, analysis_id, "Analysis complete", 1.0)
            
            return PerformanceTestResult(
                analysis_id=analysis_id,
                status=AnalysisStatus.COMPLETED,
                analysis_type=request.analysis_type,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                duration=(datetime.utcnow() - started_at).total_seconds(),
                issues=issues,
                summary=summary,
                metadata={
                    'analyzer': 'performance-tester',
                    'target_url': request.target_url,
                    'test_scenario': request.test_scenario,
                    'users': request.users,
                    'duration': request.duration
                },
                # Performance-specific metrics
                total_requests=test_results.get('total_requests', 0),
                successful_requests=test_results.get('successful_requests', 0),
                failed_requests=test_results.get('failed_requests', 0),
                avg_response_time=test_results.get('avg_response_time', 0.0),
                min_response_time=test_results.get('min_response_time', 0.0),
                max_response_time=test_results.get('max_response_time', 0.0),
                p95_response_time=test_results.get('p95_response_time', 0.0),
                p99_response_time=test_results.get('p99_response_time', 0.0),
                requests_per_second=test_results.get('requests_per_second', 0.0),
                error_rate=test_results.get('error_rate', 0.0),
                response_time_distribution=test_results.get('response_time_distribution', {})
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
                metadata={'analyzer': 'performance-tester'},
                error_message=str(e)
            )
        finally:
            # Clean up Locust process
            await self._stop_locust_test()
    
    async def _create_test_scenario(self, request: PerformanceTestRequest) -> Path:
        """Create Locust test scenario file."""
        scenario_creator = self.test_scenarios.get(
            request.test_scenario, 
            self._create_basic_load_scenario
        )
        
        return await scenario_creator(request)
    
    async def _create_basic_load_scenario(self, request: PerformanceTestRequest) -> Path:
        """Create basic load test scenario."""
        scenario_content = f'''
from locust import HttpUser, task, between
import json

class WebsiteUser(HttpUser):
    wait_time = between(1, 3)
    host = "{request.target_url}"
    
    def on_start(self):
        """Called when a user starts"""
        pass
    
    @task(3)
    def view_homepage(self):
        """Load the homepage"""
        self.client.get("/")
    
    @task(2)
    def view_about(self):
        """Load the about page"""
        self.client.get("/about", catch_response=True)
    
    @task(1)
    def search(self):
        """Perform a search"""
        self.client.get("/search?q=test")
    
    @task(1)
    def api_call(self):
        """Make an API call"""
        with self.client.get("/api/status", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status code {{response.status_code}}")
'''
        
        # Write scenario to temporary file
        scenario_file = Path(tempfile.mktemp(suffix='.py'))
        scenario_file.write_text(scenario_content)
        
        return scenario_file
    
    async def _create_stress_test_scenario(self, request: PerformanceTestRequest) -> Path:
        """Create stress test scenario with high load."""
        scenario_content = f'''
from locust import HttpUser, task, between
import random

class StressTestUser(HttpUser):
    wait_time = between(0.1, 0.5)  # Shorter wait times for stress testing
    host = "{request.target_url}"
    
    @task(5)
    def heavy_request(self):
        """Make heavy requests"""
        self.client.get("/", timeout=30)
    
    @task(3)
    def concurrent_requests(self):
        """Make multiple concurrent requests"""
        endpoints = ["/", "/about", "/contact", "/products", "/services"]
        endpoint = random.choice(endpoints)
        self.client.get(endpoint)
    
    @task(2)
    def post_data(self):
        """POST requests with data"""
        data = {{"test": "data", "timestamp": "{{random.randint(1, 1000)}}"}}
        self.client.post("/api/data", json=data, catch_response=True)
'''
        
        scenario_file = Path(tempfile.mktemp(suffix='.py'))
        scenario_file.write_text(scenario_content)
        
        return scenario_file
    
    async def _create_spike_test_scenario(self, request: PerformanceTestRequest) -> Path:
        """Create spike test scenario."""
        scenario_content = f'''
from locust import HttpUser, task, between

class SpikeTestUser(HttpUser):
    wait_time = between(0.1, 2)
    host = "{request.target_url}"
    
    @task
    def spike_load(self):
        """Generate spike load"""
        # Simulate sudden burst of requests
        self.client.get("/")
        self.client.get("/heavy-endpoint")
        self.client.get("/api/data")
'''
        
        scenario_file = Path(tempfile.mktemp(suffix='.py'))
        scenario_file.write_text(scenario_content)
        
        return scenario_file
    
    async def _create_endurance_test_scenario(self, request: PerformanceTestRequest) -> Path:
        """Create endurance test scenario for long-running tests."""
        scenario_content = f'''
from locust import HttpUser, task, between

class EnduranceTestUser(HttpUser):
    wait_time = between(2, 5)  # Longer wait times for sustained load
    host = "{request.target_url}"
    
    @task(3)
    def sustained_load(self):
        """Sustained load over time"""
        self.client.get("/")
    
    @task(2)
    def memory_intensive(self):
        """Memory intensive operations"""
        self.client.get("/api/heavy-computation")
    
    @task(1)
    def database_operations(self):
        """Database heavy operations"""
        self.client.get("/api/database-query")
'''
        
        scenario_file = Path(tempfile.mktemp(suffix='.py'))
        scenario_file.write_text(scenario_content)
        
        return scenario_file
    
    async def _start_locust_test(self, request: PerformanceTestRequest, scenario_file: Path) -> Path:
        """Start Locust test."""
        try:
            # Create output directory
            output_dir = Path(tempfile.mkdtemp())
            stats_file = output_dir / "stats.csv"
            
            # Build Locust command
            cmd = [
                'locust',
                '-f', str(scenario_file),
                '--headless',
                '--users', str(request.users),
                '--spawn-rate', str(request.spawn_rate),
                '--run-time', f"{request.duration}s",
                '--host', request.target_url,
                '--csv', str(output_dir / "stats"),
                '--html', str(output_dir / "report.html")
            ]
            
            # Start Locust process
            self.locust_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=output_dir
            )
            
            logger.info(f"Started Locust test with PID: {self.locust_process.pid}")
            return stats_file
            
        except Exception as e:
            logger.error(f"Failed to start Locust test: {str(e)}")
            raise
    
    async def _monitor_test_progress(self, request: PerformanceTestRequest, websocket, analysis_id: str):
        """Monitor test progress and send updates."""
        test_duration = request.duration
        start_time = time.time()
        
        while time.time() - start_time < test_duration:
            elapsed = time.time() - start_time
            progress = 0.3 + (elapsed / test_duration) * 0.6  # 30% to 90%
            
            await self._send_progress(
                websocket, analysis_id,
                f"Running test... {int(elapsed)}s / {test_duration}s",
                progress
            )
            
            await asyncio.sleep(5)
        
        # Wait for process to finish
        if self.locust_process:
            self.locust_process.wait()
    
    async def _collect_results(self, stats_file: Path) -> Dict[str, Any]:
        """Collect and parse Locust test results."""
        results = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'avg_response_time': 0.0,
            'min_response_time': 0.0,
            'max_response_time': 0.0,
            'p95_response_time': 0.0,
            'p99_response_time': 0.0,
            'requests_per_second': 0.0,
            'error_rate': 0.0,
            'response_time_distribution': {}
        }
        
        try:
            if stats_file.exists():
                with open(stats_file, 'r') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row.get('Type') == 'Aggregated':
                            results['total_requests'] = int(row.get('Request Count', 0))
                            results['failed_requests'] = int(row.get('Failure Count', 0))
                            results['successful_requests'] = results['total_requests'] - results['failed_requests']
                            results['avg_response_time'] = float(row.get('Average Response Time', 0))
                            results['min_response_time'] = float(row.get('Min Response Time', 0))
                            results['max_response_time'] = float(row.get('Max Response Time', 0))
                            results['requests_per_second'] = float(row.get('Requests/s', 0))
                            
                            # Calculate error rate
                            if results['total_requests'] > 0:
                                results['error_rate'] = (results['failed_requests'] / results['total_requests']) * 100
                            
                            break
            
        except Exception as e:
            logger.error(f"Failed to parse results: {str(e)}")
        
        return results
    
    def _analyze_performance_issues(self, test_results: Dict[str, Any]) -> List[AnalysisIssue]:
        """Analyze performance test results and identify issues."""
        issues = []
        
        # Check error rate
        error_rate = test_results.get('error_rate', 0)
        if error_rate > 5:  # More than 5% error rate
            severity = SeverityLevel.HIGH if error_rate > 20 else SeverityLevel.MEDIUM
            issues.append(AnalysisIssue(
                tool='locust',
                severity=severity,
                confidence='HIGH',
                file_path='',
                message=f"High error rate: {error_rate:.2f}%",
                description=f"The application has a {error_rate:.2f}% error rate, which is above acceptable threshold",
                rule_id='high_error_rate',
                fix_suggestion="Investigate server errors, optimize database queries, and improve error handling"
            ))
        
        # Check response time
        avg_response_time = test_results.get('avg_response_time', 0)
        if avg_response_time > 2000:  # More than 2 seconds
            severity = SeverityLevel.HIGH if avg_response_time > 5000 else SeverityLevel.MEDIUM
            issues.append(AnalysisIssue(
                tool='locust',
                severity=severity,
                confidence='HIGH',
                file_path='',
                message=f"Slow average response time: {avg_response_time:.0f}ms",
                description=f"Average response time of {avg_response_time:.0f}ms exceeds recommended thresholds",
                rule_id='slow_response_time',
                fix_suggestion="Optimize database queries, implement caching, optimize server configuration"
            ))
        
        # Check max response time
        max_response_time = test_results.get('max_response_time', 0)
        if max_response_time > 10000:  # More than 10 seconds
            issues.append(AnalysisIssue(
                tool='locust',
                severity=SeverityLevel.HIGH,
                confidence='HIGH',
                file_path='',
                message=f"Very slow maximum response time: {max_response_time:.0f}ms",
                description=f"Maximum response time of {max_response_time:.0f}ms indicates performance bottlenecks",
                rule_id='very_slow_max_response',
                fix_suggestion="Identify and optimize slow endpoints, implement request timeouts"
            ))
        
        # Check requests per second
        rps = test_results.get('requests_per_second', 0)
        if rps < 10:  # Less than 10 RPS might indicate performance issues
            issues.append(AnalysisIssue(
                tool='locust',
                severity=SeverityLevel.MEDIUM,
                confidence='MEDIUM',
                file_path='',
                message=f"Low throughput: {rps:.2f} requests/second",
                description=f"Application throughput of {rps:.2f} RPS is below expected performance",
                rule_id='low_throughput',
                fix_suggestion="Scale server resources, optimize application code, implement load balancing"
            ))
        
        return issues
    
    def _generate_summary(self, test_results: Dict[str, Any], issues: List[AnalysisIssue]) -> Dict[str, Any]:
        """Generate performance test summary."""
        summary = {
            'performance_score': self._calculate_performance_score(test_results),
            'test_results': test_results,
            'issues_found': len(issues),
            'by_severity': {},
            'recommendations': []
        }
        
        # Count issues by severity
        for issue in issues:
            severity = issue.severity.value
            summary['by_severity'][severity] = summary['by_severity'].get(severity, 0) + 1
        
        # Add recommendations based on results
        if test_results.get('error_rate', 0) > 1:
            summary['recommendations'].append("Investigate and fix application errors")
        
        if test_results.get('avg_response_time', 0) > 1000:
            summary['recommendations'].append("Optimize response times through caching and code optimization")
        
        if test_results.get('requests_per_second', 0) < 50:
            summary['recommendations'].append("Consider scaling infrastructure to handle higher load")
        
        return summary
    
    def _calculate_performance_score(self, test_results: Dict[str, Any]) -> float:
        """Calculate overall performance score (0-100)."""
        score = 100.0
        
        # Deduct points for errors
        error_rate = test_results.get('error_rate', 0)
        score -= min(error_rate * 2, 40)  # Max 40 points deduction for errors
        
        # Deduct points for slow response times
        avg_response_time = test_results.get('avg_response_time', 0)
        if avg_response_time > 500:  # 500ms threshold
            score -= min((avg_response_time - 500) / 100, 30)  # Max 30 points deduction
        
        # Deduct points for low throughput
        rps = test_results.get('requests_per_second', 0)
        if rps < 100:  # 100 RPS threshold
            score -= min((100 - rps) / 10, 20)  # Max 20 points deduction
        
        return max(score, 0)
    
    async def _stop_locust_test(self):
        """Stop Locust test."""
        try:
            if self.locust_process:
                self.locust_process.terminate()
                self.locust_process.wait(timeout=10)
                logger.info("Locust test stopped")
        except Exception as e:
            logger.warning(f"Error stopping Locust test: {str(e)}")
    
    async def _send_progress(self, websocket, analysis_id: str, message: str, progress: float):
        """Send progress update to client."""
        try:
            progress_update = ProgressUpdate(
                analysis_id=analysis_id,
                stage="testing",
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
    tester = PerformanceTester()
    logger.info(f"New client connected: {websocket.remote_address}")
    
    try:
        async for message in websocket:
            try:
                # Parse incoming message
                ws_message = WebSocketMessage.from_json(message)
                
                if ws_message.type == MessageType.ANALYSIS_REQUEST:
                    # Parse analysis request
                    request = create_request_from_dict(ws_message.data)
                    
                    # Only handle performance test requests
                    if isinstance(request, PerformanceTestRequest):
                        # Perform analysis
                        result = await tester.analyze(request, websocket)
                        
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
                                'message': 'This service only handles performance test requests'
                            },
                            correlation_id=ws_message.id
                        )
                        await websocket.send(error_msg.to_json())
                
                elif ws_message.type == MessageType.HEARTBEAT:
                    # Respond to heartbeat
                    response = WebSocketMessage(
                        type=MessageType.HEARTBEAT,
                        data={'status': 'healthy', 'service': 'performance-tester'}
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
    """Start the performance tester service."""
    host = os.getenv('WEBSOCKET_HOST', '0.0.0.0')
    port = int(os.getenv('WEBSOCKET_PORT', 8003))
    
    logger.info(f"Starting Performance Tester service on {host}:{port}")
    
    start_server = websockets.serve(handle_client, host, port)
    
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()


if __name__ == "__main__":
    main()
