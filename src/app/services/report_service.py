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
from ..utils.slug_utils import normalize_model_slug, generate_slug_variants
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
        
        # Normalize and generate slug variants for matching
        normalized_slug = normalize_model_slug(model_slug)
        slug_variants = generate_slug_variants(model_slug)
        
        logger.info(f"Generating model report for {model_slug} (normalized: {normalized_slug}, variants: {slug_variants})")
        
        # Query completed tasks for this model using slug variants
        query = AnalysisTask.query.filter(
            AnalysisTask.target_model.in_(slug_variants),
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
        
        # Finalize tool stats with display-friendly fields
        for tool_name, stats in tools_stats.items():
            total = stats['executions']
            stats['success_rate'] = (stats['successful'] / total * 100) if total > 0 else 0
            stats['avg_duration'] = (stats['total_duration'] / stats['successful']) if stats['successful'] > 0 else 0
            stats['findings_per_run'] = (stats['total_findings'] / stats['successful']) if stats['successful'] > 0 else 0
            # Add display-friendly fields for template
            stats['display_name'] = tool_name.replace('_', ' ').title()
            stats['total_runs'] = stats['executions']
            stats['overall_status'] = 'success' if stats['success_rate'] >= 50 else 'error'
        
        # Get model capability info if available (using correct attribute names)
        model_info = {}
        try:
            capability = ModelCapability.query.filter(
                (ModelCapability.canonical_slug == model_slug) |
                (ModelCapability.canonical_slug == normalized_slug)
            ).first()
            if capability:
                model_info = {
                    'model_name': capability.model_name,
                    'provider': capability.provider,
                    'context_window': capability.context_window,
                    'max_output_tokens': capability.max_output_tokens,
                    'supports_function_calling': capability.supports_function_calling,
                    'supports_vision': capability.supports_vision,
                    'supports_streaming': capability.supports_streaming,
                    'supports_json_mode': capability.supports_json_mode,
                    'is_free': capability.is_free,
                    'input_price_per_token': capability.input_price_per_token,
                    'output_price_per_token': capability.output_price_per_token,
                }
        except Exception as e:
            logger.warning(f"Could not fetch model capability: {e}")
        
        # Calculate aggregate execution metrics
        total_duration = sum(a.get('duration_seconds', 0) or 0 for a in apps_data)
        total_queue_time = sum(a.get('queue_time_seconds', 0) or 0 for a in apps_data)
        avg_duration = total_duration / len(apps_data) if apps_data else 0
        
        # Calculate generation statistics (using correct field names from _process_task_for_report)
        generation_stats = {
            'total_apps': len(apps_data),
            'successful_generations': sum(1 for a in apps_data if a.get('generation_status') in ('completed', 'COMPLETED')),
            'failed_generations': sum(1 for a in apps_data if a.get('generation_failed')),
            'total_scripted_fixes': sum(a.get('automatic_fixes', 0) or 0 for a in apps_data),
            'total_llm_fixes': sum(a.get('llm_fixes', 0) or 0 for a in apps_data),
            'total_manual_fixes': sum(a.get('manual_fixes', 0) or 0 for a in apps_data),
            'apps_with_fixes': sum(1 for a in apps_data if a.get('total_fixes', 0) > 0),
        }
        
        # Calculate analysis statistics
        analysis_stats = {
            'completed_analyses': sum(1 for a in apps_data if a.get('task_status') == 'completed'),
            'partial_analyses': sum(1 for a in apps_data if a.get('task_status') == 'partial_success'),
            'failed_analyses': sum(1 for a in apps_data if a.get('task_status') in ('failed', 'cancelled')),
            'total_retries': sum(a.get('retry_count', 0) or 0 for a in apps_data),
        }
        
        # Framework distribution
        backend_frameworks = {}
        frontend_frameworks = {}
        for a in apps_data:
            bf = a.get('backend_framework')
            ff = a.get('frontend_framework')
            if bf:
                backend_frameworks[bf] = backend_frameworks.get(bf, 0) + 1
            if ff:
                frontend_frameworks[ff] = frontend_frameworks.get(ff, 0) + 1
        
        return {
            'report_type': 'model_analysis',
            'model_slug': model_slug,
            'model_info': model_info,
            'generated_at': utc_now().isoformat(),
            'date_range': date_range,
            'apps': apps_data,
            'apps_count': len(apps_data),
            'total_tasks': len(tasks),
            # Summary with all fields the template expects
            'summary': {
                'total_apps': len(apps_data),
                'total_analyses': len(tasks),
                'total_findings': len(all_findings),
                'severity_breakdown': severity_counts,
                'avg_findings_per_app': len(all_findings) / len(apps_data) if apps_data else 0,
                # Extended metrics
                'avg_duration_seconds': avg_duration,
                'total_duration_seconds': total_duration,
                'total_queue_time_seconds': total_queue_time,
            },
            # Duplicate severity data for template compatibility
            'findings_breakdown': severity_counts,
            'scientific_metrics': scientific_metrics,
            # Provide both field names for compatibility
            'tools_statistics': tools_stats,
            'tool_summary': tools_stats,
            'findings': all_findings[:500],
            # Extended data sections
            'generation_stats': generation_stats,
            'analysis_stats': analysis_stats,
            'execution_metrics': {
                'total_duration_seconds': total_duration,
                'avg_duration_seconds': avg_duration,
                'total_queue_time_seconds': total_queue_time,
                'avg_queue_time_seconds': total_queue_time / len(apps_data) if apps_data else 0,
            },
            'framework_distribution': {
                'backend': backend_frameworks,
                'frontend': frontend_frameworks,
            },
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
        total_analyses = 0
        
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
                # Add model display name
                entry['model_name'] = app.model_slug.replace('_', ' / ').replace('-', ' ').title()
                # Calculate total findings for this model
                entry['total_findings'] = entry.get('findings_count', 0)
                models_data.append(entry)
                
                if entry.get('findings'):
                    all_findings.extend(entry['findings'])
                
                # Count all analyses for this app
                total_analyses += AnalysisTask.query.filter(
                    AnalysisTask.target_model == app.model_slug,
                    AnalysisTask.target_app_number == app.app_number,
                    AnalysisTask.status.in_([AnalysisStatus.COMPLETED, AnalysisStatus.PARTIAL_SUCCESS])
                ).count()
        
        report.update_progress(60)
        db.session.commit()
        
        # Calculate comparison metrics
        severity_counts = self._count_severities(all_findings)
        
        # Find common vs unique issues
        common_issues, unique_issues = self._identify_common_issues(models_data)
        
        # Calculate rankings
        rankings = self._calculate_rankings(models_data)
        
        # Calculate execution metrics
        total_duration = sum(m.get('duration_seconds', 0) or 0 for m in models_data)
        avg_duration = total_duration / len(models_data) if models_data else 0
        
        # Framework distribution
        backend_frameworks = {}
        frontend_frameworks = {}
        for m in models_data:
            bf = m.get('backend_framework')
            ff = m.get('frontend_framework')
            if bf:
                backend_frameworks[bf] = backend_frameworks.get(bf, 0) + 1
            if ff:
                frontend_frameworks[ff] = frontend_frameworks.get(ff, 0) + 1
        
        report.update_progress(80)
        db.session.commit()
        
        return {
            'report_type': 'template_comparison',
            'template_slug': template_slug,
            'generated_at': utc_now().isoformat(),
            'models': models_data,
            'models_count': len(models_data),
            'summary': {
                'template_slug': template_slug,
                'models_compared': len(models_data),
                'total_analyses': total_analyses,
                'total_findings': len(all_findings),
                'severity_breakdown': severity_counts,
                'common_issues_count': len(common_issues),
                'unique_issues_count': sum(len(v) for v in unique_issues.values()) if isinstance(unique_issues, dict) else len(unique_issues),
                'avg_duration_seconds': avg_duration,
            },
            'findings_breakdown': severity_counts,
            'rankings': rankings,
            'comparison': {
                'common_issues': common_issues[:50],
                'unique_by_model': unique_issues
            },
            'framework_distribution': {
                'backend': backend_frameworks,
                'frontend': frontend_frameworks,
            },
            'findings': all_findings[:500]
        }
    
    def _calculate_rankings(self, models_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate rankings for template comparison."""
        if not models_data:
            return {}
        
        # Score based on weighted severity (lower is better)
        def calculate_score(m):
            sev = m.get('severity_breakdown') or m.get('severity_counts') or {}
            return (
                (sev.get('critical', 0) or 0) * 100 +
                (sev.get('high', 0) or 0) * 10 +
                (sev.get('medium', 0) or 0) * 3 +
                (sev.get('low', 0) or 0) * 1 +
                (sev.get('info', 0) or 0) * 0.1
            )
        
        # Add score to each model
        for m in models_data:
            m['score'] = calculate_score(m)
        
        # Sort by score (lower is better)
        sorted_models = sorted(models_data, key=lambda x: x.get('score', float('inf')))
        
        best = sorted_models[0] if sorted_models else None
        worst = sorted_models[-1] if sorted_models else None
        
        # Find best by each severity
        by_severity = {}
        for sev in ['critical', 'high', 'medium', 'low']:
            sorted_by_sev = sorted(
                models_data,
                key=lambda x: (x.get('severity_breakdown') or {}).get(sev, 0) or (x.get('severity_counts') or {}).get(sev, 0)
            )
            if sorted_by_sev:
                by_severity[sev] = {
                    'model': sorted_by_sev[0].get('model_slug'),
                    'model_name': sorted_by_sev[0].get('model_name', sorted_by_sev[0].get('model_slug')),
                    'count': (sorted_by_sev[0].get('severity_breakdown') or {}).get(sev, 0) or (sorted_by_sev[0].get('severity_counts') or {}).get(sev, 0)
                }
        
        return {
            'best_overall': {
                'model': best.get('model_slug') if best else None,
                'model_name': best.get('model_name', best.get('model_slug')) if best else None,
                'score': best.get('score') if best else None,
                'total_findings': best.get('total_findings', 0) if best else 0,
            } if best else None,
            'worst_overall': {
                'model': worst.get('model_slug') if worst else None,
                'model_name': worst.get('model_name', worst.get('model_slug')) if worst else None,
                'score': worst.get('score') if worst else None,
                'total_findings': worst.get('total_findings', 0) if worst else 0,
            } if worst else None,
            'by_severity': by_severity,
            'all_ranked': [
                {
                    'rank': i + 1,
                    'model': m.get('model_slug'),
                    'model_name': m.get('model_name', m.get('model_slug')),
                    'score': m.get('score'),
                    'total_findings': m.get('total_findings', 0),
                }
                for i, m in enumerate(sorted_models)
            ]
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
            # Add display-friendly fields
            agg['display_name'] = t_name.replace('_', ' ').title()
            agg['name'] = t_name
            agg['total_runs'] = agg['executions']
            agg['avg_findings'] = agg['findings_per_run']
            agg['container'] = agg['service']
            tools_list.append(agg)
        
        # Sort by execution count
        tools_list.sort(key=lambda x: x['executions'], reverse=True)
        
        severity_counts = self._count_severities(all_findings)
        
        # Calculate aggregate stats
        total_runs = sum(t['executions'] for t in tools_list)
        avg_success = sum(t['success_rate'] for t in tools_list) / len(tools_list) if tools_list else 0
        
        # Group by service/container
        categories = {}
        for t in tools_list:
            svc = t.get('service', 'unknown')
            if svc not in categories:
                categories[svc] = {
                    'tools_count': 0,
                    'total_findings': 0,
                    'total_runs': 0,
                    'tools': []
                }
            categories[svc]['tools_count'] += 1
            categories[svc]['total_findings'] += t['total_findings']
            categories[svc]['total_runs'] += t['executions']
            categories[svc]['tools'].append(t['tool_name'])
        
        # Find top performers
        top_by_findings = sorted(tools_list, key=lambda x: x['total_findings'], reverse=True)[:5]
        top_by_success = sorted(tools_list, key=lambda x: x['success_rate'], reverse=True)[:5]
        
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
            'total_executions': total_runs,
            'summary': {
                'tools_analyzed': len(tools_list),
                'total_runs': total_runs,
                'total_findings': len(all_findings),
                'avg_success_rate': avg_success,
                'severity_breakdown': severity_counts
            },
            'findings_breakdown': severity_counts,
            'categories': categories,
            'by_model': tools_by_model,
            'top_performers': {
                'by_findings': [
                    {'name': t['tool_name'], 'findings': t['total_findings'], 'runs': t['executions']}
                    for t in top_by_findings
                ],
                'by_success_rate': [
                    {'name': t['tool_name'], 'success_rate': t['success_rate'], 'runs': t['executions']}
                    for t in top_by_success
                ]
            },
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
        """Process a single task into report entry format with comprehensive data."""
        # Get app metadata first - needed for all cases
        app = GeneratedApplication.query.filter_by(
            model_slug=model_slug,
            app_number=app_number
        ).first()
        
        # Try alternate slug if not found
        if not app:
            for variant in generate_slug_variants(model_slug):
                app = GeneratedApplication.query.filter_by(
                    model_slug=variant,
                    app_number=app_number
                ).first()
                if app:
                    break
        
        # Calculate duration from task timestamps
        duration = task.actual_duration or 0.0
        if not duration and task.completed_at and task.started_at:
            duration = (task.completed_at - task.started_at).total_seconds()
        
        # Calculate queue time
        queue_time = task.queue_time or 0.0
        if not queue_time and task.started_at and task.created_at:
            queue_time = (task.started_at - task.created_at).total_seconds()
        
        # Map task status to display status
        status_map = {
            AnalysisStatus.COMPLETED: 'completed',
            AnalysisStatus.PARTIAL_SUCCESS: 'partial',
            AnalysisStatus.FAILED: 'failed',
            AnalysisStatus.CANCELLED: 'cancelled',
            AnalysisStatus.RUNNING: 'running',
            AnalysisStatus.PENDING: 'pending'
        }
        display_status = status_map.get(task.status, str(task.status.value) if task.status else 'unknown')
        
        # Determine has_analysis based on task status, not result availability
        has_analysis = task.status in (
            AnalysisStatus.COMPLETED, 
            AnalysisStatus.PARTIAL_SUCCESS
        )
        
        # Build base entry with all task/app data from DB
        base_entry = {
            'app_number': app_number,
            'model_slug': model_slug,
            'task_id': task.task_id,
            'status': display_status,
            'task_status': task.status.value if task.status else 'unknown',  # Raw status for JS
            'has_analysis': has_analysis,
            'error_message': task.error_message,
            'completed_at': task.completed_at.isoformat() if task.completed_at else None,
            'started_at': task.started_at.isoformat() if task.started_at else None,
            'created_at': task.created_at.isoformat() if task.created_at else None,
            'duration_seconds': duration,
            'queue_time_seconds': queue_time,
            'retry_count': task.retry_count or 0,
            # App metadata
            'app_type': app.app_type if app else None,
            'template_slug': app.template_slug if app else None,
            'provider': app.provider if app else None,
            'backend_framework': app.backend_framework if app else None,
            'frontend_framework': app.frontend_framework if app else None,
            'generation_status': app.generation_status.value if app and app.generation_status else None,
            'generation_mode': app.generation_mode.value if app and hasattr(app, 'generation_mode') and app.generation_mode else None,
            'container_status': app.container_status if app else None,
            # Generation fix counters (correct attribute names from model)
            'generation_failed': app.is_generation_failed if app else False,
            'failure_stage': app.failure_stage if app else None,
            'generation_attempts': getattr(app, 'generation_attempts', 1) if app else 1,
            'retry_fixes': getattr(app, 'retry_fixes', 0) if app else 0,
            'automatic_fixes': getattr(app, 'automatic_fixes', 0) if app else 0,
            'llm_fixes': getattr(app, 'llm_fixes', 0) if app else 0,
            'manual_fixes': getattr(app, 'manual_fixes', 0) if app else 0,
        }
        
        # Get severity from DB as fallback (always available)
        db_severity = task.get_severity_breakdown() or {}
        db_issues_count = task.issues_found or 0
        
        # Try to load full results for detailed findings
        result = self.unified_service.load_analysis_results(task.task_id)
        
        # Initialize with DB fallback values
        severity_counts = db_severity or {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}
        findings_count = db_issues_count
        findings = []
        tools = {}
        subtasks_data = []
        
        if result and result.raw_data:
            # Have full results - extract detailed data
            raw = result.raw_data
            results_wrapper = raw.get('results', {})
            summary = raw.get('summary') or results_wrapper.get('summary') or {}
            
            # Extract findings
            findings = raw.get('findings') or results_wrapper.get('findings') or []
            
            # Get severity counts from results, fallback to DB, or compute from findings
            result_severity = summary.get('severity_breakdown') or summary.get('findings_by_severity')
            if result_severity:
                severity_counts = result_severity
            elif findings:
                severity_counts = self._count_severities(findings)
            elif db_severity:
                severity_counts = db_severity
            
            # Update findings count
            if findings:
                findings_count = len(findings)
            elif db_issues_count:
                findings_count = db_issues_count
            
            # Extract tools
            tools = raw.get('tools') or results_wrapper.get('tools') or {}
            if not tools:
                tools = self._extract_tools_from_services(raw.get('services', {}))
            
            # Extract services for subtask breakdown
            services = raw.get('services', {})
            for svc_name, svc_data in services.items():
                if isinstance(svc_data, dict):
                    subtasks_data.append({
                        'service': svc_name,
                        'status': svc_data.get('status', 'unknown'),
                        'tools_count': len(svc_data.get('analysis', {}).get('results', {})) if isinstance(svc_data.get('analysis'), dict) else 0,
                        'duration': svc_data.get('metadata', {}).get('duration_seconds') if isinstance(svc_data.get('metadata'), dict) else None
                    })
        else:
            # No result file - use DB data as-is
            # Try to get result_summary from task for tool data
            task_summary = task.get_result_summary()
            if task_summary:
                # Extract what we can from DB result_summary
                if 'tools' in task_summary:
                    tools = task_summary['tools']
                if 'findings' in task_summary:
                    findings = task_summary['findings'][:50]  # Limit
                    findings_count = len(task_summary.get('findings', []))
                if 'summary' in task_summary:
                    sum_data = task_summary['summary']
                    if 'severity_breakdown' in sum_data:
                        severity_counts = sum_data['severity_breakdown']
        
        # Ensure severity_counts has all required keys
        for key in ['critical', 'high', 'medium', 'low', 'info']:
            if key not in severity_counts:
                severity_counts[key] = 0
        
        # Get subtask info from DB if we have a main task
        if task.is_main_task:
            db_subtasks = task.get_all_subtasks()
            for st in db_subtasks:
                if not any(s['service'] == st.service_name for s in subtasks_data):
                    subtasks_data.append({
                        'service': st.service_name,
                        'status': st.status.value if st.status else 'unknown',
                        'task_id': st.task_id,
                        'issues_found': st.issues_found or 0,
                        'duration': st.actual_duration
                    })
        
        # Merge all data
        base_entry.update({
            'findings_count': findings_count,
            'severity_counts': severity_counts,
            'severity_breakdown': severity_counts,  # Alias for template
            'tools': tools,
            'findings': findings[:50],  # Limit per app
            'subtasks': subtasks_data,
            'has_subtasks': len(subtasks_data) > 0,
            # Calculated metrics (using correct attribute names from model)
            'total_fixes': (
                (getattr(app, 'automatic_fixes', 0) or 0) +
                (getattr(app, 'llm_fixes', 0) or 0) +
                (getattr(app, 'manual_fixes', 0) or 0)
            ) if app else 0
        })
        
        return base_entry
    
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
