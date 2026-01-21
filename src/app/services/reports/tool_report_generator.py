"""
Tool Report Generator

Generates tool effectiveness reports showing performance across all analyses.
Global analysis with optional filtering by model/app.

Enhanced with:
- Scientific metrics (mean, median, std_dev, variance, CV)
- CWE vulnerability statistics
- LOC metrics and defect density
- Quantitative metrics from performance tests
"""
import re
import logging
import statistics
from typing import Dict, Any, List, Optional
from pathlib import Path
from collections import defaultdict, Counter

from .base_generator import BaseReportGenerator
from ...extensions import db
from ...models import AnalysisTask, PerformanceTest, OpenRouterAnalysis, SecurityAnalysis
from ...constants import AnalysisStatus
from ...services.service_locator import ServiceLocator
from ...services.service_base import ValidationError, NotFoundError
from ...utils.time import utc_now

logger = logging.getLogger(__name__)


def _count_loc_from_files(model_slug: str, app_number: int) -> Dict[str, int]:
    """
    Count lines of code from generated app files.
    
    Returns:
        Dict with keys: total_loc, python_loc, javascript_loc, files_analyzed
    """
    result = {
        'total_loc': 0,
        'python_loc': 0,
        'javascript_loc': 0,
        'jsx_loc': 0,
        'css_loc': 0,
        'html_loc': 0,
        'other_loc': 0,
        'files_analyzed': 0,
    }
    
    # Build path to generated app
    base_path = Path(__file__).resolve().parent.parent.parent.parent.parent / 'generated' / 'apps'
    safe_slug = model_slug.replace('/', '_').replace('\\', '_')
    app_path = base_path / safe_slug / f"app{app_number}"
    
    if not app_path.exists():
        return result
    
    # Extensions to analyze
    extension_map = {
        '.py': 'python_loc',
        '.js': 'javascript_loc',
        '.jsx': 'jsx_loc',
        '.ts': 'javascript_loc',
        '.tsx': 'jsx_loc',
        '.css': 'css_loc',
        '.html': 'html_loc',
        '.htm': 'html_loc',
    }
    
    # Walk directory and count lines
    for file_path in app_path.rglob('*'):
        if not file_path.is_file():
            continue
        
        # Skip common non-source directories
        path_str = str(file_path)
        if any(skip in path_str for skip in ['node_modules', '__pycache__', '.git', 'venv', '.venv', 'dist', 'build']):
            continue
        
        ext = file_path.suffix.lower()
        if ext not in extension_map:
            continue
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = len([l for l in f.readlines() if l.strip()])  # Non-empty lines
                
                result['total_loc'] += lines
                result[extension_map[ext]] += lines
                result['files_analyzed'] += 1
        except Exception:
            pass
    
    return result


