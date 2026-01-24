"""
Analyzer Execution Service
===========================

Service that bridges Flask app to analyzer_manager.py for running analysis
and generating results in the correct format matching the target structure.

This service:
- Invokes analyzer_manager.py for comprehensive analysis
- Ensures results are saved to results/<model>/app<N>/task_<id>/
- Generates consolidated JSON, SARIF files, service snapshots, and manifest
- Updates AnalysisTask status in database
"""

import asyncio
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import json

from app.utils.logging_config import get_logger
from app.extensions import db
from app.models import AnalysisTask, AnalysisResult
from app.constants import AnalysisStatus

logger = get_logger('analyzer_execution')

# Import analyzer_manager
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from analyzer.analyzer_manager import AnalyzerManager
except ImportError as e:
    logger.error(f"Failed to import AnalyzerManager: {e}")
    AnalyzerManager = None  # type: ignore



try:
    from flask import current_app
except ImportError:
    current_app = None

class AnalyzerExecutionService:
    """Service for executing analysis via analyzer_manager."""
    
    def __init__(self):
        self.manager = AnalyzerManager() if AnalyzerManager else None
        if not self.manager:
            logger.error("AnalyzerManager not available - analysis will fail")
            
        # Capture app context if we are in one (to propagate to threads)
        self.app = None
        if current_app:
            try:
                # Get the real app object, not the proxy
                self.app = current_app._get_current_object()
                logger.debug("Captured Flask app context for execution service")
            except Exception as e:
                logger.warning(f"Could not capture Flask app object: {e}")

    async def _run_db_op(self, func: Any, *args, **kwargs) -> Any:
        """Run a DB operation in a thread with proper app context."""
        
        def wrapper():
            # If we captured an app, push its context
            ctx = None
            if self.app:
                ctx = self.app.app_context()
                ctx.push()
            elif not current_app:
                # Fallback: try to create a new app if we have none
                try:
                    from app import create_app
                    app = create_app()
                    ctx = app.app_context()
                    ctx.push()
                except Exception as e:
                    logger.warning(f"Could not create fallback app context: {e}")
            
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"DB operation failed: {e}")
                raise
            finally:
                if ctx:
                    ctx.pop()
        
        return await asyncio.to_thread(wrapper)
    
    async def execute_comprehensive_analysis(
        self,
        task: AnalysisTask,
        tools: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Execute comprehensive analysis for a task.
        
        Args:
            task: AnalysisTask to execute
            tools: Optional list of tool names to run (default: all available)
        
        Returns:
            Dict with execution results
        """
        if not self.manager:
            return {
                'success': False,
                'error': 'AnalyzerManager not available'
            }
        
        model_slug = task.target_model
        app_number = task.target_app_number
        task_id = task.task_id
        
        logger.info(
            f"Starting comprehensive analysis: task={task_id}, "
            f"model={model_slug}, app={app_number}, tools={tools}"
        )
        
        try:
            # Update task status to running
            def _set_running(t):
                t.status = AnalysisStatus.RUNNING
                t.started_at = datetime.now(timezone.utc)
                t.progress_percentage = 10
                db.session.commit()
            
            await self._run_db_op(_set_running, task)
            
            # Run comprehensive analysis via analyzer_manager
            # This will run all services and save results to the correct location
            results = await self.manager.run_comprehensive_analysis(
                model_slug=model_slug,
                app_number=app_number,
                task_name=task_id
            )
            
            logger.info(f"Analysis completed for task {task_id}")
            
            # The analyzer_manager saves results automatically
            # We just need to find the result files and create DB records
            
            # Update task status and create records
            def _complete_task(t, res):
                t.status = AnalysisStatus.COMPLETED
                t.completed_at = datetime.now(timezone.utc)
                t.progress_percentage = 100
                self._create_result_records_sync(t, res)
                db.session.commit()
            
            await self._run_db_op(_complete_task, task, results)
            
            return {
                'success': True,
                'task_id': task_id,
                'results': results
            }
            
        except Exception as e:
            logger.exception(f"Analysis failed for task {task_id}: {e}")
            
            # Update task with error
            def _fail_task(t, err_msg):
                t.status = AnalysisStatus.FAILED
                t.error_message = err_msg
                t.completed_at = datetime.now(timezone.utc)
                db.session.commit()
            
            await self._run_db_op(_fail_task, task, str(e))
            
            return {
                'success': False,
                'task_id': task_id,
                'error': str(e)
            }
    
    async def execute_custom_analysis(
        self,
        task: AnalysisTask,
        tools: List[str]
    ) -> Dict[str, Any]:
        """
        Execute analysis with specific tools.
        
        Args:
            task: AnalysisTask to execute
            tools: List of tool names to run
        
        Returns:
            Dict with execution results
        """
        if not self.manager:
            return {
                'success': False,
                'error': 'AnalyzerManager not available'
            }
        
        model_slug = task.target_model
        app_number = task.target_app_number
        task_id = task.task_id
        
        logger.info(
            f"Starting custom analysis: task={task_id}, "
            f"model={model_slug}, app={app_number}, tools={tools}"
        )
        
        try:
            # Update task status
            def _set_running_custom(t):
                t.status = AnalysisStatus.RUNNING
                t.started_at = datetime.now(timezone.utc)
                t.progress_percentage = 10
                db.session.commit()
                
            await self._run_db_op(_set_running_custom, task)
            
            # Determine which services to run based on tools
            services_to_run = self._map_tools_to_services(tools)
            
            # Run services
            all_results = {}
            for service_name in services_to_run:
                logger.info(f"Running {service_name} service for task {task_id}")
                
                service_tools = self._get_tools_for_service(tools, service_name)
                
                if service_name == 'static-analyzer':
                    result = await self.manager.run_static_analysis(
                        model_slug=model_slug,
                        app_number=app_number,
                        tools=service_tools
                    )
                elif service_name == 'dynamic-analyzer':
                    result = await self.manager.run_dynamic_analysis(
                        model_slug=model_slug,
                        app_number=app_number,
                        tools=service_tools
                    )
                elif service_name == 'performance-tester':
                    result = await self.manager.run_performance_test(
                        model_slug=model_slug,
                        app_number=app_number,
                        tools=service_tools
                    )
                elif service_name == 'ai-analyzer':
                    result = await self.manager.run_ai_analysis(
                        model_slug=model_slug,
                        app_number=app_number,
                        tools=service_tools
                    )
                else:
                    logger.warning(f"Unknown service: {service_name}")
                    continue
                
                all_results[service_name] = result
                
                # Update progress
                def _update_prog(t, p):
                    t.progress_percentage = p
                    db.session.commit()
                
                progress = 10 + (80 * len(all_results) // len(services_to_run))
                await self._run_db_op(_update_prog, task, progress)
            
            # Save consolidated results
            await self.manager.save_task_results(
                model_slug=model_slug,
                app_number=app_number,
                task_id=task_id,
                consolidated_results={'services': all_results}
            )
            
            # Update task status and records
            def _complete_custom(t, res):
                t.status = AnalysisStatus.COMPLETED
                t.completed_at = datetime.now(timezone.utc)
                t.progress_percentage = 100
                self._create_result_records_sync(t, res)
                db.session.commit()
            
            await self._run_db_op(_complete_custom, task, all_results)
            
            return {
                'success': True,
                'task_id': task_id,
                'results': all_results
            }
            
        except Exception as e:
            logger.exception(f"Custom analysis failed for task {task_id}: {e}")
            
            # Update task with error
            def _fail_custom(t, err_msg):
                t.status = AnalysisStatus.FAILED
                t.error_message = err_msg
                t.completed_at = datetime.now(timezone.utc)
                db.session.commit()
            
            await self._run_db_op(_fail_custom, task, str(e))
            
            return {
                'success': False,
                'task_id': task_id,
                'error': str(e)
            }
    
    def _map_tools_to_services(self, tools: List[str]) -> List[str]:
        """Map tool names to service names."""
        # Import tool registry to determine which service each tool belongs to
        try:
            from app.engines.container_tool_registry import get_container_tool_registry
            registry = get_container_tool_registry()
            all_tools = registry.get_all_tools()
            
            services = set()
            for tool_name in tools:
                tool_obj = all_tools.get(tool_name)
                if tool_obj and tool_obj.container:
                    services.add(tool_obj.container.value)
            
            return list(services)
        except Exception as e:
            logger.error(f"Failed to map tools to services: {e}")
            return ['static-analyzer']  # Default fallback
    
    def _get_tools_for_service(self, tools: List[str], service_name: str) -> List[str]:
        """Get tools that belong to a specific service."""
        try:
            from app.engines.container_tool_registry import get_container_tool_registry
            registry = get_container_tool_registry()
            all_tools = registry.get_all_tools()
            
            service_tools = []
            for tool_name in tools:
                tool_obj = all_tools.get(tool_name)
                if tool_obj and tool_obj.container and tool_obj.container.value == service_name:
                    service_tools.append(tool_name)
            
            return service_tools
        except Exception as e:
            logger.error(f"Failed to get tools for service {service_name}: {e}")
            return tools  # Return all tools as fallback
    
    
    def _create_result_records_sync(
        self,
        task: AnalysisTask,
        results: Dict[str, Any]
    ) -> None:
        """Create AnalysisResult records in database (synchronous, internal)."""
        try:
            # Find the result files created by analyzer_manager
            results_dir = PROJECT_ROOT / "results" / task.target_model.replace('/', '_') / f"app{task.target_app_number}"
            
            # Look for task directory
            if not results_dir.exists():
                logger.warning(f"Results dir not found: {results_dir}")
                return

            task_dirs = [d for d in results_dir.iterdir() if d.is_dir() and task.task_id in d.name]
            if not task_dirs:
                logger.warning(f"No result directory found for task {task.task_id}")
                return
            
            task_dir = task_dirs[0]
            
            # Load manifest
            manifest_file = task_dir / "manifest.json"
            if not manifest_file.exists():
                logger.warning(f"No manifest found at {manifest_file}")
                return
            
            with open(manifest_file, 'r') as f:
                manifest = json.load(f)
            
            # Create result records for each service
            service_files = manifest.get('service_files', {})
            for service_name, service_file in service_files.items():
                service_file_path = task_dir / "services" / service_file
                
                if not service_file_path.exists():
                    logger.warning(f"Service file not found: {service_file_path}")
                    continue
                
                # Load service result
                with open(service_file_path, 'r') as f:
                    service_data = json.load(f)
                
                # Create AnalysisResult record with required fields
                import uuid
                result = AnalysisResult(
                    result_id=f"result_{uuid.uuid4().hex[:12]}",
                    task_id=task.task_id,  # String foreign key to analysis_tasks.task_id
                    tool_name=service_name,
                    result_type="summary",
                    title=f"{service_name} analysis results",
                    structured_data=json.dumps(service_data),
                    created_at=datetime.now(timezone.utc),
                )
                
                db.session.add(result)
            
            # Note: Commit is handled by the caller
            
        except Exception as e:
            logger.error(f"Failed to create result records: {e}")


# Singleton instance
_analyzer_execution_service: Optional[AnalyzerExecutionService] = None


def get_analyzer_execution_service() -> AnalyzerExecutionService:
    """Get singleton analyzer execution service."""
    global _analyzer_execution_service
    if _analyzer_execution_service is None:
        _analyzer_execution_service = AnalyzerExecutionService()
    return _analyzer_execution_service
