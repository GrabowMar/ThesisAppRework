"""
Analysis Service
===============

High-level service for managing security analyses and performance tests.
Provides creation, retrieval, and execution management for analysis operations.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

from ..extensions import db
from ..models import (
    GeneratedApplication, SecurityAnalysis, PerformanceTest
)
from ..constants import AnalysisStatus
from .task_service import AnalysisTaskService


logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when analysis validation fails."""
    pass


class InvalidStateError(Exception):
    """Raised when analysis state transition is invalid."""
    pass


class NotFoundError(Exception):
    """Raised when analysis or application is not found."""
    pass


class AnalysisService:
    """Service for managing security analyses and performance tests."""

    def __init__(self):
        self.task_service = AnalysisTaskService()

    def create_security_analysis(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new security analysis."""
        if 'application_id' not in data:
            raise ValidationError("application_id is required")

        application = GeneratedApplication.query.get(data['application_id'])
        if not application:
            raise NotFoundError(f"Application {data['application_id']} not found")

        analysis_name = data.get('analysis_name', 'Security Analysis')

        # Check for existing analysis
        existing = SecurityAnalysis.query.filter_by(
            application_id=data['application_id'],
            analysis_name=analysis_name
        ).first()

        if existing:
            # Return existing analysis
            return existing.to_dict()

        # Create new analysis
        analysis = SecurityAnalysis(
            application_id=data['application_id'],
            analysis_name=analysis_name,
            status=AnalysisStatus.PENDING.value
        )

        db.session.add(analysis)
        db.session.commit()

        logger.info(f"Created security analysis {analysis.id} for application {data['application_id']}")
        return analysis.to_dict()

    def create_performance_test(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new performance test."""
        if 'application_id' not in data:
            raise ValidationError("application_id is required")

        if 'test_type' not in data:
            raise ValidationError("test_type is required")

        application = GeneratedApplication.query.get(data['application_id'])
        if not application:
            raise NotFoundError(f"Application {data['application_id']} not found")

        # Create new performance test
        test = PerformanceTest(
            application_id=data['application_id'],
            test_type=data['test_type'],
            status=AnalysisStatus.PENDING.value
        )

        db.session.add(test)
        db.session.commit()

        logger.info(f"Created performance test {test.id} for application {data['application_id']}")
        return test.to_dict()

    def list_security_analyses(self, application_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """List security analyses, optionally filtered by application."""
        query = SecurityAnalysis.query
        if application_id:
            query = query.filter_by(application_id=application_id)

        analyses = query.order_by(SecurityAnalysis.created_at.desc()).all()
        return [analysis.to_dict() for analysis in analyses]

    def get_security_analysis(self, analysis_id: int) -> Dict[str, Any]:
        """Get a specific security analysis."""
        analysis = SecurityAnalysis.query.get(analysis_id)
        if not analysis:
            raise NotFoundError(f"Security analysis {analysis_id} not found")

        return analysis.to_dict()

    def list_performance_tests(self, application_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """List performance tests, optionally filtered by application."""
        query = PerformanceTest.query
        if application_id:
            query = query.filter_by(application_id=application_id)

        tests = query.order_by(PerformanceTest.created_at.desc()).all()
        return [test.to_dict() for test in tests]

    def get_performance_test(self, test_id: int) -> Dict[str, Any]:
        """Get a specific performance test."""
        test = PerformanceTest.query.get(test_id)
        if not test:
            raise NotFoundError(f"Performance test {test_id} not found")

        return test.to_dict()

    def start_security_analysis(self, analysis_id: int) -> Dict[str, Any]:
        """Start a security analysis."""
        analysis = SecurityAnalysis.query.get(analysis_id)
        if not analysis:
            raise NotFoundError(f"Security analysis {analysis_id} not found")

        if analysis.status != AnalysisStatus.PENDING.value:
            raise InvalidStateError(f"Cannot start analysis in status: {analysis.status}")

        # Update status
        analysis.status = AnalysisStatus.RUNNING.value
        analysis.started_at = datetime.now(timezone.utc)
        db.session.commit()

        # Create analysis task
        task = self.task_service.create_task(
            model_slug=analysis.application.model_slug,
            app_number=analysis.application.app_number,
            analysis_type='security'
        )

        logger.info(f"Started security analysis {analysis_id}, task {task.task_id}")
        return {
            'status': analysis.status,
            'task_id': task.task_id,
            'started_at': analysis.started_at.isoformat()
        }

    def start_performance_test(self, test_id: int) -> Dict[str, Any]:
        """Start a performance test."""
        test = PerformanceTest.query.get(test_id)
        if not test:
            raise NotFoundError(f"Performance test {test_id} not found")

        if test.status != AnalysisStatus.PENDING.value:
            raise InvalidStateError(f"Cannot start test in status: {test.status}")

        # Update status
        test.status = AnalysisStatus.RUNNING.value
        test.started_at = datetime.now(timezone.utc)
        db.session.commit()

        # Create analysis task
        task = self.task_service.create_task(
            model_slug=test.application.model_slug,
            app_number=test.application.app_number,
            analysis_type='performance'
        )

        logger.info(f"Started performance test {test_id}, task {task.task_id}")
        return {
            'status': test.status,
            'task_id': task.task_id,
            'started_at': test.started_at.isoformat()
        }

    def start_comprehensive_analysis(self, application_id: int) -> Dict[str, Any]:
        """Start comprehensive analysis (security + performance)."""
        application = GeneratedApplication.query.get(application_id)
        if not application:
            raise NotFoundError(f"Application {application_id} not found")

        # Create security analysis
        security_data = self.create_security_analysis({
            'application_id': application_id,
            'analysis_name': 'Comprehensive Security Analysis'
        })

        # Create performance test
        performance_data = self.create_performance_test({
            'application_id': application_id,
            'test_type': 'comprehensive'
        })

        # Start both
        security_result = self.start_security_analysis(security_data['id'])
        performance_result = self.start_performance_test(performance_data['id'])

        return {
            'status': AnalysisStatus.RUNNING.value,
            'security_analysis': security_data,
            'performance_test': performance_data,
            'security_task_id': security_result['task_id'],
            'performance_task_id': performance_result['task_id']
        }

    def get_analysis_results(self, analysis_id: int) -> Dict[str, Any]:
        """Get results for a security analysis."""
        analysis = SecurityAnalysis.query.get(analysis_id)
        if not analysis:
            raise NotFoundError(f"Security analysis {analysis_id} not found")

        results = analysis.get_results() or {}

        return {
            'id': analysis.id,
            'application_id': analysis.application_id,
            'analysis_name': analysis.analysis_name,
            'status': analysis.status,
            'created_at': analysis.created_at.isoformat() if analysis.created_at else None,
            'started_at': analysis.started_at.isoformat() if analysis.started_at else None,
            'completed_at': analysis.completed_at.isoformat() if analysis.completed_at else None,
            'summary': {
                'total_issues': analysis.total_issues or 0,
                'critical_severity_count': analysis.critical_severity_count or 0,
                'high_severity_count': analysis.high_severity_count or 0,
                'medium_severity_count': analysis.medium_severity_count or 0,
                'low_severity_count': analysis.low_severity_count or 0,
                'tools_run_count': analysis.tools_run_count or 0,
                'tools_failed_count': analysis.tools_failed_count or 0,
                'analysis_duration': analysis.analysis_duration or 0
            },
            'results': results
        }

    def get_recent_activity(self) -> Dict[str, Any]:
        """Get recent analysis activity."""
        # Get recent security analyses
        security_analyses = SecurityAnalysis.query.order_by(
            SecurityAnalysis.created_at.desc()
        ).limit(10).all()

        # Get recent performance tests
        performance_tests = PerformanceTest.query.order_by(
            PerformanceTest.created_at.desc()
        ).limit(10).all()

        return {
            'security': [analysis.to_dict() for analysis in security_analyses],
            'performance': [test.to_dict() for test in performance_tests]
        }


# Initialize singleton instance
analysis_service = AnalysisService()