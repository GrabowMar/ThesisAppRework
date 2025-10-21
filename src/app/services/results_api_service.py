"""
Results API Service
==================

Comprehensive service for fetching, transforming, and serving analysis results
for the frontend. Handles data transformation from the raw API format to
structured data for different analysis tabs.
"""

from typing import Dict, Any, Optional, List, Union
import requests
import json
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class SeverityLevel(Enum):
    """Severity levels for security findings."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AnalysisType(Enum):
    """Types of analysis performed."""
    SECURITY = "security"
    PERFORMANCE = "performance"
    QUALITY = "quality"
    REQUIREMENTS = "requirements"
    COMPREHENSIVE = "comprehensive"


@dataclass
class SecurityFinding:
    """Structured security finding data."""
    tool: str
    severity: str  # Use string instead of enum for JSON serialization
    rule_id: Optional[str]
    title: str
    description: str
    file_path: Optional[str]
    line_start: Optional[int]
    line_end: Optional[int]
    confidence: Optional[str]
    cwe_id: Optional[str]
    solution: Optional[str]
    code_snippet: Optional[str]
    metadata: Dict[str, Any]


@dataclass
class PerformanceMetric:
    """Structured performance metric data."""
    tool: str
    metric_name: str
    value: Union[float, int]
    unit: str
    status: str
    threshold: Optional[Union[float, int]]
    details: Dict[str, Any]


@dataclass
class QualityIssue:
    """Structured code quality issue data."""
    tool: str
    issue_type: str
    severity: str
    file_path: Optional[str]
    line_number: Optional[int]
    message: str
    rule_id: Optional[str]
    fixable: bool
    category: str


@dataclass
class RequirementMatch:
    """Structured AI requirements analysis data."""
    requirement: str
    status: str  # met, not_met, partial, unknown
    confidence: float
    explanation: str
    evidence: List[str]
    suggestions: List[str]


@dataclass
class AnalysisResults:
    """Complete analysis results for a task."""
    task_id: str
    status: str
    analysis_type: str
    model_slug: str
    app_number: int
    timestamp: datetime
    
    # Summary data
    total_findings: int
    duration: Optional[float]
    tools_executed: List[str]
    tools_failed: List[str]
    
    # Tab-specific data
    security: Dict[str, Any]
    performance: Dict[str, Any]
    quality: Dict[str, Any]
    requirements: Dict[str, Any]
    
    # Raw metadata
    raw_data: Dict[str, Any]


class ResultsAPIService:
    """Service for fetching and transforming analysis results."""
    
    def __init__(self, base_url: str = "http://127.0.0.1:5000"):
        """
        Initialize the results API service.
        
        Args:
            base_url: Base URL for the Flask API
        """
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        # Note: timeout is set per request rather than on session
    
    def get_task_results(self, task_id: str) -> Optional[AnalysisResults]:
        """
        Fetch and transform results for a specific task.
        
        Args:
            task_id: The task ID to fetch results for
            
        Returns:
            Transformed AnalysisResults object or None if not found
        """
        try:
            # Fetch raw results from API
            raw_data = self._fetch_raw_results(task_id)
            if not raw_data:
                return None
            
            # Transform the data
            return self._transform_results(task_id, raw_data)
            
        except Exception as e:
            logger.error(f"Error fetching results for task {task_id}: {e}")
            return None
    
    def _fetch_raw_results(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Fetch raw results for a task, preferring in-process access."""
        # Prefer in-process inspection service to avoid self-HTTP deadlocks
        raw_payload = self._fetch_via_internal_service(task_id)
        if raw_payload:
            return raw_payload

        # Fallback to HTTP request (works when running behind Gunicorn/WSGI or tests)
        try:
            url = f"{self.base_url}/analysis/api/tasks/{task_id}/results.json"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed for task {task_id}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON for task {task_id}: {e}")
            return None

    # ------------------------------------------------------------------
    # Internal fetch helpers
    # ------------------------------------------------------------------
    def _fetch_via_internal_service(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Attempt to load results through the service locator (no HTTP)."""
        try:
            from .service_locator import ServiceLocator  # Local import to avoid cycles
        except Exception:
            return None

        inspection_service = ServiceLocator.get('analysis_inspection_service')
        if not inspection_service:
            return None

        try:
            payload = inspection_service.get_task_results_payload(task_id)  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to load task %s via inspection service: %s", task_id, exc)
            return None

        if not isinstance(payload, dict) or not payload:
            return None

        return self._normalise_internal_payload(task_id, payload)

    def _normalise_internal_payload(self, task_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Convert inspection payload into the raw schema expected by transformers."""
        # Create shallow copies to avoid mutating the original payload (may be reused)
        results_payload: Dict[str, Any] = dict(payload)
        metadata_src: Dict[str, Any] = dict(results_payload.get('metadata') or {})
        metadata = self._normalise_metadata(task_id, metadata_src)
        results_payload['metadata'] = metadata

        self._ensure_task_block(results_payload, metadata)
        self._ensure_summary_block(results_payload)
        self._ensure_tools_block(results_payload)
        results_payload.setdefault('raw_outputs', results_payload.get('raw_outputs') or {})
        results_payload.setdefault('services', results_payload.get('services') or {})
        results_payload.setdefault('findings', results_payload.get('findings') or [])
        results_payload.setdefault('findings_preview', results_payload.get('findings_preview') or [])

        # Top-level raw schema mirrors the external API structure
        return {
            'metadata': dict(metadata),
            'results': results_payload
        }

    def _normalise_metadata(self, task_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure metadata contains a timestamp and consistent identifiers."""
        normalised = dict(metadata)

        # Promote identifiers for downstream consumers
        normalised.setdefault('task_id', metadata.get('task_id') or metadata.get('id') or task_id)

        # Determine timestamp (prefer provided values, fallback to now)
        timestamp = (
            metadata.get('timestamp') or
            metadata.get('generated_at') or
            metadata.get('analysis_time') or
            metadata.get('created_at')
        )

        if isinstance(timestamp, datetime):
            normalised['timestamp'] = timestamp.isoformat()
        elif isinstance(timestamp, str) and timestamp:
            normalised['timestamp'] = timestamp
        else:
            normalised['timestamp'] = datetime.now(timezone.utc).isoformat()

        # Note source for debugging clarity
        normalised.setdefault('source', 'analysis_inspection_service')
        return normalised

    def _ensure_task_block(self, results_payload: Dict[str, Any], metadata: Dict[str, Any]) -> None:
        """Guarantee a task block is present with essential identifiers."""
        task_block = dict(results_payload.get('task') or {})

        fallback_values = {
            'task_id': results_payload.get('task_id') or metadata.get('task_id'),
            'analysis_type': results_payload.get('analysis_type') or metadata.get('analysis_type'),
            'model_slug': results_payload.get('model_slug') or metadata.get('model_slug'),
            'app_number': results_payload.get('app_number') or metadata.get('app_number'),
            'status': results_payload.get('derived_status') or results_payload.get('status') or metadata.get('status'),
        }

        for key, value in fallback_values.items():
            if key not in task_block or task_block[key] in (None, ''):
                task_block[key] = value

        results_payload['task'] = task_block

    def _ensure_summary_block(self, results_payload: Dict[str, Any]) -> None:
        """Ensure summary information is available for downstream use."""
        findings = results_payload.get('findings') or []
        summary = dict(results_payload.get('summary') or {})

        summary.setdefault('total_findings', results_payload.get('findings_total') or len(findings))
        summary.setdefault('severity_breakdown', results_payload.get('severity_breakdown') or results_payload.get('findings_by_severity') or {})
        summary.setdefault('findings_by_tool', results_payload.get('findings_by_tool') or {})
        summary.setdefault('tools_used', results_payload.get('tools_used') or [])
        summary.setdefault('tools_failed', results_payload.get('tools_failed') or results_payload.get('tools_skipped') or [])
        summary.setdefault('status', results_payload.get('derived_status') or results_payload.get('status') or summary.get('status'))

        results_payload['summary'] = summary

    def _ensure_tools_block(self, results_payload: Dict[str, Any]) -> None:
        """Build a tool map if one is missing (requires tool_metrics fallback)."""
        if isinstance(results_payload.get('tools'), dict) and results_payload['tools']:
            return

        metrics = results_payload.get('tool_metrics') or {}
        if not isinstance(metrics, dict):
            results_payload['tools'] = {}
            return

        tools_used = set(results_payload.get('tools_used') or [])
        tools_failed = set(results_payload.get('tools_failed') or [])

        tool_map: Dict[str, Any] = {}
        for tool_name, info in metrics.items():
            if not isinstance(info, dict):
                continue

            status = info.get('status')
            if not status:
                if tool_name in tools_failed:
                    status = 'error'
                elif tool_name in tools_used:
                    status = 'success'
                else:
                    status = 'not_available'

            tool_map[tool_name] = {
                'status': status,
                'executed': tool_name in tools_used,
                'total_issues': info.get('total_issues', 0),
                'duration_seconds': info.get('duration_seconds'),
                'exit_code': info.get('exit_code'),
                'error': info.get('error'),
                'files_analyzed': info.get('files_analyzed'),
                'metrics': info.get('metrics'),
            }

        results_payload['tools'] = tool_map
    
    def _transform_results(self, task_id: str, raw_data: Dict[str, Any]) -> AnalysisResults:
        """
        Transform raw API data into structured AnalysisResults.
        
        Args:
            task_id: The task ID
            raw_data: Raw data from the API
            
        Returns:
            Transformed AnalysisResults object
        """
        # Extract metadata
        metadata = raw_data.get('metadata', {})
        results = raw_data.get('results', {})
        
        # Basic task info
        task_info = results.get('task', {})
        summary = results.get('summary', {})
        
        # Create AnalysisResults object
        analysis_results = AnalysisResults(
            task_id=task_id,
            status=summary.get('status', 'unknown'),
            analysis_type=task_info.get('analysis_type', 'unknown'),
            model_slug=task_info.get('model_slug', ''),
            app_number=task_info.get('app_number', 0),
            timestamp=self._parse_timestamp(metadata.get('timestamp')),
            
            total_findings=summary.get('total_findings', 0),
            duration=self._calculate_duration(task_info),
            tools_executed=summary.get('tools_used', []),
            tools_failed=summary.get('tools_failed', []),
            
            security=self._transform_security_data(results),
            performance=self._transform_performance_data(results),
            quality=self._transform_quality_data(results),
            requirements=self._transform_requirements_data(results),
            
            raw_data=raw_data
        )
        
        return analysis_results
    
    def _transform_security_data(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Transform security-related data."""
        security_data = {
            'findings': [],
            'summary': {
                'critical': 0,
                'high': 0,
                'medium': 0,
                'low': 0,
                'total': 0
            },
            'tools_run': [],
            'recommendations': []
        }
        
        # Extract security findings
        findings = results.get('findings', [])
        security_findings = []
        
        for finding in findings:
            # Filter security-related findings
            if self._is_security_finding(finding):
                security_finding = self._create_security_finding(finding)
                security_findings.append(security_finding)
                
                # Update summary counts
                severity = security_finding.severity
                if severity in security_data['summary']:
                    security_data['summary'][severity] += 1
                security_data['summary']['total'] += 1
        
        security_data['findings'] = [asdict(f) for f in security_findings]
        
        # Extract security tools
        security_data['tools_run'] = self._get_security_tools(results)
        
        # Generate recommendations
        security_data['recommendations'] = self._generate_security_recommendations(security_findings)
        
        return security_data
    
    def _transform_performance_data(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Transform performance-related data."""
        performance_data = {
            'metrics': {
                'response_time': {'value': None, 'unit': 'ms', 'status': 'unknown'},
                'requests_per_sec': {'value': None, 'unit': 'req/s', 'status': 'unknown'},
                'failed_requests': {'value': None, 'unit': '%', 'status': 'unknown'},
                'max_concurrent': {'value': None, 'unit': 'users', 'status': 'unknown'}
            },
            'tools': {
                'apache_bench': {'status': 'unknown', 'results': {}},
                'locust': {'status': 'unknown', 'results': {}},
                'aiohttp': {'status': 'unknown', 'results': {}}
            },
            'recommendations': []
        }
        
        # Extract performance metrics from different services
        services = results.get('services', {})
        
        # Check performance-tester service
        perf_service = services.get('performance-tester', {})
        if perf_service:
            performance_data = self._extract_performance_metrics(perf_service, performance_data)
        
        # Generate performance recommendations
        performance_data['recommendations'] = self._generate_performance_recommendations(performance_data)
        
        return performance_data
    
    def _transform_quality_data(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Transform code quality-related data."""
        quality_data = {
            'summary': {
                'errors': 0,
                'warnings': 0,
                'info': 0,
                'type_errors': 0,
                'dead_code': 0
            },
            'tools': {
                'pylint': {'status': 'unknown', 'issues': 0},
                'mypy': {'status': 'unknown', 'issues': 0},
                'vulture': {'status': 'unknown', 'issues': 0},
                'eslint': {'status': 'unknown', 'issues': 0},
                'jshint': {'status': 'unknown', 'issues': 0},
                'safety': {'status': 'unknown', 'issues': 0}
            },
            'issues': [],
            'insights': {
                'import_issues': [],
                'type_safety': []
            }
        }
        
        # Extract quality issues from findings
        findings = results.get('findings', [])
        for finding in findings:
            if self._is_quality_finding(finding):
                quality_issue = self._create_quality_issue(finding)
                quality_data['issues'].append(asdict(quality_issue))
                
                # Update summary counts
                issue_type = quality_issue.issue_type.lower()
                if 'error' in issue_type:
                    quality_data['summary']['errors'] += 1
                elif 'warning' in issue_type:
                    quality_data['summary']['warnings'] += 1
                elif 'type' in issue_type:
                    quality_data['summary']['type_errors'] += 1
                elif 'dead' in issue_type or 'unused' in issue_type:
                    quality_data['summary']['dead_code'] += 1
                else:
                    quality_data['summary']['info'] += 1
        
        # Update tool status from services
        self._update_quality_tool_status(results, quality_data)
        
        return quality_data
    
    def _transform_requirements_data(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Transform AI requirements analysis data."""
        requirements_data = {
            'summary': {
                'total_requirements': 0,
                'met': 0,
                'not_met': 0,
                'partial': 0,
                'compliance_percentage': 0.0
            },
            'analysis_details': {
                'status': 'unknown',
                'target_model': '',
                'analysis_time': None,
                'configuration': None
            },
            'requirements': [],
            'insights': {
                'security_features': [],
                'authentication': []
            }
        }
        
        # Extract AI analysis data - pass the full results to the extraction method
        requirements_data = self._extract_ai_requirements(results, requirements_data)
        
        return requirements_data
    
    def _is_security_finding(self, finding: Dict[str, Any]) -> bool:
        """Check if a finding is security-related."""
        tool = finding.get('tool', '').lower()
        category = finding.get('category', '').lower()
        message = finding.get('message', {})
        
        security_tools = ['bandit', 'semgrep', 'zap', 'safety', 'curl', 'nmap']
        security_categories = ['security', 'vulnerability', 'cve', 'cwe']
        
        return (tool in security_tools or 
                category in security_categories or
                'security' in str(message).lower())
    
    def _create_security_finding(self, finding: Dict[str, Any]) -> SecurityFinding:
        """Create a SecurityFinding from raw finding data."""
        message = finding.get('message', {})
        file_info = finding.get('file', {})
        metadata = finding.get('metadata', {})
        evidence = finding.get('evidence', {})
        
        # Determine severity as string (don't use enum for JSON storage)
        severity_str = finding.get('severity', 'medium').lower()
        
        return SecurityFinding(
            tool=finding.get('tool', 'unknown'),
            severity=severity_str,  # Use string instead of enum
            rule_id=finding.get('rule_id') or metadata.get('rule_id'),
            title=message.get('title', '') or message.get('description', '')[:50],
            description=message.get('description', '') or message.get('title', ''),
            file_path=file_info.get('path'),
            line_start=file_info.get('line_start') or finding.get('line_number'),
            line_end=file_info.get('line_end'),
            confidence=finding.get('confidence'),
            cwe_id=metadata.get('cwe_id'),
            solution=message.get('solution'),
            code_snippet=evidence.get('code_snippet'),
            metadata=metadata
        )
    
    def _is_quality_finding(self, finding: Dict[str, Any]) -> bool:
        """Check if a finding is code quality-related."""
        tool = finding.get('tool', '').lower()
        quality_tools = ['pylint', 'mypy', 'vulture', 'eslint', 'jshint', 'flake8']
        return tool in quality_tools
    
    def _create_quality_issue(self, finding: Dict[str, Any]) -> QualityIssue:
        """Create a QualityIssue from raw finding data."""
        message = finding.get('message', {})
        file_info = finding.get('file', {})
        
        return QualityIssue(
            tool=finding.get('tool', 'unknown'),
            issue_type=finding.get('type', 'unknown'),
            severity=finding.get('severity', 'medium'),
            file_path=file_info.get('path'),
            line_number=file_info.get('line_start') or finding.get('line_number'),
            message=message.get('description', '') or message.get('title', ''),
            rule_id=finding.get('rule_id'),
            fixable=finding.get('fixable', False),
            category=finding.get('category', 'other')
        )
    
    def _get_security_tools(self, results: Dict[str, Any]) -> List[str]:
        """Extract list of security tools that were executed."""
        security_tools = []
        
        tools = results.get('tools', {})
        
        # Check from tools section
        security_tool_names = ['bandit', 'semgrep', 'zap', 'safety', 'curl', 'nmap']
        for tool_name in security_tool_names:
            tool_data = tools.get(tool_name, {})
            if tool_data.get('executed', False) or tool_data.get('status') == 'success':
                security_tools.append(tool_name)
        
        return security_tools
    
    def _generate_security_recommendations(self, findings: List[SecurityFinding]) -> List[Dict[str, Any]]:
        """Generate security recommendations based on findings."""
        recommendations = []
        
        # Check for common security issues and generate recommendations
        tools_with_findings = {f.tool for f in findings}
        
        if any(f.cwe_id for f in findings):
            recommendations.append({
                'type': 'container_security',
                'title': 'Container Security',
                'message': 'Consider adding non-root USER directive to Dockerfiles to reduce privilege escalation risks.',
                'severity': 'info',
                'source': 'semgrep findings'
            })
        
        if 'bandit' in tools_with_findings or 'semgrep' in tools_with_findings:
            recommendations.append({
                'type': 'network_security',
                'title': 'Network Security', 
                'message': 'Avoid binding to 0.0.0.0 in production. Use specific IP addresses or reverse proxy.',
                'severity': 'warning',
                'source': 'bandit/semgrep findings'
            })
        
        if 'zap' in tools_with_findings:
            recommendations.append({
                'type': 'http_headers',
                'title': 'HTTP Headers',
                'message': 'Implement security headers: CSP, HSTS, X-Frame-Options, X-Content-Type-Options.',
                'severity': 'danger',
                'source': 'ZAP findings'
            })
        
        # Always add general recommendation
        recommendations.append({
            'type': 'code_quality',
            'title': 'Code Quality',
            'message': 'Regular security code reviews and dependency updates recommended.',
            'severity': 'success',
            'source': 'general best practice'
        })
        
        return recommendations
    
    def _extract_performance_metrics(self, perf_service: Dict[str, Any], performance_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract performance metrics from performance service data."""
        try:
            # Get performance analysis from the service data
            services = perf_service.get('services', {})
            perf_analysis = services.get('performance', {})
            
            if perf_analysis and perf_analysis.get('status') == 'success':
                analysis_results = perf_analysis.get('analysis', {}).get('results', {})
                
                # Extract metrics from the first available URL result
                for url, url_data in analysis_results.items():
                    # Apache Bench metrics
                    if 'ab' in url_data:
                        ab_data = url_data['ab']
                        if ab_data.get('status') == 'success':
                            performance_data['metrics']['response_time']['value'] = ab_data.get('avg_response_time', 0) * 1000  # Convert to ms
                            performance_data['metrics']['response_time']['status'] = 'success'
                            performance_data['metrics']['requests_per_sec']['value'] = ab_data.get('requests_per_second', 0)
                            performance_data['metrics']['requests_per_sec']['status'] = 'success'
                            performance_data['metrics']['failed_requests']['value'] = ab_data.get('failed_requests', 0)
                            performance_data['metrics']['failed_requests']['status'] = 'success'
                            performance_data['tools']['apache_bench'] = {
                                'status': 'success',
                                'results': ab_data
                            }
                    
                    # Locust metrics
                    if 'locust' in url_data:
                        locust_data = url_data['locust']
                        if locust_data.get('status') == 'success':
                            performance_data['tools']['locust'] = {
                                'status': 'success',
                                'results': locust_data
                            }
                    
                    # aiohttp metrics
                    if 'aiohttp' in url_data:
                        aiohttp_data = url_data['aiohttp']
                        if aiohttp_data.get('status') == 'success':
                            performance_data['tools']['aiohttp'] = {
                                'status': 'success',
                                'results': aiohttp_data
                            }
                    
                    # Only process the first available URL for now
                    break
            
            return performance_data
            
        except Exception as e:
            logger.warning(f"Error extracting performance metrics: {e}")
            return performance_data
    
    def _generate_performance_recommendations(self, performance_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate performance recommendations."""
        return [
            {
                'type': 'response_time',
                'title': 'Response Time Optimization',
                'message': 'Consider implementing caching, compression, and CDN for better response times.',
                'icon': 'fas fa-tachometer-alt'
            },
            {
                'type': 'scalability',
                'title': 'Scalability',
                'message': 'Implement horizontal scaling and load balancing for better performance under load.',
                'icon': 'fas fa-expand-arrows-alt'
            }
        ]
    
    def _update_quality_tool_status(self, results: Dict[str, Any], quality_data: Dict[str, Any]) -> None:
        """Update quality tool status from results data."""
        tools = results.get('tools', {})
        
        for tool_name in quality_data['tools']:
            tool_info = tools.get(tool_name, {})
            if tool_info:
                quality_data['tools'][tool_name] = {
                    'status': tool_info.get('status', 'unknown'),
                    'issues': tool_info.get('total_issues', 0)
                }
    
    def _extract_ai_requirements(self, raw_outputs: Dict[str, Any], requirements_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract AI requirements analysis from raw outputs."""
        try:
            # Look for AI analyzer service data
            services = raw_outputs.get('services', {})
            ai_service = services.get('ai-analyzer', {})
            
            if ai_service and ai_service.get('success', False):
                # Get analysis details
                requirements_data['analysis_details']['status'] = 'success'
                requirements_data['analysis_details']['target_model'] = ai_service.get('model_slug', '')
                requirements_data['analysis_details']['analysis_time'] = ai_service.get('analysis_duration', 0)
                
                # Get raw analysis data
                raw_analysis = ai_service.get('raw_outputs', {})
                if raw_analysis and raw_analysis.get('status') == 'success':
                    analysis = raw_analysis.get('analysis', {})
                    results = analysis.get('results', {})
                    
                    # Extract summary data
                    summary = results.get('summary', {})
                    if summary:
                        requirements_data['summary']['total_requirements'] = summary.get('total_requirements', 0)
                        requirements_data['summary']['met'] = summary.get('requirements_met', 0)
                        requirements_data['summary']['not_met'] = summary.get('requirements_not_met', 0)
                        requirements_data['summary']['compliance_percentage'] = summary.get('compliance_percentage', 0.0)
                    
                    # Extract individual requirement checks
                    requirement_checks = results.get('requirement_checks', [])
                    for check in requirement_checks:
                        requirement = check.get('requirement', '')
                        result = check.get('result', {})
                        
                        req_item = {
                            'id': f"req_{len(requirements_data['requirements']) + 1}",
                            'title': requirement.split('::')[0] if '::' in requirement else requirement,
                            'description': requirement.split('::', 1)[1] if '::' in requirement else '',
                            'status': 'met' if result.get('met', False) else 'not_met',
                            'confidence': result.get('confidence', 'UNKNOWN').lower(),
                            'explanation': result.get('explanation', ''),
                            'category': 'functional'  # Default category
                        }
                        requirements_data['requirements'].append(req_item)
            
            return requirements_data
            
        except Exception as e:
            logger.warning(f"Error extracting AI requirements: {e}")
            return requirements_data
    
    def _parse_timestamp(self, timestamp_str: Optional[str]) -> datetime:
        """Parse timestamp string to datetime object."""
        if not timestamp_str:
            return datetime.now(timezone.utc)
        
        try:
            # Handle various timestamp formats
            if 'T' in timestamp_str and '+' in timestamp_str:
                return datetime.fromisoformat(timestamp_str.replace('+00:00', '+0000'))
            elif 'T' in timestamp_str:
                return datetime.fromisoformat(timestamp_str)
            else:
                return datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            return datetime.now(timezone.utc)
    
    def _calculate_duration(self, task_info: Dict[str, Any]) -> Optional[float]:
        """Calculate task duration from start/end times."""
        started_at = task_info.get('started_at')
        completed_at = task_info.get('completed_at')
        
        if not started_at or not completed_at:
            return None
        
        try:
            start_time = self._parse_timestamp(started_at)
            end_time = self._parse_timestamp(completed_at)
            return (end_time - start_time).total_seconds()
        except (ValueError, TypeError):
            return None