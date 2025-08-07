"""
Celery Background Tasks for AI Testing Framework
==============================================

Asynchronous task implementations for long-running analysis operations.
"""

import json
import traceback
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from celery import Celery, current_task
from flask import Flask

try:
    from .celery_config import *
    from .models import (
        SecurityAnalysis, PerformanceTest, OpenRouterAnalysis,
        BatchJob, BatchTask, GeneratedApplication, db
    )
    from .constants import AnalysisStatus, TaskStatus, JobStatus
    from .service_manager import ServiceLocator
    from .extensions import get_session
    from .app import create_app
except ImportError:
    from celery_config import *
    from models import (
        SecurityAnalysis, PerformanceTest, OpenRouterAnalysis,
        BatchJob, BatchTask, GeneratedApplication, db
    )
    from constants import AnalysisStatus, TaskStatus, JobStatus
    from service_manager import ServiceLocator
    from extensions import get_session
    from app import create_app

# Create Celery instance
celery_app = Celery('testing_framework')
celery_app.config_from_object('src.celery_config')

# Flask app instance for database operations
flask_app = create_app()


def get_flask_app():
    """Get Flask app instance for task context."""
    return flask_app


def update_task_progress(task_id: str, current: int, total: int, status: str = None):
    """Update task progress with current/total and optional status."""
    progress_data = {
        'current': current,
        'total': total,
        'percentage': round((current / total) * 100, 2) if total > 0 else 0
    }
    if status:
        progress_data['status'] = status
    
    if current_task:
        current_task.update_state(
            state='PROGRESS',
            meta=progress_data
        )


@celery_app.task(bind=True, name='src.tasks.run_security_analysis_task')
def run_security_analysis_task(self, model_slug: str, app_number: int, tools: List[str], 
                               analysis_id: Optional[int] = None):
    """
    Background task for security analysis.
    
    Args:
        model_slug: Model identifier
        app_number: Application number
        tools: List of tools to run
        analysis_id: Existing analysis ID to update
    """
    app = get_flask_app()
    
    with app.app_context():
        try:
            # Update task status
            update_task_progress(self.request.id, 0, 100, "Initializing security analysis")
            
            # Get or create SecurityAnalysis record
            with get_session() as session:
                if analysis_id:
                    analysis = session.query(SecurityAnalysis).get(analysis_id)
                    if not analysis:
                        raise ValueError(f"Analysis {analysis_id} not found")
                else:
                    # Find application
                    app_record = session.query(GeneratedApplication).filter_by(
                        model_slug=model_slug, app_number=app_number
                    ).first()
                    
                    if not app_record:
                        raise ValueError(f"Application {model_slug} app{app_number} not found")
                    
                    # Create new analysis
                    analysis = SecurityAnalysis(
                        application_id=app_record.id,
                        status=AnalysisStatus.RUNNING,
                        started_at=datetime.now(timezone.utc)
                    )
                    session.add(analysis)
                    session.commit()
                    analysis_id = analysis.id
                
                # Update status to running
                analysis.status = AnalysisStatus.RUNNING
                analysis.started_at = datetime.now(timezone.utc)
                session.commit()
            
            # Get security service
            security_service = ServiceLocator.get_security_service()
            if not security_service:
                raise RuntimeError("Security service not available")
            
            update_task_progress(self.request.id, 10, 100, "Starting security scan")
            
            # Run security analysis
            results = security_service.run_analysis(model_slug, app_number, tools)
            
            update_task_progress(self.request.id, 80, 100, "Processing results")
            
            # Update database with results
            with get_session() as session:
                analysis = session.query(SecurityAnalysis).get(analysis_id)
                analysis.status = AnalysisStatus.COMPLETED
                analysis.completed_at = datetime.now(timezone.utc)
                analysis.results_json = json.dumps(results)
                
                # Update summary counts
                if 'summary' in results:
                    summary = results['summary']
                    analysis.total_issues = summary.get('total_issues', 0)
                    analysis.critical_severity_count = summary.get('critical', 0)
                    analysis.high_severity_count = summary.get('high', 0)
                    analysis.medium_severity_count = summary.get('medium', 0)
                    analysis.low_severity_count = summary.get('low', 0)
                
                session.commit()
            
            update_task_progress(self.request.id, 100, 100, "Analysis completed")
            
            return {
                'status': 'completed',
                'analysis_id': analysis_id,
                'results': results
            }
            
        except Exception as e:
            # Update analysis status to failed
            if analysis_id:
                with get_session() as session:
                    analysis = session.query(SecurityAnalysis).get(analysis_id)
                    if analysis:
                        analysis.status = AnalysisStatus.FAILED
                        analysis.completed_at = datetime.now(timezone.utc)
                        analysis.set_metadata({'error': str(e)})
                        session.commit()
            
            self.update_state(
                state='FAILURE',
                meta={'error': str(e), 'traceback': traceback.format_exc()}
            )
            raise


