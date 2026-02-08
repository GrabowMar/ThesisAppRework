"""
Celery Tasks
============

Distributed tasks for analysis execution with distributed locking
to prevent SQLite concurrency issues.
"""

import logging
import json
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List

from app.celery_worker import celery
from app.extensions import db
from app.models import AnalysisTask, AnalysisStatus
from app.utils.distributed_lock import database_write_lock

logger = logging.getLogger(__name__)


def _extract_total_issues(payload: Dict[str, Any]) -> int:
    """Extract total issue count from various result payload formats.
    
    Handles multiple result structures:
    1. Direct summary: {'summary': {'total_findings': N}}
    2. Comprehensive nested: {'results': {'summary': {...}, 'services': {...}}}
    3. Service-specific: {'services': {'static': {'analysis': {'results': {...}}}}}
    
    If the summary shows 0 but services contain actual findings, 
    we compute the real count from service results.
    """
    total_issues = 0
    
    # Try to get from summary first
    summary_issues = 0
    if 'summary' in payload:
        summary_issues = payload['summary'].get('total_findings', 0)
    elif 'results' in payload and isinstance(payload.get('results'), dict):
        results = payload['results']
        if 'summary' in results:
            summary_issues = results['summary'].get('total_findings', 0)
    
    # If summary shows issues, trust it
    if summary_issues > 0:
        return summary_issues
    
    # Otherwise, compute from service results (summary might be buggy)
    services_to_scan = {}
    
    # Check for services at different nesting levels
    if 'services' in payload:
        services_to_scan = payload['services']
    elif 'results' in payload and isinstance(payload.get('results'), dict):
        results = payload['results']
        if 'services' in results:
            services_to_scan = results['services']
    
    # Also check top-level service keys (static, dynamic, etc.)
    for key in ('static', 'dynamic', 'performance', 'ai', 'security'):
        if key in payload and isinstance(payload[key], dict):
            services_to_scan[key] = payload[key]
    
    # Extract issues from each service
    for svc_name, svc_result in services_to_scan.items():
        if not isinstance(svc_result, dict):
            continue
        
        # Try to get from service-level summary first
        # Analysis data may be at svc_result.analysis OR svc_result.payload.analysis
        svc_analysis = svc_result.get('analysis', {})
        if not isinstance(svc_analysis, dict) or not svc_analysis:
            payload_data = svc_result.get('payload', {})
            if isinstance(payload_data, dict):
                svc_analysis = payload_data.get('analysis', payload_data)
        
        if isinstance(svc_analysis, dict):
            svc_summary = svc_analysis.get('summary', {})
            if isinstance(svc_summary, dict):
                svc_total = (svc_summary.get('total_issues_found', 0) 
                           or svc_summary.get('total_findings', 0)
                           or svc_summary.get('vulnerabilities_found', 0))
                if svc_total > 0:
                    total_issues += svc_total
                    continue
            
            # Dive into tool results: analysis.results.{language}.{tool}.total_issues
            results_data = svc_analysis.get('results', {})
            if isinstance(results_data, dict):
                for lang_results in results_data.values():
                    if isinstance(lang_results, dict):
                        for tool_result in lang_results.values():
                            if isinstance(tool_result, dict):
                                # Use total_issues OR issue_count, not both (they're the same)
                                tool_issues = tool_result.get('total_issues', 0) or tool_result.get('issue_count', 0)
                                total_issues += tool_issues
    
    # Also check top-level tools dict (from aggregate_results unified payload)
    tools_data = payload.get('tools', {})
    if isinstance(tools_data, dict) and total_issues == 0:
        for tool_result in tools_data.values():
            if isinstance(tool_result, dict):
                total_issues += tool_result.get('total_issues', 0)
    
    return total_issues


