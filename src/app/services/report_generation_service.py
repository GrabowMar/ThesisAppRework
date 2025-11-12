"""
Report Generation Service

Generates comprehensive analysis reports in multiple formats (PDF, HTML, Excel).
Supports various report types: app analysis, model comparisons, tool effectiveness, executive summaries.
"""
import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Literal
from flask import Flask, current_app

from ..extensions import db
from ..models import Report, AnalysisTask, GeneratedApplication, ModelCapability, AnalysisResult
from ..utils.time import utc_now
from .service_base import ServiceError, NotFoundError, ValidationError

logger = logging.getLogger(__name__)

ReportType = Literal['app_analysis', 'model_comparison', 'tool_effectiveness', 'executive_summary', 'custom']
ReportFormat = Literal['pdf', 'html', 'excel', 'json']


class ReportGenerationService:
    """Service for generating analysis reports in various formats."""
    
    def __init__(self, app: Optional[Flask] = None):
        """Initialize the report generation service."""
        self.app = app
        self._reports_dir: Optional[Path] = None
        self._unified_results_service = None
        self._statistics_service = None
        
        if app:
            self.init_app(app)
    
    def init_app(self, app: Flask) -> None:
        """Initialize with Flask app."""
        self.app = app
        
        # Get reports directory from config or use default
        # root_path is src/app, so parent.parent gets project root
        project_root = Path(app.root_path).parent.parent
        reports_dir = app.config.get('REPORTS_DIR', project_root / 'reports')
        self._reports_dir = Path(reports_dir)
        self._reports_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Report generation service initialized with directory: {self._reports_dir}")
    
    @property
    def reports_dir(self) -> Path:
        """Get reports directory."""
        if self._reports_dir is None:
            if current_app:
                # Get project root (parent of src/)
                project_root = Path(current_app.root_path).parent.parent
                reports_dir = current_app.config.get('REPORTS_DIR', 
                                                     project_root / 'reports')
                self._reports_dir = Path(reports_dir)
                self._reports_dir.mkdir(parents=True, exist_ok=True)
            else:
                raise ServiceError("Reports directory not configured")
        return self._reports_dir
    
    def _get_unified_results_service(self):
        """Lazy load unified results service."""
        if self._unified_results_service is None:
            from .unified_result_service import UnifiedResultService
            self._unified_results_service = UnifiedResultService()
        return self._unified_results_service
    
    def _get_statistics_service(self):
        """Get statistics service functions."""
        # statistics_service provides functions, not a class
        if self._statistics_service is None:
            from . import statistics_service
            self._statistics_service = statistics_service
        return self._statistics_service
    
    def generate_report(
        self,
        report_type: ReportType,
        format: ReportFormat,
        config: Dict[str, Any],
        title: Optional[str] = None,
        description: Optional[str] = None,
        user_id: Optional[int] = None,
        expires_in_days: Optional[int] = 30
    ) -> Report:
        """
        Generate a report based on type and configuration.
        
        Args:
            report_type: Type of report to generate
            format: Output format (pdf, html, excel, json)
            config: Report-specific configuration
            title: Optional report title
            description: Optional report description
            user_id: ID of user creating the report
            expires_in_days: Days until report expires (None = never)
        
        Returns:
            Report model instance
        """
        try:
            # Generate unique report ID
            report_id = f"report_{uuid.uuid4().hex[:12]}"
            
            # Create report record
            report = Report(
                report_id=report_id,
                report_type=report_type,
                title=title or self._generate_title(report_type, config),
                description=description,
                format=format,
                status='pending',
                created_by=user_id
            )
            
            report.set_config(config)
            
            # Set expiration
            if expires_in_days:
                report.expires_at = utc_now() + timedelta(days=expires_in_days)
            
            db.session.add(report)
            db.session.commit()
            
            logger.info(f"Created report {report_id} ({report_type}, {format})")
            
            # Generate the report
            self._generate_report_content(report)
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating report: {e}", exc_info=True)
            if 'report' in locals():
                report.mark_failed(str(e))
                db.session.commit()
            raise ServiceError(f"Failed to generate report: {e}")
    
    def _generate_report_content(self, report: Report) -> None:
        """Generate the actual report content based on type."""
        try:
            report.mark_generating()
            db.session.commit()
            
            config = report.get_config()
            
            # Route to appropriate generator
            if report.report_type == 'app_analysis':
                data = self._generate_app_analysis_data(config)
            elif report.report_type == 'model_comparison':
                data = self._generate_model_comparison_data(config)
            elif report.report_type == 'tool_effectiveness':
                data = self._generate_tool_effectiveness_data(config)
            elif report.report_type == 'executive_summary':
                data = self._generate_executive_summary_data(config)
            elif report.report_type == 'custom':
                data = self._generate_custom_data(config)
            else:
                raise ValidationError(f"Unknown report type: {report.report_type}")
            
            report.update_progress(50)
            db.session.commit()
            
            # Generate output file
            file_path = self._render_report(report, data)
            
            # Get file size
            abs_path = self.reports_dir / file_path
            file_size = abs_path.stat().st_size
            
            # Update report
            report.mark_completed(str(file_path), file_size)
            
            # Store summary
            summary = self._generate_summary(data, report.report_type)
            report.set_summary(summary)
            
            db.session.commit()
            
            logger.info(f"Report {report.report_id} generated successfully: {file_path}")
            
        except Exception as e:
            logger.error(f"Error generating report content: {e}", exc_info=True)
            report.mark_failed(str(e))
            db.session.commit()
            raise
    
    def _generate_app_analysis_data(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Generate data for single app analysis report."""
        model_slug = config.get('model_slug')
        app_number = config.get('app_number')
        task_id = config.get('task_id')
        
        if not model_slug or not app_number:
            raise ValidationError("model_slug and app_number required for app analysis report")
        
        # Load data from both DB and filesystem
        unified_service = self._get_unified_results_service()
        
        # Get latest task if not specified
        if not task_id:
            tasks = db.session.query(AnalysisTask).filter(
                AnalysisTask.target_model == model_slug,
                AnalysisTask.target_app_number == app_number,
                AnalysisTask.status == 'completed'
            ).order_by(AnalysisTask.completed_at.desc()).limit(1).all()
            
            if not tasks:
                raise NotFoundError(f"No completed analysis found for {model_slug} app {app_number}")
            
            task_id = tasks[0].task_id
        
        # Load unified results
        result = unified_service.load_analysis_results(task_id)
        
        if not result:
            raise NotFoundError(f"Analysis result not found for task {task_id}")
        
        # Get app info
        app = db.session.query(GeneratedApplication).filter(
            GeneratedApplication.model_slug == model_slug,
            GeneratedApplication.app_number == app_number
        ).first()
        
        # Compile comprehensive data
        return {
            'model_slug': model_slug,
            'app_number': app_number,
            'task_id': task_id,
            'app': app.to_dict() if app else None,
            'analysis': result.raw_data if result else {},
            'metadata': result.raw_data.get('metadata', {}) if result else {},
            'summary': result.summary if result else {},
            'tools': result.tools if result else {},
            'findings': result.raw_data.get('findings', []) if result else [],
            'services': result.raw_data.get('services', {}) if result else {},
            'timestamp': utc_now().isoformat()
        }
    
    def _generate_model_comparison_data(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Generate data for model comparison report."""
        model_slugs = config.get('model_slugs', [])
        app_number = config.get('app_number', 1)
        date_range = config.get('date_range', {})
        
        if not model_slugs:
            raise ValidationError("model_slugs required for model comparison report")
        
        unified_service = self._get_unified_results_service()
        comparison_data = []
        
        for model_slug in model_slugs:
            # Get latest completed task for this model
            tasks = db.session.query(AnalysisTask).filter(
                AnalysisTask.target_model == model_slug,
                AnalysisTask.target_app_number == app_number,
                AnalysisTask.status == 'completed'
            )
            
            # Apply date filters if provided
            if date_range.get('start'):
                tasks = tasks.filter(AnalysisTask.completed_at >= date_range['start'])
            if date_range.get('end'):
                tasks = tasks.filter(AnalysisTask.completed_at <= date_range['end'])
            
            tasks = tasks.order_by(AnalysisTask.completed_at.desc()).limit(1).all()
            
            if not tasks:
                logger.warning(f"No completed analysis for {model_slug}")
                continue
            
            task = tasks[0]
            result = unified_service.load_analysis_results(task.task_id)
            
            if result:
                findings = result.raw_data.get('findings', [])
                comparison_data.append({
                    'model_slug': model_slug,
                    'task_id': task.task_id,
                    'summary': result.summary,
                    'tools': result.tools,
                    'findings_count': len(findings) if findings else 0,
                    'findings': findings,
                    'completed_at': task.completed_at.isoformat() if task.completed_at else None
                })
        
        # Aggregate statistics
        aggregated = self._aggregate_model_comparison(comparison_data)
        
        return {
            'models': comparison_data,
            'app_number': app_number,
            'date_range': date_range,
            'aggregated': aggregated,
            'timestamp': utc_now().isoformat()
        }
    
    def _generate_tool_effectiveness_data(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Generate data for tool effectiveness report."""
        date_range = config.get('date_range', {})
        tools = config.get('tools', [])  # Specific tools or all
        
        # Query all completed tasks
        query = db.session.query(AnalysisTask).filter(
            AnalysisTask.status == 'completed'
        )
        
        # Apply date filters
        if date_range.get('start'):
            query = query.filter(AnalysisTask.completed_at >= date_range['start'])
        if date_range.get('end'):
            query = query.filter(AnalysisTask.completed_at <= date_range['end'])
        
        tasks = query.all()
        
        # Aggregate tool statistics
        tool_stats = {}
        unified_service = self._get_unified_results_service()
        
        for task in tasks:
            try:
                result = unified_service.load_analysis_results(task.task_id)
                
                if not result or not result.tools:
                    continue
                
                for tool_name, tool_data in result.tools.items():
                    # Filter if specific tools requested
                    if tools and tool_name not in tools:
                        continue
                    
                    if tool_name not in tool_stats:
                        tool_stats[tool_name] = {
                            'total_runs': 0,
                            'successful_runs': 0,
                            'failed_runs': 0,
                            'total_findings': 0,
                            'total_duration': 0,
                            'severity_breakdown': {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}
                        }
                    
                    stats = tool_stats[tool_name]
                    stats['total_runs'] += 1
                    
                    if tool_data.get('status') == 'success':
                        stats['successful_runs'] += 1
                    else:
                        stats['failed_runs'] += 1
                    
                    stats['total_findings'] += tool_data.get('total_issues', 0)
                    stats['total_duration'] += tool_data.get('duration_seconds', 0)
                    
                    # Aggregate severity breakdown
                    severity_data = tool_data.get('severity_breakdown', {})
                    for severity, count in severity_data.items():
                        if severity in stats['severity_breakdown']:
                            stats['severity_breakdown'][severity] += count
            
            except Exception as e:
                logger.warning(f"Error processing task {task.task_id} for tool stats: {e}")
                continue
        
        # Calculate percentages and averages
        for tool_name, stats in tool_stats.items():
            if stats['total_runs'] > 0:
                stats['success_rate'] = (stats['successful_runs'] / stats['total_runs']) * 100
                stats['avg_duration'] = stats['total_duration'] / stats['total_runs']
                stats['avg_findings_per_run'] = stats['total_findings'] / stats['total_runs']
            else:
                stats['success_rate'] = 0
                stats['avg_duration'] = 0
                stats['avg_findings_per_run'] = 0
        
        return {
            'tools': tool_stats,
            'date_range': date_range,
            'total_tasks_analyzed': len(tasks),
            'timestamp': utc_now().isoformat()
        }
    
    def _generate_executive_summary_data(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Generate data for executive summary report."""
        date_range = config.get('date_range', {})
        
        stats_service = self._get_statistics_service()
        
        # Get overall statistics
        try:
            # Use statistics service functions
            generation_stats = stats_service.get_application_statistics()
            model_stats = stats_service.get_model_statistics()
            
            # Get analysis task statistics
            query = db.session.query(AnalysisTask)
            
            if date_range.get('start'):
                query = query.filter(AnalysisTask.created_at >= date_range['start'])
            if date_range.get('end'):
                query = query.filter(AnalysisTask.created_at <= date_range['end'])
            
            all_tasks = query.all()
            completed_tasks = [t for t in all_tasks if t.status == 'completed']
            
            # Aggregate findings across all completed tasks
            total_findings = 0
            severity_totals = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}
            
            for task in completed_tasks:
                if task.result_summary:
                    summary = task.get_result_summary()
                    if not summary:
                        continue
                    total_findings += summary.get('total_findings', 0)
                    
                    severity_data = summary.get('severity_breakdown', {})
                    for severity, count in severity_data.items():
                        if severity in severity_totals:
                            severity_totals[severity] += count
            
            return {
                'date_range': date_range,
                'summary': {
                    'total_apps_generated': generation_stats.get('total', 0),
                    'total_analyses_run': len(all_tasks),
                    'total_analyses_completed': len(completed_tasks),
                    'total_findings': total_findings,
                    'severity_breakdown': severity_totals,
                    'total_models': model_stats.get('total', 0) if model_stats else 0
                },
                'generation_stats': generation_stats,
                'model_stats': model_stats,
                'timestamp': utc_now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error generating executive summary: {e}", exc_info=True)
            # Return minimal data on error
            return {
                'date_range': date_range,
                'summary': {},
                'error': str(e),
                'timestamp': utc_now().isoformat()
            }
    
    def _generate_custom_data(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Generate data for custom report based on config."""
        # Custom reports allow arbitrary queries based on config
        query_type = config.get('query_type')
        
        if query_type == 'specific_tasks':
            task_ids = config.get('task_ids', [])
            tasks = db.session.query(AnalysisTask).filter(
                AnalysisTask.task_id.in_(task_ids)
            ).all()
            
            return {
                'tasks': [t.to_dict() for t in tasks],
                'config': config,
                'timestamp': utc_now().isoformat()
            }
        
        # Default: return config as-is
        return {
            'config': config,
            'timestamp': utc_now().isoformat()
        }
    
    def _aggregate_model_comparison(self, comparison_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate statistics across models for comparison."""
        if not comparison_data:
            return {}
        
        aggregated = {
            'total_models': len(comparison_data),
            'avg_findings': 0,
            'avg_critical': 0,
            'avg_high': 0,
            'best_model': None,
            'worst_model': None
        }
        
        total_findings = 0
        total_critical = 0
        total_high = 0
        
        min_findings = float('inf')
        max_findings = 0
        
        for model_data in comparison_data:
            findings_count = model_data.get('findings_count', 0)
            total_findings += findings_count
            
            summary = model_data.get('summary', {})
            severity = summary.get('severity_breakdown', {})
            
            critical = severity.get('critical', 0)
            high = severity.get('high', 0)
            
            total_critical += critical
            total_high += high
            
            # Track best/worst
            if findings_count < min_findings:
                min_findings = findings_count
                aggregated['best_model'] = model_data['model_slug']
            
            if findings_count > max_findings:
                max_findings = findings_count
                aggregated['worst_model'] = model_data['model_slug']
        
        # Calculate averages
        if len(comparison_data) > 0:
            aggregated['avg_findings'] = total_findings / len(comparison_data)
            aggregated['avg_critical'] = total_critical / len(comparison_data)
            aggregated['avg_high'] = total_high / len(comparison_data)
        
        return aggregated
    
    def _render_report(self, report: Report, data: Dict[str, Any]) -> str:
        """
        Render report to file in specified format.
        
        Returns:
            Relative file path from reports directory
        """
        # Import renderers here to avoid circular imports
        from .report_renderers import render_html, render_pdf, render_excel, render_json
        
        # Create subdirectory for report type
        output_dir = self.reports_dir / report.report_type
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = f"{report.report_id}_{timestamp}"
        
        if report.format == 'html':
            filename = f"{base_filename}.html"
            file_path = output_dir / filename
            render_html(report, data, file_path)
        
        elif report.format == 'pdf':
            filename = f"{base_filename}.pdf"
            file_path = output_dir / filename
            render_pdf(report, data, file_path)
        
        elif report.format == 'excel':
            filename = f"{base_filename}.xlsx"
            file_path = output_dir / filename
            render_excel(report, data, file_path)
        
        elif report.format == 'json':
            filename = f"{base_filename}.json"
            file_path = output_dir / filename
            render_json(report, data, file_path)
        
        else:
            raise ValidationError(f"Unsupported format: {report.format}")
        
        # Return relative path
        return str(file_path.relative_to(self.reports_dir))
    
    def _generate_title(self, report_type: ReportType, config: Dict[str, Any]) -> str:
        """Generate a default title based on report type and config."""
        if report_type == 'app_analysis':
            model = config.get('model_slug', 'unknown')
            app = config.get('app_number', 'unknown')
            return f"Analysis Report: {model} App #{app}"
        
        elif report_type == 'model_comparison':
            models = config.get('model_slugs', [])
            return f"Model Comparison Report ({len(models)} models)"
        
        elif report_type == 'tool_effectiveness':
            return "Tool Effectiveness Report"
        
        elif report_type == 'executive_summary':
            return "Executive Summary Report"
        
        elif report_type == 'custom':
            return config.get('title', "Custom Report")
        
        return "Analysis Report"
    
    def _generate_summary(self, data: Dict[str, Any], report_type: ReportType) -> Dict[str, Any]:
        """Generate a summary dictionary for quick display."""
        summary = {
            'report_type': report_type,
            'generated_at': utc_now().isoformat()
        }
        
        if report_type == 'app_analysis':
            analysis = data.get('analysis', {})
            summary['model'] = data.get('model_slug')
            summary['app_number'] = data.get('app_number')
            summary['total_findings'] = analysis.get('summary', {}).get('total_findings', 0)
        
        elif report_type == 'model_comparison':
            summary['models_count'] = len(data.get('models', []))
            summary['app_number'] = data.get('app_number')
        
        elif report_type == 'tool_effectiveness':
            tools = data.get('tools', {})
            summary['tools_analyzed'] = len(tools)
            summary['total_tasks'] = data.get('total_tasks_analyzed', 0)
        
        elif report_type == 'executive_summary':
            exec_summary = data.get('summary', {})
            summary['total_apps'] = exec_summary.get('total_apps_generated', 0)
            summary['total_analyses'] = exec_summary.get('total_analyses_completed', 0)
            summary['total_findings'] = exec_summary.get('total_findings', 0)
        
        return summary
    
    def get_report(self, report_id: str) -> Optional[Report]:
        """Get report by ID."""
        return db.session.query(Report).filter(Report.report_id == report_id).first()
    
    def list_reports(
        self,
        report_type: Optional[ReportType] = None,
        status: Optional[str] = None,
        user_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Report]:
        """List reports with optional filtering."""
        query = db.session.query(Report)
        
        if report_type:
            query = query.filter(Report.report_type == report_type)
        
        if status:
            query = query.filter(Report.status == status)
        
        if user_id:
            query = query.filter(Report.created_by == user_id)
        
        query = query.order_by(Report.created_at.desc())
        query = query.limit(limit).offset(offset)
        
        return query.all()
    
    def delete_report(self, report_id: str, delete_file: bool = True) -> bool:
        """Delete a report and optionally its file."""
        report = self.get_report(report_id)
        
        if not report:
            raise NotFoundError(f"Report {report_id} not found")
        
        # Delete file if requested and exists
        if delete_file and report.file_path:
            try:
                file_path = self.reports_dir / report.file_path
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"Deleted report file: {file_path}")
            except Exception as e:
                logger.error(f"Error deleting report file: {e}")
        
        # Delete from database
        db.session.delete(report)
        db.session.commit()
        
        logger.info(f"Deleted report {report_id}")
        return True
    
    def cleanup_expired_reports(self) -> int:
        """Clean up expired reports. Returns count of deleted reports."""
        now = utc_now()
        expired = db.session.query(Report).filter(
            Report.expires_at.isnot(None),
            Report.expires_at < now
        ).all()
        
        count = 0
        for report in expired:
            try:
                self.delete_report(report.report_id, delete_file=True)
                count += 1
            except Exception as e:
                logger.error(f"Error deleting expired report {report.report_id}: {e}")
        
        logger.info(f"Cleaned up {count} expired reports")
        return count
