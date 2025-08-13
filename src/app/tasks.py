"""
Celery Integration for AI Research Platform
==========================================

Celery application factory and task definitions for orchestrating
containerized analyzer services through analyzer integration.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from celery import Celery
from celery.signals import task_prerun, task_postrun, worker_ready

# Import analyzer integration service
try:
    from app.services.analyzer_integration import get_analyzer_integration as _get_analyzer_integration
    from app.services.batch_service import batch_service
    
    _analyzer_integration_available = True
        
except ImportError:
    print("Warning: Could not import analyzer integration service.")
    
    _analyzer_integration_available = False
    _get_analyzer_integration = None
    batch_service = None

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

def get_analyzer_service():
    """Get analyzer integration service instance."""
    try:
        if _analyzer_integration_available and _get_analyzer_integration:
            return _get_analyzer_integration()
        return None
    except Exception as e:
        print(f"Failed to get analyzer integration: {e}")
        return None

def update_task_progress(current: int, total: int, status: Optional[str] = None, metadata: Optional[Dict] = None):
    """Update task progress for monitoring."""
    # Simplified version to avoid type checking issues
    # In a real implementation, this would update Celery task state
    print(f"Task progress: {current}/{total} ({int((current/total)*100) if total > 0 else 0}%) - {status or 'running'}")

def update_batch_progress(batch_job_id: Optional[str], task_completed: bool = False, 
                         task_failed: bool = False, result: Optional[Dict] = None):
    """Update batch job progress."""
    if batch_service and batch_job_id:
        try:
            batch_service.update_task_progress(
                batch_job_id, task_completed, task_failed, result
            )
        except Exception as e:
            print(f"Failed to update batch progress: {e}")

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
    
    batch_job_id = options.get('batch_job_id') if options else None
    analysis_id = options.get('analysis_id') if options else None

    # Import here to avoid circular import at module load
    from app.extensions import get_session
    from app.models import SecurityAnalysis
    from app.constants import AnalysisStatus
    import json as _json

    try:
        analyzer_service = get_analyzer_service()
        if not analyzer_service:
            raise Exception("Analyzer service not available")

        update_task_progress(0, 100, "Initializing security analysis")

        # Fetch analysis record (if provided) and mark RUNNING
        if analysis_id:
            with get_session() as session:
                analysis = session.query(SecurityAnalysis).get(analysis_id)
                if analysis:
                    analysis.status = AnalysisStatus.RUNNING
                    analysis.started_at = datetime.now(timezone.utc)
                    session.commit()

        # Default tools if not specified
        if not tools:
            tools = ['bandit', 'safety', 'pylint']

        update_task_progress(10, 100, "Starting analyzer services")

        if not analyzer_service.start_analyzer_services():
            raise Exception("Failed to start analyzer services")

        update_task_progress(20, 100, "Running security analysis")

        # Run the analysis using analyzer integration
        result = analyzer_service.run_security_analysis(
            model_slug, app_number, tools, options
        )

        update_task_progress(80, 100, "Processing results")

        status = result.get('status', 'completed')

        # Persist results
        if analysis_id:
            with get_session() as session:
                analysis = session.query(SecurityAnalysis).get(analysis_id)
                if analysis:
                    analysis.status = AnalysisStatus.COMPLETED if status == 'completed' else AnalysisStatus.FAILED
                    analysis.completed_at = datetime.now(timezone.utc)
                    if analysis.started_at:
                        analysis.analysis_duration = (analysis.completed_at - analysis.started_at).total_seconds()
                    # Store raw result JSON
                    try:
                        analysis.results_json = _json.dumps(result)
                    except Exception:
                        analysis.results_json = _json.dumps({'raw_result': str(result)})

                    # Update summary counts if present
                    summary = result.get('summary') or {}
                    # Some analyzers may return counts at top-level
                    analysis.total_issues = summary.get('total_issues') or result.get('total_issues') or 0
                    analysis.critical_severity_count = summary.get('critical') or result.get('critical_count') or 0
                    analysis.high_severity_count = summary.get('high') or result.get('high_count') or 0
                    analysis.medium_severity_count = summary.get('medium') or result.get('medium_count') or 0
                    analysis.low_severity_count = summary.get('low') or result.get('low_count') or 0
                    # Track tools run
                    if isinstance(tools, list):
                        analysis.tools_run_count = len(tools)
                    session.commit()

        # Prepare final return payload
        final_result = {
            'model_slug': model_slug,
            'app_number': app_number,
            'analysis_type': 'security',
            'tools': tools,
            'result': result,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'status': status,
            'analysis_id': analysis_id
        }

        update_batch_progress(batch_job_id, task_completed=True, result=final_result)
        update_task_progress(100, 100, "Analysis completed")
        return final_result

    except Exception as e:
        error_msg = f"Security analysis failed: {str(e)}"
        update_task_progress(0, 100, f"Error: {error_msg}")

        # Mark analysis failed immediately (avoid leaving RUNNING) before retry
        if analysis_id:
            try:
                with get_session() as session:
                    analysis = session.query(SecurityAnalysis).get(analysis_id)
                    if analysis:
                        analysis.status = AnalysisStatus.FAILED
                        analysis.completed_at = datetime.now(timezone.utc)
                        if analysis.started_at:
                            analysis.analysis_duration = (analysis.completed_at - analysis.started_at).total_seconds()
                        # Append error metadata
                        meta = analysis.get_metadata() if hasattr(analysis, 'get_metadata') else {}
                        meta['last_error'] = str(e)
                        if hasattr(analysis, 'set_metadata'):
                            analysis.set_metadata(meta)
                        session.commit()
            except Exception as meta_e:
                print(f"Failed to record failure metadata: {meta_e}")

        update_batch_progress(batch_job_id, task_failed=True)

        # Decide whether to retry: only retry transient infrastructure errors
        transient = any(msg in str(e).lower() for msg in ["timeout", "connection refused", "temporary", "unavailable"])
        if transient and getattr(self, 'request', None) and self.request.retries < 3:
            raise self.retry(exc=e, countdown=60, max_retries=3)
        # Non-transient: raise without retry so status stays FAILED
        raise

@celery.task(bind=True, name='app.tasks.performance_test_task')
def performance_test_task(self, model_slug: str, app_number: int, 
                         test_config: Optional[Dict] = None):
    """
    Run performance testing on a specific model application.
    
    Args:
        model_slug: Model identifier
        app_number: Application number
        test_config: Performance test configuration
    """
    
    batch_job_id = test_config.get('batch_job_id') if test_config else None
    
    try:
        analyzer_service = get_analyzer_service()
        if not analyzer_service:
            raise Exception("Analyzer service not available")
        
        update_task_progress(0, 100, "Initializing performance testing")
        
        # Default configuration
        config = test_config or {
            'users': 10,
            'spawn_rate': 2,
            'duration': 300,
            'host': f'http://localhost:800{app_number}'
        }
        
        update_task_progress(10, 100, "Starting analyzer services")
        
        if not analyzer_service.start_analyzer_services():
            raise Exception("Failed to start analyzer services")
        
        update_task_progress(20, 100, "Running performance tests")
        
        # Run performance test using analyzer integration
        result = analyzer_service.run_performance_test(
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
            'status': result.get('status', 'completed')
        }
        
        # Update batch progress if this is part of a batch
        update_batch_progress(batch_job_id, task_completed=True, result=final_result)
        
        update_task_progress(100, 100, "Performance testing completed")
        
        return final_result
        
    except Exception as e:
        error_msg = f"Performance testing failed: {str(e)}"
        update_task_progress(0, 100, f"Error: {error_msg}")
        
        # Update batch progress for failed task
        update_batch_progress(batch_job_id, task_failed=True)
        
        raise self.retry(exc=e, countdown=60, max_retries=3)

@celery.task(bind=True, name='app.tasks.static_analysis_task')
def static_analysis_task(self, model_slug: str, app_number: int,
                        tools: Optional[List[str]] = None, options: Optional[Dict] = None):
    """
    Run static code analysis on a specific model application.
    
    Args:
        model_slug: Model identifier
        app_number: Application number
        tools: List of static analysis tools
        options: Additional analysis options
    """
    
    batch_job_id = options.get('batch_job_id') if options else None
    
    try:
        analyzer_service = get_analyzer_service()
        if not analyzer_service:
            raise Exception("Analyzer service not available")
        
        update_task_progress(0, 100, "Initializing static analysis")
        
        # Default tools
        if not tools:
            tools = ['pylint', 'flake8']
        
        update_task_progress(10, 100, "Starting analyzer services")
        
        if not analyzer_service.start_analyzer_services():
            raise Exception("Failed to start analyzer services")
        
        update_task_progress(20, 100, "Running static analysis")
        
        # Run static analysis using analyzer integration
        result = analyzer_service.run_static_analysis(
            model_slug, app_number, tools, options
        )
        
        update_task_progress(80, 100, "Processing static analysis results")
        
        final_result = {
            'model_slug': model_slug,
            'app_number': app_number,
            'analysis_type': 'static',
            'tools': tools,
            'result': result,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'status': result.get('status', 'completed')
        }
        
        # Update batch progress if this is part of a batch
        update_batch_progress(batch_job_id, task_completed=True, result=final_result)
        
        update_task_progress(100, 100, "Static analysis completed")
        
        return final_result
        
    except Exception as e:
        error_msg = f"Static analysis failed: {str(e)}"
        update_task_progress(0, 100, f"Error: {error_msg}")
        
        # Update batch progress for failed task
        update_batch_progress(batch_job_id, task_failed=True)
        
        raise self.retry(exc=e, countdown=60, max_retries=3)

@celery.task(bind=True, name='app.tasks.ai_analysis_task')
def ai_analysis_task(self, model_slug: str, app_number: int,
                    analysis_types: Optional[List[str]] = None, options: Optional[Dict] = None):
    """
    Run AI-powered code analysis on a specific model application.
    
    Args:
        model_slug: Model identifier
        app_number: Application number
        analysis_types: Types of AI analysis to perform
        options: Additional analysis options
    """
    
    batch_job_id = options.get('batch_job_id') if options else None
    
    try:
        analyzer_service = get_analyzer_service()
        if not analyzer_service:
            raise Exception("Analyzer service not available")
        
        update_task_progress(0, 100, "Initializing AI analysis")
        
        # Default analysis types
        if not analysis_types:
            analysis_types = ['code_quality', 'security_review']
        
        update_task_progress(10, 100, "Starting analyzer services")
        
        if not analyzer_service.start_analyzer_services():
            raise Exception("Failed to start analyzer services")
        
        update_task_progress(20, 100, "Running AI analysis")
        
        # Run AI analysis using analyzer integration
        result = analyzer_service.run_ai_analysis(
            model_slug, app_number, analysis_types, options
        )
        
        update_task_progress(80, 100, "Processing AI analysis results")
        
        final_result = {
            'model_slug': model_slug,
            'app_number': app_number,
            'analysis_type': 'ai',
            'analysis_types': analysis_types,
            'result': result,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'status': result.get('status', 'completed')
        }
        
        # Update batch progress if this is part of a batch
        update_batch_progress(batch_job_id, task_completed=True, result=final_result)
        
        update_task_progress(100, 100, "AI analysis completed")
        
        return final_result
        
    except Exception as e:
        error_msg = f"AI analysis failed: {str(e)}"
        update_task_progress(0, 100, f"Error: {error_msg}")
        
        # Update batch progress for failed task
        update_batch_progress(batch_job_id, task_failed=True)
        
        raise self.retry(exc=e, countdown=60, max_retries=3)

@celery.task(bind=True, name='app.tasks.batch_analysis_task')
def batch_analysis_task(self, models: List[str], apps: List[int],
                       analysis_types: List[str], options: Optional[Dict] = None):
    """
    Run batch analysis across multiple models and applications.
    
    Args:
        models: List of model slugs
        apps: List of application numbers
        analysis_types: Types of analysis to perform
        options: Additional options
    """
    
    batch_job_id = options.get('batch_job_id') if options else None
    
    try:
        analyzer_service = get_analyzer_service()
        if not analyzer_service:
            raise Exception("Analyzer service not available")
        
        update_task_progress(0, 100, "Initializing batch analysis")
        
        total_tasks = len(models) * len(apps) * len(analysis_types)
        completed_tasks = 0
        results = {}
        
        update_task_progress(5, 100, "Starting analyzer services")
        
        if not analyzer_service.start_analyzer_services():
            raise Exception("Failed to start analyzer services")
        
        for model in models:
            model_results = {}
            for app in apps:
                app_results = {}
                for analysis_type in analysis_types:
                    try:
                        if analysis_type == 'security':
                            result = analyzer_service.run_security_analysis(
                                model, app, 
                                options.get('security_tools', ['bandit']) if options else ['bandit'], 
                                options
                            )
                        elif analysis_type == 'performance':
                            result = analyzer_service.run_performance_test(
                                model, app, 
                                options.get('performance_config', {}) if options else {}
                            )
                        elif analysis_type == 'static':
                            result = analyzer_service.run_static_analysis(
                                model, app, 
                                options.get('static_tools', ['pylint']) if options else ['pylint'], 
                                options
                            )
                        elif analysis_type == 'ai':
                            result = analyzer_service.run_ai_analysis(
                                model, app, 
                                options.get('ai_types', ['code_quality']) if options else ['code_quality'], 
                                options
                            )
                        else:
                            result = {'status': 'failed', 'error': f'Unknown analysis type: {analysis_type}'}
                        
                        app_results[analysis_type] = result
                        completed_tasks += 1
                        
                        progress = int((completed_tasks / total_tasks) * 90) + 5
                        update_task_progress(
                            progress, 100, 
                            f"Completed {analysis_type} for {model} app {app}"
                        )
                        
                    except Exception as e:
                        app_results[analysis_type] = {'status': 'failed', 'error': str(e)}
                        completed_tasks += 1
                
                model_results[f'app_{app}'] = app_results
            
            results[model] = model_results
        
        update_task_progress(95, 100, "Processing batch results")
        
        final_result = {
            'models': models,
            'apps': apps,
            'analysis_types': analysis_types,
            'results': results,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'status': 'completed',
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks
        }
        
        # Update batch progress if this is part of a batch
        update_batch_progress(batch_job_id, task_completed=True, result=final_result)
        
        update_task_progress(100, 100, "Batch analysis completed")
        
        return final_result
        
    except Exception as e:
        error_msg = f"Batch analysis failed: {str(e)}"
        update_task_progress(0, 100, f"Error: {error_msg}")
        
        # Update batch progress for failed task
        update_batch_progress(batch_job_id, task_failed=True)
        
        raise self.retry(exc=e, countdown=120, max_retries=2)

# =============================================================================
# CONTAINER MANAGEMENT TASKS
# =============================================================================

@celery.task(bind=True, name='app.tasks.container_management_task')
def container_management_task(self, action: str, service: Optional[str] = None):
    """
    Manage analyzer container operations.
    
    Args:
        action: Action to perform (start, stop, restart, status)
        service: Specific service name (optional)
    """
    
    try:
        analyzer_service = get_analyzer_service()
        if not analyzer_service:
            raise Exception("Analyzer service not available")
        
        update_task_progress(0, 100, f"Performing {action} on containers")
        
        if action == 'start':
            result = analyzer_service.start_analyzer_services()
        elif action == 'stop':
            result = analyzer_service.stop_analyzer_services()
        elif action == 'restart':
            result = analyzer_service.restart_analyzer_services()
        elif action == 'status':
            result = analyzer_service.get_services_status()
        else:
            raise ValueError(f"Unknown action: {action}")
        
        update_task_progress(100, 100, f"Container {action} completed")
        
        return {
            'action': action,
            'service': service,
            'result': result,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'status': 'completed'
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
        analyzer_service = get_analyzer_service()
        if not analyzer_service:
            return {'status': 'unavailable', 'error': 'Analyzer service not available'}
        
        health_result = analyzer_service.health_check()
        
        return {
            'health_check': health_result,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'status': 'completed'
        }
        
    except Exception as e:
        return {
            'status': 'failed',
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

@celery.task(name='app.tasks.monitor_analyzer_containers')
def monitor_analyzer_containers():
    """Monitor analyzer container resources and performance."""
    
    try:
        analyzer_service = get_analyzer_service()
        if not analyzer_service:
            return {'status': 'unavailable', 'error': 'Analyzer service not available'}
        
        status_info = analyzer_service.get_services_status()
        
        return {
            'monitoring': status_info,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'status': 'completed'
        }
        
    except Exception as e:
        return {
            'status': 'failed',
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

@celery.task(name='app.tasks.cleanup_expired_results')
def cleanup_expired_results():
    """Clean up expired analysis results and temporary files."""
    
    try:
        # This would clean up old results from database and filesystem
        # For now, just return a placeholder result
        return {
            'cleanup': {'files_cleaned': 0, 'results_cleaned': 0},
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'status': 'completed'
        }
        
    except Exception as e:
        return {
            'status': 'failed',
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
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


@celery.task(bind=True, name='app.tasks.run_enhanced_analysis')
def run_enhanced_analysis(self, model_slug: str, app_number: int, config: Dict) -> Dict:
    """
    Run enhanced analysis with custom configuration.
    
    This task orchestrates multiple analyzer services with enhanced configuration
    options for comprehensive testing.
    
    Args:
        model_slug: The model identifier (e.g., 'anthropic_claude-3.5-sonnet')
        app_number: The application number to analyze
        config: Enhanced configuration dict with tool-specific settings
        
    Returns:
        Dict containing analysis results and metadata
    """
    task_id = self.request.id
    print(f"Starting enhanced analysis task {task_id} for {model_slug} app {app_number}")
    
    try:
        # Import the analyzer configuration system
        import sys
        import os
        analyzer_path = os.path.join(os.path.dirname(__file__), '..', '..', 'analyzer')
        if analyzer_path not in sys.path:
            sys.path.append(analyzer_path)
        
        from analyzer_config import AnalyzerConfig
        
        # Initialize analyzer configuration
        analyzer_config = AnalyzerConfig()
        
        # Validate the full configuration
        validation_result = analyzer_config.validate_full_config(config)
        if not validation_result['valid']:
            return {
                'status': 'error',
                'error': 'Configuration validation failed',
                'validation_errors': validation_result['errors'],
                'task_id': task_id
            }
        
        # Get analyzer integration service
        if not _analyzer_integration_available:
            return {
                'status': 'error',
                'error': 'Analyzer integration service not available',
                'task_id': task_id
            }
        
        analyzer_integration = _get_analyzer_integration()
        results = {}
        
        # Update task progress
        self.update_state(state='PROGRESS', meta={'stage': 'starting', 'progress': 0})
        
        # Run static analysis with enhanced configuration
        if config.get('static'):
            print(f"Running enhanced static analysis for {model_slug} app {app_number}")
            self.update_state(state='PROGRESS', meta={'stage': 'static_analysis', 'progress': 20})
            
            static_result = analyzer_integration.run_static_analysis(
                model_slug, app_number, config['static']
            )
            results['static_analysis'] = static_result
        
        # Run performance testing with enhanced configuration
        if config.get('performance'):
            print(f"Running enhanced performance testing for {model_slug} app {app_number}")
            self.update_state(state='PROGRESS', meta={'stage': 'performance_testing', 'progress': 50})
            
            performance_result = analyzer_integration.run_performance_test(
                model_slug, app_number, config['performance']
            )
            results['performance_testing'] = performance_result
        
        # Run AI analysis with enhanced configuration
        if config.get('ai'):
            print(f"Running enhanced AI analysis for {model_slug} app {app_number}")
            self.update_state(state='PROGRESS', meta={'stage': 'ai_analysis', 'progress': 80})
            
            ai_result = analyzer_integration.run_ai_analysis(
                model_slug, app_number, config['ai']
            )
            results['ai_analysis'] = ai_result
        
        # Compile final results
        self.update_state(state='PROGRESS', meta={'stage': 'finalizing', 'progress': 95})
        
        # Calculate overall scores and summary
        overall_results = {
            'status': 'completed',
            'task_id': task_id,
            'model_slug': model_slug,
            'app_number': app_number,
            'config_used': config,
            'analysis_results': results,
            'completed_at': datetime.now(timezone.utc).isoformat(),
            'summary': _generate_enhanced_summary(results)
        }
        
        # Save results to database
        _save_enhanced_results(overall_results)
        
        print(f"Enhanced analysis task {task_id} completed successfully")
        return overall_results
        
    except Exception as e:
        print(f"Enhanced analysis task {task_id} failed: {e}")
        error_result = {
            'status': 'error',
            'error': str(e),
            'task_id': task_id,
            'model_slug': model_slug,
            'app_number': app_number,
            'failed_at': datetime.now(timezone.utc).isoformat()
        }
        
        # Try to save error to database
        try:
            _save_enhanced_results(error_result)
        except Exception as save_error:
            print(f"Failed to save error results: {save_error}")
        
        # Re-raise for Celery to handle
        raise self.retry(exc=e, countdown=60, max_retries=3)


def _generate_enhanced_summary(results: Dict) -> Dict:
    """Generate summary from enhanced analysis results."""
    summary = {
        'total_analyses': 0,
        'successful_analyses': 0,
        'failed_analyses': 0,
        'overall_score': 0,
        'issues_found': 0,
        'recommendations': []
    }
    
    scores = []
    
    for analysis_type, result in results.items():
        summary['total_analyses'] += 1
        
        if result.get('status') == 'success':
            summary['successful_analyses'] += 1
            
            # Extract scores based on analysis type
            if analysis_type == 'static_analysis':
                if 'bandit' in result and result['bandit'].get('total_issues'):
                    summary['issues_found'] += result['bandit']['total_issues']
                if 'pylint' in result and result['pylint'].get('score'):
                    scores.append(result['pylint']['score'])
                    
            elif analysis_type == 'performance_testing':
                if 'apache_bench' in result and result['apache_bench'].get('requests_per_second'):
                    # Convert RPS to a 0-100 score (normalize based on expected performance)
                    rps = result['apache_bench']['requests_per_second']
                    score = min(100, (rps / 100) * 100)  # 100 RPS = 100% score
                    scores.append(score)
                    
            elif analysis_type == 'ai_analysis':
                if result.get('quality_score'):
                    scores.append(result['quality_score'])
        else:
            summary['failed_analyses'] += 1
    
    # Calculate overall score
    if scores:
        summary['overall_score'] = sum(scores) / len(scores)
    
    # Generate recommendations based on results
    if summary['issues_found'] > 10:
        summary['recommendations'].append('High number of security issues detected - review critical vulnerabilities')
    
    if summary['overall_score'] < 60:
        summary['recommendations'].append('Overall score is below acceptable threshold - consider code improvements')
    
    if summary['failed_analyses'] > 0:
        summary['recommendations'].append('Some analyses failed - check analyzer configuration and connectivity')
    
    return summary


def _save_enhanced_results(results: Dict) -> None:
    """Save enhanced analysis results to database."""
    try:
        from app.extensions import db
        from app.models import EnhancedAnalysis
        
        # Create enhanced analysis record
        analysis = EnhancedAnalysis(
            task_id=results['task_id'],
            model_slug=results['model_slug'],
            app_number=results['app_number'],
            status=results['status'],
            config_json=results.get('config_used', {}),
            results_json=results.get('analysis_results', {}),
            summary_json=results.get('summary', {}),
            overall_score=results.get('summary', {}).get('overall_score'),
            created_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc) if results['status'] == 'completed' else None
        )
        
        db.session.add(analysis)
        db.session.commit()
        
        print(f"Saved enhanced analysis results for task {results['task_id']}")
        
    except Exception as e:
        print(f"Failed to save enhanced analysis results: {e}")
        # Don't re-raise - this is not critical for task completion


if __name__ == '__main__':
    print("Celery tasks module loaded successfully")
    print(f"Available tasks: {list(celery.tasks.keys())}")