@celery.task(bind=True, acks_late=True)
def execute_subtask(self, subtask_id: int, model_slug: str, app_number: int, tools: List[str], service_name: str) -> Dict[str, Any]:
    """
    Execute a single analysis subtask via WebSocket.
    
    Idempotency: If task is already RUNNING/COMPLETED/FAILED, skip re-execution.
    """
    import os
    import socket
    worker_identity = f"{socket.gethostname()}:{os.getpid()}"
    logger.info(f"[CELERY] Starting subtask {subtask_id} for {service_name} on {worker_identity}")

    try:
        # Get fresh subtask from DB
        subtask = AnalysisTask.query.get(subtask_id)
        if not subtask:
            return {'status': 'error', 'error': f'Subtask {subtask_id} not found'}

        # Idempotency guard: Skip if already in a terminal or running state
        if subtask.status in (AnalysisStatus.RUNNING, AnalysisStatus.COMPLETED, 
                              AnalysisStatus.FAILED, AnalysisStatus.PARTIAL_SUCCESS):
            logger.info(f"[CELERY] Subtask {subtask_id} already in state {subtask.status.value}, skipping re-execution")
            return {
                'status': 'skipped',
                'reason': f'Task already in state: {subtask.status.value}',
                'service_name': service_name,
                'subtask_id': subtask_id
            }

        # Mark as running (with distributed lock to prevent SQLite I/O errors)
        with database_write_lock(f"subtask_{subtask_id}_start"):
            # Re-check status inside lock (double-check pattern)
            db.session.refresh(subtask)
            if subtask.status != AnalysisStatus.PENDING:
                logger.info(f"[CELERY] Subtask {subtask_id} status changed to {subtask.status.value}, skipping")
                return {
                    'status': 'skipped',
                    'reason': f'Task status changed: {subtask.status.value}',
                    'service_name': service_name,
                    'subtask_id': subtask_id
                }
            subtask.status = AnalysisStatus.RUNNING
            subtask.started_at = datetime.now(timezone.utc)
            subtask.current_step = f"Starting {service_name} analysis..."
            subtask.progress_percentage = 10.0
            db.session.commit()

        # Execute via WebSocket using the pooled analyzer manager
        from app.services.analyzer_manager_wrapper import get_analyzer_wrapper
        
        # Update progress before execution
        with database_write_lock(f"subtask_{subtask_id}_progress"):
            subtask.current_step = f"Running {service_name} analyzer with {len(tools)} tools..."
            subtask.progress_percentage = 30.0
            db.session.commit()

        # For dynamic/performance analysis, ensure app containers are running
        # This handles cases where the daemon dispatches without pipeline container startup
        if service_name in ('dynamic-analyzer', 'performance-tester'):
            try:
                from app.services.docker_manager import DockerManager
                import time as _time
                
                dm = DockerManager()
                containers = dm.get_project_containers(model_slug, app_number)
                containers_running = bool(containers) and all(
                    c.get('status') == 'running' for c in containers
                )
                
                if not containers_running:
                    logger.info(f"[CELERY] App containers not running for {model_slug} app {app_number}, starting...")
                    with database_write_lock(f"subtask_{subtask_id}_progress"):
                        subtask.current_step = f"Starting app containers for {service_name}..."
                        db.session.commit()
                    
                    if containers:
                        start_result = dm.start_containers(model_slug, app_number)
                    else:
                        start_result = dm.build_containers(model_slug, app_number, no_cache=False, start_after=True)
                    
                    if start_result.get('success'):
                        logger.info(f"[CELERY] Containers started for {model_slug} app {app_number}, waiting for readiness...")
                        # Wait for containers to be healthy (up to 90s)
                        deadline = _time.time() + 90
                        while _time.time() < deadline:
                            health = dm.get_container_health(model_slug, app_number)
                            if health.get('all_healthy'):
                                logger.info(f"[CELERY] Containers healthy for {model_slug} app {app_number}")
                                break
                            # Check for crash
                            crash = dm._check_for_crash_loop(model_slug, app_number)
                            if crash.get('has_crash_loop'):
                                logger.warning(f"[CELERY] Container crash detected for {model_slug} app {app_number}")
                                break
                            _time.sleep(3)
                    else:
                        logger.warning(f"[CELERY] Failed to start containers for {model_slug} app {app_number}: {start_result.get('error')}")
                else:
                    logger.info(f"[CELERY] App containers already running for {model_slug} app {app_number}")
            except Exception as container_err:
                logger.warning(f"[CELERY] Container startup check failed for {model_slug} app {app_number}: {container_err}")
        
        wrapper = get_analyzer_wrapper()
        
        # Map service name to wrapper method
        result = {}
        if service_name == 'static-analyzer':
            result = wrapper.run_static_analysis(model_slug, app_number, tools)
        elif service_name == 'dynamic-analyzer':
             result = wrapper.run_dynamic_analysis(model_slug, app_number, tools=tools)
        elif service_name == 'performance-tester':
             result = wrapper.run_performance_test(model_slug, app_number, tools=tools)
        elif service_name == 'ai-analyzer':
             result = wrapper.run_ai_analysis(model_slug, app_number, tools=tools)
        else:
             # Fallback to generic if needed, or error
             raise ValueError(f"Unknown service: {service_name}")
        
        # Store result (with distributed lock to prevent SQLite I/O errors)
        status = str(result.get('status', '')).lower()
        success = status in ('success', 'completed', 'ok', 'partial')
        is_partial = status == 'partial'

        with database_write_lock(f"subtask_{subtask_id}_complete"):
            subtask.status = AnalysisStatus.PARTIAL_SUCCESS if is_partial else (AnalysisStatus.COMPLETED if success else AnalysisStatus.FAILED)
            subtask.completed_at = datetime.now(timezone.utc)
            subtask.progress_percentage = 100.0

            # Set completion message
            if success:
                subtask.current_step = f"✓ {service_name} analysis completed successfully"
            elif is_partial:
                subtask.current_step = f"⚠ {service_name} analysis completed with warnings"
            else:
                subtask.current_step = f"✗ {service_name} analysis failed"

            # Wrapper results are usually {status:..., payload:...} or just the payload if success?
            # AnalyzerManagerWrapper guarantees strict return shapes usually.
            # Let's handle generic structure.
            
            payload = result.get('payload', result) if 'payload' in result else result
            
            if payload:
                subtask.set_result_summary(payload)

            if result.get('error'):
                subtask.error_message = result['error']

            db.session.commit()
        
        return {
            'status': result.get('status', 'success' if success else 'error'),
            'payload': payload,
            'error': result.get('error'),
            'service_name': service_name,
            'subtask_id': subtask_id
        }
        
    except Exception as e:
        logger.error(f"[CELERY] Subtask {subtask_id} failed: {e}", exc_info=True)
        try:
            subtask = AnalysisTask.query.get(subtask_id)
            if subtask:
                with database_write_lock(f"subtask_{subtask_id}_error"):
                    subtask.status = AnalysisStatus.FAILED
                    subtask.error_message = str(e)
                    subtask.completed_at = datetime.now(timezone.utc)
                    db.session.commit()
        except Exception as db_err:
            logger.warning(f"Failed to update subtask {subtask_id} status in DB: {db_err}", exc_info=True)
        return {'status': 'error', 'error': str(e), 'service_name': service_name}

