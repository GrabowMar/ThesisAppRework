"""
Report Generation Service

Generates comprehensive analysis reports in multiple formats (HTML, JSON).
Supports three report types: model analysis, app comparison, tool analysis.
"""
import logging
import uuid
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Literal
from flask import Flask, current_app, render_template

from ..extensions import db
from ..models import Report
from ..utils.time import utc_now
from .service_base import ServiceError, NotFoundError, ValidationError
from .reports import ModelReportGenerator, AppReportGenerator, ToolReportGenerator

logger = logging.getLogger(__name__)

ReportType = Literal['model_analysis', 'app_analysis', 'tool_analysis']
ReportFormat = Literal['html', 'json']


class ReportGenerationService:
    """Service for generating analysis reports in various formats."""
    
    def __init__(self, app: Optional[Flask] = None):
        """Initialize the report generation service."""
        self.app = app
        self._reports_dir: Optional[Path] = None
        
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
            report_type: Type of report ('model_analysis', 'app_analysis', 'tool_analysis')
            format: Output format ('html' or 'json')
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
        """Generate the actual report content based on type using appropriate generator."""
        try:
            report.mark_generating()
            db.session.commit()
            
            config = report.get_config()
            
            # Route to appropriate generator
            generator = self._route_to_generator(report.report_type, config)
            
            # Validate configuration
            generator.validate_config()
            
            report.update_progress(20)
            db.session.commit()
            
            # Collect data
            data = generator.collect_data()
            
            report.update_progress(60)
            db.session.commit()
            
            # Generate output file
            file_path = self._render_report(report, data, generator)
            
            # Get file size
            abs_path = self.reports_dir / file_path
            file_size = abs_path.stat().st_size
            
            # Update report
            report.mark_completed(str(file_path), file_size)
            
            # Store summary
            summary = generator.generate_summary(data)
            report.set_summary(summary)
            
            db.session.commit()
            
            logger.info(f"Report {report.report_id} generated successfully: {file_path}")
            
        except Exception as e:
            logger.error(f"Error generating report content: {e}", exc_info=True)
            report.mark_failed(str(e))
            db.session.commit()
            raise
    
    def _route_to_generator(self, report_type: str, config: Dict[str, Any]):
        """Route to appropriate generator based on report type."""
        if report_type == 'model_analysis':
            return ModelReportGenerator(config, self.reports_dir)
        elif report_type == 'app_analysis':
            return AppReportGenerator(config, self.reports_dir)
        elif report_type == 'tool_analysis':
            return ToolReportGenerator(config, self.reports_dir)
        else:
            raise ValidationError(f"Unknown report type: {report_type}")
    
    def _render_report(self, report: Report, data: Dict[str, Any], generator) -> str:
        """
        Render report using Jinja2 template or JSON export.
        
        Returns:
            Relative file path from reports directory
        """
        # Create report type subdirectory
        report_type_dir = self.reports_dir / report.report_type
        report_type_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_filename = f"{report.report_id}_{timestamp}"
        
        if report.format == 'json':
            # JSON export
            filename = f"{base_filename}.json"
            file_path = report_type_dir / filename
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            relative_path = Path(report.report_type) / filename
            return str(relative_path)
        
        elif report.format == 'html':
            # HTML using Jinja2 template
            template_name = f"pages/reports/{generator.get_template_name()}"
            
            try:
                # Render template in a test request context so url_for() works
                from flask import current_app
                with current_app.test_request_context():
                    html_content = render_template(template_name, **data)
            except Exception as e:
                logger.error(f"Error rendering template {template_name}: {e}")
                raise ServiceError(f"Failed to render template: {e}")
            
            filename = f"{base_filename}.html"
            file_path = report_type_dir / filename
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            relative_path = Path(report.report_type) / filename
            return str(relative_path)
        
        else:
            raise ValidationError(f"Unsupported format: {report.format}")
    
    def _generate_title(self, report_type: ReportType, config: Dict[str, Any]) -> str:
        """Generate a default title based on report type and config."""
        if report_type == 'model_analysis':
            model = config.get('model_slug', 'unknown')
            return f"Model Analysis Report: {model}"
        
        elif report_type == 'app_analysis':
            app = config.get('app_number', 'unknown')
            return f"App Comparison Report: App #{app}"
        
        elif report_type == 'tool_analysis':
            tool = config.get('tool_name', 'All Tools')
            return f"Tool Analysis Report: {tool}"
        
        return "Analysis Report"
    
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
