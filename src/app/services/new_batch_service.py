"""
Advanced Batch Analysis Service
==============================

Comprehensive batch analysis functionality with advanced scheduling,
resource management, and intelligent task distribution.
"""

import logging
import uuid
import json
from typing import Dict, List, Optional, Any, Tuple, Set
from datetime import datetime, timezone, timedelta
from enum import Enum
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, Future
import asyncio
import threading

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc, func

from ..extensions import db
from ..models import (
    AnalysisTask, BatchAnalysis, AnalyzerConfiguration,
    AnalysisStatus, AnalysisType, Priority, BatchStatus
)
from .new_task_service import task_service, AnalysisTaskService
from .new_analyzer_service import analyzer_manager_service


logger = logging.getLogger(__name__)


@dataclass
class BatchTemplate:
    """Template for common batch analysis configurations."""
    name: str
    description: str
    analysis_types: List[str]
    default_config: Dict[str, Any]
    recommended_targets: Dict[str, Any]
    estimated_time_per_app: int  # seconds


class BatchTemplateService:
    """Service for managing batch analysis templates."""
    
    @staticmethod
    def get_default_templates() -> List[BatchTemplate]:
        """Get predefined batch analysis templates."""
        return [
            BatchTemplate(
                name="Security Comprehensive",
                description="Complete security analysis including static, dynamic, and AI review",
                analysis_types=[
                    AnalysisType.SECURITY.value,
                    AnalysisType.DYNAMIC.value,
                    AnalysisType.AI_REVIEW.value
                ],
                default_config={
                    'parallel_execution': True,
                    'continue_on_failure': True,
                    'max_retries': 2,
                    'timeout_per_task': 1800,
                    'resource_limits': {
                        'max_memory': '2GB',
                        'max_cpu_percent': 80
                    }
                },
                recommended_targets={
                    'max_apps_per_model': 5,
                    'max_total_tasks': 50
                },
                estimated_time_per_app=30  # 30 minutes
            ),
            BatchTemplate(
                name="Performance Baseline",
                description="Performance testing across multiple applications",
                analysis_types=[AnalysisType.PERFORMANCE.value],
                default_config={
                    'parallel_execution': True,
                    'continue_on_failure': True,
                    'performance_config': {
                        'users': 10,
                        'spawn_rate': 2,
                        'test_duration': '2m'
                    }
                },
                recommended_targets={
                    'max_apps_per_model': 10,
                    'max_total_tasks': 100
                },
                estimated_time_per_app=5  # 5 minutes
            ),
            BatchTemplate(
                name="Code Quality Assessment",
                description="Static analysis and code quality metrics",
                analysis_types=[
                    AnalysisType.STATIC.value,
                    AnalysisType.AI_REVIEW.value
                ],
                default_config={
                    'parallel_execution': True,
                    'continue_on_failure': True,
                    'quality_thresholds': {
                        'min_score': 7.0,
                        'max_issues': 50
                    }
                },
                recommended_targets={
                    'max_apps_per_model': 15,
                    'max_total_tasks': 200
                },
                estimated_time_per_app=8  # 8 minutes
            ),
            BatchTemplate(
                name="Full Analysis Suite",
                description="Complete analysis including all available types",
                analysis_types=[
                    AnalysisType.SECURITY.value,
                    AnalysisType.PERFORMANCE.value,
                    AnalysisType.STATIC.value,
                    AnalysisType.DYNAMIC.value,
                    AnalysisType.AI_REVIEW.value
                ],
                default_config={
                    'parallel_execution': True,
                    'continue_on_failure': True,
                    'max_retries': 1,
                    'staggered_execution': True,
                    'resource_optimization': True
                },
                recommended_targets={
                    'max_apps_per_model': 3,
                    'max_total_tasks': 30
                },
                estimated_time_per_app=45  # 45 minutes
            )
        ]
    
    @staticmethod
    def get_template(name: str) -> Optional[BatchTemplate]:
        """Get template by name."""
        templates = BatchTemplateService.get_default_templates()
        return next((t for t in templates if t.name == name), None)