@celery.task(bind=True)
def execute_analysis(self, task_id: int) -> Dict[str, Any]:
    """
    Execute a full analysis task (comprehensive or specific type).
    
    Idempotency: If task is already RUNNING/COMPLETED/FAILED, skip re-execution.
    """
    logger.info(f"[CELERY] Starting analysis task {task_id}")

    from app.services.analyzer_manager_wrapper import get_analyzer_wrapper

    try:
        # Get fresh task from DB
        task = AnalysisTask.query.get(task_id)
        if not task:
            return {'status': 'error', 'error': f'Task {task_id} not found'}
        
        # Idempotency guard: Skip if already in a terminal state
        # NOTE: We allow RUNNING status because the polling loop may have already set it
        # before dispatching to Celery. This is expected behavior.
        if task.status in (AnalysisStatus.COMPLETED, AnalysisStatus.FAILED, 
                           AnalysisStatus.PARTIAL_SUCCESS):
            logger.info(f"[CELERY] Task {task_id} already in terminal state {task.status.value}, skipping re-execution")
            return {
                'status': 'skipped',
                'reason': f'Task already in state: {task.status.value}',
                'task_id': task_id
            }
        
        # Mark as running (with distributed lock)
        with database_write_lock(f"task_{task_id}_start"):
            # Re-check status inside lock (double-check pattern)
            db.session.refresh(task)
            # Allow PENDING or RUNNING (polling loop may set RUNNING before Celery picks up)
            if task.status not in (AnalysisStatus.PENDING, AnalysisStatus.RUNNING):
                logger.info(f"[CELERY] Task {task_id} status changed to {task.status.value}, skipping")
                return {
                    'status': 'skipped',
                    'reason': f'Task status changed: {task.status.value}',
                    'task_id': task_id
                }
            task.status = AnalysisStatus.RUNNING
            task.started_at = datetime.now(timezone.utc)
            task.progress_percentage = 10.0
            db.session.commit()
        
        # Get wrapper
        wrapper = get_analyzer_wrapper()
        
        # Extract tool names from metadata
        meta = task.get_metadata() if hasattr(task, 'get_metadata') else {}
        custom_options = meta.get('custom_options', {})
        tool_names = custom_options.get('tools') or custom_options.get('selected_tool_names') or []
        
        # Determine analysis type
        analysis_type_map = {
            'security': 'security',
            'static': 'static',
            'dynamic': 'dynamic',
            'performance': 'performance',
            'ai': 'ai',
            'comprehensive': 'comprehensive'
        }
        analysis_method = analysis_type_map.get(task.task_name, 'comprehensive')
        
        logger.info(f"[CELERY] Running {analysis_method} analysis for task {task.task_id}")
        
        # Update progress (with distributed lock)
        with database_write_lock(f"task_{task_id}_progress"):
            task.progress_percentage = 30.0
            db.session.commit()
        
        # Execute analysis
        task_name = task.task_id
        
        if analysis_method == 'comprehensive':
            result = wrapper.run_comprehensive_analysis(
                model_slug=task.target_model,
                app_number=task.target_app_number,
                task_name=task_name,
                tools=tool_names if tool_names else None
            )
        elif analysis_method == 'security':
            result = {'security': wrapper.run_security_analysis(task.target_model, task.target_app_number, tool_names)}
        elif analysis_method == 'static':
            result = {'static': wrapper.run_static_analysis(task.target_model, task.target_app_number, tool_names)}
        elif analysis_method == 'dynamic':
            result = {'dynamic': wrapper.run_dynamic_analysis(task.target_model, task.target_app_number, tools=tool_names)}
        elif analysis_method == 'performance':
            result = {'performance': wrapper.run_performance_test(task.target_model, task.target_app_number, tools=tool_names)}
        elif analysis_method == 'ai':
            result = {'ai': wrapper.run_ai_analysis(task.target_model, task.target_app_number, tools=tool_names)}
        else:
            raise ValueError(f"Unknown analysis type: {analysis_method}")
            
        # Process results (similar to TaskExecutionService logic)
        # For comprehensive, result is already consolidated. For others, it's a dict of services.
        
        # Update progress (with distributed lock)
        with database_write_lock(f"task_{task_id}_progress_90"):
            task.progress_percentage = 90.0
            db.session.commit()
        
        # Determine status
        # If result has 'results' key, it's likely the consolidated format from comprehensive
        if 'results' in result and 'summary' in result.get('results', {}):
            summary = result['results']['summary']
            status = summary.get('status', 'completed')
            payload = result
        else:
            # Simple service result
            payload = {'services': result}
            # Check status of services
            statuses = [v.get('status') for v in result.values() if isinstance(v, dict)]
            if all(s == 'success' for s in statuses):
                status = 'completed'
            elif any(s == 'success' for s in statuses):
                status = 'partial'
            else:
                status = 'failed'
                
        success = status in ('completed', 'partial', 'success')
        is_partial = status == 'partial'
        
        task.status = AnalysisStatus.PARTIAL_SUCCESS if is_partial else (AnalysisStatus.COMPLETED if success else AnalysisStatus.FAILED)
        task.completed_at = datetime.now(timezone.utc)
        task.progress_percentage = 100.0
        
        # Store result summary (with distributed lock)
        with database_write_lock(f"task_{task_id}_complete"):
            task.set_result_summary(payload)

            # Update issues count - extract from various result formats
            total_issues = _extract_total_issues(payload)
            
            task.issues_found = total_issues
            logger.info(f"[CELERY] Task {task.task_id} completed with {total_issues} issues found")

            db.session.commit()
        
        return {'status': status, 'task_id': task_id}
        
    except Exception as e:
        logger.error(f"[CELERY] Analysis task {task_id} failed: {e}", exc_info=True)
        try:
            task = AnalysisTask.query.get(task_id)
            if task:
                with database_write_lock(f"task_{task_id}_error"):
                    task.status = AnalysisStatus.FAILED
                    task.error_message = str(e)
                    task.completed_at = datetime.now(timezone.utc)
                    db.session.commit()
        except Exception as db_err:
            logger.warning(f"Failed to update task {task_id} status in DB: {db_err}", exc_info=True)
        return {'status': 'error', 'error': str(e)}

