"""
Analysis Orchestrator Service
============================

High-level orchestration service that coordinates all analysis operations.
Acts as the main entry point for analysis workflows.
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone
from enum import Enum

from ..extensions import db
from ..models import (
    AnalysisTask, BatchAnalysis, AnalyzerConfiguration,
    AnalysisStatus, AnalysisType, Priority, BatchStatus
)
from .new_task_service import (
    AnalysisTaskService, BatchAnalysisService, queue_service
)
from .new_analyzer_service import (
    analyzer_config_service, analyzer_manager_service
)
from .new_batch_service import (
    batch_template_service, batch_validation_service, batch_execution_service
)
from .new_results_service import (
    results_query_service, results_aggregation_service
)


logger = logging.getLogger(__name__)


class WorkflowType(Enum):
    """Types of analysis workflows."""
    SINGLE_ANALYSIS = "single_analysis"
    BATCH_ANALYSIS = "batch_analysis"
    COMPREHENSIVE_ANALYSIS = "comprehensive_analysis"
    SCHEDULED_ANALYSIS = "scheduled_analysis"


class AnalysisOrchestrator:
    """Main orchestrator for all analysis operations."""
    
    def __init__(self):
        self.task_service = AnalysisTaskService()
        self.batch_service = BatchAnalysisService()
        self.queue_service = queue_service
        self.config_service = analyzer_config_service
        self.manager_service = analyzer_manager_service
        
    # ========================================================================
    # Single Analysis Operations
    # ========================================================================
    
    def start_single_analysis(
        self,
        model_slug: str,
        app_number: int,
        analysis_type: str,
        config_id: Optional[str] = None,
        priority: str = Priority.NORMAL.value,
        custom_options: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Start a single analysis with full validation and setup."""
        try:
            logger.info(f"Starting {analysis_type} analysis for {model_slug} app {app_number}")
            
            # Validate the request
            is_valid, message, config = self.manager_service.validate_analysis_request(
                analyzer_type=analysis_type,
                model_slug=model_slug,
                app_number=app_number,
                config_id=config_id
            )
            
            if not is_valid:
                return {
                    'success': False,
                    'error': message,
                    'error_type': 'validation_error'
                }
            
            # Check system capacity
            queue_status = self.queue_service.get_queue_status()
            if queue_status['available_slots'] <= 0:
                return {
                    'success': False,
                    'error': 'System is at capacity. Please try again later.',
                    'error_type': 'capacity_error',
                    'queue_status': queue_status
                }
            
            # Create the task
            task = self.task_service.create_task(
                model_slug=model_slug,
                app_number=app_number,
                analysis_type=analysis_type,
                config_id=config_id,
                priority=priority,
                custom_options=custom_options
            )
            
            # Add user context if provided
            if user_id:
                metadata = task.get_metadata()
                metadata['user_id'] = user_id
                metadata['initiated_at'] = datetime.now(timezone.utc).isoformat()
                task.set_metadata(metadata)
                db.session.commit()
            
            # Queue the task for execution
            self._queue_task_for_execution(task)
            
            logger.info(f"Created and queued analysis task {task.task_id}")
            
            return {
                'success': True,
                'task_id': task.task_id,
                'task': task.to_dict(),
                'estimated_completion': self._estimate_completion_time(task),
                'queue_position': self._get_queue_position(task)
            }
            
        except Exception as e:
            logger.error(f"Failed to start single analysis: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_type': 'system_error'
            }
    
    def start_comprehensive_analysis(
        self,
        model_slug: str,
        app_number: int,
        analysis_types: Optional[List[str]] = None,
        priority: str = Priority.NORMAL.value,
        custom_options: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Start comprehensive analysis with multiple analysis types."""
        try:
            if not analysis_types:
                # Default comprehensive analysis types
                analysis_types = [
                    AnalysisType.SECURITY.value,
                    AnalysisType.STATIC.value,
                    AnalysisType.PERFORMANCE.value
                ]
            
            logger.info(f"Starting comprehensive analysis for {model_slug} app {app_number}")
            
            # Check capacity for multiple tasks
            queue_status = self.queue_service.get_queue_status()
            if queue_status['available_slots'] < len(analysis_types):
                return {
                    'success': False,
                    'error': f'Insufficient capacity for {len(analysis_types)} analyses. Available slots: {queue_status["available_slots"]}',
                    'error_type': 'capacity_error'
                }
            
            # Create tasks for each analysis type
            tasks = []
            failed_tasks = []
            
            for analysis_type in analysis_types:
                try:
                    result = self.start_single_analysis(
                        model_slug=model_slug,
                        app_number=app_number,
                        analysis_type=analysis_type,
                        priority=priority,
                        custom_options=custom_options,
                        user_id=user_id
                    )
                    
                    if result['success']:
                        tasks.append(result['task'])
                    else:
                        failed_tasks.append({
                            'analysis_type': analysis_type,
                            'error': result['error']
                        })
                        
                except Exception as e:
                    failed_tasks.append({
                        'analysis_type': analysis_type,
                        'error': str(e)
                    })
            
            if not tasks:
                return {
                    'success': False,
                    'error': 'Failed to create any analysis tasks',
                    'failed_tasks': failed_tasks,
                    'error_type': 'creation_error'
                }
            
            return {
                'success': True,
                'workflow_type': WorkflowType.COMPREHENSIVE_ANALYSIS.value,
                'tasks': tasks,
                'failed_tasks': failed_tasks,
                'total_tasks': len(tasks),
                'estimated_completion': max(
                    self._estimate_completion_time_from_dict(task) for task in tasks
                ) if tasks else None
            }
            
        except Exception as e:
            logger.error(f"Failed to start comprehensive analysis: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_type': 'system_error'
            }
    
    # ========================================================================
    # Batch Analysis Operations
    # ========================================================================
    
    def create_batch_analysis(
        self,
        name: str,
        description: str,
        analysis_types: List[str],
        target_models: List[str],
        target_apps: List[int],
        template_name: Optional[str] = None,
        priority: str = Priority.NORMAL.value,
        config: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        start_immediately: bool = False
    ) -> Dict[str, Any]:
        """Create and optionally start a batch analysis."""
        try:
            logger.info(f"Creating batch analysis: {name}")
            
            # Use template if specified
            if template_name:
                template = batch_template_service.get_template(template_name)
                if template:
                    if not analysis_types:
                        analysis_types = template.analysis_types
                    if not config:
                        config = template.default_config.copy()
            
            # Validate batch configuration
            is_valid, errors = batch_validation_service.validate_batch_config(
                name=name,
                analysis_types=analysis_types,
                target_models=target_models,
                target_apps=target_apps,
                config=config or {}
            )
            
            if not is_valid:
                return {
                    'success': False,
                    'error': 'Batch validation failed',
                    'validation_errors': errors,
                    'error_type': 'validation_error'
                }
            
            # Get execution estimate
            estimate = batch_validation_service.estimate_batch_execution(
                analysis_types=analysis_types,
                target_models=target_models,
                target_apps=target_apps,
                config=config or {}
            )
            
            # Create the batch
            batch = self.batch_service.create_batch(
                name=name,
                description=description,
                analysis_types=analysis_types,
                target_models=target_models,
                target_apps=target_apps,
                priority=priority,
                config=config or {}
            )
            
            # Add user context
            if user_id:
                metadata = batch.get_metadata()
                metadata['user_id'] = user_id
                metadata['created_by'] = user_id
                metadata['template_used'] = template_name
                batch.set_metadata(metadata)
                db.session.commit()
            
            result = {
                'success': True,
                'batch_id': batch.batch_id,
                'batch': batch.to_dict(),
                'estimate': estimate,
                'workflow_type': WorkflowType.BATCH_ANALYSIS.value
            }
            
            # Start immediately if requested
            if start_immediately:
                start_result = self.start_batch_analysis(batch.batch_id, user_id=user_id)
                result['start_result'] = start_result
            
            logger.info(f"Created batch analysis {batch.batch_id} with {estimate['total_tasks']} tasks")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to create batch analysis: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_type': 'system_error'
            }
    
    def start_batch_analysis(
        self,
        batch_id: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Start execution of a batch analysis."""
        try:
            logger.info(f"Starting batch analysis {batch_id}")
            
            # Get the batch
            batch = self.batch_service.get_batch(batch_id)
            if not batch:
                return {
                    'success': False,
                    'error': 'Batch not found',
                    'error_type': 'not_found'
                }
            
            if batch.status != BatchStatus.CREATED.value:
                return {
                    'success': False,
                    'error': f'Batch cannot be started from status: {batch.status}',
                    'error_type': 'invalid_state'
                }
            
            # Check system capacity
            total_tasks = batch.total_tasks or len(batch.get_target_models()) * len(batch.get_target_apps()) * len(batch.get_analysis_types())
            queue_status = self.queue_service.get_queue_status()
            
            if queue_status['total_pending'] + total_tasks > 1000:  # System limit
                return {
                    'success': False,
                    'error': 'Adding this batch would exceed system limits',
                    'error_type': 'capacity_error',
                    'queue_status': queue_status
                }
            
            # Start the batch execution
            execution_result = batch_execution_service.execute_batch(
                batch_id=batch_id,
                async_execution=True
            )
            
            # Update metadata
            if user_id:
                metadata = batch.get_metadata()
                metadata['started_by'] = user_id
                metadata['started_at'] = datetime.now(timezone.utc).isoformat()
                batch.set_metadata(metadata)
                db.session.commit()
            
            logger.info(f"Started batch analysis {batch_id}")
            
            return {
                'success': True,
                'batch_id': batch_id,
                'execution_result': execution_result,
                'message': 'Batch analysis started successfully'
            }
            
        except Exception as e:
            logger.error(f"Failed to start batch analysis {batch_id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_type': 'system_error'
            }
    
    # ========================================================================
    # Task and Queue Management
    # ========================================================================
    
    def get_analysis_status(
        self,
        task_id: Optional[str] = None,
        batch_id: Optional[str] = None,
        include_details: bool = False
    ) -> Dict[str, Any]:
        """Get status of analysis task or batch."""
        try:
            if task_id:
                task_data = results_query_service.get_task_results(
                    task_id, include_detailed_results=include_details
                )
                if not task_data:
                    return {
                        'success': False,
                        'error': 'Task not found',
                        'error_type': 'not_found'
                    }
                
                return {
                    'success': True,
                    'type': 'task',
                    'data': task_data
                }
            
            elif batch_id:
                batch_data = results_query_service.get_batch_results(
                    batch_id, include_task_details=include_details
                )
                if not batch_data:
                    return {
                        'success': False,
                        'error': 'Batch not found',
                        'error_type': 'not_found'
                    }
                
                return {
                    'success': True,
                    'type': 'batch',
                    'data': batch_data
                }
            
            else:
                return {
                    'success': False,
                    'error': 'Either task_id or batch_id must be provided',
                    'error_type': 'validation_error'
                }
                
        except Exception as e:
            logger.error(f"Failed to get analysis status: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_type': 'system_error'
            }
    
    def cancel_analysis(
        self,
        task_id: Optional[str] = None,
        batch_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Cancel analysis task or batch."""
        try:
            if task_id:
                task = self.task_service.cancel_task(task_id)
                if not task:
                    return {
                        'success': False,
                        'error': 'Task not found or cannot be cancelled',
                        'error_type': 'not_found'
                    }
                
                # Add cancellation metadata
                if user_id:
                    metadata = task.get_metadata()
                    metadata['cancelled_by'] = user_id
                    metadata['cancelled_at'] = datetime.now(timezone.utc).isoformat()
                    task.set_metadata(metadata)
                    db.session.commit()
                
                logger.info(f"Cancelled task {task_id}")
                
                return {
                    'success': True,
                    'type': 'task',
                    'task_id': task_id,
                    'message': 'Task cancelled successfully'
                }
            
            elif batch_id:
                result = batch_execution_service.cancel_batch_execution(batch_id)
                
                # Add cancellation metadata
                if user_id:
                    batch = self.batch_service.get_batch(batch_id)
                    if batch:
                        metadata = batch.get_metadata()
                        metadata['cancelled_by'] = user_id
                        metadata['cancelled_at'] = datetime.now(timezone.utc).isoformat()
                        batch.set_metadata(metadata)
                        db.session.commit()
                
                logger.info(f"Cancelled batch {batch_id}")
                
                return {
                    'success': True,
                    'type': 'batch',
                    'batch_id': batch_id,
                    'result': result,
                    'message': 'Batch cancelled successfully'
                }
            
            else:
                return {
                    'success': False,
                    'error': 'Either task_id or batch_id must be provided',
                    'error_type': 'validation_error'
                }
                
        except Exception as e:
            logger.error(f"Failed to cancel analysis: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_type': 'system_error'
            }
    
    def get_system_overview(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Get comprehensive system overview."""
        try:
            # Get basic system data
            system_data = self.manager_service.get_system_overview()
            queue_status = self.queue_service.get_queue_status()
            dashboard_data = results_aggregation_service.get_dashboard_summary()
            
            # Get user-specific data if user_id provided
            user_data = {}
            if user_id:
                user_data = self._get_user_analysis_summary(user_id)
            
            # Get recent activity
            recent_tasks = self.task_service.get_recent_tasks(limit=10)
            recent_batches = self.batch_service.list_batches(limit=5)
            
            return {
                'success': True,
                'system_data': system_data,
                'queue_status': queue_status,
                'dashboard_data': dashboard_data,
                'user_data': user_data,
                'recent_activity': {
                    'tasks': [task.to_dict() for task in recent_tasks],
                    'batches': [batch.to_dict() for batch in recent_batches]
                },
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get system overview: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_type': 'system_error'
            }
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
    def _queue_task_for_execution(self, task: AnalysisTask) -> None:
        """Queue a task for execution (placeholder for actual queuing)."""
        # In a real implementation, this would integrate with Celery or another task queue
        # For now, we just mark it as queued
        task.status = AnalysisStatus.QUEUED.value
        task.queued_at = datetime.now(timezone.utc)
        db.session.commit()
    
    def _estimate_completion_time(self, task: AnalysisTask) -> Optional[str]:
        """Estimate task completion time."""
        if task.estimated_duration:
            estimated_completion = datetime.now(timezone.utc)
            estimated_completion = estimated_completion.replace(
                second=estimated_completion.second + task.estimated_duration
            )
            return estimated_completion.isoformat()
        return None
    
    def _estimate_completion_time_from_dict(self, task_dict: Dict[str, Any]) -> Optional[str]:
        """Estimate completion time from task dictionary."""
        estimated_duration = task_dict.get('estimated_duration')
        if estimated_duration:
            estimated_completion = datetime.now(timezone.utc)
            estimated_completion = estimated_completion.replace(
                second=estimated_completion.second + estimated_duration
            )
            return estimated_completion.isoformat()
        return None
    
    def _get_queue_position(self, task: AnalysisTask) -> int:
        """Get approximate queue position for a task."""
        # Count pending tasks with higher or equal priority created before this task
        from sqlalchemy import and_
        
        priority_order = {'critical': 4, 'high': 3, 'normal': 2, 'low': 1}
        task_priority = priority_order.get(task.priority, 2)
        
        position = AnalysisTask.query.filter(
            and_(
                AnalysisTask.status == AnalysisStatus.PENDING.value,
                AnalysisTask.created_at <= task.created_at,
                AnalysisTask.id != task.id
            )
        ).filter(
            # This is a simplified priority check
            AnalysisTask.priority.in_(['critical', 'high', 'normal', 'low'])
        ).count()
        
        return position + 1
    
    def _get_user_analysis_summary(self, user_id: str) -> Dict[str, Any]:
        """Get analysis summary for a specific user."""
        try:
            # This would query tasks and batches created by the user
            # For now, return mock data
            return {
                'total_analyses': 0,
                'active_analyses': 0,
                'completed_analyses': 0,
                'failed_analyses': 0,
                'total_batches': 0,
                'active_batches': 0
            }
        except Exception as e:
            logger.error(f"Failed to get user analysis summary: {e}")
            return {}


# Initialize singleton instance
analysis_orchestrator = AnalysisOrchestrator()



