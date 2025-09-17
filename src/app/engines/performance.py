"""
Performance Analysis Tools
=========================

Implementation of performance testing tools inspired by the attached files.
Includes Locust-based load testing and other performance analysis tools.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .base import (
    BaseAnalysisTool, ToolResult, Finding, ToolStatus, Severity, Confidence,
    find_executable, run_command, analysis_tool
)

logger = __import__('logging').getLogger(__name__)

@analysis_tool
class LocustTool(BaseAnalysisTool):
    """Locust performance testing tool."""
    
    @property
    def name(self) -> str:
        return "locust"
    
    @property
    def display_name(self) -> str:
        return "Locust Load Testing"
    
    @property
    def description(self) -> str:
        return "Load testing and performance analysis with Locust"
    
    @property
    def tags(self) -> Set[str]:
        return {"performance", "load_testing", "web", "http"}
    
    @property
    def supported_languages(self) -> Set[str]:
        return {"python", "web"}
    
    def is_available(self) -> bool:
        """Check if locust is available."""
        return find_executable("locust") is not None
    
    def get_version(self) -> Optional[str]:
        """Get locust version."""
        try:
            returncode, stdout, _ = run_command(["locust", "--version"], timeout=10)
            if returncode == 0:
                match = re.search(r'(\d+\.\d+\.\d+)', stdout)
                if match:
                    return match.group(1)
        except Exception as e:
            self.logger.debug(f"Failed to get locust version: {e}")
        return None
    
    def run_analysis(self, target_path: Path, **kwargs) -> ToolResult:
        """Run locust performance test."""
        start_time = __import__('time').time()
        
        try:
            # Get test configuration from kwargs
            host = kwargs.get('host', 'http://localhost:5000')
            users = kwargs.get('users', 10)
            spawn_rate = kwargs.get('spawn_rate', 1)
            run_time = kwargs.get('run_time', '30s')
            
            # Create temporary locustfile if none exists
            locustfile_path = self._create_default_locustfile(target_path)
            
            # Build locust command
            command = [
                "locust",
                "-f", str(locustfile_path),
                "--headless",
                "--users", str(users),
                "--spawn-rate", str(spawn_rate),
                "--run-time", run_time,
                "--host", host,
                "--csv", str(target_path / "locust_results")
            ]
            
            # Add custom args
            command.extend(self.config.custom_args)
            
            # Run locust
            returncode, stdout, stderr = run_command(
                command,
                cwd=target_path,
                timeout=self.config.timeout,
                env=self.config.environment
            )
            
            # Parse results
            findings = []
            status = ToolStatus.SUCCESS.value
            metadata = {}
            
            if returncode == 0:
                # Parse CSV results if available
                results_data = self._parse_locust_results(target_path)
                findings = self._analyze_performance_results(results_data)
                metadata = results_data
                
                if findings:
                    status = ToolStatus.ISSUES_FOUND.value.format(count=len(findings))
                else:
                    status = ToolStatus.SUCCESS.value
            else:
                status = ToolStatus.ERROR.value
                error_msg = stderr or "Locust execution failed"
                return ToolResult(
                    tool_name=self.name,
                    status=status,
                    error=error_msg,
                    output=stdout,
                    duration_seconds=__import__('time').time() - start_time
                )
            
            return ToolResult(
                tool_name=self.name,
                status=status,
                findings=findings,
                output=stdout,
                metadata=metadata,
                duration_seconds=__import__('time').time() - start_time
            )
            
        except Exception as e:
            self.logger.error(f"Locust performance test failed: {e}")
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR.value,
                error=str(e),
                duration_seconds=__import__('time').time() - start_time
            )
        finally:
            # Clean up temporary files
            try:
                temp_file = target_path / "temp_locustfile.py"
                if temp_file.exists():
                    temp_file.unlink()
            except Exception:
                pass
    
    def _create_default_locustfile(self, target_path: Path) -> Path:
        """Create a default locustfile for testing."""
        locustfile_content = '''
from locust import HttpUser, task, between

class WebsiteUser(HttpUser):
    wait_time = between(1, 3)
    
    @task(3)
    def index_page(self):
        self.client.get("/")
    
    @task(1)
    def about_page(self):
        self.client.get("/about", catch_response=True)
        
    @task(1)
    def api_health(self):
        response = self.client.get("/health")
        if response.status_code != 200:
            response.failure("Health check failed")
'''
        
        temp_file = target_path / "temp_locustfile.py"
        with open(temp_file, 'w') as f:
            f.write(locustfile_content)
        
        return temp_file
    
    def _parse_locust_results(self, target_path: Path) -> Dict[str, Any]:
        """Parse Locust CSV results."""
        results: Dict[str, Any] = {
            'requests_per_second': 0.0,
            'average_response_time': 0.0,
            'error_rate': 0.0,
            'total_requests': 0,
            'failed_requests': 0,
            'p95_response_time': 0.0,
            'p99_response_time': 0.0
        }
        
        try:
            # Parse stats CSV
            stats_file = target_path / "locust_results_stats.csv"
            if stats_file.exists():
                with open(stats_file, 'r') as f:
                    lines = f.readlines()
                    
                if len(lines) > 1:
                    # Parse the "Aggregated" line
                    for line in lines[1:]:
                        if 'Aggregated' in line or 'Total' in line:
                            parts = line.strip().split(',')
                            if len(parts) >= 10:
                                results['total_requests'] = int(parts[2]) if parts[2].isdigit() else 0
                                results['failed_requests'] = int(parts[3]) if parts[3].isdigit() else 0
                                results['average_response_time'] = float(parts[4]) if parts[4].replace('.', '').isdigit() else 0
                                results['requests_per_second'] = float(parts[10]) if parts[10].replace('.', '').isdigit() else 0
                                break
            
            # Calculate error rate
            if results['total_requests'] > 0:
                results['error_rate'] = (results['failed_requests'] / results['total_requests']) * 100
                
        except Exception as e:
            self.logger.warning(f"Failed to parse Locust results: {e}")
        
        return results
    
    def _analyze_performance_results(self, results: Dict[str, Any]) -> List[Finding]:
        """Analyze performance results and create findings for issues."""
        findings = []
        
        try:
            # Check response time thresholds
            avg_response_time = results.get('average_response_time', 0)
            if avg_response_time > 2000:  # > 2 seconds
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.HIGH.value,
                    confidence=Confidence.HIGH.value,
                    title="High average response time",
                    description=f"Average response time is {avg_response_time:.1f}ms, which exceeds 2000ms threshold",
                    category="performance",
                    rule_id="high_response_time",
                    tags=['performance', 'response_time'],
                    raw_data=results
                ))
            elif avg_response_time > 1000:  # > 1 second
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.MEDIUM.value,
                    confidence=Confidence.HIGH.value,
                    title="Elevated response time",
                    description=f"Average response time is {avg_response_time:.1f}ms, which exceeds 1000ms threshold",
                    category="performance",
                    rule_id="elevated_response_time",
                    tags=['performance', 'response_time'],
                    raw_data=results
                ))
            
            # Check error rate
            error_rate = results.get('error_rate', 0)
            if error_rate > 5:  # > 5% error rate
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.HIGH.value,
                    confidence=Confidence.HIGH.value,
                    title="High error rate",
                    description=f"Error rate is {error_rate:.1f}%, which exceeds 5% threshold",
                    category="reliability",
                    rule_id="high_error_rate",
                    tags=['performance', 'errors'],
                    raw_data=results
                ))
            elif error_rate > 1:  # > 1% error rate
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.MEDIUM.value,
                    confidence=Confidence.HIGH.value,
                    title="Elevated error rate",
                    description=f"Error rate is {error_rate:.1f}%, which exceeds 1% threshold",
                    category="reliability",
                    rule_id="elevated_error_rate",
                    tags=['performance', 'errors'],
                    raw_data=results
                ))
            
            # Check requests per second (throughput)
            rps = results.get('requests_per_second', 0)
            if rps < 10:  # Very low throughput
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.MEDIUM.value,
                    confidence=Confidence.MEDIUM.value,
                    title="Low throughput",
                    description=f"Requests per second is {rps:.1f}, which is below expected minimum of 10 RPS",
                    category="performance",
                    rule_id="low_throughput",
                    tags=['performance', 'throughput'],
                    raw_data=results
                ))
                
        except Exception as e:
            self.logger.warning(f"Failed to analyze performance results: {e}")
        
        return findings

@analysis_tool
class ApacheBenchTool(BaseAnalysisTool):
    """Apache Bench (ab) performance testing tool."""
    
    @property
    def name(self) -> str:
        return "apache-bench"
    
    @property
    def display_name(self) -> str:
        return "Apache Bench"
    
    @property
    def description(self) -> str:
        return "Simple HTTP load testing with Apache Bench"
    
    @property
    def tags(self) -> Set[str]:
        return {"performance", "load_testing", "web", "http", "simple"}
    
    @property
    def supported_languages(self) -> Set[str]:
        return {"web"}
    
    def is_available(self) -> bool:
        """Check if ab (Apache Bench) is available."""
        return find_executable("ab") is not None
    
    def get_version(self) -> Optional[str]:
        """Get ab version."""
        try:
            returncode, stdout, _ = run_command(["ab", "-V"], timeout=10)
            if returncode == 0:
                match = re.search(r'Version\s+(\d+\.\d+)', stdout)
                if match:
                    return match.group(1)
        except Exception as e:
            self.logger.debug(f"Failed to get ab version: {e}")
        return None
    
    def run_analysis(self, target_path: Path, **kwargs) -> ToolResult:
        """Run Apache Bench performance test."""
        start_time = __import__('time').time()
        
        try:
            # Get test configuration
            host = kwargs.get('host', 'http://localhost:5000')
            requests = kwargs.get('requests', 100)
            concurrency = kwargs.get('concurrency', 10)
            
            # Build ab command
            command = [
                "ab",
                "-n", str(requests),
                "-c", str(concurrency),
                "-g", str(target_path / "ab_results.tsv"),
                host + "/"
            ]
            
            # Add custom args
            command.extend(self.config.custom_args)
            
            # Run ab
            returncode, stdout, stderr = run_command(
                command,
                cwd=target_path,
                timeout=self.config.timeout,
                env=self.config.environment
            )
            
            # Parse results
            findings = []
            status = ToolStatus.SUCCESS.value
            metadata = {}
            
            if returncode == 0:
                results_data = self._parse_ab_results(stdout)
                findings = self._analyze_ab_results(results_data)
                metadata = results_data
                
                if findings:
                    status = ToolStatus.ISSUES_FOUND.value.format(count=len(findings))
                else:
                    status = ToolStatus.SUCCESS.value
            else:
                status = ToolStatus.ERROR.value
                error_msg = stderr or "Apache Bench execution failed"
                return ToolResult(
                    tool_name=self.name,
                    status=status,
                    error=error_msg,
                    output=stdout,
                    duration_seconds=__import__('time').time() - start_time
                )
            
            return ToolResult(
                tool_name=self.name,
                status=status,
                findings=findings,
                output=stdout,
                metadata=metadata,
                duration_seconds=__import__('time').time() - start_time
            )
            
        except Exception as e:
            self.logger.error(f"Apache Bench test failed: {e}")
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR.value,
                error=str(e),
                duration_seconds=__import__('time').time() - start_time
            )
    
    def _parse_ab_results(self, output: str) -> Dict[str, Any]:
        """Parse Apache Bench output."""
        results: Dict[str, Any] = {
            'requests_per_second': 0.0,
            'time_per_request': 0.0,
            'total_time': 0.0,
            'complete_requests': 0,
            'failed_requests': 0,
            'non_2xx_responses': 0
        }
        
        try:
            # Parse key metrics from ab output
            patterns = {
                'requests_per_second': r'Requests per second:\s+(\d+\.?\d*)',
                'time_per_request': r'Time per request:\s+(\d+\.?\d*)\s+\[ms\].*mean',
                'total_time': r'Time taken for tests:\s+(\d+\.?\d*)',
                'complete_requests': r'Complete requests:\s+(\d+)',
                'failed_requests': r'Failed requests:\s+(\d+)',
                'non_2xx_responses': r'Non-2xx responses:\s+(\d+)'
            }
            
            for key, pattern in patterns.items():
                match = re.search(pattern, output)
                if match:
                    results[key] = float(match.group(1))
                    
        except Exception as e:
            self.logger.warning(f"Failed to parse ab results: {e}")
        
        return results
    
    def _analyze_ab_results(self, results: Dict[str, Any]) -> List[Finding]:
        """Analyze ab results and create findings for issues."""
        findings = []
        
        try:
            # Check time per request
            time_per_request = results.get('time_per_request', 0)
            if time_per_request > 2000:  # > 2 seconds
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.HIGH.value,
                    confidence=Confidence.HIGH.value,
                    title="High response time",
                    description=f"Time per request is {time_per_request:.1f}ms, which exceeds 2000ms threshold",
                    category="performance",
                    rule_id="high_ab_response_time",
                    tags=['performance', 'response_time'],
                    raw_data=results
                ))
            
            # Check failed requests
            failed_requests = results.get('failed_requests', 0)
            complete_requests = results.get('complete_requests', 0)
            if complete_requests > 0:
                failure_rate = (failed_requests / complete_requests) * 100
                if failure_rate > 5:
                    findings.append(Finding(
                        tool=self.name,
                        severity=Severity.HIGH.value,
                        confidence=Confidence.HIGH.value,
                        title="High failure rate",
                        description=f"Failure rate is {failure_rate:.1f}%, which exceeds 5% threshold",
                        category="reliability",
                        rule_id="high_ab_failure_rate",
                        tags=['performance', 'failures'],
                        raw_data=results
                    ))
            
            # Check requests per second
            rps = results.get('requests_per_second', 0)
            if rps < 10:
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.MEDIUM.value,
                    confidence=Confidence.MEDIUM.value,
                    title="Low throughput",
                    description=f"Requests per second is {rps:.1f}, which is below expected minimum of 10 RPS",
                    category="performance",
                    rule_id="low_ab_throughput",
                    tags=['performance', 'throughput'],
                    raw_data=results
                ))
                
        except Exception as e:
            self.logger.warning(f"Failed to analyze ab results: {e}")
        
        return findings