@celery.task(bind=True)
def aggregate_results(self, results: List[Dict[str, Any]], main_task_id: str) -> Dict[str, Any]:
    """
    Aggregate results from parallel subtasks.
    
    Idempotency: If main task is already COMPLETED/FAILED, skip aggregation.
    """
    logger.info(f"[CELERY] Aggregating {len(results)} results for main task {main_task_id}")
    
    try:
        main_task = AnalysisTask.query.filter_by(task_id=main_task_id).first()
        if not main_task:
            return {'status': 'error', 'error': 'Main task not found'}
        
        # Idempotency guard: Skip if main task already finalized
        if main_task.status in (AnalysisStatus.COMPLETED, AnalysisStatus.FAILED, 
                                 AnalysisStatus.PARTIAL_SUCCESS, AnalysisStatus.CANCELLED):
            logger.info(f"[CELERY] Main task {main_task_id} already in state {main_task.status.value}, skipping aggregation")
            return {
                'status': 'skipped',
                'reason': f'Main task already finalized: {main_task.status.value}',
                'main_task_id': main_task_id
            }
            
        all_services = {}
        all_findings = []
        combined_tool_results = {}
        any_failed = False
        any_succeeded = False
        
        # Track which services were in this chord's results
        chord_services = set()
        
        for result in results:
            # Handle potential upstream failures (Celery errors)
            if not isinstance(result, dict):
                logger.error(f"Invalid result format: {result}")
                any_failed = True
                continue
                
            service_name = result.get('service_name', 'unknown')
            all_services[service_name] = result
            chord_services.add(service_name)
            
            if result.get('status') not in ('success', 'completed', 'partial'):
                any_failed = True
            else:
                any_succeeded = True
            
            payload = result.get('payload', {})
            if isinstance(payload, dict):
                # Data may be at payload level or nested under payload.analysis
                analysis = payload.get('analysis', {}) if isinstance(payload.get('analysis'), dict) else {}
                
                findings = payload.get('findings', []) or analysis.get('findings', [])
                if isinstance(findings, list):
                    all_findings.extend(findings)
                
                tool_results = payload.get('tool_results', {}) or analysis.get('tool_results', {})
                if isinstance(tool_results, dict):
                    combined_tool_results.update(tool_results)

        # Merge results from already-completed subtasks not in this chord (partial retry case)
        all_subtasks = list(main_task.subtasks) if hasattr(main_task, 'subtasks') else []
        for st in all_subtasks:
            if st.service_name in chord_services:
                continue  # Already included from chord results
            if st.status in (AnalysisStatus.COMPLETED, AnalysisStatus.PARTIAL_SUCCESS):
                prev = st.get_result_summary() if hasattr(st, 'get_result_summary') else {}
                if prev and isinstance(prev, dict):
                    svc_status = 'success' if st.status == AnalysisStatus.COMPLETED else 'partial'
                    all_services[st.service_name] = {
                        'status': svc_status,
                        'payload': prev,
                        'error': None,
                        'service_name': st.service_name,
                        'subtask_id': st.id
                    }
                    any_succeeded = True
                    # Merge tool results from previous run
                    if isinstance(prev, dict):
                        analysis_data = prev.get('analysis', prev)
                        if isinstance(analysis_data, dict):
                            prev_tools = analysis_data.get('tool_results', {})
                            if isinstance(prev_tools, dict):
                                combined_tool_results.update(prev_tools)
                    logger.info(f"[CELERY] Merged prior result for {st.service_name} (subtask {st.id})")

        # Determine status: ALL failed → FAILED; ALL succeeded → COMPLETED; mixed → PARTIAL_SUCCESS
        if any_succeeded and any_failed:
            final_status = 'partial'
            final_db_status = AnalysisStatus.PARTIAL_SUCCESS
        elif any_failed:
            final_status = 'failed'
            final_db_status = AnalysisStatus.FAILED
        else:
            final_status = 'completed'
            final_db_status = AnalysisStatus.COMPLETED

        # Build unified payload
        # Compute total findings from service-level data (not just flat findings list)
        total_findings = _extract_total_issues({
            'services': all_services,
            'tools': combined_tool_results,
        })
        # Fall back to flat findings list if service extraction found nothing
        if total_findings == 0 and all_findings:
            total_findings = len(all_findings)

        unified_payload = {
            'task': {'task_id': main_task_id},
            'summary': {
                'total_findings': total_findings,
                'services_executed': len(all_services),
                'tools_executed': len(combined_tool_results),
                'status': final_status
            },
            'services': all_services,
            'tools': combined_tool_results,
            'findings': all_findings,
            'metadata': {
                'unified_analysis': True,
                'orchestrator_version': '3.0.0',
                'executor': 'Celery',
                'generated_at': datetime.now(timezone.utc).isoformat()
            }
        }
        
        # Update main task (with distributed lock + idempotency re-check)
        with database_write_lock(f"task_{main_task_id}_aggregate"):
            # Re-check status inside lock to prevent TOCTOU race
            db.session.refresh(main_task)
            if main_task.status in (AnalysisStatus.COMPLETED, AnalysisStatus.FAILED, 
                                     AnalysisStatus.PARTIAL_SUCCESS, AnalysisStatus.CANCELLED):
                logger.info(f"[CELERY] Main task {main_task_id} already finalized inside lock ({main_task.status.value}), skipping")
                return {
                    'status': 'skipped',
                    'reason': f'Main task already finalized: {main_task.status.value}',
                    'main_task_id': main_task_id
                }
            
            main_task.status = final_db_status
            main_task.completed_at = datetime.now(timezone.utc)
            main_task.progress_percentage = 100.0
            main_task.issues_found = total_findings

            # Extract and merge severity breakdown from all services
            merged_severity = {}
            for svc_result in all_services.values():
                if not isinstance(svc_result, dict):
                    continue
                svc_analysis = svc_result.get('analysis', {})
                if not isinstance(svc_analysis, dict) or not svc_analysis:
                    p = svc_result.get('payload', {})
                    if isinstance(p, dict):
                        svc_analysis = p.get('analysis', p)
                if isinstance(svc_analysis, dict):
                    sb = svc_analysis.get('summary', {}).get('severity_breakdown', {})
                    if isinstance(sb, dict):
                        for level, count in sb.items():
                            if isinstance(count, (int, float)) and count > 0:
                                merged_severity[level] = merged_severity.get(level, 0) + int(count)
            if merged_severity:
                main_task.set_severity_breakdown(merged_severity)

            if main_task.started_at:
                 # Ensure started_at is timezone-aware
                started_at = main_task.started_at
                if started_at.tzinfo is None:
                    started_at = started_at.replace(tzinfo=timezone.utc)
                duration = (main_task.completed_at - started_at).total_seconds()
                main_task.actual_duration = duration

            main_task.set_result_summary(unified_payload)
            db.session.commit()
        
        # Write to filesystem (we need to duplicate this logic or import it)
        # Ideally, we should use a shared service for this.
        # For now, we'll rely on the TaskExecutionService to handle filesystem writes 
        # if it's polling, OR we implement it here.
        # Since this is a background task, we should write it here.
        try:
            _write_results_to_fs(main_task, unified_payload)
        except Exception as e:
            logger.error(f"Failed to write results to filesystem: {e}")

        # Cleanup: Stop and remove the analyzed app containers after successful analysis
        try:
            _cleanup_app_containers(main_task.target_model, main_task.target_app_number)
        except Exception as e:
            logger.warning(f"Failed to cleanup containers after analysis: {e}")

        return unified_payload

    except Exception as e:
        logger.error(f"[CELERY] Aggregation failed: {e}", exc_info=True)
        if main_task:
            with database_write_lock(f"task_{main_task_id}_aggregate_error"):
                main_task.status = AnalysisStatus.FAILED
                main_task.error_message = str(e)
                db.session.commit()
        return {'status': 'error', 'error': str(e)}

