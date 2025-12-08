"""
Model Report Generator

Generates comprehensive reports showing all analyses for a specific model across all apps.
Shows model performance, consistency, and patterns.
Includes generation metadata (cost, tokens, time) for full context.
"""
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

from .base_generator import BaseReportGenerator
from ...extensions import db
from ...models import AnalysisTask, GeneratedApplication
from ...services.service_locator import ServiceLocator
from ...services.service_base import ValidationError, NotFoundError
from ...utils.time import utc_now
from ..generation_statistics import load_generation_records, GenerationRecord

logger = logging.getLogger(__name__)


class ModelReportGenerator(BaseReportGenerator):
    """Generator for model-centric analysis reports."""
    
    def validate_config(self) -> None:
        """Validate configuration for model report."""
        model_slug = self.config.get('model_slug')
        if not model_slug:
            raise ValidationError("model_slug is required for model analysis report")
    
    def get_template_name(self) -> str:
        """Get template name for model reports."""
        return 'partials/_model_analysis.html'
    
    def collect_data(self) -> Dict[str, Any]:
        """
        Collect all analysis data for a specific model.
        
        Hybrid approach:
        1. Query database for all completed tasks for this model
        2. Load detailed findings from consolidated JSON files
        3. Aggregate statistics across all apps
        """
        self.validate_config()
        
        model_slug = self.config.get('model_slug')
        date_range = self.config.get('date_range', {})
        
        logger.info(f"Collecting model report data for {model_slug}")
        
        # Step 1: Query database for all completed tasks (fast filtering)
        query = db.session.query(AnalysisTask).filter(
            AnalysisTask.target_model == model_slug,
            AnalysisTask.status == 'completed'
        )
        
        # Apply date range filter if provided
        if date_range.get('start'):
            query = query.filter(AnalysisTask.completed_at >= date_range['start'])
        if date_range.get('end'):
            query = query.filter(AnalysisTask.completed_at <= date_range['end'])
        
        tasks = query.order_by(
            AnalysisTask.target_app_number,
            AnalysisTask.completed_at.desc()
        ).all()
        
        if not tasks:
            raise NotFoundError(f"No completed analyses found for model {model_slug}")
        
        # Step 2: Load detailed results from filesystem (complete data)
        unified_service = ServiceLocator().get_unified_result_service()
        
        apps_data = []
        total_findings = 0
        total_critical = 0
        total_high = 0
        total_medium = 0
        total_low = 0
        tools_stats = {}
        
        # Group tasks by app number and get latest for each app
        apps_map = {}
        for task in tasks:
            app_num = task.target_app_number
            if app_num not in apps_map:
                apps_map[app_num] = []
            apps_map[app_num].append(task)
        
        for app_number in sorted(apps_map.keys()):
            app_tasks = apps_map[app_number]
            latest_task = app_tasks[0]  # Already sorted by completed_at desc
            
            # Load consolidated results
            result = unified_service.load_analysis_results(latest_task.task_id)
            
            if not result or not result.raw_data:
                logger.warning(f"No results found for task {latest_task.task_id}")
                continue
            
            raw_data = result.raw_data
            
            # Handle nested structure: raw_data.results.summary vs raw_data.summary
            results_wrapper = raw_data.get('results', {})
            summary = raw_data.get('summary') or results_wrapper.get('summary') or {}
            
            # Aggregate statistics
            findings_count = summary.get('total_findings', 0)
            total_findings += findings_count
            
            # Handle both field names: 'findings_by_severity' (old) and 'severity_breakdown' (new)
            severity_counts = summary.get('findings_by_severity') or summary.get('severity_breakdown', {})
            total_critical += severity_counts.get('critical', 0)
            total_high += severity_counts.get('high', 0)
            total_medium += severity_counts.get('medium', 0)
            total_low += severity_counts.get('low', 0)
            
            # Extract tools - prefer top-level 'tools', then nested 'results.tools', fallback to services
            tools = raw_data.get('tools') or results_wrapper.get('tools')
            if not tools:
                tools = self._extract_tools_from_services(results_wrapper.get('services', {}))
            
            # Aggregate tool statistics
            for tool_name, tool_data in tools.items():
                if tool_name not in tools_stats:
                    tools_stats[tool_name] = {
                        'total_executions': 0,
                        'successful': 0,
                        'failed': 0,
                        'total_findings': 0,
                        'total_duration': 0.0
                    }
                
                stats = tools_stats[tool_name]
                stats['total_executions'] += 1
                
                if tool_data.get('status') == 'success':
                    stats['successful'] += 1
                else:
                    stats['failed'] += 1
                
                stats['total_findings'] += tool_data.get('total_issues') or 0
                stats['total_duration'] += tool_data.get('duration_seconds') or 0.0
            
            # Get app metadata
            app = db.session.query(GeneratedApplication).filter(
                GeneratedApplication.model_slug == model_slug,
                GeneratedApplication.app_number == app_number
            ).first()
            
            # Extract findings - prefer top-level 'findings', then nested 'results.findings', fallback to services
            findings = raw_data.get('findings') or results_wrapper.get('findings')
            if findings is None:
                findings = self._extract_findings_from_services(results_wrapper.get('services', {}))
            
            # Calculate duration from task timestamps if not in metadata
            duration_seconds = raw_data.get('metadata', {}).get('duration_seconds', 0)
            if not duration_seconds and latest_task.completed_at and latest_task.created_at:
                duration_seconds = (latest_task.completed_at - latest_task.created_at).total_seconds()
            
            apps_data.append({
                'app_number': app_number,
                'task_id': latest_task.task_id,
                'task_status': latest_task.status,
                'completed_at': latest_task.completed_at.isoformat() if latest_task.completed_at else None,
                'duration_seconds': duration_seconds,
                'app_name': f"{model_slug} / App {app_number}",  # Constructed from slug and number
                'app_type': app.app_type if app else None,
                'app_description': getattr(app, 'description', None) if app else None,
                'findings_count': findings_count,
                'severity_counts': severity_counts,
                'tools': tools,
                'findings': findings,
                'summary': summary,
                'all_tasks_count': len(app_tasks)  # Historical task count
            })
        
        # Calculate tool success rates and effectiveness metrics
        for tool_name, stats in tools_stats.items():
            total = stats['total_executions']
            stats['success_rate'] = (stats['successful'] / total * 100) if total > 0 else 0
            stats['average_duration'] = (stats['total_duration'] / stats['successful']) if stats['successful'] > 0 else 0
            stats['findings_per_execution'] = (stats['total_findings'] / stats['successful']) if stats['successful'] > 0 else 0
        
        # Calculate scientific/statistical metrics
        findings_per_app = [app['findings_count'] for app in apps_data]
        durations = [app['duration_seconds'] for app in apps_data if app['duration_seconds'] > 0]
        
        scientific_stats = self._calculate_scientific_metrics(findings_per_app, durations, apps_data)
        
        # Load generation metadata (cost, tokens, time)
        generation_metadata = self._get_generation_metadata_for_model(model_slug)
        
        # Compile final data structure
        data = {
            'report_type': 'model_analysis',
            'model_slug': model_slug,
            'timestamp': utc_now().isoformat(),
            'date_range': date_range,
            'apps': apps_data,
            'apps_count': len(apps_data),
            'total_tasks': len(tasks),
            'aggregated_stats': {
                'total_findings': total_findings,
                'findings_by_severity': {
                    'critical': total_critical,
                    'high': total_high,
                    'medium': total_medium,
                    'low': total_low
                },
                'average_findings_per_app': total_findings / len(apps_data) if apps_data else 0
            },
            'scientific_metrics': scientific_stats,
            'tools_statistics': tools_stats,
            'generation_metadata': generation_metadata
        }
        
        self.data = data
        return data
    
    def generate_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate summary for model report."""
        return {
            'model_slug': data.get('model_slug'),
            'apps_analyzed': data.get('apps_count', 0),
            'total_findings': data.get('aggregated_stats', {}).get('total_findings', 0),
            'critical_findings': data.get('aggregated_stats', {}).get('findings_by_severity', {}).get('critical', 0),
            'generated_at': data.get('timestamp')
        }
    
    # ==========================================================================
    # HELPER METHODS - Data Extraction from Nested Structures
    # ==========================================================================
    
    def _extract_tools_from_services(self, services: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract tool execution data from nested services structure.
        
        Flattens the nested structure:
        services -> {service_type} -> analysis -> results -> {language} -> {tool}
        
        Returns a flat dict: {tool_name: {status, total_issues, duration_seconds}}
        """
        tools = {}
        
        for service_type, service_data in services.items():
            if not isinstance(service_data, dict):
                continue
            
            analysis = service_data.get('analysis', {})
            if not isinstance(analysis, dict):
                continue
            
            results = analysis.get('results', {})
            if not isinstance(results, dict):
                continue
            
            # Handle language-specific nesting (python, javascript, etc.)
            for lang_or_tool, lang_data in results.items():
                if isinstance(lang_data, dict):
                    # Check if it's a language wrapper (contains tool results)
                    for tool_name, tool_data in lang_data.items():
                        if isinstance(tool_data, dict) and 'status' in tool_data:
                            tools[tool_name] = {
                                'status': tool_data.get('status', 'unknown'),
                                'total_issues': tool_data.get('total_issues', 0),
                                'duration_seconds': tool_data.get('duration_seconds', 0.0),
                                'service': service_type,
                                'language': lang_or_tool
                            }
                elif isinstance(lang_or_tool, str):
                    # Direct tool entry (no language wrapper)
                    if isinstance(results.get(lang_or_tool), dict):
                        tool_data = results[lang_or_tool]
                        if 'status' in tool_data:
                            tools[lang_or_tool] = {
                                'status': tool_data.get('status', 'unknown'),
                                'total_issues': tool_data.get('total_issues', 0),
                                'duration_seconds': tool_data.get('duration_seconds', 0.0),
                                'service': service_type
                            }
        
        return tools
    
    def _extract_findings_from_services(self, services: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract all findings from nested services structure.
        
        Flattens findings from all services into a unified list with standardized format.
        """
        findings = []
        
        for service_type, service_data in services.items():
            if not isinstance(service_data, dict):
                continue
            
            analysis = service_data.get('analysis', {})
            if not isinstance(analysis, dict):
                continue
            
            results = analysis.get('results', {})
            if not isinstance(results, dict):
                continue
            
            # Extract findings from language-specific results
            for lang_or_tool, lang_data in results.items():
                if isinstance(lang_data, dict):
                    # Language wrapper case
                    for tool_name, tool_data in lang_data.items():
                        if isinstance(tool_data, dict):
                            tool_findings = tool_data.get('findings', []) or tool_data.get('issues', [])
                            for finding in tool_findings:
                                if isinstance(finding, dict):
                                    # Normalize finding structure
                                    findings.append({
                                        'tool': tool_name,
                                        'service': service_type,
                                        'severity': finding.get('severity', 'medium').lower(),
                                        'message': finding.get('message', '') or finding.get('description', ''),
                                        'file': finding.get('file', '') or finding.get('location', {}).get('file', ''),
                                        'line': finding.get('line') or finding.get('location', {}).get('line'),
                                        'column': finding.get('column') or finding.get('location', {}).get('column'),
                                        'code': finding.get('code', '') or finding.get('rule_id', ''),
                                        'category': finding.get('category', '')
                                    })
        
        return findings
    
    def _calculate_scientific_metrics(
        self,
        findings_per_app: List[int],
        durations: List[float],
        apps_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate scientific/statistical metrics for the analysis results.
        
        Returns comprehensive statistical measures for academic rigor.
        """
        import statistics
        
        metrics = {
            'findings_distribution': {},
            'duration_statistics': {},
            'severity_distribution': {},
            'tool_coverage': {}
        }
        
        if not findings_per_app:
            return metrics
        
        # Findings distribution statistics
        metrics['findings_distribution'] = {
            'mean': statistics.mean(findings_per_app),
            'median': statistics.median(findings_per_app),
            'min': min(findings_per_app),
            'max': max(findings_per_app),
            'range': max(findings_per_app) - min(findings_per_app),
            'total': sum(findings_per_app)
        }
        
        # Add standard deviation and variance if we have enough data points
        if len(findings_per_app) > 1:
            metrics['findings_distribution']['std_dev'] = statistics.stdev(findings_per_app)
            metrics['findings_distribution']['variance'] = statistics.variance(findings_per_app)
            
            # Coefficient of variation (normalized measure of dispersion)
            mean_val = metrics['findings_distribution']['mean']
            if mean_val > 0:
                metrics['findings_distribution']['cv_percent'] = (
                    metrics['findings_distribution']['std_dev'] / mean_val * 100
                )
        
        # Duration statistics
        if durations:
            metrics['duration_statistics'] = {
                'mean': statistics.mean(durations),
                'median': statistics.median(durations),
                'min': min(durations),
                'max': max(durations),
                'total': sum(durations)
            }
            
            if len(durations) > 1:
                metrics['duration_statistics']['std_dev'] = statistics.stdev(durations)
        
        # Severity distribution across all apps
        severity_totals = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
        for app in apps_data:
            sev_counts = app.get('severity_counts', {})
            for severity in severity_totals.keys():
                severity_totals[severity] += sev_counts.get(severity, 0)
        
        total_findings = sum(severity_totals.values())
        if total_findings > 0:
            metrics['severity_distribution'] = {
                'counts': severity_totals,
                'percentages': {
                    severity: (count / total_findings * 100)
                    for severity, count in severity_totals.items()
                }
            }
        
        # Tool coverage analysis
        all_tools = set()
        for app in apps_data:
            app_tools = app.get('tools', {})
            all_tools.update(app_tools.keys())
        
        metrics['tool_coverage'] = {
            'total_unique_tools': len(all_tools),
            'tools_used': sorted(list(all_tools)),
            'avg_tools_per_app': len(all_tools) / len(apps_data) if apps_data else 0
        }
        
        return metrics
    
    def _get_generation_metadata_for_model(self, model_slug: str) -> Dict[str, Any]:
        """
        Load generation metadata (cost, tokens, time) for all apps of a model.
        
        Returns aggregated generation statistics across all apps.
        """
        try:
            records = load_generation_records(include_files=True, include_db=True, include_applications=True)
            
            # Filter to this model
            model_records = [r for r in records if r.model == model_slug]
            
            if not model_records:
                return {'available': False, 'message': 'No generation metadata found'}
            
            # Aggregate statistics
            total_cost = 0.0
            total_tokens = 0
            total_prompt_tokens = 0
            total_completion_tokens = 0
            total_generation_time_ms = 0
            total_lines = 0
            records_with_cost = 0
            records_with_tokens = 0
            records_with_time = 0
            records_with_lines = 0
            
            # Per-app breakdown
            apps_generation = {}
            providers = set()
            
            for rec in model_records:
                app_num = rec.app_num
                if app_num is None:
                    continue
                
                if app_num not in apps_generation:
                    apps_generation[app_num] = {
                        'app_number': app_num,
                        'components': [],
                        'total_cost': 0.0,
                        'total_tokens': 0,
                        'generation_time_ms': 0,
                        'total_lines': 0,
                        'provider': None,
                        'success': None
                    }
                
                app_data = apps_generation[app_num]
                
                # Track component
                if rec.component:
                    app_data['components'].append(rec.component)
                
                # Aggregate costs
                if rec.estimated_cost:
                    app_data['total_cost'] += rec.estimated_cost
                    total_cost += rec.estimated_cost
                    records_with_cost += 1
                
                # Aggregate tokens
                if rec.total_tokens:
                    app_data['total_tokens'] += rec.total_tokens
                    total_tokens += rec.total_tokens
                    records_with_tokens += 1
                
                if rec.prompt_tokens:
                    total_prompt_tokens += rec.prompt_tokens
                if rec.completion_tokens:
                    total_completion_tokens += rec.completion_tokens
                
                # Aggregate generation time
                if rec.generation_time_ms:
                    app_data['generation_time_ms'] += rec.generation_time_ms
                    total_generation_time_ms += rec.generation_time_ms
                    records_with_time += 1
                
                # Aggregate lines
                if rec.total_lines:
                    app_data['total_lines'] += rec.total_lines
                    total_lines += rec.total_lines
                    records_with_lines += 1
                
                # Track provider
                if rec.provider_name:
                    providers.add(rec.provider_name)
                    app_data['provider'] = rec.provider_name
                
                # Track success
                if rec.success is not None:
                    app_data['success'] = rec.success
            
            return {
                'available': True,
                'total_generations': len(model_records),
                'total_cost': round(total_cost, 6),
                'total_tokens': total_tokens,
                'total_prompt_tokens': total_prompt_tokens,
                'total_completion_tokens': total_completion_tokens,
                'total_generation_time_ms': total_generation_time_ms,
                'total_generation_time_seconds': round(total_generation_time_ms / 1000, 2) if total_generation_time_ms else 0,
                'total_lines_generated': total_lines,
                'avg_cost_per_generation': round(total_cost / records_with_cost, 6) if records_with_cost else 0,
                'avg_tokens_per_generation': round(total_tokens / records_with_tokens) if records_with_tokens else 0,
                'avg_generation_time_ms': round(total_generation_time_ms / records_with_time) if records_with_time else 0,
                'avg_lines_per_generation': round(total_lines / records_with_lines) if records_with_lines else 0,
                'providers': list(providers),
                'apps_breakdown': list(apps_generation.values())
            }
        except Exception as e:
            logger.warning(f"Failed to load generation metadata for {model_slug}: {e}")
            return {'available': False, 'error': str(e)}