@celery_app.task(bind=True, name='src.tasks.run_performance_test_task')
def run_performance_test_task(self, model_slug: str, app_number: int, config: Dict[str, Any],
                              test_id: Optional[int] = None):
    """Background task for performance testing."""
    app = get_flask_app()
    
    with app.app_context():
        try:
            update_task_progress(self.request.id, 0, 100, "Initializing performance test")
            
            # Get or create PerformanceTest record
            with get_session() as session:
                if test_id:
                    test = session.query(PerformanceTest).get(test_id)
                    if not test:
                        raise ValueError(f"Performance test {test_id} not found")
                else:
                    # Find application
                    app_record = session.query(GeneratedApplication).filter_by(
                        model_slug=model_slug, app_number=app_number
                    ).first()
                    
                    if not app_record:
                        raise ValueError(f"Application {model_slug} app{app_number} not found")
                    
                    # Create new test
                    test = PerformanceTest(
                        application_id=app_record.id,
                        status=AnalysisStatus.RUNNING,
                        started_at=datetime.now(timezone.utc)
                    )
                    session.add(test)
                    session.commit()
                    test_id = test.id
                
                # Update status
                test.status = AnalysisStatus.RUNNING
                test.started_at = datetime.now(timezone.utc)
                session.commit()
            
            # Get performance service
            performance_service = ServiceLocator.get_performance_service()
            if not performance_service:
                raise RuntimeError("Performance service not available")
            
            update_task_progress(self.request.id, 10, 100, "Running performance test")
            
            # Run performance test
            results = performance_service.run_test(model_slug, app_number, config)
            
            update_task_progress(self.request.id, 90, 100, "Processing results")
            
            # Update database
            with get_session() as session:
                test = session.query(PerformanceTest).get(test_id)
                test.status = AnalysisStatus.COMPLETED
                test.completed_at = datetime.now(timezone.utc)
                test.results_json = json.dumps(results)
                session.commit()
            
            update_task_progress(self.request.id, 100, 100, "Test completed")
            
            return {
                'status': 'completed',
                'test_id': test_id,
                'results': results
            }
            
        except Exception as e:
            # Update test status to failed
            if test_id:
                with get_session() as session:
                    test = session.query(PerformanceTest).get(test_id)
                    if test:
                        test.status = AnalysisStatus.FAILED
                        test.completed_at = datetime.now(timezone.utc)
                        session.commit()
            
            self.update_state(
                state='FAILURE',
                meta={'error': str(e), 'traceback': traceback.format_exc()}
            )
            raise


@celery_app.task(bind=True, name='src.tasks.run_openrouter_analysis_task')
def run_openrouter_analysis_task(self, model_slug: str, app_number: int, 
                                  requirements: str = None, analysis_id: Optional[int] = None):
    """Background task for OpenRouter AI analysis."""
    app = get_flask_app()
    
    with app.app_context():
        try:
            update_task_progress(self.request.id, 0, 100, "Initializing AI analysis")
            
            # Get or create OpenRouterAnalysis record
            with get_session() as session:
                if analysis_id:
                    analysis = session.query(OpenRouterAnalysis).get(analysis_id)
                    if not analysis:
                        raise ValueError(f"Analysis {analysis_id} not found")
                else:
                    # Find application
                    app_record = session.query(GeneratedApplication).filter_by(
                        model_slug=model_slug, app_number=app_number
                    ).first()
                    
                    if not app_record:
                        raise ValueError(f"Application {model_slug} app{app_number} not found")
                    
                    # Create new analysis
                    analysis = OpenRouterAnalysis(
                        application_id=app_record.id,
                        status=AnalysisStatus.RUNNING,
                        started_at=datetime.now(timezone.utc)
                    )
                    session.add(analysis)
                    session.commit()
                    analysis_id = analysis.id
                
                # Update status
                analysis.status = AnalysisStatus.RUNNING
                analysis.started_at = datetime.now(timezone.utc)
                session.commit()
            
            # Get OpenRouter service
            openrouter_service = ServiceLocator.get_openrouter_service()
            if not openrouter_service:
                raise RuntimeError("OpenRouter service not available")
            
            update_task_progress(self.request.id, 20, 100, "Running AI analysis")
            
            # Run analysis
            results = openrouter_service.analyze_code(model_slug, app_number, requirements)
            
            update_task_progress(self.request.id, 90, 100, "Processing results")
            
            # Update database
            with get_session() as session:
                analysis = session.query(OpenRouterAnalysis).get(analysis_id)
                analysis.status = AnalysisStatus.COMPLETED
                analysis.completed_at = datetime.now(timezone.utc)
                analysis.results_json = json.dumps(results)
                session.commit()
            
            update_task_progress(self.request.id, 100, 100, "Analysis completed")
            
            return {
                'status': 'completed',
                'analysis_id': analysis_id,
                'results': results
            }
            
        except Exception as e:
            # Update analysis status to failed
            if analysis_id:
                with get_session() as session:
                    analysis = session.query(OpenRouterAnalysis).get(analysis_id)
                    if analysis:
                        analysis.status = AnalysisStatus.FAILED
                        analysis.completed_at = datetime.now(timezone.utc)
                        session.commit()
            
            self.update_state(
                state='FAILURE',
                meta={'error': str(e), 'traceback': traceback.format_exc()}
            )
            raise