def _run_websocket_sync(service_name: str, model_slug: str, app_number: int, tools: List[str], timeout: int = 600) -> Dict[str, Any]:
    """Helper to run async WebSocket code synchronously."""
    import os
    import websockets
    from websockets.exceptions import ConnectionClosed
    import time
    
    SERVICE_PORTS = {
        'static-analyzer': 2001,
        'dynamic-analyzer': 2002,
        'performance-tester': 2003,
        'ai-analyzer': 2004
    }
    port = SERVICE_PORTS.get(service_name)
    if not port:
        return {'status': 'error', 'error': f'Unknown service: {service_name}'}
    
    # Resolve target URLs for dynamic/performance analysis
    target_urls = []
    if service_name in ('dynamic-analyzer', 'performance-tester'):
        try:
            from app.services.analyzer_manager_wrapper import get_analyzer_wrapper
            analyzer_mgr = get_analyzer_wrapper().manager
            ports = analyzer_mgr._resolve_app_ports(model_slug, app_number)
            if ports:
                backend_port, frontend_port = ports
                # Decide if analyzers/apps are running in Docker via AnalyzerManager
                try:
                    is_docker = analyzer_mgr._is_running_in_docker()
                except Exception:
                    is_docker = os.environ.get('IN_DOCKER', '').lower() in ('true', '1', 'yes')

                # Also consider configured analyzer URLs as an indicator (docker-compose uses container names)
                da_urls = os.environ.get('DYNAMIC_ANALYZER_URLS', '') + os.environ.get('DYNAMIC_ANALYZER_URL', '')
                if not is_docker and da_urls and service_name in da_urls:
                    is_docker = True
                    logger.debug(f"Inferred Docker environment for {service_name} from DYNAMIC_ANALYZER_URL(S)")

                if is_docker:
                    # Look up build_id from RUNNING containers first (authoritative source)
                    # Fall back to database only if no running containers found
                    build_id = None
                    try:
                        from app.services.service_locator import ServiceLocator
                        docker_mgr = ServiceLocator.get_docker_manager()
                        if docker_mgr:
                            build_id = docker_mgr.get_running_build_id(model_slug, app_number)
                            if build_id:
                                logger.debug(f"[CELERY] Using build_id from running container: {build_id}")
                    except Exception as e:
                        logger.debug(f"[CELERY] Could not get build_id from Docker: {e}")
                    
                    # Fall back to database if not found in running containers
                    if not build_id:
                        try:
                            from app.models import GeneratedApplication
                            app_record = GeneratedApplication.query.filter_by(
                                model_slug=model_slug, app_number=app_number
                            ).first()
                            if app_record and app_record.build_id:
                                build_id = app_record.build_id
                                logger.debug(f"[CELERY] Using build_id from database (no running container): {build_id}")
                        except Exception as e:
                            logger.debug(f"[CELERY] Could not lookup build_id from database: {e}")
                    
                    safe_slug = model_slug.replace('_', '-').replace('.', '-')
                    if build_id:
                        container_prefix = f"{safe_slug}-app{app_number}-{build_id}"
                    else:
                        container_prefix = f"{safe_slug}-app{app_number}"
                    # Container-to-container: use resolved internal ports when available
                    target_urls = [
                        f"http://{container_prefix}_backend:{backend_port}",
                        f"http://{container_prefix}_frontend:80"
                    ]
                    logger.info(f"[CELERY] Resolved target URLs for {service_name} (container network, build_id={build_id}): {target_urls}")
                else:
                    target_urls = [
                        f"http://localhost:{backend_port}",
                        f"http://localhost:{frontend_port}"
                    ]
                    logger.info(f"[CELERY] Resolved target URLs for {service_name} (localhost ports): {target_urls}")
            else:
                logger.warning(f"[CELERY] Could not resolve ports for {model_slug}/app{app_number}")
        except Exception as e:
            logger.warning(f"[CELERY] Error resolving ports: {e}")

    # Resolve AI config for ai-analyzer (template_slug, ports)
    ai_config = None
    if service_name == 'ai-analyzer':
        try:
            from app.services.analyzer_manager_wrapper import get_analyzer_wrapper
            analyzer_mgr = get_analyzer_wrapper().manager
            ai_config = analyzer_mgr._resolve_ai_config(model_slug, app_number, tools)
            if ai_config:
                logger.info(f"[CELERY] Resolved AI config for {service_name}: template={ai_config.get('template_slug')}")
            else:
                logger.warning(f"[CELERY] Could not resolve AI config for {model_slug}/app{app_number}")
        except Exception as e:
            logger.warning(f"[CELERY] Error resolving AI config: {e}")

    async def _ws_client():
        uri = f'ws://analyzer-gateway:8765' # Use gateway if possible, or direct service
        # In docker-compose, services are reachable by name.
        # But here we are in 'celery-worker' container.
        # We can try direct connection to service container.
        uri = f'ws://{service_name}:{port}'
        
        MESSAGE_TYPES = {
            'static-analyzer': 'static_analyze',
            'dynamic-analyzer': 'dynamic_analyze',
            'ai-analyzer': 'ai_analyze',
            'performance-tester': 'performance_test'
        }
        msg_type = MESSAGE_TYPES.get(service_name, 'analysis_request')
        
        req = {
            'type': msg_type,
            'model_slug': model_slug,
            'app_number': app_number,
            'tools': tools,
            'id': f"{model_slug}_app{app_number}_{service_name}_celery",
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        # Add target_urls for dynamic/performance analysis
        if target_urls:
            req['target_urls'] = target_urls
            # Legacy support for performance-tester
            if service_name == 'performance-tester':
                req['target_url'] = target_urls[0]
            logger.info(f"[CELERY] Added target_urls to {service_name} request: {target_urls}")
        
        # Add AI analyzer config (template_slug, ports, etc.)
        if service_name == 'ai-analyzer' and ai_config:
            req['config'] = ai_config
            logger.info(f"[CELERY] Added AI config to request: template_slug={ai_config.get('template_slug')}")
        
        logger.info(f"[CELERY] Connecting to {service_name} at {uri}...")
        
        try:
            async with websockets.connect(
                uri,
                open_timeout=10,
                close_timeout=10,
                ping_interval=30,
                ping_timeout=10,
                max_size=100 * 1024 * 1024,  # 100MB to match server
            ) as ws:
                await ws.send(json.dumps(req))
                
                deadline = time.time() + timeout
                terminal_result = None
                
                while time.time() < deadline:
                    try:
                        resp = await asyncio.wait_for(ws.recv(), timeout=10.0)  # Increased from 5s to 10s
                        frame = json.loads(resp)

                        # Check for terminal frame
                        ftype = str(frame.get('type', '')).lower()
                        has_analysis = isinstance(frame.get('analysis'), dict)
                        fstatus = str(frame.get('status', '')).lower()

                        # Ignore non-terminal messages (status updates, progress)
                        if ftype in ('status_update', 'progress_update', 'progress'):
                            logger.debug(f"[CELERY] Received {ftype}: {frame.get('message', 'N/A')}")
                            continue

                        # Terminal detection: result frames OR frames with analysis data
                        is_terminal = (
                            ('analysis_result' in ftype) or
                            ('_result' in ftype and has_analysis) or
                            (ftype.endswith('_analysis') and has_analysis) or
                            (fstatus in ('success', 'completed') and has_analysis) or
                            (ftype == 'result' and has_analysis)
                        )

                        if is_terminal:
                            terminal_result = {
                                'status': frame.get('status', 'success'),
                                'payload': frame.get('analysis', frame),
                                'error': frame.get('error')
                            }
                            logger.info(f"[CELERY] Received terminal result from {service_name}")
                            break
                    except asyncio.TimeoutError:
                        # No message in 10 seconds - continue waiting
                        continue
                    except ConnectionClosed as cc:
                        # Close code 1000 means normal closure - this is OK
                        if cc.code == 1000 and terminal_result:
                            break
                        elif cc.code == 1000:
                            # Normal close but no result yet - might be in the close reason
                            logger.warning(f"Connection closed normally (1000) before receiving result")
                            break
                        else:
                            return {'status': 'error', 'error': f'Connection closed with code {cc.code}: {cc.reason}'}
                
                if terminal_result:
                    return terminal_result
                return {'status': 'timeout', 'error': 'Analysis timed out waiting for result'}
                
        except ConnectionClosed as cc:
            # Handle close during handshake or initial communication
            if cc.code == 1000:
                logger.warning(f"Connection closed normally during {service_name} analysis")
                return {'status': 'error', 'error': 'Connection closed before result received'}
            return {'status': 'error', 'error': f'WebSocket closed with code {cc.code}: {cc.reason}'}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_ws_client())
    finally:
        loop.close()

