"""
Report Service (v2)
==================

Simplified report generation service that stores JSON data directly in the database.
No file generation - reports are rendered client-side from JSON data.

Report Types:
- model_analysis: All analyses for a single model across all apps
- template_comparison: Cross-model comparison for a single template  
- tool_analysis: Tool effectiveness metrics across analyses
"""

import json
import logging
import uuid
import statistics
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Literal

from ..extensions import db
from ..models import Report, AnalysisTask, GeneratedApplication, ModelCapability
from ..constants import AnalysisStatus
from ..utils.time import utc_now
from .unified_result_service import UnifiedResultService
from .service_locator import ServiceLocator

logger = logging.getLogger(__name__)

ReportType = Literal['model_analysis', 'template_comparison', 'tool_analysis']


class ReportService:
    """
    Simplified report generation service.
    
    All report data is stored as JSON in the database - no file I/O.
    Reports are rendered client-side using JavaScript.
    """
    
    def __init__(self):
        """Initialize the report service."""
        self._unified_service: Optional[UnifiedResultService] = None
    
    @property
    def unified_service(self) -> UnifiedResultService:
        """Lazy-load unified result service."""
        if self._unified_service is None:
            try:
                self._unified_service = ServiceLocator().get_unified_result_service()
            except Exception:
                self._unified_service = UnifiedResultService()
        return self._unified_service
    
    # ==========================================================================
    # PUBLIC API
    # ==========================================================================
    
    def generate_report(
        self,
        report_type: ReportType,
        config: Dict[str, Any],
        title: Optional[str] = None,
        description: Optional[str] = None,
        user_id: Optional[int] = None,
        expires_in_days: int = 30
    ) -> Report:
        """
        Generate a report and store data in database.
        
        Args:
            report_type: Type of report to generate
            config: Report-specific configuration
            title: Optional custom title
            description: Optional description
            user_id: ID of user creating report
            expires_in_days: Days until report expires
            
        Returns:
            Report model instance with data populated
        """
        # Validate config
        self._validate_config(report_type, config)
        
        # Generate unique ID
        report_id = f"report_{uuid.uuid4().hex[:12]}"
        
        # Create report record
        report = Report(
            report_id=report_id,
            report_type=report_type,
            title=title or self._generate_title(report_type, config),
            description=description,
            format='json',  # Always JSON now
            status='generating',
            created_by=user_id,
            progress_percent=0
        )
        report.set_config(config)
        
        if expires_in_days:
            report.expires_at = utc_now() + timedelta(days=expires_in_days)
        
        db.session.add(report)
        db.session.commit()
        
        try:
            # Generate report data based on type
            logger.info(f"Generating {report_type} report {report_id}")
            
            if report_type == 'model_analysis':
                data = self._generate_model_report(config, report)
            elif report_type == 'template_comparison':
                data = self._generate_template_comparison(config, report)
            elif report_type == 'tool_analysis':
                data = self._generate_tool_report(config, report)
            else:
                raise ValueError(f"Unknown report type: {report_type}")
            
            # Store data and mark complete
            report.set_report_data(data)
            report.set_summary(self._extract_summary(report_type, data))
            report.status = 'completed'
            report.completed_at = utc_now()
            report.progress_percent = 100
            
            db.session.commit()
            logger.info(f"Report {report_id} generated successfully")
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate report {report_id}: {e}", exc_info=True)
            report.status = 'failed'
            report.error_message = str(e)
            report.completed_at = utc_now()
            db.session.commit()
            raise
    
    def get_report(self, report_id: str) -> Optional[Report]:
        """Get report by ID."""
        return Report.query.filter_by(report_id=report_id).first()
    
    def get_report_data(self, report_id: str) -> Optional[Dict[str, Any]]:
        """Get report data as dictionary."""
        report = self.get_report(report_id)
        if report and report.status == 'completed':
            return report.get_report_data()
        return None
    
    def list_reports(
        self,
        report_type: Optional[str] = None,
        status: Optional[str] = None,
        user_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Report]:
        """List reports with optional filtering."""
        query = Report.query
        
        if report_type:
            query = query.filter(Report.report_type == report_type)
        if status:
            query = query.filter(Report.status == status)
        if user_id:
            query = query.filter(Report.created_by == user_id)
        
        return query.order_by(Report.created_at.desc()).limit(limit).offset(offset).all()
    
    def delete_report(self, report_id: str) -> bool:
        """Delete a report."""
        report = self.get_report(report_id)
        if not report:
            return False
        
        db.session.delete(report)
        db.session.commit()
        logger.info(f"Deleted report {report_id}")
        return True
    
    def cleanup_expired_reports(self) -> int:
        """Delete expired reports. Returns count deleted."""
        now = utc_now()
        expired = Report.query.filter(
            Report.expires_at.isnot(None),
            Report.expires_at < now
        ).all()
        
        count = 0
        for report in expired:
            try:
                db.session.delete(report)
                count += 1
            except Exception as e:
                logger.error(f"Failed to delete expired report {report.report_id}: {e}")
        
        db.session.commit()
        logger.info(f"Cleaned up {count} expired reports")
        return count
    
    # ==========================================================================
    # REPORT GENERATORS
    # ==========================================================================
    
    def _generate_model_report(self, config: Dict[str, Any], report: Report) -> Dict[str, Any]:
        """
        Generate model analysis report.
        
        Shows all analyses for a single model across all apps.
        """
        model_slug = config['model_slug']
        date_range = config.get('date_range', {})
        
        # Query completed tasks for this model
        query = AnalysisTask.query.filter(
            AnalysisTask.target_model == model_slug,
            AnalysisTask.status.in_([
                AnalysisStatus.COMPLETED,
                AnalysisStatus.PARTIAL_SUCCESS,
                AnalysisStatus.FAILED,
                AnalysisStatus.CANCELLED
            ])
        )
        
        if date_range.get('start'):
            query = query.filter(AnalysisTask.completed_at >= date_range['start'])
        if date_range.get('end'):
            query = query.filter(AnalysisTask.completed_at <= date_range['end'])
        
        tasks = query.order_by(
            AnalysisTask.target_app_number,
            AnalysisTask.completed_at.desc()
        ).all()
        
        report.update_progress(20)
        db.session.commit()
        
        # Group by app and get latest task per app
        apps_map: Dict[int, List[AnalysisTask]] = {}
        for task in tasks:
            app_num = task.target_app_number
            if app_num not in apps_map:
                apps_map[app_num] = []
            apps_map[app_num].append(task)
        
        # Process each app
        apps_data = []
        all_findings = []
        tools_stats: Dict[str, Dict[str, Any]] = {}
        
        for app_number in sorted(apps_map.keys()):
            app_tasks = apps_map[app_number]
            latest_task = app_tasks[0]
            
            app_entry = self._process_task_for_report(latest_task, model_slug, app_number)
            apps_data.append(app_entry)
            
            # Aggregate findings
            if app_entry.get('findings'):
                all_findings.extend(app_entry['findings'])
            
            # Aggregate tool stats
            for tool_name, tool_data in app_entry.get('tools', {}).items():
                if tool_name not in tools_stats:
                    tools_stats[tool_name] = {
                        'executions': 0,
                        'successful': 0,
                        'failed': 0,
                        'total_findings': 0,
                        'total_duration': 0.0
                    }
                
                stats = tools_stats[tool_name]
                stats['executions'] += 1
                
                status = tool_data.get('status', 'unknown')
                if status in ('success', 'completed', 'no_issues'):
                    stats['successful'] += 1
                elif status == 'failed':
                    stats['failed'] += 1
                
                stats['total_findings'] += tool_data.get('total_issues', 0)
                stats['total_duration'] += tool_data.get('duration_seconds', 0)
        
        report.update_progress(80)
        db.session.commit()
        
        # Calculate aggregated statistics
        severity_counts = self._count_severities(all_findings)
        scientific_metrics = self._calculate_metrics(apps_data)
        
        # Finalize tool stats
        for tool_name, stats in tools_stats.items():
            total = stats['executions']
            stats['success_rate'] = (stats['successful'] / total * 100) if total > 0 else 0
            stats['avg_duration'] = (stats['total_duration'] / stats['successful']) if stats['successful'] > 0 else 0
            stats['findings_per_run'] = (stats['total_findings'] / stats['successful']) if stats['successful'] > 0 else 0
        
        return {
            'report_type': 'model_analysis',
            'model_slug': model_slug,
            'generated_at': utc_now().isoformat(),
            'date_range': date_range,
            'apps': apps_data,
            'apps_count': len(apps_data),
            'total_tasks': len(tasks),
            'summary': {
                'total_findings': len(all_findings),
                'severity_breakdown': severity_counts,
                'avg_findings_per_app': len(all_findings) / len(apps_data) if apps_data else 0
            },
            'scientific_metrics': scientific_metrics,
            'tools_statistics': tools_stats,
            'findings': all_findings[:500]  # Limit findings in response
        }
    
    def _generate_template_comparison(self, config: Dict[str, Any], report: Report) -> Dict[str, Any]:
        """
        Generate template comparison report.
        
        Compares how different models implemented the same template.
        """
        template_slug = config['template_slug']
        filter_models = config.get('filter_models', [])
        
        # Find all apps with this template
        apps_query = GeneratedApplication.query.filter(
            GeneratedApplication.template_slug == template_slug
        )
        
        if filter_models:
            apps_query = apps_query.filter(
                GeneratedApplication.model_slug.in_(filter_models)
            )
        
        apps = apps_query.all()
        
        report.update_progress(20)
        db.session.commit()
        
        # Get latest completed analysis for each app
        models_data = []
        all_findings = []
        
        for app in apps:
            # Get latest completed task for this app
            task = AnalysisTask.query.filter(
                AnalysisTask.target_model == app.model_slug,
                AnalysisTask.target_app_number == app.app_number,
                AnalysisTask.status.in_([
                    AnalysisStatus.COMPLETED,
                    AnalysisStatus.PARTIAL_SUCCESS,
                    AnalysisStatus.FAILED
                ])
            ).order_by(AnalysisTask.completed_at.desc()).first()
            
            if task:
                entry = self._process_task_for_report(task, app.model_slug, app.app_number)
                entry['template_slug'] = template_slug
                models_data.append(entry)
                
                if entry.get('findings'):
                    all_findings.extend(entry['findings'])
        
        report.update_progress(80)
        db.session.commit()
        
        # Calculate comparison metrics
        severity_counts = self._count_severities(all_findings)
        
        # Find common vs unique issues
        common_issues, unique_issues = self._identify_common_issues(models_data)
        
        return {
            'report_type': 'template_comparison',
            'template_slug': template_slug,
            'generated_at': utc_now().isoformat(),
            'models': models_data,
            'models_count': len(models_data),
            'summary': {
                'total_findings': len(all_findings),
                'severity_breakdown': severity_counts,
                'common_issues_count': len(common_issues),
                'unique_issues_count': len(unique_issues)
            },
            'comparison': {
                'common_issues': common_issues[:50],
                'unique_by_model': unique_issues
            },
            'findings': all_findings[:500]
        }
    
    def _generate_tool_report(self, config: Dict[str, Any], report: Report) -> Dict[str, Any]:
        """
        Generate tool analysis report.
        
        Shows tool effectiveness across all analyses.
        """
        tool_name = config.get('tool_name')  # Optional - None means all tools
        filter_model = config.get('filter_model')
        filter_app = config.get('filter_app')
        
        # Query completed tasks
        query = AnalysisTask.query.filter(
            AnalysisTask.status.in_([
                AnalysisStatus.COMPLETED,
                AnalysisStatus.PARTIAL_SUCCESS
            ])
        )
        
        if filter_model:
            query = query.filter(AnalysisTask.target_model == filter_model)
        if filter_app:
            query = query.filter(AnalysisTask.target_app_number == filter_app)
        
        tasks = query.order_by(AnalysisTask.completed_at.desc()).limit(200).all()
        
        report.update_progress(20)
        db.session.commit()
        
        # Collect tool data across all tasks
        tools_aggregate: Dict[str, Dict[str, Any]] = {}
        tools_by_model: Dict[str, Dict[str, Dict[str, Any]]] = {}
        all_findings = []
        
        for task in tasks:
            result = self.unified_service.load_analysis_results(task.task_id)
            if not result:
                continue
            
            # Extract tool data from services
            services = result.tools or {}
            for service_name, service_data in services.items():
                if not isinstance(service_data, dict):
                    continue
                
                # Parse tool results from service
                tool_results = self._extract_tools_from_service(service_data)
                
                for t_name, t_data in tool_results.items():
                    # Skip if filtering to specific tool
                    if tool_name and t_name != tool_name:
                        continue
                    
                    # Initialize aggregate entry
                    if t_name not in tools_aggregate:
                        tools_aggregate[t_name] = {
                            'tool_name': t_name,
                            'service': service_name,
                            'executions': 0,
                            'successful': 0,
                            'failed': 0,
                            'total_findings': 0,
                            'total_duration': 0.0,
                            'findings_by_severity': {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}
                        }
                    
                    agg = tools_aggregate[t_name]
                    agg['executions'] += 1
                    
                    status = t_data.get('status', 'unknown')
                    if status in ('success', 'completed', 'no_issues'):
                        agg['successful'] += 1
                    elif status == 'failed':
                        agg['failed'] += 1
                    
                    findings_count = t_data.get('total_issues', 0)
                    agg['total_findings'] += findings_count
                    agg['total_duration'] += t_data.get('duration_seconds', 0)
                    
                    # Count findings by severity
                    for finding in t_data.get('issues', []):
                        sev = finding.get('severity', 'info').lower()
                        if sev in agg['findings_by_severity']:
                            agg['findings_by_severity'][sev] += 1
                        all_findings.append({**finding, 'tool': t_name})
                    
                    # Track by model
                    model_slug = task.target_model
                    if model_slug not in tools_by_model:
                        tools_by_model[model_slug] = {}
                    if t_name not in tools_by_model[model_slug]:
                        tools_by_model[model_slug][t_name] = {
                            'executions': 0, 'successful': 0, 'findings': 0
                        }
                    
                    tbm = tools_by_model[model_slug][t_name]
                    tbm['executions'] += 1
                    if status in ('success', 'completed', 'no_issues'):
                        tbm['successful'] += 1
                    tbm['findings'] += findings_count
        
        report.update_progress(80)
        db.session.commit()
        
        # Finalize aggregates
        tools_list = []
        for t_name, agg in tools_aggregate.items():
            total = agg['executions']
            agg['success_rate'] = (agg['successful'] / total * 100) if total > 0 else 0
            agg['avg_duration'] = (agg['total_duration'] / agg['successful']) if agg['successful'] > 0 else 0
            agg['findings_per_run'] = (agg['total_findings'] / agg['successful']) if agg['successful'] > 0 else 0
            tools_list.append(agg)
        
        # Sort by execution count
        tools_list.sort(key=lambda x: x['executions'], reverse=True)
        
        severity_counts = self._count_severities(all_findings)
        
        return {
            'report_type': 'tool_analysis',
            'generated_at': utc_now().isoformat(),
            'filter': {
                'tool_name': tool_name,
                'model': filter_model,
                'app': filter_app
            },
            'tools': tools_list,
            'tools_count': len(tools_list),
            'total_executions': sum(t['executions'] for t in tools_list),
            'summary': {
                'total_findings': len(all_findings),
                'severity_breakdown': severity_counts
            },
            'by_model': tools_by_model,
            'findings': all_findings[:500]
        }
    
    # ==========================================================================
    # HELPERS
    # ==========================================================================
    
    def _validate_config(self, report_type: str, config: Dict[str, Any]) -> None:
        """Validate config for report type."""
        if report_type == 'model_analysis':
            if not config.get('model_slug'):
                raise ValueError("model_slug is required for model_analysis")
        elif report_type == 'template_comparison':
            if not config.get('template_slug'):
                raise ValueError("template_slug is required for template_comparison")
        elif report_type == 'tool_analysis':
            pass  # All fields optional
        else:
            raise ValueError(f"Unknown report type: {report_type}")
    
    def _generate_title(self, report_type: str, config: Dict[str, Any]) -> str:
        """Generate default title."""
        if report_type == 'model_analysis':
            return f"Model Analysis: {config.get('model_slug', 'Unknown')}"
        elif report_type == 'template_comparison':
            return f"Template Comparison: {config.get('template_slug', 'Unknown')}"
        elif report_type == 'tool_analysis':
            tool = config.get('tool_name', 'All Tools')
            return f"Tool Analysis: {tool}"
        return "Analysis Report"
    
    def _process_task_for_report(
        self,
        task: AnalysisTask,
        model_slug: str,
        app_number: int
    ) -> Dict[str, Any]:
        """Process a single task into report entry format."""
        # Check for failed/cancelled tasks
        if task.status in (AnalysisStatus.FAILED, AnalysisStatus.CANCELLED):
            return {
                'app_number': app_number,
                'model_slug': model_slug,
                'task_id': task.task_id,
                'status': 'failed',
                'error_message': task.error_message or 'Analysis failed or was cancelled',
                'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                'findings_count': 0,
                'severity_counts': {},
                'tools': {},
                'findings': []
            }
        
        # Load full results
        result = self.unified_service.load_analysis_results(task.task_id)
        
        if not result or not result.raw_data:
            return {
                'app_number': app_number,
                'model_slug': model_slug,
                'task_id': task.task_id,
                'status': 'no_results',
                'error_message': 'No analysis results available',
                'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                'findings_count': 0,
                'severity_counts': {},
                'tools': {},
                'findings': []
            }
        
        raw = result.raw_data
        results_wrapper = raw.get('results', {})
        summary = raw.get('summary') or results_wrapper.get('summary') or {}
        
        # Extract findings
        findings = raw.get('findings') or results_wrapper.get('findings') or []
        severity_counts = summary.get('severity_breakdown') or summary.get('findings_by_severity', {})
        
        # Extract tools
        tools = raw.get('tools') or results_wrapper.get('tools') or {}
        if not tools:
            tools = self._extract_tools_from_services(raw.get('services', {}))
        
        # Calculate duration
        duration = 0.0
        if task.completed_at and task.created_at:
            duration = (task.completed_at - task.created_at).total_seconds()
        
        # Get app metadata
        app = GeneratedApplication.query.filter_by(
            model_slug=model_slug,
            app_number=app_number
        ).first()
        
        return {
            'app_number': app_number,
            'model_slug': model_slug,
            'task_id': task.task_id,
            'status': 'completed',
            'completed_at': task.completed_at.isoformat() if task.completed_at else None,
            'duration_seconds': duration,
            'app_type': app.app_type if app else None,
            'template_slug': app.template_slug if app else None,
            'findings_count': len(findings),
            'severity_counts': severity_counts,
            'tools': tools,
            'findings': findings[:100]  # Limit per app
        }
    
    def _extract_tools_from_services(self, services: Dict[str, Any]) -> Dict[str, Any]:
        """Extract flat tool map from nested services structure."""
        tools = {}
        
        for service_name, service_data in services.items():
            if not isinstance(service_data, dict):
                continue
            
            tool_results = self._extract_tools_from_service(service_data)
            for tool_name, tool_data in tool_results.items():
                tool_data['service'] = service_name
                tools[tool_name] = tool_data
        
        return tools
    
    def _extract_tools_from_service(self, service_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract tool results from a single service."""
        tools = {}
        
        analysis = service_data.get('analysis', {})
        results = analysis.get('results', {})
        
        if not isinstance(results, dict):
            return tools
        
        # Handle language-grouped structure (static analyzer)
        for key, value in results.items():
            if isinstance(value, dict):
                # Check if it's a language wrapper
                has_tool_children = any(
                    isinstance(v, dict) and ('status' in v or 'executed' in v)
                    for v in value.values()
                    if not str(v).startswith('_')
                )
                
                if has_tool_children:
                    # Language wrapper - extract tools
                    for tool_name, tool_data in value.items():
                        if isinstance(tool_data, dict) and ('status' in tool_data or 'executed' in tool_data):
                            tools[tool_name] = self._normalize_tool_data(tool_data)
                elif 'status' in value or 'executed' in value:
                    # Direct tool entry
                    tools[key] = self._normalize_tool_data(value)
        
        return tools
    
    def _normalize_tool_data(self, tool_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize tool data to consistent format."""
        status = tool_data.get('status', 'unknown')
        if status in ('success', 'completed', 'no_issues'):
            status = 'success'
        elif tool_data.get('executed') == False:
            status = 'skipped'
        
        return {
            'status': status,
            'total_issues': tool_data.get('total_issues') or tool_data.get('issue_count', 0),
            'duration_seconds': tool_data.get('duration_seconds', 0),
            'issues': tool_data.get('issues', []),
            'executed': tool_data.get('executed', True)
        }
    
    def _count_severities(self, findings: List[Dict[str, Any]]) -> Dict[str, int]:
        """Count findings by severity."""
        counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}
        for f in findings:
            sev = str(f.get('severity', 'info')).lower()
            if sev in counts:
                counts[sev] += 1
        return counts
    
    def _calculate_metrics(self, apps_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate statistical metrics for apps."""
        if not apps_data:
            return {}
        
        findings_counts = [a.get('findings_count', 0) for a in apps_data]
        durations = [a.get('duration_seconds', 0) for a in apps_data if a.get('duration_seconds', 0) > 0]
        
        metrics = {
            'findings_distribution': {
                'mean': statistics.mean(findings_counts) if findings_counts else 0,
                'median': statistics.median(findings_counts) if findings_counts else 0,
                'min': min(findings_counts) if findings_counts else 0,
                'max': max(findings_counts) if findings_counts else 0,
                'total': sum(findings_counts)
            }
        }
        
        if len(findings_counts) > 1:
            metrics['findings_distribution']['std_dev'] = statistics.stdev(findings_counts)
        
        if durations:
            metrics['duration_statistics'] = {
                'mean': statistics.mean(durations),
                'median': statistics.median(durations),
                'total': sum(durations)
            }
        
        return metrics
    
    def _identify_common_issues(self, models_data: List[Dict[str, Any]]) -> tuple:
        """Identify issues common across models vs unique to specific models."""
        # Group findings by message/rule
        issue_occurrences: Dict[str, List[str]] = {}
        
        for model in models_data:
            model_slug = model.get('model_slug', 'unknown')
            for finding in model.get('findings', []):
                key = f"{finding.get('tool', '')}:{finding.get('message', '')[:100]}"
                if key not in issue_occurrences:
                    issue_occurrences[key] = []
                if model_slug not in issue_occurrences[key]:
                    issue_occurrences[key].append(model_slug)
        
        # Categorize as common (>50% of models) or unique
        threshold = len(models_data) / 2
        common = []
        unique: Dict[str, List[str]] = {}
        
        for key, models in issue_occurrences.items():
            parts = key.split(':', 1)
            issue_info = {'tool': parts[0], 'message': parts[1] if len(parts) > 1 else '', 'models': models}
            
            if len(models) >= threshold:
                common.append(issue_info)
            else:
                for model in models:
                    if model not in unique:
                        unique[model] = []
                    unique[model].append(issue_info)
        
        return common, unique
    
    def _extract_summary(self, report_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract quick summary for list display."""
        summary = data.get('summary', {})
        
        if report_type == 'model_analysis':
            return {
                'model_slug': data.get('model_slug'),
                'apps_count': data.get('apps_count', 0),
                'total_findings': summary.get('total_findings', 0),
                'critical': summary.get('severity_breakdown', {}).get('critical', 0)
            }
        elif report_type == 'template_comparison':
            return {
                'template_slug': data.get('template_slug'),
                'models_count': data.get('models_count', 0),
                'total_findings': summary.get('total_findings', 0),
                'common_issues': summary.get('common_issues_count', 0)
            }
        elif report_type == 'tool_analysis':
            return {
                'tools_count': data.get('tools_count', 0),
                'total_executions': data.get('total_executions', 0),
                'total_findings': summary.get('total_findings', 0)
            }
        
        return summary


# Singleton accessor
_report_service: Optional[ReportService] = None


def get_report_service() -> ReportService:
    """Get singleton ReportService instance."""
    global _report_service
    if _report_service is None:
        _report_service = ReportService()
    return _report_service