@celery_app.task(bind=True, name='src.tasks.run_batch_analysis_task')
def run_batch_analysis_task(self, batch_job_id: int):
    """Background task for batch analysis coordination."""
    app = get_flask_app()
    
    with app.app_context():
        try:
            update_task_progress(self.request.id, 0, 100, "Initializing batch analysis")
            
            # Get batch job
            with get_session() as session:
                batch_job = session.query(BatchJob).get(batch_job_id)
                if not batch_job:
                    raise ValueError(f"Batch job {batch_job_id} not found")
                
                # Update status
                batch_job.status = JobStatus.RUNNING
                batch_job.started_at = datetime.now(timezone.utc)
                session.commit()
                
                # Get tasks
                tasks = session.query(BatchTask).filter_by(batch_job_id=batch_job_id).all()
            
            total_tasks = len(tasks)
            completed_tasks = 0
            
            # Execute tasks
            for task in tasks:
                try:
                    update_task_progress(
                        self.request.id, 
                        completed_tasks, 
                        total_tasks, 
                        f"Processing task {task.id}"
                    )
                    
                    # Update task status
                    with get_session() as session:
                        task_record = session.query(BatchTask).get(task.id)
                        task_record.status = TaskStatus.RUNNING
                        task_record.started_at = datetime.now(timezone.utc)
                        session.commit()
                    
                    # Execute based on task type
                    task_config = json.loads(task.task_config)
                    
                    if task.task_type == 'security_analysis':
                        result = run_security_analysis_task.delay(
                            task_config['model_slug'],
                            task_config['app_number'],
                            task_config.get('tools', [])
                        )
                    elif task.task_type == 'performance_test':
                        result = run_performance_test_task.delay(
                            task_config['model_slug'],
                            task_config['app_number'],
                            task_config.get('config', {})
                        )
                    elif task.task_type == 'openrouter_analysis':
                        result = run_openrouter_analysis_task.delay(
                            task_config['model_slug'],
                            task_config['app_number'],
                            task_config.get('requirements')
                        )
                    
                    # Wait for task completion
                    task_result = result.get(timeout=3600)  # 1 hour timeout
                    
                    # Update task with results
                    with get_session() as session:
                        task_record = session.query(BatchTask).get(task.id)
                        task_record.status = TaskStatus.COMPLETED
                        task_record.completed_at = datetime.now(timezone.utc)
                        task_record.results_json = json.dumps(task_result)
                        session.commit()
                    
                    completed_tasks += 1
                    
                except Exception as task_error:
                    # Mark task as failed
                    with get_session() as session:
                        task_record = session.query(BatchTask).get(task.id)
                        task_record.status = TaskStatus.FAILED
                        task_record.completed_at = datetime.now(timezone.utc)
                        task_record.set_metadata({'error': str(task_error)})
                        session.commit()
                    
                    completed_tasks += 1
            
            # Update batch job status
            with get_session() as session:
                batch_job = session.query(BatchJob).get(batch_job_id)
                batch_job.status = JobStatus.COMPLETED
                batch_job.completed_at = datetime.now(timezone.utc)
                session.commit()
            
            update_task_progress(self.request.id, 100, 100, "Batch analysis completed")
            
            return {
                'status': 'completed',
                'batch_job_id': batch_job_id,
                'completed_tasks': completed_tasks,
                'total_tasks': total_tasks
            }
            
        except Exception as e:
            # Update batch job status to failed
            with get_session() as session:
                batch_job = session.query(BatchJob).get(batch_job_id)
                if batch_job:
                    batch_job.status = JobStatus.FAILED
                    batch_job.completed_at = datetime.now(timezone.utc)
                    session.commit()
            
            self.update_state(
                state='FAILURE',
                meta={'error': str(e), 'traceback': traceback.format_exc()}
            )
            raise


@celery_app.task(name='src.tasks.cleanup_expired_results')
def cleanup_expired_results():
    """Periodic task to cleanup expired analysis results."""
    app = get_flask_app()
    
    with app.app_context():
        try:
            # Cleanup logic for expired results
            cleanup_count = 0
            
            # Add cleanup implementation here
            
            return {'cleaned_up': cleanup_count}
            
        except Exception as e:
            return {'error': str(e)}


@celery_app.task(name='src.tasks.health_check_containers')
def health_check_containers():
    """Periodic task to check container health."""
    app = get_flask_app()
    
    with app.app_context():
        try:
            docker_manager = ServiceLocator.get_docker_manager()
            if not docker_manager:
                return {'error': 'Docker manager not available'}
            
            status = docker_manager.get_infrastructure_status()
            
            return {
                'status': 'completed',
                'infrastructure_status': status.to_dict() if hasattr(status, 'to_dict') else str(status)
            }
            
        except Exception as e:
            return {'error': str(e)}


# Celery signal handlers
@celery_app.task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds):
    """Called before task execution."""
    pass


@celery_app.task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, 
                        retval=None, state=None, **kwds):
    """Called after task execution."""
    pass


if __name__ == '__main__':
    celery_app.start()
