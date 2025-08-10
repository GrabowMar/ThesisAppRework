"""
Celery Integration for AI Research Platform
==========================================

Celery application factory and task definitions for orchestrating
containerized analyzer services through analyzer_manager.py.
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union

from celery import Celery, current_task
from celery.signals import task_prerun, task_postrun, worker_ready

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import analyzer manager
analyzer_path = project_root / 'analyzer'
sys.path.insert(0, str(analyzer_path))

try:
    from analyzer_manager import AnalyzerManager, AnalysisRequest
except ImportError:
    print("Warning: Could not import analyzer_manager. Make sure the analyzer directory is accessible.")
    AnalyzerManager = None
    AnalysisRequest = None

# Import configuration
from config.celery_config import (
    BROKER_URL, CELERY_RESULT_BACKEND, CELERY_TASK_SERIALIZER, 
    CELERY_RESULT_SERIALIZER, CELERY_ACCEPT_CONTENT, CELERY_TIMEZONE,
    CELERY_ENABLE_UTC, CELERY_ROUTES, CELERY_QUEUES,
    CELERY_WORKER_PREFETCH_MULTIPLIER, CELERY_WORKER_MAX_TASKS_PER_CHILD,
    CELERY_TASK_TRACK_STARTED, CELERY_TASK_TIME_LIMIT, CELERY_TASK_SOFT_TIME_LIMIT,
    CELERY_TASK_ACKS_LATE, CELERY_WORKER_SEND_TASK_EVENTS, CELERY_RESULT_EXPIRES,
    CELERY_SEND_EVENTS, CELERY_TASK_REJECT_ON_WORKER_LOST, CELERY_TASK_DEFAULT_RETRY_DELAY,
    CELERY_TASK_MAX_RETRIES, CELERYBEAT_SCHEDULE
)

def create_celery_app(app_name: str = 'ai_research_platform') -> Celery:
    """Create and configure Celery application."""
    
    celery = Celery(app_name)
    
    # Update configuration
    celery.conf.update(
        broker_url=BROKER_URL,
        result_backend=CELERY_RESULT_BACKEND,
        task_serializer=CELERY_TASK_SERIALIZER,
        result_serializer=CELERY_RESULT_SERIALIZER,
        accept_content=CELERY_ACCEPT_CONTENT,
        timezone=CELERY_TIMEZONE,
        enable_utc=CELERY_ENABLE_UTC,
        task_routes=CELERY_ROUTES,
        task_queues=CELERY_QUEUES,
        worker_prefetch_multiplier=CELERY_WORKER_PREFETCH_MULTIPLIER,
        worker_max_tasks_per_child=CELERY_WORKER_MAX_TASKS_PER_CHILD,
        task_track_started=CELERY_TASK_TRACK_STARTED,
        task_time_limit=CELERY_TASK_TIME_LIMIT,
        task_soft_time_limit=CELERY_TASK_SOFT_TIME_LIMIT,
        task_acks_late=CELERY_TASK_ACKS_LATE,
        worker_send_task_events=CELERY_WORKER_SEND_TASK_EVENTS,
        result_expires=CELERY_RESULT_EXPIRES,
        send_events=CELERY_SEND_EVENTS,
        task_reject_on_worker_lost=CELERY_TASK_REJECT_ON_WORKER_LOST,
        task_default_retry_delay=CELERY_TASK_DEFAULT_RETRY_DELAY,
        task_max_retries=CELERY_TASK_MAX_RETRIES,
        beat_schedule=CELERYBEAT_SCHEDULE,
    )
    
    return celery

# Create Celery instance
celery = create_celery_app()

# Global analyzer manager instance
_analyzer_manager = None

def get_analyzer_manager():
    """Get or create analyzer manager instance."""
    global _analyzer_manager
    if _analyzer_manager is None and AnalyzerManager is not None:
        try:
            _analyzer_manager = AnalyzerManager()
        except Exception as e:
            print(f"Failed to create analyzer manager: {e}")
            return None
    return _analyzer_manager

def update_task_progress(current: int, total: int, status: Optional[str] = None, metadata: Optional[Dict] = None):
    """Update task progress for monitoring."""
    if not current_task:
        return
    
    progress_data = {
        'current': current,
        'total': total,
        'percentage': int((current / total) * 100) if total > 0 else 0,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    
    if status:
        progress_data['status'] = status
    
    if metadata:
        progress_data.update(metadata)
    
    try:
        current_task.update_state(
            state='PROGRESS',
            meta=progress_data
        )
    except Exception as e:
        print(f"Failed to update task progress: {e}")

# =============================================================================
# ANALYZER ORCHESTRATION TASKS
# =============================================================================

@celery.task(bind=True, name='app.tasks.security_analysis_task')
def security_analysis_task(self, model_slug: str, app_number: int, 
                          tools: Optional[List[str]] = None, options: Optional[Dict] = None):
    """
    Run security analysis on a specific model application.
    
    Args:
        model_slug: Model identifier (e.g., 'openai_gpt-4')
        app_number: Application number (1-30)
        tools: List of security tools to run
        options: Additional analysis options
    """
    
    try:
        analyzer_manager = get_analyzer_manager()
        if not analyzer_manager:
            raise Exception("Analyzer manager not available")
        
        update_task_progress(0, 100, "Initializing security analysis")
        
        # Default tools if not specified
        if not tools:
            tools = ['bandit', 'safety', 'semgrep']
        
        # Create analysis request (remove if not used in actual implementation)
        if AnalysisRequest:
            _ = AnalysisRequest(
                model_slug=model_slug,
                app_number=app_number,
                analysis_type='security',
                options=options or {},
                timeout=options.get('timeout', 600) if options else 600
            )
        
        update_task_progress(10, 100, "Starting analyzer services")
        
        # Ensure analyzer services are running
        if not analyzer_manager.start_services():
            raise Exception("Failed to start analyzer services")
        
        update_task_progress(20, 100, "Running security analysis")
        
        # Run the analysis
        results = {}
        total_tools = len(tools)
        
        for i, tool in enumerate(tools):
            update_task_progress(
                20 + (i * 60 // total_tools), 
                100, 
                f"Running {tool} analysis"
            )
            
            try:
                tool_result = analyzer_manager.run_security_analysis(
                    model_slug, app_number, tool, options
                )
                results[tool] = tool_result
            except Exception as e:
                results[tool] = {'error': str(e), 'status': 'failed'}
        
        update_task_progress(80, 100, "Processing results")
        
        # Aggregate results
        final_result = {
            'model_slug': model_slug,
            'app_number': app_number,
            'analysis_type': 'security',
            'tools': tools,
            'results': results,
            'summary': _create_security_summary(results),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'status': 'completed'
        }
        
        update_task_progress(100, 100, "Analysis completed")
        
        return final_result
        
    except Exception as e:
        error_msg = f"Security analysis failed: {str(e)}"
        update_task_progress(0, 100, f"Error: {error_msg}")
        raise self.retry(exc=e, countdown=60, max_retries=3)

@celery.task(bind=True, name='app.tasks.performance_test_task')
def performance_test_task(self, model_slug: str, app_number: int, 
                         test_config: Dict = None):
    """
    Run performance testing on a specific model application.
    
    Args:
        model_slug: Model identifier
        app_number: Application number
        test_config: Performance test configuration
    """
    
    try:
        analyzer_manager = get_analyzer_manager()
        if not analyzer_manager:
            raise Exception("Analyzer manager not available")
        
        update_task_progress(0, 100, "Initializing performance testing")
        
        # Default configuration
        config = test_config or {
            'users': 10,
            'spawn_rate': 2,
            'duration': 300,  # 5 minutes
            'host': f'http://localhost:800{app_number}'
        }
        
        update_task_progress(10, 100, "Starting analyzer services")
        
        if not analyzer_manager.start_services():
            raise Exception("Failed to start analyzer services")
        
        update_task_progress(20, 100, "Running performance tests")
        
        # Run performance test
        result = analyzer_manager.run_performance_test(
            model_slug, app_number, config
        )
        
        update_task_progress(80, 100, "Processing performance results")
        
        final_result = {
            'model_slug': model_slug,
            'app_number': app_number,
            'analysis_type': 'performance',
            'config': config,
            'result': result,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'status': 'completed'
        }
        
        update_task_progress(100, 100, "Performance testing completed")
        
        return final_result
        
    except Exception as e:
        error_msg = f"Performance testing failed: {str(e)}"
        update_task_progress(0, 100, f"Error: {error_msg}")
        raise self.retry(exc=e, countdown=60, max_retries=3)

@celery.task(bind=True, name='app.tasks.static_analysis_task')
def static_analysis_task(self, model_slug: str, app_number: int,
                        tools: List[str] = None, options: Dict = None):
    """
    Run static code analysis on a specific model application.
    
    Args:
        model_slug: Model identifier
        app_number: Application number
        tools: List of static analysis tools
        options: Additional analysis options
    """
    
    try:
        analyzer_manager = get_analyzer_manager()
        if not analyzer_manager:
            raise Exception("Analyzer manager not available")
        
        update_task_progress(0, 100, "Initializing static analysis")
        
        # Default tools
        if not tools:
            tools = ['pylint', 'flake8', 'mypy', 'eslint']
        
        update_task_progress(10, 100, "Starting analyzer services")
        
        if not analyzer_manager.start_services():
            raise Exception("Failed to start analyzer services")
        
        update_task_progress(20, 100, "Running static analysis")
        
        results = {}
        total_tools = len(tools)
        
        for i, tool in enumerate(tools):
            update_task_progress(
                20 + (i * 60 // total_tools),
                100,
                f"Running {tool} analysis"
            )
            
            try:
                tool_result = analyzer_manager.run_static_analysis(
                    model_slug, app_number, tool, options
                )
                results[tool] = tool_result
            except Exception as e:
                results[tool] = {'error': str(e), 'status': 'failed'}
        
        update_task_progress(80, 100, "Processing static analysis results")
        
        final_result = {
            'model_slug': model_slug,
            'app_number': app_number,
            'analysis_type': 'static',
            'tools': tools,
            'results': results,
            'summary': _create_static_summary(results),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'status': 'completed'
        }
        
        update_task_progress(100, 100, "Static analysis completed")
        
        return final_result
        
    except Exception as e:
        error_msg = f"Static analysis failed: {str(e)}"
        update_task_progress(0, 100, f"Error: {error_msg}")
        raise self.retry(exc=e, countdown=60, max_retries=3)

@celery.task(bind=True, name='app.tasks.ai_analysis_task')
def ai_analysis_task(self, model_slug: str, app_number: int,
                    analysis_types: List[str] = None, options: Dict = None):
    """
    Run AI-powered code analysis on a specific model application.
    
    Args:
        model_slug: Model identifier
        app_number: Application number
        analysis_types: Types of AI analysis to perform
        options: Additional analysis options
    """
    
    try:
        analyzer_manager = get_analyzer_manager()
        if not analyzer_manager:
            raise Exception("Analyzer manager not available")
        
        update_task_progress(0, 100, "Initializing AI analysis")
        
        # Default analysis types
        if not analysis_types:
            analysis_types = ['code_quality', 'security_review', 'architecture_analysis']
        
        update_task_progress(10, 100, "Starting analyzer services")
        
        if not analyzer_manager.start_services():
            raise Exception("Failed to start analyzer services")
        
        update_task_progress(20, 100, "Running AI analysis")
        
        results = {}
        total_types = len(analysis_types)
        
        for i, analysis_type in enumerate(analysis_types):
            update_task_progress(
                20 + (i * 60 // total_types),
                100,
                f"Running {analysis_type} analysis"
            )
            
            try:
                result = analyzer_manager.run_ai_analysis(
                    model_slug, app_number, analysis_type, options
                )
                results[analysis_type] = result
            except Exception as e:
                results[analysis_type] = {'error': str(e), 'status': 'failed'}
        
        update_task_progress(80, 100, "Processing AI analysis results")
        
        final_result = {
            'model_slug': model_slug,
            'app_number': app_number,
            'analysis_type': 'ai',
            'analysis_types': analysis_types,
            'results': results,
            'summary': _create_ai_summary(results),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'status': 'completed'
        }
        
        update_task_progress(100, 100, "AI analysis completed")
        
        return final_result
        
    except Exception as e:
        error_msg = f"AI analysis failed: {str(e)}"
        update_task_progress(0, 100, f"Error: {error_msg}")
        raise self.retry(exc=e, countdown=60, max_retries=3)

@celery.task(bind=True, name='app.tasks.batch_analysis_task')
def batch_analysis_task(self, models: List[str], apps: List[int],
                       analysis_types: List[str], options: Dict = None):
    """
    Run batch analysis across multiple models and applications.
    
    Args:
        models: List of model slugs
        apps: List of application numbers
        analysis_types: Types of analysis to perform
        options: Additional options
    """
    
    try:
        analyzer_manager = get_analyzer_manager()
        if not analyzer_manager:
            raise Exception("Analyzer manager not available")
        
        total_tasks = len(models) * len(apps) * len(analysis_types)
        current_task_num = 0
        
        update_task_progress(0, total_tasks, "Initializing batch analysis")
        
        if not analyzer_manager.start_services():
            raise Exception("Failed to start analyzer services")
        
        results = {}
        
        for model in models:
            results[model] = {}
            
            for app in apps:
                results[model][app] = {}
                
                for analysis_type in analysis_types:
                    current_task_num += 1
                    update_task_progress(
                        current_task_num, 
                        total_tasks,
                        f"Analyzing {model} app {app} - {analysis_type}"
                    )
                    
                    try:
                        if analysis_type == 'security':
                            result = analyzer_manager.run_security_analysis(
                                model, app, options.get('security_tools', []), options
                            )
                        elif analysis_type == 'performance':
                            result = analyzer_manager.run_performance_test(
                                model, app, options.get('performance_config', {})
                            )
                        elif analysis_type == 'static':
                            result = analyzer_manager.run_static_analysis(
                                model, app, options.get('static_tools', []), options
                            )
                        elif analysis_type == 'ai':
                            result = analyzer_manager.run_ai_analysis(
                                model, app, options.get('ai_types', []), options
                            )
                        else:
                            result = {'error': f'Unknown analysis type: {analysis_type}'}
                        
                        results[model][app][analysis_type] = result
                        
                    except Exception as e:
                        results[model][app][analysis_type] = {
                            'error': str(e), 
                            'status': 'failed'
                        }
        
        final_result = {
            'batch_id': self.request.id,
            'models': models,
            'apps': apps,
            'analysis_types': analysis_types,
            'results': results,
            'summary': _create_batch_summary(results),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'status': 'completed'
        }
        
        update_task_progress(total_tasks, total_tasks, "Batch analysis completed")
        
        return final_result
        
    except Exception as e:
        error_msg = f"Batch analysis failed: {str(e)}"
        update_task_progress(0, 0, f"Error: {error_msg}")
        raise self.retry(exc=e, countdown=120, max_retries=2)

# =============================================================================
# CONTAINER MANAGEMENT TASKS
# =============================================================================

@celery.task(bind=True, name='app.tasks.container_management_task')
def container_management_task(self, action: str, service: str = None):
    """
    Manage analyzer container operations.
    
    Args:
        action: Action to perform (start, stop, restart, status)
        service: Specific service name (optional)
    """
    
    try:
        analyzer_manager = get_analyzer_manager()
        if not analyzer_manager:
            raise Exception("Analyzer manager not available")
        
        update_task_progress(0, 100, f"Performing {action} operation")
        
        if action == 'start':
            result = analyzer_manager.start_services()
            status = "Services started successfully" if result else "Failed to start services"
        elif action == 'stop':
            result = analyzer_manager.stop_services()
            status = "Services stopped successfully" if result else "Failed to stop services"
        elif action == 'restart':
            result = analyzer_manager.restart_services()
            status = "Services restarted successfully" if result else "Failed to restart services"
        elif action == 'status':
            result = analyzer_manager.get_container_status()
            status = "Status retrieved successfully"
        else:
            raise ValueError(f"Unknown action: {action}")
        
        update_task_progress(100, 100, status)
        
        return {
            'action': action,
            'service': service,
            'result': result,
            'status': status,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        error_msg = f"Container management failed: {str(e)}"
        update_task_progress(0, 100, f"Error: {error_msg}")
        raise self.retry(exc=e, countdown=30, max_retries=3)

# =============================================================================
# MONITORING TASKS
# =============================================================================

@celery.task(name='app.tasks.health_check_analyzers')
def health_check_analyzers():
    """Periodic health check of analyzer services."""
    
    try:
        analyzer_manager = get_analyzer_manager()
        if not analyzer_manager:
            return {'status': 'error', 'message': 'Analyzer manager not available'}
        
        status = analyzer_manager.get_container_status()
        
        health_summary = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'services': status,
            'healthy_count': sum(1 for service in status.values() if service.get('status') == 'running'),
            'total_count': len(status),
            'overall_status': 'healthy' if all(s.get('status') == 'running' for s in status.values()) else 'degraded'
        }
        
        return health_summary
        
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

@celery.task(name='app.tasks.monitor_analyzer_containers')
def monitor_analyzer_containers():
    """Monitor analyzer container resources and performance."""
    
    try:
        analyzer_manager = get_analyzer_manager()
        if not analyzer_manager:
            return {'status': 'error', 'message': 'Analyzer manager not available'}
        
        # Get container statistics
        containers = analyzer_manager.get_container_status()
        
        monitoring_data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'containers': containers,
            'alerts': [],
            'recommendations': []
        }
        
        # Check for issues and generate alerts
        for name, info in containers.items():
            if info.get('status') != 'running':
                monitoring_data['alerts'].append({
                    'severity': 'high',
                    'service': name,
                    'message': f'Container {name} is not running'
                })
        
        return monitoring_data
        
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

@celery.task(name='app.tasks.cleanup_expired_results')
def cleanup_expired_results():
    """Clean up expired analysis results and temporary files."""
    
    try:
        # This would integrate with your database models to clean up old results
        cleanup_summary = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'cleaned_files': 0,
            'cleaned_records': 0,
            'freed_space': 0
        }
        
        # Add actual cleanup logic here
        
        return cleanup_summary
        
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _create_security_summary(results: Dict) -> Dict:
    """Create summary from security analysis results."""
    
    total_issues = 0
    severity_counts = {'low': 0, 'medium': 0, 'high': 0, 'critical': 0}
    tools_run = len(results)
    successful_tools = sum(1 for r in results.values() if r.get('status') != 'failed')
    
    for tool_result in results.values():
        if isinstance(tool_result, dict) and 'issues' in tool_result:
            issues = tool_result['issues']
            total_issues += len(issues)
            
            for issue in issues:
                severity = issue.get('severity', 'low').lower()
                if severity in severity_counts:
                    severity_counts[severity] += 1
    
    return {
        'total_issues': total_issues,
        'severity_distribution': severity_counts,
        'tools_run': tools_run,
        'successful_tools': successful_tools,
        'success_rate': (successful_tools / tools_run * 100) if tools_run > 0 else 0
    }

def _create_static_summary(results: Dict) -> Dict:
    """Create summary from static analysis results."""
    
    total_violations = 0
    tools_run = len(results)
    successful_tools = sum(1 for r in results.values() if r.get('status') != 'failed')
    
    for tool_result in results.values():
        if isinstance(tool_result, dict) and 'violations' in tool_result:
            total_violations += len(tool_result['violations'])
    
    return {
        'total_violations': total_violations,
        'tools_run': tools_run,
        'successful_tools': successful_tools,
        'success_rate': (successful_tools / tools_run * 100) if tools_run > 0 else 0
    }

def _create_ai_summary(results: Dict) -> Dict:
    """Create summary from AI analysis results."""
    
    analysis_types = len(results)
    successful_analyses = sum(1 for r in results.values() if r.get('status') != 'failed')
    
    return {
        'analysis_types': analysis_types,
        'successful_analyses': successful_analyses,
        'success_rate': (successful_analyses / analysis_types * 100) if analysis_types > 0 else 0
    }

def _create_batch_summary(results: Dict) -> Dict:
    """Create summary from batch analysis results."""
    
    total_analyses = 0
    successful_analyses = 0
    
    for model_results in results.values():
        for app_results in model_results.values():
            for analysis_result in app_results.values():
                total_analyses += 1
                if analysis_result.get('status') != 'failed':
                    successful_analyses += 1
    
    return {
        'total_analyses': total_analyses,
        'successful_analyses': successful_analyses,
        'success_rate': (successful_analyses / total_analyses * 100) if total_analyses > 0 else 0,
        'models_analyzed': len(results),
        'apps_per_model': len(list(results.values())[0]) if results else 0
    }

# =============================================================================
# CELERY SIGNALS
# =============================================================================

@task_prerun.connect
def task_prerun_handler(task_id, task, *args, **kwargs):
    """Handle task pre-execution setup."""
    print(f"Starting task {task.name} with ID {task_id}")

@task_postrun.connect
def task_postrun_handler(task_id, task, retval, state, *args, **kwargs):
    """Handle task post-execution cleanup."""
    print(f"Completed task {task.name} with ID {task_id}, state: {state}")

@worker_ready.connect
def worker_ready_handler(sender, **kwargs):
    """Handle worker ready event."""
    print(f"Celery worker {sender} is ready and connected to analyzer infrastructure")

if __name__ == '__main__':
    print("Celery tasks module loaded successfully")
    print(f"Available tasks: {list(celery.tasks.keys())}")