class ToolReportGenerator(BaseReportGenerator):
    """Generator for tool-centric performance reports.
    
    Enhanced with scientific metrics, CWE analysis, and quantitative measurements.
    """
    
    # Known analysis tools by category - for classification and filtering
    KNOWN_TOOLS = {
        # Static Analysis - Python
        'bandit': {'category': 'security', 'language': 'python'},
        'semgrep': {'category': 'security', 'language': 'multi'},
        'pylint': {'category': 'quality', 'language': 'python'},
        'flake8': {'category': 'quality', 'language': 'python'},
        'mypy': {'category': 'types', 'language': 'python'},
        'ruff': {'category': 'quality', 'language': 'python'},
        'safety': {'category': 'dependencies', 'language': 'python'},
        'pip-audit': {'category': 'dependencies', 'language': 'python'},
        'vulture': {'category': 'quality', 'language': 'python'},
        'radon': {'category': 'complexity', 'language': 'python'},
        # Static Analysis - JavaScript
        'eslint': {'category': 'quality', 'language': 'javascript'},
        'jshint': {'category': 'quality', 'language': 'javascript'},
        'npm-audit': {'category': 'dependencies', 'language': 'javascript'},
        'stylelint': {'category': 'quality', 'language': 'css'},
        # Dynamic Analysis
        'zap': {'category': 'security', 'language': 'runtime'},
        'owasp-zap': {'category': 'security', 'language': 'runtime'},
        # Performance
        'locust': {'category': 'performance', 'language': 'runtime'},
        'artillery': {'category': 'performance', 'language': 'runtime'},
        'ab': {'category': 'performance', 'language': 'runtime'},
        'aiohttp': {'category': 'performance', 'language': 'runtime'},
        # AI Analysis
        'ai-analyzer': {'category': 'ai', 'language': 'multi'},
    }
    
    # CWE categories for vulnerability classification
    CWE_CATEGORIES = {
        'CWE-78': 'OS Command Injection',
        'CWE-79': 'Cross-site Scripting (XSS)',
        'CWE-89': 'SQL Injection',
        'CWE-94': 'Code Injection',
        'CWE-95': 'Eval Injection',
        'CWE-119': 'Buffer Overflow',
        'CWE-125': 'Out-of-bounds Read',
        'CWE-200': 'Information Exposure',
        'CWE-259': 'Hard-coded Password',
        'CWE-284': 'Access Control',
        'CWE-285': 'Improper Authorization',
        'CWE-287': 'Authentication Issues',
        'CWE-311': 'Missing Encryption',
        'CWE-312': 'Cleartext Storage',
        'CWE-327': 'Broken Crypto',
        'CWE-400': 'Resource Exhaustion',
        'CWE-434': 'Unrestricted Upload',
        'CWE-502': 'Deserialization',
        'CWE-601': 'Open Redirect',
        'CWE-611': 'XXE',
        'CWE-798': 'Hard-coded Credentials',
    }
    
    # =========================================================================
    # Helper Methods for Enhanced Metrics
    # =========================================================================
    
    def _extract_tools_from_services(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract flattened tool results from nested service structures.
        
        Handles multiple result formats from analyzer_manager.
        Applies filter_mode from config to exclude/include specific analyzer services.
        """
        tools = {}
        
        # Direct tools key
        if 'tools' in raw_data:
            tools.update(raw_data['tools'])
        
        # Nested in results
        results = raw_data.get('results', {})
        if isinstance(results, dict):
            if 'tools' in results:
                tools.update(results['tools'])
            
            # Tool results nested under services - apply filter here
            services = results.get('services', {})
            services = self.filter_services_data(services)
            if isinstance(services, dict):
                for service_name, service_data in services.items():
                    if isinstance(service_data, dict):
                        # Check for tool_results in analysis
                        analysis = service_data.get('analysis', {})
                        if isinstance(analysis, dict):
                            tool_results = analysis.get('tool_results', {})
                            if isinstance(tool_results, dict):
                                for tool_name, tool_data in tool_results.items():
                                    if tool_name not in tools:
                                        tools[tool_name] = tool_data
        
        # Services at top level
        if 'services' in raw_data:
            for service_name, service_data in raw_data.get('services', {}).items():
                if isinstance(service_data, dict):
                    analysis = service_data.get('analysis', {})
                    if isinstance(analysis, dict):
                        tool_results = analysis.get('tool_results', {})
                        if isinstance(tool_results, dict):
                            for tool_name, tool_data in tool_results.items():
                                if tool_name not in tools:
                                    tools[tool_name] = tool_data
        
        return tools
    
    def _extract_findings_from_services(self, raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract findings from nested service structures.
        
        Handles multiple result formats and deduplicates.
        Applies filter_mode from config to exclude/include specific analyzer services.
        """
        findings = []
        seen_signatures = set()
        
        def add_finding(finding: Dict[str, Any]):
            sig = f"{finding.get('file', '')}:{finding.get('line', 0)}:{finding.get('rule_id', '')}:{finding.get('message', '')[:50]}"
            if sig not in seen_signatures:
                seen_signatures.add(sig)
                findings.append(finding)
        
        # Direct findings key
        if 'findings' in raw_data and isinstance(raw_data['findings'], list):
            for f in raw_data['findings']:
                add_finding(f)
        
        # Nested in results - apply filter to services
        results = raw_data.get('results', {})
        if isinstance(results, dict):
            if 'findings' in results and isinstance(results['findings'], list):
                for f in results['findings']:
                    add_finding(f)
            
            # Findings nested under services - apply filter
            services = results.get('services', {})
            services = self.filter_services_data(services)
            if isinstance(services, dict):
                for service_data in services.values():
                    if isinstance(service_data, dict):
                        svc_findings = service_data.get('findings', [])
                        if isinstance(svc_findings, list):
                            for f in svc_findings:
                                add_finding(f)
        
        # Services at top level - apply filter
        if 'services' in raw_data:
            services = self.filter_services_data(raw_data.get('services', {}))
            for service_data in services.values():
                if isinstance(service_data, dict):
                    svc_findings = service_data.get('findings', [])
                    if isinstance(svc_findings, list):
                        for f in svc_findings:
                            add_finding(f)
        
        return findings
    
    def _calculate_scientific_metrics(self, values: List[float]) -> Dict[str, float]:
        """Calculate scientific statistics for a list of numeric values.
        
        Returns dict with: count, sum, mean, median, std_dev, variance, min, max, range, cv
        """
        if not values:
            return {}
        
        n = len(values)
        total = sum(values)
        mean = total / n if n > 0 else 0
        
        result = {
            'count': n,
            'sum': round(total, 4),
            'mean': round(mean, 4),
            'min': round(min(values), 4),
            'max': round(max(values), 4),
            'range': round(max(values) - min(values), 4),
        }
        
        if n >= 2:
            result['median'] = round(statistics.median(values), 4)
            result['std_dev'] = round(statistics.stdev(values), 4)
            result['variance'] = round(statistics.variance(values), 4)
            # Coefficient of variation (CV) - relative standard deviation
            if mean != 0:
                result['cv'] = round((result['std_dev'] / abs(mean)) * 100, 2)
            else:
                result['cv'] = 0.0
        else:
            result['median'] = result['mean']
            result['std_dev'] = 0.0
            result['variance'] = 0.0
            result['cv'] = 0.0
        
        return result
    
    def _extract_cwe_statistics(self, findings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract and categorize CWE statistics from findings.
        
        Returns dict with: cwe_counts, top_cwes, cwe_categories, total_with_cwe
        """
        cwe_counter = Counter()
        findings_with_cwe = 0
        
        # Pattern to extract CWE IDs
        cwe_pattern = re.compile(r'CWE-(\d+)', re.IGNORECASE)
        
        for finding in findings:
            cwe_id = None
            
            # Check common CWE field locations
            if 'cwe' in finding:
                cwe_val = finding['cwe']
                if isinstance(cwe_val, str):
                    match = cwe_pattern.search(cwe_val)
                    if match:
                        cwe_id = f"CWE-{match.group(1)}"
                elif isinstance(cwe_val, int):
                    cwe_id = f"CWE-{cwe_val}"
            
            # Check rule_id for CWE references
            if not cwe_id and 'rule_id' in finding:
                match = cwe_pattern.search(str(finding['rule_id']))
                if match:
                    cwe_id = f"CWE-{match.group(1)}"
            
            # Check message for CWE references
            if not cwe_id and 'message' in finding:
                match = cwe_pattern.search(str(finding['message']))
                if match:
                    cwe_id = f"CWE-{match.group(1)}"
            
            if cwe_id:
                cwe_counter[cwe_id] += 1
                findings_with_cwe += 1
        
        # Build result
        top_cwes = cwe_counter.most_common(10)
        cwe_with_names = [
            {
                'cwe_id': cwe_id,
                'count': count,
                'name': self.CWE_CATEGORIES.get(cwe_id, 'Unknown')
            }
            for cwe_id, count in top_cwes
        ]
        
        # Categorize by vulnerability type
        categories = defaultdict(int)
        for cwe_id, count in cwe_counter.items():
            category = self.CWE_CATEGORIES.get(cwe_id, 'Other')
            categories[category] += count
        
        return {
            'total_with_cwe': findings_with_cwe,
            'unique_cwes': len(cwe_counter),
            'cwe_counts': dict(cwe_counter),
            'top_cwes': cwe_with_names,
            'categories': dict(categories),
        }
    
    def _calculate_loc_metrics(self, model_slug: str, app_number: int, findings_count: int) -> Dict[str, Any]:
        """Calculate LOC metrics for a specific app.
        
        Uses _count_loc_from_files() standalone function.
        """
        loc_data = _count_loc_from_files(model_slug, app_number)
        
        total_loc = loc_data.get('total_loc', 0)
        
        return {
            'total_loc': total_loc,
            'python_loc': loc_data.get('python_loc', 0),
            'javascript_loc': loc_data.get('javascript_loc', 0),
            'jsx_loc': loc_data.get('jsx_loc', 0),
            'css_loc': loc_data.get('css_loc', 0),
            'files_analyzed': loc_data.get('files_analyzed', 0),
            'defect_density': round(findings_count / total_loc * 1000, 4) if total_loc > 0 else 0,  # per 1000 LOC
        }
    
    def _get_quantitative_metrics_for_model(self, model_slug: str, app_number: int) -> Dict[str, Any]:
        """Load quantitative metrics from database for a model/app.
        
        Queries: PerformanceTest, OpenRouterAnalysis, SecurityAnalysis tables.
        These tables use application_id FK, so we query through GeneratedApplication.
        """
        result: Dict[str, Any] = {
            'performance': None,
            'ai_analysis': None,
            'security_scan': None,
        }
        
        # First get the application ID for this model/app
        try:
            from app.models import GeneratedApplication
            app = GeneratedApplication.query.filter_by(
                model_slug=model_slug,
                app_number=app_number
            ).first()
            
            if not app:
                return result
            app_id = app.id
        except Exception as e:
            logger.debug(f"Error getting app ID for metrics: {e}")
            return result
        
        try:
            # Performance test results - query by application_id
            # Columns: application_id, average_response_time, p95_response_time, p99_response_time, error_rate, requests_per_second
            perf_test = PerformanceTest.query.filter_by(
                application_id=app_id
            ).order_by(PerformanceTest.created_at.desc()).first()
            
            if perf_test:
                result['performance'] = {
                    'avg_response_time_ms': perf_test.average_response_time,
                    'requests_per_second': perf_test.requests_per_second,
                    'error_rate': perf_test.error_rate,
                    'p95_response_time_ms': perf_test.p95_response_time,
                    'total_requests': getattr(perf_test, 'total_requests', None),
                    'successful_requests': getattr(perf_test, 'successful_requests', None),
                    'created_at': perf_test.created_at.isoformat() if perf_test.created_at else None,
                }
        except Exception as e:
            logger.debug(f"Error loading performance metrics: {e}")
        
        try:
            # AI/OpenRouter analysis results - query by application_id
            # Columns: application_id, overall_score, code_quality_score, security_score, maintainability_score
            ai_analysis = OpenRouterAnalysis.query.filter_by(
                application_id=app_id
            ).order_by(OpenRouterAnalysis.created_at.desc()).first()
            
            if ai_analysis:
                result['ai_analysis'] = {
                    'total_cost': getattr(ai_analysis, 'total_cost', None),
                    'total_tokens': getattr(ai_analysis, 'total_tokens', None),
                    'prompt_tokens': getattr(ai_analysis, 'prompt_tokens', None),
                    'completion_tokens': getattr(ai_analysis, 'completion_tokens', None),
                    'analysis_model': getattr(ai_analysis, 'analysis_model', None),
                    'compliance_score': ai_analysis.overall_score,  # Use overall_score as compliance proxy
                    'code_quality_score': ai_analysis.code_quality_score,
                    'security_score': ai_analysis.security_score,
                    'created_at': ai_analysis.created_at.isoformat() if ai_analysis.created_at else None,
                }
        except Exception as e:
            logger.debug(f"Error loading AI analysis metrics: {e}")
        
        try:
            # Security scan results - query by application_id
            # Columns: application_id, total_issues, critical_severity_count, high_severity_count, medium_severity_count, low_severity_count
            sec_scan = SecurityAnalysis.query.filter_by(
                application_id=app_id
            ).order_by(SecurityAnalysis.created_at.desc()).first()
            
            if sec_scan:
                result['security_scan'] = {
                    'total_vulnerabilities': sec_scan.total_issues,
                    'critical_count': sec_scan.critical_severity_count,
                    'high_count': sec_scan.high_severity_count,
                    'medium_count': sec_scan.medium_severity_count,
                    'low_count': sec_scan.low_severity_count,
                    'scan_duration_seconds': getattr(sec_scan, 'scan_duration_seconds', None),
                    'created_at': sec_scan.created_at.isoformat() if sec_scan.created_at else None,
                }
        except Exception as e:
            logger.debug(f"Error loading security scan metrics: {e}")
        
        return result
    
    def validate_config(self) -> None:
        """Validate configuration for tool report."""
        # Tool name is optional - if not provided, analyze all tools
        pass
    
    def get_template_name(self) -> str:
        """Get template name for tool reports."""
        return 'partials/_tool_analysis.html'
    
    def collect_data(self) -> Dict[str, Any]:
        """
        Collect tool performance data across all analyses.
        
        Global but filterable:
        - Analyze all tools by default
        - Filter by specific tool name if provided
        - Filter by model if provided
        - Filter by app if provided
        - Filter by date range if provided
        
        Hybrid approach:
        1. Query database for all completed tasks (with filters)
        2. Load detailed tool data from consolidated JSON files
        3. Aggregate tool statistics globally
        """
        tool_name = self.config.get('tool_name')  # Optional
        filter_model = self.config.get('filter_model')  # Optional (single model)
        filter_models = self.config.get('filter_models', [])  # Optional (list of models from pipeline)
        filter_app = self.config.get('filter_app')  # Optional (single app)
        filter_apps = self.config.get('filter_apps', [])  # Optional (list of apps from pipeline)
        date_range = self.config.get('date_range', {})
        
        logger.info(f"Collecting tool report data (tool={tool_name}, model={filter_model or filter_models}, app={filter_app or filter_apps})")
        
        # Step 1: Query database for terminal tasks (fast filtering)
        query = db.session.query(AnalysisTask).filter(
            AnalysisTask.status.in_([  # type: ignore[union-attr]
                AnalysisStatus.COMPLETED,
                AnalysisStatus.PARTIAL_SUCCESS
            ])
        )
        
        # Apply filters
        if filter_model:
            query = query.filter(AnalysisTask.target_model == filter_model)
        elif filter_models:
            query = query.filter(AnalysisTask.target_model.in_(filter_models))
        
        if filter_app is not None:
            query = query.filter(AnalysisTask.target_app_number == filter_app)
        elif filter_apps:
            query = query.filter(AnalysisTask.target_app_number.in_(filter_apps))
        if date_range.get('start'):
            query = query.filter(AnalysisTask.completed_at >= date_range['start'])
        if date_range.get('end'):
            query = query.filter(AnalysisTask.completed_at <= date_range['end'])
        
        tasks = query.order_by(AnalysisTask.completed_at.desc()).all()  # type: ignore[union-attr]
        
        if not tasks:
            logger.warning("No completed analyses found with the specified filters")
            tasks = []  # Continue with empty list
        
        # Step 2: Load detailed tool data from filesystem
        unified_service = ServiceLocator().get_unified_result_service()
        
        # Global tool statistics
        tools_data = defaultdict(lambda: {
            'tool_name': '',
            'total_executions': 0,
            'successful': 0,
            'failed': 0,
            'total_findings': 0,
            'findings_by_severity': {
                'critical': 0,
                'high': 0,
                'medium': 0,
                'low': 0,
                'info': 0
            },
            'total_duration': 0.0,
            'executions_by_model': defaultdict(int),
            'success_by_model': defaultdict(int),
            'findings_by_model': defaultdict(int),
            'execution_timeline': []  # For trend analysis
        })
        
        processed_tasks = 0
        
        for task in tasks:
            # Load consolidated results
            result = unified_service.load_analysis_results(task.task_id)  # type: ignore[union-attr]
            
            if not result or not result.raw_data:
                logger.warning(f"No results found for task {task.task_id}")
                continue
            
            raw_data = result.raw_data
            # Handle nested 'results' structure from analyzer_manager
            results_wrapper = raw_data.get('results', {})
            tools = raw_data.get('tools') or results_wrapper.get('tools', {})
            findings = raw_data.get('findings') or results_wrapper.get('findings', [])
            
            # Process each tool in this task
            for tool, tool_data in tools.items():
                # Skip if filtering by specific tool and this isn't it
                if tool_name and tool != tool_name:
                    continue
                
                stats: Dict[str, Any] = tools_data[tool]
                stats['tool_name'] = tool
                
                # Execution statistics
                stats['total_executions'] += 1
                stats['executions_by_model'][task.target_model] += 1
                
                if tool_data.get('executed'):
                    if tool_data.get('status') == 'success':
                        stats['successful'] += 1
                        stats['success_by_model'][task.target_model] += 1
                    else:
                        stats['failed'] += 1
                
                # Duration - ensure we handle None values
                duration = tool_data.get('duration_seconds')
                stats['total_duration'] += float(duration) if duration is not None else 0.0
                
                # Timeline entry for trend analysis
                stats['execution_timeline'].append({
                    'date': task.completed_at.isoformat() if task.completed_at else None,
                    'model': task.target_model,
                    'app': task.target_app_number,
                    'success': tool_data.get('status') == 'success',
                    'findings': tool_data.get('total_issues', 0) or 0,
                    'duration': float(duration) if duration is not None else 0.0
                })
            
            # Count findings by tool with enhanced CWE tracking
            for finding in findings:
                finding_tool = finding.get('tool')
                
                # Skip if filtering by specific tool and this isn't it
                if tool_name and finding_tool != tool_name:
                    continue
                
                if finding_tool:
                    stats: Dict[str, Any] = tools_data[finding_tool]  # type: ignore[no-redef]
                    stats['total_findings'] += 1
                    stats['findings_by_model'][task.target_model] += 1
                    
                    # Track severity
                    severity = finding.get('severity', 'info').lower()
                    if severity in stats['findings_by_severity']:
                        stats['findings_by_severity'][severity] += 1
                    
                    # Track CWE IDs for security analysis
                    if 'cwe_statistics' not in stats:
                        stats['cwe_statistics'] = defaultdict(int)
                    
                    cwe_id = finding.get('cwe') or finding.get('cwe_id')
                    if cwe_id:
                        # Normalize CWE ID format
                        if isinstance(cwe_id, (int, float)):
                            cwe_id = f"CWE-{int(cwe_id)}"
                        elif isinstance(cwe_id, str) and not cwe_id.startswith('CWE-'):
                            cwe_id = f"CWE-{cwe_id}"
                        stats['cwe_statistics'][cwe_id] += 1
            
            processed_tasks += 1
        
        # Convert defaultdicts to regular dicts and calculate rates
        tools_list = []
        all_findings_for_aggregate = []  # Collect all findings for aggregate stats
        
        for tool_name_key, stats in tools_data.items():
            # Convert nested defaultdicts
            stats['executions_by_model'] = dict(stats['executions_by_model'])
            stats['success_by_model'] = dict(stats['success_by_model'])
            stats['findings_by_model'] = dict(stats['findings_by_model'])
            
            # Convert CWE statistics if present
            if 'cwe_statistics' in stats:
                cwe_stats = dict(stats['cwe_statistics'])
                stats['cwe_statistics'] = cwe_stats
                # Add CWE category mapping
                stats['cwe_categories'] = {}
                for cwe_id, count in cwe_stats.items():
                    category = self.CWE_CATEGORIES.get(cwe_id, 'other')
                    if category not in stats['cwe_categories']:
                        stats['cwe_categories'][category] = 0
                    stats['cwe_categories'][category] += count
            else:
                stats['cwe_statistics'] = {}
                stats['cwe_categories'] = {}
            
            # Calculate rates
            total_exec = stats['total_executions']
            stats['success_rate'] = (stats['successful'] / total_exec * 100) if total_exec > 0 else 0
            stats['failure_rate'] = (stats['failed'] / total_exec * 100) if total_exec > 0 else 0
            stats['average_duration'] = (stats['total_duration'] / stats['successful']) if stats['successful'] > 0 else 0
            stats['average_findings_per_execution'] = (stats['total_findings'] / stats['successful']) if stats['successful'] > 0 else 0
            
            # Calculate scientific metrics per tool
            findings_counts = [entry.get('findings', 0) for entry in stats['execution_timeline']]
            duration_values = [entry.get('duration', 0) for entry in stats['execution_timeline'] if entry.get('duration')]
            
            if findings_counts:
                stats['scientific_metrics'] = {
                    'findings_mean': statistics.mean(findings_counts) if findings_counts else 0,
                    'findings_median': statistics.median(findings_counts) if findings_counts else 0,
                    'findings_stdev': statistics.stdev(findings_counts) if len(findings_counts) > 1 else 0,
                    'findings_min': min(findings_counts) if findings_counts else 0,
                    'findings_max': max(findings_counts) if findings_counts else 0,
                    'duration_mean': statistics.mean(duration_values) if duration_values else 0,
                    'duration_median': statistics.median(duration_values) if duration_values else 0,
                    'duration_stdev': statistics.stdev(duration_values) if len(duration_values) > 1 else 0,
                    'sample_size': len(findings_counts)
                }
            else:
                stats['scientific_metrics'] = {
                    'findings_mean': 0, 'findings_median': 0, 'findings_stdev': 0,
                    'findings_min': 0, 'findings_max': 0,
                    'duration_mean': 0, 'duration_median': 0, 'duration_stdev': 0,
                    'sample_size': 0
                }
            
            # Classify tool by category from KNOWN_TOOLS
            stats['tool_category'] = 'other'
            for category, tool_info in self.KNOWN_TOOLS.items():
                if tool_name_key == category:  # category is actually tool name
                    stats['tool_category'] = tool_info.get('category', 'other')
                    break
            
            # Sort timeline by date
            stats['execution_timeline'].sort(key=lambda x: x['date'] or '', reverse=True)
            
            # Collect findings data for aggregate statistics
            all_findings_for_aggregate.extend(findings_counts)
            
            tools_list.append(stats)
        
        # Sort tools by total executions (most used first)
        tools_list.sort(key=lambda x: x['total_executions'], reverse=True)
        
        # Calculate overall statistics
        total_executions = sum(t['total_executions'] for t in tools_list)
        total_successful = sum(t['successful'] for t in tools_list)
        total_findings = sum(t['total_findings'] for t in tools_list)
        
        # Identify best/worst performers
        best_success_rate_tool = None
        worst_success_rate_tool = None
        fastest_tool = None
        slowest_tool = None
        most_findings_tool = None
        
        if tools_list:
            sorted_by_success = sorted([t for t in tools_list if t['total_executions'] > 0], 
                                      key=lambda x: x['success_rate'], reverse=True)
            if sorted_by_success:
                best_success_rate_tool = sorted_by_success[0]['tool_name']
                worst_success_rate_tool = sorted_by_success[-1]['tool_name']
            
            sorted_by_duration = sorted([t for t in tools_list if t['successful'] > 0],
                                       key=lambda x: x['average_duration'])
            if sorted_by_duration:
                fastest_tool = sorted_by_duration[0]['tool_name']
                slowest_tool = sorted_by_duration[-1]['tool_name']
            
            sorted_by_findings = sorted(tools_list, key=lambda x: x['total_findings'], reverse=True)
            most_findings_tool = sorted_by_findings[0]['tool_name']
        
        # Compile final data structure
        data = {
            'report_type': 'tool_analysis',
            'timestamp': utc_now().isoformat(),
            'filters': {
                'tool_name': tool_name,
                'filter_model': filter_model,
                'filter_app': filter_app,
                'date_range': date_range
            },
            'tools': tools_list,
            'tools_count': len(tools_list),
            'tasks_analyzed': processed_tasks,
            'overall_stats': {
                'total_executions': total_executions,
                'total_successful': total_successful,
                'total_findings': total_findings,
                'overall_success_rate': (total_successful / total_executions * 100) if total_executions > 0 else 0
            },
            'insights': {
                'best_success_rate_tool': best_success_rate_tool,
                'worst_success_rate_tool': worst_success_rate_tool,
                'fastest_tool': fastest_tool,
                'slowest_tool': slowest_tool,
                'most_findings_tool': most_findings_tool
            },
            # Aggregate statistics across all tools (for research papers)
            'aggregate_statistics': {
                'total_tools_analyzed': len(tools_list),
                'total_analyses_run': processed_tasks,
                'findings_statistics': {
                    'total': total_findings,
                    'mean': statistics.mean(all_findings_for_aggregate) if all_findings_for_aggregate else 0,
                    'median': statistics.median(all_findings_for_aggregate) if all_findings_for_aggregate else 0,
                    'stdev': statistics.stdev(all_findings_for_aggregate) if len(all_findings_for_aggregate) > 1 else 0,
                    'min': min(all_findings_for_aggregate) if all_findings_for_aggregate else 0,
                    'max': max(all_findings_for_aggregate) if all_findings_for_aggregate else 0
                },
                'success_rates': {
                    'overall': (total_successful / total_executions * 100) if total_executions > 0 else 0,
                    'by_category': {}  # Will be populated below
                },
                'cwe_aggregate': {},  # Aggregate CWE statistics across all tools
                'tool_categories': {}  # Tools grouped by category
            }
        }
        
        # Aggregate CWE statistics across all tools
        aggregate_cwe = defaultdict(int)
        for tool_stats in tools_list:
            for cwe_id, count in tool_stats.get('cwe_statistics', {}).items():
                aggregate_cwe[cwe_id] += count
        data['aggregate_statistics']['cwe_aggregate'] = dict(aggregate_cwe)
        
        # Aggregate CWE by category
        cwe_by_category = defaultdict(int)
        for cwe_id, count in aggregate_cwe.items():
            category = self.CWE_CATEGORIES.get(cwe_id, 'other')
            cwe_by_category[category] += count
        data['aggregate_statistics']['cwe_by_category'] = dict(cwe_by_category)
        
        # Group tools by category and calculate category-level stats
        tools_by_category = defaultdict(list)
        for tool_stats in tools_list:
            category = tool_stats.get('tool_category', 'other')
            tools_by_category[category].append(tool_stats)
        
        category_stats = {}
        for category, category_tools in tools_by_category.items():
            cat_total_exec = sum(t['total_executions'] for t in category_tools)
            cat_successful = sum(t['successful'] for t in category_tools)
            cat_findings = sum(t['total_findings'] for t in category_tools)
            category_stats[category] = {
                'tools_count': len(category_tools),
                'tool_names': [t['tool_name'] for t in category_tools],
                'total_executions': cat_total_exec,
                'total_successful': cat_successful,
                'total_findings': cat_findings,
                'success_rate': (cat_successful / cat_total_exec * 100) if cat_total_exec > 0 else 0
            }
        
        data['aggregate_statistics']['tool_categories'] = category_stats
        data['aggregate_statistics']['success_rates']['by_category'] = {
            cat: stats['success_rate'] for cat, stats in category_stats.items()
        }
        
        # Add tool categories from registry for template rendering
        data = self.add_tool_context(data)
        
        self.data = data
        return data
    
    def generate_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate summary for tool report."""
        return {
            'tools_analyzed': data.get('tools_count', 0),
            'tasks_analyzed': data.get('tasks_analyzed', 0),
            'total_findings': data.get('overall_stats', {}).get('total_findings', 0),
            'overall_success_rate': round(data.get('overall_stats', {}).get('overall_success_rate', 0), 1),
            'best_tool': data.get('insights', {}).get('best_success_rate_tool'),
            'generated_at': data.get('timestamp')
        }
