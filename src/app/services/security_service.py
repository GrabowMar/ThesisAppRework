"""
Security Analysis Service for Celery App

Provides security analysis functionality for AI-generated applications.
Integrates with containerized security scanners and provides fallback analysis.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pathlib import Path

from ..models import SecurityAnalysis, GeneratedApplication
from ..constants import AnalysisStatus
from ..extensions import get_session

logger = logging.getLogger(__name__)


class SecurityService:
    """Service for managing security analysis operations."""
    
    def __init__(self):
        self.logger = logger
        self.active_scans: Dict[str, Dict[str, Any]] = {}
        self.project_root = Path(__file__).parent.parent.parent.parent
        self.models_dir = self.project_root / "misc" / "models"
    
    def start_security_analysis(self, model_slug: str, app_number: int, 
                               tools: Optional[List[str]] = None, 
                               options: Optional[Dict[str, Any]] = None) -> str:
        """Start a security analysis for a specific application."""
        
        # Generate unique scan ID
        scan_id = str(uuid.uuid4())
        
        # Default tools if not specified
        if not tools:
            tools = ['bandit', 'safety', 'pylint']
        
        # Create database record
        try:
            with get_session() as session:
                # Get or create application record
                app = session.query(GeneratedApplication).filter_by(
                    model_slug=model_slug,
                    app_number=app_number
                ).first()
                
                if not app:
                    # Create application record if it doesn't exist
                    app = GeneratedApplication()
                    app.model_slug = model_slug
                    app.app_number = app_number
                    app.app_type = 'web_application'
                    app.provider = self._extract_provider(model_slug)
                    session.add(app)
                    session.flush()  # Get the ID
                
                # Create security analysis record
                analysis = SecurityAnalysis()
                analysis.application_id = app.id
                analysis.status = AnalysisStatus.PENDING
                analysis.bandit_enabled = 'bandit' in tools
                analysis.safety_enabled = 'safety' in tools
                analysis.pylint_enabled = 'pylint' in tools
                analysis.eslint_enabled = 'eslint' in tools
                analysis.npm_audit_enabled = 'npm_audit' in tools
                analysis.started_at = datetime.now(timezone.utc)
                
                if options:
                    analysis.set_metadata(options)
                
                session.add(analysis)
                session.commit()
                
                # Store scan info
                self.active_scans[scan_id] = {
                    'analysis_id': analysis.id,
                    'model_slug': model_slug,
                    'app_number': app_number,
                    'tools': tools,
                    'status': AnalysisStatus.PENDING,
                    'started_at': datetime.now(timezone.utc)
                }
                
                self.logger.info(f"Started security analysis {scan_id} for {model_slug}/app{app_number}")
                return scan_id
        
        except Exception as e:
            self.logger.error(f"Failed to start security analysis: {e}")
            raise
    
    def get_analysis_status(self, scan_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a security analysis."""
        scan_info = self.active_scans.get(scan_id)
        if not scan_info:
            return None
        
        try:
            with get_session() as session:
                analysis = session.query(SecurityAnalysis).get(scan_info['analysis_id'])
                if analysis:
                    return {
                        'scan_id': scan_id,
                        'status': analysis.status.value,
                        'model_slug': scan_info['model_slug'],
                        'app_number': scan_info['app_number'],
                        'tools': scan_info['tools'],
                        'started_at': analysis.started_at.isoformat() if analysis.started_at else None,
                        'completed_at': analysis.completed_at.isoformat() if analysis.completed_at else None,
                        'total_issues': analysis.total_issues,
                        'critical_count': analysis.critical_severity_count,
                        'high_count': analysis.high_severity_count,
                        'medium_count': analysis.medium_severity_count,
                        'low_count': analysis.low_severity_count,
                        'duration': analysis.analysis_duration
                    }
        except Exception as e:
            self.logger.error(f"Failed to get analysis status: {e}")
        
        return None
    
    def update_analysis_progress(self, scan_id: str, status: AnalysisStatus, 
                               results: Optional[Dict[str, Any]] = None):
        """Update the progress of a security analysis."""
        scan_info = self.active_scans.get(scan_id)
        if not scan_info:
            return
        
        try:
            with get_session() as session:
                analysis = session.query(SecurityAnalysis).get(scan_info['analysis_id'])
                if analysis:
                    analysis.status = status
                    
                    if status == AnalysisStatus.COMPLETED:
                        analysis.completed_at = datetime.now(timezone.utc)
                        
                        if analysis.started_at:
                            duration = (analysis.completed_at - analysis.started_at).total_seconds()
                            analysis.analysis_duration = duration
                        
                        if results:
                            analysis.set_results(results)
                            
                            # Update issue counts
                            issues = results.get('issues', [])
                            analysis.total_issues = len(issues)
                            
                            # Count by severity
                            severity_counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
                            for issue in issues:
                                severity = issue.get('severity', 'low').lower()
                                if severity in severity_counts:
                                    severity_counts[severity] += 1
                            
                            analysis.critical_severity_count = severity_counts['critical']
                            analysis.high_severity_count = severity_counts['high']
                            analysis.medium_severity_count = severity_counts['medium']
                            analysis.low_severity_count = severity_counts['low']
                    
                    session.commit()
                    
                    # Update local tracking
                    scan_info['status'] = status
                    
                    self.logger.info(f"Updated security analysis {scan_id} status to {status.value}")
        
        except Exception as e:
            self.logger.error(f"Failed to update analysis progress: {e}")
    
    def get_analysis_results(self, scan_id: str) -> Optional[Dict[str, Any]]:
        """Get the results of a completed security analysis."""
        scan_info = self.active_scans.get(scan_id)
        if not scan_info:
            return None
        
        try:
            with get_session() as session:
                analysis = session.query(SecurityAnalysis).get(scan_info['analysis_id'])
                if analysis and analysis.status == AnalysisStatus.COMPLETED:
                    return analysis.get_results()
        except Exception as e:
            self.logger.error(f"Failed to get analysis results: {e}")
        
        return None
    
    def list_analyses(self, model_slug: Optional[str] = None, 
                     app_number: Optional[int] = None,
                     status: Optional[AnalysisStatus] = None) -> List[Dict[str, Any]]:
        """List security analyses with optional filtering."""
        try:
            with get_session() as session:
                query = session.query(SecurityAnalysis).join(GeneratedApplication)
                
                if model_slug:
                    query = query.filter(GeneratedApplication.model_slug == model_slug)
                if app_number:
                    query = query.filter(GeneratedApplication.app_number == app_number)
                if status:
                    query = query.filter(SecurityAnalysis.status == status)
                
                analyses = query.order_by(SecurityAnalysis.created_at.desc()).all()
                
                results = []
                for analysis in analyses:
                    # Get application info
                    app = session.query(GeneratedApplication).get(analysis.application_id)
                    if app:
                        results.append({
                            'id': analysis.id,
                            'model_slug': app.model_slug,
                            'app_number': app.app_number,
                            'status': analysis.status.value,
                            'total_issues': analysis.total_issues,
                            'critical_count': analysis.critical_severity_count,
                            'high_count': analysis.high_severity_count,
                            'medium_count': analysis.medium_severity_count,
                            'low_count': analysis.low_severity_count,
                            'started_at': analysis.started_at.isoformat() if analysis.started_at else None,
                            'completed_at': analysis.completed_at.isoformat() if analysis.completed_at else None,
                            'duration': analysis.analysis_duration
                        })
                
                return results
        
        except Exception as e:
            self.logger.error(f"Failed to list analyses: {e}")
            return []
    
    def get_analysis_summary(self) -> Dict[str, Any]:
        """Get summary statistics for security analyses."""
        try:
            with get_session() as session:
                total_analyses = session.query(SecurityAnalysis).count()
                completed_analyses = session.query(SecurityAnalysis).filter_by(
                    status=AnalysisStatus.COMPLETED
                ).count()
                failed_analyses = session.query(SecurityAnalysis).filter_by(
                    status=AnalysisStatus.FAILED
                ).count()
                running_analyses = session.query(SecurityAnalysis).filter_by(
                    status=AnalysisStatus.RUNNING
                ).count()
                
                # Get total issues from completed analyses
                completed = session.query(SecurityAnalysis).filter_by(
                    status=AnalysisStatus.COMPLETED
                ).all()
                
                total_issues = sum(a.total_issues for a in completed)
                total_critical = sum(a.critical_severity_count for a in completed)
                total_high = sum(a.high_severity_count for a in completed)
                total_medium = sum(a.medium_severity_count for a in completed)
                total_low = sum(a.low_severity_count for a in completed)
                
                return {
                    'total_analyses': total_analyses,
                    'completed_analyses': completed_analyses,
                    'failed_analyses': failed_analyses,
                    'running_analyses': running_analyses,
                    'pending_analyses': total_analyses - completed_analyses - failed_analyses - running_analyses,
                    'total_issues': total_issues,
                    'critical_issues': total_critical,
                    'high_issues': total_high,
                    'medium_issues': total_medium,
                    'low_issues': total_low
                }
        
        except Exception as e:
            self.logger.error(f"Failed to get analysis summary: {e}")
            return {}
    
    def cleanup_old_scans(self, max_age_hours: int = 24) -> int:
        """Clean up old scan records from memory."""
        from datetime import timedelta
        
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        removed_count = 0
        
        scans_to_remove = []
        for scan_id, scan_info in self.active_scans.items():
            if scan_info['started_at'] < cutoff_time:
                scans_to_remove.append(scan_id)
        
        for scan_id in scans_to_remove:
            del self.active_scans[scan_id]
            removed_count += 1
        
        self.logger.info(f"Cleaned up {removed_count} old scan records")
        return removed_count
    
    def _extract_provider(self, model_slug: str) -> str:
        """Extract provider name from model slug."""
        if model_slug.startswith('anthropic'):
            return 'anthropic'
        elif model_slug.startswith('openai'):
            return 'openai'
        elif model_slug.startswith('google'):
            return 'google'
        elif model_slug.startswith('meta'):
            return 'meta'
        elif model_slug.startswith('microsoft'):
            return 'microsoft'
        else:
            return 'unknown'
    
    def _get_app_path(self, model_slug: str, app_number: int) -> Path:
        """Get the filesystem path for an application."""
        return self.models_dir / model_slug / f"app{app_number}"
    
    def _check_app_exists(self, model_slug: str, app_number: int) -> bool:
        """Check if an application exists on the filesystem."""
        app_path = self._get_app_path(model_slug, app_number)
        return app_path.exists() and app_path.is_dir()


# Global instance
security_service = SecurityService()