class BatchValidationService:
    """Service for validating batch configurations."""
    
    @staticmethod
    def validate_batch_config(
        name: str,
        analysis_types: List[str],
        target_models: List[str],
        target_apps: List[int],
        config: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, List[str]]:
        """Validate batch configuration and return validation results."""
        errors = []
        
        # Validate name
        if not name or not name.strip():
            errors.append("Batch name is required")
        elif len(name.strip()) < 3:
            errors.append("Batch name must be at least 3 characters")
        elif len(name.strip()) > 200:
            errors.append("Batch name must be less than 200 characters")
        
        # Validate analysis types
        if not analysis_types:
            errors.append("At least one analysis type is required")
        else:
            valid_types = [t.value for t in AnalysisType]
            invalid_types = [t for t in analysis_types if t not in valid_types]
            if invalid_types:
                errors.append(f"Invalid analysis types: {', '.join(invalid_types)}")
        
        # Validate targets
        if not target_models:
            errors.append("At least one target model is required")
        elif len(target_models) > 50:
            errors.append("Maximum 50 target models allowed")
        
        if not target_apps:
            errors.append("At least one target app is required")
        elif len(target_apps) > 100:
            errors.append("Maximum 100 target apps allowed")
        elif any(app < 1 for app in target_apps):
            errors.append("App numbers must be positive integers")
        
        # Calculate total tasks
        total_tasks = len(target_models) * len(target_apps) * len(analysis_types)
        if total_tasks > 1000:
            errors.append(f"Total tasks ({total_tasks}) exceeds maximum limit of 1000")
        
        # Validate configuration
        if config:
            config_errors = BatchValidationService._validate_config(config)
            errors.extend(config_errors)
        
        return len(errors) == 0, errors
    
    @staticmethod
    def _validate_config(config: Dict[str, Any]) -> List[str]:
        """Validate batch configuration parameters."""
        errors = []
        
        # Validate parallel execution settings
        max_parallel = config.get('max_parallel_tasks', 3)
        if not isinstance(max_parallel, int) or max_parallel < 1 or max_parallel > 10:
            errors.append("max_parallel_tasks must be between 1 and 10")
        
        # Validate timeout
        task_timeout = config.get('task_timeout', 3600)
        if not isinstance(task_timeout, int) or task_timeout < 60 or task_timeout > 7200:
            errors.append("task_timeout must be between 60 and 7200 seconds")
        
        # Validate priority
        priority = config.get('priority', Priority.NORMAL.value)
        valid_priorities = [p.value for p in Priority]
        if priority not in valid_priorities:
            errors.append(f"Invalid priority: {priority}")
        
        return errors
    
    @staticmethod
    def estimate_batch_execution(
        analysis_types: List[str],
        target_models: List[str],
        target_apps: List[int],
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Estimate batch execution time and resource usage."""
        
        # Base time estimates per analysis type (in seconds)
        time_estimates = {
            AnalysisType.SECURITY.value: 300,
            AnalysisType.PERFORMANCE.value: 180,
            AnalysisType.STATIC.value: 120,
            AnalysisType.DYNAMIC.value: 600,
            AnalysisType.AI_REVIEW.value: 240,
            AnalysisType.COMPREHENSIVE.value: 900
        }
        
        total_tasks = len(target_models) * len(target_apps) * len(analysis_types)
        
        # Calculate estimated time per task
        avg_time_per_task = sum(time_estimates.get(t, 300) for t in analysis_types) / len(analysis_types)
        
        # Account for parallel execution
        max_parallel = config.get('max_parallel_tasks', 3) if config else 3
        
        # Sequential time
        total_sequential_time = total_tasks * avg_time_per_task
        
        # Parallel time (with some overhead)
        parallel_efficiency = 0.85  # Account for overhead and resource contention
        parallel_time = (total_sequential_time / max_parallel) * (1 / parallel_efficiency)
        
        # Add startup and coordination overhead
        coordination_overhead = min(total_tasks * 5, 300)  # Max 5 minutes
        estimated_total_time = parallel_time + coordination_overhead
        
        return {
            'total_tasks': total_tasks,
            'estimated_time_seconds': int(estimated_total_time),
            'estimated_time_formatted': BatchValidationService._format_duration(estimated_total_time),
            'max_parallel_tasks': max_parallel,
            'avg_time_per_task': int(avg_time_per_task),
            'sequential_time': int(total_sequential_time),
            'parallel_time': int(parallel_time),
            'coordination_overhead': int(coordination_overhead),
            'estimated_completion': (
                datetime.now(timezone.utc) + timedelta(seconds=estimated_total_time)
            ).isoformat()
        }
    
    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            remaining_seconds = int(seconds % 60)
            return f"{minutes}m {remaining_seconds}s"
        else:
            hours = int(seconds / 3600)
            remaining_minutes = int((seconds % 3600) / 60)
            return f"{hours}h {remaining_minutes}m"


class BatchExecutionService:
    """Service for executing batch analyses with advanced scheduling."""
    
    def __init__(self):
        self.execution_threads = {}
        self.resource_monitor = BatchResourceMonitor()
    
    def execute_batch(self, batch_id: str, async_execution: bool = True) -> Dict[str, Any]:
        """Execute a batch analysis."""
        batch = BatchAnalysis.query.filter_by(batch_id=batch_id).first()
        if not batch:
            raise ValueError(f"Batch not found: {batch_id}")
        
        if batch.status != BatchStatus.CREATED.value:
            raise ValueError(f"Batch cannot be executed from status: {batch.status}")
        
        # Generate tasks if not already done
        if len(batch.tasks) == 0:
            self._generate_batch_tasks(batch)
        
        # Mark batch as started
        batch.mark_started()
        db.session.commit()
        
        logger.info(f"Starting execution of batch {batch_id} with {len(batch.tasks)} tasks")
        
        if async_execution:
            # Start execution in background thread
            execution_thread = threading.Thread(
                target=self._execute_batch_async,
                args=(batch_id,),
                daemon=True
            )
            execution_thread.start()
            self.execution_threads[batch_id] = execution_thread
            
            return {
                'batch_id': batch_id,
                'status': 'starting',
                'execution_mode': 'async',
                'message': 'Batch execution started in background'
            }
        else:
            # Synchronous execution
            return self._execute_batch_sync(batch_id)
    
    def _generate_batch_tasks(self, batch: BatchAnalysis) -> None:
        """Generate all tasks for a batch."""
        analysis_types = batch.get_analysis_types()
        target_models = batch.get_target_models()
        target_apps = batch.get_target_apps()
        batch_config = batch.get_config()
        
        tasks_created = 0
        for model_slug in target_models:
            for app_number in target_apps:
                for analysis_type in analysis_types:
                    try:
                        task = AnalysisTaskService.create_task(
                            model_slug=model_slug,
                            app_number=app_number,
                            analysis_type=analysis_type,
                            priority=batch.priority,
                            custom_options=batch_config.get('task_options'),
                            batch_id=batch.id
                        )
                        tasks_created += 1
                    except Exception as e:
                        logger.error(
                            f"Failed to create task for {model_slug} app {app_number} "
                            f"{analysis_type}: {e}"
                        )
        
        # Update batch with actual task count
        batch.total_tasks = tasks_created
        db.session.commit()
        
        logger.info(f"Generated {tasks_created} tasks for batch {batch.batch_id}")
    
    def _execute_batch_async(self, batch_id: str) -> None:
        """Execute batch in background thread."""
        try:
            result = self._execute_batch_sync(batch_id)
            logger.info(f"Batch {batch_id} execution completed: {result['status']}")
        except Exception as e:
            logger.error(f"Batch {batch_id} execution failed: {e}")
            # Mark batch as failed
            batch = BatchAnalysis.query.filter_by(batch_id=batch_id).first()
            if batch:
                batch.mark_failed(str(e))
                db.session.commit()
        finally:
            # Clean up thread reference
            if batch_id in self.execution_threads:
                del self.execution_threads[batch_id]
    
    def _execute_batch_sync(self, batch_id: str) -> Dict[str, Any]:
        """Execute batch synchronously."""
        batch = BatchAnalysis.query.filter_by(batch_id=batch_id).first()
        if not batch:
            raise ValueError(f"Batch not found: {batch_id}")
        
        start_time = datetime.now(timezone.utc)
        config = batch.get_config()
        max_parallel = config.get('max_parallel_tasks', 3)
        continue_on_failure = config.get('continue_on_failure', True)
        
        # Get all tasks for this batch
        tasks = batch.tasks
        pending_tasks = [t for t in tasks if t.status == AnalysisStatus.PENDING.value]
        
        completed_tasks = 0
        failed_tasks = 0
        
        # Execute tasks with controlled parallelism
        with ThreadPoolExecutor(max_workers=max_parallel) as executor:
            # Submit initial batch of tasks
            active_futures = {}
            
            # Submit first batch
            for i, task in enumerate(pending_tasks[:max_parallel]):
                future = executor.submit(self._execute_single_task, task)
                active_futures[future] = task
            
            # Process remaining tasks
            remaining_tasks = pending_tasks[max_parallel:]
            
            while active_futures or remaining_tasks:
                # Wait for at least one task to complete
                if active_futures:
                    completed_futures = []
                    for future in active_futures:
                        if future.done():
                            completed_futures.append(future)
                    
                    # Process completed tasks
                    for future in completed_futures:
                        task = active_futures[future]
                        try:
                            result = future.result()
                            if result['success']:
                                completed_tasks += 1
                                logger.debug(f"Task {task.task_id} completed successfully")
                            else:
                                failed_tasks += 1
                                logger.warning(f"Task {task.task_id} failed: {result.get('error')}")
                                
                                if not continue_on_failure:
                                    # Cancel remaining tasks
                                    for remaining_task in remaining_tasks:
                                        remaining_task.mark_cancelled()
                                    remaining_tasks = []
                                    
                                    # Cancel active futures
                                    for active_future in active_futures:
                                        if active_future != future:
                                            active_future.cancel()
                                    
                                    active_futures = {}
                                    break
                        except Exception as e:
                            failed_tasks += 1
                            logger.error(f"Task {task.task_id} execution error: {e}")
                        
                        del active_futures[future]
                    
                    # Submit new tasks if available
                    while len(active_futures) < max_parallel and remaining_tasks:
                        next_task = remaining_tasks.pop(0)
                        future = executor.submit(self._execute_single_task, next_task)
                        active_futures[future] = next_task
                
                # Update batch progress
                batch.completed_tasks = completed_tasks
                batch.failed_tasks = failed_tasks
                db.session.commit()
                
                # Brief pause to avoid overwhelming the system
                if active_futures:
                    import time
                    time.sleep(0.1)
        
        # Mark batch as completed
        end_time = datetime.now(timezone.utc)
        execution_time = (end_time - start_time).total_seconds()
        
        if failed_tasks > 0 and not continue_on_failure:
            batch.mark_failed(f"Batch failed due to {failed_tasks} failed tasks")
        else:
            batch.mark_completed()
        
        # Update final statistics
        results_summary = {
            'total_tasks': len(tasks),
            'completed_tasks': completed_tasks,
            'failed_tasks': failed_tasks,
            'cancelled_tasks': len(tasks) - completed_tasks - failed_tasks,
            'execution_time_seconds': int(execution_time),
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat()
        }
        
        batch.set_results_summary(results_summary)
        db.session.commit()
        
        logger.info(
            f"Batch {batch_id} execution completed: "
            f"{completed_tasks} completed, {failed_tasks} failed"
        )
        
        return {
            'batch_id': batch_id,
            'status': batch.status,
            'results_summary': results_summary,
            'execution_mode': 'sync'
        }
    
    def _execute_single_task(self, task: AnalysisTask) -> Dict[str, Any]:
        """Execute a single analysis task."""
        try:
            # Mark task as started
            task.mark_started()
            db.session.commit()
            
            # Simulate task execution (in real implementation, this would
            # integrate with the actual analyzer services)
            import time
            import random
            
            # Simulate execution time
            execution_time = random.uniform(1, 5)  # 1-5 seconds for demo
            time.sleep(execution_time)
            
            # Simulate success/failure
            success_rate = 0.9  # 90% success rate
            if random.random() < success_rate:
                # Success
                mock_results = {
                    'status': 'completed',
                    'analysis_type': task.analysis_type,
                    'findings': random.randint(0, 10),
                    'score': random.uniform(7.0, 10.0),
                    'execution_time': execution_time
                }
                task.mark_completed(mock_results)
                db.session.commit()
                
                return {'success': True, 'results': mock_results}
            else:
                # Failure
                error_message = "Simulated analysis failure"
                task.mark_failed(error_message)
                db.session.commit()
                
                return {'success': False, 'error': error_message}
                
        except Exception as e:
            task.mark_failed(str(e))
            db.session.commit()
            return {'success': False, 'error': str(e)}
    
    def cancel_batch_execution(self, batch_id: str) -> Dict[str, Any]:
        """Cancel a running batch execution."""
        batch = BatchAnalysis.query.filter_by(batch_id=batch_id).first()
        if not batch:
            raise ValueError(f"Batch not found: {batch_id}")
        
        if not batch.is_running:
            raise ValueError(f"Batch is not running: {batch.status}")
        
        # Cancel all non-completed tasks
        cancelled_count = 0
        for task in batch.tasks:
            if not task.is_complete:
                task.mark_cancelled()
                cancelled_count += 1
        
        batch.mark_cancelled()
        db.session.commit()
        
        # Stop execution thread if running
        if batch_id in self.execution_threads:
            # Note: Thread cancellation is complex in Python
            # In a real implementation, you'd use proper cancellation mechanisms
            logger.info(f"Stopping execution thread for batch {batch_id}")
        
        logger.info(f"Cancelled batch {batch_id}, cancelled {cancelled_count} tasks")
        
        return {
            'batch_id': batch_id,
            'status': 'cancelled',
            'cancelled_tasks': cancelled_count,
            'message': f'Batch execution cancelled, {cancelled_count} tasks cancelled'
        }


class BatchResourceMonitor:
    """Monitor resource usage during batch execution."""
    
    def __init__(self):
        self.resource_history = {}
    
    def start_monitoring(self, batch_id: str) -> None:
        """Start monitoring resources for a batch."""
        self.resource_history[batch_id] = []
        logger.debug(f"Started resource monitoring for batch {batch_id}")
    
    def record_resources(self, batch_id: str) -> Dict[str, Any]:
        """Record current resource usage."""
        # This would integrate with actual system monitoring
        resources = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'cpu_percent': 45.0,  # Mock data
            'memory_mb': 1024,    # Mock data
            'disk_io_mb': 50,     # Mock data
            'network_io_mb': 10   # Mock data
        }
        
        if batch_id in self.resource_history:
            self.resource_history[batch_id].append(resources)
        
        return resources
    
    def stop_monitoring(self, batch_id: str) -> Dict[str, Any]:
        """Stop monitoring and return summary."""
        history = self.resource_history.get(batch_id, [])
        
        if history:
            summary = {
                'total_records': len(history),
                'avg_cpu_percent': sum(r['cpu_percent'] for r in history) / len(history),
                'avg_memory_mb': sum(r['memory_mb'] for r in history) / len(history),
                'peak_cpu_percent': max(r['cpu_percent'] for r in history),
                'peak_memory_mb': max(r['memory_mb'] for r in history),
                'monitoring_duration': len(history) * 30  # Assuming 30s intervals
            }
        else:
            summary = {'message': 'No resource data recorded'}
        
        # Clean up
        if batch_id in self.resource_history:
            del self.resource_history[batch_id]
        
        logger.debug(f"Stopped resource monitoring for batch {batch_id}")
        return summary


# Initialize service instances
batch_template_service = BatchTemplateService()
batch_validation_service = BatchValidationService()
batch_execution_service = BatchExecutionService()