def _write_results_to_fs(task, payload):
    """Write results to filesystem (simplified version)."""
    from pathlib import Path
    
    # We need to reconstruct the path logic
    # Assuming we are in /app/src/app/tasks.py -> /app/results
    results_base = Path('/app/results')
    if not results_base.exists():
        # Fallback for local dev
        results_base = Path(__file__).parent.parent.parent.parent / 'results'
        
    safe_slug = task.target_model.replace('/', '_')
    task_folder = task.task_id if task.task_id.startswith('task_') else f"task_{task.task_id}"
    
    out_dir = results_base / safe_slug / f"app{task.target_app_number}" / task_folder
    out_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{safe_slug}_app{task.target_app_number}_{task_folder}_{timestamp}.json"
    
    with open(out_dir / filename, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2, default=str)
        
    # Write manifest
    manifest = {
        'task_id': task.task_id,
        'status': 'completed',
        'main_result_file': filename,
        'timestamp': datetime.now().isoformat()
    }
    with open(out_dir / 'manifest.json', 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)


def _cleanup_app_containers(model_slug: str, app_number: int) -> None:
    """Stop and remove containers for the analyzed app after analysis completes.
    
    This frees up resources by removing containers that are no longer needed
    after analysis is complete.
    """
    try:
        from app.services.docker_manager import DockerManager
        
        docker_mgr = DockerManager()
        result = docker_mgr.stop_containers(model_slug, app_number)
        
        if result.get('success'):
            logger.info(f"[CLEANUP] Stopped containers for {model_slug} app {app_number}")
        else:
            logger.warning(f"[CLEANUP] Failed to stop containers for {model_slug} app {app_number}: {result.get('error')}")
            
    except Exception as e:
        logger.warning(f"[CLEANUP] Error cleaning up containers for {model_slug} app {app_number}: {e}")
