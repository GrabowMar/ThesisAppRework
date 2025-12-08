"""Pipeline Execution Service
==============================

Background daemon service that processes automation pipelines.
Similar to TaskExecutionService but handles the multi-stage pipeline workflow:
Generation → Analysis → Reports

Key features:
- Polls database for running pipelines
- Executes jobs sequentially within each stage
- Handles stage transitions automatically
- Checks analyzer service health before analysis stage
- Emits real-time updates via WebSocket if available
"""

from __future__ import annotations

import threading
import time
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from app.utils.logging_config import get_logger
from app.extensions import db, get_components
from app.models import PipelineExecution, PipelineExecutionStatus, GeneratedApplication, AnalysisTask
from app.constants import AnalysisStatus
from app.services.service_locator import ServiceLocator

logger = get_logger("pipeline_executor")


class PipelineExecutionService:
    """Background service for executing automation pipelines.
    
    Lifecycle:
    - Polls DB for pipelines with status='running'
    - For each running pipeline, executes the next pending job
    - Handles stage transitions (generation → analysis → reports)
    - Checks analyzer health before analysis stage
    """
    
    def __init__(self, poll_interval: float = 3.0, app=None):
        """Initialize pipeline execution service.
        
        Args:
            poll_interval: Seconds between polling for work
            app: Flask application instance for context
        """
        self.poll_interval = poll_interval
        self._app = app
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._current_pipeline_id: Optional[str] = None
        
        # Analyzer health cache
        self._analyzer_healthy: Optional[bool] = None
        self._analyzer_check_time: float = 0.0
        self._analyzer_check_interval: float = 60.0  # Re-check every 60 seconds
        
        self._log("PipelineExecutionService initialized (poll_interval=%s)", poll_interval)
    
    def _log(self, msg: str, *args, level: str = 'info', **kwargs):
        """Log with consistent formatting."""
        formatted = msg % args if args else msg
        log_func = getattr(logger, level, logger.info)
        log_func(f"[PipelineExecutor] {formatted}")
    
    def start(self):
        """Start the background execution thread."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._log("PipelineExecutionService started")
    
    def stop(self):
        """Stop the background execution thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        self._log("PipelineExecutionService stopped")
    
    def _run_loop(self):
        """Main execution loop - polls for and processes pipelines."""
        self._log("Execution loop started")
        
        while self._running:
            with (self._app.app_context() if self._app else _nullcontext()):
                try:
                    # Get running pipelines
                    pipelines = PipelineExecution.get_running_pipelines()
                    
                    if not pipelines:
                        time.sleep(self.poll_interval)
                        continue
                    
                    self._log("Found %d running pipeline(s)", len(pipelines), level='debug')
                    
                    # Process each running pipeline
                    for pipeline in pipelines:
                        try:
                            self._current_pipeline_id = pipeline.pipeline_id
                            self._process_pipeline(pipeline)
                        except Exception as e:
                            self._log(
                                "Error processing pipeline %s: %s",
                                pipeline.pipeline_id, e,
                                level='error'
                            )
                            # Mark pipeline as failed on exception
                            try:
                                pipeline.fail(str(e))
                                db.session.commit()
                            except Exception:
                                db.session.rollback()
                        finally:
                            self._current_pipeline_id = None
                    
                except Exception as e:
                    self._log("Pipeline execution loop error: %s", e, level='error')
                
                time.sleep(self.poll_interval)
    
    def _process_pipeline(self, pipeline: PipelineExecution):
        """Process a single pipeline - execute its next job."""
        # Get next job to execute
        job = pipeline.get_next_job()
        
        if job is None:
            # No more jobs - check if we need to transition stages
            self._check_stage_transition(pipeline)
            return
        
        self._log(
            "Processing pipeline %s: stage=%s, job=%s",
            pipeline.pipeline_id, job['stage'], job.get('job_index', 0)
        )
        
        # Execute based on stage
        if job['stage'] == 'generation':
            self._execute_generation_job(pipeline, job)
        elif job['stage'] == 'analysis':
            self._execute_analysis_job(pipeline, job)
        elif job['stage'] == 'reports':
            self._execute_reports_job(pipeline, job)
        
        # Advance to next job
        pipeline.advance_job_index()
        db.session.commit()
        
        # Emit progress update
        self._emit_progress_update(pipeline)
    
    def _check_stage_transition(self, pipeline: PipelineExecution):
        """Check if pipeline should transition to next stage or complete."""
        progress = pipeline.progress
        
        if pipeline.current_stage == 'generation':
            gen = progress.get('generation', {})
            if gen.get('status') == 'completed':
                # Check if analysis is enabled
                if progress.get('analysis', {}).get('status') != 'skipped':
                    pipeline.current_stage = 'analysis'
                    pipeline.current_job_index = 0
                    progress['analysis']['status'] = 'running'
                    pipeline.progress = progress
                    self._log("Pipeline %s transitioning to analysis stage", pipeline.pipeline_id)
                else:
                    # Skip to reports
                    pipeline.current_stage = 'reports'
                    pipeline.current_job_index = 0
        
        elif pipeline.current_stage == 'analysis':
            # Poll actual task completion status from database
            analysis_done = self._check_analysis_tasks_completion(pipeline)
            
            if analysis_done:
                if progress.get('reports', {}).get('status') != 'skipped':
                    pipeline.current_stage = 'reports'
                    pipeline.current_job_index = 0
                    progress = pipeline.progress  # Refresh after update
                    progress['reports']['status'] = 'running'
                    pipeline.progress = progress
                    self._log("Pipeline %s transitioning to reports stage", pipeline.pipeline_id)
                else:
                    # Complete pipeline
                    pipeline.status = PipelineExecutionStatus.COMPLETED
                    pipeline.completed_at = datetime.now(timezone.utc)
        
        elif pipeline.current_stage == 'reports':
            reports = progress.get('reports', {})
            if reports.get('status') == 'completed':
                pipeline.status = PipelineExecutionStatus.COMPLETED
                pipeline.completed_at = datetime.now(timezone.utc)
                pipeline.current_stage = 'done'
                self._log("Pipeline %s completed", pipeline.pipeline_id)
        
        db.session.commit()
    
    def _check_analysis_tasks_completion(self, pipeline: PipelineExecution) -> bool:
        """Check actual completion status of analysis tasks from DB.
        
        Returns True if all tasks have reached a terminal state.
        """
        progress = pipeline.progress
        task_ids = progress.get('analysis', {}).get('task_ids', [])
        
        if not task_ids:
            self._log(
                "Pipeline %s: No analysis tasks to wait for",
                pipeline.pipeline_id
            )
            return True  # No tasks to wait for
        
        completed_count = 0
        failed_count = 0
        pending_count = 0
        
        for task_id in task_ids:
            # Handle skipped/error markers
            if task_id.startswith('skipped') or task_id.startswith('error:'):
                failed_count += 1
                continue
            
            # Query actual task status from database
            task = AnalysisTask.query.filter_by(task_id=task_id).first()
            if not task:
                # Task not found - treat as failed
                self._log(
                    "Analysis task %s not found in database",
                    task_id, level='warning'
                )
                failed_count += 1
                continue
            
            if task.status == AnalysisStatus.COMPLETED:
                completed_count += 1
            elif task.status == AnalysisStatus.PARTIAL_SUCCESS:
                completed_count += 1  # Partial success counts as complete
            elif task.status in (AnalysisStatus.FAILED, AnalysisStatus.CANCELLED):
                failed_count += 1
            else:
                # PENDING, RUNNING, or other active states
                pending_count += 1
        
        total_tasks = len(task_ids)
        terminal_count = completed_count + failed_count
        
        self._log(
            "Pipeline %s analysis status: %d/%d terminal (completed=%d, failed=%d, pending=%d)",
            pipeline.pipeline_id,
            terminal_count,
            total_tasks,
            completed_count,
            failed_count,
            pending_count
        )
        
        # Must wait for ALL tasks to reach terminal state
        if pending_count > 0:
            return False
        
        # Update pipeline progress with final counts
        pipeline.update_analysis_completion(completed_count, failed_count)
        
        self._log(
            "Pipeline %s: All %d analysis tasks finished (%d success, %d failed)",
            pipeline.pipeline_id,
            total_tasks,
            completed_count,
            failed_count
        )
        return True
    
    def _execute_generation_job(self, pipeline: PipelineExecution, job: Dict[str, Any]):
        """Execute a single generation job."""
        model_slug = job['model_slug']
        template_slug = job['template_slug']
        
        self._log(
            "Generating app for %s with template %s",
            model_slug, template_slug
        )
        
        try:
            # Get generation service
            from app.services.generation import get_generation_service
            svc = get_generation_service()
            
            # Get next app number for this model
            max_app = GeneratedApplication.query.filter_by(
                model_slug=model_slug
            ).order_by(
                GeneratedApplication.app_number.desc()
            ).first()
            app_num = (max_app.app_number + 1) if max_app else 1
            
            # Run generation (async wrapper)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                gen_result = loop.run_until_complete(
                    svc.generate_full_app(
                        model_slug=model_slug,
                        app_num=app_num,
                        template_slug=template_slug,
                    )
                )
            finally:
                loop.close()
            
            # Record result
            result = {
                'model_slug': model_slug,
                'template_slug': template_slug,
                'app_number': gen_result.get('app_number', app_num),
                'success': gen_result.get('success', True),
            }
            pipeline.add_generation_result(result)
            
            self._log(
                "Generated %s app %d with template %s",
                model_slug, result['app_number'], template_slug
            )
            
        except Exception as e:
            self._log(
                "Generation failed for %s with %s: %s",
                model_slug, template_slug, e,
                level='error'
            )
            result = {
                'model_slug': model_slug,
                'template_slug': template_slug,
                'success': False,
                'error': str(e),
            }
            pipeline.add_generation_result(result)
        
        db.session.commit()
    
    def _execute_analysis_job(self, pipeline: PipelineExecution, job: Dict[str, Any]):
        """Execute a single analysis job."""
        # Skip if generation failed
        if not job.get('success', False):
            self._log(
                "Skipping analysis for %s app %s - generation failed",
                job.get('model_slug'), job.get('app_number')
            )
            pipeline.add_analysis_task_id('skipped', success=False)
            db.session.commit()
            return
        
        model_slug = job['model_slug']
        app_number = job['app_number']
        
        # Check if we already created a task for this app in this pipeline
        # (prevents duplicates on server restart)
        progress = pipeline.progress
        existing_task_ids = progress.get('analysis', {}).get('task_ids', [])
        
        # Check if any existing task targets this app
        for task_id in existing_task_ids:
            if task_id.startswith('skipped') or task_id.startswith('error:'):
                continue
            existing_task = AnalysisTask.query.filter_by(task_id=task_id).first()
            if (existing_task and 
                existing_task.target_model == model_slug and 
                existing_task.target_app_number == app_number):
                self._log(
                    "Skipping duplicate analysis task for %s app %d (already have %s)",
                    model_slug, app_number, task_id
                )
                return  # Already have a task for this app
        
        # Check analyzer health on first analysis job
        if job['job_index'] == 0:
            if not self._ensure_analyzers_healthy(pipeline):
                # Analyzers not available - check if auto-start was disabled
                config = pipeline.config
                auto_start = config.get('analysis', {}).get('options', {}).get('autoStartContainers', False)
                
                if not auto_start:
                    # User didn't enable auto-start - fail pipeline with helpful message
                    error_msg = (
                        "Analyzer services are not running. Either:\n"
                        "1. Start containers manually: ./start.ps1 -Mode Start\n"
                        "2. Or enable 'Auto-start containers' in pipeline settings"
                    )
                    self._log(
                        "Failing pipeline %s - analyzers unavailable and auto-start disabled",
                        pipeline.pipeline_id,
                        level='error'
                    )
                    pipeline.fail(error_msg)
                    db.session.commit()
                    return
                else:
                    # Auto-start was enabled but failed
                    self._log(
                        "Analyzer services failed to start for pipeline %s - continuing with degraded analysis",
                        pipeline.pipeline_id,
                        level='warning'
                    )
        
        self._log(
            "Creating analysis task for %s app %d",
            model_slug, app_number
        )
        
        try:
            from app.services.task_service import AnalysisTaskService
            from app.engines.container_tool_registry import get_container_tool_registry
            
            # Get analysis config
            config = pipeline.config
            analysis_config = config.get('analysis', {})
            profile = analysis_config.get('profile', 'comprehensive')
            tools = analysis_config.get('tools', [])
            options = analysis_config.get('options', {})
            
            # Get default tools if none specified
            if not tools:
                try:
                    registry = get_container_tool_registry()
                    all_tools = registry.get_all_tools()
                    tools = [t.name for t in all_tools.values() if t.available]
                except Exception:
                    tools = []
            
            # Build container management options
            container_management = {}
            if options.get('autoStartContainers', False):
                container_management = {
                    'start_before_analysis': True,
                    'build_if_missing': True,
                    'stop_after_analysis': False,
                }
            
            # Create analysis task
            task = AnalysisTaskService.create_task(
                model_slug=model_slug,
                app_number=app_number,
                tools=tools,
                priority='normal',
                custom_options={
                    'source': 'automation_pipeline',
                    'pipeline_id': pipeline.pipeline_id,
                    'container_management': container_management,
                },
            )
            
            pipeline.add_analysis_task_id(task.task_id, success=True)
            
            self._log(
                "Created analysis task %s for %s app %d",
                task.task_id, model_slug, app_number
            )
            
        except Exception as e:
            self._log(
                "Analysis task creation failed for %s app %d: %s",
                model_slug, app_number, e,
                level='error'
            )
            pipeline.add_analysis_task_id(f'error:{str(e)}', success=False)
        
        db.session.commit()
    
    def _execute_reports_job(self, pipeline: PipelineExecution, job: Dict[str, Any]):
        """Execute report generation job."""
        successful_apps = job.get('apps', [])
        
        if not successful_apps:
            self._log(
                "No successful apps to report on for pipeline %s",
                pipeline.pipeline_id,
                level='warning'
            )
            pipeline.add_report_id('skipped', success=False)
            db.session.commit()
            return
        
        self._log(
            "Generating reports for %d apps in pipeline %s",
            len(successful_apps), pipeline.pipeline_id
        )
        
        try:
            from app.services.report_generation_service import ReportGenerationService
            from flask import current_app
            
            report_service = ServiceLocator.get_report_service()
            if report_service is None:
                report_service = ReportGenerationService(current_app)
            
            config = pipeline.config
            reports_config = config.get('reports', {})
            report_types = reports_config.get('types', ['app_analysis'])
            report_format = reports_config.get('format', 'html')
            
            created_reports = []
            
            for report_type in report_types:
                if report_type == 'app_analysis':
                    # Generate report for each app
                    for app_result in successful_apps:
                        report_config = {
                            'model_slug': app_result.get('model_slug'),
                            'app_number': app_result.get('app_number'),
                        }
                        
                        report = report_service.generate_report(
                            report_type=report_type,
                            format=report_format,
                            config=report_config,
                            title=f"Pipeline Report - {app_result.get('model_slug')} App {app_result.get('app_number')}",
                            user_id=pipeline.user_id,
                        )
                        created_reports.append(report.report_id)
                else:
                    # Model comparison or tool effectiveness
                    report_config = {
                        'filter_models': list(set(r.get('model_slug') for r in successful_apps)),
                        'filter_apps': list(set(r.get('app_number') for r in successful_apps)),
                    }
                    
                    report = report_service.generate_report(
                        report_type=report_type,
                        format=report_format,
                        config=report_config,
                        title=f"Pipeline {report_type.replace('_', ' ').title()}",
                        user_id=pipeline.user_id,
                    )
                    created_reports.append(report.report_id)
            
            # Record reports
            for report_id in created_reports:
                pipeline.add_report_id(report_id, success=True)
            
            self._log(
                "Generated %d reports for pipeline %s",
                len(created_reports), pipeline.pipeline_id
            )
            
        except Exception as e:
            self._log(
                "Report generation failed for pipeline %s: %s",
                pipeline.pipeline_id, e,
                level='error'
            )
            pipeline.add_report_id(f'error:{str(e)}', success=False)
        
        db.session.commit()
    
    def _ensure_analyzers_healthy(self, pipeline: PipelineExecution) -> bool:
        """Check and optionally start analyzer containers.
        
        Returns True if analyzers are healthy or were successfully started.
        """
        # Check cache first
        current_time = time.time()
        if (self._analyzer_healthy is not None and 
            (current_time - self._analyzer_check_time) < self._analyzer_check_interval):
            return self._analyzer_healthy
        
        config = pipeline.config
        analysis_options = config.get('analysis', {}).get('options', {})
        auto_start = analysis_options.get('autoStartContainers', False)
        
        try:
            import sys
            from pathlib import Path
            from flask import current_app
            
            # Add project root to path
            project_root = Path(current_app.root_path).parent.parent
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))
            
            from analyzer.analyzer_manager import AnalyzerManager
            
            manager = AnalyzerManager()
            
            # Check current status
            containers = manager.get_container_status()
            all_running = all(
                c.get('state') == 'running'
                for c in containers.values()
            ) if containers else False
            
            # Check port accessibility
            all_ports_accessible = all(
                manager.check_port_accessibility('localhost', service_info.port)
                for service_info in manager.services.values()
            )
            
            if all_running and all_ports_accessible:
                self._analyzer_healthy = True
                self._analyzer_check_time = current_time
                self._log("Analyzer containers healthy")
                return True
            
            # Need to start containers if auto_start is enabled
            if auto_start:
                self._log("Starting analyzer containers...")
                
                success = manager.start_services()
                if not success:
                    self._log("Failed to start analyzer containers", level='error')
                    self._analyzer_healthy = False
                    self._analyzer_check_time = current_time
                    return False
                
                # Wait for containers to become healthy
                max_wait = 90
                start_time = time.time()
                
                while time.time() - start_time < max_wait:
                    all_accessible = all(
                        manager.check_port_accessibility('localhost', service_info.port)
                        for service_info in manager.services.values()
                    )
                    
                    if all_accessible:
                        self._log("Analyzer containers started and healthy")
                        self._analyzer_healthy = True
                        self._analyzer_check_time = current_time
                        return True
                    
                    time.sleep(3)
                
                self._log("Timeout waiting for analyzer containers", level='warning')
                self._analyzer_healthy = False
                self._analyzer_check_time = current_time
                return False
            
            # Not auto-starting - just report status
            self._analyzer_healthy = False
            self._analyzer_check_time = current_time
            return False
            
        except Exception as e:
            self._log("Error checking analyzer health: %s", e, level='error')
            self._analyzer_healthy = False
            self._analyzer_check_time = current_time
            return False
    
    def _emit_progress_update(self, pipeline: PipelineExecution):
        """Emit real-time progress update via WebSocket if available."""
        try:
            from app.realtime.task_events import emit_task_event
            
            emit_task_event(
                "pipeline.updated",
                {
                    "pipeline_id": pipeline.pipeline_id,
                    "status": pipeline.status,
                    "stage": pipeline.current_stage,
                    "progress": pipeline.progress,
                    "overall_progress": pipeline.get_overall_progress(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception:
            pass  # WebSocket not available - that's fine


# Null context manager for when app is None
class _nullcontext:
    def __enter__(self):
        return None
    def __exit__(self, *args):
        pass


# Module-level singleton
_pipeline_execution_service: Optional[PipelineExecutionService] = None


def get_pipeline_execution_service() -> Optional[PipelineExecutionService]:
    """Get the pipeline execution service singleton."""
    return _pipeline_execution_service


def init_pipeline_execution_service(app) -> PipelineExecutionService:
    """Initialize and start the pipeline execution service."""
    global _pipeline_execution_service
    
    if _pipeline_execution_service is None:
        # Shorter interval in test mode
        poll_interval = 2.0 if app.config.get('TESTING') else 3.0
        
        _pipeline_execution_service = PipelineExecutionService(
            poll_interval=poll_interval,
            app=app
        )
        _pipeline_execution_service.start()
        
        logger.info("PipelineExecutionService initialized and started")
    
    return _pipeline_execution_service
